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

  it('mints a valid NFT and blocks invalid metadata or a former owner', async () => {
    const nft = await MojAssets.new(accounts[0]);
    await nft.safeMint(accounts[1], 'ipfs://moj1-pilot');
    assert.equal(addressFromResult(await nft.ownerOf(1)), accounts[1]);
    await expectRevert(nft.safeMint(accounts[1], ''));
    await nft.transferOwnership(accounts[1]);
    await expectRevert(nft.safeMint(accounts[1], 'ipfs://former-owner'));
  });
});
