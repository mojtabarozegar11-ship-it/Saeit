# C06 — Real execution contract for five hourly production lanes

**Owner:** Zomorod Melal / MojPlayWin. **Engine:** mojtaba.bot.ai.
**Hard target:** for each actual hourly run, A=50, B=50, C=50, D=50,
E=50 independent completed acts; 250 total per hourly round.

This is an *implementation* contract, not a claim that 250 commercial
acts were delivered. The five saved ChatGPT schedules and the 96 legacy
`delivery_pending` rows do not constitute executable authoring jobs.

## The missing component addressed by C06

`deploy/mojtaba_bot_cycle_worker.py` previously accepted only already
committed source changes and read-only observations. C06 adds
`deploy/mojtaba_bot_cycle_batch_executor.py`: a locally usable actor
that applies **already authored substantive outputs**, validates each
target and provenance, creates five Git commits for up to fifty changes,
then commits one manifest and submits all receipts to the central
evidence ledger.

It does NOT create credible scholarly text or gameplay logic from an
empty queue, independently assess economic/medical/legal claims, send
mail, push to GitHub, deploy to VPS, trade, charge customers or book
revenue. The domain-specific authoring steps remain necessary.

## Exact payload from each domain producer

One versioned JSON array per *single run*, containing 1 to 50 fully
authored changes. There is **no placeholder/queue-only mode** that
increments success. Example (illustrative, not an executable product):

```json
[
  {
    "action_id": "B-UNIQUE-EXECUTION-ITEM-001",
    "path": "deliverables/research/unique-study/methods.md",
    "kind": "deliverable_created",
    "content": "# Full original manuscript ...",
    "before": "Evidence-based condition before authoring",
    "change": "One genuine complete amendment or deliverable",
    "after": "Independently observed result after authoring",
    "expected_sha256": null,
    "source_paths": ["editorial/agricultural-economics-2026/climate-risk-farm-panel-econometrics.md"]
  }
]
```

The `content` in this example is intentionally incomplete; it MUST
be replaced by a substantive final draft before submission. A
`source_change` replacing a tracked file uses its exact pre-change
SHA-256 in `expected_sha256`. A new file uses `null`. Do not claim
a completed book if only one chapter is written, or a sold product if
only a calculator is patched.

### Lane ownership and allowed artifact paths

| Lane | Owned work | Allowed changed paths |
|---|---|---|
| A | Books, authorized written instructional products and MojPlayWin writing | `deliverables/books/`, `deliverables/mojplaywin/` |
| B | Peer-reviewable research materials and editorial deliverables | `deliverables/research/` |
| C | Games, gameplay code, graphics-source specs and token design code | `games/` |
| D | Economic calculators, independent services and digital products | `product_recipes/`, `deliverables/products/` |
| E | mojtaba.bot.ai orchestration and management artifacts | `deploy/mojtaba_bot_*`, `deliverables/command/` |

For other repositories (e.g. private Moj Coin/Bazei), a separate
private, authorized workspace and evidence adapter is needed. Never
mirror private source into public Saeit to fill a quota.

## Operation in an authorized and clean local work/ checkout

**1. Preflight and validate only:**

```sh
python3 deploy/mojtaba_bot_cycle_batch_executor.py \
  --cycle B \
  --jobs /secure/created-by-B/not-published/jobs.json \
  --run-id B-20261112T1410Z \
  --expected-branch work/unified-master-c02-evidence-gates-20261112 \
  --state /secure/central/mojtaba-cycle-ledger.json
```

This makes NO source changes, commits, pushes, deployments or receipt
successes; only validates preconditions.

**2. After reviewing content for rights, privacy and actual quality,
commit locally:**

```sh
python3 deploy/mojtaba_bot_cycle_batch_executor.py \
  --cycle B \
  --jobs /secure/created-by-B/not-published/jobs.json \
  --run-id B-20261112T1410Z \
  --expected-branch work/unified-master-c02-evidence-gates-20261112 \
  --state /secure/central/mojtaba-cycle-ledger.json \
  --commit-local
```

Only the currently checked-out `work/` branch is mutated, never main.
The script creates up to five groups of ten independently changed files,
five artifact commits, and one evidence manifest. Syntax checks are
necessary but NOT proof of scholarly review or product readiness.

**3. If interrupted after any complete 10-action commit**, call the
same command using unchanged `--run-id` and exact same job set with
`--resume`. The engine finds its own prior batch commits by exact
run identity, checks real file bytes against their immutable Git proof,
and continues with the next uncommitted group. It does not replay
previously committed batches. If a batch was only partially written or
another process changed the checkout, the run blocks rather than
overwriting concurrent work.

**4. Transfer/ingest:** the executor does not automatically push its
local commits. GitHub transport and persistent worker availability
must be confirmed separately. A GitHub connector can instead author
each finished batch using `create_tree`, `create_commit` and
`update_ref` on the approved work branch, then submit the same strict
C03 receipt manifest. Either mode requires immutable source evidence.

## What 50/50 means

To count **one** action: a distinct useful deliverable/source revision,
specific before and after, a nonrepeated path/content identity, a
committed Git SHA and file SHA-256, an independent QC readback, and
the central receipt gate's acceptance. Fifty operations on one file,
fifty audits, fifty copied documents, and fifty tasks listed in a
queue do not count as 50 value-creating deliveries.

A complete commercial order additionally requires independently
verified legal offer/contract, customer acceptance, authorized payment
and delivery. C06's engineering receipts **do not provide those proofs**.

If fewer than fifty real jobs are available, output the verified
numerator, use independently eligible work from other priorities of
the same lane, and report the exact shortfall. Never fabricate output,
circumvent approval, publish private documents, or claim income.

## Operational readiness still unverified

The hourly automations are enabled, but there is **no evidence yet**
of a persistent VPS job producer with fifty actual authored payloads
per lane per hour, no authenticated operating deployment for this
batch executor, and no verified end-to-end production transfer.
Passing the disposable 50-file QA proves software capacity ONLY.

**Financial/security rules:** no paid API calls, expenses, external
emails, tickets, live trades, unapproved publication, production
deployment or irreversible deletion. Remote Desktop Commander
and retired PICM are excluded.
