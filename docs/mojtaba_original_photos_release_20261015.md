# Mojtaba Roozegar — owner-supplied 10-photo gallery (staged)

This branch is **NOT a live deployment**. The site at `/mojtaba.roozegar/` belongs to the existing, independent V17 Django app on cPanel. Its root, base template, routing and SEO must remain intact.

## Confirmed by real GitHub Actions inspection

- Read-only SSH inventory: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38773081397 (success).
- Verified app: `/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17`.
- Home template: `templates/personal_site/core/home.html`.
- Existing dedicated gallery route/template is separate. This change only adds a rich photo/story section to the existing home page.

## Important: original photos are not in this Git branch yet

The 10 user-provided individual photos currently exist in a ZIP package in the user's ChatGPT Library, **not** in GitHub or on cPanel. The connector does not automatically transfer ChatGPT Library attachments to GitHub Actions. Do **not** run installation or claim publication before the actual photo bytes have been securely staged on cPanel or committed into the repository in `assets/mojtaba_20261015/`.

File names: `photo-01.jpg` through `photo-10.jpg`. Their SHA-256 digests are pinned in `scripts/mojtaba_personal_photo_gallery.py`. Never substitute stock or generated photographs.

## Safe procedure, after photo bytes are available

1. Revalidate the production path with a read-only GitHub Actions probe.
2. Place photos in a **new private staging directory**, verify exact SHA-256 values using the script:
   `python3 scripts/mojtaba_personal_photo_gallery.py check --photo-dir /path/to/staged/images`
3. Inspect diff; verify all 10 static targets and that `staticfiles` can actually serve these paths in the V17 app.
4. Only then run `install` over the verified app via the pinned GitHub → VPS → cPanel SSH relay; it backs up the existing home template and touches no other site's root.
5. Run the appropriate V17 staticfiles collect step **only after checking** its settings; verify HTTP 200 for homepage and each of 10 images, no changes to canonical/robots/structured data, and unchanged root status for Zomorod Melal and MojPlayWin.
6. Roll back immediately from the reported backup if live or accessibility checks fail.

No migration, DNS edit, public upload, payment edit, V17 URL change, or overwriting of existing home media should be performed as part of this staging PR.
