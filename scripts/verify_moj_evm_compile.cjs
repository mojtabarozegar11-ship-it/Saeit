"use strict";
/*
 * Offline Solidity compile gate for 50 Moj candidates.
 * No wallet, RPC, deploy, secret, chain transaction or market operation.
 * Requires pinned solc@0.8.20 and @openzeppelin/contracts@5.0.2.
 */
const fs = require("node:fs");
const path = require("node:path");
const solc = require("solc");
const {isTrustedSolidityImport} = require("./moj_evm_import_guard.cjs");
const bundle = process.argv[2];

function fail(message) {
  console.error("MOJ_EVM_COMPILE_FAILED:", message);
  process.exitCode = 1;
}
if (!bundle || !fs.statSync(bundle, {throwIfNoEntry: false})?.isDirectory()) {
  fail("expected_offline_bundle_directory");
} else if (!solc.version().startsWith("0.8.20")) {
  fail("unpinned_solidity_compiler");
} else {
  const sources = {};
  for (let n = 1; n <= 50; n += 1) {
    const filename = `moj${n}/contracts/Moj${n}FixedSupply.sol`;
    const full = path.join(bundle, "evm-candidates", filename);
    const code = fs.readFileSync(full, "utf8");
    if (!code.includes(`contract Moj${n}FixedSupply is ERC20`) ||
        !code.includes(`ERC20("Moj ${n}", "MOJ${n}")`) ||
        (code.match(/_mint\(/g) || []).length !== 1) {
      fail(`source_identity_or_mint_mismatch:${n}`);
      break;
    }
    sources[filename] = {content: code};
  }
  if (process.exitCode !== 1) {
    const input = {
      language: "Solidity",
      sources,
      settings: {
        outputSelection: {"*": {"*": ["abi", "evm.bytecode.object"]}}
      }
    };
    const compilerOutput = JSON.parse(solc.compile(JSON.stringify(input), {
      import: (requested) => {
        if (!isTrustedSolidityImport(requested)) {
          return {error: `untrusted_solidity_import:${requested}`};
        }
        try {
          return {contents: fs.readFileSync(require.resolve(requested), "utf8")};
        } catch (error) {
          return {error: `dependency_not_found:${requested}`};
        }
      }
    }));
    const errors = (compilerOutput.errors || []).filter(x => x.severity === "error");
    if (errors.length) {
      fail(errors.map(x => x.formattedMessage).join("\n"));
    } else {
      let compiled = 0;
      for (let n = 1; n <= 50; n += 1) {
        const filename = `moj${n}/contracts/Moj${n}FixedSupply.sol`;
        const artifact = compilerOutput.contracts?.[filename]?.[`Moj${n}FixedSupply`];
        const bytecode = artifact?.evm?.bytecode?.object;
        if (!artifact || !Array.isArray(artifact.abi) || !bytecode ||
            /[^0-9a-f]/i.test(bytecode)) {
          fail(`missing_or_unlinked_contract_artifact:${n}`);
          break;
        }
        compiled += 1;
      }
      if (compiled === 50) {
        console.log(JSON.stringify({
          contracts_compiled: 50,
          compiler: solc.version(),
          source_files: 50,
          production_network: "undecided",
          blockchain_transactions: 0,
          contracts_deployed: 0,
          security_audit_complete: false,
          verified_revenue: false,
          status: "offline_compile_only"
        }));
      }
    }
  }
}
