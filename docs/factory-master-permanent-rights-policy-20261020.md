# Zomorod Melal — permanent master rights framework (owner-authorized technical policy)

Framework ID: `ZOMOROD-MASTER-PERSONAL-RIGHTS-20261020`
Version: 1.0
Effective status: owner-authorized **technical scope**, not a signed/executed agreement or independent ownership verification.

## Standing scope, not a finite product list

The master document is **not limited to 68 products**, a fixed inventory, a production cycle, or a future product count. It is intended to cover **all present and future eligible outputs** of the Zomorod Melal factory, including new categories, research, text, software, games, media, and later versions. A new master framework is not required merely because a product is newly generated. The standing policy has no contractually scheduled expiry date, subject to valid termination and mandatory applicable law; it does not extend the statutory term of any intellectual-property right.

## Person, company, and title boundaries

- The owner **declares** personal economic-rights ownership in applicable products under the professional identity “مجتبی روزگار”. Legal identity for signatures/commerce must be authenticated from formal documents.
- The company “شرکت کشت و صنعت زمرد ملل” is described as the **operational and commercial platform**, not the automatic assignee of the owner's economic rights.
- Neither unilateral owner declaration nor machine-generated passports extinguishes employee, subcontractor, collaborator, open-source, stock asset, music, AI service or other third-party rights.
- A rights title or license not actually owned/acquired cannot be conferred by this framework. Authorship / moral-rights attribution stays subject to applicable law.

## Contract and authorization status

The owner specifically attested on 21 October 2026 that the **historical master agreement was executed in 1398**, in both capacities (natural-person economic-rights holder and authorized company signatory), and that the agreement bears the company seal. The owner also affirmed that the 1405 typed reconstruction contains the same terms as the signed 1398 agreement. **Record this as an existing owner-attested execution; never request that the owner re-sign it merely because the technical evidence gate remains false.** See `docs/legal/factory-natural-legal-identity-owner-signer-20261021-fa.md` and its recorded version hash. This attestation does not itself independently authenticate the historical signature, legal signing authority, third-party component rights, or a later product revision. Accordingly, until independent agreement/authority evidence is verified, `valid_execution_and_authority_evidence_verified=false` and `company_operational_permission.executed_agreement_verified=false` mean **independent verification is outstanding**, not that the owner denied signing or that the agreement did not exist. A Git commit, successful CI or VPS backfill does not cure that evidence gap. Person and company remain distinct legal parties even when represented by one individual.

## Owner-attested 1398 founding documents — 2026 text is separate

The user supplied a company memorandum, articles of association, company registration screenshots and confirmed that the **historical foundational company documents were signed in 1398**. This is recorded as an **owner attestation**, not an inspection of actual signatures or official registry certification. The user is not required to upload a signature image.

- Declared registration: company "شرکت کشت و صنعت زمرد ملل", *با مسئولیت محدود*, national ID `14008746024`, registration number `3110`, registration date `1398/08/16`, Marvdasht, Fars. Evidence source is supplied documents/screenshots; official registry independently checked = **false**.
- The newer master rights text was drafted/reconstructed in 1405; its newly added clauses may **not** be described as signed in 1398 just because historical company documents were signed then.
- The company and web storefront are a **technical/commercial sales-services platform**, not the automatic owner of product IP or automatically the merchant-of-record. The individual is the declared seller; exact legal name, gateway acceptance, settlement and invoicing require specific verification before taking payment.
- Keep existing v4 product passports immutable. Add an independent private, read-only-once corporate-context v1 sidecar per exact artifact revision; status remains declaration-only, commercial release remains false.
- Do not push scans, private addresses, signatures or confidential contracts into GitHub.

## Permanent policy vs. per-product evidence

The master framework remains standing and is not re-signed per product. Product-specific provenance is still necessary for reliable third-party and customer clearance:

- Source identity, artifact SHA-256 and actual contributing parties / subcontractor assignments
- Third-party license terms for code, images, audio, fonts, models, datasets and other components
- Quality review, legal seller identity, payment compliance and explicit owner publication authorization

These are **evidence records**, not new master contracts.

## Engineering requirements / fail-closed gates

- Private, source-bound, write-once versioned passport sidecars; never overwrite historical v2/v3 receipts.
- New v4 fields: `master_framework` with an indefinite-but-law-subordinate standing scope, `product_count_cap=null` and `requires_new_master_contract_for_each_product=false`.
- Every v4 passport must retain `commercial_release_allowed=false`, `third_party_rights_cleared=false`, and `executed_agreement_verified=false` until separate evidence-based verification through a deliberately authorized release process.
- Existing sales, products, payment routes and public pages must not be enabled by a mere policy update.
- No public listing, price or checkout change is part of this rollout.
- Do not publish full confidential contract, account information, identity numbers or signatures to this public GitHub repository.

## Acceptance criteria

1. A newly built eligible product inherits the same framework ID and no count/date cap.
2. Source hash or archive mismatch fails closed.
3. Preexisting v2/v3 sidecars remain untouched and v4 is separate.
4. Hundreds of simulated future product IDs are allowed by master scope, without signing or commerce authorization being fabricated.
5. If deployed to VPS, verify an actual private v4 inventory readback and record the GitHub Actions run URL. An Actions success alone does not establish rights clearance or sale readiness.

This is a policy specification and implementation record, **not** a substituted signature, binding legal advice, or legal transfer of IP title.
