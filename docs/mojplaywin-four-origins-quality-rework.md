# MojPlayWin factory — four-origin intake and non-discarding QA rework

Scope remains **mojplaywin.com main site only**. This is a code-reviewed
predeployment change; no cPanel or VPS production data is changed by this PR.

## Four distinct production demand/origin sources

| origin_type | Source | Source evidence |
|---|---|---|
| site | Site topic, activities and cards | Actual main-site source card (24 reviewed proposals; other cards as unscoped signals) |
| customer | Genuine customer manufacturing request | Unique request ID and documented requirements; never confuse with paid customer \`Order\` |
| market | Independent market demand | Verifiable research reference, market problem and report (not invented purchase numbers) |
| invention | Factory-originated innovation and R&D | Unique internal experiment/idea reference and objective; not dependent on external orders |

Manual customer, market and invention briefs can be registered by an
authorized MojPlayWin main-site superuser. There is no artificial requirement
that the factory receive a customer order before it may design or experiment.

Every entry is an **internal manufacturing brief**. It cannot initiate
payment, produce customer orders, invoke the VPS runtime or sell a product.

## Rework instead of discard

1. Finished *candidate* artifact is submitted for QA **with a traceable
   artifact reference** by a human operator; this does not assert a real
   factory shipment absent proof.
2. An inspector records an immutable revision-specific verdict with an
   idempotency key and review notes.
3. If QA **fails**, at least one structured defect is **mandatory**:
   defect code, severity, root cause, expected result, actual result,
   and exact correction plan.
4. Each failure automatically creates a durable correction/rework ticket and
   updates the manufacturing brief to \`rework_required\`. The product record,
   failed revision, defect details and full history are preserved.
5. The remediation operator claims the ticket, records a substantive
   correction-evidence note for **every** defect, and submits a new artifact
   reference different from the failed revision.
6. Product goes back into \`qa_review\` and must receive a **new independent
   QA result**. A failed QC test is never silently changed into a pass.
7. When failure recurs three times, mark \`attention_required\` and route
   to a responsible expert owner, rather than deleting/discarding it or
   running endless uncontrolled retries. The work can be resumed.
8. A passed QA verdict means only \`qa_passed\`, not a releasable storefront
   item. Owner rights, tested delivery, commercial permissions and customer
   value are separate release gates.

**No quality failure can create a \`rejected\` manufacturing order or delete
a product.** Separately, preproduction duplicate, illegal, unsafe or
technically impossible proposals may be deferred, with history preserved;
there is never an obligation to sell an unsafe/noncompliant product.

## Components staged in PR

- Django schema extension and reversible \`0041\` migration.
- \`core/mojplaywin_quality_loop.py\` operations for four-origin registration,
  inspection, diagnosis, repair and independent retest.
- Host-isolated Django admin lists for all production briefs, inspections,
  defect root causes and rework tickets.
- Regression tests for all origins, idempotence, quality errors and expert
  escalation after repeated failures.

The admin currently **displays** the QA/rework history as read-only.
Production and correction operations in the application service still need
the separate authenticated UI and secure VPS dispatch adapter; their
availability in source code is not proof of deployed operations.

## Safe validation

\`\`\`bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core.tests.test_mojplaywin_four_origins_qa
python manage.py test core.tests.test_mojplaywin_production_bank core.tests.test_mojplaywin_production_intake
\`\`\`

Do **not** migrate or seed on an unverified production database. Do not use
the empty SQLite environment previously observed on another site.
