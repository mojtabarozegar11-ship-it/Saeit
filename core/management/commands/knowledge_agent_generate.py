import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from openai import OpenAI
from core.knowledge_agent_models import KnowledgeAgentRun
from core.approval import ApprovalService
from core.models import AgentTask, ApprovalGrant


class Command(BaseCommand):
    help = "Generate one queued knowledge draft only with an explicit, single-use paid-model grant."

    def add_arguments(self, parser):
        parser.add_argument(
            "--approval-grant-id", type=int, default=None,
            help="Owner-issued, one-time grant scoped to this exact generation task and run.",
        )

    def handle(self, *args, **options):
        run = KnowledgeAgentRun.objects.filter(status="queued").select_related("book", "plan").first()
        if not run:
            self.stdout.write("KNOWLEDGE_AGENT: no queued run")
            return

        task = AgentTask.objects.filter(
            action_type="knowledge_content_generation",
            input_data__run_id=run.pk,
            status__in=("queued", "blocked"),
        ).order_by("-id").first()
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            summary = "OPENAI_API_KEY is not configured; no content was fabricated."
            run.status = "blocked"
            run.output_summary = summary
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "output_summary", "finished_at"])
            self._finish_task(task, "blocked", run, summary)
            self.stdout.write("KNOWLEDGE_AGENT: blocked; API key unavailable")
            return

        grant_id = options.get("approval_grant_id")
        if not grant_id:
            # A configured API key is not evidence of authority to incur a cost.
            # Keep the run queued for an eventual, explicitly approved execution.
            if task and task.status == "queued":
                task.status = "blocked"
                task.output_data = {
                    "run_id": run.pk,
                    "approval_required": True,
                    "summary": "Paid model invocation requires an owner-approved, one-time task grant.",
                }
                task.save(update_fields=["status", "output_data", "updated_at"])
            self.stdout.write("KNOWLEDGE_AGENT: awaiting_owner_approved_paid_grant; no API call")
            return

        # Claim and authorize atomically before invoking the billable service.
        # A second worker cannot claim the same queued run or reuse its grant.
        with transaction.atomic():
            claimed = KnowledgeAgentRun.objects.select_for_update().get(pk=run.pk)
            locked_task = AgentTask.objects.select_for_update().filter(pk=task.pk).first() if task else None
            if claimed.status != "queued" or not locked_task or locked_task.status != "queued":
                raise CommandError("Knowledge generation is not queued or approved for execution")
            try:
                grant = ApprovalGrant.objects.select_related("approval").get(pk=grant_id)
            except ApprovalGrant.DoesNotExist as exc:
                raise CommandError("Knowledge generation approval grant does not exist") from exc
            approval = grant.approval
            if (
                approval.status != "approved"
                or approval.action_type != "knowledge_content_generation"
                or approval.target_type != "AgentTask"
                or approval.target_id != str(locked_task.pk)
            ):
                raise CommandError("Approval grant is not for this knowledge generation task")
            try:
                ApprovalService().authorize_grant(grant_id, {
                    "action": "knowledge_content_generation",
                    "run_id": run.pk,
                    "paid_model": True,
                })
            except ValueError as exc:
                raise CommandError(f"Knowledge generation approval denied: {exc}") from exc
            claimed.status = "running"
            claimed.save(update_fields=["status"])
            locked_task.status = "running"
            locked_task.attempt_count += 1
            locked_task.save(update_fields=["status", "attempt_count", "updated_at"])

        run.status = "running"
        task = locked_task

        book = run.book
        from core.knowledge_quality import quality_contract
        contract = quality_contract()
        prompt = f"""برای کتاب «{book.title}» در حوزه «{book.domain}» یک بخش پژوهشی فارسی تولید کن.
این کتابخانه از تاریخ ۲۵ آبان ۱۳۹۸ به بعد در حال توسعه است. هدف: {book.objective}.
ساختار پایه کتاب: {book.outline or []}.
قرارداد کیفیت: {contract}.
الزامات: فقط اطلاعات قابل اتکا و قابل بررسی؛ منبع یا نقل‌قول ساختگی ممنوع؛ ادعاهای نیازمند منبع را علامت‌گذاری کن؛ واقعیت، تحلیل و دیدگاه را جدا کن؛ عدم‌قطعیت را صریح بنویس؛ متن آموزشی، ساختاریافته و مناسب دانشنامه باشد؛ عنوان بخش، متن، منابع/راهنمای اعتبارسنجی و موضوعات مرتبط ارائه شود."""
        try:
            client = OpenAI(api_key=key)
            response = client.chat.completions.create(model=os.getenv("OPENAI_KNOWLEDGE_MODEL", os.getenv("OPENAI_CHAT_MODEL", "gpt-5.6")), messages=[
                {"role":"system","content":"تو مدیر محتوای دانشنامه‌ای کنترل‌شده هستی. جعل منبع، ادعای انتشار، یا تبدیل برنامه آینده به واقعیت ممنوع است."},
                {"role":"user","content":prompt},
            ])
            text = (response.choices[0].message.content or "").strip()
            if not text:
                raise RuntimeError("empty model output")
            book.content = (book.content + "\n\n" + text).strip()
            book.generated_sections += 1
            book.status = "review"
            book.save(update_fields=["content", "generated_sections", "status", "updated_at"])
            summary = f"یک بخش برای {book.title} تولید شد و برای بازبینی ثبت شد."
            run.status = "completed"
            run.output_summary = summary
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "output_summary", "finished_at"])
            self._finish_task(task, "completed", run, summary)
            self.stdout.write(self.style.SUCCESS(f"KNOWLEDGE_AGENT: generated book={book.code} section={book.generated_sections}"))
        except Exception as exc:
            run.status = "failed"
            run.output_summary = str(exc)[:5000]
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "output_summary", "finished_at"])
            self._finish_task(task, "failed", run, run.output_summary)
            raise

    @staticmethod
    def _finish_task(task, status, run, summary):
        if not task:
            return
        task.status = status
        task.output_data = {
            "run_id": run.pk,
            "book_id": run.book_id,
            "approval_required": run.approval_required,
            "summary": summary[:1000],
        }
        task.save(update_fields=["status", "output_data", "updated_at"])
