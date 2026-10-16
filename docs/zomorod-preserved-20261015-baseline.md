# Zomorod Melal — preserved pre-incident site baseline

**Authoritative direction from site owner (16 October 2026):** Preserve and use the original main site version from the backup taken around 01:00 on 15 October 2026, subsequently restored to the live domain. Do not replace it with a new template or reset existing content.

## Confirmed live evidence (read-only inspection; run 38951956032)

- Homepage: `/home/zomorod2/public_html/index.html`, title: `زمرد ملل | پیوند پژوهش، تولید و بازار`, 68,786 bytes, SHA-256 prefix `6c88b4015fa068256c6a`, HTTP 200.
- `/amozeshgah/`: existing live `index.html`, 26,266 bytes, prefix `87f5aedc6bf858b646f1`, HTTP 200.
- `/mohammad/`: existing live `index.html`, 95,599 bytes, prefix `aa574765795cab6c4941`, HTTP 200.
- `/ghanadi/`: existing live `index.html`, 40,645 bytes, prefix `32361747bb8bacc0f309`, HTTP 200.
- `/agriculture/` and `/admin/login/` failed HTTP 500 at inspection; successful internal Django smoke tests are not proof of a working public Passenger runtime.
- A prior 15 October restoration report (GitHub Actions run 38740796800) recorded a 22,519-byte original homepage and the same original site title. **Its bytes differ from the current live 68,786-byte homepage; exact equivalence to the circa-01:00 backup has NOT been proved.** Do not use that older file size to overwrite the current live site.
- Host backup directories `~/.backups/zomorodmelal-root-homepage`, `~/.backups/zomorodmelal-amozeshgah`, and `~/.backups/zomorodmelal-app` exist. The exact circa-01:00 full recovery artifact has not yet been uniquely identified.

## Mandatory release policy

1. Treat the original restored site and all its pages, menus, content, images, links and data as immutable baseline. New features are additive, not a replacement template.
2. Do **not** run a full account, database, document-root or home-directory restore based on an approximate time. First verify the exact backup's manifest, timestamp, hashes, recoverability, and intended scope.
3. Before any main-site change: take a separate restorable snapshot and verify its integrity. Match existing live root files, and reject any unexpected change to `public_html/index.html` or its root `.htaccess`.
4. `/mohammad/`, `/ghanadi/`, `/amozeshgah/` are independent and **must not be touched**. Their 200 health checks must remain passing. Do not alter the separate VPS agent factory.
5. Keep GitHub `Saeit` release scoped to the existing live application's own files. No replacement homepage or mass file sync.
6. Do not announce Passenger resolved or agriculture pages published unless public `/agriculture/`, `/agriculture/genetics/`, images, `/agents/`, and protected sibling routes all pass, with verified backups and a functional rollback.
7. Until the circa-01:00 backup is matched exactly, use the verified currently restored live homepage as the **preservation** reference; do not overwrite it.

## Evidence

- [Read-only baseline inventory and health check](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38951956032)
- [Historical original-homepage restoration attempt](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38740796800)
- [Recent Passenger publish and rollback run](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38950353545)
