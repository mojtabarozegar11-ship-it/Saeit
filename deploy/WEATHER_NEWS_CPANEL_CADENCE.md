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

## Controlled release steps after reauthentication

1. Reconfirm the live source, database route, valid account and existing cron.
   Do not alter an unrelated path or any of the 141 existing worktree changes.
2. Compare individual hashes/content before installing only these source files:
   `core/news_feed_reader.py`, `core/management/commands/news_agent_cycle.py`,
   and, only if absent, `core/management/commands/weather_agent_cycle.py`.
   Store timestamped copies of any destination files before replacement.
3. Run `manage.py check`, validate an actual official-feed fetch, inspect
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
6. The `/weather/` and `/news/` paths are separate static pages and require a
   separately reviewed UI wiring/deployment. A Django publication alone does
   not establish those static pages have updated.

Never pay for a source, emit email, publish RSS news automatically, or enable
unreviewed promotional or financial material. Drafts need factual human review.
