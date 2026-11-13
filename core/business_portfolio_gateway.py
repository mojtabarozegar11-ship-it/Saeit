"""Read-only source-grounded portfolio inventory for the ONE Mojtaba.bot.ai.

Rows and counts describe local Django state only. They never certify a live
site, SEO traffic, real exchange balance, game rewards, or settled revenue.
No raw customer records, email addresses or payment references are returned.
"""
from __future__ import annotations

from .models import (
    AgentTask, KnowledgeArticle, Order, PaymentIntent, Product, Report,
    ResearchProject, ResearchSource,
)
from .unified_bot_identity import BOT_CODE, FACTORY_CAPABILITIES


DOMAINS = (
    "research", "knowledge", "catalog", "commerce", "content_seo",
    "newsletter", "mojplaywin", "factory", "games", "trading",
)


def _read_db_domain(domain):
    """Use only existing read-only Django model queries. No external calls."""
    if domain == "research":
        return {
            "research_projects": ResearchProject.objects.count(),
            "research_sources": ResearchSource.objects.count(),
            "research_reports": Report.objects.count(),
            "scientific_peer_review_attested": False,
        }
    if domain == "knowledge":
        return {
            "knowledge_articles": KnowledgeArticle.objects.count(),
            "knowledge_articles_marked_published": KnowledgeArticle.objects.filter(
                published=True
            ).count(),
            "books_independently_classified": False,
        }
    if domain == "catalog":
        return {
            "product_rows": Product.objects.count(),
            "active_product_rows": Product.objects.filter(active=True).count(),
            "inactive_product_rows": Product.objects.filter(active=False).count(),
            "customer_delivery_attested": False,
        }
    if domain == "commerce":
        return {
            "order_rows": Order.objects.count(),
            "payment_intent_rows": PaymentIntent.objects.count(),
            "settled_cash_verified": None,
            "external_payment_reconciliation_attested": False,
        }
    if domain == "content_seo":
        from .blog_models import BlogPage, BlogTranslation, BlogPublication
        return {
            "blog_pages": BlogPage.objects.count(),
            "active_blog_pages": BlogPage.objects.filter(active=True).count(),
            "blog_translations": BlogTranslation.objects.count(),
            "internal_publication_rows": BlogPublication.objects.filter(
                internal_page__isnull=False
            ).count(),
            "search_console_metrics_attested": False,
        }
    if domain == "newsletter":
        from .newsletter_models import NewsletterStory
        return {
            "newsletter_stories": NewsletterStory.objects.count(),
            "newsletter_marked_published": NewsletterStory.objects.filter(
                status="published"
            ).count(),
            "external_delivery_attested": False,
        }
    if domain == "mojplaywin":
        from command_center.models import MpwRecord, TENANT
        rows = MpwRecord.objects.filter(tenant=TENANT)
        return {
            "local_main_tenant_records": rows.count(),
            "local_draft_records": rows.filter(state="draft").count(),
            "local_published_records": rows.filter(state="published").count(),
            "checkout_trx_and_delivery_attested": False,
        }
    if domain == "factory":
        canonical = AgentTask.objects.filter(
            agent__code=BOT_CODE,
            action_type__in=FACTORY_CAPABILITIES,
        )
        return {
            "canonical_factory_task_rows": canonical.count(),
            "canonical_factory_tasks_completed": canonical.filter(
                status="completed"
            ).count(),
            "vps_factory_runtime_attested": False,
            "hardware_qa_attested": False,
        }
    raise ValueError("BUSINESS_PORTFOLIO_UNSUPPORTED_LOCAL_DOMAIN")


def inspect_business_portfolio(payload):
    """One allowlisted, tenant-agnostic aggregate read; no model writes."""
    if type(payload) is not dict or set(payload) - {"domain"}:
        raise ValueError("BUSINESS_PORTFOLIO_INVALID_REQUEST")
    domain = payload.get("domain", "all")
    if type(domain) is not str or domain not in (*DOMAINS, "all"):
        raise ValueError("BUSINESS_PORTFOLIO_UNKNOWN_DOMAIN")
    selected = DOMAINS if domain == "all" else (domain,)
    sections = {}
    for item in selected:
        if item in ("games", "trading"):
            sections[item] = {
                "local_django_coverage": "unverified",
                "independent_external_runtime_required": True,
                "live_activity_attested": False,
            }
        else:
            sections[item] = {
                "local_django_coverage": "row_count_only",
                "metrics": _read_db_domain(item),
                "external_business_outcome_attested": False,
            }
    inspected = tuple(
        item for item in selected if item not in ("games", "trading")
    )
    return {
        "action_performed": (
            "Read bounded aggregate inventory from existing Django models "
            "without modifying products, tasks, trades or publications."
        ),
        "verified_effect": bool(inspected),
        "evidence": {
            "kind": "internal_portfolio_row_inventory",
            "requested_domain": domain,
            "inspected_local_domains": inspected,
            "source": "Django SQL row counts only",
            "sections": sections,
        },
        "commercial_publication": False,
        "financial_actions": False,
        "settled_revenue": None,
        "live_runtime_or_market_attestation": False,
    }
