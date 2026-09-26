from django.http import Http404
from django.shortcuts import render
from django.utils.html import strip_tags

from .knowledge_agent_models import KnowledgeBook, KnowledgeDomain
from .models import KnowledgeArticle


def _meta(text, limit=155):
    value = " ".join(strip_tags(str(text or "")).split())
    return value[:limit].rstrip() + ("…" if len(value) > limit else "")


def knowledge_article_detail(request, slug):
    article = KnowledgeArticle.objects.select_related("source_report__project").filter(slug=slug, published=True).first()
    if not article:
        raise Http404
    related = KnowledgeArticle.objects.filter(published=True).exclude(pk=article.pk).order_by("-updated_at")[:6]
    context = {"article": article, "related": related, "meta": _meta(article.content)}
    return render(request, "core/knowledge_article_detail.html", context)


def knowledge_book_detail(request, slug):
    book = KnowledgeBook.objects.select_related("plan", "domain_ref").filter(code=slug).first()
    if not book:
        raise Http404
    related = KnowledgeBook.objects.filter(plan=book.plan).exclude(pk=book.pk).order_by("id")[:6]
    context = {"book": book, "related": related, "meta": _meta(book.objective), "free": bool(book.plan and book.plan.public_free)}
    return render(request, "core/knowledge_book_detail.html", context)


def knowledge_domain_detail(request, slug):
    domain = KnowledgeDomain.objects.filter(code=slug, active=True).first()
    if not domain:
        raise Http404
    books = KnowledgeBook.objects.filter(domain_ref=domain).order_by("id")
    articles = KnowledgeArticle.objects.filter(published=True, title__icontains=domain.title[:40]).order_by("-updated_at")[:12]
    context = {"domain": domain, "books": books, "articles": articles, "meta": _meta(domain.scientific_scope)}
    return render(request, "core/knowledge_domain_detail.html", context)
