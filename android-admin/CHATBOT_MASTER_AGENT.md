# Master Agent Chatbot

The Android admin app is the owner-facing control surface for Saeit's Master Agent and Robot Empire.

## Runtime contract
- Backend is authoritative for execution, approvals, audit, tasks, agents, and robot runs.
- Chat is an authenticated command/consultation channel; a generated reply is never treated as proof of execution.
- Risky actions remain approval-gated by the backend.
- The app uses HTTPS and encrypted local token storage.
- Dashboard refresh is intentionally lightweight; deep browser checks and expensive evolution work remain server-side.

## Current endpoints
- POST /api/auth/token/
- GET /api/admin/dashboard/
- GET/POST /api/agent-control/
- GET /api/tasks/
- GET /api/approvals/?status=pending
- POST /api/approvals/{id}/decide/
- POST /api/master-chat/
- POST /api/master-chat/{id}/messages/

## Operational principle
Fast path: dashboard → health → chat → approval → task status.
Deep path: Master Evolution Robot, browser verification, research, and production actions execute on the server under governance.

## Verification rule
The Android client must display server state and timestamps rather than inventing success. A command is successful only when the backend returns a successful state transition.

## Build
The project is configured for Android SDK 35 / Kotlin Compose. Production deployment is intentionally separate from source changes.
