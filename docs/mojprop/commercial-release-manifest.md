# MOJ PROP commercial release manifest

Status: internal evidence protocol; not a payment switch and not legal advice.

The manifest makes every commercial gate traceable to a review reference and
review timestamp. A passing source test or a completed manifest does not itself
enable a route, create an invoice, accept TRX, settle funds, or authorize a
broker action.

## Required record

Each of the ten gates from the readiness evaluator must have:

- a boolean status;
- a non-secret evidence reference when complete;
- a review timestamp when complete.

The reference should point to a private ledger entry, approved policy document,
test artifact, provider verification record, or owner decision record. Secrets,
wallet keys, customer data and credentials must never be stored in the manifest.

## Fail-closed rules

The manifest is rejected when:

- a required gate is missing;
- an unknown gate is supplied;
- a status is not an actual boolean;
- a completed gate lacks a reference or review timestamp.

Even with all ten gates evidenced, the result remains closed unless the public
route and payment controls are separately and explicitly true. The module only
returns a report; it has no runtime mutation path.

## Current release boundary

For the current English MOJ PROP release:

- the information route may be publicly visible;
- the public paid checkout remains closed;
- invoice creation and settlement remain disabled;
- the independent database migration remains unauthorized;
- revenue must be evidenced by a real settled transaction, not by code or page availability.
