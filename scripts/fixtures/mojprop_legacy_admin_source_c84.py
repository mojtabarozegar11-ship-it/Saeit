from .models import MojPropRequest
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
