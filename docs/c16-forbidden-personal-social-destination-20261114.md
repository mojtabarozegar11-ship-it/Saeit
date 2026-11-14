# C16 permanent outbound destination exclusion — 2026-11-14

The owner explicitly forbids posts to the page/account identified as
`Dr.mojtaba.rozegar` (all connected networks and posting routes). This
is a **destination-level prohibition**. It is not lifted by an approved
campaign, a generic "owner has delegated decisions" setting, service marketing,
a source-code deployment, a changed provider, or a scheduled task.

Resolved live identifiers from the connected provider, used **only as
destination-denial IDs**:
- handle: `dr.mojtaba.rozegar`
- Metricool brand ID: `7317306`
- connected Facebook Page ID: `102203064721826`

## Real containment carried out in Metricool

Exactly six previously prepared Facebook publications on this connected brand
were edited (not deleted) to `draft=true` and `autoPublish=false`. A second
read returned 6/6 with these flags and 0/6 with automatic publishing enabled.
The provider still surfaced `PENDING` metadata, which MUST NOT be interpreted
as an external published post. The installed Metricool integration exposed no
delete action. Do not reactivate these drafts.

## Required programmatic controls

1. Deny an exact or embedded forbidden destination, public URL, page ID, brand
   ID or provider alias **before any credential fetch, queue claim or outbound
   HTTP request**.
2. Protect both the integrated `social_hub` provider adapters/worker and the
   older `scripts/mojtaba_direct_social_publisher_20261026.py` route.
3. Approved historical jobs do not override this rule; fail closed instead of
   retrying, re-scheduling, renaming or selecting another social network.
4. Never route company service advertisements through the forbidden account.
   The existing company-owned website and specifically authenticated,
   permitted company channels are distinct; do not infer that a company-owned
   social publisher is connected when the connected brand is personal.
5. No new marketing spend, payment, email, SMS, account connection or external
   publication without the applicable approvals and permitted destination.

## Evidence and limits

The six draft/autoPublish controls were read directly from the connected
Metricool account. The code-level controls are source-only until reviewed and
deployed through the existing single-bot operational path. This file does not
claim that a provider deleted the drafts or that a posted item was removed.
It does not create a parallel robot or separate posting automation.

Return to commercial priorities: six existing public professional service
scope URLs, correct `/services/` navigation, a legitimate consented inquiry
pipeline and actual verified customer cash settlement.
