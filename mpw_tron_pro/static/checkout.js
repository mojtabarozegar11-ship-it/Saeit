(() => {
  'use strict';
  const el = (id) => document.getElementById(id);
  let config;
  try { config = JSON.parse(el('invoice-data').textContent); } catch { return; }
  const feedback = el('feedback');
  const timer = el('timer');
  const progress = el('timer-progress');
  const startMono = performance.now();
  const serverStart = Number(config.serverNow) || Date.now();
  const networkMainnet = '0x2b6653dc';
  let verifying = false;
  let lastTxid = '';
  let walletBusy = false;
  const deadline = Number(config.expires) || 0;
  const nowServer = () => serverStart + Math.max(0, performance.now() - startMono);
  const monitorNotice = el('monitoring-notice');
  function monitorStatus(code) {
    if (!monitorNotice || config.preview) return;
    monitorNotice.classList.remove('running','degraded');
    if (code === 'running') {
      monitorNotice.classList.add('running');
      monitorNotice.textContent = 'Automatic blockchain monitoring is active. You can leave this page and return later.';
    } else if (code === 'degraded') {
      monitorNotice.classList.add('degraded');
      monitorNotice.textContent = 'Automatic monitoring reports degraded health. Keep your transaction ID.';
    } else {
      monitorNotice.textContent = 'Automatic scanning is unavailable or not configured. Manual transaction verification is available.';
    }
  }
  monitorStatus(config.monitoring || 'not_configured');
  const terminal = () => config.status === 'paid';
  const needsReview = () => config.status === 'underpaid' || config.status === 'overpaid';
  const preventNewSend = () => config.preview || terminal() || needsReview() || nowServer() > deadline;
  const msg = (message, state = '') => {
    if (feedback) { feedback.textContent = message; feedback.dataset.state = state; }
  };
  function disableSend() {
    for (const id of ['copy-address', 'copy-amount', 'tronlink-pay']) {
      if (el(id)) el(id).disabled = true;
    }
    const trust = el('trust-wallet-pay');
    if (trust) { trust.setAttribute('aria-disabled', 'true'); trust.removeAttribute('href'); trust.setAttribute('tabindex','-1'); }
  }
  function phase(name) {
    const quote = el('phase-quote'), chain = el('phase-chain'), final = el('phase-final'), delivery = el('phase-delivery');
    if (!quote || !chain || !final || !delivery) return;
    for (const item of [quote, chain, final, delivery]) {item.classList.remove('active','done');}
    quote.classList.add('done');
    if (name === 'paid') {chain.classList.add('done'); final.classList.add('active');}
    else if (name === 'checking') {chain.classList.add('active');}
    else {quote.classList.remove('done'); quote.classList.add('active');}
  }
  const changeStatus = (status) => {
    const region = document.querySelector('.payment-status');
    const title = region?.querySelector('b');
    const subtitle = region?.querySelector('div:nth-child(2) span');
    const badge = region?.querySelector('.status-label');
    if (!region || !title || !subtitle || !badge) return;
    region.dataset.status = status;
    const states = {
      paid: ['Your TRX payment is confirmed','Verified on a finalized TRON block.','PAID'],
      expired: ['Invoice expired','Do not start a new transfer. An earlier transfer can still be reviewed.','EXPIRED'],
      underpaid: ['Transfer requires attention','A finalized transfer was found, but the amount was less than quoted.','REVIEW'],
      overpaid: ['Transfer requires attention','A finalized transfer was found, but the amount was more than quoted.','REVIEW'],
      checking: ['Transaction submitted','Checking TRON finality. Do not initiate a second transfer.','CHECKING'],
      pending: ['Waiting for your payment','Automatic status updates require an active server scanner.','PENDING']
    };
    const data = states[status] || states.pending;
    title.textContent = data[0]; subtitle.textContent = data[1]; badge.textContent = data[2];
    phase(status);
    if (status === 'paid' || status === 'expired' || status === 'underpaid' || status === 'overpaid') disableSend();
    if (status === 'paid') {
      if (el('verify-button')) el('verify-button').disabled = true;
      if (el('txid')) el('txid').disabled = true;
    }
  };
  function updateDelivery(status) {
    const box = el('fulfillment-notice');
    if (!box) return;
    box.dataset.status = status;
    const delivered = status === 'delivered';
    const queued = status === 'pending_delivery';
    box.textContent = delivered
      ? '✓ Digital delivery confirmed by MojPlayWin. Access your product from your purchase library.'
      : queued ? 'TRX confirmed. The delivery agent is processing your purchase automatically.'
      : 'Payment is confirmed, but the store delivery integration is not active. Contact support with your order number; do not pay again.';
    if (delivered) {
      el('stage-done')?.classList.add('done');
      el('phase-final')?.classList.add('done');
      el('phase-delivery')?.classList.add('active');
    }
  }
  function proofLink(txid) {
    if (!/^[a-f0-9]{64}$/.test(txid || '')) return;
    const section = el('receipt-proof'), link = el('receipt-link');
    if (!section || !link) return;
    link.href = `https://tronscan.org/#/transaction/${txid}`;
    section.hidden = false;
  }
  async function copy(value, element) {
    if (!value || preventNewSend()) return;
    try {
      await navigator.clipboard.writeText(value);
      const label = element.querySelector('span:last-child');
      if (label) {
        const old = label.textContent; label.textContent = 'Copied ✓';
        setTimeout(() => { label.textContent = old; }, 1600);
      }
    } catch { msg('Could not copy. Manually select and copy the details shown.', 'error'); }
  }
  el('copy-address')?.addEventListener('click', (e) => copy(config.address, e.currentTarget));
  el('copy-amount')?.addEventListener('click', (e) => copy(config.amount, e.currentTarget));
  el('trust-wallet-pay')?.addEventListener('click', (e) => {
    if (preventNewSend()) { e.preventDefault(); return; }
    msg('Confirm the recipient and exact TRX amount in Trust Wallet. Do not send twice.');
  });
  function updateTime() {
    if (config.preview) return;
    const remaining = Math.max(0, deadline - nowServer());
    if (timer) {
      const minutes = Math.floor(remaining / 60000);
      const seconds = Math.floor((remaining % 60000) / 1000);
      timer.textContent = `${String(minutes).padStart(2,'0')}:${String(seconds).padStart(2,'0')}`;
    }
    if (progress) progress.style.width = `${Math.min(100,Math.max(0,Math.round(100*remaining/600000)))}%`;
    if (remaining <= 0 && !terminal() && !needsReview()) {
      config.status = 'expired'; changeStatus('expired');
    }
  }
  if (config.status === 'paid') { changeStatus('paid'); updateDelivery(config.fulfillment); }
  else if (needsReview()) changeStatus(config.status);
  updateTime();
  if (!config.preview) setInterval(updateTime,1000);
  const statusUrl = config.preview ? null : `/api/status/${config.token}`;
  const refresh = async () => {
    if (!statusUrl || document.hidden || verifying) return;
    try {
      const response = await fetch(statusUrl,{cache:'no-store',credentials:'same-origin'});
      if (!response.ok) return;
      const state = await response.json();
      monitorStatus(state.monitoring);
      if (state.status === 'paid' && state.payment_confirmed === true) {
        config.status = 'paid'; changeStatus('paid'); proofLink(state.txid);
        updateDelivery(state.fulfillment);
        msg(state.fulfillment === 'delivered'
          ? 'Payment and digital delivery confirmed.'
          : 'Payment confirmed. Automatic delivery is awaiting store acknowledgement.', 'paid');
      } else if (state.status === 'underpaid' || state.status === 'overpaid') {
        config.status = state.status; changeStatus(state.status);
        msg('A finalized transfer was detected but does not match the invoice. Do not pay again; contact support.', 'error');
      } else if (state.status === 'expired' && !terminal()) {
        config.status = 'expired'; changeStatus('expired');
      }
    } catch { /* Temporary network errors do not mean payment failed. */ }
  };
  if (!config.preview) { refresh(); setInterval(refresh,12000); document.addEventListener('visibilitychange', () => {if (!document.hidden) refresh();}); }

  async function verifyTxId(txid, {silent = false} = {}) {
    if (!/^[0-9a-f]{64}$/.test(txid)) {
      if (!silent) msg('Enter a valid 64-character TRON transaction ID.', 'error');
      return false;
    }
    if (config.preview || terminal() || verifying) return false;
    verifying = true;
    if (el('verify-button')) el('verify-button').disabled = true;
    if (!silent) msg('Checking the finalized TRON blockchain. Do not send payment again.');
    try {
      const response = await fetch(`/api/verify/${config.token}`,{
        method:'POST',credentials:'same-origin',cache:'no-store',
        headers:{'Content-Type':'application/json'},body:JSON.stringify({txid})
      });
      const state = await response.json();
      if (response.ok && state.status === 'paid') {
        config.status = 'paid'; changeStatus('paid'); proofLink(state.txid || txid);
        updateDelivery('pending_delivery');
        msg('TRX verified. Automatic delivery is pending store acknowledgement.', 'paid');
        return true;
      }
      if (response.ok && ['underpaid','overpaid'].includes(state.status)) {
        config.status = state.status; changeStatus(state.status);
        msg('Transfer requires manual review due to amount mismatch. Do not pay again.', 'error');
        return false;
      }
      if (!silent) msg(response.status === 429 ? 'Verification limit reached. Please use automatic status updates.' :
        (state.message || 'Finality not confirmed yet. Do not send another transfer.'), 'error');
    } catch {if (!silent) msg('Connection interrupted. Revisit this invoice; do not initiate another transfer.', 'error');}
    finally {verifying = false; if (!terminal() && el('verify-button')) el('verify-button').disabled = false;}
    return false;
  }
  el('verify-form')?.addEventListener('submit', (event) => {
    event.preventDefault();
    const txid = el('txid')?.value.trim().toLowerCase() || '';
    verifyTxId(txid);
  });

  // Wallet requests never see recovery words or secret keys. Signing always happens
  // inside the user's already-installed TronLink provider, after user consent.
  const tronButton = el('tronlink-pay');
  const providerAvailable = () => Boolean(window.tron?.isTronLink && window.tron?.request);
  if (!config.preview && tronButton && !providerAvailable()) {
    tronButton.disabled = true;
    tronButton.title = 'TronLink browser provider not detected. Use Trust Wallet or QR.';
  }
  if (el('wallet-support') && !config.preview && !providerAvailable()) {
    el('wallet-support').textContent = 'TronLink not detected in this browser. Trust Wallet and QR remain available. Never share your recovery phrase.';
  }
  tronButton?.addEventListener('click', async () => {
    if (preventNewSend() || walletBusy || !providerAvailable()) return;
    const amountSun = config.amountSun;
    if (!Number.isSafeInteger(amountSun) || amountSun <= 0 || amountSun > 10**13 ||
        !/^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(config.address || '')) {
      msg('Untrusted checkout quote; payment disabled.','error'); return;
    }
    walletBusy = true; tronButton.disabled = true;
    let txid = '';
    try {
      const provider = window.tron;
      await provider.request({method:'eth_requestAccounts'});
      const chainRaw = await provider.request({method:'eth_chainId'});
      const chain = typeof chainRaw === 'object' && chainRaw ? chainRaw.result : chainRaw;
      if (typeof chain !== 'string' || chain.toLowerCase() !== networkMainnet) {
        throw new Error('Switch your wallet to TRON Mainnet before approving payment.');
      }
      const tronWeb = provider.tronWeb;
      if (!tronWeb?.transactionBuilder?.sendTrx || !tronWeb?.trx?.sign || !tronWeb?.trx?.sendRawTransaction || !tronWeb?.address?.toHex) {
        throw new Error('Your wallet does not support secure TRX signing in this browser.');
      }
      const sender = tronWeb.defaultAddress?.base58;
      if (!/^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(sender || '')) throw new Error('Wallet sender address missing.');
      if (preventNewSend()) throw new Error('Invoice expired. Request a fresh invoice before transferring.');
      msg('Review the destination and TRX amount in TronLink before you approve.');
      const unsigned = await tronWeb.transactionBuilder.sendTrx(config.address, amountSun, sender);
      const contract = unsigned?.raw_data?.contract?.[0];
      const values = contract?.parameter?.value;
      const intended = tronWeb.address.toHex(config.address).toUpperCase();
      const from = tronWeb.address.toHex(sender).toUpperCase();
      if (!/^[a-f0-9]{64}$/i.test(unsigned?.txID || '') ||
          unsigned.raw_data.contract.length !== 1 || contract.type !== 'TransferContract' ||
          values?.to_address?.toUpperCase() !== intended ||
          values?.owner_address?.toUpperCase() !== from || values?.amount !== amountSun) {
        throw new Error('Wallet transaction differs from the verified invoice; signing stopped.');
      }
      txid = unsigned.txID.toLowerCase();
      if (el('txid')) el('txid').value = txid;
      const signed = await tronWeb.trx.sign(unsigned);
      if (signed?.txID?.toLowerCase() !== txid || !Array.isArray(signed.signature) || !signed.signature.length) {
        throw new Error('Transaction not signed. No confirmed transfer.');
      }
      const broadcast = await tronWeb.trx.sendRawTransaction(signed);
      // Broadcast acknowledgement is NEVER evidence of a finalized TRON payment.
      lastTxid = txid;
      changeStatus('checking');
      msg(broadcast?.result === true ?
        'Transaction broadcast. Waiting for finality; do not send again.' :
        'Broadcast status uncertain. Check this transaction ID before any further action.');
      // Probe at bounded intervals; status polling will also update after server reconciliation.
      for (const ms of [12000, 30000, 45000]) {
        setTimeout(() => {if (!terminal() && !needsReview()) verifyTxId(lastTxid,{silent:true});}, ms);
      }
    } catch (error) {
      msg(txid ? 'Transaction may be pending. Check the transaction ID before paying again.' :
        (error?.message || 'Wallet connection cancelled or unavailable. No transfer confirmed.'), 'error');
    } finally { walletBusy = false; if (!preventNewSend() && providerAvailable()) tronButton.disabled = false; }
  });
})();