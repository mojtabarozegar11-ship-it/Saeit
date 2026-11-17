# C171 — owner cPanel Passenger Application Manager registry, read-only

**Classification:** metadata-only. **NO DEPLOY, NO MySQL, NO DB rows, NO cloud upload, NO charges.**

This C171 probe extends the already authorized [C170 owner process footprint](https://github.com/mojtabarozegar11-ship-it/Saeit/pull/2687), not a new SSH route. The official read-only cPanel UAPI operation `PassengerApps list_applications` returns registered app metadata. It is invoked locally on the owner account after the existing pinned SSH relay verifies the owner and host key.

The UAPI JSON may contain `envvars`, app names, domains and paths. **The entire raw JSON is parsed inside the cPanel owner's process and never written to Actions logs, files or stdout.** The cPanel subprocess has a 512KiB hard output limit, bounded time, stderr suppression and child reaping. The script emits only finite counts and booleans, with no raw paths, app names, envvars, SQL, credentials or customer records. It refuses nonowner execution, malformed JSON, duplicate keys and excess app entries.

For each configured app it classifies **only the registered path** as staging, MojPlayWin webroot, another owner path, outside owner home or unverified; and counts whether the exact known public site domain was registered. **A registration is not a live-worker attestation**, and does not prove the MySQL schema used by current Passenger, a complete media/subdomain inventory, or any recoverable backup.

Only if C171 shows the expected registered path can the next operator constrain the independent **live worker** and **full media** investigation. A missing app registration is not proof the site is inactive (there may be manually configured Passenger apps or missing cPanel feature support). A failed UAPI call never authorizes SQL or production mutation.

The existing current backup gates remain mandatory: independent server-side A/B OAuth, provider-confirmed free quota, recoverable owner private key, verified worker-to-schema and all uploads/subsites scope, consistent bounded encrypted source stream, both remote readbacks and a complete isolated restore.

Official reference: https://api.docs.cpanel.net/cpanel/introduction and https://docs.cpanel.net/knowledge-base/web-services/using-passenger-applications/
