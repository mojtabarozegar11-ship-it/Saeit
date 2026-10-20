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

Until an agreement is validly executed and authority verified, `valid_execution_and_authority_evidence_verified=false` and `company_operational_permission.executed_agreement_verified=false`. A draft file, Git commit, successful CI, successful VPS backfill or owner statement is **not** proof of execution. Person and company are distinct parties, even if represented by one individual. Required corporate authorization must be checked before dual-capacity signing.

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
