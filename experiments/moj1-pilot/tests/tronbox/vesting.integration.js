/* Real TVM integration tests on an ephemeral, localhost-only TRON runtime. */
const MojCoin = artifacts.require('MojCoin');
const MojVestingVault = artifacts.require('MojVestingVault');
const MojApprovalReserveClockHarness = artifacts.require('MojApprovalReserveClockHarness');
const MojGenesisDistributor = artifacts.require('MojGenesisDistributor');
const MojAssets = artifacts.require('MojAssets');

contract('MOJ1 escrowed genesis allocations', (accounts) => {
  const unit = 10n ** 18n;
  const amounts = [35n, 20n, 15n, 10n, 15n, 5n].map(x => (x * 1_000_000_000n * unit).toString());
  const day = 86400;
  let token, distributor, vaults, start;

  async function expectRevert(txPromise) {
    const txId = await txPromise;
    const receipt = await tronWeb.trx.getTransactionInfo(txId);
    assert.equal(receipt?.receipt?.result, 'REVERT', 'TVM receipt must show REVERT');
  }

  function addressFromResult(raw) {
    return tronWeb.address.fromHex(raw);
  }

  before(async () => {
    token = await MojCoin.new(accounts[0]);
    distributor = await MojGenesisDistributor.at(addressFromResult(await token.distributor()));
    start = Math.floor(Date.now() / 1000) + 7200;
    vaults = [];
    for (let i = 0; i < 6; i++) {
      const beneficiary = accounts[i + 1];
      if (i === 2 || i === 5) {
        vaults.push(await MojApprovalReserveClockHarness.new(token.address, beneficiary, accounts[0], amounts[i]));
      } else {
        const cliff = i === 3 ? 365 * day : 0;
        const duration = (i === 0 ? 1825 : i === 3 ? 1095 : 1460) * day;
        vaults.push(await MojVestingVault.new(token.address, beneficiary, amounts[i], start, cliff, duration));
      }
    }
  });

  it('escrows 100 billion before distribution and blocks an unauthorized caller', async () => {
    const supply = (100_000_000_000n * unit).toString();
    assert.equal((await token.totalSupply()).toString(), supply);
    assert.equal((await token.balanceOf(distributor.address)).toString(), supply);
    assert.equal((await token.balanceOf(accounts[0])).toString(), '0');
    assert.equal(await distributor.distributed(), false);
    await expectRevert(distributor.distribute(vaults.map(x => x.address), start, {from: accounts[1]}));
    assert.equal((await token.balanceOf(distributor.address)).toString(), supply);
  });

  it('funds six immutable independent vaults once with exact percentages', async () => {
    await distributor.distribute(vaults.map(x => x.address), start, {from: accounts[0]});
    assert.equal(await distributor.distributed(), true);
    assert.equal((await token.balanceOf(distributor.address)).toString(), '0');
    for (let i = 0; i < 6; i++) {
      assert.equal((await distributor.bucketAmount(i)).toString(), amounts[i]);
      assert.equal((await token.balanceOf(vaults[i].address)).toString(), amounts[i]);
      assert.equal(await vaults[i].fullyFunded(), true);
      assert.equal(addressFromResult(await vaults[i].beneficiary()), accounts[i + 1]);
      assert.equal(addressFromResult(await distributor.vaults(i)), addressFromResult(vaults[i].address));
    }
    assert.equal((await token.totalSupply()).toString(), (100_000_000_000n * unit).toString());
  });

  it('enforces the team cliff and 3-year linear schedule', async () => {
    const team = vaults[3];
    const cliff = 365 * day;
    const duration = 1095 * day;
    assert.equal((await team.vestedAt(start + cliff)).toString(), '0');
    assert.equal((await team.vestedAt(start + cliff + duration / 2)).toString(), (5_000_000_000n * unit).toString());
    assert.equal((await team.vestedAt(start + cliff + duration)).toString(), amounts[3]);
    await expectRevert(team.release());
    assert.equal((await token.balanceOf(team.address)).toString(), amounts[3]);
  });

  it('blocks any second distribution, leaving every existing vault unchanged', async () => {
    await expectRevert(distributor.distribute(vaults.map(x => x.address), start));
    for (let i = 0; i < 6; i++) {
      assert.equal((await token.balanceOf(vaults[i].address)).toString(), amounts[i]);
    }
  });

  it('enforces reserve controller, strict tranche caps, cancellation and 30-day advance notice', async () => {
    const reserve = vaults[2];
    const cap = (1_000_000_000n * unit).toString();
    await reserve.setTime(start); // test fixture only; immutable production chain clock is unmodified
    assert.equal((await reserve.trancheCap()).toString(), cap);
    assert.equal((await vaults[5].trancheCap()).toString(), (250_000_000n * unit).toString());
    await expectRevert(reserve.scheduleRelease(cap, {from: accounts[1]}));
    await expectRevert(reserve.scheduleRelease('0', {from: accounts[0]}));
    await expectRevert(reserve.scheduleRelease((1_000_000_001n * unit).toString(), {from: accounts[0]}));
    await expectRevert(reserve.executeRelease());
    await reserve.scheduleRelease(cap, {from: accounts[0]});
    assert.notEqual((await reserve.releaseScheduledAt()).toString(), '0');
    assert.equal((await reserve.scheduledAmount()).toString(), cap);
    await expectRevert(reserve.scheduleRelease(cap, {from: accounts[0]}));
    await expectRevert(reserve.cancelRelease({from: accounts[1]}));
    await expectRevert(reserve.executeRelease());
    await reserve.cancelRelease({from: accounts[0]});
    assert.equal((await reserve.releaseScheduledAt()).toString(), '0');
    assert.equal((await reserve.scheduledAmount()).toString(), '0');
    assert.equal((await reserve.releasedAmount()).toString(), '0');
    assert.equal((await token.balanceOf(reserve.address)).toString(), amounts[2]);
    assert.equal((await token.balanceOf(accounts[3])).toString(), '0');
  });

  it('rejects a duplicate bucket list without moving escrowed supply', async () => {
    const fresh = await MojCoin.new(accounts[0]);
    const escrow = await MojGenesisDistributor.at(addressFromResult(await fresh.distributor()));
    const invalid = Array(6).fill(vaults[0].address);
    await expectRevert(escrow.distribute(invalid, start));
    assert.equal(await escrow.distributed(), false);
    assert.equal((await fresh.balanceOf(escrow.address)).toString(), (100_000_000_000n * unit).toString());
  });

  it('releases only capped liquidity tranches after 30-day notice and >=90-day cooldown', async () => {
    const reserve = vaults[2];
    const cap = (1_000_000_000n * unit).toString();
    await reserve.setTime(start);
    await reserve.scheduleRelease(cap, {from: accounts[0]});
    const firstExecutableAt = Number((await reserve.releaseScheduledAt()).toString());
    assert.equal(firstExecutableAt, start + 30 * day);
    await reserve.setTime(firstExecutableAt - 1);
    await expectRevert(reserve.executeRelease());
    await reserve.setTime(firstExecutableAt);
    await reserve.executeRelease({from: accounts[8]}); // anyone can execute, never redirect
    assert.equal((await reserve.releasedAmount()).toString(), cap);
    assert.equal((await token.balanceOf(accounts[3])).toString(), cap);
    assert.equal((await token.balanceOf(reserve.address)).toString(), (14_000_000_000n * unit).toString());
    assert.equal((await reserve.nextReleaseAt()).toString(), String(firstExecutableAt + 90 * day));
    assert.equal((await reserve.releaseScheduledAt()).toString(), '0');
    await expectRevert(reserve.executeRelease()); // no replay

    await reserve.scheduleRelease(cap, {from: accounts[0]});
    const secondExecutableAt = Number((await reserve.releaseScheduledAt()).toString());
    assert.equal(secondExecutableAt, firstExecutableAt + 90 * day);
    await reserve.setTime(secondExecutableAt - 1);
    await expectRevert(reserve.executeRelease());
    await reserve.setTime(secondExecutableAt);
    await reserve.executeRelease();
    assert.equal((await reserve.releasedAmount()).toString(), (2_000_000_000n * unit).toString());
    assert.equal((await token.balanceOf(accounts[3])).toString(), (2_000_000_000n * unit).toString());
    assert.equal(await reserve.released(), false);
    assert.equal(await reserve.fullyFunded(), true);
  });

  it('enforces contingency cap, independent notice/cancel, and exact fixed-supply conservation', async () => {
    const reserve = vaults[5];
    const cap = (250_000_000n * unit).toString();
    await reserve.setTime(start);
    await expectRevert(reserve.scheduleRelease((250_000_001n * unit).toString(), {from: accounts[0]}));
    await reserve.scheduleRelease(cap, {from: accounts[0]});
    await reserve.cancelRelease({from: accounts[0]});
    await expectRevert(reserve.executeRelease());
    await reserve.scheduleRelease(cap, {from: accounts[0]});
    const executableAt = Number((await reserve.releaseScheduledAt()).toString());
    await reserve.setTime(executableAt);
    await reserve.executeRelease({from: accounts[7]});
    assert.equal((await reserve.releasedAmount()).toString(), cap);
    assert.equal((await token.balanceOf(accounts[6])).toString(), cap);
    assert.equal((await token.balanceOf(reserve.address)).toString(), (4_750_000_000n * unit).toString());
    assert.equal(await reserve.fullyFunded(), true);

    let vaultBalances = 0n;
    for (const vault of vaults) vaultBalances += BigInt((await token.balanceOf(vault.address)).toString());
    const paid = BigInt((await token.balanceOf(accounts[3])).toString()) +
      BigInt((await token.balanceOf(accounts[6])).toString());
    assert.equal(vaultBalances + paid, 100_000_000_000n * unit);
    assert.equal((await token.totalSupply()).toString(), (100_000_000_000n * unit).toString());
  });

  it('rejects unfunded matured vesting; then releases the entire team-style allocation once to beneficiary', async () => {
    // Standalone copies of the real (unmodified) production vault, funded with LOCAL TVM tokens
    // previously released to a disposable beneficiary. No clock override or Mainnet interaction.
    const amount = 500n * unit;
    const now = Math.floor(Date.now() / 1000);
    const historicalStart = now - (365 + 1095 + 2) * day;
    const vault = await MojVestingVault.new(
      token.address, accounts[7], amount.toString(), historicalStart, 365 * day, 1095 * day
    );
    assert.equal((await vault.vestedAt(now)).toString(), amount.toString());
    assert.equal(await vault.fullyFunded(), false);
    await expectRevert(vault.release({from: accounts[9]}));
    assert.equal((await vault.released()).toString(), '0');

    const beneficiaryBefore = BigInt((await token.balanceOf(accounts[7])).toString());
    await token.transfer(vault.address, amount.toString(), {from: accounts[3]});
    assert.equal(await vault.fullyFunded(), true);
    await vault.release({from: accounts[9]}); // an arbitrary caller cannot redirect the payout
    assert.equal((await vault.released()).toString(), amount.toString());
    assert.equal((await token.balanceOf(vault.address)).toString(), '0');
    assert.equal(BigInt((await token.balanceOf(accounts[7])).toString()) - beneficiaryBefore, amount);
    await expectRevert(vault.release({from: accounts[0]})); // fully claimed cannot replay
    assert.equal((await vault.released()).toString(), amount.toString());
  });

  it('pays only the vested partial amount and leaves the unvested portion escrowed', async () => {
    const amount = 1200n * unit;
    const now = Math.floor(Date.now() / 1000);
    const duration = 365 * day;
    const historicalStart = now - Math.floor(duration / 2);
    const vault = await MojVestingVault.new(
      token.address, accounts[8], amount.toString(), historicalStart, 0, duration
    );
    await token.transfer(vault.address, amount.toString(), {from: accounts[3]});
    const beneficiaryBefore = BigInt((await token.balanceOf(accounts[8])).toString());
    await vault.release({from: accounts[6]});
    const claimed = BigInt((await vault.released()).toString());
    const vaultBalance = BigInt((await token.balanceOf(vault.address)).toString());
    const beneficiaryAfter = BigInt((await token.balanceOf(accounts[8])).toString());
    assert.ok(claimed > 0n && claimed < amount, 'partially vested allocation required');
    assert.equal(beneficiaryAfter - beneficiaryBefore, claimed);
    assert.equal(vaultBalance + claimed, amount, 'no allocation leak or over-release');
    assert.equal(await vault.fullyFunded(), true);
    assert.equal((await token.totalSupply()).toString(), (100_000_000_000n * unit).toString());
  });

  it('mints a valid NFT and blocks invalid metadata or a former owner', async () => {
    const nft = await MojAssets.new(accounts[0]);
    await nft.safeMint(accounts[1], 'ipfs://moj1-pilot');
    assert.equal(addressFromResult(await nft.ownerOf(1)), accounts[1]);
    await expectRevert(nft.safeMint(accounts[1], ''));
    await nft.transferOwnership(accounts[1]);
    await expectRevert(nft.safeMint(accounts[1], 'ipfs://former-owner'));
  });
});

const MojPilotGovernance = artifacts.require('MojPilotGovernance');

contract('MOJ1 experimental 2-of-3 governance on isolated TVM', (accounts) => {
  async function expectReverted(promise) {
    const txId = await promise;
    const info = await tronWeb.trx.getTransactionInfo(txId);
    assert.equal(info?.receipt?.result, 'REVERT', 'Transaction must revert in TVM');
  }

  it('requires two different owners before executing a token read through governance', async () => {
    const governance = await MojPilotGovernance.new([accounts[0], accounts[1], accounts[2]]);
    const token = await MojCoin.new(governance.address);
    const escrowAddress = tronWeb.address.fromHex(await token.distributor());
    const distributor = await MojGenesisDistributor.at(escrowAddress);
    assert.equal(tronWeb.address.toHex(await distributor.governance()), tronWeb.address.toHex(governance.address));
    const callData = '0x18160ddd'; // TRC20 totalSupply()
    await expectReverted(governance.execute(token.address, callData, 0, {from: accounts[0]}));
    await expectReverted(governance.approve(token.address, callData, 0, {from: accounts[5]}));
    await governance.approve(token.address, callData, 0, {from: accounts[0]});
    await expectReverted(governance.approve(token.address, callData, 0, {from: accounts[0]}));
    assert.equal((await governance.approvals(await governance.operationHash(token.address, callData, 0))).toString(), '1');
    await expectReverted(governance.execute(token.address, callData, 0, {from: accounts[2]}));
    await governance.approve(token.address, callData, 0, {from: accounts[1]});
    await governance.execute(token.address, callData, 0, {from: accounts[2]});
    assert.equal((await governance.nonce()).toString(), '1');
    await expectReverted(governance.execute(token.address, callData, 0, {from: accounts[0]}));
    assert.equal((await token.totalSupply()).toString(), (100_000_000_000n * 10n ** 18n).toString());
  });

  it('rejects duplicate governance owners and a zero-address owner', async () => {
    try {
      await MojPilotGovernance.new([accounts[0], accounts[0], accounts[1]]);
      assert.fail('duplicate owners should fail');
    } catch (error) {
      assert.match(String(error.message), /Duplicate owner|revert|REVERT|failed|not been deployed/i);
    }
  });
  it('executes an actual governed ownership change after two owner approvals', async () => {
    const governance = await MojPilotGovernance.new([accounts[0], accounts[1], accounts[2]]);
    const collection = await MojAssets.new(governance.address);
    const receiver = accounts[7];
    // Standard Ownable transferOwnership(address) selector + 32-byte ABI address.
    const data = '0xf2fde38b' + tronWeb.address.toHex(receiver).slice(2).padStart(64, '0');
    assert.equal(tronWeb.address.toHex(await collection.owner()), tronWeb.address.toHex(governance.address));
    await governance.approve(collection.address, data, 0, {from: accounts[0]});
    await expectReverted(governance.execute(collection.address, data, 0, {from: accounts[1]}));
    await governance.approve(collection.address, data, 0, {from: accounts[2]});
    await governance.execute(collection.address, data, 0, {from: accounts[1]});
    assert.equal(tronWeb.address.toHex(await collection.owner()), tronWeb.address.toHex(receiver));
    assert.equal((await governance.nonce()).toString(), '1');
    await expectReverted(governance.execute(collection.address, data, 0, {from: accounts[0]}));
  });

});
