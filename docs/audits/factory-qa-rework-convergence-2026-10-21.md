# 2026-10-21 factory QA/rework convergence (technical only)

## Corrected operational faults
1. Real native archives with 97 or 145 files were incorrectly held by an 80-member prescreen limit. The new prescreen allows up to **256 members** while preserving the **25 MiB compressed archive**, **100 MiB uncompressed contents**, source and archive SHA, CRC, traversal, symlink and unique-name restrictions. This is a private engineering-screen correction, **not** an F14/F28 expert-quality endorsement or a commercial license.
2. The F14/F28 independent critic previously returned a red GitHub workflow when it correctly refused release. The workflow now verifies the **specific intentional exit code 2** and validates the complete blocked-verdict JSON before reporting a successful *safety control*. Unsafe products remain blocked.
3. MojPlayWin Stage1 packaging on VPS staged the current `factory_product_maker.py` without its private personal-owner passport dependency. Transfer/install now includes the exact `factory_personal_owner_passport_policy_20261020.py`, with digest verification. No owner rights, legal license, money, publication or customer access is fabricated.

## Tests and deployment
- `python3 -m unittest tests.test_factory_owner_review_packets_20261020 tests.test_mpw_factory_stage1_technical_repair`
- Test/QA is required before VPS-side installation and production evidence must be read back.
- The Stage1 courier is correctly **skipped for pull requests**. A green preflight on a PR is not proof of VPS mutation.
- Changes do not patch scientific datasets, rebuild the original ZIPs, remove Stage1 review returns, bypass resource caps or approve a product.

## Remaining independent gates
- Source provenance for historical goods, rights for each third-party component, expert review, usable tested buyer artifacts, market acceptance, properly configured merchant/payment identity, real end-to-end purchase/receipt/refund/download, and backups/restores are still separately required.
- No 40/40 live production or 100/100 quality/commerce claim without verified production evidence.
