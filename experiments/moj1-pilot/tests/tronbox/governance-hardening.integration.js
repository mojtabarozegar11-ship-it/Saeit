/* MOJ1 governance hardening: disposable localhost TRON TVM only. Never use real keys. */
const Governance = artifacts.require('MojPilotGovernance');

contract('MOJ1 2-of-3 signer rotation and recovery guard', accounts => {
  const normalize = value => tronWeb.address.toHex(value);
  function encodeRotation(index, nextOwner) {
    const selector = tronWeb.sha3('replaceOwner(uint8,address)').slice(2, 10);
    const ownerIndex = BigInt(index).toString(16).padStart(64, '0');
    const account = normalize(nextOwner).slice(2).padStart(64, '0');
    return '0x' + selector + ownerIndex + account;
  }
  async function expectRevert(promise) {
    const id = await promise;
    const receipt = await tronWeb.trx.getTransactionInfo(id);
    assert.equal(receipt?.receipt?.result, 'REVERT', 'expected a real TVM REVERT receipt');
  }
  it('requires two different current owners for signer rotation and removes an old signer', async () => {
    const gov = await Governance.new([accounts[0], accounts[1], accounts[2]]);
    await expectRevert(gov.replaceOwner(1, accounts[3], {from: accounts[0]}));
    const rotate = encodeRotation(1, accounts[3]);
    await gov.approve(gov.address, rotate, 0, {from: accounts[0]});
    await expectRevert(gov.execute(gov.address, rotate, 0, {from: accounts[2]}));
    await gov.approve(gov.address, rotate, 0, {from: accounts[2]});
    const op = await gov.operationHash(gov.address, rotate, 0);
    assert.equal((await gov.currentApprovalCount(op)).toString(), '2');
    await gov.execute(gov.address, rotate, 0, {from: accounts[0]});
    assert.equal(normalize(await gov.owners(1)), normalize(accounts[3]));
    assert.equal((await gov.nonce()).toString(), '1');
    await expectRevert(gov.execute(gov.address, rotate, 0, {from: accounts[0]}));
    const next = encodeRotation(2, accounts[4]);
    await expectRevert(gov.approve(gov.address, next, 1, {from: accounts[1]}));
    await gov.approve(gov.address, next, 1, {from: accounts[0]});
    await gov.approve(gov.address, next, 1, {from: accounts[3]});
    await gov.execute(gov.address, next, 1, {from: accounts[3]});
    assert.equal(normalize(await gov.owners(2)), normalize(accounts[4]));
    assert.equal((await gov.nonce()).toString(), '2');
  });

  it('rejects a duplicate signer and preserves the nonce on reverted execution', async () => {
    const gov = await Governance.new([accounts[0], accounts[1], accounts[2]]);
    const duplicate = encodeRotation(0, accounts[1]);
    await gov.approve(gov.address, duplicate, 0, {from: accounts[0]});
    await gov.approve(gov.address, duplicate, 0, {from: accounts[1]});
    await expectRevert(gov.execute(gov.address, duplicate, 0, {from: accounts[2]}));
    assert.equal((await gov.nonce()).toString(), '0');
    assert.equal(normalize(await gov.owners(0)), normalize(accounts[0]));
  });
});
