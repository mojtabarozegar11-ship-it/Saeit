# Master Agent Chatbot

The Android admin chatbot is the owner-facing control surface for Saeit.

## Contract
- Conversation is session based.
- Backend remains authoritative for execution.
- Chat may propose research plans and explain task state.
- Sensitive actions require an owner approval recorded by the backend.
- The client must never report an action as executed merely because a chat response was generated.
- API calls use HTTPS.

## Current endpoints
- POST /api/master-chat/
- POST /api/master-chat/{id}/messages/

## Next integration layers
1. Approval Center
2. Research request creation
3. Task status streaming/polling
4. Agent routing visibility
5. Audit trail
6. Secure token storage

No production deployment is performed by this Android module.
