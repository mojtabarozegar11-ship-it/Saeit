from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from .daily_content_models import DailyContentPlan, DailyContentDraft
from .models import Agent, AgentCapability, KnowledgeArticle


COMPANY_PROMPT = "شرکت کشت و صنعت زمرد ملل"
CEO_PROMPT = "مجتبی روزگار"
QUESTION_MARK = "؟"


class DailyContentPlanner:
    """Create exactly two distinct daily question-led content slots."""

    @transaction.atomic
    def ensure_plan(self, project, run_date=None, company_topic=None, ceo_topic=None):
        run_date = run_date or date.today()
        company_topic = (company_topic or "" ).strip() or "" 
        ceo_topic = (ceo_topic or "").strip() or ""
        if not company_topic:
            company_topic = f"{COMPANY_PROMPT} چیست و چه زمینه‌هایی را دنبال می‌کند"
        if not ceo_topic:
            ceo_topic = f"{CEO_PROMPT} کیست و چه سوابق پژوهشی و مدیریتی دارد"
        plan, _ = DailyContentPlan.objects.get_or_create(
            project=project,
            run_date=run_date,
            defaults={
                "company_topic": company_topic,
                "ceo_topic": ceo_topic,
            },
        )
        return plan

    def question_title(self, topic, identity):
        topic = " ".join(str(topic or "").split()).strip(" ؟?")
        if identity not in topic:
            topic = f"{identity}: {topic}"
        title = topic if topic.endswith(QUESTION_MARK) else f"{topic}{QUESTION_MARK}"
        return title[:300]

    @transaction.atomic
    def create_drafts(self, plan, company_content, ceo_content):
        if plan is None or not plan.pk:
            raise ValidationError("A saved daily content plan is required.")
        self._validate_content(company_content)
        self._validate_content(ceo_content)
        rows = []
        specs = [
            ("company", plan.company_topic, COMPANY_PROMPT, company_content),
            ("ceo", plan.ceo_topic, CEO_PROMPT, ceo_content),
        ]
        for kind, topic, identity, content in specs:
            title = self.question_title(topic, identity)
            base_slug = slugify(title, allow_unicode=True) or f"daily-{plan.run_date}-{kind}"
            slug = base_slug
            suffix = 2
            while DailyContentDraft.objects.filter(slug=slug).exclude(plan=plan, kind=kind).exists():
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            draft, _ = DailyContentDraft.objects.update_or_create(
                plan=plan,
                kind=kind,
                defaults={"title": title, "slug": slug, "content": content, "status": "draft"},
            )
            rows.append(draft)
        plan.company_title = rows[0].title
        plan.ceo_title = rows[1].title
        plan.status = "drafts_ready"
        plan.save(update_fields=["company_title", "ceo_title", "status", "updated_at"])
        return rows

    @staticmethod
    def _validate_content(content):
        if not str(content or "").strip():
            raise ValidationError("Daily content draft cannot be empty.")


class DailyContentAgent:
    """Generate/store the site's two daily drafts; publication must be separately approved."""

    code = "daily_content_agent"
    capability_code = "daily_content_generate"

    def prepare(self, project, run_date=None, company_topic=None, ceo_topic=None,
                company_content="", ceo_content=""):
        plan = DailyContentPlanner().ensure_plan(project, run_date, company_topic, ceo_topic)
        return DailyContentPlanner().create_drafts(plan, company_content, ceo_content)

    @staticmethod
    def publish_ready_article(draft, owner):
        """Create an unpublished KnowledgeArticle; /publish/ remains the approval boundary."""
        if draft.status not in {"draft", "approval_pending"}:
            raise ValidationError("Draft is not eligible for publication workflow.")
        existing = draft.knowledge_article
        if existing is not None:
            return existing
        article = KnowledgeArticle.objects.create(
            title=draft.title,
            slug=draft.slug,
            content=draft.content,
            version=1,
            published=False,
        )
        draft.knowledge_article = article
        draft.status = "approval_pending"
        draft.save(update_fields=["knowledge_article", "status", "updated_at"])
        return article
