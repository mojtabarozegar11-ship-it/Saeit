"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {isTrustedSolidityImport} = require("../scripts/moj_evm_import_guard.cjs");

test("offline Solidity compilation calls import gate before resolving dependencies", () => {
  const source = fs.readFileSync(path.join(__dirname, "../scripts/verify_moj_evm_compile.cjs"), "utf8");
  const guard = source.indexOf("if (!isTrustedSolidityImport(requested))");
  const resolution = source.indexOf("require.resolve(requested)");
  assert.ok(guard >= 0 && resolution > guard);
});

test("accepts only pinned OpenZeppelin Solidity source units", () => {
  for (const requested of [
    "@openzeppelin/contracts/token/ERC20/ERC20.sol",
    "@openzeppelin/contracts/token/ERC20/IERC20.sol",
    "@openzeppelin/contracts/utils/Context.sol",
    "@openzeppelin/contracts/interfaces/draft-IERC6093.sol",
  ]) {
    assert.equal(isTrustedSolidityImport(requested), true, requested);
  }
});

test("rejects arbitrary packages, URLs, disk paths and traversal", () => {
  for (const requested of [
    "node:fs", "/etc/passwd", "../../private/secret.sol",
    "https://example.test/contract.sol", "@other/contracts/Malicious.sol",
    "@openzeppelin/contracts/../../private.sol",
    "@openzeppelin/contracts/utils/../secret.sol",
    "@openzeppelin/contracts\\..\\private.sol",
    "@openzeppelin/contracts/.hidden.sol", "@openzeppelin/contracts/token/ERC20/",
    null, 42,
  ]) {
    assert.equal(isTrustedSolidityImport(requested), false, String(requested));
  }
});
