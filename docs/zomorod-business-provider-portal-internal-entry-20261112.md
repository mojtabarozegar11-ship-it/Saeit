# Zomorod Melal business desk — internal-page cPanel entry (read-only first)

Status: documented navigation path, **not an authenticated session**. This is for PR #2219 and the private `/business/` desk. No production modifications are authorized by this document.

## Confirmed provider navigation, avoiding SSH, VPS relay and port guessing

1. Open **https://parswebserver.com/** (provider homepage).
2. Use its **«ورود | عضویت»** navigation link to `https://portal.parswebserver.com/index.php?rp=/login`.
3. An authorized owner signs in to the existing Pars Web Server customer account **within the browser**. Do not request or copy credentials into GitHub, ChatGPT, workflow logs or tickets.
4. From the **authenticated customer area**, open **Services / سرویس‌های من**.
5. Select the actual existing web-hosting service for **zomorodmelal.ir**, not a new order or a VPS.
6. Choose **«ورود به cPanel»** (single-sign-on link from service details) instead of constructing a direct `:2083`, guessing an SSH port or using a proxy.
7. Confirm that the resulting cPanel belongs to the correct hosting account before inspecting any file.

**Official provider documentation**:
- https://parswebserver.com/نحوه-ورود-به-سی-پنل/
- https://parswebserver.com/how-to-add-a-new-user-in-cpanel/

## Read-only checks after valid sign-in

- cPanel File Manager: inspect private path `/home/zomorod2/.private/zomorod-business/app.php` and presence of `genetics-center.php`. Hidden files may require explicit visibility setting. Do **not** download credentials or paste private code into public messages.
- Inspect permitted file metadata: size, modified date and, if a trusted hash tool exists, SHA-256 for `app.php` and `genetics-center.php` without modifying either. A SHA-256 must never be guessed.
- Confirm `/home/zomorod2/.private/zomorod-business/management.sqlite3` exists, but do not directly open/edit/replace the production database; inspect available disk/quota non-destructively.
- Inspect cPanel backup facilities and site-specific PHP version; ensure there is sufficient space and a tested recovery strategy before any release.
- Do not start shell commands, edit File Manager files, change passwords, disable authentication, create tickets, pay or deploy as part of this read-only audit.

## Outcome labels

- **PROVEN**: only values actually read from the signed-in service.
- **UNKNOWN**: anything not inspected or blocked by authentication, subscription or tools.
- **PREREQUISITE**: owner-authorized browser sign-in/session and separate approval for any eventual production deployment.

## Current evidence (2026-11-12)

- The official provider homepage links to its customer-area sign-in. The public login page was reached through that **internal link**.
- **Not proven:** a logged-in customer session, presence of the target hosting service in account, access to cPanel File Manager, hashes of live files or database backup.
- The available TinyFish browser profile list does **not** confirm an existing signed-in Pars Web Server/cPanel session. Its wallet is below zero and browser automation has usage cost; do not run it or request a top-up without separate owner approval.
- No SSH and no remote deployment were used.

## PR #2219 boundary

The PR implements private PHP navigation and tested admin-only idempotent project registration in a synthetic database. It is still **Draft**. Do not merge or run `workflow_dispatch` based only on a reachable customer login page. If the browser path is the chosen production route, use a controlled cPanel File Manager release after explicit approval and a verifiable backup; do not substitute the old VPS relay route.

**Financial safety:** never confuse the estimated 65.4M USD model with an approved budget, invoice, liability or amount paid.
