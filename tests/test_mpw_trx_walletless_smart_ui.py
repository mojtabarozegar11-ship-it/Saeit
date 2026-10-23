"""Execute actual checkout JavaScript in a mocked DOM, without wallets/network."""
import subprocess
import unittest

from services.mpw_trx_walletless_checkout_ui import SCRIPT
from services.mpw_trx_walletless_one_tap_ui import WALLET_ACTION_JS


def browser_test(source, setup):
    program = """
const vm=require('node:vm');
const assert=require('node:assert/strict');
(async()=>{
  const source=process.argv[1];
  %s
})().catch(e=>{console.error(e);process.exitCode=1});
""" % setup
    completed=subprocess.run(["node","-e",program,source],capture_output=True,text=True,
                             timeout=8,check=False)
    if completed.returncode:
        raise AssertionError(completed.stderr)


class SmartPaymentBehaviorTests(unittest.TestCase):
    def test_wallet_response_never_reenables_second_transfer(self):
        browser_test(WALLET_ACTION_JS,r'''
const handlers={};let requests=0;let events=[];
const button={disabled:false,hidden:false,addEventListener:(name,fn)=>handlers[name]=fn};
const appButton={hidden:false,href:''};const note={textContent:''};
const nodes={checkout:{dataset:{sun:'1234567',guest:'false'}},
  'mpw-easy-pay':button,'mpw-open-wallet':appButton,'mpw-wallet-note':note,
  'native-amount':{textContent:'1.234567'},recipient:{textContent:'T'+'A'.repeat(33)}};
const document={getElementById:id=>nodes[id]};
const location={hostname:'mojplaywin.com',pathname:'/commerce/trx-easy/invoice/7/',
  origin:'https://mojplaywin.com',href:'https://mojplaywin.com/commerce/trx-easy/invoice/7/'};
const window={tronWeb:{trx:{sendTransaction:async()=>{requests++;return {result:true}}}},
  dispatchEvent:e=>events.push(e.type)};
vm.runInNewContext(source,{document,location,window,Event:class{constructor(type){this.type=type}},BigInt,Number});
await Promise.all([handlers.click(),handlers.click()]);
await handlers.click();
assert.equal(requests,1);
assert.equal(button.disabled,true);
assert.equal(button.hidden,true);
assert.deepEqual(events,['mpw-wallet-submitted']);
assert.match(note.textContent,/Do not pay twice/);
''')

    def test_polling_single_flight_and_server_only_download_grant(self):
        browser_test(SCRIPT,r'''
const callbacks={};let scheduled=[];let requests=0;let finish;
const pending=new Promise(resolve=>finish=resolve);
const nodes={checkout:{getAttribute:()=>'/commerce/trx-easy/status/7/'},
  status:{textContent:''},download:{hidden:true,href:'#'},
  recipient:{textContent:'T'+'A'.repeat(33)},'native-amount':{textContent:'1.234567'},
  'copy-recipient':{addEventListener(){}},'copy-amount':{addEventListener(){}}};
const document={hidden:false,getElementById:id=>nodes[id],
  addEventListener:(name,fn)=>callbacks[name]=fn};
const window={setTimeout:(fn,ms)=>{scheduled.push({fn,ms});return scheduled.length},
  clearTimeout:()=>{},addEventListener:(name,fn)=>callbacks[name]=fn};
const fetch=()=>{requests++;return pending};
vm.runInNewContext(source,{document,window,fetch,Date,AbortController});
assert.equal(scheduled[0].ms,1500);
scheduled[0].fn();
callbacks['mpw-wallet-submitted']();
assert.equal(requests,1);
assert.equal(nodes.download.hidden,true);
finish({ok:true,json:async()=>({status:'paid',can_download:true,
  download_path:'/commerce/trx-easy/download/7/'})});
await new Promise(resolve=>setImmediate(resolve));
assert.equal(nodes.download.hidden,false);
assert.equal(nodes.download.href,'/commerce/trx-easy/download/7/');
assert.match(nodes.status.textContent,/independently confirmed/);
''')

    def test_untrusted_paid_reply_cannot_unlock_download(self):
        browser_test(SCRIPT,r'''
const callbacks={};const timers=[];
const nodes={checkout:{getAttribute:()=>'/commerce/trx-easy/status/7/'},
  status:{textContent:''},download:{hidden:true,href:'#'},
  recipient:{textContent:''},'native-amount':{textContent:''},
  'copy-recipient':{addEventListener(){}},'copy-amount':{addEventListener(){}}};
const document={hidden:false,getElementById:id=>nodes[id],
  addEventListener:(name,fn)=>callbacks[name]=fn};
const window={setTimeout:(fn,ms)=>{timers.push({fn,ms});return timers.length},
  clearTimeout:()=>{},addEventListener:(name,fn)=>callbacks[name]=fn};
const fetch=async()=>({ok:true,json:async()=>({status:'paid',can_download:true,
  download_path:'https://attacker.example/steal'})});
vm.runInNewContext(source,{document,window,fetch,Date,AbortController});
await timers[0].fn();
await new Promise(resolve=>setImmediate(resolve));
assert.equal(nodes.download.hidden,true);
assert.equal(nodes.download.href,'#');
assert.match(nodes.status.textContent,/additional server check/);
assert.equal(timers[timers.length-1].ms,4000);
''')


if __name__ == "__main__":
    unittest.main()
