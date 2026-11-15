"""End-to-end browser contract for manual educational plan inquiries.

This executes the real inline homepage JavaScript in a minimal DOM under Node.
It creates no real order, payment, email, wallet call or outside network traffic.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "templates" / "moj-prop-v4" / "index.html"
SIGNALS = ROOT / "templates" / "moj-prop" / "signals" / "index.html"

NODE_BROWSER = r"""
const fs = require("fs");
const vm = require("vm");
const html = fs.readFileSync(process.argv[1], "utf8");
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)];
const applicationScript = scripts.find(s => s[1].includes("const form=document.getElementById('request-form')"));
if (!applicationScript) throw Error("Application form script was not found");
const ids = ["request-form", "result", "copy", "download", "receipt-token",
  "status-check", "status-result", "selected-signal-plan", "selected-starter30", "notes",
  "service", "name", "email", "horizon", "website", "consent",
  "digital-product", "digital-product-field", "status-form", "status-token"];
function makeNode() {
  return {
    value: "", hidden: true, checked: false, disabled: false, textContent: "",
    style: {}, required: false,
    maxLength: 5000, listeners: {}, addEventListener(type, handler) {
      const earlier=this.listeners[type];
      this.listeners[type]=earlier ? (...args)=>{earlier(...args);return handler(...args);} : handler;
    }, setAttribute() {}, removeAttribute() {}
  };
}
const elements = Object.fromEntries(ids.map(id => [id, makeNode()]));
elements["name"].value = "Real Buyer";
elements["email"].value = "buyer@example.com";
elements["service"].value = "blueprint";
elements["horizon"].value = "week";
elements["notes"].value = process.argv[4] || "A detailed educational research objective for gold.";
elements["consent"].checked = true;
elements["request-form"].querySelector = () => makeNode();
const posted = [];
const ctx = {
  URLSearchParams,
  AbortController,
  setTimeout: () => 1,
  clearTimeout: () => {},
  window: { location: { search: process.argv[2] || "" } },
  document: { getElementById(id) {
    if (!elements[id]) throw Error("Missing test DOM node: " + id);
    return elements[id];
  }},
  fetch: async (url, options) => {
    if (!options || !options.method) {
      return {ok:true, json:async()=>({csrf_token:"test-only-csrf"})};
    }
    posted.push({url, body:JSON.parse(options.body)});
    if (process.argv[5]==="response-lost") throw Error("response lost after POST");
    if (process.argv[5]==="bad-email") return {status:400,ok:false,json:async()=>({ok:false,detail:"Invalid fields",fields:{email:"Use a real email."}})};
    if (process.argv[5]==="throttled") return {status:429,ok:false,json:async()=>({ok:false,detail:"Too many requests."})};
    return {status:201,ok:true,json:async()=>({
      ok:true, request_id:"MOJPROP-20261115-A1B2C3D4",
      receipt_token:"synthetic-signed-token"
    })};
  }
};
vm.runInNewContext(applicationScript[1], ctx, {timeout:1000});
if (process.argv[3]) {
  elements["service"].value = process.argv[3];
  elements["service"].listeners.change();
}
(async () => {
  await elements["request-form"].listeners.submit({preventDefault(){}});
  process.stdout.write(JSON.stringify({
    posted,
    service:elements["service"].value,
    summary:elements["selected-signal-plan"].textContent,
    hidden:elements["selected-signal-plan"].hidden,
    starter:elements["selected-starter30"].textContent,
    starterHidden:elements["selected-starter30"].hidden,
    notesMaxLength:elements["notes"].maxLength,
    receipt:elements["result"].textContent,
    downloadEnabled:!elements["download"].disabled
  }));
})().catch(err => {console.error(err); process.exitCode = 1;});
"""


class SignalPlanInquiryTests(unittest.TestCase):
    def test_three_price_card_links_target_the_real_intake_page(self):
        html = SIGNALS.read_text(encoding="utf-8")
        for plan in ("education-weekly", "education-monthly", "education-quarterly"):
            with self.subTest(plan=plan):
                self.assertIn(
                    'href="/moj-prop/?service=signals&plan=' + plan + '#request"',
                    html,
                )

    def test_browser_inquiry_is_explicitly_nonfinancial(self):
        html = HOME.read_text(encoding="utf-8")
        self.assertIn("No payment or subscription is active", html)
        self.assertIn("written quote required", html)
        self.assertIn("notes:submittedNotes", html)
        self.assertIn("selected-signal-plan", html)

    def _browser(self, query: str, service: str = "", notes: str = "", mode: str = "") -> dict:
        if shutil.which("node") is None:
            self.skipTest("Node runtime is unavailable in this environment")
        result = subprocess.run(
            ["node", "-e", NODE_BROWSER, str(HOME), query, service, notes, mode],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_weekly_plan_persists_in_post_and_private_receipt(self):
        state = self._browser("?service=signals&plan=education-weekly")
        self.assertEqual(len(state["posted"]), 1)
        self.assertEqual(state["posted"][0]["body"]["service"], "signals")
        self.assertIn("education-weekly", state["posted"][0]["body"]["notes"])
        self.assertIn("indicative USD 9.90", state["posted"][0]["body"]["notes"])
        self.assertIn("education-weekly", state["receipt"])
        self.assertTrue(state["downloadEnabled"])
        self.assertFalse(state["hidden"])

    def test_monthly_plan_is_not_dropped(self):
        state = self._browser("?service=signals&plan=education-monthly")
        self.assertIn("education-monthly", state["posted"][0]["body"]["notes"])
        self.assertIn("29.90", state["summary"])

    def test_quarterly_plan_is_not_dropped(self):
        state = self._browser("?service=signals&plan=education-quarterly")
        self.assertIn("education-quarterly", state["posted"][0]["body"]["notes"])
        self.assertIn("79.90", state["summary"])

    def test_unknown_plan_is_ignored_not_reflected(self):
        state = self._browser("?service=signals&plan=%3Cscript%3E")
        self.assertTrue(state["hidden"])
        self.assertEqual(state["notesMaxLength"], 5000)
        self.assertNotIn("Requested educational plan", state["posted"][0]["body"]["notes"])
        self.assertNotIn("<script>", state["receipt"])

    def test_non_signal_service_never_claims_a_signal_plan(self):
        state = self._browser("?service=blueprint&plan=education-monthly")
        self.assertTrue(state["hidden"])
        self.assertEqual(state["posted"][0]["body"]["service"], "blueprint")
        self.assertNotIn("education-monthly", state["posted"][0]["body"]["notes"])

    def test_switching_away_from_signals_removes_plan_attribution(self):
        state = self._browser("?service=signals&plan=education-weekly", "audit")
        self.assertTrue(state["hidden"])
        self.assertEqual(state["notesMaxLength"], 5000)
        self.assertEqual(state["posted"][0]["body"]["service"], "audit")
        self.assertNotIn("Requested educational plan", state["posted"][0]["body"]["notes"])

    def test_digital_product_inquiry_survives_parallel_signal_plan_fix(self):
        state = self._browser("?service=digital&product=72")
        self.assertEqual(state["posted"][0]["body"]["service"], "digital")
        self.assertEqual(state["posted"][0]["body"]["product_id"], 72)
        self.assertNotIn("Requested educational plan", state["posted"][0]["body"]["notes"])

    def test_bounded_notes_must_not_create_a_false_receipt(self):
        state = self._browser(
            "?service=signals&plan=education-weekly",
            notes="G" * 4970,
        )
        self.assertEqual(state["posted"], [])
        self.assertFalse(state["downloadEnabled"])
        self.assertIn("Request NOT submitted", state["receipt"])


    def test_free_educational_request_preserves_free_scope_not_paid_sku(self):
        state = self._browser("?service=signals&tier=free")
        self.assertEqual(len(state["posted"]), 1)
        notes = state["posted"][0]["body"]["notes"]
        self.assertEqual(state["posted"][0]["body"]["service"], "signals")
        self.assertIn("Requested free educational example", notes)
        self.assertIn("FREE", state["summary"])
        self.assertIn("free educational example", state["receipt"].lower())
        self.assertNotIn("Requested educational plan:", notes)
        self.assertTrue(state["downloadEnabled"])
        self.assertFalse(state["hidden"])

    def test_free_tier_wins_over_buyer_supplied_paid_plan_parameter(self):
        state = self._browser("?service=signals&tier=free&plan=education-quarterly")
        self.assertIn("Requested free educational example", state["posted"][0]["body"]["notes"])
        self.assertNotIn("education-quarterly", state["posted"][0]["body"]["notes"])
        self.assertNotIn("79.90", state["summary"])

    def test_switching_away_removes_free_entitlement_claim(self):
        state = self._browser("?service=signals&tier=free", "audit")
        self.assertTrue(state["hidden"])
        self.assertNotIn("Requested free educational example", state["posted"][0]["body"]["notes"])
        self.assertEqual(state["posted"][0]["body"]["service"], "audit")

    def test_unknown_free_tier_is_not_a_free_request(self):
        state = self._browser("?service=signals&tier=bogus")
        self.assertNotIn("Requested free educational example", state["posted"][0]["body"]["notes"])
        self.assertTrue(state["hidden"])


    def test_canonical_starter_single_sku_scope_is_consistent(self):
        home = HOME.read_text("utf-8")
        catalog = (ROOT / "templates/moj-prop-v4/catalog/index.html").read_text("utf-8")
        detail = (ROOT / "templates/moj-prop-v4/starter-30-trx/index.html").read_text("utf-8")
        for page in (home, catalog, detail):
            self.assertIn("30", page)
            self.assertIn("TRX", page)
            self.assertIn("starter-30-trx#request", page)
            self.assertNotIn("two-page risk-readiness", page.lower())
        self.assertIn("10-session", catalog)
        self.assertIn("ten-session", home)
        self.assertIn("MOJPROP-STARTER30", detail)

    def test_canonical_starter_prefills_real_crm_and_private_receipt(self):
        state = self._browser("?service=blueprint&package=starter-30-trx")
        self.assertEqual(len(state["posted"]), 1)
        p = state["posted"][0]["body"]
        self.assertEqual(p["service"], "blueprint")
        self.assertIsNone(p["product_id"])
        self.assertIn("MOJPROP-STARTER30", p["notes"])
        self.assertIn("30 native TRX", p["notes"])
        self.assertIn("NOT paid", p["notes"])
        self.assertIn("MOJPROP-STARTER30", state["receipt"])
        self.assertFalse(state["starterHidden"])
        self.assertTrue(state["downloadEnabled"])

    def test_wrong_and_unknown_package_codes_are_ignored(self):
        for query in (
            "?service=signals&package=starter-30-trx",
            "?service=blueprint&package=%3Cscript%3E",
            "?service=blueprint&package=starter-30-trx%0Apaid",
        ):
            with self.subTest(query=query):
                state = self._browser(query)
                self.assertTrue(state["starterHidden"])
                self.assertNotIn("MOJPROP-STARTER30", state["posted"][0]["body"]["notes"])
                self.assertNotIn("<script>", state["receipt"])

    def test_starter_switch_to_audit_drops_package_claim(self):
        state = self._browser("?service=blueprint&package=starter-30-trx", service="audit")
        self.assertTrue(state["starterHidden"])
        self.assertEqual(state["posted"][0]["body"]["service"], "audit")
        self.assertNotIn("MOJPROP-STARTER30", state["posted"][0]["body"]["notes"])
        self.assertFalse(state["hidden"])

    def test_starter_note_prefix_cannot_exceed_server_max(self):
        state = self._browser("?service=blueprint&package=starter-30-trx", notes="X"*4970)
        self.assertEqual(state["posted"], [])
        self.assertFalse(state["downloadEnabled"])
        self.assertIn("Request NOT submitted", state["receipt"])

    def test_server_explicit_400_keeps_correctable_error(self):
        state = self._browser("?service=blueprint&package=starter-30-trx", mode="bad-email")
        self.assertIn("email: Use a real email.", state["receipt"])
        self.assertIn("Request NOT submitted", state["receipt"])
        self.assertNotIn("Submission status unconfirmed", state["receipt"])

    def test_server_explicit_429_keeps_retry_guidance(self):
        state = self._browser("?service=blueprint&package=starter-30-trx", mode="throttled")
        self.assertIn("Wait before resubmitting", state["receipt"])
        self.assertIn("Request NOT submitted", state["receipt"])

    def test_lost_post_response_never_claims_payment_or_id(self):
        state = self._browser("?service=blueprint&package=starter-30-trx", mode="response-lost")
        self.assertEqual(len(state["posted"]), 1)
        self.assertIn("Submission status unconfirmed", state["receipt"])
        self.assertIn("Avoid duplicate submissions", state["receipt"])
        self.assertNotIn("No ID or payment was created", state["receipt"])
        self.assertFalse(state["downloadEnabled"])


if __name__ == "__main__":
    unittest.main()
