# Ramadan War R43 — private backup lifecycle release candidate
R42 exact offline game retained. R43 clears sensitive pasted/exported backup text on window blur, hidden-tab transition and bfcache return, and explains the redaction in the open dialog.
Node regression: 115/115 local tests passed against the offline R43 copy; GitHub exact-head CI and desktop/mobile browser QA remain separate and unverified. Local Chromium returned ERR_BLOCKED_BY_ADMINISTRATOR.
Rotation: Air Supremacy Escape pauses even with focused HUD buttons; ECHOFORM R43 Escape handles focused action buttons without intercepting form select.
S-01 receives a separate local-only browser accessibility gate; never interacts with payment or production services.
No factory VPS/master-agent writes, no MOJ1, no deployment. Public release remains S-01 gated by off-VPS backup and rollback.
