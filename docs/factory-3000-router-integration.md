# اتصال یک‌مرحله‌ای میزکار ۳۰۰۰ ابزاری به کارخانه VPS

Commit of `factory_tool_router.py` creates an actual **local** invocation interface for all 3000 production-support bindings, including the additional 2000 T26–T75 family bindings. This is not an installation of native manufacturing engines and does not certify commercial product quality.

- Each existing five-minute forty-family controller tick now invokes a hash-verified local router before launching the controller; no new cron entry or schedule.
- During each tick the router executes ten genuine deterministic operations against each family's **real registry profile** (400 calls), creates per-family SHA-256 proof entries and a private dashboard.
- Full catalog verification checks runtime and base-code SHA-256, catalog SHA-256, unique registered IDs and per-family 75 operations.
- Every registered tool can also be called by existing private workers through `--tool-id` / `--role` / `--input-file` / `--output-file` under `private/autonomous-product-cycle/tool-router/jobs/`, or through queued JSON requests in `tool-router/requests/`. Queued requests run on the same existing factory tick, max ten per cycle, and create isolated responses in `tool-router/results/`.
- The role field is a local caller label, **not an authentication system**. Actual agent-specific callers remain to be demonstrated; reporting their live adoption just because an API exists would be false.
- No network, third-party API, worker spawning, online payments, cPanel edits, automatic product promotion, public distribution, or native generator activation. No change to existing 1000-tool installer.

Runtime receipts:
`/home/githubops/factory-runtime/private/autonomous-product-cycle/tool-router/dashboard.json` and `/home/githubops/factory-runtime/operations/forty-execution/factory_tool_router.py`.

Example request from an authorized local worker:
```json
{"schema":"saeit.factory.local-tool-request.v1","request_id":"task123","role":"planner","tool_id":"F27-T26","payload":{"numbers":[3,5,7]}}
```
Save privately to `tool-router/requests/task123.json`; on next tick read `tool-router/results/task123.json`. Passing synthetic fixtures proves the routing code, not the independent scientific or commercial quality of the resulting products.
