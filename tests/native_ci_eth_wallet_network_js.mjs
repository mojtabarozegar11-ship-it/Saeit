// Browser-free tests for customer-approved Ethereum mainnet wallet proof.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const page = fs.readFileSync(
  "mpw_native_checkout/templates/mpw_native_checkout/merchant_wallet_proof.html","utf8"
);
const match = page.match(/async function signEth\(message,expected\)\{[\s\S]*?\n\}\n(?=async function signTrx)/);
assert.ok(match,"merchant ETH proof function must exist");
const account="0x89149b01f59115B86553561F12438D2ADF517E75";
const message="MojPlayWin Merchant Wallet Ownership\nDomain: mojplaywin.com";
let cases=0;
async function runCase(initialId,{allowSwitch=true,secondId="0x1",expected=account,
    walletAccount=account,expectSuccess=true,expectedSwitches=0,expectedSigns=1}={}){
  let switched=false,switches=0,signs=0;
  const provider={
    request:async ({method,params})=>{
      if(method==="eth_requestAccounts")return [walletAccount];
      if(method==="eth_chainId")return switched?secondId:initialId;
      if(method==="wallet_switchEthereumChain"){
        switches++;
        assert.equal(Array.isArray(params),true);
        assert.equal(params[0].chainId,"0x1");
        if(!allowSwitch)throw new Error("user rejected switch");
        switched=true;return null;
      }
      if(method==="personal_sign"){
        signs++;
        assert.equal(params[0],message);
        assert.equal(params[1],walletAccount);
        return "0x"+("a".repeat(130));
      }
      throw new Error("unrecognized wallet method");
    }
  };
  const scope={window:{ethereum:provider},console};
  vm.runInNewContext(match[0]+"\nthis.signEth = signEth;",scope);
  if(expectSuccess){
    assert.equal(await scope.signEth(message,expected),"0x"+("a".repeat(130)));
  }else{
    await assert.rejects(scope.signEth(message,expected));
  }
  assert.equal(switches,expectedSwitches);
  assert.equal(signs,expectedSigns);
  cases++;
}
await runCase("0x1");
await runCase("0x01");
await runCase("1");
await runCase(1);
await runCase("0x89",{expectedSwitches:1});
await runCase("0x89",{allowSwitch:false,expectSuccess:false,expectedSwitches:1,expectedSigns:0});
await runCase("0x89",{secondId:"0x89",expectSuccess:false,expectedSwitches:1,expectedSigns:0});
await runCase("0x89",{walletAccount:"0x0000000000000000000000000000000000000001",expectSuccess:false,expectedSigns:0});
console.log("MPW_ETH_NETWORK_WALLET_GUARD_TESTS_PASSED="+cases);
console.log("MPW_REAL_WALLET_NOT_CONNECTED=True");
console.log("MPW_TRANSACTION_NOT_SENT=True");
