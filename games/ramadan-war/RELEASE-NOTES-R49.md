# G-01 R49 — Ramadan War verified offline package, rotation and S-01 handoff (2026-10-30)

## Primary / Ramadan Web
- Corrected two integrated CI test assumptions from R48 run 41102452031 (lines 355 and 361): unsafe fallback returns null, and both restore abort guards precede hero assignment and engine build.
- Reject non-finite saved hero coordinates before any fallback relocation; no corrupted save mutation.
- Rebuilt offline preview-manifest.json from actual packaged assets: R48 carried R41 metadata and four stale SHA-256 entries (campaign-backup.mjs, game.js, input-guard.mjs, save-validation.mjs). R49 manifest matches all 32 declared runtime assets.
- Independent ZIP /Games/G01/R49/ramadan-war-g01-r49-verified-manifest-20261030.zip in **private Library**, upload and independent Library listing confirmed. ZIP SHA-256: `edc64e4f64de9b690c113e69726aac5c1c4186131838a728c84a5d77ee700e19`. 103 entries, ZIP CRC PASS, 102/102 all-files SHA-256 PASS, 32/32 current runtime-manifest hashes PASS, 141/141 local Node QA PASS. Offline package **DELIVERED**; live release NOT VERIFIED.
- The ZIP is a local review build. Browser acceptance and source-exact CI are separate gates. Never infer live release from ZIP integrity or Node tests.

## Rotation
- Crown Defender: corrupt local quality/contrast preferences now rejected against actual select enumerations; boolean settings preserved.
- Cake Maker / Taniya: keyboard focus returns to the selected topping/candle control after redraw, with disabled-boundary fallback to the complementary action.

## Help G -> S
- `games/g01-handoffs/g01_s01_public_anchor_audit_r49.mjs` and corresponding synthetic test: read-only, anonymous DOM anchor name/center-hit-target audit. Emits only indices/reason codes, never URLs, customer text or credentials. S-01 owns authorized browser use and all site changes.

## Hold and release
- No factory VPS/master-agent write, restart, cron/systemd/DB/worker change, cleanup, SSH dispatch or deployment.
- MOJ1 and paid wallet operations remain disabled. No public merge/deploy or paid transaction.
- Exact next action: verify latest R49 branch CI including desktop/mobile browser; correct any failures. S-01 must separately prove off-VPS backup/isolated restore, rights, rollback, staging and live URL before release.
- Unity, Air Supremacy, Roham, ECHOFORM and other queued games remain unclosed. Next round-robin: Unity and Air Supremacy.
