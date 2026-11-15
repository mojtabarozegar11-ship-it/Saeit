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


from .models import MojPropRequest, MojPropOffer, MojPropDeliveryEvidence
from django import forms
from django.utils import timezone
from .mojprop_workflow import validate_status_change
from .mojprop_offer_draft import build_offer_draft
from django.db import transaction
from django.core.exceptions import PermissionDenied, ValidationError


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


@admin.action(
    description="Start manual review of consented new Moj Prop requests",
    permissions=["change"],
)
def start_mojprop_review(modeladmin, request, queryset):
    """Review only brand-new consented leads; never alter offered cases."""
    updated = queryset.filter(status="new", consent=True).update(
        status="reviewing", reviewed_at=timezone.now()
    )
    modeladmin.message_user(request, f"{updated} new request(s) moved to reviewing.")


@admin.register(MojPropRequest)
class MojPropRequestAdmin(ModelAdmin):
    form = MojPropRequestStatusForm
    actions = ("download_offer_drafts", "start_mojprop_review")
    list_display = ("request_id", "name", "email", "route", "status", "offer_stage", "created_at")
    list_filter = ("status", "route", "horizon", "created_at")
    search_fields = ("request_id", "name", "email", "notes")
    readonly_fields = (
        "request_id", "name", "email", "route", "horizon", "product_id", "notes",
        "consent", "source", "created_at", "updated_at", "ip_hash",
        "user_agent", "reviewed_at",
    )
    ordering = ("-created_at",)

    @admin.display(description="Written quote status")
    def offer_stage(self, obj):
        latest = obj.commercial_offers.order_by("-version").first()
        return latest.status if latest else "NO OFFER"

    def has_add_permission(self, request):
        # Customer lead existence must be backed by a consented public intake.
        return False

    def has_delete_permission(self, request, obj=None):
        # Preserve written proposal, consent, delivery and dispute evidence.
        # Use "closed" or "spam" status, not destructive admin deletion.
        return False

    @admin.action(description="Export ONE private UNSENT proposal draft for manual review")
    def download_offer_drafts(self, request, queryset):
        # This action never sends mail, changes order status or charges a customer.
        if not request.user.is_staff or not request.user.has_perm("core.change_mojproprequest"):
            return HttpResponse(status=403)
        # A single buyer per download prevents accidental cross-customer
        # disclosure when forwarding a draft to one customer manually.
        if queryset.count() != 1:
            return HttpResponse("Select exactly one reviewed customer request.", status=409,
                                content_type="text/plain")
        leads = list(queryset.order_by("request_id")[:1])
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
        if not change or not obj.pk:
            raise PermissionDenied("A real consented customer request is required")
        # Re-evaluate against the latest locked row. A stale admin form must
        # never overwrite a more recent client's approval or delivery evidence.
        with transaction.atomic():
            locked = (MojPropRequest.objects.select_for_update()
                      .filter(pk=obj.pk).first())
            if locked is None:
                raise PermissionDenied("Customer request no longer exists")
            try:
                validate_status_change(
                    locked.status, obj.status, obj.internal_note, locked.internal_note
                )
            except ValidationError as exc:
                raise PermissionDenied(
                    "Customer status/evidence changed; refresh before saving"
                ) from exc
            if locked.status == "new" and obj.status == "reviewing" and locked.reviewed_at is None:
                obj.reviewed_at = timezone.now()
            else:
                obj.reviewed_at = locked.reviewed_at
            super().save_model(request, obj, form, change)

@admin.register(MojPropOffer)
class MojPropOfferAdmin(ModelAdmin):
    """Real commercial quote pipeline; no automatic mail or fake settlement."""

    list_display = (
        "lead", "version", "title", "amount", "currency", "status",
        "accepted_at", "delivery_days", "expires_at", "created_at",
    )
    list_filter = ("status", "currency", "delivery_days", "created_at")
    search_fields = (
        "lead__request_id", "lead__email", "lead__name", "title", "scope",
    )
    autocomplete_fields = ("lead",)
    readonly_fields = (
        "created_at", "updated_at", "created_by", "manual_proposal",
        "public_quote_link",
    )
    fields = (
        "lead", "version", "title", "scope", "exclusions",
        "amount", "currency", "delivery_days",
        "status", "reviewed_at", "issued_at", "expires_at",
        "accepted_at", "acceptance_reference",
        "created_by", "internal_note", "manual_proposal", "public_quote_link",
        "created_at", "updated_at",
    )
    ordering = ("-created_at",)

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj and obj.status in ("issued", "accepted"):
            return tuple(fields) + (
                "lead", "version", "title", "scope", "exclusions",
                "amount", "currency", "delivery_days",
                "issued_at", "reviewed_at", "expires_at",
            )
        return fields

    @admin.display(description="Unsent written proposal (not an invoice)")
    def manual_proposal(self, obj):
        if not obj.pk:
            return "Save the draft first; no message is sent."
        return obj.manual_quote_text

    @admin.display(description="Unsent signed buyer URL (expires after 24 h)")
    def public_quote_link(self, obj):
        from django.conf import settings
        from core.mojprop_quote_views import quote_read_token
        if getattr(settings, "MOJPROP_PUBLIC_QUOTES_ENABLED", False) is not True:
            return "Public quote sharing is disabled until owner-approved deployment."
        try:
            token = quote_read_token(obj)
        except ValueError:
            return "Quote is not issued, has expired or needs review."
        # Return a relative route; admins must not assume the other site's
        # hostname or publish a query containing customer information.
        return reverse("mojprop_quote_public", kwargs={"token": token})

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        # Admin.save_model is also invoked on internal edits: validate
        # every status, price and timeline before persisting.
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(MojPropDeliveryEvidence)
class MojPropDeliveryEvidenceAdmin(ModelAdmin):
    """Private evidence desk: a recorded handoff is not a verified payment."""

    list_display = (
        "offer", "artifact_name", "status", "handed_off_at", "acknowledged_at",
        "created_at",
    )
    list_filter = ("status", "created_at", "handed_off_at")
    search_fields = (
        "offer__lead__request_id", "offer__lead__email", "artifact_name",
        "artifact_sha256", "handoff_reference",
    )
    autocomplete_fields = ("offer",)
    readonly_fields = ("created_at", "updated_at")
    fields = (
        "offer", "artifact_name", "artifact_sha256", "status",
        "clearance_reference", "handoff_reference", "handed_off_at",
        "acknowledgment_reference", "acknowledged_at",
        "created_at", "updated_at",
    )

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj and obj.status in ("sent", "acknowledged"):
            return tuple(fields) + (
                "offer", "artifact_sha256", "artifact_name",
                "clearance_reference", "handoff_reference", "handed_off_at",
            )
        return fields

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)
