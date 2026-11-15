from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

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
    EducationTrack, EducationCourse, EducationResource, EducationLesson, EducationPresentation,
    EducationEnrollment, EducationProgress, EducationBookmark, EducationAssessment,
    EducationQuestion, EducationAttempt, EducationCertificate,
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
        # Keep the optional OpenAI client out of Django admin autodiscovery/startup.
        from .chat_runtime import MasterAgentChat

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

@admin.register(EducationTrack)
class EducationTrackAdmin(ModelAdmin):
    list_display = ("title", "key", "level", "active", "sort_order")
    list_filter = ("active", "level")
    search_fields = ("title", "key", "description")
    ordering = ("sort_order", "id")

@admin.register(EducationCourse)
class EducationCourseAdmin(ModelAdmin):
    list_display = ("title", "track", "is_free", "price", "active", "approved", "quality_status", "version")
    list_filter = ("active", "approved", "is_free", "quality_status", "track")
    search_fields = ("title", "slug", "summary", "outcome")
    prepopulated_fields = {"slug": ("title",)}
    list_select_related = ("track", "product")

@admin.register(EducationResource)
class EducationResourceAdmin(ModelAdmin):
    list_display = ("title", "kind", "course", "is_free", "active", "approved", "sort_order")
    list_filter = ("kind", "active", "approved", "is_free")
    search_fields = ("title", "content")
    ordering = ("sort_order", "id")

@admin.register(EducationLesson)
class EducationLessonAdmin(ModelAdmin):
    list_display = ("title", "course", "lesson_type", "duration_minutes", "is_free_preview", "active", "sort_order")
    list_filter = ("lesson_type", "active", "is_free_preview")
    search_fields = ("title", "summary", "content")
    ordering = ("course", "sort_order", "id")


@admin.register(EducationPresentation)
class EducationPresentationAdmin(ModelAdmin):
    list_display = ("title", "course", "audience", "slide_count", "is_free", "active", "approved", "quality_status", "version")
    list_filter = ("audience", "is_free", "active", "approved", "quality_status")
    search_fields = ("title", "description", "presenter_notes", "assessment_notes")
    list_select_related = ("course",)


@admin.register(EducationEnrollment)
class EducationEnrollmentAdmin(ModelAdmin):
    list_display = ("user", "course", "status", "source", "completed_at", "updated_at")
    list_filter = ("status", "source")
    search_fields = ("user__username", "course__title")


@admin.register(EducationProgress)
class EducationProgressAdmin(ModelAdmin):
    list_display = ("enrollment", "lesson", "completed", "progress_percent", "completed_at")
    list_filter = ("completed",)
    search_fields = ("enrollment__user__username", "lesson__title")


@admin.register(EducationBookmark)
class EducationBookmarkAdmin(ModelAdmin):
    list_display = ("user", "lesson", "created_at")
    search_fields = ("user__username", "lesson__title")


@admin.register(EducationAssessment)
class EducationAssessmentAdmin(ModelAdmin):
    list_display = ("title", "course", "passing_score", "active", "approved")
    list_filter = ("active", "approved")
    search_fields = ("title", "course__title")


@admin.register(EducationQuestion)
class EducationQuestionAdmin(ModelAdmin):
    list_display = ("assessment", "prompt", "correct_index", "sort_order")
    search_fields = ("prompt",)


@admin.register(EducationAttempt)
class EducationAttemptAdmin(ModelAdmin):
    list_display = ("user", "assessment", "score", "passed", "submitted_at")
    list_filter = ("passed",)
    search_fields = ("user__username", "assessment__title")


@admin.register(EducationCertificate)
class EducationCertificateAdmin(ModelAdmin):
    list_display = ("code", "title", "enrollment", "issued_at")
    search_fields = ("code", "title", "enrollment__user__username")



from .newsletter_models import NewsletterAgentLink, NewsletterOccasion, NewsletterPublication, NewsletterSchedule, NewsletterSource, NewsletterStory, NewsletterSubmission


@admin.register(NewsletterSubmission)
class NewsletterSubmissionAdmin(ModelAdmin):
    list_display = ("subject", "status", "created_by", "created_at", "generated_story")
    fieldsets = (("ارسال به ایجنت اصلی محتوا", {"fields": ("subject", "body", "image", "video", "company_unit_title", "company_unit_slug", "company_activity_status", "company_project_title", "company_target_paths", "requested_publish_at")}), ("وضعیت پردازش", {"fields": ("status", "created_by", "generated_story", "created_at", "processed_at")}))
    list_filter = ("status", "created_at")
    search_fields = ("subject", "body")
    readonly_fields = ("status", "processed_at", "generated_story", "created_at")

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
        ("زمان‌بندی و هویت", {"fields": ("author_name", "event_date", "company_activity_kind", "manager_action", "company_unit_title", "company_unit_slug", "company_activity_status", "company_project_title", "company_activity_content", "published_at", "status")}),
        ("منبع و کنترل تکرار", {"fields": ("source", "fingerprint", "source_fingerprint")}),
    )
    readonly_fields = ("fingerprint", "source_fingerprint")

    def save_model(self, request, obj, form, change):
        obj.author_name = "مجتبی روزگار"
        super().save_model(request, obj, form, change)


admin.site.register([NewsletterAgentLink, NewsletterOccasion, NewsletterPublication, NewsletterSchedule, NewsletterSource])

from .knowledge_agent_models import KnowledgeAgentPlan, KnowledgeBook, KnowledgeAgentRun

@admin.register(KnowledgeAgentPlan)
class KnowledgeAgentPlanAdmin(admin.ModelAdmin):
    list_display = ("title", "start_date", "cadence_hours", "active", "require_owner_approval", "next_run_at")
    list_filter = ("active", "require_owner_approval")
    search_fields = ("code", "title", "mission", "goal")

@admin.register(KnowledgeBook)
class KnowledgeBookAdmin(admin.ModelAdmin):
    list_display = ("title", "domain", "status", "generated_sections", "target_sections")
    list_filter = ("status", "domain")
    search_fields = ("title", "domain", "objective")

@admin.register(KnowledgeAgentRun)
class KnowledgeAgentRunAdmin(admin.ModelAdmin):
    list_display = ("plan", "book", "status", "approval_required", "created_at", "finished_at")
    list_filter = ("status", "approval_required")
    search_fields = ("objective", "output_summary")

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

from .company_inquiry_models import CompanyInquiry

@admin.register(CompanyInquiry)
class CompanyInquiryAdmin(admin.ModelAdmin):
    list_display = ("subject", "kind", "name", "organization", "status", "created_at")
    list_filter = ("kind", "status", "created_at")
    search_fields = ("name", "organization", "email", "subject", "message")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (("درخواست", {"fields": ("kind", "name", "organization", "email", "phone", "subject", "message")}), ("مدیریت", {"fields": ("status", "internal_note", "created_at", "updated_at")}))


from .models import MojPropRequest
from django import forms
from django.utils import timezone
from .mojprop_workflow import validate_status_change
from .mojprop_offer_draft import build_offer_draft


class MojPropRequestStatusForm(forms.ModelForm):
    class Meta:
        model = MojPropRequest
        fields = ("status", "internal_note")

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk and "status" in cleaned and "internal_note" in cleaned:
            recorded = (MojPropRequest.objects.filter(pk=self.instance.pk)
                        .values_list("status", "internal_note").first())
            if recorded is None:
                raise forms.ValidationError("Original customer request no longer exists")
            previous, previous_note = recorded
            try:
                validate_status_change(
                    previous, cleaned["status"], cleaned["internal_note"], previous_note
                )
            except forms.ValidationError as exc:
                self.add_error("status", exc)
        return cleaned


@admin.register(MojPropRequest)
class MojPropRequestAdmin(ModelAdmin):
    form = MojPropRequestStatusForm
    actions = ("download_offer_drafts",)
    list_display = ("request_id", "name", "email", "route", "status", "created_at")
    list_filter = ("status", "route", "horizon", "created_at")
    search_fields = ("request_id", "name", "email", "notes")
    readonly_fields = (
        "request_id", "name", "email", "route", "horizon", "notes",
        "consent", "source", "created_at", "updated_at", "ip_hash",
        "user_agent", "reviewed_at",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        # Customer lead existence must be backed by a consented public intake.
        return False

    def has_delete_permission(self, request, obj=None):
        # Preserve written proposal, consent, delivery and dispute evidence.
        # Use "closed" or "spam" status, not destructive admin deletion.
        return False

    @admin.action(description="Export UNSENT written offer drafts for reviewed leads")
    def download_offer_drafts(self, request, queryset):
        # This action never sends mail, changes order status or charges a customer.
        if not request.user.is_staff or not request.user.has_perm("core.view_mojproprequest"):
            return HttpResponse(status=403)
        leads = list(queryset.order_by("request_id")[:100])
        if not leads or queryset.count() != len(leads):
            return HttpResponse("Select 1–100 reviewed customer requests.", status=409,
                                content_type="text/plain")
        try:
            docs = [build_offer_draft(lead) for lead in leads]
        except ValueError:
            return HttpResponse("Selected requests are not eligible for an offer draft.",
                                status=409, content_type="text/plain")
        response = HttpResponse("\n\n--- UNSENT DRAFT SEPARATOR ---\n\n".join(docs),
                                content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="mojprop-unsent-offer-drafts.txt"'
        response["Cache-Control"] = "private, no-store, max-age=0"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    def save_model(self, request, obj, form, change):
        old = (MojPropRequest.objects.filter(pk=obj.pk)
               .values_list("status", flat=True).first()) if change else None
        if old == "new" and obj.status == "reviewing" and obj.reviewed_at is None:
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)
