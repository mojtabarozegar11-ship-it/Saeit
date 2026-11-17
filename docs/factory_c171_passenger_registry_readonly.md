# C171 — owner cPanel Passenger Application Manager registry, read-only

**Classification:** metadata-only. **NO DEPLOY, NO MySQL, NO DB rows, NO cloud upload, NO charges.**

This C171 probe extends the already authorized [C170 owner process footprint](https://github.com/mojtabarozegar11-ship-it/Saeit/pull/2687), not a new SSH route. The official read-only cPanel UAPI operation `PassengerApps list_applications` returns registered app metadata. It is invoked locally on the owner account after the existing pinned SSH relay verifies the owner and host key.

The UAPI JSON may contain `envvars`, app names, domains and paths. **The entire raw JSON is parsed inside the cPanel owner's process and never written to Actions logs, files or stdout.** The cPanel subprocess has a 512KiB hard output limit, bounded time, stderr suppression and child reaping. The script emits only finite counts and booleans, with no raw paths, app names, envvars, SQL, credentials or customer records. It refuses nonowner execution, malformed JSON, duplicate keys and excess app entries.

For each configured app it classifies **only the registered path** as staging, MojPlayWin webroot, another owner path, outside owner home or unverified; and counts whether the exact known public site domain was registered. **A registration is not a live-worker attestation**, and does not prove the MySQL schema used by current Passenger, a complete media/subdomain inventory, or any recoverable backup.

Only if C171 shows the expected registered path can the next operator constrain the independent **live worker** and **full media** investigation. A missing app registration is not proof the site is inactive (there may be manually configured Passenger apps or missing cPanel feature support). A failed UAPI call never authorizes SQL or production mutation.

The existing current backup gates remain mandatory: independent server-side A/B OAuth, provider-confirmed free quota, recoverable owner private key, verified worker-to-schema and all uploads/subsites scope, consistent bounded encrypted source stream, both remote readbacks and a complete isolated restore.

Official reference: https://api.docs.cpanel.net/cpanel/introduction and https://docs.cpanel.net/knowledge-base/web-services/using-passenger-applications/


## Registered-root metadata extension (owner-only)

Actual C171 cPanel UAPI returned **two enabled, registered target-domain
applications**, both pointing to app roots **under the owner home, but outside
the earlier fixed staging and webroot paths**. Therefore a backup scoped only
to the staging code directory would risk omitting the serving application.
These are registered application paths, **not proof that workers are currently
executing from them**.

The extended census inspects *only* filesystem metadata at each actual
registered owner root. It refuses symbolic links, non-owner paths, group-
writable directory ancestry, unresolved and outside-home paths. For each
admitted root it checks the presence of `passenger_wsgi.py`, `manage.py`,
and direct `media` / `uploads` directories via `lstat` ONLY. No file
contents, config secrets, media names, customer files, DB tables or SQL are
read. All registered paths and per-app identities remain private; public
logs contain only counts. No recursive media backup completeness is claimed.

A missing root or missing immediate media folder does NOT prove no user media
exists. A positive WSGI entrypoint metadata result does NOT attest to a
running Passenger interpreter's live database identity. App/media capture
and the full current backup remain on independent authorization and restore
gates.
