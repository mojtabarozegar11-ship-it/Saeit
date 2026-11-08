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

Never pay for a source, emit email, publish RSS news automatically, or enable
unreviewed promotional or financial material. Drafts need factual human review.
