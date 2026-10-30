# G-01 R48 — Save restore geometry fix (offline playable)

- Recover saved hero positions whose center is in a floor tile but whose 0.21 radius clips a wall.
- Preserve score, earned upgrades, objective progress and inventory during safe position recovery.
- Reject unsafe fallback instead of resuming into impassable geometry; preserve in-memory checkpoint on failed restore.
- New five-case regression suite; full Node suite 139/139 locally.
- Rotation in separate GitHub source files: Roham drawing touch pointer ownership, cancellation and single-tap dots; ECHOFORM expected-versus-received failure feedback.
- Cross-owner S-01 handoff: read-only, source-redacted checkout SHA drift comparator with five synthetic unit tests.
- No payment activation, factory writes, merge, deployment or public site change.
