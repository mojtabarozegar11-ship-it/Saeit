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

const USDT_ETHEREUM = '0xdac17f958d2ee523a2206206994597c13d831ec7';
const USDT_TRON = 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t';

function formatTokenUnits(raw, decimals, symbol) {
  if (typeof raw === 'number' && !Number.isSafeInteger(raw)) throw Error('Unsafe token precision.');
  if (!Number.isInteger(decimals) || decimals < 0 || decimals > 18) throw Error('Invalid token decimals.');
  const quantity = BigInt(String(raw));
  if (quantity < 0n) throw Error('Invalid token amount.');
  const base = 10n ** BigInt(decimals);
  const fraction = decimals ?
    (quantity % base).toString().padStart(decimals, '0').replace(/0+$/, '') : '';
  return (quantity / base).toString() + (fraction ? '.' + fraction : '') + ' ' + symbol;
}

/** Mainnet-only eth_call; never signs or broadcasts a transaction. */
async function getErc20Usdt(provider, address) {
  if (!/^0x[0-9a-fA-F]{40}$/.test(address)) throw Error('Invalid EVM address.');
  const chainBefore = await provider.request({ method: 'eth_chainId' });
  if (chainBefore !== '0x1') throw Error('USDT ERC20 is shown only on Ethereum mainnet.');
  const data = '0x70a08231' + address.slice(2).toLowerCase().padStart(64, '0');
  const balance = await provider.request({
    method: 'eth_call', params: [{ to: USDT_ETHEREUM, data }, 'latest']
  });
  const decimalsHex = await provider.request({
    method: 'eth_call', params: [{ to: USDT_ETHEREUM, data: '0x313ce567' }, 'latest']
  });
  if (!/^0x[0-9a-fA-F]+$/.test(balance) || !/^0x[0-9a-fA-F]+$/.test(decimalsHex)) {
    throw Error('Malformed ERC20 response.');
  }
  if (Number(BigInt(decimalsHex)) !== 6) throw Error('Unexpected USDT contract precision.');
  const [chainAfter, accountsAfter] = await Promise.all([
    provider.request({ method: 'eth_chainId' }),
    provider.request({ method: 'eth_accounts' })
  ]);
  if (chainAfter !== chainBefore || !Array.isArray(accountsAfter) || !accountsAfter[0] ||
      accountsAfter[0].toLowerCase() !== address.toLowerCase()) {
    throw Error('EVM account or network changed during token read.');
  }
  return formatTokenUnits(BigInt(balance), 6, 'USDT');
}

/** TRC20 contract calls are read-only through the authorized wallet provider. */
async function getTrc20Usdt(tronWeb, address) {
  if (!tronWeb || typeof tronWeb.contract !== 'function') throw Error('TRC20 unavailable.');
  const token = await tronWeb.contract().at(USDT_TRON);
  if (!token || !token.balanceOf || !token.decimals) throw Error('Invalid TRC20 contract.');
  const amount = await token.balanceOf(address).call();
  const decimalsRaw = await token.decimals().call();
  const decimals = Number(decimalsRaw.toString());
  if (decimals !== 6) throw Error('Unexpected TRC20 USDT precision.');
  return formatTokenUnits(amount.toString(), decimals, 'USDT');
}

/** Requests only an address and read-only balances. Never signs or sends funds. */
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
  let usdt = null;
  try { usdt = await getTrc20Usdt(tronWeb, address); } catch (_) { /* Never misreport unavailable as zero. */ }
  if (!tronWeb.defaultAddress || tronWeb.defaultAddress.base58 !== address) {
    throw Error('Wallet changed during token refresh.');
  }
  return usdt ? { address, balance: formatSun(amountSun), usdt } :
    { address, balance: formatSun(amountSun) };
}

if (typeof module !== 'undefined') {
  module.exports = { quote, money, formatSun, formatTokenUnits, getTronState, getErc20Usdt, getTrc20Usdt };
}

if (typeof document !== 'undefined') {
  const el = id => document.getElementById(id);
  const evmTokenDisplay = document.createElement('p');
  evmTokenDisplay.setAttribute('role', 'status');
  evmTokenDisplay.textContent = 'USDT ERC20: connect an Ethereum mainnet wallet to view.';
  const evmPanel = document.querySelector('#wallet article.panel');
  if (evmPanel) evmPanel.appendChild(evmTokenDisplay);
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
    evmTokenDisplay.textContent = 'USDT ERC20: connect an Ethereum mainnet wallet to view.';
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
      if (chain === '0x1') {
        try {
          const tokenBalance = await getErc20Usdt(p, address);
          if (e === epoch) evmTokenDisplay.textContent = 'USDT ERC20: ' + tokenBalance;
        } catch (_) {
          if (e === epoch) evmTokenDisplay.textContent = 'USDT ERC20: unavailable (not zero).';
        }
      } else {
        evmTokenDisplay.textContent = 'USDT ERC20: select Ethereum mainnet to view.';
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
      'ETH, TRX and supported USDT balances are read-only. ' +
      'Other assets and WalletConnect QR pairing are not supported. ' +
      'Wallet connection does not verify financial identity.';
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
      'USDT TRC20 is read-only when supported by the wallet. QR pairing is not enabled.';
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
        details.textContent = 'Public address: ' + result.address + ' · TRX: ' + result.balance + ' · USDT TRC20: ' + (result.usdt || 'unavailable (not zero)');
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
            'Unable to read TRON wallet. Check the wallet connection and retry.';
        }
      } finally {
        button.disabled = false;
      }
    });
  }
}
