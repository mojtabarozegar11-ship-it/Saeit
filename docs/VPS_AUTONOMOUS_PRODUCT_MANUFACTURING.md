# Saeit VPS — independent, supply-led product manufacturing

## Objective

An always-on VPS production process must create products **before customers order**.
Customer checkout, payment verification, and digital delivery are downstream
commercial processes and cannot be prerequisites to manufacturing.

## What is implemented in source

- scripts/factory_autonomous_portfolio.py: bounded, rotating, read-only audit
  of factory-managed candidates already present in the isolated VPS database.
- product_recipes/farm_enterprise_economics/: first real, working digital
  tool recipe with seven executable tests and a transparent illustrative example.
- scripts/factory_product_maker.py: deterministic, offline, ZIP packaging,
  real QA tests, integrity hashes, repeat-build deduplication and confidential
  internal manufacturing manifests. New product lines are added as versioned
  recipes; a recipe must contain working outputs and runnable QA.
- scripts/factory_vps_product_cycle.py: single no-orders factory pass, with
  a local concurrency lock, evidence dossiers and working product packaging.
- deploy/install_autonomous_factory_products.sh: one-time authorized VPS-only
  installer. It does not touch the existing research factory loop or sites.

## No fabricated results

Production output is genuine runnable source, example inputs, tests and
documentation. The model uses customer-supplied values, not made-up current
farm prices. Passing software QA is **not** evidence of scientific validity,
market demand, suitability for sale, licensing or owner's publication approval.

Until storefront integration is explicitly verified, all outputs remain
PRIVATE_INTERNAL_QA, never public products or paid listings.

## Current deployment status

The earlier one-product research pilot was installed on VPS. This new
product-manufacturing cycle is **source-controlled, but must not be described
as deployed to VPS until a separate installation run explicitly verifies it**.
Standard GitHub CI passing proves code tests only, not VPS installation.

## One-time local installation (authorized service user only)

From an authorized source checkout placed on VPS, run:

    bash deploy/install_autonomous_factory_products.sh

Prerequisites: VPS contains the already verified isolated factory database,
virtualenv, cron and factory-runtime directories. The service user must be
the non-root factory user (normally githubops).

Before installing, verify the source checkout is the intended and reviewed
repository commit. The installer checks locally and fails if prerequisites
are absent.

## Runtime after a successful VPS installation

- Schedule: VPS-local cron at minute 23 of every hour.
- Main loop remains independent, protected by its own existing watchdog.
- All customer orders remain irrelevant to upstream manufacturing.
- No OpenAI, GitHub API or remote marketplace connectivity is used per tick.
- No processing of identical source packages after SHA-256 matches.
- Maximum 25 existing research candidates per cycle.
- Maximum 2 product recipe builds per cycle.
- Product archives, manifests and logs are stored privately in
  /home/githubops/factory-runtime/private/autonomous-product-cycle/
  and /home/githubops/factory-runtime/operations/autonomous-product-cycle.log.
- New products require new approved, versioned recipes or a separate
  evidence-controlled generation engine. The current catalog starts with
  one recipe and does not pretend to support unlimited independent products.

## Health verification

After running the installer on VPS, examine:

    crontab -l | grep SAEIT_AUTONOMOUS_PRODUCTS_V2
    python3 -m json.tool \
      "$HOME/factory-runtime/private/autonomous-product-cycle/production-state.json"
    ls -l \
      "$HOME/factory-runtime/private/autonomous-product-cycle/digital-products/farm_enterprise_economics"

A successful private production cycle reports an artifact and an explicit
false publication status. It is NOT a storefront product until the established
owner/quality and platform-specific release gates pass.

## Rollback

The installer saves a pre-change crontab at
factory-runtime/operations/backups/crontab-before-autonomous-product-<timestamp>.txt.
The original VPS research loop is never replaced. To disable only this add-on,
restore the preserved crontab or remove solely the tagged
SAEIT_AUTONOMOUS_PRODUCTS_V2 entry, after checking for later user changes.

No marketplace credentials or private secrets belong in the public repository.
