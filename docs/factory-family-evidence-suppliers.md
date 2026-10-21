# Per-family evidence suppliers

The family registry has 40 production families. This module provisions one
separate evidence supplier identity per family and creates a version-bound
intake checklist from that family's specialist tests.

Evidence requests are append-only and have no fixed item-count cap. Each
evidence item must still be tied to the exact source and artifact hashes and
must retain provenance. The registry deliberately reports every supplier as
`WAITING_FOR_CONNECTED_SOURCES` until a real source adapter is connected.
It does not manufacture evidence, certify reviewers, award quality points, or
authorize release.

Run the registry contract:

```sh
python3 -B scripts/factory_family_evidence_suppliers_v1.py \
  --families factory_config/forty_families.json \
  --output /tmp/family-evidence-suppliers.json
```

Create a version-specific evidence intake for one family by adding
`--family-id F28 --source-sha256 <64-hex> --artifact-sha256 <64-hex>`.
