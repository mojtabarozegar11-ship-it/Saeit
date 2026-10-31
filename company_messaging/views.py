from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from enterprise_portal.views import office_access, no_cache
from ecosystem_hub.access import require_unit, user_units
from .forms import ComposeForm, ContactForm
from .models import Contact, Message, MessageEvent
from .services import enqueue


def visible_messages(user):
    qs = Message.objects.select_related("unit", "sender", "contact", "recipient_user")
    if user.is_superuser:
        return qs
    return qs.filter(unit__in=user_units(user)).filter(
        Q(sender=user) | Q(recipient_user=user)
    )


def permission(user, code):
    if not user.is_superuser and not user.has_perm("company_messaging." + code):
        raise PermissionDenied("مجوز دسترسی پیام‌رسانی موجود نیست.")


@office_access
@require_GET
def inbox(request):
    permission(request.user, "view_message")
    qs = visible_messages(request.user)
    return no_cache(render(request, "company_messaging/inbox.html", {
        "incoming": qs.filter(recipient_user=request.user)[:100],
        "outgoing": qs.filter(sender=request.user)[:100],
        "can_compose": request.user.is_superuser or request.user.has_perm("company_messaging.add_message"),
        "external_send_enabled": getattr(settings, "COMPANY_MESSAGING_SEND_ENABLED", False),
    }))


@office_access
@require_http_methods(["GET", "POST"])
def compose(request):
    permission(request.user, "add_message")
    form = ComposeForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        msg = form.save(commit=False)
        msg.sender = request.user
        if not msg.scheduled_at:
            msg.scheduled_at = timezone.now()
        try:
            enqueue(msg)
        except Exception as exc:
            from django.core.exceptions import ValidationError
            if isinstance(exc, ValidationError):
                form.add_error(None, exc)
            else:
                raise
        else:
            return no_cache(redirect("company_messaging:detail", pk=msg.pk))
    return no_cache(render(request, "company_messaging/compose.html", {"form": form, "external_send_enabled": getattr(settings, "COMPANY_MESSAGING_SEND_ENABLED", False)}))


@office_access
@require_GET
def detail(request, pk):
    permission(request.user, "view_message")
    msg = get_object_or_404(visible_messages(request.user), pk=pk)
    return no_cache(render(request, "company_messaging/detail.html", {
        "message": msg, "events": msg.events.all()[:30]
    }))


@office_access
@require_POST
def mark_read(request, pk):
    permission(request.user, "view_message")
    with transaction.atomic():
        msg = get_object_or_404(
            visible_messages(request.user).select_for_update(),
            pk=pk, channel="internal", recipient_user=request.user,
        )
        if not msg.read_at:
            msg.read_at = timezone.now()
            msg.save(update_fields=["read_at"])
            MessageEvent.objects.create(message=msg, code="read_by_recipient")
    return no_cache(redirect("company_messaging:detail", pk=pk))


def visible_contacts(user):
    """Never expose contacts outside the manager's active business units."""
    return Contact.objects.select_related("unit").filter(unit__in=user_units(user))


@office_access
@require_GET
def contacts(request):
    permission(request.user, "manage_company_contacts")
    from django.core.paginator import Paginator
    page = Paginator(visible_contacts(request.user).order_by("name", "pk"), 50).get_page(
        request.GET.get("page")
    )
    return no_cache(render(request, "company_messaging/contacts.html", {"contacts": page}))


@office_access
@require_http_methods(["GET", "POST"])
def contact_create(request):
    permission(request.user, "manage_company_contacts")
    form = ContactForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        require_unit(request.user, form.cleaned_data["unit"], write=True)
        form.save()
        return no_cache(redirect("company_messaging:contacts"))
    return no_cache(render(request, "company_messaging/contact_form.html", {
        "form": form, "editing": False,
    }))


@office_access
@require_http_methods(["GET", "POST"])
def contact_edit(request, pk):
    permission(request.user, "manage_company_contacts")
    with transaction.atomic():
        contact = get_object_or_404(visible_contacts(request.user).select_for_update(), pk=pk)
        require_unit(request.user, contact.unit, write=True)
        form = ContactForm(request.POST or None, instance=contact, user=request.user)
        if request.method == "POST" and form.is_valid():
            form.save()
            return no_cache(redirect("company_messaging:contacts"))
    return no_cache(render(request, "company_messaging/contact_form.html", {
        "form": form, "editing": True,
    }))
