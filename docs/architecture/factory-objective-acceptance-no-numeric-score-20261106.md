# Factory release policy — objective acceptance (2026-11-06)

Owner decision: retire the mandatory numerical 1000-point quality criterion.
It was a manufactured bottleneck rather than evidence that a customer could
use the product. Never convert the removal of that criterion into a blanket
right to sell, charge or distribute third-party material.

## Two separate decisions

1. **Manufacturing completed:** verify the exact immutable source digest and
   customer ZIP SHA-256, required files, real non-skipped unit tests executed
   from a fresh extracted customer archive, safe archive entries, consistent
   measurements and required private technical evidence. This independently
   frees the single-product manufacturing slot.
2. **Commercially releasable:** verify actual package bytes, all relevant
   functional evidence, legitimate distribution rights, security and privacy,
   truthful documentation and claims, complete exact-version product review,
   correct real storefront mapping, and the owner's exact-version publication
   authorization. Unmet or unproven conditions prevent the public action.

No `1000` score, points-based rubric, doctoral dossier or four-person scoring
panel is a precondition to either decision. The historic authenticated
quality artifacts and v1 customer receipts remain unmodified for audit.

## Data and compatibility

- New manufacturing manifests use `professional_quality_standard =
  objective_acceptance_v1` and have no numeric grade. Preexisting immutable
  manifests retain their original fields and hashes.
- Cached packages receive a v2 *policy sidecar* bound to the same archive SHA.
  Existing shipped ZIP bytes do not change.
- New customer receipts are `technical-receipt-v2.json` and unscored
  `readiness-v2.json`. Legacy v1 receipts remain readable by the single-slot
  state and finished-goods warehouse. A future audit will not overwrite an old
  signed or stored acceptance artifact.
- The cPanel-facing release guard requires measured technical success and
  the v2 exact-artifact ChatGPT review, while its separate rights check and
  production Django approval gate remain binding. The free preview exception
  is unchanged; it still requires distribution rights.
- The VPS-native scheduled service remains the only recurring manufacturer:
  no dependency on GitHub Actions, and no unattended site publication or
  payments are introduced.

## Deployment and proof

The bounded one-shot installer `deploy/install_factory_objective_quality_20261106.sh`
replaces only three required native factory Python modules and the finished-goods
warehouse module if installed. It takes production locks, verifies original
paths and source digests, retains private backups, re-runs one native private
cycle, verifies the objective state and that commercial release is disabled,
then checks the cron hash is unchanged. Failure before verified completion
restores original Python modules. The legacy archives and product passports are
never deleted.

Public publishing on MojPlayWin is a separate deployment/authorization workflow
because its live cPanel Passenger/Django root must be verified independently.
