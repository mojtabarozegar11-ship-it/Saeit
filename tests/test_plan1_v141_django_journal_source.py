"""STATIC checks for the v1.4.1 Django journal and migration.

These parse source and check safety invariants only; they are NOT database
migration execution tests or evidence of a deployed MariaDB service.
"""
import ast
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
FILES={
 "models":ROOT/"prop_firm/plan1_v141_persistence_models.py",
 "registry":ROOT/"prop_firm/models.py",
 "migration":ROOT/"prop_firm/migrations/0009_v141_sim_replay_journal.py",
 "service":ROOT/"prop_firm/plan1_v141_atomic_receipt_service.py",
 "policy":ROOT/"prop_firm/plan1_v141_replay_journal_policy.py",
}
def source(name):
    return FILES[name].read_text("utf-8")


class DjangoReplayJournalSourceChecks(unittest.TestCase):
    def test_01_model_compiles_as_python(self):
        compile(source("models"),str(FILES["models"]),"exec")

    def test_02_migration_compiles_as_python(self):
        compile(source("migration"),str(FILES["migration"]),"exec")

    def test_03_transactional_service_compiles_as_python(self):
        compile(source("service"),str(FILES["service"]),"exec")

    def test_04_policy_compiles_as_python(self):
        compile(source("policy"),str(FILES["policy"]),"exec")

    def test_05_isolated_models_registered_with_django(self):
        self.assertIn("from .plan1_v141_persistence_models import",source("registry"))
        self.assertIn("PropV141SimState, PropV141SimReceipt",source("registry"))

    def test_06_migration_chains_off_latest_parent_0008(self):
        self.assertIn('("prop_firm", "0008_prospect_contact_intake")',source("migration"))

    def test_07_migration_creates_only_two_new_tables(self):
        x=source("migration")
        self.assertEqual(x.count("migrations.CreateModel("),2)
        self.assertIn('name="PropV141SimState"',x)
        self.assertIn('name="PropV141SimReceipt"',x)

    def test_08_does_not_modify_historical_customer_models(self):
        x=source("migration")
        for forbidden in ("migrations.AlterField","migrations.RemoveField",
                          "migrations.AddField","migrations.DeleteModel",
                          "migrations.RunPython","migrations.RunSQL",
                          "PropChallengeEnrollment","PropSocialEvidence"):
            self.assertNotIn(forbidden,x)

    def test_09_journal_per_challenge_has_unique_reference(self):
        self.assertIn("unique=True",source("models"))
        self.assertIn('challenge_ref = models.CharField(max_length=64, unique=True)',source("models"))

    def test_10_db_receipts_have_unique_sequence_constraint(self):
        self.assertIn('name="mp_v141_receipt_state_seq"',source("models"))
        self.assertIn('name="mp_v141_receipt_state_seq"',source("migration"))

    def test_11_db_receipts_have_unique_manifest_id(self):
        self.assertIn('name="mp_v141_receipt_unique_id"',source("models"))
        self.assertIn('name="mp_v141_receipt_unique_id"',source("migration"))

    def test_12_replay_writer_uses_db_atomic_transaction(self):
        self.assertIn("@transaction.atomic",source("service"))

    def test_13_challenge_state_is_row_locked(self):
        self.assertIn("PropV141SimState.objects.select_for_update().get(pk=state_pk)",source("service"))

    def test_14_unprovisioned_challenge_cannot_be_created(self):
        self.assertNotIn("PropV141SimState.objects.create(",source("service"))
        self.assertNotIn("get_or_create(",source("service"))
        self.assertIn("unprovisioned challenge must not be created",source("service"))

    def test_15_receipts_are_append_only_metadata_not_misleading_archives(self):
        self.assertIn("PropV141SimReceipt.objects.create(",source("service"))
        self.assertNotIn("raw_manifest = models.BinaryField",source("models"))
        self.assertIn("NOT the original broker/ledger evidence",source("models"))

    def test_16_server_only_key_config_not_committed_as_static_literal(self):
        self.assertIn("trusted_signer_keys=trusted_signer_keys",source("service"))
        self.assertNotIn("hardcoded_signing_secret",source("service"))

    def test_17_backend_verifies_actual_signed_hmac_manifest(self):
        self.assertIn("verify_and_replay_signed_simulator_manifest(",source("service"))
        self.assertIn("signed simulator snapshot rejected",source("service"))

    def test_18_replayed_sequence_and_stage_time_saved_in_one_transaction(self):
        x=source("service")
        for field in ("last_sequence", "last_phase_one_accepted_at",
                      "last_phase_two_started_at", "last_phase_two_completed_at",
                      "last_receipt_sha256"):
            self.assertIn(f'"{field}"',x)

    def test_19_policy_blocks_stage2_promotion_without_old_pass(self):
        x=source("policy")
        self.assertIn("stage two lacks prior independently reviewed stage-one checkpoint",x)

    def test_20_no_public_payment_or_broker_write_functions(self):
        for name in ("service","policy"):
            x=ast.parse(source(name))
            fns=[n.name for n in ast.walk(x) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
            for forbidden in ("pay", "send_order", "charge_customer", "transfer_trx",
                              "create_live_broker_account", "activate_paid_enrollment"):
                self.assertNotIn(forbidden,fns)


if __name__=="__main__":
    unittest.main()
