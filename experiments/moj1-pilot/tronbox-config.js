// Local-only TVM configuration. Never include an external TRON RPC or a real private key here.
module.exports = {
  networks: {
    development: {
      privateKey: process.env.LOCAL_PRIVATE_KEY,
      userFeePercentage: 0,
      feeLimit: 1000 * 1e6,
      fullHost: 'http://127.0.0.1:9090',
      network_id: '9'
    }
  },
  compilers: {
    solc: { version: '0.8.25', settings: { optimizer: { enabled: true, runs: 200 } } }
  }
};
