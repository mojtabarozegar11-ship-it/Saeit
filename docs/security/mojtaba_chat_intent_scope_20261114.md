# mojtaba.bot.ai — exact chat intent and approval scope gate (2026-11-14)

## Problem, evidence and operational limit
The old parser looked for broad phrases such as "create page", inferred MojPlayWin whenever "Zomorod" was absent, harvested an arbitrary slash path, and auto-generated a title from surrounding prose. A reference to a task could therefore be filed as an owner approval request for the wrong business site. It did not authorize payment, but such ambiguous requests are not reliable production management.

**This staged patch adds narrow, valid intent parsing and shared path policy.** Only the canonical `mojtaba.bot.ai` agent is represented. A valid operation enters the **existing pending approval** flow; it is not executed and never gains settlement, deployment, publication or direct owner authority.

## 20 distinct source-level controls
1. Reject non-string chat input.
2. Enforce bounded command size (≤ 4,000 characters).
3. Reject control characters and multiline requests.
4. Reject directionality and zero-width spoofing controls.
5. Reject questions as an action trigger.
6. Reject explicit negative commands.
7. Reject cancellation language.
8. Recognize cPanel preflight only as an exact command.
9. Recognize Passenger inventory only as an exact command.
10. Preserve exact full-match recognition for explicit deploy commands, which the chat runtime still blocks.
11. Require command verb at the beginning of a draft action.
12. Reject mixed create/edit operations.
13. Require exactly one explicit business site.
14. Reject requests mentioning both business targets.
15. Exclude quoted titles from target detection.
16. Require one canonical absolute page path.
17. Reject root/double slash/dot/traversal and URL-percent/confusable paths.
18. Bind Zomorod changes to `/company/`, preserving case-sensitive exact path text.
19. Require one bounded, explicitly quoted, non-markup new page title; do not fabricate names.
20. Bind owner approval reason to typed operation ID/action/risk/target/parameters plus a strictly positive integer session ID.

**Extra hardening:** owner identity flags must be actual booleans; the Django approval validator imports the same canonical `valid_draft_path` function to avoid parser/approval drift.

## Test and non-production release
- `tests/test_mojtaba_chat_intent_20261114.py` contains 42 generated named parser regression methods and 21 explicit scope/identity tests: **63 offline cases**.
- Existing `tests/test_mojtaba_authorization_boundary_20261114.py` in the parent security branch has **42 more** cases.
- The scoped workflow runs only Python unittest + syntax validation (no database or internet calls by the scripts).
- An independent Django approval lifecycle/test suite remains necessary: pure parser tests do not establish live DB request binding, customer checkout or website availability.
- DO NOT merge to main or deploy, trade, email, invoice, charge, use a paid model, create a new bot, retire workers or collect private customer data without separate owner approval.

**Accounting:** 20/20 policy checks are implemented in source; this is 100% of the *limited 20-control code checklist*, not whole-bot completion or commercial readiness. Receipts, published versions, settled TRX, customer deliveries and revenue remain **UNKNOWN**.
