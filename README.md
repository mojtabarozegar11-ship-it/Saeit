# SAEIT — AI-Native Deep Research Platform

Production-oriented Django foundation for the research, knowledge, data, agent orchestration, approval, audit, and revenue platform defined in the master architecture.

Repository scope: this project only.


## Official public websites

These are external public-facing websites associated with the broader work; their availability, commercial checkout and deployments are verified separately from this source repository.

- **MojPlayWin — international digital store:** [Storefront](https://mojplaywin.com/store/?utm_source=github&utm_medium=referral&utm_campaign=saeit_official_sites_20261024) · [Chess improvement digital book (US $7.50)](https://mojplaywin.com/store/product/72/?utm_source=github&utm_medium=referral&utm_campaign=saeit_official_sites_20261024&utm_content=chess) · [Taniya illustrated digital book (US $4.00)](https://mojplaywin.com/store/product/225/?utm_source=github&utm_medium=referral&utm_campaign=saeit_official_sites_20261024&utm_content=taniya) · [Atelier Interior website kit (US $6.80)](https://mojplaywin.com/store/product/879/?utm_source=github&utm_medium=referral&utm_campaign=saeit_official_sites_20261024&utm_content=atelier). Prices are the listed prices verified on 24 October 2026; checkout requires an account and an order-specific TRX invoice, and file access follows independently confirmed payment. This is not a claim that a complete paid purchase was tested.
- **Zomorod Melal — Iranian agricultural research and industry:** [Official Persian website](https://zomorodmelal.ir/?utm_source=github&utm_medium=referral&utm_campaign=saeit_official_sites_20261024) · [Public research-project register](https://zomorodmelal.ir/research/projects/?utm_source=github&utm_medium=referral&utm_campaign=saeit_official_sites_20261024). The register currently lists no independently approved public project records.
- **Mojtaba Roozegar — independent professional and research profile:** [Public profile](https://mojplaywin.com/mojtaba.roozegar/resume/?utm_source=github&utm_medium=referral&utm_campaign=saeit_official_sites_20261024). Owner-reported credentials are distinguished from independently verified publications.

## Free public learning and research guides

Original educational notes, with current official product and company links. These are public resources, not claims of independently verified sales, journal publications or production deployments.

- [Chess: an 84-day measurable study companion](docs/marketing/chess-84-day-study-companion-20261024.md) — decision logs, critical-position review and progress measurement.
- [Taniya: read-aloud and early-years activity guide](docs/marketing/taniya-read-aloud-activity-guide-20261024.md) — rhythm, story sequencing and family activities.
- [Atelier Interior: a client website launch checklist](docs/marketing/atelier-interior-website-launch-checklist-20261024.md) — licensing, accessibility, SEO and reliable contact forms.
- [راهنمای محاسبه علمی مقدار بذر گندم](docs/marketing/fa-wheat-seed-rate-field-guide-20261024.md) — محاسبه بذر، مفروضات، واحدها و تحلیل حساسیت.
- [Research collaboration: evidence and deliverables](docs/marketing/mojtaba-roozegar-research-collaboration-brief-20261024.md) — a transparent framework for scientific and enterprise discussions.

## Runtime safety

The execution path is governed by capability, risk, owner-approval, execution-identity, retry-budget, and audit controls. Production-changing or other sensitive actions must pass the approval gate before execution.

## Production checks

Run the read-only readiness gate before deployment:

```bash
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py production_gate
```

The production gate fails closed when required production settings, database connectivity, migrations, or runtime health checks are not satisfied.

## Stale-task recovery

A bounded recovery pass is available for a host scheduler/cron:

```bash
python manage.py recover_stale_tasks --limit 50 --stale-after 900
```

The command only considers running tasks older than the configured threshold and delegates the state transition to the controlled task runtime.

For cPanel deployment, configure this command as a periodic cron job **after** the application environment/virtualenv is verified. Do not run it against an unverified production database.

## CI

The repository includes automated Django checks, migration consistency checks, tests, and a production-readiness gate. A green CI result is required before production deployment.

## Deployment boundary

GitHub is the development/source-of-truth stage. cPanel/Passenger deployment is a separate production stage and must be validated independently; historical deployment commits are not treated as proof of current server health.
