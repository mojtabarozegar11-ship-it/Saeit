# Operational delivery acceptance — websites + factory + agents

Owner requires a **real operational handover**, not code-only or test-only reports.

## Required running estate
- Iranian Persian website: real domain and production service health, live pages, checkout/payment integration as applicable.
- Global English website: real domain and production service health, localized pages, payment/crypto integration as applicable.
- Factory on VPS 178.239.147.150: live service, persistent PostgreSQL, queue/scheduler, verified representative product through research evidence persistence and stage 4→5.
- Master Agent: original host instance **must remain active**, complete isolated VPS copy must operate.
- Every existing subordinate agent: original hosting instance **must remain active**, complete isolated VPS copy must operate, with no duplicate outbound actions or shared queue collisions.
- Site-to-factory APIs, service health monitoring, restart policies, backups and tested restore.

## Evidence required before saying delivered
1. Timestamped authenticated server inventory (processes, RAM/disk, services, deployment versions).
2. Real public HTTP checks for both websites, including representative routes and user workflows; screenshots where meaningful.
3. Real database connection/migration and durable readback on VPS, without exposing credentials or user data.
4. A real end-to-end factory execution with stored research evidence, automatic stage 4→5 transition and artifact, not a mocked test.
5. Master Agent and subordinate-agent registry count/hash comparison between hosting and VPS, representative safe action on VPS, and host-original health proof.
6. Negative duplicate-scheduler/outbound-action check; secrets isolated.
7. systemd/service restart recovery, backup and restore verification, resource headroom, rollback readiness.
8. Owner approval for any production cutover, irreversible change or autonomous external action.

**Status**: This file defines release criteria only. No evidence currently proves all these gates. Do not report project delivered until they pass.
