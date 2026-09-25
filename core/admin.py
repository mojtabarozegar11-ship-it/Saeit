from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .chat_runtime import MasterAgentChat
from .models import (
    Agent,
    AgentCapability,
    AgentTask,
    ApprovalRequest,
    AuditLog,
    ChatMessage,
    ChatSession,
    Evidence,
    Finding,
    KnowledgeArticle,
    Order,
    Product,
    Report,
    ResearchProject,
    ResearchSource,
)


class ChatSessionAdmin(ModelAdmin):
    change_list_template = "admin/core/chatsession/change_list.html"
    list_display = ("id", "user", "title", "status", "created_at", "updated_at")
    search_fields = ("title", "user__username")
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(user=request.user)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "master-agent-chat/",
                self.admin_site.admin_view(self.chat_console),
                name="core_chatsession_master_agent_chat",
            ),
        ]
        return custom + urls

    def chat_console(self, request):
        session_id = request.GET.get("session")
        session = None
        if session_id:
            session = ChatSession.objects.filter(pk=session_id, user=request.user).first()

        if session is None:
            session = ChatSession.objects.create(
                user=request.user,
                title="Master Agent",
            )

        if request.method == "POST":
            message = str(request.POST.get("message", "")).strip()
            if message:
                MasterAgentChat().respond(session, message)
            return HttpResponseRedirect(
                f"{reverse('admin:core_chatsession_master_agent_chat')}?session={session.pk}"
            )

        messages = session.messages.order_by("created_at")
        sessions = ChatSession.objects.filter(user=request.user).order_by("-updated_at")[:30]
        context = {
            **self.admin_site.each_context(request),
            "title": "چت با Master Agent",
            "session": session,
            "messages": messages,
            "sessions": sessions,
            "opts": self.model._meta,
        }
        return TemplateResponse(
            request,
            "admin/core/master_agent_chat.html",
            context,
        )


admin.site.register(ChatSession, ChatSessionAdmin)

admin.site.register([
    ResearchProject,
    ResearchSource,
    Evidence,
    Finding,
    Report,
    Agent,
    AgentCapability,
    AgentTask,
    ChatMessage,
    ApprovalRequest,
    AuditLog,
    KnowledgeArticle,
    Product,
    Order,
])

from .newsletter_models import NewsletterAgentLink, NewsletterOccasion, NewsletterPublication, NewsletterSchedule, NewsletterSource, NewsletterStory, NewsletterSubmission


@admin.register(NewsletterSubmission)
class NewsletterSubmissionAdmin(ModelAdmin):
    list_display = ("subject", "status", "created_by", "created_at", "generated_story")
    list_filter = ("status", "created_at")
    search_fields = ("subject", "body")
    readonly_fields = ("status", "processed_at", "generated_story", "created_at")
    fields = ("subject", "body", "image", "video", "requested_publish_at", "occasion_code", "status", "created_by", "generated_story", "created_at", "processed_at")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        if obj.status == "queued":
            from .newsletter_engine import process_submission
            process_submission(obj)


@admin.register(NewsletterStory)
class NewsletterStoryAdmin(ModelAdmin):
    list_display = ("title", "story_type", "status", "published_at", "author_name")
    list_filter = ("status", "story_type", "published_at")
    search_fields = ("title", "summary", "body", "author_name")
    date_hierarchy = "published_at"
    fieldsets = (
        ("محتوا", {"fields": ("agent", "story_type", "title", "summary", "body", "seo_keywords", "image", "video")}),
        ("زمان‌بندی و هویت", {"fields": ("author_name", "event_date", "company_activity_kind", "manager_action", "published_at", "status")}),
        ("منبع و کنترل تکرار", {"fields": ("source", "fingerprint", "source_fingerprint")}),
    )
    readonly_fields = ("fingerprint", "source_fingerprint")

    def save_model(self, request, obj, form, change):
        obj.author_name = "مجتبی روزگار"
        super().save_model(request, obj, form, change)


admin.site.register([NewsletterAgentLink, NewsletterOccasion, NewsletterPublication, NewsletterSchedule, NewsletterSource])

from .blog_models import BlogDistributionPlan, BlogPage, BlogPublication, BlogTranslation, ExternalBlogTarget
admin.site.register([BlogDistributionPlan, BlogPage, BlogPublication, BlogTranslation, ExternalBlogTarget])

from .company_content_models import CompanyContentLink, CompanyGalleryMedia

@admin.register(CompanyContentLink)
class CompanyContentLinkAdmin(admin.ModelAdmin):
    list_display = ("content_type", "relation", "target_path", "newsletter_story", "knowledge_article", "created_at")
    list_filter = ("content_type", "relation")
    search_fields = ("target_path", "note")

@admin.register(CompanyGalleryMedia)
class CompanyGalleryMediaAdmin(admin.ModelAdmin):
    list_display = ("title", "media_type", "research_domain", "target_path", "published", "published_at")
    list_filter = ("media_type", "published", "research_domain")
    search_fields = ("title", "description", "target_path", "research_domain", "project_label")
    fields = ("media_type", "title", "description", "image", "video", "target_path", "newsletter_story", "project_label", "research_domain", "tags", "published", "published_at")
