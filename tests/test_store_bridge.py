"""Private VPS->cPanel handoff: integrity, idempotency, zero publication."""
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1] / "scripts"

def load(name):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

receiver = load("store_receiver")
sender = load("factory_store_sender")


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inbox = self.root / "private-inbox"
        self.product = self.root / "factory" / "farm_enterprise_economics"
        self.product.mkdir(parents=True)
        self.archive = self.product / "farm_enterprise_economics-internal-qa.zip"
        with zipfile.ZipFile(str(self.archive), "w", compression=zipfile.ZIP_DEFLATED) as f:
            f.writestr("farm_enterprise_economics/calculator.py", "print(42)")
        self.digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.meta = {
            "recipe": "farm_enterprise_economics",
            "artifact_sha256": self.digest,
            "qa_status": "passed",
            "commercial_status": "private_internal_qa_pass_not_published",
            "public_listing_enabled": False,
            "owner_publication_approval": False,
            "price": None,
        }
        self.manifest = self.product / "manufacturing_manifest.json"
        self.manifest.write_text(json.dumps(self.meta), encoding="utf-8")

    def stage(self):
        d = self.inbox / "incoming" / self.product.name
        d.mkdir(parents=True)
        (d / (self.digest + ".zip.partial")).write_bytes(self.archive.read_bytes())
        (d / (self.digest + ".json.partial")).write_bytes(self.manifest.read_bytes())

    def test_receiver_validation_reason_is_strictly_allowlisted(self):
        self.assertEqual(receiver.safe_finalize_reason(
            ValueError("UNSAFE_ARCHIVE_MEMBER")), "UNSAFE_ARCHIVE_MEMBER")
        self.assertIsNone(receiver.safe_finalize_reason(ValueError("my secret token")))
        self.assertIsNone(receiver.safe_finalize_reason(
            ValueError("SENSITIVE_API_KEY")))
        self.assertIsNone(receiver.safe_finalize_reason(OSError("UNSAFE_ARCHIVE_MEMBER")))

    def test_sender_never_echoes_untrusted_remote_stderr(self):
        response = mock.Mock(returncode=1, stdout="",
                             stderr="STORE_RECEIVER_SAFE_REASON=UNSAFE_ARCHIVE_MEMBER\n"
                                    "authorization_token=do-not-print\n")
        with mock.patch.object(sender.subprocess, "run", return_value=response), \
             mock.patch("sys.stderr", new_callable=io.StringIO) as stream:
            with self.assertRaisesRegex(RuntimeError,
                                        "PRIVATE_DELIVERY_FINALIZE_RC_1"):
                sender.call(["ssh", "sensitive-key-material"], stage="finalize")
        safe = stream.getvalue()
        self.assertIn("FACTORY_STORE_RECEIVER_REJECTION=UNSAFE_ARCHIVE_MEMBER", safe)
        self.assertNotIn("do-not-print", safe)
        self.assertNotIn("sensitive-key-material", safe)

    def test_receipt_is_private_and_noncommercial(self):
        self.stage()
        receiver.finalize(self.inbox, self.product.name, self.digest)
        self.assertTrue(receiver.status(self.inbox, self.product.name, self.digest))
        receipt = json.loads(receiver.receipt_path(self.inbox, self.product.name, self.digest).read_text())
        self.assertFalse(receipt["public_store_listing"])
        self.assertFalse(receipt["database_written"])
        archive = self.inbox / "packages" / self.product.name / (self.digest + ".zip")
        self.assertEqual(archive.stat().st_mode & 0o777, 0o600)

    def test_tampered_archive_rejected(self):
        self.stage()
        path = self.inbox / "incoming" / self.product.name / (self.digest + ".zip.partial")
        path.write_bytes(b"corrupted")
        with self.assertRaises(ValueError):
            receiver.finalize(self.inbox, self.product.name, self.digest)

    def test_public_listing_flag_rejected(self):
        self.meta["public_listing_enabled"] = True
        self.manifest.write_text(json.dumps(self.meta))
        with self.assertRaises(ValueError):
            sender.verify_source(self.manifest, self.archive, self.product.name)
        self.stage()
        with self.assertRaises(ValueError):
            receiver.finalize(self.inbox, self.product.name, self.digest)

    def test_zip_path_traversal_rejected(self):
        with zipfile.ZipFile(str(self.archive), "w") as z:
            z.writestr("farm_enterprise_economics/../../escape.py", "unsafe")
        self.digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.meta["artifact_sha256"] = self.digest
        self.manifest.write_text(json.dumps(self.meta))
        self.stage()
        with self.assertRaises(ValueError):
            receiver.finalize(self.inbox, self.product.name, self.digest)

    def test_sender_blocks_stale_artifact_when_qa_rework_is_open(self):
        ticket = self.manifest.parents[2] / "qa-rework" / self.product.name / "ledger.json"
        ticket.parent.mkdir(parents=True)
        ticket.write_text(json.dumps({
            "schema": "saeit.factory.qa-rework.v1",
            "current_status": "needs_rework",
            "public_sale_allowed": False,
            "history": [{"code": "PRODUCT_QA_FAILED"}],
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "BLOCKED_FOR_REWORK"):
            sender.verify_source(self.manifest, self.archive, self.product.name)
        ticket.write_text(json.dumps({
            "schema": "saeit.factory.qa-rework.v1",
            "current_status": "technical_qa_pass_only_owner_and_content_review_pending",
            "public_sale_allowed": False,
            "history": [{"status": "technically_recovered"}],
        }), encoding="utf-8")
        self.assertEqual(
            sender.verify_source(self.manifest, self.archive, self.product.name),
            self.digest,
        )

    def test_sender_rejects_unverified_rework_ledger(self):
        ticket = self.manifest.parents[2] / "qa-rework" / self.product.name / "ledger.json"
        ticket.parent.mkdir(parents=True)
        ticket.write_text('not-json', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, "LEDGER_INVALID"):
            sender.verify_source(self.manifest, self.archive, self.product.name)

    def test_sender_does_not_contact_network_on_dry_run(self):
        with mock.patch.object(sender, "call", side_effect=AssertionError("no network allowed")):
            result = sender.deliver(self.product.name, self.product.parent, ["key"], dry_run=True)
        self.assertEqual(result["status"], "dry_run_private_only")

    def test_sender_skips_already_received(self):
        with mock.patch.object(sender, "call") as call:
            call.return_value = mock.Mock(returncode=0, stdout="STORE_PRIVATE_RECEIPT_VERIFIED")
            result = sender.deliver(self.product.name, self.product.parent, ["key"])
        self.assertEqual(result["status"], "already_received")
        self.assertEqual(call.call_count, 1)


    def test_sender_rotates_through_all_recipes(self):
        source = self.product.parent
        for name in ("a_recipe", "b_recipe", "c_recipe", "d_recipe", "e_recipe"):
            (source / name).mkdir()
        all_names = sorted(p.name for p in source.iterdir() if p.is_dir())
        sent = []

        def fake_delivery(recipe, root, options, *, dry_run=False):
            self.assertEqual(root, source)
            sent.append(recipe)
            return {"recipe": recipe, "status": "received_private"}

        # This test checks rotation only; its placeholder directories have no
        # manifests. Product integrity itself is tested separately.
        with mock.patch.object(sender, "host_ssh_options", return_value=["verified"]), \
             mock.patch.object(sender, "verify_source", return_value="verified-sha"), \
             mock.patch.object(sender, "deliver", side_effect=fake_delivery):
            a = sender.sync(source, "unused", "unused", limit=3)
            b = sender.sync(source, "unused", "unused", limit=3)
            c = sender.sync(source, "unused", "unused", limit=3)
        self.assertEqual([x["recipe"] for x in a], all_names[:3])
        self.assertEqual([x["recipe"] for x in b], all_names[3:])
        self.assertEqual([x["recipe"] for x in c], all_names[:3])
        self.assertEqual(sender.read_cursor(source.parent / "store-send-cursor.json"), all_names[2])

    def test_sender_checkpoint_survives_partial_delivery_failure(self):
        source = self.product.parent
        for name in ("a_recipe", "b_recipe"):
            (source / name).mkdir()
        ordered = sorted(p.name for p in source.iterdir() if p.is_dir())
        attempts = []

        def fail_second(recipe, root, options, *, dry_run=False):
            attempts.append(recipe)
            if len(attempts) == 2:
                raise RuntimeError("temporary SSH failure")
            return {"recipe": recipe, "status": "received_private"}

        # The fault-injection test isolates the SSH receipt boundary from
        # product QA, which is covered by real-SHA regression tests.
        with mock.patch.object(sender, "host_ssh_options", return_value=["verified"]), \
             mock.patch.object(sender, "verify_source", return_value="verified-sha"), \
             mock.patch.object(sender, "deliver", side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError, "temporary SSH failure"):
                sender.sync(source, "unused", "unused", limit=3)
        self.assertEqual(sender.read_cursor(source.parent / "store-send-cursor.json"), ordered[0])

    def test_sender_dryrun_does_not_advance_checkpoint(self):
        source = self.product.parent
        with mock.patch.object(sender, "host_ssh_options", return_value=["verified"]), \
             mock.patch.object(sender, "deliver", return_value={
                 "recipe": self.product.name, "status": "dry_run_private_only"
             }):
            sender.sync(source, "unused", "unused", limit=3, dry_run=True)
        self.assertFalse((source.parent / "store-send-cursor.json").exists())

    def test_sender_rejects_tampered_cursor_and_symlink(self):
        source = self.product.parent
        cursor = source.parent / "store-send-cursor.json"
        cursor.write_text("not json", encoding="utf-8")
        with mock.patch.object(sender, "host_ssh_options", return_value=["verified"]):
            with self.assertRaisesRegex(ValueError, "STORE_CURSOR_CORRUPTED"):
                sender.sync(source, "unused", "unused", limit=3)
        cursor.unlink()
        cursor.symlink_to(self.manifest)
        with mock.patch.object(sender, "host_ssh_options", return_value=["verified"]):
            with self.assertRaisesRegex(ValueError, "STORE_CURSOR_SYMLINK_UNSAFE"):
                sender.sync(source, "unused", "unused", limit=3)


    def make_private_f34_icon_archive(self, *, extra=False, review=True):
        """Synthetic byte fixtures prove receiver contract, not actual icon QA."""
        recipe = "fieldwork_ui_48_icons"
        folder = self.root / recipe
        folder.mkdir(exist_ok=True)
        archive = folder / (recipe + "-internal-qa.zip")
        names = [
            concept + "_" + variant + suffix
            for concept in ("sprout", "cloud", "shield", "package",
                            "chart", "sun", "database", "flask",
                            "globe", "heart", "gear", "compass")
            for variant in ("outline", "tile", "stamped", "dual")
            for suffix in (".svg", ".png")
        ] + ["README.md", "LICENSE.txt", "catalog.json", "preview.html"]
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for name in names:
                z.writestr(recipe + "/" + name, ("synthetic " + name).encode())
            if extra:
                z.writestr(recipe + "/unapproved_extra.svg", b"unexpected")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        gates = {
            key: True for key in (
                "requirements", "correctness", "negative_cases", "usability",
                "accessibility", "security", "compatibility", "provenance",
                "specialist_review", "release_integrity"
            )
        }
        if not review:
            gates["release_integrity"] = False
        manifest = dict(self.meta,
            recipe=recipe, artifact_sha256=digest, family_id="F34", files=names,
            qa_measurements={
                "review_kind": "separate_automated_technical_verification",
                "validated_archive_members": 100, "archive_sha256": digest,
                "critical_defects": [], "gates": gates,
            })
        meta = folder / "manufacturing_manifest.json"
        meta.write_text(json.dumps(manifest))
        return recipe, archive, meta, digest

    def test_exact_f34_100_member_archive_is_private_only(self):
        recipe, archive, meta, digest = self.make_private_f34_icon_archive()
        validated = receiver.validate_package(archive, meta, recipe, digest)
        self.assertEqual(validated["qa_measurements"]["validated_archive_members"], 100)
        staged = self.inbox / "incoming" / recipe
        staged.mkdir(parents=True)
        (staged / (digest + ".zip.partial")).write_bytes(archive.read_bytes())
        (staged / (digest + ".json.partial")).write_bytes(meta.read_bytes())
        receiver.finalize(self.inbox, recipe, digest)
        self.assertTrue(receiver.status(self.inbox, recipe, digest))
        receipt = json.loads(receiver.receipt_path(self.inbox, recipe, digest).read_text())
        self.assertFalse(receipt["public_store_listing"])
        self.assertFalse(receipt["database_written"])

    def test_f34_more_than_100_members_is_rejected(self):
        recipe, archive, meta, digest = self.make_private_f34_icon_archive(extra=True)
        with self.assertRaisesRegex(ValueError, "F34_EXACT_ICON_PACKAGE_INVALID"):
            receiver.validate_package(archive, meta, recipe, digest)

    def test_f34_missing_independent_gate_is_rejected(self):
        recipe, archive, meta, digest = self.make_private_f34_icon_archive(review=False)
        with self.assertRaisesRegex(ValueError, "F34_EVIDENCE_CONTRACT_INVALID"):
            receiver.validate_package(archive, meta, recipe, digest)

    def test_all_other_recipes_remain_bound_to_80_members(self):
        recipe = "normal_workbook"
        folder = self.root / recipe
        folder.mkdir()
        archive = folder / "normal_workbook-internal-qa.zip"
        with zipfile.ZipFile(archive, "w") as z:
            for n in range(81):
                z.writestr(recipe + "/entry_%02d.txt" % n, b"synthetic")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        manifest = dict(self.meta, recipe=recipe, artifact_sha256=digest)
        path = folder / "manufacturing_manifest.json"
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "ARCHIVE_FILE_COUNT_INVALID"):
            receiver.validate_package(archive, path, recipe, digest)


if __name__ == "__main__":
    unittest.main()
