#!/usr/bin/env python3
"""Prepare a private 20-language Living Cities account-UI candidate, never publish it.

No database, Passenger, public directory, previous saves, or payment service is changed.
"""
import argparse
import os
from pathlib import Path
import shutil

HOME = Path("/home/zomorod2")
SITE = HOME / "mojplaywin.com"
ROOT = HOME / ".private/mpw-living-cities-global"
SOURCE_SHA = "eca666cbb730a6fcf70d284328893a78ad966881"
PUBLIC = SITE / "living-cities"
STAGE = ROOT / ("account-ui-review-" + SOURCE_SHA)
PUBLIC_OWNER = "MPW-LIVING-CITIES-GLOBAL-20-LANG-" + SOURCE_SHA
REVIEW_OWNER = "MPW-LIVING-CITIES-ACCOUNT-REVIEW-" + SOURCE_SHA
STATIC = Path("static/living_cities")
ASSETS = {
    "app.mjs", "sim.mjs", "render.mjs", "style.css", "tycoon.mjs",
    "tycoon-panel.mjs", "tycoon-idempotency.mjs", "tycoon.css",
    "progression.mjs", "global-i18n.mjs", "global-missions-i18n.mjs",
    "global-campaign.mjs", "global-shell.mjs", "global-theme.css",
    "gameplay-i18n.mjs", "weekly-expeditions.mjs",
}
CSRF_HELPER = """// Secure same-origin CSRF bootstrap for the static account edition.
let currentToken = "";
let pendingToken = null;
const valid = value => typeof value === "string" && /^[a-zA-Z0-9]{64}$/.test(value);
export function setCsrfToken(value) {
  if (!valid(value)) throw new Error("Invalid game security token");
  currentToken = value;
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta) meta.content = value;
  return value;
}
export async function getCsrfToken() {
  if (valid(currentToken)) return currentToken;
  if (!pendingToken) pendingToken = (async () => {
    const response = await fetch("/api/living-cities/auth/csrf/", {
      method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error"
    });
    if (!response.ok) throw new Error("Game sign-in security is unavailable");
    return setCsrfToken((await response.json()).csrf_token);
  })();
  try { return await pendingToken; }
  finally { pendingToken = null; }
}
"""


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def once(source, before, after, label):
    require(source.count(before) == 1, "changed_asset_contract:" + label)
    return source.replace(before, after, 1)


def routes(source, label):
    old = "/living-cities/api/living-cities/"
    require(old in source, "missing_browser_api_prefix:" + label)
    source = source.replace(old, "/api/living-cities/")
    if label == "app":
        old = "/living-cities/api/auth/"
        require(old in source, "missing_browser_auth_prefix")
        source = source.replace(old, "/api/living-cities/auth/")
    require("/living-cities/api/" not in source, "stale_api_prefix")
    return source


def account_html(source):
    source = once(source, 'data-lc-edition="browser"',
                  'data-lc-edition="account"', "html_mode")
    source = once(source, "LOCAL SAVE · MOJ1 PAYMENTS UNAVAILABLE",
                  "LOCAL OR ACCOUNT-SAVED PLAY · MOJ1 PAYMENTS UNAVAILABLE",
                  "safety_banner")
    require("/living-cities/static/living_cities/app.mjs" in source,
            "global_module_path_missing")
    return source


def account_app(source):
    require('import "./global-shell.mjs";' in source and
            'from "./gameplay-i18n.mjs"' in source, "global_i18n_missing")
    source = routes(source, "app")
    source = once(source, 'import "./tycoon-panel.mjs";',
                  'import "./tycoon-panel.mjs";\nimport {getCsrfToken, setCsrfToken} from "./account-csrf.mjs";',
                  "app_csrf_import")
    source = once(source,
                  'const csrf=document.querySelector(\'meta[name="csrf-token"]\')?.content||"";',
                  'const csrf=await getCsrfToken();', "world_csrf")
    source = once(source,
                  'const csrf=$("#csrf_token")?.value||document.querySelector(\'meta[name="csrf-token"]\')?.content;',
                  'const csrf=await getCsrfToken();', "code_csrf")
    source = once(source,
                  'headers:{"Content-Type":"application/json"},\n      body:JSON.stringify({username,password})',
                  'headers:{"Content-Type":"application/json","X-CSRFToken":await getCsrfToken()},\n      body:JSON.stringify({username,password})',
                  "login_csrf")
    source = once(source,
                  'if(!response.ok||!data.authenticated)throw Error("Invalid account details");\n    booting=true;await bootstrap();setTab("account");',
                  'if(!response.ok||!data.authenticated)throw Error("Invalid account details");\n    setCsrfToken(data.csrf_token);\n    booting=true;await bootstrap();\n    document.dispatchEvent(new Event("living-cities:account-signed-in"));\n    setTab("account");',
                  "post_login_rotation")
    source = once(source,
                  'try{await fetch("/api/living-cities/auth/logout/",{method:"POST",credentials:"same-origin",cache:"no-store"});}catch(_e){}\n    location.reload();',
                  'try{\n      const response=await fetch("/api/living-cities/auth/logout/",{\n        method:"POST",credentials:"same-origin",cache:"no-store",redirect:"error",\n        headers:{"X-CSRFToken":await getCsrfToken()}\n      });\n      if(!response.ok)throw Error("Logout rejected");\n      location.reload();\n    }catch(_e){flash("Sign-out unavailable. Please retry.");}',
                  "logout_csrf")
    source = once(source, "Continue with your Bazei account",
                  "Continue with your MojPlayWin account", "account_label")
    source = once(source, "Existing Bazei accounts only.",
                  "Existing MojPlayWin accounts only.", "account_help")
    return source


def account_tycoon(source):
    require('from "./gameplay-i18n.mjs"' in source, "tycoon_i18n_missing")
    source = routes(source, "tycoon")
    source = once(source,
                  'import { createTycoonActionKeys } from "./tycoon-idempotency.mjs";',
                  'import { createTycoonActionKeys } from "./tycoon-idempotency.mjs";\nimport {getCsrfToken} from "./account-csrf.mjs";',
                  "tycoon_csrf_import")
    old = 'const csrf = document.querySelector(\'meta[name="csrf-token"]\')?.content || "";'
    require(source.count(old) == 2, "tycoon_csrf_contract_changed")
    source = source.replace(old, "const csrf = await getCsrfToken();")
    source = once(source,
                  'const browserEdition = document.documentElement.dataset.lcEdition === "browser";',
                  'const browserEdition = document.documentElement.dataset.lcEdition === "browser";\nconst checkoutEnabled = false; // MOJ1 checkout intentionally disabled.',
                  "checkout_off")
    source = once(source,
                  '${browserEdition ? "disabled" : ""}>${browserEdition ? "Checkout unavailable" : "Choose pack"}',
                  '${!checkoutEnabled ? "disabled" : ""}>${!checkoutEnabled ? "Checkout unavailable" : "Choose pack"}',
                  "checkout_button_off")
    source = once(source, "if (browserEdition || !selectedPackId || confirmButton.disabled) return;",
                  "if (!checkoutEnabled || !selectedPackId || confirmButton.disabled) return;",
                  "checkout_request_off")
    source = once(source, 'if (action === "buy-gems" && !browserEdition) openGemDialog(actionButton.dataset.pack);',
                  'if (action === "buy-gems" && checkoutEnabled) openGemDialog(actionButton.dataset.pack);',
                  "checkout_action_off")
    source = once(source, '  if (!browserEdition) void bootstrapTycoon();',
                  '  document.addEventListener("living-cities:account-signed-in", () => {\n    if (!browserEdition) void bootstrapTycoon();\n  });\n  if (!browserEdition) void bootstrapTycoon();',
                  "tycoon_signin_reload")
    return source


def account_global_shell(source):
    require("browserSnapshots(localStorage)" in source and
            "weeklyExpedition(world,tycoon,localStorage)" in source,
            "local_world_tour_source_changed")
    return once(source,
                "' · '+safe(GT(\"worldSafety\",lang))+'</p>';",
                "' · '+safe(GT(\"worldSafety\",lang))+' · WORLD TOUR PROGRESS IS LOCAL-ONLY, NOT ACCOUNT-SYNCED</p>';",
                "tour_missions_not_server_authoritative")


def changes_from_browser(html, app, tycoon, global_shell):
    return {
        Path("play/index.html"): account_html(html),
        STATIC / "app.mjs": account_app(app),
        STATIC / "tycoon-panel.mjs": account_tycoon(tycoon),
        STATIC / "global-shell.mjs": account_global_shell(global_shell),
        STATIC / "account-csrf.mjs": CSRF_HELPER,
    }


def validate_public():
    require(os.geteuid() == HOME.stat().st_uid, "wrong_cpanel_uid")
    for folder in (HOME, SITE, ROOT, PUBLIC, STAGE):
        require(not folder.is_symlink(), "symlink_in_release_path")
    require(PUBLIC.is_dir() and ROOT.is_dir(), "live_game_or_private_root_missing")
    require((PUBLIC / "LC-OWNER.txt").read_text().strip() == PUBLIC_OWNER,
            "current_global_252_release_not_recognized")
    for path in PUBLIC.rglob("*"):
        require(not path.is_symlink(), "unexpected_public_symlink")
        rel = path.relative_to(PUBLIC)
        if path.is_file():
            require(str(rel) in {"index.html", "play/index.html", "LC-OWNER.txt", ".htaccess"}
                    or (rel.parent == STATIC and rel.name in ASSETS),
                    "unexpected_public_game_file:" + str(rel))
    require(all((PUBLIC / STATIC / name).is_file() for name in ASSETS),
            "incomplete_global_release")
    require(not (PUBLIC / STATIC / "account-csrf.mjs").exists(),
            "unexpected_existing_account_code")
    return changes_from_browser(
        (PUBLIC / "play/index.html").read_text(encoding="utf-8"),
        (PUBLIC / STATIC / "app.mjs").read_text(encoding="utf-8"),
        (PUBLIC / STATIC / "tycoon-panel.mjs").read_text(encoding="utf-8"),
        (PUBLIC / STATIC / "global-shell.mjs").read_text(encoding="utf-8"),
    )


def stage_review(changes):
    require(not STAGE.exists(), "review_stage_already_exists")
    require(shutil.disk_usage(str(SITE)).free > 250 * 1024 * 1024,
            "insufficient_disk_for_review_stage")
    shutil.copytree(PUBLIC, STAGE, symlinks=False)
    for rel, content in changes.items():
        file = STAGE / rel
        require(not file.is_symlink(), "unsafe_review_asset")
        file.write_text(content, encoding="utf-8")
        file.chmod(0o644)
    marker = STAGE / "LC-OWNER.txt"
    marker.write_text(REVIEW_OWNER + "\n", encoding="utf-8")
    marker.chmod(0o644)
    require((PUBLIC / "LC-OWNER.txt").read_text().strip() == PUBLIC_OWNER,
            "production_owner_changed")
    print("MPW_PRIVATE_ACCOUNT_UI_REVIEW_STAGE=" + str(STAGE))
    print("MPW_PUBLIC_GAME_UNTOUCHED=true")
    print("MPW_NO_PUBLISH_COMMAND=true")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "stage"))
    args = parser.parse_args()
    changes = validate_public()
    require(all(isinstance(s, str) for s in changes.values()), "nontext_asset")
    print("MPW_ACCOUNT_ASSET_CONTRACT=PASS")
    print("MPW_20_LANG_252_QUEST_SOURCE_PRESERVED=true")
    print("MPW_MOJ1_CHECKOUT_DISABLED=true")
    if args.action == "stage":
        stage_review(changes)


if __name__ == "__main__":
    main()
