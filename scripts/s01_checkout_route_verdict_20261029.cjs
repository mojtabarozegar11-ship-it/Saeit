'use strict';
// Pure classification of anonymous GET navigation; never a buyer-flow proof.
function classifyNavigation(path, http, finalPath, error, finalSearch = '') {
  const authGated = /\/checkout\/$/.test(path) || path.includes('/purchases/');
  const authRequired = authGated && finalPath === '/accounts/login/';
  // A login response with a mismatched next target can strand a buyer on
  // another product or an external site. Never count it as a healthy checkout.
  let safeLoginReturn = true;
  if (authRequired && finalSearch) {
    if (typeof finalSearch !== 'string') safeLoginReturn = false;
    else {
      try {
        const nextValues = new URLSearchParams(finalSearch).getAll('next');
        safeLoginReturn = nextValues.length <= 1 &&
          (nextValues.length === 0 || nextValues[0] === path);
      } catch (_) { safeLoginReturn = false; }
    }
  }
  const expectedDestination = finalPath === path || (authRequired && safeLoginReturn);
  const unexpectedRedirect = !expectedDestination;
  // Redirect-only, malformed or missing responses are not successful page observations.
  // page.goto normally returns the final response, but classify defensively.
  const observedSafe = Number.isInteger(http) && http >= 200 && http < 300 && !error && expectedDestination;
  return {authRequired, unexpectedRedirect, observedSafe};
}
module.exports = {classifyNavigation};
