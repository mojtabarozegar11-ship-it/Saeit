# Weather and official-news agents — cPanel release plan

Scope: `zomorodmelal.ir` / `Saeit` on cPanel. **No GitHub Actions runtime.**

## Verified production baseline (2026-11-08)

- Python interpreter: `/home/zomorod2/virtualenv/Saeit/3.10/bin/python`.
- `manage.py check` succeeded with Django 5.2.18.
- 31/31 Iranian provinces returned seven complete days of MET Norway forecasts.
- A live weather `NewsletterStory` (`id=1`) was published and observed at
  `https://zomorodmelal.ir/newsletter/weather-iran-2026-11-08/`.
- Three active DB agents were created: `content-research`,
  `newsletter-world-watch`, `newsletter-company-news`.
- Database safety copy (matching SHA-256 immediately after copy):
  `/home/zomorod2/.private/weather_news_pre_activation_20261108.sqlite3`.
- cPanel `/home/zomorod2/Saeit` had 141 pre-existing changed/untracked items.
  **Do not run blanket pull/reset/deploy.**
- No weather/news cron line was observed. A cPanel session expired before cron
  activation; no cron activation was claimed or attempted afterward.

## Pinned VPS-to-cPanel relay audit (cycle 3)

- The existing `.github/workflows/cpanel-direct-command-bridge.yml` and
  `deploy/cpanel_direct_command.sh` are explicitly **read-only**. Their sole
  operations are relay preflight, cPanel/Passenger inventory, Django checks and
  migration listing. They cannot install code, change cron, or activate agents.
  Preserve this allowlist; do not weaken it to bypass cPanel sign-in.
- The direct-bridge `django_check` path currently names Python **3.11**, while
  the interpreter directly verified in the production cPanel terminal for this
  weather/news work was **3.10**. Discover which virtual environment is active
  for the exact running Passenger app before choosing a Python or cron path.
  A successful check in another interpreter is not proof of live parity.
- PR #2194 includes additional offline checks for seven consecutive dates,
  duplicate provinces, impossible values, stable FAO/USDA identity, and
  HTTPS redirects restricted to the source publisher. Code/tests remain
  source-side until an explicitly scoped, backed-up cPanel install.

## Controlled release steps after reauthentication

### Mandatory read-only file-conflict preflight (cycle 8)

PR #2194 ships two additional release files:
`deploy/newsroom_release_manifest_20261108.json` and
`deploy/newsroom_release_preflight.py`. The manifest pins the Git blob SHAs of
**19 exact application files**, including the published-page templates. It does
not grant deployment authority and the checker **cannot write files**.
The manifest's `commit` is the immutable application-code snapshot whose
19 file hashes are enumerated (cycle 12: `dea67c8d`); a later documentation-only
commit may carry that manifest without changing the application snapshot.

Cycle 10 also HTML-script-escapes untrusted JSON-LD values in public newsletter
detail pages (`core/newsletter_views.py` and `core/editorial_signature.py`).
This is source-side protection only; it is **not deployed** until the existing
cPanel login and individual host-file reconciliation have been completed.
Cycle 11 additionally blocks public surfaces from showing unapproved, future,
unpublished or prohibited newsletter stories, and filters public channel records
to confirmed published channel entries. A successful GitHub CI does not prove
these protections are active on the live cPanel instance.
Cycle 12 adds a model-level `#مجتبی_روزگار` final-signature requirement for a
`published` NewsletterStory and for published channel distribution. Publishing
to a channel also requires a presently public, non-future story. Legacy unsigned
published rows must be individually corrected under editorial approval before
their next programmatic save or public-channel distribution; the source change
does not silently rewrite their bodies.

After authenticating legitimately and placing these two verified release-tool
files in an accessible, nonproduction staging directory, inspect the actual
Passenger app path (confirm it independently first):

```bash
python3 deploy/newsroom_release_preflight.py \
  --target-root /home/zomorod2/Saeit --strict
```

- `already_current` means the target bytes match this PR's pinned Git blob.
- `new_file_missing` means the PR adds a file not present on the target.
- `different_manual_merge_required` means the target has local contents that
  must be backed up, reviewed, and reconciled individually before any write.
- `modified_file_missing`, `unsafe_symlink`, `unsafe_not_regular_file`, and
  `unreadable` are release blockers, not implicit permission to replace.
- This scan does **not** prove whether cPanel/LiteSpeed serves `/weather/` or
  `/news/` from another public document root. Inspect those routes separately.
- Cycle 18 adds a separate **read-only** script for this exact distinction:
  `deploy/newsroom_static_routes_audit.py`. After legitimate cPanel access,
  independently confirm the document root for `zomorodmelal.ir` from Passenger/
  web-server settings, then run the staged script against **that exact root**:

  ```bash
  python3 deploy/newsroom_static_routes_audit.py --public-root /home/zomorod2/public_html
  ```

  This example path is only a prior observed candidate, **not a fresh route
  verification**. The audit prints SHA-256 and whether `news/index.html` and
  `weather/index.html` reference the previously injected editorial loader. It
  does not mutate content, does not follow a route symlink, and does **not**
  prove the live server sends traffic to the inspected files. Compare with
  active rewrite/Passenger rules and independent HTTP evidence before any
  changes. Do not broaden the read-only GitHub→VPS→cPanel command bridge.
- Never use the broad eight-template deployment workflow as a substitute for
  this reconciliation, and never expand the read-only VPS-to-cPanel bridge.

The `--strict` return code is nonzero when reconciliation is required. Do not
claim a safe release merely because the command exits zero: it never installs
anything and missing new files still require a reviewed installation step.

1. Reconfirm the live source, database route, valid account and existing cron.
   Do not alter an unrelated path or any of the 141 existing worktree changes.
2. Compare individual hashes/content before installing only these source files:
   `core/news_feed_reader.py`, `core/management/commands/news_agent_cycle.py`,
   `core/weather_weekly_report.py`, the minimal `build_public_report()`
   integration in `core/weather_agent.py`, and, only if absent,
   `core/management/commands/weather_agent_cycle.py`. The installed
   `weather_agent.py` was already modified on 2026-11-07: review its diff
   manually and merge only the compatible function change. Store timestamped
   copies of any destination files before replacement.
3. Run `manage.py check`, validate actual USDA NASS and FAO official-feed fetches,
   tolerate an isolated feed failure but report it explicitly, then inspect
   `news_agent_cycle` output and its **draft-only** records. Never bypass a
   source or agent validation failure.
4. In cPanel Cron Jobs, configure in server timezone (`+03:30` on 2026-11-08)
   and only after verifying the relevant commands exist on the live path:

   Weather once per day, 06:20 (local server time):

   ```cron
   20 6 * * * /bin/flock -n /home/zomorod2/.private/zm_weather.lock /home/zomorod2/virtualenv/Saeit/3.10/bin/python /home/zomorod2/Saeit/manage.py weather_agent_cycle >> /home/zomorod2/.private/zm_weather.log 2>&1
   ```

   News every six hours, 10 minutes past hour (00, 06, 12, 18):

   ```cron
   10 */6 * * * /bin/flock -n /home/zomorod2/.private/zm_news.lock /home/zomorod2/virtualenv/Saeit/3.10/bin/python /home/zomorod2/Saeit/manage.py news_agent_cycle --max-items 15 >> /home/zomorod2/.private/zm_news.log 2>&1
   ```

5. Verify **actual** next execution timestamps, successful logs, no duplicate
   news fingerprint, weather report freshness and public newsletter render.
6. The first published story showed just the first daily slice for each of
   31 provinces despite 7-day retrieval. The new weekly report builder renders
   all seven dates; compare public content after the guarded deploy, without
   claiming the prior story was a full 7-day decision report.
7. The `/weather/` and `/news/` paths are separate static pages and require a
   separately reviewed UI wiring/deployment. A Django publication alone does
   not establish those static pages have updated.

## Live public-HTML negative delivery gate (cycle 19)

On 2026-11-09 (Asia/Tehran), a fresh **public-browser inspection** observed:

- `/weather/` still says it does not publish a live forecast, although it has
  the independent user-input irrigation-risk calculator.
- `/news/` still shows company/information navigation, not a working external
  news reader.
- The November 8 public newsletter weather bulletin renders **31 day-one
  province records**, not **217 daily records** (31 provinces × seven days).
  Its visible original-report body did not end with `#مجتبی_روزگار`.

`deploy/newsroom_public_delivery_audit.py` is a new **read-only, fail-closed
negative gate** for these visible defects. Run it from a trusted host that
can reach the public site with a valid HTTPS certificate; it only fetches
three fixed `zomorodmelal.ir` paths, refuses redirects, caps response sizes,
and cannot publish or modify anything:

```bash
python3 deploy/newsroom_public_delivery_audit.py --story-date 2026-11-08
```

Exit `0`: none of the explicit negative markers were observed and the
published story has all 217 date lines, 31 province headers and the exact
final signature **inside** the original report. Exit `1`: known publication
defect remains. Exit `2`: HTTP/HTML evidence could not be obtained. A clean
exit does **not** prove that client-side JavaScript, data freshness, backend
agents, approved-news semantics or cron operate correctly: complete separate
browser/Passenger/release checks before declaring the service operational.
This script is not part of the live application release manifest and cannot
be used to bypass cPanel authentication or the host-key safety gate.

Never pay for a source, emit email, publish RSS news automatically, or enable
unreviewed promotional or financial material. Drafts need factual human review.
