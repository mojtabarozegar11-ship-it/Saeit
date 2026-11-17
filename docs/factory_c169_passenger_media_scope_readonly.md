# C169 — Production backup admission: current Passenger source and media-scope evidence

**DRAFT / NO DEPLOY / NO LIVE SQL DUMP / NO CUSTOMER ROWS / NO CHARGES**

This script is an additive, owner-scoped diagnostic only. It inspects the fixed cPanel owner-staging Django settings and bounded metadata of six fixed common media directories; reads only a bounded AST of the existing Passenger WSGI entrypoint and no customer data. Reports finite statuses/counters, never paths, file names, credentials, database names or customer identifiers. Does not import Passenger WSGI, attach to live workers, open DB connections, export SQL, process webhooks or change permissions. Uses one GitHub self-hosted factory runner and existing owner pinned SSH relay.

C118 earlier established a WSGI file with staging path literal. C161 earlier established configured MySQL and Django FileSystemStorage with `MEDIA_ROOT` unset; C168 established 101/101 InnoDB storage engines, but only on owner staging. None of those facts proves the currently-running Passenger process's live DB identity, full media scope, or backup consistency.

The six candidate paths are all under a fixed owner home. Every scan examines at most 128 immediate entries, does not recurse, refuses symlinked parents and reports no names or content. Unknown, missing, unsafe, over-limit and nonfilesystem paths are explicitly unverified. **No metadata scan grants permission to delete backups or run a current 16.68GB DB dump**. The result can be used to define a safer inventory plan; independent source+media discovery, provider quota, encrypted transfer, and isolated service restore remain separate gates.

There is no GitHub-hosted job in this workflow; self-hosted GitHub Action usage is currently free under the GitHub's announced postponement, though owner infrastructure usage still applies. No new paid resources requested.

C169 v2 recognizes direct WSGI `application` bindings **and imported bindings** (`from config.wsgi import application` or aliased import). A missing direct assignment must never be interpreted as a missing live WSGI application. Thirty offline cases checked before remote cPanel read.
