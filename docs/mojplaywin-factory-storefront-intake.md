# MojPlayWin — card-driven factory-to-storefront plan

Scope: **main mojplaywin.com only**. Sub-sites, Zomorod Melal, payment
providers, hosting, current live database and other tenants are untouched.

## Purpose
The storefront is the *verified, saleable output* of the factory. Existing
activity cards are a source of possible buyer problems and production briefs,
**not** actual demand, purchases, manufacturing authorization, or inventory.

## Phase 1 — implemented as a read-only code preview
- Data comes directly from the main site's \`VENTURES\`, \`SECTIONS\` and
  \`FEATURES\` objects in \`core/mojplaywin_views.py\`.
- 24 curated internal production proposals are linked to the three cards in
  each of eight business venture areas.
- Wider section and feature cards appear as \`needs_scoping\` signals.
- Identifiers are stable; unreviewed venture additions or changed card
  counts fail closed, without creating products.
- All prices are null; rights, identity, quality and actual demand are
  unverified; checkout and public publication are strictly disabled.
- No new DB table, customer order, agent task, cron entry, deployment,
  migration, payment, or external operation is performed.

Preview after checking out this branch into a correctly configured Django
environment:

\`\`\`bash
python manage.py mojplaywin_production_intake --summary
python manage.py mojplaywin_production_intake
python manage.py test core.tests.test_mojplaywin_production_intake
\`\`\`

The output is an auditable *candidate manifest*, not a shipping product.

## Next implementation gates (not implemented in phase 1)
1. Confirm owner identity, rights, target audience and delivery constraints
   for every candidate. Discard products without demonstrated buyer value.
2. Collect actual opt-in requests, analytics, or other genuine demand
   signals (privacy-first and without fabricated purchase/order counts).
3. Create a separate idempotent **manufacturing order** model/state machine:
   \`proposed -> scoped -> approved -> queued -> in_production ->
   qa_review -> releasable -> listed\`. Keep customer \`Order\` separate.
   Enforce one scoped order per unique source + product recipe/version.
4. Transfer only approved bounded job specifications to the VPS factory,
   with owner authorization, retry limits, cost budgets and audit trails.
5. Require authentic artifacts, license/IP proof, usability checks, exact
   file checksum, product pages, entitlement and testable checkout.
6. Create/update Django \`Product\` in inactive draft status and publish
   *only* on the existing owner-approval gate once payments and downloads
   have independently passed live end-to-end tests.
7. Show actual metrics in management: sourced cards, approved briefs,
   running jobs, QA pass/fail, published products and verified sales.

Do not conflate the 88 existing VPS factory records with the new MojPlayWin
card-derived proposals; reconcile ownership and provenance before linking
or deduplicating them.

## Highest-feasibility starting briefs (hypotheses, not market validation)
- Digital Product Delivery Test Kit
- Accessible Storefront Audit Toolkit
- Menu Costing & Stock Calculator
- Farm Cost & Margin Planner
- Post-Purchase Customer Journey Kit

All products require verified original value, rights and practical QA
before appearing as buyable stock. The existing static MojPlayWin store
is not automatically replaced in this read-only phase.
