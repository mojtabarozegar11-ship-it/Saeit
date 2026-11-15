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
  "status-check", "status-result", "selected-signal-plan", "notes",
  "service", "name", "email", "horizon", "website", "consent"];
function makeNode() {
  return {
    value: "", hidden: true, checked: false, disabled: false, textContent: "",
    maxLength: 5000, listeners: {}, addEventListener(type, handler) {
      this.listeners[type] = handler;
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

    def _browser(self, query: str, service: str = "", notes: str = "") -> dict:
        if shutil.which("node") is None:
            self.skipTest("Node runtime is unavailable in this environment")
        result = subprocess.run(
            ["node", "-e", NODE_BROWSER, str(HOME), query, service, notes],
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

    def test_bounded_notes_must_not_create_a_false_receipt(self):
        state = self._browser(
            "?service=signals&plan=education-weekly",
            notes="G" * 4970,
        )
        self.assertEqual(state["posted"], [])
        self.assertFalse(state["downloadEnabled"])
        self.assertIn("Request NOT submitted", state["receipt"])


if __name__ == "__main__":
    unittest.main()
