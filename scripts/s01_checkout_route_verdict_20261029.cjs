'use strict';
// Pure classification of anonymous GET navigation; never a buyer-flow proof.
function classifyNavigation(path, http, finalPath, error) {
  const authGated = /\/checkout\/$/.test(path) || path.includes('/purchases/');
  const authRequired = authGated && finalPath === '/accounts/login/';
  const expectedDestination = finalPath === path || authRequired;
  const unexpectedRedirect = !expectedDestination;
  // Redirect-only, malformed or missing responses are not successful page observations.
  // page.goto normally returns the final response, but classify defensively.
  const observedSafe = Number.isInteger(http) && http >= 200 && http < 300 && !error && expectedDestination;
  return {authRequired, unexpectedRedirect, observedSafe};
}
module.exports = {classifyNavigation};
