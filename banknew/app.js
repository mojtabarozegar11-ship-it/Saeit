'use strict';

function quote(value) {
  if (!/^(0|[1-9]\d{0,11})(\.\d{1,2})?$/.test(value)) {
    throw Error('Enter a non-negative amount with up to two decimal places.');
  }
  const [whole, part = ''] = value.split('.');
  const cents = BigInt(whole) * 100n + BigInt(part.padEnd(2, '0'));
  const fee = (cents + 500n) / 1000n;
  return { fee, net: cents - fee };
}

function money(cents) {
  return '$' + (cents / 100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',') +
    '.' + (cents % 100n).toString().padStart(2, '0');
}

function formatSun(value) {
  const sun = BigInt(value);
  if (sun < 0n) throw Error('Invalid TRX balance.');
  const whole = sun / 1000000n;
  const fractional = (sun % 1000000n).toString().padStart(6, '0').replace(/0+$/, '');
  return whole.toString() + (fractional ? '.' + fractional : '') + ' TRX';
}

/** Requests only an account address and a read-only native balance. Never signs or sends funds. */
async function getTronState(provider) {
  if (!provider || typeof provider.request !== 'function') {
    throw Error('Open the page with a compatible TRON wallet such as TronLink.');
  }
  const accounts = await provider.request({ method: 'eth_requestAccounts' });
  const tronWeb = provider.tronWeb;
  if (!tronWeb || !tronWeb.ready || !tronWeb.trx ||
      typeof tronWeb.trx.getBalance !== 'function') {
    throw Error('TRON wallet is not ready.');
  }
  const address = tronWeb.defaultAddress && tronWeb.defaultAddress.base58 ||
    (Array.isArray(accounts) ? accounts[0] : '');
  if (!address || typeof tronWeb.isAddress !== 'function' || !tronWeb.isAddress(address)) {
    throw Error('Invalid TRON wallet address.');
  }
  const amountSun = await tronWeb.trx.getBalance(address);
  const freshAddress = tronWeb.defaultAddress && tronWeb.defaultAddress.base58;
  if (freshAddress !== address) throw Error('Wallet changed during balance refresh.');
  return { address, balance: formatSun(amountSun) };
}

if (typeof module !== 'undefined') {
  module.exports = { quote, money, formatSun, getTronState };
}

if (typeof document !== 'undefined') {
  const el = id => document.getElementById(id);
  let provider = null;
  let epoch = 0;

  el('amount').addEventListener('input', () => {
    try {
      const q = quote(el('amount').value.trim());
      el('fee').textContent = money(q.fee);
      el('net').textContent = money(q.net);
      el('fee-error').textContent = '';
    } catch (e) {
      el('fee').textContent = '—';
      el('net').textContent = '—';
      el('fee-error').textContent = e.message;
    }
  });

  function clear() {
    epoch++;
    if (provider && provider.removeListener) {
      provider.removeListener('accountsChanged', changed);
      provider.removeListener('chainChanged', changed);
      provider.removeListener('disconnect', clear);
    }
    provider = null;
    for (const k of ['chain', 'address', 'balance']) el(k).textContent = '—';
    el('wallet-message').textContent = 'No wallet connected.';
    el('disconnect').hidden = true;
  }

  function changed() {
    clear();
    el('wallet-message').textContent = 'Wallet or network changed. Reconnect to refresh.';
  }

  el('disconnect').addEventListener('click', clear);
  el('connect').addEventListener('click', async () => {
    clear();
    const e = ++epoch;
    const p = window.ethereum;
    if (!p || typeof p.request !== 'function') {
      el('wallet-message').textContent =
        'Open this page in an EVM-compatible wallet browser, or use its official browser extension.';
      return;
    }
    el('connect').disabled = true;
    el('wallet-message').textContent = 'Waiting for wallet permission…';
    try {
      const accounts = await p.request({ method: 'eth_requestAccounts' });
      if (!accounts.length) throw Error('No account shared.');
      const address = accounts[0];
      if (!/^0x[0-9a-fA-F]{40}$/.test(address)) throw Error('Invalid wallet address.');
      const chain = await p.request({ method: 'eth_chainId' });
      const raw = await p.request({ method: 'eth_getBalance', params: [address, 'latest'] });
      const after = await p.request({ method: 'eth_chainId' });
      const current = await p.request({ method: 'eth_accounts' });
      if (chain !== after || !current[0] ||
          current[0].toLowerCase() !== address.toLowerCase()) {
        throw Error('Wallet changed during refresh. Reconnect.');
      }
      if (e !== epoch) return;
      provider = p;
      el('address').textContent = address;
      el('chain').textContent = BigInt(chain).toString();
      if (chain === '0x1') {
        const wei = BigInt(raw);
        el('balance').textContent = (wei / 1000000000000000000n).toString() +
          '.' + (wei % 1000000000000000000n).toString().padStart(18, '0') + ' ETH';
      } else {
        el('balance').textContent = BigInt(raw).toString() + ' base units (network-specific)';
      }
      el('wallet-message').textContent =
        'Address connected. Balance reported by your wallet provider; not independently verified.';
      el('disconnect').hidden = false;
      if (p.on) {
        p.on('accountsChanged', changed);
        p.on('chainChanged', changed);
        p.on('disconnect', clear);
      }
    } catch (error) {
      if (e === epoch) {
        el('wallet-message').textContent = error.code === 4001 ?
          'Connection declined. No transaction was requested.' :
          'Unable to read wallet. Check the connection and try again.';
      }
    } finally {
      el('connect').disabled = false;
    }
  });

  // Isolated TRON read-only panel. No wallet permission is requested on page load.
  const walletGrid = document.querySelector('#wallet .grid');
  const legacyDisclaimer = document.querySelector('#wallet article.panel .fine');
  if (legacyDisclaimer) {
    legacyDisclaimer.textContent =
      'Token balances and WalletConnect QR pairing are not integrated. ' +
      'A connected address is not proof of identity.';
  }
  if (walletGrid) {
    const panel = document.createElement('article');
    panel.className = 'panel';
    const heading = document.createElement('h3');
    heading.textContent = 'TRON wallet';
    const description = document.createElement('p');
    description.textContent = 'Connect TronLink to view your public address and native TRX balance.';
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Connect TRON wallet ↗';
    const message = document.createElement('p');
    message.setAttribute('role', 'status');
    message.setAttribute('aria-live', 'polite');
    message.textContent = 'No TRON wallet connected.';
    const details = document.createElement('p');
    details.textContent = 'Address and balance are not independently verified.';
    const notice = document.createElement('p');
    notice.className = 'fine';
    notice.textContent =
      'Read-only: no private keys, transactions, signatures or token approvals. ' +
      'TRC20 balances and QR pairing are not enabled.';
    panel.append(heading, description, button, message, details, notice);
    walletGrid.append(panel);

    let tronEpoch = 0;
    let tronProvider = null;
    const resetTron = () => {
      tronEpoch++;
      if (tronProvider && tronProvider.removeListener) {
        tronProvider.removeListener('accountsChanged', changedTron);
        tronProvider.removeListener('chainChanged', changedTron);
        tronProvider.removeListener('disconnect', changedTron);
      }
      tronProvider = null;
      details.textContent = 'Address and balance are not independently verified.';
    };
    const changedTron = () => {
      resetTron();
      message.textContent = 'TRON account or network changed. Reconnect to refresh.';
    };
    button.addEventListener('click', async () => {
      resetTron();
      const sequence = ++tronEpoch;
      const p = window.tron || window.tronLink;
      if (!p) {
        message.textContent = 'Open this page in a TRON wallet browser or install TronLink.';
        return;
      }
      button.disabled = true;
      message.textContent = 'Waiting for TRON wallet permission…';
      try {
        const result = await getTronState(p);
        if (sequence !== tronEpoch) return;
        tronProvider = p;
        details.textContent = 'Public address: ' + result.address + ' · Balance: ' + result.balance;
        message.textContent = 'Wallet connected (read-only).';
        if (p.on) {
          p.on('accountsChanged', changedTron);
          p.on('chainChanged', changedTron);
          p.on('disconnect', changedTron);
        }
      } catch (error) {
        if (sequence === tronEpoch) {
          message.textContent = error.code === 4001 ?
            'TRON wallet connection declined.' :
            'Unable to read TRON wallet: ' + String(error.message || 'connection failed');
        }
      } finally {
        button.disabled = false;
      }
    });
  }
}
