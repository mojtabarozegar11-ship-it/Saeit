// Restricted local TRE testing only. DO NOT add Mainnet or public endpoints.
if(process.env.CI_MOJ7_LOCAL_ONLY!=='1') throw new Error('MOJ7 tests require local-only CI gate');
const HOST='http://127.0.0.1:9090';
module.exports = {
  networks:{development:{
    privateKey:'0000000000000000000000000000000000000000000000000000000000000001',
    fullHost:HOST,
    network_id:'9',
    feeLimit:200*1e6,
    userFeePercentage:100
  }},
  compilers:{solc:{version:'0.8.20',settings:{optimizer:{enabled:true,runs:200}}}}
};
