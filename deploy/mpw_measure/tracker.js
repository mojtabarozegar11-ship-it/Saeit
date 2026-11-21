/* MojPlayWin optional first-party visit and purchase-intent telemetry.
 * No PII, URL query strings, IPs, wallet addresses, form field values or
 * purchases are transmitted. Consent is required before any event.
 */
(function () {
  "use strict";
  var pathname = location.pathname;
  function pageKey(p) {
    if (p === "/store/") return "/store/";
    if (/^\/store\/product\/[0-9]+\/$/.test(p)) return "/store/product/";
    if (p === "/commerce/trx-easy/") return p;
    if (/^\/commerce\/book\/[0-9]+\/$/.test(p)) return "/commerce/book/";
    if (/^\/commerce\/trx-easy\/invoice\/[0-9]+\/$/.test(p)) return "/commerce/trx-easy/invoice/";
    if (p === "/commerce/trx-easy/purchases/") return p;
    if (p === "/commerce/trx-easy/recover/") return p;
    if (p === "/moj-prop/" || p === "/moj-prop/starter-30-trx/" ||
        p === "/moj-prop/payment/" || p === "/moj-prop/catalog/" ||
        p === "/moj-prop/rules/" || p === "/moj-prop/contact/" ||
        p === "/mojprop-starter30-checkout/") return p;
    return "";
  }
  var page = pageKey(pathname);
  if (!page || !window.crypto || !crypto.getRandomValues || !window.fetch) return;
  var consentKey = "mpw_measure_consent_v1", sessionKey = "mpw_measure_session_v1";
  var enabled = false, engaged = false, started = false;
  var session = "";
  function sessionId() {
    try {
      var old = JSON.parse(sessionStorage.getItem(sessionKey) || "null");
      if (old && /^[a-f0-9]{32}$/.test(old.id) && Date.now() - old.at < 1800000) {
        old.at = Date.now(); sessionStorage.setItem(sessionKey, JSON.stringify(old)); return old.id;
      }
      var b = new Uint8Array(16); crypto.getRandomValues(b);
      var id = Array.from(b, function (x) { return x.toString(16).padStart(2, "0"); }).join("");
      sessionStorage.setItem(sessionKey, JSON.stringify({id: id, at: Date.now()}));
      return id;
    } catch (e) { return ""; }
  }
  function utm(name) {
    var v = new URLSearchParams(location.search).get("utm_" + name) || "";
    return /^[a-zA-Z0-9_-]{1,48}$/.test(v) ? v.slice(0, name === "campaign" ? 48 : 32) : "";
  }
  function send(event) {
    if (!enabled || !session || document.visibilityState === "hidden") return;
    var data = JSON.stringify({
      event: event, page: page, session: session,
      source: utm("source"), medium: utm("medium"), campaign: utm("campaign")
    });
    try {
      fetch("/mpw-measure/collect.php", {
        method: "POST", mode: "same-origin", credentials: "omit",
        cache: "no-store", keepalive: true,
        headers: {"Content-Type": "application/json"}, body: data
      }).catch(function () {});
    } catch (e) {}
  }
  function engagedEvent() {
    if (engaged || !enabled) return;
    engaged = true; send("engaged");
  }
  function start() {
    if (started) return;
    started = true; enabled = true; session = sessionId();
    if (!session) return;
    if (document.visibilityState === "visible") send("page");
    ["pointerdown", "keydown", "touchstart", "scroll"].forEach(function (eventName) {
      addEventListener(eventName, engagedEvent, {once:true, passive:true});
    });
  }
  function optOut() {
    enabled = false; session = "";
    try { sessionStorage.removeItem(sessionKey); } catch (e) {}
  }
  function banner() {
    var node = document.createElement("section");
    node.setAttribute("role", "region");
    node.setAttribute("aria-label", "Optional analytics consent");
    node.style.cssText = "position:fixed;z-index:2147483645;bottom:12px;left:12px;right:12px;max-width:660px;margin:auto;background:#17202b;color:#f6f2e9;border:1px solid #b8a470;border-radius:12px;padding:14px 16px;font:13px/1.5 system-ui;box-shadow:0 8px 30px #0009";
    node.innerHTML = '<span>Allow optional anonymous visit and purchase-click measurement? No email, wallet, form content or payment details are collected. <a href="/privacy/" style="color:#a5ebdf">Privacy</a>.</span> ';
    var yes = document.createElement("button"), no = document.createElement("button");
    yes.type = no.type = "button";
    yes.textContent = "Allow"; no.textContent = "Decline";
    [yes, no].forEach(function (button) {
      button.style.cssText = "margin:6px 6px 0 0;padding:6px 12px;border:1px solid #c5ad6f;border-radius:8px;background:#e6c77c;color:#1a1a1a;font:600 12px system-ui;cursor:pointer";
      node.appendChild(button);
    });
    yes.addEventListener("click", function () {
      try { localStorage.setItem(consentKey, "yes"); } catch (e) {}
      node.remove(); start();
    });
    no.addEventListener("click", function () {
      try { localStorage.setItem(consentKey, "no"); } catch (e) {}
      node.remove(); optOut();
    });
    document.body.appendChild(node);
  }
  function onLinkClick(e) {
    if (!enabled) return;
    var a = e.target && e.target.closest ? e.target.closest("a[href]") : null;
    if (!a) return;
    var u;
    try { u = new URL(a.href, location.href); } catch (error) { return; }
    if (u.origin !== location.origin) return;
    var p = u.pathname;
    if (/^\/commerce\/book\/[0-9]+\/$/.test(p) ||
        p === "/mojprop-starter30-checkout/" ||
        p === "/moj-prop/starter-30-trx/") {
      send("buy_click");
    } else if (/^\/store\/product\/[0-9]+\/$/.test(p)) {
      send("product_click");
    } else if (p === "/moj-prop/catalog/" || p === "/moj-prop/rules/" ||
               p === "/moj-prop/payment/") {
      send("plan_click");
    } else if (p === "/moj-prop/contact/" || p === "/support/") {
      send("help_click");
    }
    engagedEvent();
  }
  function init() {
    document.addEventListener("click", onLinkClick, true);
    document.addEventListener("submit", function (e) {
      if (enabled && e.target && e.target.tagName === "FORM") {
        send("form_submit"); engagedEvent();
      }
    }, true);
    var consent = "";
    try { consent = localStorage.getItem(consentKey) || ""; } catch (e) {}
    if (consent === "yes") start();
    else if (consent !== "no") banner();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
