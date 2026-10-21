/*
 * ON-CHAIN integration suite for TronBox + local TVM runtime (TRE).
 * Unlike the Node model tests, this invokes compiled contracts; NOT run without TRE.
 * Run: npm run test:onchain:local
 */
const MojCoin = artifacts.require('MojCoin');
const MojVestingVault = artifacts.require('MojVestingVault');

contract('MOJ1 token and team vault', (accounts) => {
  it('funds the vault and exposes immutable cliff / duration math', async () => {
    const token = await MojCoin.new(accounts[0]);
    const allocation = '10000000000000000000000000000'; // 10 billion * 10^18
    const start = Math.floor(Date.now() / 1000) + 3600;
    const cliff = 365 * 86400;
    const duration = 3 * 365 * 86400;
    const vault = await MojVestingVault.new(
      token.address, accounts[1], allocation, start, cliff, duration
    );

    assert.equal(await vault.fullyFunded(), false);
    assert.equal((await vault.vestedAt(start + cliff)).toString(), '0');
    assert.equal((await vault.vestedAt(start + cliff + duration / 2)).toString(), '5000000000000000000000000000');
    assert.equal((await vault.vestedAt(start + cliff + duration)).toString(), allocation);
    await token.transfer(vault.address, allocation);
    assert.equal(await vault.fullyFunded(), true);
    assert.equal((await token.balanceOf(vault.address)).toString(), allocation);
    // TronBox returns raw hex for contract addresses; account fixtures are Base58.
    assert.equal(tronWeb.address.fromHex(await vault.beneficiary()), accounts[1]);
  });
});
