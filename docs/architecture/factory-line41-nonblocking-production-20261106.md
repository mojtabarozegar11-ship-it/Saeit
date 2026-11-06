# Factory line 41: technical completion and commercial release are separate

## Operating decision — 6 November 2026

`1000/1000` is an **aspirational, version-specific professional quality target**,
not a prerequisite for occupying or leaving the private manufacturing line.
It must not be represented as a measured score without real evidence. One
product remains active in manufacturing at any instant.

This change does **not** make an unreleased ZIP saleable or automatically publish
it. Existing signed rights, specialist, editorial, owner and storefront checks
remain the only applicable routes to public/paid distribution.

## Production state machine

1. **Candidate**: source recipe discovered from the installed catalog or a
   previously generated private recipe; source bytes are hashed.
2. **Active build**: a single recipe runs real source tests, reproducible ZIP
   generation and isolated customer-ZIP extraction/tests.
3. **Private engineering completion**: the current source hash, manifest,
   physical ZIP SHA-256 and exact-version customer technical receipt all agree.
   The version is recorded in `technical_exited`. The one active slot is freed.
4. **Professional improvement / rights / commercial review**: persists outside
   the manufacturing slot. `exited` retains historical signed records separately;
   technical completion never updates a commercial clearance or enables sales.
5. **Changed or compromised version**: a changed source or invalid receipt/hash
   causes re-admission and re-testing; a missing old recipe stays in the durable
   waiting queue without monopolizing the executable slot.

Neither technical completion nor a high quality claim is a revenue event.
Storefront publication, payment settlement, fulfilment and measured receipts
must be audited separately before reporting commercial operation.

## Safety and durability

- The VPS cron is the runtime owner; GitHub is not in the per-cycle path.
- One active recipe; unregistered historical queue entries do not block it.
- A private source must have a real README and runnable tests. The runner may
  consume previously generated recipes without enabling speculative generation.
- At least 512 MiB of disk must remain free to start new manufacturing; the
  scheduler reports a **real storage hold**, not a successful build, below this.
- A technical exit never deletes source, prior rework records, ZIPs or receipts.
- A technical exit does not set `professional_quality_approved`,
  `owner_publication_approval`, `public_listing_enabled` or `commerce_enabled`.
- Prior signed clearance records are retained untouched during migration.

## Evidence and rollout gates

Latest confirmed read-only VPS observation before the change: [run 42245415267](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/42245415267),
6 November 2026 at 15:42 UTC. It reported 7,952 completed cycles, 568
consecutive cycles without a new artifact, one active product, 54 waiting,
no signed clearance, and approximately 0.752 GiB free disk. The active
product had passed technical QA; these figures do not prove sales.

Deployment must fail before making changes if the exact VPS runner/cron is not
identified, permissions or symlinks are unsafe, the single-product lock cannot
be acquired, or disk space is below the bounded reserve. Use a byte-verified
backup of the live module, stage the reviewed version, and verify the VPS-local
cycle and private no-publication state after cutover. Do not modify unrelated
services, root cron, cPanel, payments or customer data.

Acceptance means a **fresh** post-install read-only receipt showing a second
distinct private technical ZIP or a precise runtime blocker. No claim of
commercial sales is permitted from CI, package counts or SHA hashes alone.

## Tests

`python3 -m unittest tests.test_factory_vps_product_cycle tests.test_factory_product_rework tests.test_factory_vps_current_health_readonly -q`

This suite covers serialization, quality-gate separation, source changes,
customer-receipt tampering, missing queued recipes, low disk, and non-generating
runner continuation. Passing these isolated checks does not establish live
installation.
