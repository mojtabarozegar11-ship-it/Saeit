# Zomorod Melal private office — communication center

Scope: extension of the private ERP stack (PR #402 -> #408 -> #437); **not deployed** on the live Zomorod site.
Public homepage, sub-sites, commerce/payment and existing financial records are unchanged.

## Routes
- /company/office/messages/ — private staff inbox and sent items
- /company/office/messages/new/ — per-unit compose, internal / email / SMS / Telegram / WhatsApp
- /company/office/messages/<id>/ — participants-only message history
- /company/office/messages/<id>/read/ — CSRF-protected internal read receipt (POST only)
- /admin/company_messaging/contact/ — scoped contact register/consent record

## Implemented delivery semantics
- Internal staff messages are available immediately. No network provider needed.
- External messages are queued, NEVER sent from the HTTP POST request.
- A contact must be active, not suppressed, in the sender's permitted unit, have a channel address and timestamped consent with an evidence reference. Revoked consent blocks queued sends again at dispatch.
- Worker management command defaults to PREVIEW and only accepts --commit if COMPANY_MESSAGING_SEND_ENABLED=true.
- Providers: Django SMTP; Kavenegar SMS; Telegram official Bot API; WhatsApp official Cloud API using an *approved template with exactly one text parameter*. The provider credentials/config and approved template are NOT supplied or hardcoded.
- Accepted = upstream provider acknowledgement; neither handset delivery nor read receipt is claimed. No inbound external-message channel or provider status callback is installed. Webhook support needs independently verified provider signatures/phone ownership.
- After a network handoff, unknown outcomes are marked uncertain; retries are deliberately NOT automatic. Reconcile with provider's verified delivery log first to prevent duplicate external messages.
- No bulk campaign import or unsolicited sends. Recipient opt-out/suppression is enforced.
- No actual external sends were made while implementing this change.

## Private configuration (never commit real values)
COMPANY_MESSAGING_SEND_ENABLED=false
COMPANY_MESSAGING_EMAIL_ENABLED=false
COMPANY_MESSAGING_SMS_ENABLED=false
COMPANY_MESSAGING_TELEGRAM_ENABLED=false
COMPANY_MESSAGING_WHATSAPP_ENABLED=false
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=...
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL=...
COMPANY_SMS_KAVENEGAR_KEY=...
COMPANY_SMS_KAVENEGAR_SENDER=...
COMPANY_TELEGRAM_BOT_TOKEN=...
COMPANY_WHATSAPP_ACCESS_TOKEN=...
COMPANY_WHATSAPP_PHONE_ID=...
COMPANY_WHATSAPP_TEMPLATE_NAME=...  # preapproved one-body-variable business template
COMPANY_WHATSAPP_TEMPLATE_LANGUAGE=fa

Provision secrets in protected cPanel environment only; never in GitHub or ChatGPT.
Use the owner's approved sender identity/provider accounts and documented recipient opt-in.

## Staging acceptance (never run a blind production migration)
1. Restore-test private database and media backup with off-host copy and a documented rollback.
2. Verify HTTPS/proxy, secure cookies, rate limiting, MFA and Passenger login health.
3. Check effective database identity and schema; use isolated staging first:
   python manage.py makemigrations --check --dry-run company_messaging
   python manage.py check
   python manage.py migrate --plan
   python manage.py test company_messaging enterprise_portal ecosystem_hub
4. Migrate only reviewed additive company_messaging schema on staging, test access across units and the preserved public routes. Then test recovery and rollback.
5. Configure a real provider in staging with authorized test contacts, actual opt-in, rate/budget limits, and independent receipts. Review each real-send cost/contract separately.
6. Activate worker only after signed operational go-live checklist: a scheduler at a conservative interval may invoke:
   python manage.py dispatch_company_messages --commit --limit 20
   Disable immediately with COMPANY_MESSAGING_SEND_ENABLED=false.
7. Verify queue -> acceptance -> **independent delivery status** on each provider, and live protected login. Do not report production readiness before this.

## Not yet production-ready
- Existing private ERP stack PR #402/#408/#437 is draft/not deployed. Independent public read-only probes found private office failures.
- No guaranteed usable SMTP, Kavenegar sender, Telegram bot or official WhatsApp business profile and approved template were verified.
- External receipt callbacks, inbox channels, operational opt-out capture, template approval, sender compliance, DLP, retention policy and 24/7 supervised worker need operational provisioning/testing.
- No password, token, OTP or contact data is in source. Never use the unauthenticated browser bridge or the unofficial WhatsApp pairing bridge for company mass messaging.
