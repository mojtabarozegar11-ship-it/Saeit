# MojPlayWin independent newsroom — 18 October 2026

This is an adapted implementation of the evidence-first Zomorod newsletter methodology, **not** a copy of Zomorod articles, subscribers, publication records, dates, branding, or database.

## URLs (after approved and verified deployment)

- MojPlayWin: /newsletter/ (approved articles only); /newsletter/<slug>/; /newsletter/archive/
- MojPlayWin staff only: /staff/mojplaywin-newsletter/ (read-only counts and draft-quality holds)
- Zomorod Melal: the existing /newsletter/ routes dispatch to their **original** views, unchanged on Zomorod hostnames
- No updates to /farnaz/, /zahra/, /sam an/, /mojtaba.roozegar/, /taniya/ or other subsite routes. [Do not take the list as exhaustive.]

## Private storage and editorial governance

- Isolated file: \`BASE_DIR/.private/mojplaywin-newsletter.sqlite3\` or the absolute path set in \`MOJPLAYWIN_NEWSLETTER_DB\`.
- Database must stay outside public directories, mode 0600; parent directory 0700.
- Zomorod Django NewsletterStory model and existing DB remain untouched.
- Article draft JSON fields: category, title, summary, body, analysis, origin (\`internal\` or \`external\`), evidence, keywords, event_date, source_url, publisher, source_title.
- External articles require a named publisher, a full source title, and an HTTPS source link. Editors must substantively verify factual and source claims themselves: syntax validation alone is not source verification.
- An independent analysis of at least 450 characters is necessary for the high quality gate. No automatic false expert attribution to the Zomorod CEO.
- Quality gate requires score >=90/100 **and** a distinct human approval. Producer agents cannot self-approve.
- Duplicate drafts are blocked by a deterministic fingerprint. Failing drafts remain private.
- Publishing uses explicitly approved stories only. \`publish-due\` can be scheduled, but NO cron and NO outbound posting is installed by this branch.
- Do not migrate email subscribers or mailing lists without a separate opt-in and deliverability/privacy review.

## Controlled operations

Run under the authorized MojPlayWin deployment identity, in the repository root:

\`\`\`bash
python3 scripts/mpw_newsletter_cli.py init
python3 scripts/mpw_newsletter_cli.py draft --json /private/verified-mpw-article.json
python3 scripts/mpw_newsletter_cli.py stats
python3 scripts/mpw_newsletter_cli.py approve --id 1 --editor verified-owner
python3 scripts/mpw_newsletter_cli.py publish-due
\`\`\`

Agent integrations can submit draft JSON; do not let the quality-monitor cron perform the \`approve\` action. For a publication timestamp, use \`--when '2026-10-20T09:00:00+03:30'\` at approval time. The publication command is idempotent.

## Deployment gates (not performed in this branch)

1. Review Django route diff and all impacted files; pass Python tests and security review.
2. Identify the currently deployed MojPlayWin Passenger app location and its exact revisions through the pinned GitHub Actions → VPS relay → cPanel route.
3. Make a verified, recoverable backup of current MojPlayWin site, its separately hosted sibling sites and shared config; verify restore in an isolated location.
4. In an isolated staging instance, apply only the reviewed changes and initialize the **private** newsletter DB. Confirm tenant routing, staff-only screen, published versus unpublished views, and Django checks.
5. Perform atomic scoped update; verify /newsletter/, /newsletter/archive/, an approved article, existing Zomorod /newsletter/, existing Moj home/store and representative sibling sites. Roll back if any check fails.
6. Only after that verification, connect draft generation and approved publication to the site's existing agents/cron. No new cron must overwrite existing cron entries.

**This PR does not publish to the live site.** Green CI validates the code but does not establish cPanel/Passenger production readiness.
