# Unified VPS migration: factory + Master Agent copy + all subordinate agents

## Owner-approved target
Move the **entire factory** to VPS `178.239.147.150` while **copying** (not moving) the website-host Master Agent and **all its subordinate agents** to the same VPS, as one coordinated deployment. The original Master Agent **and all existing subordinate agents** on the website host must remain untouched and operational. The VPS receives independent full copies of the Master Agent and every subordinate agent; do not relocate or disable any hosting agent.

## Non-negotiable
- No destructive removal or disabling of **any hosting agent**, including the Master Agent and all subordinate agents; no source overwrite, no production DNS cutover without explicit go-live approval.
- Preserve the rule: obtain owner approval before Master Agent actions. No silent autonomous external effects.
- No duplicated scheduled/outbound tasks between host and VPS; isolate DBs, queues, worker identities, locks, webhooks, API credentials and cron.
- Preserve all subordinate agents; inventory from the **live runtime** rather than assuming repo folders are complete.
- Deployment is an atomic *release gate*: copy both workloads, validate together, then enable as an integrated system. If any required component fails, keep VPS execution disabled and preserve original.

## Chain of execution
1. Read-only inventory on hosting and VPS: factory roots, Master Agent roots, subordinate agents, services, databases, volumes, symlinks, runtime config names (not values), data sizes, OS/CPU/RAM/disk.
2. Dependency graph and source-of-truth inventory: distinguish factory workers from Master Agent sub-agents; identify shared state and exact scheduler owners.
3. Quiescent consistent snapshots of relevant databases and state with rollback plan; encrypted off-host backup, restore verification, SHA-256 manifests. No deletion at source.
4. Provision VPS least-privilege Unix users, isolated Python envs, persistent data dirs, PostgreSQL databases, logs, systemd units and network restrictions. Size for 4 GB RAM and disk before starting.
5. Transfer complete factory + Master Agent copy + every subordinate agent, including code, migrations, dependencies, templates and necessary persisted state. Never log or blindly reuse live secrets.
6. Apply DB migrations to isolated destination; verify counts/checksums and agent registry completeness; ensure all agents and factory share the intended orchestrator API while preserving separation of concerns.
7. Start healthchecks and a safe representative end-to-end factory job, including stage 4→5 real evidence persistence; verify the Master Agent can discover and coordinate sub-agents.
8. Confirm original host Master Agent still works and no duplicate cron/outbound action; restart, resource pressure, backup/restore, rollback tests.
9. Request distinct owner approval before production traffic or autonomous outbound operations are enabled. Preserve site public frontend where intended.

## Acceptance evidence
- Exact inventory and byte totals, with VPS free memory/disk.
- SHA-256 manifests for each transferred component and explicit sub-agent count.
- All required processes healthy and isolated; PostgreSQL reachable; real factory task passes with persisted evidence.
- Host original Master Agent **and every subordinate agent** unchanged, present and healthy.
- One coherent deployment report, rollback commands, and owner approval checkpoint.

**Execution status:** specification committed; no claim that snapshots, transfer, VPS service deployment or acceptance have happened.
