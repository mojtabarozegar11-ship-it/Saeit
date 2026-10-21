// Local-only migration: the integration tests instantiate their own contracts.
// TronBox requires a migration callback with at least one argument.
module.exports = function (deployer) {
  void deployer;
};
