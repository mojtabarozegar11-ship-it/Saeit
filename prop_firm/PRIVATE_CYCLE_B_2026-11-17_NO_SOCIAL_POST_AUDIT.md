# Private operational ledger — Cycle B — 2026-11-17

Scope: MOJ-PROP-01 real two-stage trader evaluation; NOT MOJPROP-STARTER30 education.
Repository source branch: feature/prop-firm-policy-v11-20261114; canonical PR #2310 (draft, not deployed).

## Owner change superseding the historical v1.2 buyer-post condition

The buyer does **not** have to create, publish, send, submit, upload, retain, or link Instagram/Facebook posts. No missing social content may be used to fail evaluation, deny a fair refund, or deny otherwise eligible funded profit. The immutable historical 2026-11-15/v1.2 information packet is preserved as evidence, while the prospective 2026-11-17/no-social-post-waiver-v1 information copy expressly supersedes its two-post clause. Existing executed buyer contracts, if any, need individual review and a properly communicated amendment; the source-only waiver cannot silently rewrite a signed agreement.

## Changes implemented this cycle

1. Created versioned buyer no-post waiver module.
2. Kept historical FA/EN disclosure unchanged.
3. Linked waiver to historical disclosure digest.
4. Recomputed digest from historical canonical fields.
5. Fail-closed on digest mismatch.
6. Fail-closed if historical post clause differs.
7. Required zero Instagram posts.
8. Required zero Facebook posts.
9. Removed buyer post-link requirement.
10. Removed buyer media-upload requirement.
11. Removed posting as an evaluation-pass condition.
12. Removed posting as a funded-profit condition.
13. Removed posting as a fair-refund condition.
14. Disallowed inferred marketing consent.
15. Continued exclusion of owner's private social accounts.
16. Kept signed-contract evidence independently required.
17. Kept payable invoice disabled in amendment.
18. Kept paid enrollment disabled in amendment.
19. Derived current FA buyer information without historical mandatory post clause.
20. Derived current EN buyer information without historical mandatory post clause.
21. Preserved 30 native TRX / 30,000,000 SUN.
22. Preserved two simulated phases, 28-day deadline, 50 positions and six days per phase.
23. Preserved conditional USD 100 real account and 70/30 eligible real profit.
24. Corrected B pre-purchase disclosures.
25. Added 45 isolated regression methods.
26. Added CI step for these regressions.
27. Added CI trigger paths for new module/tests.
28. Corrected newline matching in immutable historical text substitution.
29. Strengthened verification of exact historical social clause.
30. Logged remaining legal and runtime gates here.

## Important remaining blockers (do not claim ready for sale)

- The historical Plan 1 `plans.py` and `buyer_order_review.py` still contain `social_posts_per_platform=1`, and the existing qualification engine still enforces two posts. This is a known **runtime contradiction**: the amendment is NOT yet end-to-end enforced. Do not deploy or accept payment under contradictory terms.
- The 20-gate B evidence schema still contains social-policy review and advertising consent fields. These must be redesigned as voluntary marketing with no buyer challenge prerequisite, and the signed-contract version must be reissued before payable order enablement.
- The signed buyer contract, KYC/country eligibility, legal clearance, genuine funding reserve, broker execution, refund handling, independent payment proof, and production deployment have not been independently demonstrated by this cycle.
- PropInterest is consent-only. A received email is not KYC, a contract, an invoice, payment, enrollment, or marketing permission.
- This cycle did not send email, charge TRX, deploy, or create a customer enrollment. CI outcomes have not been independently verified after these new commits.

## Next owner-B work

Resolve versioned contract conflict in B's signed private review packet and consent form, bind only independently verified evidence from canonical PropInterest, and coordinate runtime qualification correction with A before any sale. Preserve history and ensure an amendment is accepted explicitly rather than overwriting an earlier signed contract.
