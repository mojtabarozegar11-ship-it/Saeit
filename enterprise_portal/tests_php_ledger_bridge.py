"""Regression for PHP V7 source-of-truth: aggregate-only, never a second ledger."""
import os
import sqlite3
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .php_ledger_bridge import LedgerUnavailable, read_php_finance_snapshot

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def finance_fixture(db_path):
    with sqlite3.connect(db_path) as connection:
        connection.executescript("""
            CREATE TABLE ledger_accounts (id integer,code text,type text);
            CREATE TABLE journal_entries (id integer,doc_no text,doc_date text);
            CREATE TABLE journal_lines (entry_id integer,account_id integer,debit integer,credit integer,currency text);
            CREATE TABLE invoices (id integer,kind text,currency text,amount integer);
            CREATE TABLE invoice_payments (invoice_id integer,amount integer);
            INSERT INTO journal_entries VALUES (1,'IR-01','2026-11-01'),(2,'US-01','2026-11-01');
            INSERT INTO journal_lines VALUES
              (1,1,10005,0,'IRR'),(1,2,0,10005,'IRR'),
              (2,1,2050,0,'USD'),(2,2,0,2050,'USD');
            INSERT INTO invoices VALUES (1,'sale','IRR',10005),(2,'purchase','USD',2050);
            INSERT INTO invoice_payments VALUES (1,4000);
        """)


class PHPFinanceReadOnlySourceTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "management.sqlite3"
        finance_fixture(self.db_path)

    def test_no_cross_currency_conversion_and_exact_minor_units(self):
        snapshot = read_php_finance_snapshot(self.db_path)
        self.assertEqual(snapshot["document_count"], 2)
        self.assertEqual(snapshot["invoice_count"], 2)
        self.assertEqual(snapshot["imbalance_count"], 0)
        turns = {row["currency"]: row for row in snapshot["turnovers"]}
        self.assertEqual(turns["IRR"]["debit"], "100.05")
        self.assertEqual(turns["USD"]["debit"], "20.50")
        self.assertTrue(all(row["balanced"] for row in snapshot["turnovers"]))
        inv = {row["currency"]: row for row in snapshot["invoices"]}
        self.assertEqual(inv["IRR"]["paid"], "40.00")
        self.assertEqual(inv["IRR"]["outstanding"], "60.05")
        self.assertEqual(inv["USD"]["outstanding"], "20.50")

    def test_read_does_not_modify_database(self):
        before = self.db_path.read_bytes()
        read_php_finance_snapshot(self.db_path)
        self.assertEqual(self.db_path.read_bytes(), before)

    def test_source_never_returns_client_or_employee_details(self):
        snapshot = read_php_finance_snapshot(self.db_path)
        self.assertEqual(set(snapshot), {
            "authority", "document_count", "invoice_count",
            "imbalance_count", "turnovers", "invoices",
        })

    def test_missing_source_is_fail_closed_and_not_created(self):
        missing = Path(self.temp.name) / "missing.sqlite3"
        with self.assertRaises(LedgerUnavailable):
            read_php_finance_snapshot(missing)
        self.assertFalse(missing.exists())

    def test_unconfigured_source_is_fail_closed(self):
        with self.assertRaises(LedgerUnavailable):
            read_php_finance_snapshot("")

    def test_non_php_database_schema_is_rejected(self):
        other = Path(self.temp.name) / "other.sqlite3"
        with sqlite3.connect(other) as connection:
            connection.execute("CREATE TABLE unrelated (id integer)")
        with self.assertRaisesRegex(LedgerUnavailable, "SCHEMA_MISMATCH"):
            read_php_finance_snapshot(other)

    def test_symlink_source_is_rejected(self):
        alias = Path(self.temp.name) / "linked.sqlite3"
        try:
            os.symlink(self.db_path, alias)
        except (OSError, NotImplementedError):
            self.skipTest("symlink not supported")
        with self.assertRaisesRegex(LedgerUnavailable, "PATH_REJECTED"):
            read_php_finance_snapshot(alias)

    def test_detects_per_currency_unbalanced_journal(self):
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "INSERT INTO journal_lines VALUES (2,3,1,0,'IRR')"
            )
        snapshot = read_php_finance_snapshot(self.db_path)
        self.assertEqual(snapshot["imbalance_count"], 1)
        self.assertFalse({r["currency"]: r for r in snapshot["turnovers"]}["IRR"]["balanced"])


@override_settings(COMPANY_OFFICE_REQUIRE_MFA=False, STORAGES=STORAGES)
class PHPFinancePrivateViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="php-finance-owner", email="owner@example.org",
            password="TestPasswordOnly!123",
        )
        self.url = reverse("enterprise_portal:authoritative_finance")

    def test_unauthenticated_cannot_read_even_when_source_missing(self):
        response = self.client.get(self.url, secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/company/office/secure-login/", response["Location"])

    @override_settings(ZM_PHP_LEDGER_READONLY_PATH="")
    def test_authorized_but_unconfigured_is_503_not_django_fallback(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url, secure=True)
        self.assertEqual(response.status_code, 503)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn("django_migrations", response.content.decode("utf-8"))

    def test_department_staff_cannot_see_company_wide_ledger(self):
        from django.contrib.auth.models import Permission
        staff = get_user_model().objects.create_user(
            username="department-accountant", password="TestPasswordOnly!123",
            is_active=True, is_staff=True,
        )
        for code in ("view_businessunit", "view_journalentry"):
            staff.user_permissions.add(Permission.objects.get(
                content_type__app_label="enterprise_portal", codename=code,
            ))
        self.client.force_login(staff)
        with override_settings(ZM_PHP_LEDGER_READONLY_PATH=""):
            response = self.client.get(self.url, secure=True)
        self.assertEqual(response.status_code, 403)

    def test_explicit_source_shows_aggregate_without_source_row_details(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "management.sqlite3"
            finance_fixture(path)
            self.client.force_login(self.user)
            with override_settings(ZM_PHP_LEDGER_READONLY_PATH=str(path)):
                response = self.client.get(self.url, secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "100.05")
        self.assertContains(response, "60.05")
        self.assertIn("no-store", response["Cache-Control"])
