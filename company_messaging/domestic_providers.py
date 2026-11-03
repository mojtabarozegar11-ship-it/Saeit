"""Verified official bot endpoints only; never scrape user sessions or reuse personal logins."""
import json
import urllib.parse
from django.conf import settings
from .services import ProviderNotReady, _http_post


def send_bot_message(platform, chat_id, body):
    """Return upstream acceptance reference, not handset delivery proof."""
    if platform not in ("bale", "eitaa", "rubika", "telegram"):
        raise ProviderNotReady("unsupported_platform")
    if not chat_id or not body or len(body) > 4096:
        raise ProviderNotReady("invalid_bot_destination_or_body")
    if not getattr(settings, "COMPANY_MESSAGING_" + platform.upper() + "_ENABLED", False):
        raise ProviderNotReady("bot_channel_disabled")
    if platform == "bale":
        token = getattr(settings, "COMPANY_BALE_BOT_TOKEN", "")
        if not token:
            raise ProviderNotReady("bale_not_configured")
        url = "https://tapi.bale.ai/bot%s/sendMessage" % urllib.parse.quote(token, safe=":")
        data = {"chat_id": chat_id, "text": body}
    elif platform == "eitaa":
        token = getattr(settings, "COMPANY_EITAA_APP_TOKEN", "")
        if not token:
            raise ProviderNotReady("eitaa_not_configured")
        url = "https://eitaayar.ir/api/app/sendMessage"
        data = {"token": token, "chat_id": chat_id, "text": body}
    elif platform == "rubika":
        token = getattr(settings, "COMPANY_RUBIKA_BOT_TOKEN", "")
        if not token:
            raise ProviderNotReady("rubika_not_configured")
        url = "https://botapi.rubika.ir/v3/%s/sendMessage" % urllib.parse.quote(token, safe=":")
        data = {"chat_id": chat_id, "text": body}
    else:
        token = getattr(settings, "COMPANY_TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise ProviderNotReady("telegram_not_configured")
        url = "https://api.telegram.org/bot%s/sendMessage" % urllib.parse.quote(token, safe=":")
        data = {"chat_id": chat_id, "text": body, "protect_content": True}
    result = _http_post(url, json.dumps(data).encode("utf-8"), {"Content-Type": "application/json"})
    if not isinstance(result, dict):
        raise RuntimeError("bot_unexpected_response")
    # Rubika uses message_id in its response data; Bale/Telegram use result;
    # Eitaa app API explicitly returns {"ok": true, "result": "success"}.
    if platform == "rubika":
        response = result.get("data") or result
        message_id = response.get("message_id") if isinstance(response, dict) else None
        if not message_id:
            raise RuntimeError("rubika_unconfirmed")
    else:
        if result.get("ok") is not True:
            raise RuntimeError("bot_unconfirmed")
        response = result.get("result")
        if platform != "eitaa" and not isinstance(response, dict):
            raise RuntimeError("bot_unconfirmed")
        if platform == "eitaa":
            if response != "success":
                raise RuntimeError("eitaa_unconfirmed")
            message_id = "accepted-by-eitaayar"
        else:
            message_id = response.get("message_id")
            if not message_id:
                raise RuntimeError("bot_missing_message_id")
    return str(message_id)[:128]
