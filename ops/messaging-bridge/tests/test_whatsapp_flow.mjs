/** Deterministic fake-socket regressions: never use real accounts/network. */
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const sourcePath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../whatsapp.mjs');
const original = await fs.readFile(sourcePath, 'utf8');
async function runScenario({mode, events, pairingCode=false}) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'mmsg-flow-'));
  try {
    const calls = [];
    const proc = {
      argv: ['node','whatsapp.mjs',mode,'--account','primary',...(pairingCode?['--pairing-code']:[])],
      env:{MOJMSG_STATE_DIR:root}, stdin:{isTTY:true}, stdout:{isTTY:true}, exitCode:0,
      umask(){}, on(){}, exit(code){throw new Error('Unexpected exit '+code);}
    };
    let connections=0;
    const socketFactory=()=>{
      const iteration=connections++;
      const handlers={};
      const socket={
        ev:{on(event,handler){handlers[event]=handler;}},
        authState:{creds:{registered:false}},
        async requestPairingCode(number){calls.push('pairing.request:'+number);return '12345678';},
        end(){calls.push('socket.end');handlers['connection.update']?.({connection:'close'});}
      };
      setImmediate(async()=>{
        for(const event of events[iteration]??[]){
          if(event==='qr') await handlers['connection.update']({qr:'private-token'});
          else if(event==='restart') await handlers['connection.update']({connection:'close',lastDisconnect:{error:{output:{statusCode:515}}}});
          else if(event==='open'){
            await handlers['creds.update']?.({});
            await handlers['connection.update']({connection:'open'});
          }
        }
      });
      return socket;
    };
    const code=original.replace(/^import .*?;\r?\n/gm,'')
      .replace('await pause(1500)','await pause(0)')
      .replace('3000*Math.pow','0*Math.pow');
    const context={
      fs,path,process:proc,pino:()=>({}),qrTerm:{generate:()=>calls.push('qr')},
      readline:{createInterface:()=>({question:async()=> '15551234567',close(){}})},
      makeWASocket:socketFactory,
      useMultiFileAuthState:async()=>({state:{},saveCreds:async()=>calls.push('credentials.saved')}),
      DisconnectReason:{loggedOut:401,connectionReplaced:440,restartRequired:515},
      console:{log:(...args)=>calls.push(args.join(' ')),error:(...args)=>calls.push('error:'+args.join(' '))},
      setTimeout,clearTimeout,setInterval,clearInterval,setImmediate,Date,Math
    };
    await vm.runInNewContext('(async()=>{\n'+code+'\n})()',context,{timeout:2000});
    const state=JSON.parse(await fs.readFile(path.join(root,'whatsapp-primary-status.json'),'utf8'));
    return {calls,status:state.status,connections,exitCode:proc.exitCode};
  } finally {await fs.rm(root,{recursive:true,force:true});}
}
const daemon=await runScenario({mode:'daemon',events:[['qr']]});
assert.equal(daemon.status,'LOGIN_REQUIRED');
assert.equal(daemon.connections,1);
const login=await runScenario({mode:'login',events:[['qr','restart'],['open']]});
assert.equal(login.status,'AUTHORIZED');
assert.equal(login.connections,2);
assert.ok(login.calls.includes('credentials.saved'));
const shortCode=await runScenario({mode:'login',events:[['qr','restart'],['open']],pairingCode:true});
assert.equal(shortCode.status,'AUTHORIZED');
assert.equal(shortCode.connections,2);
assert.ok(shortCode.calls.includes('pairing.request:15551234567'));
assert.ok(shortCode.calls.some(x=>x.startsWith('PAIRING CODE') && x.includes('12345678')));
assert.equal(shortCode.calls.includes('qr'),false);
console.log('WhatsApp fake-socket state tests PASS');
