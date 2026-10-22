import test from 'node:test';
import assert from 'node:assert/strict';
import {attestBytecode} from '../scripts/bytecode-attestation.mjs';

const addressToHex = x => x;
const governance = '41' + '11'.repeat(20);
const escrow = '41' + '22'.repeat(20);
const other = '41' + '33'.repeat(20);
const word = address => address.slice(2).padStart(64, '0');
const hex = value => value.toLowerCase();

function fixture({name = 'MojAssets', withImmutable = false} = {}) {
  const creation = '6001600255';
  const compiledRuntime = withImmutable ?
    '60'.repeat(5) + '00'.repeat(32) + '5b'.repeat(9) : '60'.repeat(46);
  const chainRuntime = withImmutable ?
    '60'.repeat(5) + word(escrow) + '5b'.repeat(9) : compiledRuntime;
  return {
    name,
    artifact: {
      contractName: name, bytecode: creation, deployedBytecode: compiledRuntime,
      immutableReferences: withImmutable ? {'101': [{start: 5, length: 32}]} : {}
    },
    chainInfo: {smart_contract: {bytecode: creation + word(governance)}, runtimecode: chainRuntime},
    constructorAddresses: [governance],
    immutableAddresses: withImmutable ? [escrow] : [],
    addressToHex
  };
}

test('exact creation and runtime code are attested without signing', () => {
  const result = attestBytecode(fixture());
  assert.equal(result.method, 'CREATION_AND_EXACT_RUNTIME_MATCH');
  assert.match(result.runtimeSha256, /^[a-f0-9]{64}$/);
});

test('constructor bytecode without appended args remains valid if runtime is exact', () => {
  const input = fixture();
  input.chainInfo.smart_contract.bytecode = input.artifact.bytecode;
  assert.equal(attestBytecode(input).immutableSlots, 0);
});

test('TRON constructor arguments are exact when appended', () => {
  const input = fixture();
  input.chainInfo.smart_contract.bytecode = input.artifact.bytecode + word(other);
  assert.throws(() => attestBytecode(input), /CREATION_CODE_MISMATCH/);
});

test('mutating a single creation opcode must fail closed', () => {
  const input = fixture();
  input.chainInfo.smart_contract.bytecode = '6003600255' + word(governance);
  assert.throws(() => attestBytecode(input), /CREATION_CODE_MISMATCH/);
});

test('mutating a single runtime opcode must fail closed', () => {
  const input = fixture();
  input.chainInfo.runtimecode = '61' + input.chainInfo.runtimecode.slice(2);
  assert.throws(() => attestBytecode(input), /RUNTIME_CODE_MISMATCH/);
});

test('only declared immutable slots may differ from compiled runtime', () => {
  const input = fixture({name: 'MojCoin', withImmutable: true});
  assert.equal(attestBytecode(input).immutableSlots, 1);
  input.chainInfo.runtimecode = input.chainInfo.runtimecode.slice(0, 12) +
    'ff' + input.chainInfo.runtimecode.slice(14);
  assert.throws(() => attestBytecode(input), /IMMUTABLE_VALUE_MISMATCH/);
});

test('known immutable addresses can be identified when TronBox omits slot metadata', () => {
  const input = fixture({name: 'MojGenesisDistributor', withImmutable: true});
  input.artifact.immutableReferences = {};
  assert.equal(attestBytecode(input).method,
    'CREATION_AND_RUNTIME_MATCH_WITH_VERIFIED_IMMUTABLE_ADDRESS_SLOTS');
});

test('forged reference spans and absent compiled runtime are refused', () => {
  const input = fixture({name: 'MojCoin', withImmutable: true});
  input.artifact.immutableReferences = {'101': [{start: 40, length: 32}]};
  assert.throws(() => attestBytecode(input), /INVALID_IMMUTABLE_SPAN/);
  const second = fixture();
  delete second.artifact.deployedBytecode;
  assert.throws(() => attestBytecode(second), /COMPILED_RUNTIME_INVALID_HEX/);
});

test('missing chain bytecode is never interpreted as an empty contract', () => {
  const input = fixture();
  delete input.chainInfo.smart_contract.bytecode;
  assert.throws(() => attestBytecode(input), /CHAIN_CREATION_INVALID_HEX/);
});
