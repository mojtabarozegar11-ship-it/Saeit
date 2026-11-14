# Farm Economics — CRM order-inquiry and signed receipt release boundary

**14 November 2026 | branch-only source change | sole agent `mojtaba.bot.ai`**

## Actual defect eliminated in proposed source
The existing `/company/` POST path stored a `CompanyInquiry` but redirected the browser to the company landing page without a durable receipt; invalid submissions were redirected too, losing the visitor's inputs. The public farm product landing page only produced a local JSON/mailto and did **not** create a server-side lead.

This change reuses the **same existing** `CompanyInquiry` model, database and Django admin. It does **not** introduce a duplicate customer database, a new organization bot, a merchant gateway or a second live inbox.

## Delivered source integration
1. New farm-specific Django entry `/company/farm-economics/request/` (GET and POST): real CSRF-protected input form, kind/subject normalized on server, binding to the *existing* Django CRM.
2. Successful valid POST persists the existing CompanyInquiry and redirects to a signed receipt URL; a receipt shows only the allowed coarse stage, never name, email, phone, messages or farm economics.
3. Signed receipt verified using Django signing + secret key and a maximum age of 30 days; forgery/expiry/deleted records produce 404; receipt only allows GET and uses no-store, noindex, no-referrer. The URL does **not** prove contract, price or payment.
4. Invalid POST returns a 400 correction page with bound form values and errors and retains the farm-specific action; no 302 fake success.
5. Explicit consent, honeypot and existing Django CSRF are mandatory; a 15-minute salted-HMAC session retry guard reuses the saved lead receipt for identical submissions. **This is not global atomic de-duplication across browsers.**
6. Existing `/services/` Django template now advertises item 16 linking to the specialized intake route; the existing company-page form also asks for consent. `CompanyInquiryAdmin` displays a farm service classification, while the read-only `python manage.py farm_inquiry_pipeline --days 30` command aggregates saved ZM-FARM CRM leads by stage without disclosing PII.
7. New Django regression tests cover signed status, PII protection, consent, bot form, invalid retries, session duplicates, source-of-truth CRM, farm-specific route, and coarse status; existing six validation tests updated for 400-invalid behavior.

## Real-world boundary and testing honesty
- **65/65 read-only structural source assertions** passed against fetched GitHub branch files. All source writes were read back from the connected GitHub repository. These are not Django end-to-end tests.
- **32 new Django ORM/client tests written, 0/32 executed** because Django/production DB was unavailable in the local execution environment. Six older Django tests modified, also not executed. No CI green assertion.
- No production code, PHP source, cPanel path, MariaDB schema, Django migration or real buyer lead was modified. No new payment/order/contract/revenue created. Source-only branch has no approved merge or deployment.
- Live `https://zomorodmelal.ir/company/` and PHP `/ask-master/` could not be independently fetched in this cycle. The actual active host implementation is UNKNOWN. The existing PHP intake must not be silently disabled or redirected.

## Safe deploy and revenue acceptance gates
1. Identify effective Passenger/cPanel and PHP routing read-only, determine which service forms the real canonical inbox; preserve all existing valid requests and entitlements.
2. Run `python manage.py check` and the actual CRM regression files against the matching Django 5.x/MariaDB test environment, validate routing order, signed token expiration and cross-browser duplicate behavior. Do not send a fake production customer lead.
3. Confirm `/company/farm-economics/request/` GET status and CSRF, POST a genuinely consented customer request only, verify one CompanyInquiry row, receipt URL, admin display and no exposure of contact details in public response.
4. Confirm PHP and Django don't compete for the *same* buyer's inquiry; use one authoritative source of truth and an explicit migration plan if changing canonical route.
5. Independently confirm outbound response policy and company mailbox receipt; never mark mailto click or draft as delivered.
6. Once buyer has consented, prepare exact commercial scope, delivery timeline and approved quote; no sample values represented as customer metrics.
7. Reconcile any eventual authorized payment against an independently confirmed merchant account; only then mark received cash and issue reviewed deliverables.
8. Only after owner-specific approval perform scoped live code release and verify rollback/monitoring. No unauthorized spending, deployment, message sending or signing.

## Real nonbinding commercial progress
A genuine supplier reply was read in the company Gmail mailbox and a **non-sent** threaded reply draft requesting written legal product documents and commercial terms was created. This supplier correspondence is a procurement opportunity, **not** a paying farm economics customer or received revenue.

## Metrics
The number of operationally received ZM-FARM leads, paid contracts, confirmed collected cash, and global company completion are presently **unverified/unknown**. Source changes are not equivalent to live company revenue.
