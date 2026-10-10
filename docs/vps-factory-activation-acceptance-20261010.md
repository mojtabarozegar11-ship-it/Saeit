# VPS factory activation: blocked handoff and acceptance criteria

Scope: ONLY VPS 178.239.147.150 (githubops), /home/githubops/factory-runtime. Do not contact cPanel, zohal.pws-dns.net, or ProxyJump. Do not transfer data between hosts.

## Verified baseline (2026-10-10)
- GitHub Actions run 38034981759: FAILED, correctly rejected false success.
- The existing VPS loop process was alive.
- `core.self_hosted_research_provider.SelfHostedStagingResearchProvider` is importable and advertises `real_research=True`.
- `FACTORY_RESEARCH_PROVIDER` is not configured in the active process.
- `FACTORY_DISCOVERY_ERROR type=FactoryAgentBlocked`; `processed_runs=0`.
- SQLite target: `/home/githubops/factory-runtime/private/factory-fresh-isolated.sqlite3`.

## Required authorized execution (NOT completed)
1. Snapshot current VPS loop script, environment configuration, database, and current PID; verify permissions and available disk space.
2. Determine whether Django settings overrides the environment provider path. Configure the existing provider using `FACTORY_RESEARCH_PROVIDER=core.self_hosted_research_provider.SelfHostedStagingResearchProvider` in the persistent service environment. Never print secrets.
3. Safely stop only the identified VPS factory loop and any child tick; ensure no concurrent SQLite writer. Restart once under an exclusive lock and verify its actual environment. Avoid killing unrelated processes.
4. Confirm `configured_research_provider()` resolves the expected class and `real_research=True`.
5. Run a bounded real research tick against an existing factory product; preserve SSRF checks, rate limits, source relevance, and zero paid-LLM budget.
6. Confirm genuine evidence was fetched and persisted to the isolated SQLite database, and that the same product transitioned from stage 4 to stage 5. Record nonsecret run/product/evidence IDs and timestamps.
7. Check process remains alive across subsequent ticks; on failure restore the prior script/configuration and report the exact blocker.

## Acceptance gates
- Provider resolves from the actual running process (not just direct Python import).
- Nonzero successful processed runs attributable to the new deployment; historical log matches do not count.
- Database records show fetched evidence and valid stage 4->5 transition for the same product.
- Repeated ticks show no concurrent writers, no cost-limit violations, and no regressions.
- GitHub workflow exits success only after the above evidence is checked.

No stage 4->5 success is claimed until these gates pass. This runbook does not execute remote changes.
