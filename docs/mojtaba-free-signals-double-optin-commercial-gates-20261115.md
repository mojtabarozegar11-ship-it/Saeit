# Mojtaba.bot.ai free educational audience — controlled commercial release

Date: 2026-11-15. Scope: `Saeit` / Moj Prop; one operating identity `mojtaba.bot.ai`.

## Product distinction
- **Public free learning:** the Signal Desk's hypothetical/historical methodology is readable without registration.
- **One-off free request:** existing `/moj-prop-intake/` requires customer consent for that specific request only; it is *not* a mailing subscription or an entitlement.
- **Free email research audience:** distinct `MojSignalFreeSubscription` holds independent checkbox consent, `pending` until second user-initiated POST of a signed email confirmation token (48h TTL), `confirmed` afterward, and durable `unsubscribed` suppression. GET never silently activates or unsubscribes.
- **Paid research:** existing source catalog quote codes USD 9.90, USD 29.90, USD 79.90; separate manual written quote, no recurring paid plan or charged entitlement. No financial recommendation or live execution activated.

## Source implemented
- Django `core/signal_free_models.py`, `core/signal_free_views.py`, migration `0046_signal_free_subscription`, root WSGI routes, default-disabled `MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED`.
- Safe SMTP gate: exact authenticated Django SMTP backend, nonblank owned mail host/user/password/from email, exactly one of TLS/SSL, independently enabled environmental switch. Console or file email backends forbidden for live.
- Registration POST needs CSRF and independently checked consent; bounded JSON rejects duplicate keys, honeypots, bad email and repeated attempts. Generic 202 response prevents account enumeration. Failed SMTP rolls back pending row.
- Confirmation and unsubscribe links use purpose-specific Django timestamped signing and one-time nonce; GET only shows a POST confirmation form. After successful unsubscribe, stored nonce is revoked.
- Signed unsubscribe helper must be included in every **separately reviewed** educational email. Sending mail content is NOT enabled by this source release.
- Read-only private Django admin membership status, privacy-safe CLI counts and 30-day stale pending-only cleanup with explicit `--apply`. Do not delete unsubscribed suppression records.
- Static Signal Desk now has a separate independent checkbox/CSRF form; when backend email is unavailable it explicitly says unavailable; there is no fictitious successful registration.

## Release packaging and rollback
- Commercial backend installer and offline migration preflight now include `0046`, the two free modules, `config/settings.py`, and scoped append-only live-model/admin/settings/url patching.
- Preserve existing owner/tenant code: fail closed on unknown live schema >=0041, changed stored migrations, changed independent model/view modules and partial root URL routes.
- Run `migrate core 0046_signal_free_subscription --noinput` only after independent DB/media restore evidence and safe migration closure. Do **not** run unbounded migrate.
- Pinned manual workflow packages all of these, installs backend first and publishes static page second. Both public free and existing Moj Prop/other root endpoints require smoke checks. Every deployed file is individually backed up; application-code rollback cannot alone reverse DDL, so a independently verified database restoration is mandatory before release.
- Static installer now supports `signals/index.html`, and retains an exact historical baseline; refuses nonbaseline live overrides; its manifest enforces reversible restoration.

## Production go/no-go (all required; unknown=NO-GO)
1. All exact latest PR head CI (CI, Django CI, migration closure and backend source selftest) green and security reviewed.
2. Clear branch drift, no auto-deploy on merge and source archival.
3. Independent verified backup **and restore** of actual database/media + rollback procedure for host/tenant, with owner conditional approval.
4. Host-level DNS, TLS, Apache/Passenger and real GET `/moj-signal-free-subscribe/` with CSRF and `enabled=false` prior to SMTP activation; verify `/moj-prop/signals/` shows free and paid details.
5. Verify owned SMTP credentials and domain sender acceptance without publishing secrets; approve privacy notice, unsubscribe and no unsolicited emails.
6. Only then enable `MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED=true` through approved live cPanel environment and perform a **consented** independent confirmation + unsubscribe end-to-end with real mailbox evidence.
7. Create reviewed original historical educational content and obtain required jurisdictional legal clearance for any future actionable market calls.
8. Payment and commercial delivery are a separate path: lawful seller, verified TRON beneficiary, independent finality, immutable invoices/refunds and entitlement. No claims of paid revenue without bank/chain plus delivery proof.

## No-go facts
GitHub source, CI green, an HTML 200, a pending email, and an unaccepted quote are NOT confirmed memberships, live signals, payments or revenue. No new cost, live trade, real customer email, dispatch or deploy was initiated by this change.
