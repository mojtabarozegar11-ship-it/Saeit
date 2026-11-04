/* Disposable localhost TRON TVM only; never use the clock harness with real assets. */
const Governed = artifacts.require('MojGovernanceGuardedClockHarness');
const Token = artifacts.require('MojRewardTestToken');

contract('MOJ1 delayed and rotatable 2-of-3 candidate', accounts => {
  const start = 1_800_000_000;
  const delay = 48 * 60 * 60;
  const rotationDelay = 7 * 24 * 60 * 60;
  const unit = 10n ** 18n;
  const amount = n => (BigInt(n) * unit).toString();
  const uint = n => BigInt(n).toString(16).padStart(64, '0');

  async function expectRevert(promise) {
    const txid = await promise;
    const info = await tronWeb.trx.getTransactionInfo(txid);
    assert.equal(info?.receipt?.result, 'REVERT');
  }

  async function setup() {
    const gov = await Governed.new([accounts[0], accounts[1], accounts[2]], start);
    const token = await Token.new();
    await token.transfer(gov.address, amount(20), {from: accounts[0]});
    return {gov, token};
  }

  function transferData(recipient, count) {
    return '0x' + tronWeb.sha3('transfer(address,uint256)').slice(2, 10) +
      tronWeb.address.toHex(recipient).slice(2).padStart(64, '0') + uint(amount(count));
  }

  function rotateData(slot, nextOwner) {
    return '0x' + tronWeb.sha3('replaceOwner(uint256,address)').slice(2, 10) +
      uint(slot) + tronWeb.address.toHex(nextOwner).slice(2).padStart(64, '0');
  }

  it('enforces two distinct owners, a real delay and nonce replay protection', async () => {
    const {gov, token} = await setup();
    const data = transferData(accounts[7], 3);
    await expectRevert(gov.approve(token.address, data, 0, {from: accounts[7]}));
    await gov.approve(token.address, data, 0, {from: accounts[0]});
    await expectRevert(gov.approve(token.address, data, 0, {from: accounts[0]}));
    await expectRevert(gov.execute(token.address, data, 0, {from: accounts[2]}));
    await gov.approve(token.address, data, 0, {from: accounts[1]});
    await expectRevert(gov.execute(token.address, data, 0, {from: accounts[2]}));
    await gov.setTestClock(start + delay - 1);
    await expectRevert(gov.execute(token.address, data, 0, {from: accounts[0]}));
    await gov.setTestClock(start + delay);
    const before = BigInt((await token.balanceOf(accounts[7])).toString());
    await gov.execute(token.address, data, 0, {from: accounts[2]});
    assert.equal(BigInt((await token.balanceOf(accounts[7])).toString()) - before, 3n * unit);
    assert.equal((await gov.nonce()).toString(), '1');
    await expectRevert(gov.execute(token.address, data, 0, {from: accounts[2]}));
  });

  it('rotates one owner only by a separate delayed 2-of-3 self-call', async () => {
    const {gov, token} = await setup();
    const data = rotateData(2, accounts[3]);
    await expectRevert(gov.replaceOwner(2, accounts[3], {from: accounts[0]}));
    await gov.approve(gov.address, data, 0, {from: accounts[0]});
    await gov.approve(gov.address, data, 0, {from: accounts[1]});
    await gov.setTestClock(start + rotationDelay - 1);
    await expectRevert(gov.execute(gov.address, data, 0, {from: accounts[0]}));
    await gov.setTestClock(start + rotationDelay);
    await gov.execute(gov.address, data, 0, {from: accounts[0]});
    assert.equal(tronWeb.address.toHex(await gov.owners(2)), tronWeb.address.toHex(accounts[3]));
    const spend = transferData(accounts[8], 1);
    await expectRevert(gov.approve(token.address, spend, 1, {from: accounts[2]}));
    await gov.approve(token.address, spend, 1, {from: accounts[3]});
    await gov.approve(token.address, spend, 1, {from: accounts[1]});
    await gov.setTestClock(start + rotationDelay + delay);
    await gov.execute(token.address, spend, 1, {from: accounts[3]});
    assert.equal((await token.balanceOf(accounts[8])).toString(), amount(1));
  });

  it('lets two owners cancel a pending nonce without transferring funds', async () => {
    const {gov, token} = await setup();
    const spend = transferData(accounts[8], 1);
    await gov.approve(token.address, spend, 0, {from: accounts[0]});
    await gov.approve(token.address, spend, 0, {from: accounts[1]});
    const cancel = '0x' + tronWeb.sha3('cancelCurrentNonce()').slice(2, 10);
    await gov.approve(gov.address, cancel, 0, {from: accounts[0]});
    await gov.approve(gov.address, cancel, 0, {from: accounts[2]});
    await gov.setTestClock(start + rotationDelay);
    await gov.execute(gov.address, cancel, 0, {from: accounts[0]});
    assert.equal((await gov.nonce()).toString(), '1');
    await expectRevert(gov.execute(token.address, spend, 0, {from: accounts[1]}));
    assert.equal((await token.balanceOf(accounts[8])).toString(), '0');
  });

  it('allows an emergency 2-of-3 veto before an external operation reaches its 48-hour deadline', async () => {
    const {gov, token} = await setup();
    const risky = transferData(accounts[8], 4);
    await gov.approve(token.address, risky, 0, {from: accounts[0]});
    await gov.approve(token.address, risky, 0, {from: accounts[1]});
    await expectRevert(gov.vetoCurrentNonce({from: accounts[8]}));
    await gov.vetoCurrentNonce({from: accounts[0]});
    assert.equal((await gov.nonce()).toString(), '0');
    await expectRevert(gov.vetoCurrentNonce({from: accounts[0]}));
    await gov.vetoCurrentNonce({from: accounts[2]});
    assert.equal((await gov.emergencyVetoCount(0)).toString(), '2');
    assert.equal((await gov.nonce()).toString(), '1');
    await gov.setTestClock(start + rotationDelay);
    await expectRevert(gov.execute(token.address, risky, 0, {from: accounts[1]}));
    assert.equal((await token.balanceOf(accounts[8])).toString(), '0');

    // The veto cannot transfer funds or permanently disable the controller.
    const safe = transferData(accounts[7], 2);
    await gov.approve(token.address, safe, 1, {from: accounts[0]});
    await gov.approve(token.address, safe, 1, {from: accounts[1]});
    await gov.setTestClock(start + rotationDelay + delay);
    await gov.execute(token.address, safe, 1, {from: accounts[2]});
    assert.equal((await token.balanceOf(accounts[7])).toString(), amount(2));
    assert.equal((await gov.nonce()).toString(), '2');
  });
});
