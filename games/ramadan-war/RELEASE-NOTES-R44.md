# Ramadan War R44 — private backup recovery and async safety

Changes from R43: (1) accept one optional UTF-8 BOM in valid manual JSON backups while keeping the strict 512 KiB byte cap and schema validation; (2) reject stale asynchronous file reads after a newer file is selected; (3) reject stale file reads after navigating to a different screen; (4) refuse to open a private clipboard fallback dialog on a different screen; (5) refuse to open the fallback when the tab is hidden. All R43 gameplay and assets remain intact.

Local checks: `node --test qa/*.test.mjs`. Run the game through a loopback static HTTP server (not `file://`). R43 real desktop/mobile browser CI [run 41059231635](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41059231635) passed; that does **not** substitute for R44 exact-head browser CI. Public release needs S-01 backup/rollback and live URL verification. Factory HOLD; MOJ1 disabled.
