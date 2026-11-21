(function () {
  'use strict';
  // Campaign-only routing across public MOJ PROP educational pages.
  // Never collect identity, wallet data, cookies, or query parameters.
  var allow = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content'];
  var query = new URLSearchParams(window.location.search);
  var campaign = {};
  allow.forEach(function (key) {
    var value = query.get(key);
    if (value && value.length <= 80 && /^[A-Za-z0-9_.:-]+$/.test(value)) {
      campaign[key] = value;
    }
  });
  if (Object.keys(campaign).length === 0) return;

  function allowedPath(path) {
    return path === '/moj-prop/' ||
      path === '/moj-prop/rules/' ||
      path === '/moj-prop/starter-30-trx/' ||
      path === '/moj-prop/education/' ||
      /^\/moj-prop\/education\/[a-z0-9-]+\/$/.test(path);
  }
  document.querySelectorAll('a[href]').forEach(function (link) {
    var url;
    try { url = new URL(link.getAttribute('href'), window.location.origin); }
    catch (error) { return; }
    if (url.origin !== window.location.origin || !allowedPath(url.pathname)) return;
    allow.forEach(function (key) {
      if (Object.prototype.hasOwnProperty.call(campaign, key) &&
          !url.searchParams.has(key)) {
        url.searchParams.set(key, campaign[key]);
      }
    });
    link.setAttribute('href', url.pathname + url.search + url.hash);
  });
})();
