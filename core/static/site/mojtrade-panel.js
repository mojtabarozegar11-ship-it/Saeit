/* Public status only: no credentials, account access, order placement or live execution. */
(function () {
  'use strict';
  var blocks = document.querySelectorAll('[data-mojtrade-feed]');
  blocks.forEach(function (block) {
    var endpoint = block.getAttribute('data-mojtrade-feed');
    var state = block.querySelector('[data-mojtrade-status]');
    var list = block.querySelector('[data-mojtrade-signals]');
    var updated = block.querySelector('[data-mojtrade-updated]');
    var fa = block.getAttribute('lang') === 'fa';
    if (!endpoint || !state || !list || !updated) return;
    fetch(endpoint, { mode: 'cors', credentials: 'omit', cache: 'no-store' })
      .then(function (response) { if (!response.ok) throw new Error('feed unavailable'); return response.json(); })
      .then(function (data) {
        if (data.service !== 'MojTrade AI' || data.schema_version !== 1 ||
            data.live_trading_enabled !== false || data.execution_mode !== 'disabled') {
          throw new Error('untrusted feed');
        }
        var published = data.status === 'verified' && data.signal_publication === 'enabled';
        state.textContent = published ? (fa ? 'اطلاعات تأییدشده' : 'Verified feed') :
          (fa ? 'انتشار سیگنال غیرفعال' : 'Signal publication disabled');
        list.replaceChildren();
        if (published && Array.isArray(data.signals)) {
          data.signals.slice(0, 25).forEach(function (item) {
            var li = document.createElement('li');
            li.textContent = [item.market, item.symbol, item.timeframe, item.stance,
              item.observed_at, item.method, item.data_source].join(' · ');
            list.appendChild(li);
          });
        }
        updated.textContent = published && data.generated_at ?
          (fa ? 'زمان تولید: ' : 'Generated: ') + data.generated_at :
          (fa ? 'هیچ سیگنال تأییدشده‌ای برای انتشار موجود نیست.' : 'No approved signal available for publication.');
      })
      .catch(function () {
        state.textContent = fa ? 'اتصال برقرار نیست' : 'Feed unavailable';
        updated.textContent = fa ? 'اتصال زنده هنوز تأیید نشده است.' : 'Live feed connection has not been verified.';
      });
  });
})();
