// Keyless, read-only verification of MOJ1's published Shasta deployment.
// Never sign, broadcast, distribute, mint or access the MojPlayWin payment database.
import {TronWeb} from 'tronweb';
import {readFile} from 'node:fs/promises';

const manifest = JSON.parse(await readFile(new URL('../shasta-deployment.json', import.meta.url),'utf8'));
if (manifest.network !== 'Shasta' || manifest.chain_scope !== 'TESTNET_ONLY' ||
    manifest.rpc !== 'https://api.shasta.trongrid.io' ||
    manifest.public_sale_enabled !== false || manifest.real_payment_enabled !== false ||
    manifest.mojplaywin_integration_mode !== 'READ_ONLY_STAGING') {
  throw Error('Shasta-only no-sale staging manifest required');
}
const tron = new TronWeb({fullHost:'https://api.shasta.trongrid.io'});
const artifacts = {};
for (const contract of ['MojPilotGovernance','MojCoin','MojGenesisDistributor','MojAssets']) {
  const a = JSON.parse(await readFile(new URL('../build/contracts/'+contract+'.json',import.meta.url),'utf8'));
  if(a.contractName!==contract || !Array.isArray(a.abi)) throw Error('ABI_MISSING_'+contract);
  artifacts[contract]=a;
}
const canonical = value => tron.address.fromHex(tron.address.toHex(String(value)));
const requireSame = (a,b,label) => { if(canonical(a)!==canonical(b)) throw Error(label+'_MISMATCH'); };
const requireEqual = (a,b,label) => { if(String(a)!==String(b)) throw Error(label+'_MISMATCH'); };
const contract = (name,address) => tron.contract(artifacts[name].abi,address);
const governor = contract('MojPilotGovernance',manifest.governance_contract);
const token = contract('MojCoin',manifest.token_contract);
const escrow = contract('MojGenesisDistributor',manifest.genesis_escrow);
const nft = contract('MojAssets',manifest.nft_contract);
for(const address of [manifest.governance_contract,manifest.token_contract,manifest.nft_contract]) {
  const onChain = await tron.trx.getContract(address);
  if(!onChain?.bytecode) throw Error('SHASTA_CONTRACT_CODE_MISSING_'+address);
}
for(let i=0;i<3;i++) requireSame(await governor.owners(i).call(),manifest.test_governance_owners[i],'GOVERNANCE_OWNER_'+i);
requireEqual(await governor.nonce().call(),0,'GOVERNANCE_NONCE');
const [name,symbol,decimals,supply,dist,escrowAmount,govAddress,distributed,
       nftName,nftSymbol,nftOwner,maxItems]=await Promise.all([
  token.name().call(),token.symbol().call(),token.decimals().call(),
  token.totalSupply().call(),token.distributor().call(),
  token.balanceOf(manifest.genesis_escrow).call(),escrow.governance().call(),
  escrow.distributed().call(),nft.name().call(),nft.symbol().call(),
  nft.owner().call(),nft.MAX_ITEMS().call()
]);
requireEqual(name,manifest.name,'TOKEN_NAME');
requireEqual(symbol,manifest.symbol,'TOKEN_SYMBOL');
requireEqual(decimals,manifest.decimals,'TOKEN_DECIMALS');
const expected = BigInt(manifest.total_supply_whole)*10n**BigInt(manifest.decimals);
requireEqual(supply.toString(),expected.toString(),'FIXED_SUPPLY');
requireEqual(escrowAmount.toString(),expected.toString(),'GENESIS_ESCROW_CONSERVATION');
requireSame(dist,manifest.genesis_escrow,'DISTRIBUTOR');
requireSame(govAddress,manifest.governance_contract,'DISTRIBUTOR_GOVERNANCE');
requireEqual(distributed,false,'GENESIS_NOT_DISTRIBUTED');
requireEqual(nftName,'Moj Digital Assets','NFT_NAME');
requireEqual(nftSymbol,'MOJA','NFT_SYMBOL');
requireSame(nftOwner,manifest.governance_contract,'NFT_OWNER');
requireEqual(maxItems,10000,'NFT_LIMIT');
console.log(JSON.stringify({
  mode:'MOJ1_SHASTA_PUBLIC_READ_ONLY',status:'PASS',token:manifest.token_contract,
  escrow:manifest.genesis_escrow,governance:manifest.governance_contract,
  nft:manifest.nft_contract,totalWholeTokens:manifest.total_supply_whole,
  escrowFullyFunded:true,distributed:false,mainnet:false,privateKeyUsed:false,
  paymentsModified:false
},null,2));
