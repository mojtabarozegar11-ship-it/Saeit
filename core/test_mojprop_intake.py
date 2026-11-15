import json
import re
from pathlib import Path

from django.conf import settings
from django.test import Client, TestCase, override_settings

from .models import MojPropRequest


@override_settings(ALLOWED_HOSTS=[
    "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir", "evil.example"
])
class MojPropIntakeTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        response = self.client.get(
            "/moj-prop-intake/", secure=True, HTTP_HOST="mojplaywin.com",
        )
        self.assertEqual(response.status_code, 200)
        self.csrf_token = response.json()["csrf_token"]

    def payload(self, **overrides):
        value = {
            "name": "Moj Prop Client",
            "email": "client@farmco.org",
            "service": "brief",
            "horizon": "week",
            "notes": "Need a dated gold market brief for educational review.",
            "consent": True,
            "website": "",
        }
        value.update(overrides)
        return value

    def post(self, value):
        return self.client.post(
            "/moj-prop-intake/",
            data=json.dumps(value),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
            HTTP_HOST="mojplaywin.com",
            HTTP_ORIGIN="https://mojplaywin.com",
            REMOTE_ADDR="198.51.100.40",
            secure=True,
        )

    def test_valid_request_is_stored_for_manual_review(self):
        response = self.post(self.payload())
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["request_id"].startswith("MOJPROP-"))
        record = MojPropRequest.objects.get(request_id=body["request_id"])
        self.assertEqual(record.status, "new")
        self.assertEqual(record.route, "brief")
        self.assertEqual(record.email, "client@farmco.org")

    def test_invalid_consent_is_rejected(self):
        response = self.post(self.payload(consent=False))
        self.assertEqual(response.status_code, 400)
        self.assertIn("consent", response.json()["fields"])
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_honeypot_is_rejected(self):
        response = self.post(self.payload(website="bot-filled"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_invalid_email_is_rejected(self):
        response = self.post(self.payload(email="not-an-email"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json()["fields"])

    def test_real_api_route_outside_passenger_disabled_static_directory(self):
        from django.urls import resolve, reverse
        from core.mojprop_views import mojprop_intake
        self.assertEqual(reverse("mojprop_intake"), "/moj-prop-intake/")
        self.assertIs(resolve("/moj-prop-intake/").func, mojprop_intake)
        self.assertIs(resolve("/moj-prop/intake/").func, mojprop_intake)
        source = (Path(settings.BASE_DIR) / "templates/moj-prop-v4/index.html").read_text("utf-8")
        self.assertIn("const endpoint='/moj-prop-intake/';", source)
        self.assertNotIn("const endpoint='/moj-prop/intake/';", source)
        installer = (Path(settings.BASE_DIR) / "scripts/deploy_mojplaywin_moj_prop.py").read_text("utf-8")
        self.assertIn('PUBLIC_HTACCESS = "PassengerEnabled off', installer)

    def test_catalog_release_requires_public_api_before_static_changes(self):
        workflow = (Path(settings.BASE_DIR) /
                    ".github/workflows/mojplaywin-moj-prop-deploy.yml").read_text("utf-8")
        upload = workflow.index("Upload isolated Moj Prop package")
        backend = workflow.index("Deploy Moj Prop intake backend with backup and migration")
        preflight = workflow.index("Confirm live Django request API")
        static = workflow.index("Update only /moj-prop/ commercial catalog")
        self.assertLess(upload, backend)
        self.assertLess(backend, preflight)
        self.assertLess(preflight, static)
        self.assertNotIn("core/migrations/0042_alter_mojproprequest_source.py", workflow)
        self.assertIn("https://mojplaywin.com/moj-prop-intake/", workflow)
        self.assertIn("MOJ_PROP_LIVE_INTAKE_API_PREFLIGHT=PASS", workflow)
        self.assertIn('response.get("service") != "moj-prop-intake"', workflow)

    def test_live_graph_dependency_joiner_preserves_every_leaf(self):
        from scripts.deploy_mojplaywin_moj_prop_backend import format_core_migration_dependencies
        value = format_core_migration_dependencies((
            "0049_mpw_guest_email_recovery", "0040_commercefunnelevent",
        ))
        self.assertIn('("core", "0049_mpw_guest_email_recovery")', value)
        self.assertIn('("core", "0040_commercefunnelevent")', value)
        self.assertEqual(value.count('("core", '), 2)

    def test_live_graph_dependency_joiner_refuses_untrusted_graph(self):
        from scripts.deploy_mojplaywin_moj_prop_backend import format_core_migration_dependencies
        for leaves in ((), ("bad",),
                       ("0049_mpw_guest_email_recovery", "0049_mpw_guest_email_recovery"),
                       ("0041_mojprop_request",), ("0042_alter_mojproprequest_source",)):
            with self.subTest(leaves=leaves), self.assertRaises(RuntimeError):
                format_core_migration_dependencies(leaves)

    def test_cpanel_uses_actual_core_graph_and_refuses_migration_overwrite(self):
        script = (Path(settings.BASE_DIR) /
                  "scripts/deploy_mojplaywin_moj_prop_backend.py").read_text("utf-8")
        self.assertIn("live_core_migration_leaves()", script)
        self.assertIn("MOJ_PROP_MIGRATION_PARENTS=", script)
        self.assertIn('if target.exists():', script)
        self.assertIn("MOJ_PROP_MIGRATION_ALREADY_INSTALLED=PASS", script)
        self.assertIn("mojprop_migration_operations_signature(current)", script)
        self.assertNotIn('if candidates else "0001_initial"', script)
        self.assertNotIn("install_join_migration", script)
        self.assertIn("def restart_passenger()", script)

    def test_existing_cpanel_0041_is_idempotent_only_when_schema_matches(self):
        from scripts.deploy_mojplaywin_moj_prop_backend import (
            mojprop_migration_operations_signature,
        )
        text = (Path(settings.BASE_DIR) /
                "core/migrations/0041_mojprop_request.py").read_text("utf-8")
        private = text.replace(
            '"0040_commercefunnelevent"', '"0049_mpw_guest_email_recovery"',
        )
        self.assertEqual(
            mojprop_migration_operations_signature(text),
            mojprop_migration_operations_signature(private),
        )
        changed = private.replace(
            '("source", models.CharField(default="moj-prop", max_length=80))',
            '("source", models.CharField(default="tampered", max_length=80))',
        )
        self.assertNotEqual(
            mojprop_migration_operations_signature(text),
            mojprop_migration_operations_signature(changed),
        )

    def test_existing_cpanel_migration_invalid_parent_fails_closed(self):
        from scripts.deploy_mojplaywin_moj_prop_backend import (
            mojprop_migration_operations_signature,
        )
        text = (Path(settings.BASE_DIR) /
                "core/migrations/0041_mojprop_request.py").read_text("utf-8")
        malformed = (
            text.replace('("core", "0040_commercefunnelevent")',
                         '("different_app", "0040_commercefunnelevent")'),
            text.replace('("core", "0040_commercefunnelevent")',
                         '("core", "not_a_valid_migration")'),
        )
        for case in malformed:
            with self.subTest(value=case[:50]), self.assertRaises(RuntimeError):
                mojprop_migration_operations_signature(case)

    def test_public_core_source_field_matches_existing_0041(self):
        migration = (Path(settings.BASE_DIR) /
                     "core/migrations/0041_mojprop_request.py").read_text("utf-8")
        self.assertIn('("source", models.CharField(default="moj-prop", max_length=80))', migration)
        self.assertFalse(MojPropRequest._meta.get_field("source").blank)
        self.assertIn('("core", "0040_commercefunnelevent")', migration)
        self.assertFalse((Path(settings.BASE_DIR) /
                          "core/migrations/0042_alter_mojproprequest_source.py").exists())

    def test_cpanel_deploy_logs_never_dump_raw_process_arguments_or_uapi_secrets(self):
        script = (Path(settings.BASE_DIR) /
                  "scripts/deploy_mojplaywin_moj_prop_backend.py").read_text("utf-8")
        self.assertNotIn('print("MOJ_PROP_PROCESS=" + line[:500])', script)
        self.assertNotIn('print("MOJ_PROP_UAPI_LIST=" + result.stdout', script)
        self.assertNotIn('print("MOJ_PROP_SELECTOR_GET=" + result.stdout', script)

    def test_release_rollback_covers_preflight_and_static_errors(self):
        workflow = (Path(settings.BASE_DIR) /
                    ".github/workflows/mojplaywin-moj-prop-deploy.yml").read_text("utf-8")
        self.assertIn("Roll back Moj Prop backend if verification fails", workflow)
        self.assertIn("if: failure() && steps.backend.outcome == 'success'", workflow)
        self.assertIn("if: failure() && steps.deploy.outcome == 'success' && steps.smoke.outcome == 'failure'", workflow)

    def test_real_public_form_horizon_options_match_backend_contract(self):
        html = (Path(settings.BASE_DIR) / "templates/moj-prop-v4/index.html").read_text("utf-8")
        fragment = re.search(r'<select id="horizon">(.*?)</select>', html)
        self.assertIsNotNone(fragment)
        options = re.findall(r'<option value="([a-z]+)">([^<]+)</option>', fragment.group(1))
        self.assertEqual(options, [
            ("urgent", "Today / urgent"), ("week", "This week"),
            ("month", "This month"), ("review", "Initial review only"),
        ])
        self.assertIn("const horizon=document.getElementById('horizon').value;", html)
        self.assertIn("body:JSON.stringify({name,email,service,horizon,notes,website,consent:", html)

    def test_all_four_real_form_horizons_create_reviewable_request(self):
        for i, horizon in enumerate(("urgent", "week", "month", "review")):
            with self.subTest(horizon=horizon):
                answer = self.post(self.payload(
                    horizon=horizon, email=f"buyer{i}@farmco.org",
                ))
                self.assertEqual(answer.status_code, 201)
                self.assertEqual(
                    MojPropRequest.objects.get(request_id=answer.json()["request_id"]).horizon,
                    horizon,
                )
        self.assertEqual(MojPropRequest.objects.count(), 4)

    def test_display_horizon_text_cannot_silently_be_saved(self):
        response = self.post(self.payload(horizon="This week"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("horizon", response.json()["fields"])
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_api_requires_owned_https_host_for_get_and_post(self):
        unguarded = Client(enforce_csrf_checks=False)
        for host, secure in (("evil.example", True), ("zomorodmelal.ir", True),
                             ("mojplaywin.com", False)):
            with self.subTest(host=host, secure=secure):
                self.assertEqual(self.client.get(
                    "/moj-prop-intake/", HTTP_HOST=host, secure=secure,
                ).status_code, 404)
                self.assertEqual(unguarded.post(
                    "/moj-prop-intake/", data=json.dumps(self.payload()),
                    content_type="application/json", HTTP_HOST=host,
                    HTTP_X_CSRFTOKEN=self.csrf_token, secure=secure,
                ).status_code, 404)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_x_real_ip_forgery_does_not_reset_ip_rate_limit(self):
        for i in range(5):
            response = self.client.post(
                "/moj-prop-intake/", data=json.dumps(self.payload(
                    email=f"client{i}@farmco.org",
                )),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=self.csrf_token, HTTP_HOST="mojplaywin.com",
                HTTP_ORIGIN="https://mojplaywin.com",
                REMOTE_ADDR="203.0.113.48", HTTP_X_REAL_IP=f"198.51.100.{i + 1}",
                secure=True,
            )
            self.assertEqual(response.status_code, 201)
        blocked = self.client.post(
            "/moj-prop-intake/", data=json.dumps(self.payload(email="new@farmco.org")),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf_token,
            HTTP_HOST="mojplaywin.com", HTTP_ORIGIN="https://mojplaywin.com",
            REMOTE_ADDR="203.0.113.48", HTTP_X_REAL_IP="198.51.100.200",
            secure=True,
        )
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked["Retry-After"], "600")
        self.assertEqual(MojPropRequest.objects.count(), 5)
        self.assertEqual(MojPropRequest.objects.values("ip_hash").distinct().count(), 1)

    def test_oversized_request_fails_without_row_creation(self):
        response = self.post(self.payload(notes="N" * 20000))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_overlong_customer_data_is_rejected_not_truncated(self):
        for field, value in (("email", "a" * 251 + "@farmco.org"),
                             ("name", "A" * 201),
                             ("notes", "N" * 5001)):
            with self.subTest(field=field):
                response = self.post(self.payload(**{field: value}))
                self.assertEqual(response.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_reserved_fake_mailboxes_cannot_enter_commercial_pipeline(self):
        for email in ("fake@example.com", "buyer@example.org", "x@example.net",
                      "a@guest.mojplaywin.com", "a@test.invalid", "a@demo.local"):
            with self.subTest(email=email):
                answer = self.post(self.payload(email=email))
                self.assertEqual(answer.status_code, 400)
                self.assertIn("email", answer.json()["fields"])
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_duplicate_json_claim_cannot_choose_second_value(self):
        document = json.dumps(self.payload())
        document = document.replace('"horizon": "week"',
                                    '"horizon": "urgent", "horizon": "week"')
        answer = self.client.post(
            "/moj-prop-intake/", data=document,
            content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf_token,
            HTTP_HOST="mojplaywin.com", HTTP_ORIGIN="https://mojplaywin.com",
            REMOTE_ADDR="198.51.100.40", secure=True,
        )
        self.assertEqual(answer.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_unexpected_field_and_bad_json_types_fail_closed(self):
        for case in (
            dict(self.payload(), price_paid=True),
            dict(self.payload(), name=200),
            dict(self.payload(), notes=None),
            dict(self.payload(), website={"hidden": "bot"}),
        ):
            with self.subTest(case=repr(case)[:60]):
                answer = self.post(case)
                self.assertEqual(answer.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_no_csrf_header_no_manual_review_row(self):
        c = Client(enforce_csrf_checks=True)
        response = c.post(
            "/moj-prop-intake/", data=json.dumps(self.payload()),
            content_type="application/json", HTTP_HOST="mojplaywin.com",
            secure=True,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_new_client_uuidv4_submission_has_an_opaque_receipt(self):
        import uuid
        submission_id = str(uuid.uuid4())
        reply = self.post(self.payload(submission_id=submission_id))
        self.assertEqual(reply.status_code, 201)
        self.assertFalse(reply.json()["replayed"])
        request_id = reply.json()["request_id"]
        self.assertTrue(request_id.startswith("MOJPROP-I-"))
        self.assertNotIn(submission_id, request_id)
        self.assertLessEqual(len(request_id), 40)
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_same_browser_retry_recovers_receipt_without_duplicate_lead(self):
        import uuid
        form = self.payload(submission_id=str(uuid.uuid4()))
        original = self.post(form)
        self.assertEqual(original.status_code, 201)
        retry = self.post(form)
        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.json()["replayed"])
        self.assertEqual(retry.json()["request_id"], original.json()["request_id"])
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_exact_retry_remains_recoverable_after_new_request_throttle(self):
        import uuid
        form = self.payload(submission_id=str(uuid.uuid4()))
        original = self.post(form)
        self.assertEqual(original.status_code, 201)
        for index in range(4):
            response = self.post(self.payload(email=f"buyer{index}@farmco.org"))
            self.assertEqual(response.status_code, 201)
        limited = self.post(self.payload(
            email="new@farmco.org", submission_id=str(uuid.uuid4()),
        ))
        self.assertEqual(limited.status_code, 429)
        retry = self.post(form)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json()["request_id"], original.json()["request_id"])
        self.assertEqual(MojPropRequest.objects.count(), 5)

    def test_reusing_client_uuid_for_changed_buyer_or_service_returns_conflict(self):
        import uuid
        token = str(uuid.uuid4())
        self.assertEqual(self.post(self.payload(submission_id=token)).status_code, 201)
        for change in (
            {"name": "Different Client"},
            {"email": "new@farmco.org"},
            {"service": "audit"},
            {"horizon": "month"},
            {"notes": "A different valid research request for customers."},
        ):
            with self.subTest(change=change):
                answer = self.post(self.payload(submission_id=token, **change))
                self.assertEqual(answer.status_code, 409)
                self.assertFalse(answer.json()["ok"])
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_invalid_or_non_random_retry_keys_do_not_create_leads(self):
        import uuid
        for bad in ("", "123", "x" * 36, str(uuid.uuid1()), str(uuid.uuid4()) + "X",
                    123, None, False, {"id": "fake"}):
            with self.subTest(bad=repr(bad)):
                result = self.post(self.payload(submission_id=bad))
                self.assertEqual(result.status_code, 400)
                self.assertIn("submission_id", result.json().get("fields", {}))
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_unique_new_browser_keys_can_submit_distinct_real_requests(self):
        import uuid
        numbers = []
        for index in range(2):
            result = self.post(self.payload(submission_id=str(uuid.uuid4())))
            self.assertEqual(result.status_code, 201)
            numbers.append(result.json()["request_id"])
        self.assertEqual(len(set(numbers)), 2)
        self.assertEqual(MojPropRequest.objects.count(), 2)

    def test_existing_live_legacy_browser_without_retry_key_still_works(self):
        result = self.post(self.payload())
        self.assertEqual(result.status_code, 201)
        self.assertFalse(result.json()["replayed"])
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_actual_html_has_stable_retry_and_real_contact_permission(self):
        source = (Path(settings.BASE_DIR) /
                  "templates/moj-prop-v4/index.html").read_text("utf-8")
        self.assertIn("submission_id:submissionId", source)
        self.assertIn("crypto.randomUUID()", source)
        self.assertIn("crypto.getRandomValues", source)
        self.assertIn("if(!submissionId) submissionId=secureSubmissionId()", source)
        self.assertIn('minlength="20" maxlength="5000"', source)
        self.assertIn('maxlength="254"', source)
        self.assertIn("I agree to be contacted at this email about this request only", source)
        self.assertIn('role="status" aria-live="polite"', source)
        self.assertIn("Submission may have arrived.", source)

    def test_owner_only_status_not_a_payment_or_trade(self):
        from core.models import Order, PaymentIntent
        answer = self.post(self.payload())
        self.assertEqual(answer.status_code, 201)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(PaymentIntent.objects.count(), 0)
        self.assertEqual(MojPropRequest.objects.get().status, "new")
        self.assertEqual(answer.json()["next_step"], "manual_review")

    def test_csrf_and_receipt_response_are_private_not_cached(self):
        response = self.client.get(
            "/moj-prop-intake/", secure=True, HTTP_HOST="mojplaywin.com",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("private, no-store", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        result = self.post(self.payload())
        self.assertEqual(result["Referrer-Policy"], "same-origin")

