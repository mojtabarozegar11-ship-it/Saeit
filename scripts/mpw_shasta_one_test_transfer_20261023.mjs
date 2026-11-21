// Strictly one controlled real TRANSFER on the zero-value TRON SHASTA testnet.
// Existing VPS-only test key NEVER leaves its protected 0600 file.
// Pre-broadcast atomic journal prevents double-send after retries/crashes.
import {TronWeb} from 'tronweb';
import fs from 'node:fs';
import path from 'node:path';
const SHASTA='https://api.shasta.trongrid.io';
const TEST_SIGNER='TWTBsKZPVuQgaGNbyJWJm9XR28g4wVBCNQ';
const HOME='/home/githubops';
const ROOT=HOME+'/.local/share/moj1-shasta-test-20261021';
const DEST=HOME+'/.local/share/mpw-trx-shasta-merchant-canary-20261023';
const AMOUNT_SUN=1_123_456;
const MARKER='SHASTA_ONLY_SEND_ONE_TEST_TRX';
if(process.env.MPW_SHASTA_CANARY_CONFIRM!==MARKER)throw Error('Test-only explicit execution flag required');
if(process.env.HOME!==HOME)throw Error('Unrecognized VPS owner');
if(!fs.existsSync(ROOT+'/wallet.key'))throw Error('Protected test signer unavailable');
const stat=fs.lstatSync(ROOT+'/wallet.key');
if(!stat.isFile()||stat.isSymbolicLink()||(stat.mode&0o777)!==0o600||stat.size!==32)throw Error('Untrusted signer file');
const publicInfo=JSON.parse(fs.readFileSync(ROOT+'/wallet-public.json','utf8'));
if(!['SHASTA_TEST_ONLY','Shasta-dedicated-test-use-only'].includes(publicInfo.network) ||
   publicInfo.production_approved===true)throw Error('Testnet-only wallet metadata required');
const keyHex=fs.readFileSync(ROOT+'/wallet.key').toString('hex');
const tron=new TronWeb({fullHost:SHASTA,privateKey:keyHex});
const sender=tron.address.fromPrivateKey(keyHex);
if(sender!==TEST_SIGNER)throw Error('Funded testnet signer identity mismatch');
if(AMOUNT_SUN<=0||AMOUNT_SUN>2_000_000)throw Error('Test transfer budget exceeded');
fs.mkdirSync(DEST,{recursive:true,mode:0o700});
if(fs.lstatSync(DEST).isSymbolicLink()||(fs.statSync(DEST).mode&0o777)!==0o700)throw Error('Unprotected test journal');
const receiverKeyFile=path.join(DEST,'receiver.key');
const journalFile=path.join(DEST,'canary-journal.json');
function atomicJSON(value){
  const temporary=journalFile+'.new';
  if(fs.existsSync(temporary))throw Error('Unresolved prior journal write');
  const fd=fs.openSync(temporary,'wx',0o600);
  try{fs.writeFileSync(fd,JSON.stringify(value));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  fs.renameSync(temporary,journalFile);
}
if(fs.existsSync(journalFile)){
  const prior=JSON.parse(fs.readFileSync(journalFile,'utf8'));
  if(prior.network!=='tron-shasta'||prior.amount_sun!==AMOUNT_SUN||
     !tron.isAddress(prior.recipient)|| !/^[0-9a-f]{64}$/.test(prior.txid??'')){
    throw Error('Previous canary journal requires review');
  }
  console.log(JSON.stringify({status:'EXISTING_TEST_TRANSACTION_DO_NOT_RESEND',
    network:'tron-shasta',txid:prior.txid,recipient:prior.recipient,
    amount_sun:prior.amount_sun,private_key_exported:false,mainnet:false}));
  process.exit(0);
}
let receiver;
if(fs.existsSync(receiverKeyFile)){
  const st=fs.lstatSync(receiverKeyFile);
  if(!st.isFile()||(st.mode&0o777)!==0o600||st.size!==32)throw Error('Unsafe test receiver key');
  receiver=tron.address.fromPrivateKey(fs.readFileSync(receiverKeyFile).toString('hex'));
}else{
  const account=await tron.createAccount();
  if(!tron.isAddress(account?.address?.base58)||!/^[0-9a-f]{64}$/i.test(account.privateKey))
    throw Error('Failed to create test-only receiving account');
  fs.writeFileSync(receiverKeyFile,Buffer.from(account.privateKey,'hex'),{flag:'wx',mode:0o600});
  receiver=account.address.base58;
}
if(receiver===sender || !tron.isAddress(receiver))throw Error('Test receiver must differ from funded signer');
const balance=await tron.trx.getBalance(sender);
if(!Number.isSafeInteger(balance)||balance<20_000_000)throw Error('Insufficient valueless Shasta TRX');
const unsigned=await tron.transactionBuilder.sendTrx(receiver,AMOUNT_SUN,sender);
const contract=unsigned?.raw_data?.contract;
if(!Array.isArray(contract)||contract.length!==1||contract[0].type!=='TransferContract')
  throw Error('Unexpected test transaction type');
const value=contract[0]?.parameter?.value;
if(value?.amount!==AMOUNT_SUN ||
  value?.owner_address?.toLowerCase()!==tron.address.toHex(sender).toLowerCase() ||
  value?.to_address?.toLowerCase()!==tron.address.toHex(receiver).toLowerCase())
  throw Error('Unsigned test transaction identity disagreement');
if(typeof unsigned.raw_data.expiration!=='number' ||
  unsigned.raw_data.expiration<=Date.now())throw Error('Expired unsigned test transfer');
const signed=await tron.trx.sign(unsigned);
if(!/^[0-9a-f]{64}$/i.test(signed?.txID??'')||
  signed.txID!==unsigned.txID||signed.raw_data_hex!==unsigned.raw_data_hex||
  !Array.isArray(signed.signature)||signed.signature.length<1)throw Error('Test transaction not signed safely');
const note={network:'tron-shasta',amount_sun:AMOUNT_SUN,
  recipient:receiver,sender,test_only:true,txid:signed.txID.toLowerCase(),
  status:'BROADCAST_UNCERTAIN',created_at:new Date().toISOString()};
atomicJSON(note);
let accepted;
try{accepted=await tron.trx.sendRawTransaction(signed);}catch(err){
  throw Error('Single Shasta broadcast uncertain; do not resend');
}
if(accepted?.result!==true && accepted?.code!=='DUP_TRANSACTION_ERROR')
  throw Error('Shasta broadcast unverified; journal blocks resend');
fs.writeFileSync(journalFile,JSON.stringify({...note,status:'BROADCAST_ACCEPTED'}),
  {mode:0o600});
console.log(JSON.stringify({status:'ONE_SHASTA_TEST_TRANSFER_BROADCAST',
  network:'tron-shasta',sender,recipient:receiver,amount_sun:AMOUNT_SUN,
  txid:signed.txID.toLowerCase(),private_key_exported:false,
  mainnet:false,production_financial_writes:0}));
