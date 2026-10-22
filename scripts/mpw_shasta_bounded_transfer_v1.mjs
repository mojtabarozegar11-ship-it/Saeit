/** One-shot Shasta-only payment evidence; NEVER a production checkout. */
import {TronWeb} from 'tronweb';
import {readFile, open, lstat, stat} from 'node:fs/promises';
import {join} from 'node:path';
import {homedir} from 'node:os';
import {createHash} from 'node:crypto';

const ENDPOINT = 'https://api.shasta.trongrid.io';
const SOURCE = 'TWTBsKZPVuQgaGNbyJWJm9XR28g4wVBCNQ';
const SUN = 100000;
const ROOT = join(homedir(), '.local/share/moj1-shasta-test-20261021');
const JOURNAL = join(ROOT, 'mpw-shasta-bounded-native-transfer-journal-v1.json');
const RECEIPT = join(ROOT, 'mpw-shasta-bounded-native-transfer-receipt-v1.json');
const hold = (why) => { throw new Error('SHASTA_HOLD:' + why); };
const json = async (p) => JSON.parse(await readFile(p, 'utf8'));
const hex = (address) => TronWeb.address.toHex(address).toLowerCase();

async function writeOnce(path, data) {
  const file = await open(path, 'wx', 0o600);
  try { await file.writeFile(JSON.stringify(data) + '\n'); await file.sync(); }
  finally { await file.close(); }
}
async function rpc(path, body = null) {
  const allowed = ['/walletsolidity/getnowblock',
    '/walletsolidity/gettransactionbyid','/walletsolidity/gettransactioninfobyid'];
  if (!allowed.includes(path)) hold('unapproved endpoint');
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), 15000);
  try {
    const result = await fetch(ENDPOINT + path, {method: body ? 'POST' : 'GET',
      redirect:'error', signal:abort.signal,
      headers:{'Accept':'application/json','Content-Type':'application/json'},
      ...(body ? {body:JSON.stringify(body)} : {})});
    if (!result.ok || !(result.headers.get('content-type')||'').startsWith('application/json'))
      hold('invalid Shasta RPC response');
    const raw = await result.text();
    if (raw.length > 150000) hold('oversized RPC response');
    const data = JSON.parse(raw);
    if (!data || typeof data !== 'object' || Array.isArray(data) || data.Error)
      hold('invalid Shasta payload');
    return data;
  } finally { clearTimeout(timer); }
}
async function checkSolidified(entry) {
  if (!/^[a-f0-9]{64}$/.test(entry.txid)) hold('untrusted txid');
  const head = await rpc('/walletsolidity/getnowblock');
  const height = head?.block_header?.raw_data?.number;
  const at = head?.block_header?.raw_data?.timestamp;
  if (!Number.isSafeInteger(height) || height < 1 ||
      !Number.isSafeInteger(at) || Math.abs(Date.now()-at)>600000)
    hold('stale solidity head');
  const param = {value:entry.txid,visible:false};
  const tx = await rpc('/walletsolidity/gettransactionbyid',param);
  const info = await rpc('/walletsolidity/gettransactioninfobyid',param);
  if (!tx.txID || !info.id) return null;
  const contracts = tx.raw_data?.contract;
  const transfer = contracts?.[0]?.parameter?.value;
  const block = info.blockNumber;
  if (tx.txID!==entry.txid || info.id!==entry.txid ||
      !Array.isArray(contracts) || contracts.length!==1 ||
      contracts[0].type!=='TransferContract' ||
      tx.ret?.length!==1 || tx.ret[0].contractRet!=='SUCCESS' ||
      info.result==='FAILED' || !info.receipt ||
      ![undefined,'SUCCESS'].includes(info.receipt.result) ||
      !Number.isSafeInteger(block) || block<1 || block>height ||
      !Number.isSafeInteger(info.blockTimeStamp) ||
      transfer?.owner_address?.toLowerCase()!==hex(entry.sender) ||
      transfer?.to_address?.toLowerCase()!==hex(entry.recipient) ||
      transfer?.amount!==SUN) hold('solidified receipt does not match exact transfer');
  const evidence = {network:'Shasta',txid:entry.txid,sender:entry.sender,
    recipient:entry.recipient,amount_sun:SUN,solidified_block:block,
    live_invoice_paid:false,live_ledger_writes:0,live_deliveries:0};
  return {...evidence,sha256:createHash('sha256').update(JSON.stringify(evidence)).digest('hex')};
}
async function main() {
  if (process.env.SHASTA_TRANSFER_CONFIRM!=='ONE_TEST_TRANSFER_100000_SUN' ||
      process.env.TRON_PRIVATE_KEY || process.env.TRON_FULL_HOST ||
      process.env.TRON_NETWORK) hold('network or authorization policy mismatch');
  const directory = await stat(ROOT);
  if (!directory.isDirectory() || (directory.mode & 0o777)!==0o700)
    hold('invalid isolated wallet storage');
  const [wallet,owners] = await Promise.all([
    json(join(ROOT,'wallet-public.json')),
    json(join(ROOT,'governance-test-owners/owners-public.json'))]);
  if (wallet.address_base58!==SOURCE || !String(wallet.network).includes('Shasta') ||
      owners.network!=='SHASTA_TEST_ONLY' || owners.production_approved!==false ||
      !Array.isArray(owners.owners) || owners.owners.length!==3)
    hold('wallet and controlled test owners mismatch');
  const recipient = owners.owners[0]?.address_base58;
  if (!TronWeb.isAddress(recipient) || recipient===SOURCE)
    hold('uncontrolled test destination');
  let recorded;
  try { recorded = await json(JOURNAL); }
  catch (error) { if (error.code!=='ENOENT') hold('unreadable journal'); }
  if (!recorded) {
    const keyFile = join(ROOT,'wallet.key');
    const mode = await lstat(keyFile);
    if (!mode.isFile() || mode.isSymbolicLink() || (mode.mode & 0o777)!==0o600)
      hold('unsafe private key file');
    const privateKey = (await readFile(keyFile)).toString('hex');
    if (!/^[a-f0-9]{64}$/.test(privateKey)) hold('invalid test signing key');
    const tron = new TronWeb({fullHost:ENDPOINT,privateKey});
    if (tron.defaultAddress.base58!==SOURCE) hold('unexpected signing account');
    const balance = await tron.trx.getBalance(SOURCE);
    if (!Number.isSafeInteger(balance) || balance<10000000 || balance>10000000000)
      hold('bounded test balance check failed');
    const unsigned = await tron.transactionBuilder.sendTrx(recipient,SUN,SOURCE);
    const contract = unsigned?.raw_data?.contract;
    const amount = contract?.[0]?.parameter?.value;
    if (!Array.isArray(contract) || contract.length!==1 ||
        contract[0].type!=='TransferContract' || amount?.amount!==SUN ||
        amount?.owner_address?.toLowerCase()!==hex(SOURCE) ||
        amount?.to_address?.toLowerCase()!==hex(recipient))
      hold('untrusted transaction-builder result');
    const signed = await tron.trx.sign(unsigned,privateKey);
    if (!/^[a-f0-9]{64}$/.test(signed?.txID || '') || !signed?.signature?.length)
      hold('not signed');
    recorded = {v:1,network:'Shasta',txid:signed.txID,sender:SOURCE,
      recipient,amount_sun:SUN,possible_broadcast:true,production_authority:false};
    // Durable before send: if any stage crashes, NEVER retry the debit.
    await writeOnce(JOURNAL,recorded);
    const sent = await tron.trx.sendRawTransaction(signed);
    if (sent?.result!==true || sent.txid!==signed.txID)
      hold('broadcast not positively acknowledged; journal retained');
    console.log('SHASTA_BOUND_PAYMENT_BROADCAST=ACKNOWLEDGED');
  } else {
    if (recorded.v!==1 || recorded.network!=='Shasta' ||
        recorded.sender!==SOURCE || recorded.recipient!==recipient ||
        recorded.amount_sun!==SUN || recorded.production_authority!==false)
      hold('journal cannot be reused for different transfer');
    console.log('SHASTA_RESTART=READ_ONLY_NO_REBROADCAST');
  }
  for (let attempt=0;attempt<20;attempt++) {
    const verified = await checkSolidified(recorded);
    if (verified) {
      try { await writeOnce(RECEIPT,verified); }
      catch (error) {
        if (error.code!=='EEXIST' ||
            JSON.stringify(await json(RECEIPT))!==JSON.stringify(verified))
          hold('existing receipt not identical');
      }
      console.log(JSON.stringify({status:'SHASTA_SOLIDIFIED_TEST_TRANSFER_PASS',
        txid:verified.txid,solidified_block:verified.solidified_block,
        amount_sun:SUN,live_purchase_complete:false,production_writes:0}));
      return;
    }
    if (attempt<19) await new Promise(r=>setTimeout(r,10000));
  }
  hold('not yet solidified, read-only reconciliation required');
}
main().catch(error=>{console.error(String(error));process.exitCode=1;});
