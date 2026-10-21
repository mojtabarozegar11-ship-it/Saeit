(() => {
  'use strict';
  const el = (id) => document.getElementById(id);
  let config;
  try { config = JSON.parse(el('invoice-data').textContent); } catch { return; }
  const feedback = el('feedback');
  const changeStatus = (status) => {
    const region = document.querySelector('.payment-status');
    const title = region?.querySelector('b');
    const subtitle = region?.querySelector('div:nth-child(2) span');
    const badge = region?.querySelector('.status-label');
    if (!region || !title || !subtitle || !badge) return;
    region.dataset.status = status;
    if (status === 'paid') {
      title.textContent = 'Your TRX payment is confirmed';
      subtitle.textContent = 'Confirmed on the finalized TRON blockchain.';
      badge.textContent = 'PAID';
    } else if (status === 'expired') {
      title.textContent = 'Invoice expired';
      subtitle.textContent = 'Please request a new invoice before transferring TRX.';
      badge.textContent = 'EXPIRED';
    }
  };
  const display = (message, state = '') => {
    feedback.textContent = message;
    feedback.dataset.state = state;
  };
  const copy = async (value, element) => {
    if (!value || config.preview) return;
    try {
      await navigator.clipboard.writeText(value);
      const label = element.querySelector('span:last-child');
      if (label) { const old = label.textContent; label.textContent = 'Copied ✓'; setTimeout(() => { label.textContent = old; }, 1600); }
    } catch { display('Clipboard unavailable. Select the address or amount to copy.', 'error'); }
  };
  el('copy-address')?.addEventListener('click', (e) => copy(config.address, e.currentTarget));
  el('copy-amount')?.addEventListener('click', (e) => copy(config.amount, e.currentTarget));
  const timer = el('timer');
  const prog = el('timer-progress');
  const total = 600000;
  const updateTime = () => {
    if (config.preview) return;
    const remaining = Math.max(0, config.expires - Date.now());
    const mins = Math.floor(remaining / 60000);
    const secs = Math.floor((remaining % 60000) / 1000);
    timer.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    prog.style.width = `${Math.round(100 * remaining / total)}%`;
    if (remaining === 0 && config.status !== 'paid') { changeStatus('expired'); display('Invoice expired. Do not send new funds. Contact support for a fresh invoice.', 'error'); }
  };
  if (config.status === 'paid') changeStatus('paid');
  updateTime();
  if (!config.preview) setInterval(updateTime, 1000);
  const statusUrl = config.preview ? null : `/api/status/${config.token}`;
  let verifying = false;
  const refresh = async () => {
    if (!statusUrl || document.hidden || verifying) return;
    try {
      const response = await fetch(statusUrl, {cache:'no-store', credentials:'same-origin'});
      if (!response.ok) return;
      const state = await response.json();
      if (state.status === 'expired' && config.status !== 'paid') changeStatus('expired');
      if (state.status === 'paid') {
        config.status = 'paid';
        changeStatus('paid');
        display('TRON payment confirmed on a finalized block. Your order is recorded as paid.', 'paid');
        el('stage-done').classList.add('done');
        el('verify-button').disabled = true;
        el('txid').disabled = true;
      }
    } catch { /* Temporary network failure does not imply failed payment. */ }
  };
  if (!config.preview) { refresh(); setInterval(refresh, 12000); }
  el('verify-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (config.preview || verifying || config.status === 'paid') return;
    const txid = el('txid').value.trim().toLowerCase();
    if (!/^[0-9a-f]{64}$/.test(txid)) {
      display('Enter the complete 64-character TRON transaction hash.', 'error'); return;
    }
    verifying = true;
    el('verify-button').disabled = true;
    display('Checking the finalized TRON blockchain. Do not send payment again.');
    try {
      const response = await fetch(`/api/verify/${config.token}`, {
        method: 'POST', credentials:'same-origin', cache:'no-store',
        headers: {'Content-Type':'application/json'}, body:JSON.stringify({txid})
      });
      const result = await response.json();
      if (response.ok && result.status === 'paid') {
        config.status = 'paid';
        changeStatus('paid');
        display('Payment finalized and registered. Your order has been marked paid.', 'paid');
        el('stage-done').classList.add('done'); el('txid').disabled = true;
      } else display(result.message || 'Not finalized yet. Try again without sending another payment.', 'error');
    } catch { display('Connection interrupted. Re-check this invoice; do not pay twice.', 'error'); }
    finally { verifying = false; if (config.status !== 'paid') el('verify-button').disabled = false; }
  });
})();