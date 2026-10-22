/* All transactions use disposable localhost TRON TVM accounts and no real MOJ1 tokens. */
const V1Coin = artifacts.require('MojCoin');
const V1Escrow = artifacts.require('MojGenesisDistributor');
const V2Coin = artifacts.require('MojCoinGuarded');
const V2Escrow = artifacts.require('MojGenesisFactoryGuarded');
const Vesting = artifacts.require('MojVestingVault');
const Reserve = artifacts.require('MojApprovalReserve');
const Lookalike = artifacts.require('MojVestingLookalike');

contract('MOJ1 genesis destination forgery: exploit demonstration and guarded V2', accounts => {
  const unit = 10n ** 18n;
  const billion = 1_000_000_000n;
  const amounts = [35n,20n,15n,10n,15n,5n].map(n => String(n * billion * unit));
  const day = 86400;
  const t0 = () => Math.floor(Date.now() / 1000) + 7200;
  const fromHex = value => tronWeb.address.fromHex(value);
  const total = (100n * billion * unit).toString();

  async function expectRevert(promise) {
    const id = await promise;
    const receipt = await tronWeb.trx.getTransactionInfo(id);
    assert.equal(receipt?.receipt?.result, 'REVERT', 'expected an actual TVM REVERT receipt');
  }

  it('reproduces HIGH-RISK V1: a getter-compatible fake vault can drain pre-cliff rewards', async () => {
    const coin = await V1Coin.new(accounts[0]);
    const escrow = await V1Escrow.at(fromHex(await coin.distributor()));
    const start = t0();
    const fake = await Lookalike.new(coin.address, accounts[1], amounts[0], start, 0, 1825 * day);
    const destinations = [fake.address];
    for (let i = 1; i < 6; i++) {
      if (i === 2 || i === 5) {
        destinations.push((await Reserve.new(coin.address, accounts[i + 1], accounts[0], amounts[i])).address);
      } else {
        const cliff = i === 3 ? 365 * day : 0;
        const duration = (i === 3 ? 1095 : 1460) * day;
        destinations.push((await Vesting.new(
          coin.address, accounts[i + 1], amounts[i], start, cliff, duration
        )).address);
      }
    }
    await escrow.distribute(destinations, start, {from: accounts[0]});
    assert.equal(await escrow.distributed(), true, 'V1 incorrectly accepts fake view methods');
    assert.equal((await coin.balanceOf(fake.address)).toString(), amounts[0]);
    const stolenBefore = BigInt((await coin.balanceOf(accounts[9])).toString());
    await fake.drain(accounts[9], {from: accounts[8]});
    assert.equal((await coin.balanceOf(fake.address)).toString(), '0');
    assert.equal((BigInt((await coin.balanceOf(accounts[9])).toString()) - stolenBefore).toString(), amounts[0]);
    assert.equal((await coin.totalSupply()).toString(), total);
  });

  it('V2 constructs real vaults itself, funds 100bn atomically and prevents caller-supplied vault code', async () => {
    const coin = await V2Coin.new(accounts[0]);
    const escrow = await V2Escrow.at(fromHex(await coin.distributor()));
    const recipients = accounts.slice(1, 7);
    const start = t0();
    assert.equal((await coin.balanceOf(escrow.address)).toString(), total);
    await expectRevert(escrow.distribute(recipients, start, {from: accounts[8]}));
    const invalid = [...recipients]; invalid[2] = recipients[0];
    await expectRevert(escrow.distribute(invalid, start, {from: accounts[0]}));
    assert.equal((await coin.balanceOf(escrow.address)).toString(), total);

    await escrow.distribute(recipients, start, {from: accounts[0]});
    assert.equal(await escrow.distributed(), true);
    assert.equal((await coin.balanceOf(escrow.address)).toString(), '0');

    let sum = 0n;
    for (let i = 0; i < 6; ++i) {
      const address = fromHex(await escrow.vaults(i));
      assert.notEqual(address, recipients[i], 'recipient is not the vault');
      assert.equal((await coin.balanceOf(address)).toString(), amounts[i]);
      if (i === 2 || i === 5) {
        const reserve = await Reserve.at(address);
        assert.equal(fromHex(await reserve.beneficiary()), recipients[i]);
        assert.equal(fromHex(await reserve.releaseController()), accounts[0]);
        assert.equal((await reserve.trancheCap()).toString(),
          (i === 2 ? 1n * billion * unit : 250_000_000n * unit).toString());
        await expectRevert(reserve.executeRelease({from: accounts[8]}));
      } else {
        const vault = await Vesting.at(address);
        assert.equal(fromHex(await vault.beneficiary()), recipients[i]);
        assert.equal((await vault.start()).toString(), String(start));
        assert.equal((await vault.cliff()).toString(), String(i === 3 ? 365 * day : 0));
        assert.equal(await vault.fullyFunded(), true);
        await expectRevert(vault.release({from: accounts[8]}));
      }
      sum += BigInt((await coin.balanceOf(address)).toString());
    }
    assert.equal(sum.toString(), total);
    await expectRevert(escrow.distribute(recipients, start, {from: accounts[0]}));
    assert.equal((await coin.totalSupply()).toString(), total);
  });
});
