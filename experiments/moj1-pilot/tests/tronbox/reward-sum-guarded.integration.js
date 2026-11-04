/* MOJ1 reward-sum escrow: disposable LOCAL TRON TVM only, synthetic accounts and test token. */
const Reward = artifacts.require('MojRewardClaimsSumGuarded');
const Token = artifacts.require('MojRewardTestToken');
const Governance = artifacts.require('MojPilotGovernance');

contract('MOJ1 domain-bound Merkle-sum reward liabilities', accounts => {
  const unit = 10n ** 18n;
  const amount = n => (BigInt(n) * unit).toString();
  const uint = n => BigInt(n).toString(16).padStart(64, '0');
  const manifest = '0x' + 'ab'.repeat(32);
  const proof = (epoch, index, account, value, hashes = [], sums = [], counts = []) =>
    [epoch, index, account, value, hashes, sums, counts];

  function publishData(epoch, root, budget, count) {
    const selector = tronWeb.sha3('publishEpoch(uint256,bytes32,uint256,uint256,bytes32)').slice(2, 10);
    return '0x' + selector + uint(epoch) + root.replace(/^0x/, '').padStart(64, '0') +
      uint(budget) + uint(count) + manifest.slice(2);
  }

  async function expectRevert(promise) {
    const txid = await promise;
    const receipt = await tronWeb.trx.getTransactionInfo(txid);
    assert.equal(receipt?.receipt?.result, 'REVERT', 'actual TVM revert required');
  }

  async function governed(gov, escrow, data, nonce) {
    await gov.approve(escrow.address, data, nonce, {from: accounts[0]});
    await gov.approve(escrow.address, data, nonce, {from: accounts[1]});
    const txid = await gov.execute(escrow.address, data, nonce, {from: accounts[2]});
    const info = await tronWeb.trx.getTransactionInfo(txid);
    assert.equal(info?.receipt?.result, 'SUCCESS');
  }

  async function setup() {
    const gov = await Governance.new([accounts[0], accounts[1], accounts[2]]);
    const token = await Token.new();
    const escrow = await Reward.new(token.address, gov.address);
    await token.transfer(escrow.address, amount(50), {from: accounts[0]});
    return {gov, token, escrow};
  }

  it('pays one proven leaf exactly, rejects forged amounts and replay, and settles fully', async () => {
    const {gov, token, escrow} = await setup();
    const recipient = accounts[7];
    const root = await escrow.claimLeaf(7, 0, recipient, amount(10));
    await expectRevert(escrow.publishEpoch(7, root, amount(10), 1, manifest, {from: accounts[0]}));
    await governed(gov, escrow, publishData(7, root, amount(10), 1), 0);
    assert.equal((await escrow.outstandingCommitments()).toString(), amount(10));
    assert.equal(await escrow.verifyClaim(proof(7, 0, recipient, amount(10))), true);
    assert.equal(await escrow.verifyClaim(proof(7, 0, recipient, amount(9))), false);
    await expectRevert(escrow.claim(proof(7, 0, accounts[8], amount(10)), {from: accounts[9]}));
    await escrow.claim(proof(7, 0, recipient, amount(10)), {from: accounts[9]});
    assert.equal((await token.balanceOf(recipient)).toString(), amount(10));
    assert.equal((await escrow.outstandingCommitments()).toString(), '0');
    assert.equal((await escrow.availableToCommit()).toString(), amount(40));
    await expectRevert(escrow.claim(proof(7, 0, recipient, amount(10)), {from: accounts[9]}));
  });

  it('cryptographically binds a two-leaf root to the exact total and keeps unpaid claims reserved', async () => {
    const {gov, token, escrow} = await setup();
    const a = await escrow.claimLeaf(12, 0, accounts[6], amount(10));
    const b = await escrow.claimLeaf(12, 1, accounts[7], amount(5));
    const node = await escrow.combineNodes(a, amount(10), 1, b, amount(5), 1);
    const root = node[0];
    assert.equal(BigInt(node[1].toString()), 15n * unit);
    assert.equal(node[2].toString(), '2');
    await governed(gov, escrow, publishData(12, root, amount(15), 2), 0);

    assert.equal(await escrow.verifyClaim(proof(12, 0, accounts[6], amount(10), [b], [amount(5)], [1])), true);
    assert.equal(await escrow.verifyClaim(proof(12, 0, accounts[6], amount(10), [b], [amount(4)], [1])), false);
    assert.equal(await escrow.verifyClaim(proof(12, 0, accounts[6], amount(10), [b], [amount(5)], [2])), false);
    await expectRevert(escrow.claim(proof(12, 0, accounts[6], amount(10), [b], [amount(4)], [1]), {from: accounts[8]}));

    await escrow.claim(proof(12, 0, accounts[6], amount(10), [b], [amount(5)], [1]), {from: accounts[8]});
    assert.equal((await escrow.outstandingCommitments()).toString(), amount(5));
    assert.equal((await escrow.availableToCommit()).toString(), amount(35));
    assert.equal((await token.balanceOf(escrow.address)).toString(), amount(40));
    await escrow.claim(proof(12, 1, accounts[7], amount(5), [a], [amount(10)], [1]), {from: accounts[8]});
    assert.equal((await escrow.outstandingCommitments()).toString(), '0');
    assert.equal((await token.balanceOf(escrow.address)).toString(), amount(35));
    assert.equal((await escrow.epochs(12)).claimCount.toString(), '2');
  });

  it('does not confiscate unclaimed entitlements even when a malicious root repeats a wallet', async () => {
    const {gov, token, escrow} = await setup();
    const a = await escrow.claimLeaf(21, 0, accounts[6], amount(10));
    const b = await escrow.claimLeaf(21, 1, accounts[6], amount(5));
    const root = (await escrow.combineNodes(a, amount(10), 1, b, amount(5), 1))[0];
    await governed(gov, escrow, publishData(21, root, amount(15), 2), 0);
    await escrow.claim(proof(21, 0, accounts[6], amount(10), [b], [amount(5)], [1]), {from: accounts[9]});
    await expectRevert(escrow.claim(proof(21, 1, accounts[6], amount(5), [a], [amount(10)], [1]), {from: accounts[9]}));
    assert.equal((await escrow.outstandingCommitments()).toString(), amount(5));
    assert.equal((await escrow.availableToCommit()).toString(), amount(35));
    assert.equal((await token.balanceOf(escrow.address)).toString(), amount(40));
  });

  it('rejects a proof replayed against another contract address and another epoch', async () => {
    const {gov, token, escrow} = await setup();
    const other = await Reward.new(token.address, gov.address);
    await token.transfer(other.address, amount(10), {from: accounts[0]});
    const root = await escrow.claimLeaf(33, 0, accounts[6], amount(5));
    await governed(gov, escrow, publishData(33, root, amount(5), 1), 0);
    await governed(gov, other, publishData(33, root, amount(5), 1), 1);
    await governed(gov, escrow, publishData(34, root, amount(5), 1), 2);
    assert.equal(await other.verifyClaim(proof(33, 0, accounts[6], amount(5))), false);
    assert.equal(await escrow.verifyClaim(proof(34, 0, accounts[6], amount(5))), false);
    assert.equal((await escrow.outstandingCommitments()).toString(), amount(10));
    await escrow.claim(proof(33, 0, accounts[6], amount(5)), {from: accounts[9]});
    assert.equal((await token.balanceOf(accounts[6])).toString(), amount(5));
  });
});
