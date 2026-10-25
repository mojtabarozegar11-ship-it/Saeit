# Mobile Game Commercial Release: Evidence-Based Gatebook

*Free operational resource, MojPlayWin, 25 October 2026. A checklist, not certification of any game or app.*

## The principle
A build is not commercially ready merely because it opens. Every acceptance item needs a release build identifier, device/OS, expected result, observed result, evidence link, severity, accountable owner, date and retest result. Mark untested items UNKNOWN, not PASS.

| Gate | Required evidence | Stop-release condition |
| --- | --- | --- |
| Reproducible build | Signed release artifact, toolchain versions, checksum, clean build | Only an editor preview exists |
| Start and recovery | Cold launch, resume, interruptions, offline behavior on multiple device tiers | Crash or lost progress |
| Input | Touch, gestures, safe areas, orientation, controller where advertised | Core action impossible |
| Gameplay | Explicit rules, progression, scoring, difficulty, win/loss state, seed replay | Unwinnable levels |
| Performance | Frame-time distribution, memory trend, thermal checks | Sustained stalls or runaway memory |
| Persistence | Save/load, migration, corrupt save, reinstalls | Loss of paid or earned entitlement |
| Accessibility | Contrast, scaling, motion alternatives, color-independent signals | Unusable essential control |
| Privacy | Data inventory, consent/legal basis where needed, retention and deletion | Undisclosed data collection |
| Payments | Store-compliant checkout, server-side entitlement, restore, refund path | Client-only receipt check |
| Rights | Licenses for models, audio, fonts, art and trademarks | Missing permission |
| Support | Contact, version, escalation, privacy and refund terms | No workable support |
| Release | Rollback trigger, staged rollout, crash monitoring, named owner | No recovery plan |

## A measurable first-session study
Recruit first-time players and experienced players, on at least low- and mid-tier devices. Do not instruct participants unless the game would naturally provide instruction. Observe time to first meaningful action, time to first success, mis-taps, failed attempts, confusion, pauses, assistance requests, voluntary continuation after five and ten minutes, and qualitative reasons. Ask permission before recording. Do not present small-sample observations as population retention.

## Real retention and revenue metrics
Define day-1 retention as eligible new users who return on day 1 divided by eligible installs, with timezone and deduplication rules specified. Report sample sizes. Separate ad impressions, net ad revenue, in-app purchases, refunds, platform fees and taxes. Do not equate a payment unit test with a successful live buyer transaction. Verify store policy and legal eligibility for each target market before launch.

## Release decision record
- Build checksum and version:
- Device and OS test matrix:
- Critical/high/medium unresolved issues:
- Observed crash-free sessions and denominator:
- Rights, privacy and safety reviewer:
- Payment entitlement and restore evidence, if relevant:
- Store listing accuracy and screenshots from real gameplay:
- Named release owner and rollback trigger:
- Decision (GO / NO-GO / MORE EVIDENCE), date, signature:

NO-GO if any critical issue remains, asset rights are uncertain, a mandatory platform check is incomplete or an advertised checkout has no independent end-to-end evidence.

**Free companion:** [browser-game release evidence worksheet](https://mojplaywin.com/mpw-free-tools/20261025/browser-game-qa/?utm_source=github&utm_medium=resource&utm_campaign=game_release_20261025). [MojPlayWin](https://mojplaywin.com/?utm_source=github&utm_medium=resource&utm_campaign=game_release_20261025). No claim is made that any mobile game is presently available for purchase.