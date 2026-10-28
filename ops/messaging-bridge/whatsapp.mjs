/** WhatsApp linked-device keeper, two isolated accounts, no message capture or sends.
 * Unofficial Baileys transport: use at your own risk and never for spam.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import readline from 'node:readline/promises';
import makeWASocket, { useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import pino from 'pino';
import qrTerm from 'qrcode-terminal';

process.umask(0o077);
const mode = process.argv[2];
const index = process.argv.indexOf('--account');
const account = index >= 0 ? process.argv[index + 1] : 'primary';
const byPairingCode = process.argv.includes('--pairing-code');
if (!['login', 'daemon', 'status'].includes(mode) || !['primary', 'secondary'].includes(account) || (byPairingCode && mode !== 'login')) {
  console.error('Usage: node whatsapp.mjs login|daemon|status --account primary|secondary');
  process.exit(2);
}
const root = process.env.MOJMSG_STATE_DIR || '/var/lib/moj-messaging';
const authDir = path.join(root, 'whatsapp', account);
const statusPath = path.join(root, `whatsapp-${account}-status.json`);
async function status(value) {
  const temp = `${statusPath}.${process.pid}.tmp`;
  await fs.writeFile(temp, JSON.stringify({service:'whatsapp', account, status:value, timestamp:Math.floor(Date.now()/1000)})+'\n', {mode:0o600});
  await fs.rename(temp, statusPath);
}
if (mode === 'status') {
  try { console.log((await fs.readFile(statusPath,'utf8')).trim()); }
  catch { console.log('NOT_STARTED'); }
  process.exit(0);
}
// Status probes must not create or alter private authentication directories.
await fs.mkdir(authDir, {recursive:true, mode:0o700});
await fs.chmod(authDir, 0o700);
if (mode === 'login' && (!process.stdin.isTTY || !process.stdout.isTTY)) {
  console.error('For security, pairing is allowed only in an interactive private terminal.');
  process.exit(2);
}
if (mode === 'login' && byPairingCode) {
  const rl = readline.createInterface({input:process.stdin, output:process.stdout});
  try {
    phoneNumber = (await rl.question('WhatsApp phone with country code (digits only, no +): ')).trim();
  } finally { rl.close(); }
  if (!/^[1-9][0-9]{7,14}$/.test(phoneNumber)) {
    console.error('Invalid international phone number.');
    process.exit(2);
  }
}
const logger = pino({level:'silent'});
let running = true;
let sock;
let attempts = 0;
let beat;
let phoneNumber = null;
const pause = (ms) => new Promise(resolve => setTimeout(resolve, ms));
process.on('SIGTERM', ()=> {running=false; clearInterval(beat); sock?.end(undefined);});
process.on('SIGINT', ()=> {running=false; clearInterval(beat); sock?.end(undefined);});

async function start() {
  const {state, saveCreds} = await useMultiFileAuthState(authDir);
  await status('CONNECTING');
  const socket = makeWASocket({
    auth:state, logger, markOnlineOnConnect:false, syncFullHistory:false,
    printQRInTerminal:false,
  });
  sock = socket;
  let requestedPairingCode = false;
  let credentialsSaved = Promise.resolve();
  let credentialsSaveFailed = false;
  socket.ev.on('creds.update', () => {
    credentialsSaved = credentialsSaved.then(() => saveCreds()).catch(() => {
      credentialsSaveFailed = true;
      console.error('Unable to save credentials; login must not be treated as durable.');
      socket.end(undefined);
    });
  });
  return new Promise(resolve => {
    let settled=false;
    const finish = async (reason) => {
      if (settled) return;
      settled=true;
      clearInterval(beat);
      await status(reason);
      resolve(reason);
    };
    socket.ev.on('connection.update', async ({connection, qr, lastDisconnect}) => {
      if (qr) {
        if (mode === 'login') {
          if (byPairingCode && !requestedPairingCode && !socket.authState.creds.registered) {
            requestedPairingCode = true;
            try {
              const pairingCode = await socket.requestPairingCode(phoneNumber);
              console.log('PAIRING CODE (enter on your WhatsApp phone; never share):', pairingCode);
              console.log('WhatsApp > Linked devices > Link a device > Link with phone number instead');
            } catch {
              await finish('PAIRING_CODE_FAILED');
              socket.end(undefined);
            }
          } else if (!byPairingCode) {
            console.log('Scan this QR with WhatsApp > Linked devices > Link a device:');
            qrTerm.generate(qr,{small:true});
          }
        } else {
          // Settle first: end() may synchronously emit a close event.
          await finish('LOGIN_REQUIRED');
          socket.end(undefined);
        }
      }
      if (connection === 'open') {
        attempts=0;
        await status('CONNECTED');
        if (mode === 'login') {
          await pause(1500);
          await credentialsSaved;
          if (credentialsSaveFailed) {
            await finish('CREDENTIAL_SAVE_FAILED');
            socket.end(undefined);
          } else {
            console.log('AUTHORIZED: WhatsApp credentials saved in the private state folder.');
            await finish('AUTHORIZED');
            socket.end(undefined);
          }
        } else {
          clearInterval(beat);
          beat=setInterval(()=> status('CONNECTED').catch(()=>{}),30000);
        }
      }
      if (connection === 'close') {
        const code = lastDisconnect?.error?.output?.statusCode;
        await finish(credentialsSaveFailed ? 'CREDENTIAL_SAVE_FAILED' :
                     code === DisconnectReason.loggedOut ? 'LOGIN_REQUIRED' :
                     code === DisconnectReason.connectionReplaced ? 'SESSION_CONFLICT' :
                     code === DisconnectReason.restartRequired ? 'PAIRING_RESTART' : 'DISCONNECTED');
      }
    });
  });
}
while (running) {
  let outcome;
  try { outcome=await start(); }
  catch (e) { console.error(`Connection failed (${e?.name||'error'}).`); outcome='DISCONNECTED'; }
  if (outcome === 'AUTHORIZED' || outcome === 'LOGIN_REQUIRED' || outcome === 'SESSION_CONFLICT' || outcome === 'CREDENTIAL_SAVE_FAILED' || outcome === 'PAIRING_CODE_FAILED' || !running) {
    if (mode === 'login' && outcome !== 'AUTHORIZED') process.exitCode = 3;
    break;
  }
  // Initial QR pairing may require a restart before the first authenticated 'open'.
  if (mode === 'login' && attempts >= 10) {
    await status('PAIRING_RETRIES_EXCEEDED');
    process.exitCode = 4;
    break;
  }
  attempts++;
  await pause(Math.min(60000, 3000*Math.pow(2,Math.min(attempts,4))));
}
if (mode==='daemon' && running && (await fs.readFile(statusPath,'utf8')).includes('LOGIN_REQUIRED')) process.exitCode=3;