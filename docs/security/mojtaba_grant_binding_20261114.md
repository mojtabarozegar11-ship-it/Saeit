# mojtaba.bot.ai — owner-approved one-time grant security, 2026-11-14

## Verifiable vulnerability found
The prior `ApprovalService.issue_grant()` accepted arbitrary caller-provided `scope` for an approved request, and `authorize_grant()` only matched keys supplied by its caller, not the full issued scope. It did not revalidate active superuser status or parent approval at consumption and allowed unlimited grants from one approval.

**These are code-level boundary gaps, not proof of exploitation.** Fixes are staged in a Draft PR that does not touch production.

## 20 implemented controls
1. Explicit allowlist of four grant action types.
2. Scope action must exactly match the approval action.
3. Approval target type must match the grant action.
4. Scope must have exactly the defined keys, never hidden extras.
5. Approval risk must meet operation's minimum.
6. Approval object identity must be a bounded canonical ID.
7. Payment scope must bind exactly one Order ID.
8. Knowledge publication scope must bind exactly one article ID.
9. Outbound trade-mail action must bind the one named mailbox.
10. Paid knowledge grant requires typed positive `run_id` and boolean `paid_model=True`.
11. Paid knowledge grant must match the stored AgentTask's actual run and action.
12. Grant issuer must be the original approval's designated owner.
13. Grant issuer must currently be an active superuser.
14. A pending/rejected approval cannot issue a grant.
15. TTL must be a real integer between 30 and 900 seconds.
16. Only one grant can ever be issued per approved request.
17. Consumer must present an explicit, exact full scope; no subset or wildcard.
18. Consumer must verify the parent approval remains approved.
19. Consumer must verify active superuser owner and unchanged actor binding.
20. Consumer must reject an expired, used, or tampered grant and record a one-shot DB audit.

**Compatibility review:** The existing two approval-grant tests now use correctly matched superuser, action and target fixtures. Knowledge generation's paid grant test also uses an active superuser, and a cross-task run is rejected at *issuance* instead of waiting until model execution.

## Tests and evidence
- `tests/test_mojtaba_grant_policy_20261114.py`: 30 pure Python contracts.
- `core/tests/test_grant_binding_20261114.py`: 30 real Django test-DB authorization/nonce/expiry cases.
- Existing `core/tests/test_approval_grants.py` and `core/tests/test_knowledge_agent_generate.py` included in scoped CI.
- `.github/workflows/mojtaba-grant-boundary-ci.yml`: hosted scoped CI, no credentials, broker, external mail, VPS, cPanel or production deployment.
- **PASS is not assumed** from source code. Link exact SHA and CI conclusion after run.

## Operational truth / NO-GO
- `mojtaba.bot.ai` remains the sole canonical bot. No new independent bot, broker account or worker is created.
- Source/isolated tests are not production cPanel/VPS integration, customer consent, paid order, independent TRX settlement, completed download or actual income evidence.
- Single-approval/single-grant rules are deliberately conservative. A *new* independently approved request is required for each later high-impact action: this is not a revenue blocker to remove without a legal substitute.
- PR remains Draft; no main merge, live payment, production publishing, email, live trading or owner expense.
