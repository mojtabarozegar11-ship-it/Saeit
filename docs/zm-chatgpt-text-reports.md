# Private ChatGPT action-text reports and scheduled-source import

Route: `/company/office/chatgpt-reports/` — CEO-only HTTPS/MFA, read-only, paginated.
Immutable reports store text, cycle/number, claimed action time, run reference, source
GitHub comment, declared outcome and optional separate human review. This is **not**
a replica of private ChatGPT conversations, nor a bank/payment or deployment audit.

## Existing cycle source

The owner's management task already posts numbered summaries in Saeit issue #1725:
`https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1725`.
The importer only accepts the exact owner username and a first-line header such as:

```text
## گزارش ۰۵-۰۰۰۴ | 2026-11-01 19:08 UTC | ZM-CTRL-20261101-PR1782-CI41340155618
```

It does not accept unnumbered or unrelated comments. No private account, customer,
supplier or payment details may be posted to the public issue. Imported text remains
**unreviewed** and outcome `partial`, regardless of any stronger claims in comments;
a GitHub comment is not independent evidence that a sale or deployment occurred.
Report codes are unique and immutable; collisions from another source cause errors.

## Controlled importer

Preview (read-only, no database writes or model creation):

```sh
python manage.py sync_chatgpt_action_reports
```

After releasing and attesting the *effective* production DB, an authorized
scheduler may run the import exactly once per hourly cycle using the following
requirements **on the trusted server**:

```sh
ZM_CHATGPT_REPORT_SYNC_ENABLED=1 ZM_CHATGPT_REPORT_DB_ATTESTED=1 \
python manage.py sync_chatgpt_action_reports --commit \
  --unit-code='<active validated unit code>' \
  --recorder-id='<existing authorized superuser ID>'
```

Do **not** put tokens, passwords, customer details or other private data in CLI
arguments or GitHub Actions logs. A read-only `ZM_GITHUB_REPORTS_READ_TOKEN`
is optional for Github API throttling; keep it solely in a server secret store.
The command accesses only the fixed GitHub issue API, times out, caps response
size and pages, ignores off-format or other-author posts, redacts stdout to
counts, stops on conflicting report codes, and never contacts financial providers.

**Important:** Both environment switches are operator attestations and NOT
substitutes for actual Passenger effective DB confirmation, independently
restored backup, MFA/RBAC and rollback approval. This PR deliberately does
not install cron or enable `--commit` on the production host. It can be
integrated only through the guarded parent release PR #1774. The existing
ChatGPT hourly schedule remains unchanged.
