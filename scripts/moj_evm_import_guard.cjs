"use strict";
/* A minimal, dependency-free admission gate for offline Solidity imports.
 * It cannot by itself attest an installed package version. The caller still
 * pins solc/OpenZeppelin and reads files using Node's normal package loader.
 */
const PREFIX = "@openzeppelin/contracts/";

function isTrustedSolidityImport(requested) {
  if (typeof requested !== "string" || !requested.startsWith(PREFIX) ||
      !requested.endsWith(".sol")) return false;
  const remainder = requested.slice(PREFIX.length);
  // No dot segments, absolute paths, URL syntax, backslashes or arbitrary
  // packages can ever be sent to require.resolve by the compilation gate.
  return remainder.split("/").every(part =>
    /^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(part));
}

module.exports = {isTrustedSolidityImport};
