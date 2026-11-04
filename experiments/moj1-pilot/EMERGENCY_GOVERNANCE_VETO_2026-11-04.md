# MOJ1 governance emergency veto — isolated security finding and candidate patch

**Status: undeployed, unmerged, not independently audited. Mainnet NO-GO.**

## Finding: 48-hour action with a seven-day cancellation path

At the previous candidate commit `74aecfafa8b7cf7d64a75c977a840216e85f32a4`, an authorized outside-contract call could be executed once two signers approved and 48 hours elapsed. The `cancelCurrentNonce()` self-call inherited the seven-day owner-change delay. If signers discovered an error shortly after the operation was approved, their cancellation would not be executable before the risky action. This is a **governance response-time design flaw**, not proof of an actual exploit or loss.

## New candidate mechanism

- `vetoCurrentNonce()` can be invoked only by one of the three current independent owners.
- Each signer can vote only once per current nonce; the second independent vote increments the nonce immediately, invalidating **all** operations approved for that nonce.
- No token transfer, external contract call, beneficiary replacement or new operation can be performed through the veto.
- A single signer, outsider or replayed veto cannot cancel an operation.
- The existing seven-day delay for signer changes and full 48-hour external-operation delay remain unchanged.
- A compromised quorum of two owners can still block operations or authorize changes after timelocks; emergency veto is not a substitute for genuine key independence, hardening or recovery governance.

## Local evidence and external audit tasks

- The disposable local TVM test checks an outsider veto rejection, one vote insufficient, double vote rejection, second distinct owner's immediate cancellation, failed replay of previously approved transfer after time passes, and the ability to schedule an ordinary later operation.
- The audit must check cancel/execution race conditions, signer rotations, quorum loss, malicious token callbacks, forged calldata/digests and boundary nonce behavior.
- Independent verification is required before authorizing any Mainnet signer, token movement, claim publication or legal/financial commitment. No local harness, test timestamp override or self-review qualifies as an independent signer or security audit.
