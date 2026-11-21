(function () {
  'use strict';
  // These values describe campaign origin only. Never carry visitor data,
  // wallets, emails, receipt tokens, or arbitrary URL query parameters.
  var allowed = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content'];
  var incoming = new URLSearchParams(window.location.search);
  var inputs = {};
  allowed.forEach(function (key) {
    var raw = incoming.get(key);
    if (raw && raw.length <= 80 && /^[A-Za-z0-9_.:-]+$/.test(raw)) {
      inputs[key] = raw;
    }
  });
  if (Object.keys(inputs).length === 0) return;

  document.querySelectorAll('a[href]').forEach(function (anchor) {
    var url;
    try { url = new URL(anchor.getAttribute('href'), window.location.origin); }
    catch (e) { return; }
    if (url.origin !== window.location.origin ||
        url.pathname !== '/mojprop-starter30-checkout/') return;
    allowed.forEach(function (key) {
      if (Object.prototype.hasOwnProperty.call(inputs, key) &&
          !url.searchParams.has(key)) {
        url.searchParams.set(key, inputs[key]);
      }
    });
    anchor.setAttribute('href', url.pathname + url.search + url.hash);
  });
})();
