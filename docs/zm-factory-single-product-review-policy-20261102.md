# Zomorod Melal — single-product production and independent-review rule

Owner instruction, 2026-11-02: **never enable every factory line at once**.

## Required state machine

1. `factory_held`: keep the previous full hold. Do not restart broad cron jobs, timers, shared writers, or production families.
2. `one_order_active`: after a *fresh private* scheduler and disk audit, only one exact work order may enter engineering. Rework repeats on that same order.
3. `finished_private`: technical quality and genuine archive evidence validated by the 12-stage governance system; never a storefront product automatically.
4. `awaiting_independent_chatgpt_review`: separately inspect the actual archive, scientific calculations, source citations, security, licenses, practical execution, and deliverable integrity. Output an evidence-based report bound to the exact product and passport SHA-256 values.
5. `review_approved`: the report contains no blocking findings, all six criteria pass, and an AI-independent-technical-reviewer receipt is signed using a separately enrolled key. A generic AI statement, unsourced claim, or self-signed factory receipt is insufficient. AI review is a technical screening control, **not** an accredited human professional's certificate or a legal authorization.
6. `private_store_handoff`: only the exact reviewed artifact/version may enter the Zomorod store as a **private/unpublished record**. A distinct authorized human store operator must verify the real store-side receipt and sign the hash-bound handoff record. This is not a public listing, sale, price setting, or bank transaction.
7. `commercial_release_pending`: public availability requires separate owner/commercial approval, verified distribution rights, a real price and fulfillment readiness. The serial worker cannot grant this approval or publish a product.
8. Advance to the **next** product only after technical certification, the signed ChatGPT technical review, **and** the signed private-store handoff for that same product. Never launch parallel production.

## Guard added on feature branch

The `scripts/factory_strict_serial_fullcycle_v1.py` cursor now requires all three:

- `certified_finished(...)`: existing signed, artifact-bound 12-stage factory governance; and
- `independently_reviewed(...)`: a distinct signed ChatGPT-review record, bound to product ZIP, product passport, and separately hashed review report; and
- `store_handoff_verified(...)`: a separately signed human-operator acknowledgment, bound to the precise artifact, review receipt and private store receipt, with public access and payment marked false.

Missing either review or store acknowledgment means the **same** product retains the single slot and no next work order is started. The factory script never publishes to storefronts and has `publications: 0` by design. Reviewers must be securely enrolled out of band; keys must not be fabricated or extracted from secrets. The presence of a signed store receipt does not by itself verify a live database row; the store operator must substantiate it against private store records before signing. These gates are software controls, not evidence that a real product has already passed review or been transferred.

## Verified operational boundary

- The GitHub Actions *full factory hold* completed successfully on **2026-10-30**, run **41093272474**. This is evidence of that run, not proof of the factory's present-minute state.
- A fresh VPS inspection was **not** completed: a proposed workflow exporting private factory audit data into public GitHub Actions logs was rejected on privacy grounds, and no alternate export was attempted.
- The Zomorod private store contained **174** factory drafts and **29** consumer-package candidates; every observed candidate remained unpublished with no paid price. No customer sale was made.
- The site has no active cron entry directly invoking `zomorod_factory_store_import.py` at the time of this review. This does not prove all VPS schedules are stopped.
- A system-origin, idempotent **critical** command-center task `factory:single_product_independent_review` is queued in the private management panel. It does not restart the factory or approve anything.
- Python AST parsing of the edited runner and unit test source passed. The full temporary-file unit suite could **not** run under the current restricted execution policy, so those tests are **not** claimed as passing.

## Restart and release conditions

Keep the full hold until a private, non-public VPS state audit proves no competing scheduler, sufficient disk space, and a single prepared work order. Review an actual customer-deliverable artifact (not merely a `synth_` identifier or transport receipt) before signing a review. The first qualifying product must be reviewed and released through an authorized controlled channel before opening any subsequent slot.
