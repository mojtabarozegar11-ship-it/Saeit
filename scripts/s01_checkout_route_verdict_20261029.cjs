'use strict';
// Pure classification of anonymous GET navigation; never a buyer-flow proof.
function classifyNavigation(path, http, finalPath, error, finalSearch = '') {
  const authGated = /\/checkout\/$/.test(path) || path.includes('/purchases/');
  const authRequired = authGated && finalPath === '/accounts/login/';
  // A login response with a mismatched next target can strand a buyer on
  // another product or an external site. Never count it as a healthy checkout.
  let safeLoginReturn = false;
  if (authRequired && typeof finalSearch === 'string' && finalSearch.startsWith('?')) {
    try {
      const params = new URLSearchParams(finalSearch);
      const nextValues = params.getAll('next');
      // A login redirect without the exact original return path strands the
      // buyer; extra/duplicate query keys make the navigation ambiguous.
      safeLoginReturn = [...params.keys()].every(key => key === 'next') &&
        nextValues.length === 1 && nextValues[0] === path;
    } catch (_) { safeLoginReturn = false; }
  }
  // No query is expected on a directly requested canonical checkout route.
  const expectedDestination = (finalPath === path && !finalSearch) ||
    (authRequired && safeLoginReturn);
  const unexpectedRedirect = !expectedDestination;
  // Redirect-only, malformed or missing responses are not successful page observations.
  // page.goto normally returns the final response, but classify defensively.
  const observedSafe = Number.isInteger(http) && http >= 200 && http < 300 && !error && expectedDestination;
  return {authRequired, unexpectedRedirect, observedSafe};
}
module.exports = {classifyNavigation};
