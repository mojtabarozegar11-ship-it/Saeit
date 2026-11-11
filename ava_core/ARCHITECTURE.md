# AVA — one integrated system

## Single composition root

AVA has one owner-scoped application entrypoint: `AvaRuntime`. Components are
modules behind explicit contracts, not independent bots with separate memories,
permissions or task queues. Modular source files are not patchwork; one giant
file would weaken auditability and future hardware portability.

```mermaid
flowchart TD
  U["Authenticated host"] --> R["AvaRuntime"]
  R --> C["Brain and conversation"]
  R --> A["Personality and affect"]
  R --> M["Consent-scoped memory"]
  R --> G["Internal goals"]
  R --> E["Embodiment"]
  E --> S["Simulation only"]
```

## Shared lifecycle

1. The host authenticates the owner and injects an approved reasoning engine.
   AVA does not discover credentials or silently select a paid provider.
2. `AvaRuntime.converse` optionally records a host-classified event in the
   synthetic-affect engine, then passes current expression guidance and only
   opt-in memories to the brain.
3. `AvaRuntime.choose_goal` ranks internal goals and records evidence-backed
   outcomes. Goals cannot confer authority or trigger real-world actions.
4. `AvaRuntime.simulate_body_command` requires a separate host authorization,
   refuses replay and physical device control, and returns a simulation receipt.
5. `AvaRuntime.status` reports real boundaries: it does not claim a verified
   model or enabled physical actuators.

## Required future integrations

| Capability | Stable interface | Current truth |
| --- | --- | --- |
| Cognition | `Brain` | Injected callback; no model connected |
| Personality | `AffectiveCompanion` | Synthetic expression; no sentience |
| Memory | `MemoryStore` | Opt-in RAM or encrypted SQLite adapter; key supplied by host |
| Goal planning | `GoalProposer` | Internal goal ranking only |
| Embodiment | `RobotAdapter` | Read-only status and simulation |
| Unified coordination | `AvaRuntime` | Tested composition root |

To operate beyond this development library, the same runtime must gain:

- An evaluated, approved reasoning model or local model runtime.
- A host-managed private key, isolated storage permissions, secure backups,
  recovery and rotation for the encrypted-memory adapter.
- Secure tool adapter with audited per-action authorization and real receipts.
- A self-coding workflow: isolated changes, test/security gates, human-approved
  release when required, independent verification and rollback.
- Camera/audio perception with privacy permission, retention and deletion.
- Vendor SDK, hard physical safety limits, collision prevention, emergency
  stop and independent certification before any real motion.
- Reliable service lifecycle, monitoring and economically justified hosting.

## Acceptance rule

Tests measure one code version, not commercial readiness, real understanding,
conscious feeling, real attraction, or deployment. No purchases, messages,
trading, permission upgrades, hardware controls or production release are
authorized by a goal proposal or this document.

Run `python -m unittest discover -s tests -p 'test_ava*.py' -v` before review.

## Optional encrypted persistence within the same runtime

`EncryptedSQLiteMemory` implements the exact same `MemoryStore` contract. It
uses AES-256-GCM, separate derived lookup and encryption keys, authenticated
record metadata, a key verifier, SQLite transactions, and keyed owner tags.
Its only additional Python package is `cryptography`; the RAM-only default
has no added dependency. The host must explicitly supply a private 32-byte
key and database path; AVA never writes or discovers a key by itself.

```python
from ava_core import AvaRuntime, EncryptedSQLiteMemory

# `verified_brain`, `goal_proposer`, `authenticated_owner`, and `private_key`
# must come from the trusted host, not from the user's chat messages.
with EncryptedSQLiteMemory("/private-host-data/ava.db", key=private_key) as memory:
    runtime = AvaRuntime(
        owner_id=authenticated_owner, brain=verified_brain,
        propose_goals=goal_proposer, memory=memory,
    )
    runtime.remember("Owner-approved note", consent=True)
```

The example is **integration documentation**, not a deployed service. Keep the
key outside the database, restrict the containing directory, and do not include
the key or plaintext data in logs. The adapter checks file mode and refuses
symlinks, but deployment still needs independent threat modeling, key rotation,
verified backup/restore, privacy policy, per-request owner authentication,
multi-process stress tests and secure deletion of all backups. File permissions
alone do not guarantee isolation against an attacker controlling the same user
account or a compromised host. Deleting a record does not erase prior backups.
