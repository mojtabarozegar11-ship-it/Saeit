# Gate 97 operational drill record

Run these only after `staging_preflight` passes. Preserve timestamps, run IDs and JSON output.

| Drill | Procedure | PASS evidence |
|---|---|---|
| unattended scheduler | Configure only the staging cron to run `staging_tick.sh`; do not manually advance a task | cron log shows seed/recovery tick without Production path/DB |
| process restart/resume | Start a Factory Run, stop the staging app between bounded steps, restart Passenger, resume with the same `--run-id` | same FactoryRun continues; no duplicate completed stage |
| stale recovery | In an isolated drill run, allow a running task to exceed the stale threshold and invoke the recovery command | audited stale recovery followed by bounded continuation |
| transient retry | Cause a staging-only provider/network transient failure, restore connectivity, resume | retry is bounded/audited and evidence is not duplicated |
| bounded re-research | Use a Goal where first evidence is insufficient | Master requests bounded re-research or blocks; it never invents evidence |
| idempotent replay | Re-run maintenance/recovery and resume same run ID | completed stages/artifacts are not duplicated and lineage remains valid |

A human may initiate/observe these acceptance drills, but must not create intermediate Factory tasks, edit stage state, manufacture evidence/artifacts, or bypass a blocker. Any such intervention invalidates the autonomy acceptance.

Gate 97 requires both the Goal-only candidate acceptance PASS and all operational drills PASS in the isolated real-staging environment.
