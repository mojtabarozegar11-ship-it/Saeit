# mojtaba.bot.ai — security audit of four approval boundaries
**Audit date:** 2026-11-14. **Scope:** offline source and pure-decision regression; **production:** NOT inspected or changed.

Canonical public bot remains exactly `mojtaba.bot.ai`. The four modules make *advisory, fail-closed decisions*; they do not create credentials, consume a one-time approval, execute tools, transfer funds, trade, deploy, publish, deliver a sale or prove consent. Real financial, external message and host operations require independently verified owner authority and action-scoped receipts.

## Twenty explicit corrective audit controls

| ID | Control / tested rejection or positive invariant | Implementation |
|---|---|---|
| 01 | Typed owner identifier, no list/dict masquerading | action_policy |
| 02 | Typed nonblank target identifier | action_policy |
| 03 | Authentication must be boolean True, not "true"/1 | action_policy |
| 04 | Action must belong to typed enum | action_policy |
| 05 | Sensitive action without approval remains pending | action_policy |
| 06 | Approval verification requires boolean True | action_policy |
| 07 | Approval must match exact enum action | action_policy |
| 08 | Approval must match exact target resource | action_policy |
| 09 | Unknown action cannot acquire implied authority | action_policy |
| 10 | Pure approval input values must be nonblank strings | approvals |
| 11 | Receipt must have correct typed structure | approvals |
| 12 | Receipt approval flag requires boolean True | approvals |
| 13 | Host timestamp and expiry must be real datetime values | approvals |
| 14 | Naive timestamp and exact expiry rejected | approvals |
| 15 | Guard rejects unhashable/non-string action and target | operation_guard |
| 16 | Guard rejects malformed receipt and non-boolean verified | operation_guard |
| 17 | Guard rejects malformed receipt ID and time | operation_guard |
| 18 | Per-request policy rejects non-boolean auth and malformed IDs | operation_policy |
| 19 | Per-request approval IDs/owner/resource match exactly, Unicode safe | operation_policy |
| 20 | Per-request expiry, request replay or unknown action rejected | operation_policy |

## Test artifact and limits

- `tests/test_mojtaba_authorization_boundary_20261114.py`: **42 explicit** offline test methods, including positive acceptance controls, malformed inputs and cross-request rejection.
- Existing `tests/test_action_policy.py`, `tests/test_unified_approvals.py` and `tests/test_operation_policy.py` remain unchanged and are selected for scoped CI regression.
- Workflow `.github/workflows/mojtaba-auth-boundary-ci.yml` is scoped to PRs targeting the canonical integration branch: source-only unittest/compile, no secrets, external providers, DB, broker, VPS, cPanel or deployment.

### Operational and commercial evidence gate (NO-GO)
1. This patch's source check is **not** a proof of single running VPS/cPanel bot or effective per-user authorization.
2. A pure `True` does **not** prove an owner approval was issued, authenticated, unexpired at action time, consumed exactly once or recorded durably.
3. Remain Draft until exact-head CI and host-authorized integrations establish the complete approval chain.
4. No customer order, real inquiry, settled TRX, payment receipt, license delivery, email, profitable trade or financial return has been independently attested by this audit.
5. Do not merge to `main`, run a production workflow, create a cost, call an LLM provider, retire a legacy worker, or execute live side effects without the owner's separate approval.

**Progress interpretation:** 20/20 audit-control rows have code or test coverage in this review scope, *not* 100% operational readiness. The 42 tests are an implemented regression suite; their pass/fail must be reported from CI, not inferred from source creation.
