"""Auditable outbound queue: no provider is contacted by a web request."""
import json
import urllib.error
import urllib.parse
import urllib.request
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone
from .models import Message, MessageEvent


class ProviderNotReady(Exception):
    pass


def enqueue(message):
    """Freeze one new recipient and consent snapshot before queueing."""
    if message.pk:
        raise ValidationError("پیام ثبت‌شده را دوباره در صف قرار ندهید.")
    message.status = "internal" if message.channel == "internal" else "queued"
    if not message.scheduled_at:
        message.scheduled_at = timezone.now()
    message.recipient_fingerprint = message.destination_fingerprint()
    message.full_clean()
    with transaction.atomic():
        message.save()
        MessageEvent.objects.create(message=message, code="internal_created" if message.channel == "internal" else "queued")
    return message


def _http_post(url, data, headers):
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    # Any network error after request handoff is ambiguous: do not blindly retry.
    with urllib.request.urlopen(request, timeout=12) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError("provider_http_error")
        payload = response.read(8192)
    return json.loads(payload or b"{}")


def _deliver(msg):
    contact = msg.contact
    if not getattr(settings, "COMPANY_MESSAGING_" + msg.channel.upper() + "_ENABLED", False):
        raise ProviderNotReady("channel_disabled")
    if msg.channel == "email":
        if not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL or not settings.EMAIL_HOST_USER:
            raise ProviderNotReady("email_not_configured")
        count = EmailMessage(msg.subject or "پیام زمرد ملل", msg.body,
                             settings.DEFAULT_FROM_EMAIL, [contact.email]).send(fail_silently=False)
        if count != 1:
            raise RuntimeError("email_unconfirmed")
        return "smtp-accepted"
    if msg.channel == "sms":
        key = getattr(settings, "COMPANY_SMS_KAVENEGAR_KEY", "")
        sender = getattr(settings, "COMPANY_SMS_KAVENEGAR_SENDER", "")
        if not key or not sender:
            raise ProviderNotReady("sms_not_configured")
        form = urllib.parse.urlencode({"receptor": contact.phone_e164, "sender": sender, "message": msg.body}).encode()
        result = _http_post("https://api.kavenegar.com/v1/%s/sms/send.json" % urllib.parse.quote(key, safe=""),
                            form, {"Content-Type": "application/x-www-form-urlencoded"})
        if result.get("return", {}).get("status") != 200:
            raise RuntimeError("sms_provider_rejected")
        entries = result.get("entries")
        message_id = (entries[0].get("messageid") if isinstance(entries, list)
                      and entries and isinstance(entries[0], dict) else None)
        if not message_id:
            raise RuntimeError("sms_missing_message_id")
        return str(message_id)[:128]
    if msg.channel == "telegram":
        token = getattr(settings, "COMPANY_TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise ProviderNotReady("telegram_not_configured")
        data = json.dumps({"chat_id": contact.telegram_chat_id, "text": msg.body,
                           "protect_content": True}).encode()
        result = _http_post("https://api.telegram.org/bot%s/sendMessage" % token, data,
                            {"Content-Type": "application/json"})
        if not result.get("ok"):
            raise RuntimeError("telegram_rejected")
        return str(result.get("result", {}).get("message_id", ""))[:128]
    if msg.channel in ("bale", "eitaa", "rubika"):
        from .domestic_providers import send_bot_message
        destination = getattr(contact, msg.channel + "_chat_id")
        return send_bot_message(msg.channel, destination, msg.body)
    if msg.channel == "whatsapp":
        token = getattr(settings, "COMPANY_WHATSAPP_ACCESS_TOKEN", "")
        phone_id = getattr(settings, "COMPANY_WHATSAPP_PHONE_ID", "")
        template = getattr(settings, "COMPANY_WHATSAPP_TEMPLATE_NAME", "")
        language = getattr(settings, "COMPANY_WHATSAPP_TEMPLATE_LANGUAGE", "fa")
        if not token or not phone_id or not template:
            raise ProviderNotReady("whatsapp_not_configured")
        # Only send an approved business template with precisely one text parameter.
        data = json.dumps({
            "messaging_product": "whatsapp", "to": contact.phone_e164.lstrip("+"),
            "type": "template", "template": {
                "name": template, "language": {"code": language},
                "components": [{"type": "body", "parameters": [{"type": "text", "text": msg.body}]}],
            },
        }).encode()
        result = _http_post("https://graph.facebook.com/v23.0/%s/messages" %
                            urllib.parse.quote(phone_id, safe=""), data,
                            {"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        messages = result.get("messages")
        message_id = (messages[0].get("id") if isinstance(messages, list)
                      and messages and isinstance(messages[0], dict) else None)
        if not message_id:
            raise RuntimeError("whatsapp_missing_message_id")
        return str(message_id)[:128]
    raise ProviderNotReady("unknown_channel")


def dispatch_one(pk):
    """At-most-one automated attempt. A crash/timeout is uncertain, never auto-retried."""
    if not getattr(settings, "COMPANY_MESSAGING_SEND_ENABLED", False):
        return "disabled"
    with transaction.atomic():
        msg = Message.objects.select_for_update().get(pk=pk)
        if msg.status != "queued" or msg.scheduled_at > timezone.now():
            return "not_due"
        try:
            msg.full_clean()
        except ValidationError:
            msg.status = "blocked"
            msg.error_code = "recipient_or_consent_invalid"
            msg.save(update_fields=["status", "error_code"])
            MessageEvent.objects.create(message=msg, code="blocked_consent")
            return "blocked"
        msg.status = "sending"
        msg.attempts += 1
        msg.save(update_fields=["status", "attempts"])
        MessageEvent.objects.create(message=msg, code="provider_handoff")
    try:
        reference = _deliver(msg)
    except ProviderNotReady:
        new_status, reason = "blocked", "provider_not_configured"
    except Exception:
        # The provider may have accepted a message despite network timeout.
        new_status, reason = "uncertain", "provider_outcome_unknown"
    else:
        new_status, reason = "accepted", ""
    with transaction.atomic():
        item = Message.objects.select_for_update().get(pk=pk)
        if item.status != "sending":
            return "manual_review"
        item.status = new_status
        item.error_code = reason
        if new_status == "accepted":
            item.accepted_at = timezone.now()
            item.external_reference = reference
        item.save(update_fields=["status", "error_code", "accepted_at", "external_reference"])
        MessageEvent.objects.create(message=item, code=new_status)
    return new_status
