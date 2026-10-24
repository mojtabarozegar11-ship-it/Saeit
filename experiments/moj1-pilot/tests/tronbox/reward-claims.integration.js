/* MOJ1 reward-claims pilot: disposable LOCAL TRON TVM; no real wallet or public distribution. */
const Reward = artifacts.require('MojRewardClaimsPilot');
const TestToken = artifacts.require('MojRewardTestToken');
const Governance = artifacts.require('MojPilotGovernance');

contract('MOJ1 escrowed Merkle reward claims (local TVM only)', accounts => {
  const unit = 10n ** 18n;
  const amount = n => (BigInt(n) * unit).toString();
  const uint = n => BigInt(n).toString(16).padStart(64, '0');

  function publishData(epoch, root, budget) {
    const selector = tronWeb.sha3('publishEpoch(uint256,bytes32,uint256)').slice(2, 10);
    return '0x' + selector + uint(epoch) + root.replace(/^0x/, '').padStart(64, '0') + uint(budget);
  }

  function cancelData(epoch) {
    return '0x' + tronWeb.sha3('cancelEmptyEpoch(uint256)').slice(2, 10) + uint(epoch);
  }

  async function expectRevert(promise) {
    const txid = await promise;
    const info = await tronWeb.trx.getTransactionInfo(txid);
    assert.equal(info?.receipt?.result, 'REVERT', 'expected a real local TVM REVERT receipt');
  }

  async function governed(gov, escrow, data, nonce) {
    await gov.approve(escrow.address, data, nonce, {from: accounts[0]});
    await expectRevert(gov.execute(escrow.address, data, nonce, {from: accounts[2]}));
    await gov.approve(escrow.address, data, nonce, {from: accounts[1]});
    const txid = await gov.execute(escrow.address, data, nonce, {from: accounts[2]});
    const info = await tronWeb.trx.getTransactionInfo(txid);
    assert.equal(info?.receipt?.result, 'SUCCESS', 'governed operation must succeed on TVM');
  }

  async function setup() {
    const gov = await Governance.new([accounts[0], accounts[1], accounts[2]]);
    const token = await TestToken.new();
    const escrow = await Reward.new(token.address, gov.address);
    await token.transfer(escrow.address, amount(40), {from: accounts[0]});
    assert.equal((await token.balanceOf(escrow.address)).toString(), amount(40));
    return {gov, token, escrow};
  }

  it('requires 2-of-3 to publish, pays a proven account only once, and never overspends', async () => {
    const {gov, token, escrow} = await setup();
    const recipient = accounts[7];
    const root = await escrow.claimLeaf(1, 0, recipient, amount(10));
    const data = publishData(1, root, amount(25));
    await expectRevert(escrow.publishEpoch(1, root, amount(25), {from: accounts[0]}));
    await governed(gov, escrow, data, 0);
    assert.equal((await gov.nonce()).toString(), '1');
    assert.equal((await escrow.outstandingCommitments()).toString(), amount(25));
    assert.equal((await escrow.availableToCommit()).toString(), amount(15));
    await expectRevert(escrow.claim(1, 0, accounts[8], amount(10), [], {from: accounts[6]}));
    await expectRevert(escrow.claim(1, 0, recipient, amount(11), [], {from: accounts[6]}));
    await expectRevert(escrow.claim(2, 0, recipient, amount(10), [], {from: accounts[6]}));
    const before = BigInt((await token.balanceOf(recipient)).toString());
    const txid = await escrow.claim(1, 0, recipient, amount(10), [], {from: accounts[9]});
    const info = await tronWeb.trx.getTransactionInfo(txid);
    assert.equal(info?.receipt?.result, 'SUCCESS');
    assert.equal((BigInt((await token.balanceOf(recipient)).toString()) - before).toString(), amount(10));
    assert.equal((await escrow.claimedIndex(1, 0)), true);
    assert.equal((await escrow.claimedAccount(1, recipient)), true);
    assert.equal((await escrow.outstandingCommitments()).toString(), amount(15));
    assert.equal((await escrow.availableToCommit()).toString(), amount(15));
    await expectRevert(escrow.claim(1, 0, recipient, amount(10), [], {from: accounts[9]}));
    assert.equal((await token.balanceOf(escrow.address)).toString(), amount(30));
    assert.equal((await escrow.outstandingCommitments()).toString(), amount(15));
  });

  it('refuses unfunded epochs and never frees a partly-claimed epoch liability', async () => {
    const {gov, token, escrow} = await setup();
    const root = await escrow.claimLeaf(9, 0, accounts[6], amount(9));
    const unfunded = publishData(9, root, amount(41));
    await gov.approve(escrow.address, unfunded, 0, {from: accounts[0]});
    await gov.approve(escrow.address, unfunded, 0, {from: accounts[1]});
    await expectRevert(gov.execute(escrow.address, unfunded, 0, {from: accounts[2]}));
    assert.equal((await gov.nonce()).toString(), '0', 'failed transaction must not burn nonce');
    assert.equal((await escrow.outstandingCommitments()).toString(), '0');
    await governed(gov, escrow, publishData(9, root, amount(40)), 0);
    await expectRevert(escrow.claim(9, 0, accounts[6], amount(9), ['0x' + '00'.repeat(32)], {from: accounts[6]}));
    await escrow.claim(9, 0, accounts[6], amount(9), [], {from: accounts[6]});
    const cancel = cancelData(9);
    await gov.approve(escrow.address, cancel, 1, {from: accounts[0]});
    await gov.approve(escrow.address, cancel, 1, {from: accounts[1]});
    await expectRevert(gov.execute(escrow.address, cancel, 1, {from: accounts[2]}));
    assert.equal((await gov.nonce()).toString(), '1');
    assert.equal((await escrow.outstandingCommitments()).toString(), amount(31));
    assert.equal((await escrow.availableToCommit()).toString(), '0');
    assert.equal((await token.balanceOf(escrow.address)).toString(), amount(31));
    const nextRoot = await escrow.claimLeaf(10, 0, accounts[7], amount(1));
    const nextData = publishData(10, nextRoot, amount(1));
    await gov.approve(escrow.address, nextData, 1, {from: accounts[0]});
    await gov.approve(escrow.address, nextData, 1, {from: accounts[1]});
    await expectRevert(gov.execute(escrow.address, nextData, 1, {from: accounts[2]}));
  });

  it('governance may cancel an untouched epoch, never republish its identifier or claim it', async () => {
    const {gov, escrow} = await setup();
    const root = await escrow.claimLeaf(25, 0, accounts[7], amount(8));
    await governed(gov, escrow, publishData(25, root, amount(8)), 0);
    await governed(gov, escrow, cancelData(25), 1);
    assert.equal((await escrow.availableToCommit()).toString(), amount(40));
    assert.equal((await escrow.outstandingCommitments()).toString(), '0');
    await expectRevert(escrow.claim(25, 0, accounts[7], amount(8), [], {from: accounts[8]}));
    const repeat = publishData(25, root, amount(8));
    await gov.approve(escrow.address, repeat, 2, {from: accounts[0]});
    await gov.approve(escrow.address, repeat, 2, {from: accounts[1]});
    await expectRevert(gov.execute(escrow.address, repeat, 2, {from: accounts[2]}));
    assert.equal((await gov.nonce()).toString(), '2');
  });
});
