// Fail-closed, keyless creation and runtime bytecode attestation for Shasta.
// A contract's ABI/readable methods are not a substitute for deployed-code identity.
import {createHash} from 'node:crypto';

function canonicalHex(value, label) {
  const h = String(value ?? '').replace(/^0x/i, '').toLowerCase();
  if (!h || h.length % 2 || !/^[0-9a-f]+$/.test(h)) {
    throw new Error(label + '_INVALID_HEX');
  }
  return h;
}

function addressWord(address, addressToHex) {
  const h = canonicalHex(addressToHex(address), 'ADDRESS');
  if (!/^41[0-9a-f]{40}$/.test(h)) throw new Error('ADDRESS_NOT_TRON_HEX');
  return h.slice(2).padStart(64, '0');
}

function immutableSpans(artifact, byteLength) {
  const references = artifact.immutableReferences ?? {};
  if (!references || typeof references !== 'object' || Array.isArray(references)) {
    throw new Error('INVALID_IMMUTABLE_REFERENCES');
  }
  const spans = [];
  for (const entries of Object.values(references)) {
    if (!Array.isArray(entries)) throw new Error('INVALID_IMMUTABLE_REFERENCES');
    for (const entry of entries) {
      if (!Number.isInteger(entry.start) || !Number.isInteger(entry.length) ||
          entry.start < 0 || entry.length !== 32 || entry.start + entry.length > byteLength) {
        throw new Error('INVALID_IMMUTABLE_SPAN');
      }
      spans.push({start: entry.start * 2, end: (entry.start + entry.length) * 2});
    }
  }
  spans.sort((a, b) => a.start - b.start);
  for (let i = 1; i < spans.length; ++i) {
    if (spans[i].start < spans[i - 1].end) throw new Error('OVERLAPPING_IMMUTABLE_SPANS');
  }
  return spans;
}

export function attestBytecode({name, artifact, chainInfo, constructorAddresses,
                                immutableAddresses = [], addressToHex}) {
  if (!/^[A-Za-z0-9]+$/.test(name) || artifact?.contractName !== name ||
      typeof addressToHex !== 'function' || !Array.isArray(constructorAddresses) ||
      !Array.isArray(immutableAddresses)) {
    throw new Error('ATTESTATION_INPUT_INVALID');
  }
  const original = canonicalHex(artifact.bytecode, name + '_COMPILED_CREATION');
  const deployedCreation = canonicalHex(chainInfo?.smart_contract?.bytecode,
    name + '_CHAIN_CREATION');
  const args = constructorAddresses.map(address => addressWord(address, addressToHex)).join('');
  // On TRON the creation bytecode may be exposed without the appended constructor
  // arguments, so accept exactly one of these two documented representations.
  // Constructor/state identity is verified independently by the read-only caller.
  if (deployedCreation !== original && deployedCreation !== original + args) {
    throw new Error(name + '_CREATION_CODE_MISMATCH');
  }
  const runtime = canonicalHex(chainInfo?.runtimecode, name + '_CHAIN_RUNTIME');
  const compiledRuntime = canonicalHex(artifact.deployedBytecode, name + '_COMPILED_RUNTIME');
  if (runtime.length !== compiledRuntime.length) {
    throw new Error(name + '_RUNTIME_LENGTH_MISMATCH');
  }
  const spans = immutableSpans(artifact, runtime.length / 2);
  const expectedValues = new Set(immutableAddresses.map(address => addressWord(address, addressToHex)));
  if (spans.length && !expectedValues.size) throw new Error(name + '_UNBOUND_IMMUTABLES');
  let cursor = 0;
  for (const span of spans) {
    if (runtime.slice(cursor, span.start) !== compiledRuntime.slice(cursor, span.start)) {
      throw new Error(name + '_RUNTIME_CODE_MISMATCH');
    }
    if (!expectedValues.has(runtime.slice(span.start, span.end))) {
      throw new Error(name + '_IMMUTABLE_VALUE_MISMATCH');
    }
    cursor = span.end;
  }
  if (runtime.slice(cursor) !== compiledRuntime.slice(cursor)) {
    throw new Error(name + '_RUNTIME_CODE_MISMATCH');
  }
  return {
    contract: name,
    method: spans.length ? 'CREATION_AND_RUNTIME_MATCH_WITH_CHECKED_IMMUTABLES' :
      'CREATION_AND_EXACT_RUNTIME_MATCH',
    immutableSlots: spans.length,
    creationSha256: createHash('sha256').update(deployedCreation, 'hex').digest('hex'),
    runtimeSha256: createHash('sha256').update(runtime, 'hex').digest('hex')
  };
}
