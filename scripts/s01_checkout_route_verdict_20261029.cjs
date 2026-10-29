'use strict';
// Pure classification of anonymous GET navigation; never a buyer-flow proof.
function classifyNavigation(path, http, finalPath, error) {
  const authGated = /\/checkout\/$/.test(path) || path.includes('/purchases/');
  const authRequired = authGated && finalPath === '/accounts/login/';
  const expectedDestination = finalPath === path || authRequired;
  const unexpectedRedirect = !expectedDestination;
  const observedSafe = http >= 200 && http < 400 && !error && expectedDestination;
  return {authRequired, unexpectedRedirect, observedSafe};
}
module.exports = {classifyNavigation};
