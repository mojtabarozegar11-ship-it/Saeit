/*
 * ON-CHAIN integration suite for TronBox + local TVM runtime (TRE).
 * Unlike the Node model tests, this invokes compiled contracts; NOT run without TRE.
 * Run: npm run test:onchain:local
 */
const MojCoin = artifacts.require('MojCoin');
const MojVestingVault = artifacts.require('MojVestingVault');
const MojAssets = artifacts.require('MojAssets');

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
  it('keeps the fixed 100 billion MOJ1 supply unchanged after transfers', async () => {
    const token = await MojCoin.new(accounts[0]);
    const fixedSupply = '100000000000000000000000000000';
    const smallTransfer = '2500000000000000000';
    assert.equal((await token.totalSupply()).toString(), fixedSupply);
    await token.transfer(accounts[1], smallTransfer);
    assert.equal((await token.balanceOf(accounts[1])).toString(), smallTransfer);
    assert.equal((await token.totalSupply()).toString(), fixedSupply);
  });

  it('mints an identified NFT with an owner and a metadata URI', async () => {
    const collection = await MojAssets.new(accounts[0]);
    await collection.safeMint(accounts[1], 'ipfs://moj1-local-fixture-1');
    assert.equal(tronWeb.address.fromHex(await collection.ownerOf(1)), accounts[1]);
    assert.equal(await collection.tokenURI(1), 'ipfs://moj1-local-fixture-1');
  });


  it('rejects release before funding and before the cliff without losing tokens', async () => {
    const token = await MojCoin.new(accounts[0]);
    const allocation = '100000000000000000000'; // 100 MOJ1
    const start = Math.floor(Date.now() / 1000) + 3600;
    const vault = await MojVestingVault.new(token.address, accounts[1], allocation, start, 86400, 86400);

    let rejectedUnfunded = false;
    try { await vault.release(); } catch (error) { rejectedUnfunded = true; }
    assert.equal(rejectedUnfunded, true, 'unfunded vault must reject release');
    assert.equal((await vault.released()).toString(), '0');

    await token.transfer(vault.address, allocation);
    let rejectedBeforeCliff = false;
    try { await vault.release(); } catch (error) { rejectedBeforeCliff = true; }
    assert.equal(rejectedBeforeCliff, true, 'pre-cliff release must be rejected');
    assert.equal((await vault.released()).toString(), '0');
    assert.equal((await token.balanceOf(vault.address)).toString(), allocation);
    assert.equal((await token.balanceOf(accounts[1])).toString(), '0');
  });

  it('rejects invalid NFT metadata and a former NFT owner minting', async () => {
    const collection = await MojAssets.new(accounts[0]);
    let rejectedBlank = false;
    try { await collection.safeMint(accounts[1], ''); } catch (error) { rejectedBlank = true; }
    assert.equal(rejectedBlank, true, 'blank NFT metadata must fail');
    assert.equal((await collection.balanceOf(accounts[1])).toString(), '0');

    await collection.transferOwnership(accounts[1]);
    let rejectedFormerOwner = false;
    try { await collection.safeMint(accounts[1], 'ipfs://former-owner-test'); } catch (error) { rejectedFormerOwner = true; }
    assert.equal(rejectedFormerOwner, true, 'former owner must not mint');
    assert.equal((await collection.balanceOf(accounts[1])).toString(), '0');
  });

});
