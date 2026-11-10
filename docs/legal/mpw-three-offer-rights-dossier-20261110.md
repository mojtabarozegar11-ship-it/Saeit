# MojPlayWin — three-offer authorship and commercial-rights evidence dossier

**As of:** 2026-11-10. **Scope:** SKU 72, SKU 225, SKU 879. **Status:** documentary evidence incomplete for all three. This document is an inventory and clearance workflow, **not** a copyright certificate, signature, legal opinion, proof of ownership, or authorization to receive payment.

## 1. Defined works and historical file references

| SKU | Offer | Historical private filename | Historical expected SHA-256 | Existing reference |
| --- | --- | --- | --- | --- |
| 72 | Chess-improvement PDF | `MojPlayWin_Chess_Grandmaster_Final_Covered_2026.pdf` | `3837fc3cb21ed1a2e7c33e0db8f8e10d158583309b02b97d4d674d25a147207a` | `.github/workflows/mpw-two-books-payment-depth-20261018.yml` |
| 225 | Taniya story PDF | `Taniya_and_the_Little_Baker_Worms.pdf` | `2f6dace4e5bc09ffe5f8d7a677ddff4980fe00de94b7c2ea5b286d1303901d48` | `.github/workflows/mpw-two-books-payment-depth-20261018.yml` |
| 879 | Atelier Interior website ZIP | `atelier-interior-kit-v1-repacked.zip` | `98bffad4ccf36f84c7924ca77e4a8b473b42f33a8fce4d85cefe2367afc097aa` | `catalog/mojplaywin/atelier-interior-kit-v1.json` |

The digests are **historical references**, not fresh hashes of the current commercial download. The current private files have not been acquired or inspected in this dossier. Their presence, byte-for-byte integrity, authorship and legal distribution rights therefore remain unconfirmed here.

## 2. Distinct questions that must not be conflated

1. **Identity of the work:** Verify the actual private download file and its digest against the item sold to customers. A public preview or marketing cover is not necessarily the sold file.
2. **Original authorship and chronology:** Preserve editable manuscripts, creation history, revision timestamps and source projects. A name in PDF metadata, a workflow owner ID or a declared author name is only a claim, not independently authenticated chain of title.
3. **Embedded third-party materials:** Itemize illustrations, cover artwork, photographs, fonts, icons, SVG, templates, software and dependencies; preserve origin and the exact commercial redistribution or resale license of each. An asset being downloadable or AI-assisted does not alone establish commercial permission.
4. **Authority to sell:** Document whether the legal author owns all economic rights, whether the storefront seller is that person or a separate company, and any applicable permission/assignment from author to seller. Record the legal identity and any public pen name or spelling variants without assuming equivalence.
5. **Independent review:** The final reviewer must check the actual work, evidence authenticity, applicable rights and scope, and sign a dated finding referencing the exact file hash. This dossier and its script cannot perform that review or sign on anyone's behalf.

**General copyright context:** In many countries original literary and artistic works acquire copyright without a registration formality; lack of a registration certificate alone does not prove that rights are absent. Conversely, a source repository, hash, catalog entry or author's assertion does not prove a clean chain of title or third-party permissions. Jurisdiction-specific disputes or transfers require qualified review.

## 3. Product-by-product evidence worklist

### SKU 72 — Chess PDF

- [ ] Original editable chess manuscript and dated composition/revision record.
- [ ] Legal author identity and documented link to the displayed name `Mojtaba Roozegar`.
- [ ] Cover art, diagrams, chess fonts, screenshots, other embedded assets: provenance and licenses.
- [ ] Author-to-MojPlayWin seller distribution authority, including commercial digital-download scope.
- [ ] Independent signed review referencing the actual sale-file hash.

### SKU 225 — Taniya PDF

- [ ] Original editable story manuscript and dated revision record.
- [ ] Legal author identity and documented display-name relationship.
- [ ] Each illustration, cover, font and stock/AI-assisted input: provenance and legally sufficient commercial-use license.
- [ ] Author-to-MojPlayWin seller distribution authority.
- [ ] Independent signed review referencing the actual sale-file hash.

### SKU 879 — Atelier Interior ZIP

- [ ] Complete original source and dated build/repack history, plus a reproducible ZIP manifest.
- [ ] Authorship evidence and display-name relationship.
- [ ] Every redistributed image, SVG, font, script, library and dependency inventoried with version, source, license and license conditions.
- [ ] Explicit authority to resell a **client-ready website kit**, including third-party sublicensing restrictions and the proposed one-site-per-client license.
- [ ] Author-to-seller distribution authority and independent signed review of the actual ZIP.
- [ ] Reconcile the historical `preview_only`, `checkout_enabled=false`, `paid_delivery_enabled=false` flags in `catalog/mojplaywin/atelier-interior-kit-v1.json` with the actual live storefront and checkout, without assuming historical metadata is current.

## 4. Blank ownership/permission statement for a human to complete

The following is a form template only. **No declaration has been made or signed.** Do not fill in facts, signatures or license IDs without source documents.

> Legal rights holder: [full legal name and identification reference]  
> Public author / brand name: [name and evidence of alias relationship]  
> Seller legal entity/person: [name, jurisdiction, relationship to rights holder]  
> Product title, SKU and format: [details]  
> Private commercial-delivery filename: [name]  
> SHA-256 independently measured from delivery artifact: [64 hexadecimal characters]  
> Original manuscript/source and dated evidence references: [private references]  
> Embedded third-party materials and licenses: [per-asset evidence / terms / proof of valid acquisition]  
> Scope of rights retained or transferred: [reproduce, distribute, sell digital copies, modify, sublicense, geography, duration, restrictions]  
> Exceptions or disputed components: [details or none with substantiation]  
> Declaration date and authentic rights-holder signature: [unfilled]  
> Independent reviewer, credentials, signature, date and finding: [unfilled]

Keep identity documents and signed source agreements in a private restricted-access location. The register may store **non-secret references** to those records after independent verification, not the documents or personal IDs themselves.

## 5. Source-level gate delivered here

`catalog/mojplaywin/three_offer_rights_register_20261110.json` creates one record per SKU with explicit missing fields. `scripts/mpw_three_offer_rights_evidence_20261110.py` and `tests/test_mpw_three_offer_rights_evidence_20261110.py` provide a read-only offline preflight: exact SKU set, immutable historical reference hash, mandatory independent signed-review slot and rejection of fabricated `approved` status. Even when a reference field is filled, it is **unverified** and the script returns `commercial_sale_legally_cleared_by_this_script=false`.

The code intentionally does **not** change the live storefront, checkout, payment flow, private assets, licensing, pricing, seller accounts, email or production configuration. It also makes no attempt to retrieve confidential materials from uncontrolled sources. No expense or external commitment is authorized.

## 6. Conditions before claiming legal readiness

- [ ] Obtain the original editable materials and full creation history for each product.
- [ ] Prove all cover, illustration, code, font and other embedded third-party redistribution rights.
- [ ] Verify rights-holder identity, seller authority and, where relevant, a signed assignment or distribution permission.
- [ ] Independently hash and visually/sample inspect **the exact** current paid-delivery artifacts.
- [ ] Resolve SKU 879's historical preview-versus-paid discrepancy against live deployment evidence.
- [ ] Obtain an independent signed assessment, with limitations recorded rather than concealed.
- [ ] Separately pass security, delivery, consumer information, refund and payment-readiness checks before any commercial release claim.

**Outcome of this pass:** 3/3 SKUs inventoried; 0/3 products have independently authenticated documentary rights clearance in the evidence available to this audit. This means **not proven cleared**, not that infringement has been established. No paid commercialization or deployment is approved by this dossier.
