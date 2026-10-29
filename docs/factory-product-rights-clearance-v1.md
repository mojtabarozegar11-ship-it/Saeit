# Artifact-bound product rights clearance

This gate applies to new factory public releases, including free previews, and to native factory store listings. It is independent of the QC1000 quality certificate. An artifact cannot pass because a manifest contains a boolean such as `rights_cleared`.

## Private evidence layout

For recipe `<recipe>` and exact ZIP SHA-256 `<sha256>`, keep these files in the private factory inbox (never in the public repository):

- `rights-clearance/<recipe>/<sha256>/rights-manifest.json`
- `rights-clearance/<recipe>/<sha256>/signed-clearance.json`
- `rights-evidence/<document-sha256>.pdf` for every cited contract, license, or permission document
- `quality-trust/trusted-reviewers.json`, rooted in the operator-pinned `FACTORY_QA_TRUST_ROOT_SHA256`

The manifest records the recipe, exact ZIP digest, distribution territory and term, public and commercial distribution scope, and one component record for every regular file in the ZIP. Each component record binds its path, SHA-256, size, rights holder, basis, and one or more source-document hashes. Evidence files are re-hashed from disk. The inventory must exactly equal the ZIP contents.

The signed decision has schema `saeit.factory.product-rights-clearance.v1`. Its canonical JSON decision object binds the recipe, ZIP SHA-256, canonical manifest SHA-256, `approved_for_public_distribution`, and commercial-distribution scope. The approvals must include two distinct signatures: an identity-verified `rights_reviewer` and the `owner`. The rights reviewer entry in the root-pinned trust registry must also carry a validated legal-qualification evidence hash, and the matching private PDF must be present and hash-correct. The existing pinned reviewer registry and Ed25519 verifier are used; owner delegates cannot sign for either role.

## What the gate establishes

The gate establishes byte integrity, evidence-file presence, component coverage, scope binding, and valid signatures from keys in the configured trust registry. It does not decide whether a contract is authentic, whether a signer had legal authority, or whether a rights grant is legally sufficient. Those are human legal-review decisions recorded by the accountable signers. Missing or uncertain evidence keeps the release blocked.

Free public previews require public-distribution clearance. Commercial store listing additionally requires explicit commercial-distribution scope. QC certification remains an independent gate.
