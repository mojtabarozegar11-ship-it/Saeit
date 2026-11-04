/* MOJ7 PRIVATE TRON chain only. No production keys, Mainnet, or public-testnet transactions. */
const Token = artifacts.require('MOJ7');
const SUPPLY = '1000000000000000000';
const MAX = ((2n ** 256n)-1n).toString();
const ZERO = '410000000000000000000000000000000000000000';
async function mustRevert(promise) {
  let result;
  let rejected;
  try {
    result = await promise;
  } catch (error) {
    rejected = error;
  }
  if (rejected) {
    assert(/revert|execution reverted|contract revert/i.test(String(rejected.message)),
      'Unexpected transaction error (not an explicit REVERT): ' + String(rejected.message).slice(0,400));
    return;
  }
  const isTxid = x => typeof x === 'string' && /^[a-fA-F0-9]{64}$/.test(x.replace(/^0x/, ''));
  const txid = isTxid(result) ? result.replace(/^0x/, '') :
    [result?.txID, result?.txid, result?.transactionHash,
     result?.receipt?.txID, result?.receipt?.transactionHash]
      .find(isTxid);
  assert(txid, 'No transaction ID returned; refusing to assume revert, shape=' +
    (result && typeof result === 'object' ? Object.keys(result).slice(0,20).join(',') : typeof result));
  let receiptInfo;
  for (let attempt = 0; attempt < 20; attempt++) {
    receiptInfo = await tronWrap.trx.getTransactionInfo(txid);
    if (receiptInfo?.receipt?.result) break;
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  assert(receiptInfo?.receipt?.result, 'Missing receipt for tx=' + txid);
  assert.equal(receiptInfo.receipt.result, 'REVERT',
    'Expected REVERT; received ' + receiptInfo.receipt.result + ' tx=' + txid);
}
contract('MOJ7 local TRE integration', accounts => {
  let token;
  beforeEach(async () => {
    assert(accounts.length >= 3, 'TRE accounts missing');
    token = await Token.new(accounts[0], {from:accounts[0]});
  });
  it('matches immutable trillion-token supply and decimals', async () => {
    assert.equal(String(await token.totalSupply()),SUPPLY);
    assert.equal(String(await token.decimals()),'6');
    assert.equal(String(await token.balanceOf(accounts[0])),SUPPLY);
    assert.equal(String(await token.balanceOf(accounts[1])),'0');
  });
  it('allocates all supply to explicit beneficiary, not deployer', async () => {
    const instance=await Token.new(accounts[1],{from:accounts[0]});
    assert.equal(String(await instance.balanceOf(accounts[0])),'0');
    assert.equal(String(await instance.balanceOf(accounts[1])),SUPPLY);
  });
  it('rejects zero initial holder', async () => {
    await mustRevert(Token.new(ZERO,{from:accounts[0]}));
  });
  it('transfers correct base units', async () => {
    await token.transfer(accounts[1],'13000000',{from:accounts[0]});
    assert.equal(String(await token.balanceOf(accounts[1])),'13000000');
    assert.equal(String(await token.balanceOf(accounts[0])),(BigInt(SUPPLY)-13000000n).toString());
  });
  it('rejects transfer exceeding balance',async () => {
    await mustRevert(token.transfer(accounts[1],(BigInt(SUPPLY)+1n).toString(),{from:accounts[0]}));
    assert.equal(String(await token.balanceOf(accounts[1])),'0');
  });
  it('rejects zero recipient', async () => {
    await mustRevert(token.transfer(ZERO,'1',{from:accounts[0]}));
  });
  it('preserves supply and balance on self transfer', async () => {
    await token.transfer(accounts[0],'999',{from:accounts[0]});
    assert.equal(String(await token.balanceOf(accounts[0])),SUPPLY);
  });
  it('allows zero transfers with no balance changes', async () => {
    await token.transfer(accounts[1],'0',{from:accounts[0]});
    assert.equal(String(await token.balanceOf(accounts[0])),SUPPLY);
    assert.equal(String(await token.balanceOf(accounts[1])),'0');
  });
  it('rejects zero spender',async () => {
    await mustRevert(token.approve(ZERO,'1',{from:accounts[0]}));
  });
  it('requires approve(0) before changing nonzero allowance', async () => {
    await token.approve(accounts[0],'25',{from:accounts[0]});
    await mustRevert(token.approve(accounts[0],'26',{from:accounts[0]}));
    assert.equal(String(await token.allowance(accounts[0],accounts[0])),'25');
    await token.approve(accounts[0],'0',{from:accounts[0]});
    await token.approve(accounts[0],'26',{from:accounts[0]});
    assert.equal(String(await token.allowance(accounts[0],accounts[0])),'26');
  });
  it('transferFrom consumes finite allowance and prevents excess spend',async () => {
    await token.approve(accounts[0],'25',{from:accounts[0]});
    await token.transferFrom(accounts[0],accounts[1],'20',{from:accounts[0]});
    assert.equal(String(await token.allowance(accounts[0],accounts[0])),'5');
    assert.equal(String(await token.balanceOf(accounts[1])),'20');
    await mustRevert(token.transferFrom(accounts[0],accounts[1],'6',{from:accounts[0]}));
  });
  it('transferFrom respects unlimited allowance',async () => {
    await token.approve(accounts[0],MAX,{from:accounts[0]});
    await token.transferFrom(accounts[0],accounts[1],'17',{from:accounts[0]});
    assert.equal(String(await token.allowance(accounts[0],accounts[0])),MAX);
  });
  it('rejects transferFrom without allowance',async () => {
    await mustRevert(token.transferFrom(accounts[1],accounts[2],'1',{from:accounts[0]}));
  });
  it('rejects transferFrom from the zero address', async () => {
    await mustRevert(token.transferFrom(ZERO,accounts[1],'0',{from:accounts[0]}));
  });
});
