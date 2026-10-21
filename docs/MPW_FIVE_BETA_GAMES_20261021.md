# MojPlayWin five original browser game betas — 2026-10-21

An isolated, English-language playable web collection built for US/international audience testing.

| Game | Genre | Main play mechanic |
| --- | --- | --- |
| Pulse Forge | Precision arcade | Time reactor strikes and manage focus charges |
| Beacon Labyrinth | Maze puzzle | Recover three beacons while evading patrols |
| Cipher Garden | Memory | Reproduce increasingly long six-petal sequences |
| Skyline Keeper | Tower defense | Deploy and upgrade three defenses over ten waves |
| Nebula Salvage | Orbital physics | Fire gravity-bent probes to recover cargo |

## Publication and safety

- Public path: `https://mojplaywin.com/game-releases/20261021/index.html`.
- The original `/games/` route, Django files, checkout, sub-sites, and previous 20261020 release are intentionally untouched by this workflow.
- English SEO titles, unique descriptions, canonicals, OpenGraph, structured WebApplication/VideoGame data, and a six-URL scoped sitemap.
- Beta clearly disclosed; no claim of Google Play approval, US app-store publication, ratings, server leaderboards, or commercial readiness.
- All games run entirely client-side; no network requests, account, purchases, tracking, or external dependencies. Best scores are saved in browser localStorage.
- Mobile touch and desktop keyboard support; optional user-activated sound; automatic pause on tab switch.
- Deployment requires unit/source validation, pinned SSH relay, exact cPanel owner/root identity, destination absence, and public HTTP smoke. Failure retains only this release in an offline recovery directory.

## Acceptance after deployment

1. Load all six public HTML pages and sitemap; check canonical and beta disclosures.
2. Click Start and exercise the main action in each game.
3. Verify `/`, `/games/`, `/store/` remain HTTP 200 with unchanged content/behavior.
4. Test responsive layouts and keyboard/touch on real devices before a US commercial launch.
5. Link the collection from the main `/games/` UI only through a separately reviewed, existing-site scoped release (the shared Django main-site workflow is currently safety-disabled).
