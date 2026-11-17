"""Source safety gates for isolated transactional v1.4.1 virtual tenant books.

These checks compile/inspect code only; NEVER claim real MariaDB, real
Django model installation, actual broker connectivity or paid registration.
"""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT/"prop_firm/plan1_v141_virtual_tenant_models.py"
MIGRATION = ROOT/"prop_firm/migrations/0010_v141_virtual_tenant_books.py"
WRITER = ROOT/"prop_firm/plan1_v141_atomic_virtual_fill_service.py"
REGISTRY = ROOT/"prop_firm/models.py"
PURE = ROOT/"prop_firm/plan1_v141_virtual_tenant_fill_ledger.py"


class VirtualTenantDjangoSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = MODEL.read_text("utf-8")
        cls.migration = MIGRATION.read_text("utf-8")
        cls.writer = WRITER.read_text("utf-8")
        cls.registry = REGISTRY.read_text("utf-8")
        cls.pure = PURE.read_text("utf-8")

    def test_01_model_compiles(self):
        ast.parse(self.model)

    def test_02_migration_compiles(self):
        ast.parse(self.migration)

    def test_03_writer_compiles(self):
        ast.parse(self.writer)

    def test_04_book_is_separate_from_old_funded_accounts(self):
        self.assertIn("class PropV141VirtualBook(models.Model):",self.model)
        self.assertNotIn("class PropAccount",self.model)

    def test_05_event_table_is_append_only_in_intended_writer(self):
        self.assertIn("class PropV141VirtualFill(models.Model):",self.model)
        self.assertIn("PropV141VirtualFill.objects.create(",self.writer)
        self.assertNotIn("PropV141VirtualFill.objects.delete(",self.writer)
        self.assertNotIn("PropV141VirtualFill.objects.update(",self.writer)

    def test_06_book_ownership_binds_to_registered_site_user(self):
        self.assertIn("owner = models.ForeignKey(settings.AUTH_USER_MODEL",self.model)
        self.assertIn("book.owner_id != authenticated_site_user_pk",self.writer)

    def test_07_inactive_owner_fails_closed(self):
        self.assertIn("book.owner.is_active is not True",self.writer)

    def test_08_book_state_is_exactly_one_to_one(self):
        self.assertIn("state = models.OneToOneField(",self.model)
        self.assertIn('to="prop_firm.propv141simstate"',self.migration)

    def test_09_last_stage_checksum_and_sequence_persisted(self):
        for field in ("last_sequence","last_history_sha256",
                      "last_realized_net_usd","last_fully_closed_count"):
            self.assertIn(field,self.model)
            self.assertIn(field,self.migration)
            self.assertIn(field,self.writer)

    def test_10_unlocked_stage_cannot_exceed_two(self):
        self.assertIn("mp_v141_virt_stage_range",self.model)
        self.assertIn("mp_v141_virt_stage_range",self.migration)

    def test_11_event_global_id_is_unique(self):
        self.assertIn("event_id = models.CharField(max_length=96, unique=True)",self.model)
        self.assertIn('("event_id", models.CharField(max_length=96, unique=True))',self.migration)

    def test_12_event_sequence_unique_per_book(self):
        self.assertIn('fields=["book", "sequence"]',self.model)
        self.assertIn('fields=["book", "sequence"]',self.migration)

    def test_13_append_under_book_lock(self):
        self.assertIn("@transaction.atomic",self.writer)
        self.assertIn(".select_for_update().get(pk=trusted_book_pk)",self.writer)

    def test_14_full_historical_replay_before_append(self):
        self.assertIn("_book_snapshot(book, past_events, now=server_now)",self.writer)
        self.assertIn("stored virtual book fails immutable replay consistency",self.writer)

    def test_15_atomic_event_create_and_book_save(self):
        self.assertIn("PropV141VirtualFill.objects.create(",self.writer)
        self.assertIn('book.save(update_fields=[',self.writer)

    def test_16_old_source_events_not_reconsumed_across_traders(self):
        self.assertIn("PropV141VirtualFill.objects.filter(event_id=fill.event_id).exists()",self.writer)
        self.assertIn("source event ID already consumed by another customer",self.writer)

    def test_17_same_event_retry_checks_exact_row(self):
        self.assertIn("_existing_row_matches(book, old, fill)",self.writer)
        self.assertIn("idempotent_replay=True",self.writer)

    def test_18_signed_source_ingress_with_server_owned_key(self):
        self.assertIn("server_owned_hmac_keys.get(book.state.trusted_key_id)",self.writer)
        self.assertIn("hmac.compare_digest(required_sig, ingress_signature_sha256)",self.writer)

    def test_19_key_length_minimum_32_bytes(self):
        self.assertIn("len(key) < 32",self.writer)

    def test_20_signed_source_scoped_to_book_and_user(self):
        self.assertIn("book_pk=book.pk",self.writer)
        self.assertIn("owner_pk=str(book.owner_id)",self.writer)
        self.assertIn("expected_contract=book.terms_sha256",self.writer)

    def test_21_wrong_buyer_contract_fails_closed(self):
        self.assertIn("book.terms_sha256 != terms.contract_candidate_sha256",self.writer)
        self.assertIn("book.terms_sha256 != book.state.terms_sha256",self.writer)

    def test_22_stage_two_requires_signed_checkpoint_metadata(self):
        self.assertIn("book.state.last_phase_one_accepted_at is None",self.writer)
        self.assertIn("book.state.last_phase_one_evidence_sha256",self.writer)

    def test_23_event_schema_requires_positive_quantity_price(self):
        for key in ("mp_v141_virt_positive_qty","mp_v141_virt_positive_price"):
            self.assertIn(key,self.model)
            self.assertIn(key,self.migration)

    def test_24_negative_event_fee_rejected_by_db_constraint(self):
        self.assertIn("mp_v141_virt_nonneg_fee",self.model)
        self.assertIn("mp_v141_virt_nonneg_fee",self.migration)

    def test_25_exact_decimal_eight_place_realized_pnl(self):
        self.assertIn("max_digits=24, decimal_places=8",self.model)
        self.assertIn("max_digits=24, decimal_places=8",self.migration)

    def test_26_no_wallet_broker_executor_or_payment_endpoint(self):
        tree=ast.parse(self.writer)
        imports={x.module for x in ast.walk(tree) if isinstance(x,ast.ImportFrom)}
        self.assertNotIn("core.views",imports)
        self.assertNotIn("prop_firm.allocation_service",imports)
        self.assertNotIn("django.urls",imports)
        self.assertNotIn("requests",imports)
        self.assertNotIn("httpx",imports)

    def test_27_persistent_result_flags_never_grant_cash_or_execution(self):
        for flag in ("live_broker_orders_authorized: bool = False",
                     "customer_fee_collection_authorized: bool = False",
                     "payouts_authorized: bool = False"):
            self.assertIn(flag,self.writer)

    def test_28_migration_depends_on_exact_0009(self):
        self.assertIn('("prop_firm", "0009_v141_sim_replay_journal")',self.migration)

    def test_29_migration_has_no_historical_alter_remove_data_operations(self):
        for forbidden in ("migrations.AlterModel", "migrations.AlterField",
                          "migrations.RemoveField", "migrations.RunPython",
                          "migrations.RunSQL", "migrations.DeleteModel"):
            self.assertNotIn(forbidden,self.migration)

    def test_30_new_models_registered_but_old_allocation_untouched(self):
        self.assertIn("from .plan1_v141_virtual_tenant_models import",self.registry)
        self.assertIn("PropV141VirtualBook, PropV141VirtualFill",self.registry)

    def test_31_replay_rejects_cross_tenant_identity(self):
        self.assertIn("cross-tenant or foreign-source virtual fill",self.pure)
        self.assertIn("global source event reused or changed",self.pure)

    def test_32_no_real_broker_account_ref_in_per_user_ledger(self):
        self.assertNotIn("company_broker_ref",self.model)
        self.assertNotIn("company_broker_ref",self.writer)

    def test_33_real_django_migration_not_claimed_by_source(self):
        self.assertIn("DO NOT APPLY",self.migration)
        self.assertIn("untested on real MariaDB",self.writer)

    def test_34_no_public_user_supplied_book_id(self):
        self.assertIn("Never pass a client-supplied book PK",self.writer)
        self.assertNotIn("request.POST",self.writer)
        self.assertNotIn("request.data",self.writer)


    def test_35_accepted_stage_one_cannot_take_new_signed_fills(self):
        self.assertIn("stage-one virtual history already accepted and frozen",self.writer)

    def test_36_stage_two_event_must_be_after_server_transition(self):
        self.assertIn("fill.executed_at_utc < started",self.writer)
        self.assertIn("book.state.last_phase_two_started_at",self.writer)

    def test_37_completed_stage_two_rejects_new_event(self):
        self.assertIn("book.state.last_phase_two_completed_at is not None",self.writer)
        self.assertIn("stage-two event outside independently recorded active stage",self.writer)


if __name__=="__main__":
    unittest.main()
