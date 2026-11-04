# F-01: trusted public-key enrollment and independently signed product exit

Status: **ADMINISTRATIVE ONBOARDING REQUIRED — NOT ACTIVE**. This is an operational procedure, not evidence that any reviewer has approved any product. No one may invent reviewers, substitute an automated signature for independent judgment, or mark a legacy order complete to unlock the next SKU.

## Exact roles and production trust roots

| Role | Required verification root | Source of private-key control |
|---|---|---|
| Domain specialist | `/etc/saeit/factory-quality-reviewer-public-keys/domain_specialist.pem` | Real domain specialist, separate from factory |
| Independent quality auditor | `/etc/saeit/factory-quality-reviewer-public-keys/independent_quality_auditor.pem` | Independent auditor, separate from factory |
| Rights reviewer | `/etc/saeit/factory-quality-reviewer-public-keys/rights_reviewer.pem` | Actual qualified rights reviewer, separate from factory |
| Cycle receiver | `/etc/saeit/hourly-cycle-receiver-public-keys/<cycle>.pem` where cycle is exactly one of `R-01`, `B-01`, `S-01`, `G-01` | Actual authorized recipient (at least one cycle for a given release) |

The running production user `githubops` must not have write permission to either trust directory or its files. The corresponding private keys must remain on the named signers' own devices or independently managed signing systems; **never** check them into Git, copy them to the factory, or transmit them through an Action log.

## Administrative enrollment checklist (per person)

1. A human server administrator verifies the signer's real legal identity and current role through an independent channel. Record the verification method, verifier, date, and an internal reference in a restricted administrative record. Do not put identity documents, addresses or private credentials in GitHub.
2. The signer generates and retains a private key on a device under their own control and supplies **only** a PEM-encoded public key. Existing `openssl dgst -sha256 -verify` checks require a compatible signing key (for example, RSA 3072-bit).
3. The administrator issues a **unique, random, short-lived challenge** bound to this repository, the named role, key fingerprint, signer identity record, and enrollment timestamp. The signer signs the exact challenge file using their own private key, returning only the detached signature.
4. The administrator verifies the signature with `openssl dgst -sha256 -verify role.pem -signature challenge.sig challenge.txt`, and independently contacts the verified individual to confirm intent. Reject an expired challenge, duplicate key across nominally independent roles, key mismatch, or any unverified identity.
5. From a privileged server session, verify `/etc/saeit` and trust-root parent directories are not symlinks and have safe ownership. Install only the accepted **public** key atomically as a root-owned regular file with no group/other write bits. The applicable trust directory is root-owned and not group/other writable; give the runtime user read access only if needed. Before replacement, retain a restricted rollback copy and a non-secret audit record.
6. Maintain a root-controlled mapping for each role containing identity verification reference, the PEM's SHA-256 fingerprint, activation date, expiration or rotation date, and revocation status. The current verifier checks the fixed role PEM filename and detached signature, **not the real-world identity record**; administrators are responsible for real-world verification until a separate identity-binding gate is reviewed and deployed.
7. For a replacement/revocation: block new releases, remove or rotate the affected trust entry under administrative change control, re-verify all remaining distinct identities and fingerprints, and require fresh independent signatures for release as necessary.

No fabricated signature, ChatGPT-generated private key, empty file, fake signer name, self-approved quality score, or certificate issued by the factory is acceptable evidence.

## Production acceptance (different from key enrollment)

1. The actual expert reviewers evaluate the exact product build and sign **the same original, unmodified** `quality-excellence/signed-clearances/<recipe>/current.json` as separate `domain_specialist.sig`, `independent_quality_auditor.sig`, and `rights_reviewer.sig` files, each created by the corresponding real reviewer.
2. The clearance must give an actual justified score of 1000/1000 and bind to the artifact hash. Source `scripts/factory_vps_product_cycle.py` verifies these detached signatures using the trusted public keys.
3. A real receiving owner must verify the exact delivered product and sign the original `product-lifecycle/hourly-cycle-handoffs/<cycle>/<order>/receipt.json` as `receipt.sig`, including `accepted_by_receiver`, evidence and the exact delivered SHA-256. The serial controller rejects missing/unmatched delivery.
4. Only after both independently signed quality clearance **and** authentic product acceptance may the line release its active product and admit the next. Incomplete legacy AGRI200 work cannot be re-labeled complete for convenience.

## Fail-closed activation constraints found on 2026-11-04

- Live read-only run #10: legacy AGRI200 reports `all_complete=false` and an active order; line41 has one active recipe; global reservation owner is unverified.
- The `githubops` SSH account cannot read the root crontab using noninteractive sudo; this means global scheduler coverage and exclusive ownership are **not proved**.
- Read-only run #11 additionally inventories public-key directory and role-file posture without publishing signer names or keys.
- Production must remain off while any competing producer, unverified scheduler, unsafe key directory, unverified real signer or missing evidence leaves a gap. Preserve old state and backups. A future legacy-lane parking procedure must be explicit, reversible, independently reviewed, and must never equate 'parked' with 'completed'.

## Owner/admin handoff: prerequisites still needed

A legitimate administrative actor with sufficient VPS rights, independently identified domain specialist, quality auditor, rights reviewer, and at least one designated receiver; each person's verified public key and proof-of-possession, plus an approved global scheduler inventory. Until those exist, the factory can safely be audited and its one existing product improved, but it cannot truthfully issue a signed independent-quality exit.
