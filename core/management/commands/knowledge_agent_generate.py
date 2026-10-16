import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from openai import OpenAI
from core.knowledge_agent_models import KnowledgeAgentRun
from core.models import AgentTask


class Command(BaseCommand):
    help = "Execute one queued Knowledge Content Director generation cycle."

    def handle(self, *args, **options):
        run = KnowledgeAgentRun.objects.filter(status="queued").select_related("book", "plan").first()
        if not run:
            self.stdout.write("KNOWLEDGE_AGENT: no queued run")
            return

        task = AgentTask.objects.filter(
            action_type="knowledge_content_generation",
            input_data__run_id=run.pk,
            status__in=("queued", "running"),
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

        run.status = "running"
        run.save(update_fields=["status"])
        if task:
            task.status = "running"
            task.attempt_count += 1
            task.save(update_fields=["status", "attempt_count", "updated_at"])

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
