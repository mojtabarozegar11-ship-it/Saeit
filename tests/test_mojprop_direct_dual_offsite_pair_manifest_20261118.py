"""Two-kind private encrypted backup technical receipt synthetic tests only.

No actual MySQL/source files, production SQL import, Google Drive OAuth, disk,
owner recovery keys or real customer data. Synthetic two-cloud memory only.
"""
import io
import json
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from scripts import mojprop_direct_dual_offsite_stream_core_20261118 as core
from scripts import mojprop_direct_dual_offsite_pair_manifest_20261118 as pair
from tests.test_mojprop_direct_dual_offsite_stream_core_20261118 import MemoryPrivateSink

SET="mojplaywin_20261118T041500Z_abcdef0123456789"
MAIN="679d2fefd349f580e765fee1a5fc823c48e01851"
PAYLOAD=b"ONLY-SYNTHETIC-BACKUP-REPLAY\n"*(core.PART_MIN//30+100)


class TwoKindPairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        cls.public=cls.private.public_key().public_bytes(
            serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        cls.pubsha=core.digest(cls.private.public_key().public_bytes(
            serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo))

    def setUp(self):
        self.sinks=(MemoryPrivateSink(),MemoryPrivateSink())
        self.reviews=(
            core.ProviderReview("private_one",True,True,True,True,core.MAX_SOURCE*2),
            core.ProviderReview("private_two",True,True,True,True,core.MAX_SOURCE*2))
        self.base="mojprop-recovery/"+SET+"/"

    def kind(self,kind):
        return core.stream_to_two_private_sinks(io.BytesIO(PAYLOAD),self.sinks,self.reviews,
            self.public,set_id=SET,kind=kind,
            expected_source_bytes=len(PAYLOAD),part_size=core.PART_MIN)

    def ready(self):
        self.kind("mysql")
        self.kind("files")

    def commit(self,**kw):
        return pair.finalize_technical_pair(
            kw.get("sinks",self.sinks),set_id=kw.get("set_id",SET),
            expected_recipient_pubkey_sha256=kw.get("pubsha",self.pubsha),
            expected_main_source_commit=kw.get("main",MAIN))

    def mutate_manifest(self,kind,method):
        path=self.base+kind+"/manifest.json"
        for cloud in self.sinks:
            obj=json.loads(cloud.parts[path])
            method(obj)
            cloud.parts[path]=core.encoded(obj)

    def test_01_both_mysql_and_files_create_technical_receipt(self):
        self.ready()
        result=self.commit()
        self.assertEqual(result["files_present_kinds"],2)
        self.assertTrue(result["technical_receipt_written_to_two_stores"])

    def test_02_both_cloud_receipts_are_identical(self):
        self.ready();self.commit()
        key=self.base+"complete-set-technical.json"
        self.assertEqual(self.sinks[0].parts[key],self.sinks[1].parts[key])

    def test_03_missing_files_kind_refuses_complete_receipt(self):
        self.kind("mysql")
        with self.assertRaises(core.DualOffsiteDenied):
            self.commit()
        self.assertNotIn(self.base+"complete-set-technical.json",self.sinks[0].parts)

    def test_04_missing_mysql_kind_refuses_complete_receipt(self):
        self.kind("files")
        with self.assertRaises(core.DualOffsiteDenied):
            self.commit()

    def test_05_mysql_part_changed_on_one_cloud_refused(self):
        self.ready()
        key=next(k for k in self.sinks[1].parts if "/mysql/" in k and k.endswith(".gcm"))
        self.sinks[1].parts[key]=self.sinks[1].parts[key][:-1]+b"Z"
        with self.assertRaises(core.DualOffsiteDenied):
            self.commit()

    def test_06_files_cipher_both_clouds_changed_refuses_manifest_chain(self):
        self.ready()
        key=next(k for k in self.sinks[0].parts if "/files/" in k and k.endswith(".gcm"))
        for cloud in self.sinks:
            raw=cloud.parts[key]
            cloud.parts[key]=raw[:-1]+bytes([raw[-1]^1])
        with self.assertRaises(core.DualOffsiteDenied):
            self.commit()

    def test_07_pair_pubkey_fingerprint_does_not_match_denied(self):
        self.ready()
        with self.assertRaises(core.DualOffsiteDenied):
            self.commit(pubsha="f"*64)

    def test_08_pair_missing_valid_source_commit_denied(self):
        self.ready()
        with self.assertRaises(core.DualOffsiteDenied):
            self.commit(main="not-a-git-commit")

    def test_09_two_clouds_are_separate_objects(self):
        self.ready()
        with self.assertRaises(core.DualOffsiteDenied):
            self.commit(sinks=(self.sinks[0],self.sinks[0]))

    def test_10_repeated_commit_rejects_overwrite(self):
        self.ready();self.commit()
        with self.assertRaises(core.DualOffsiteDenied):
            self.commit()

    def test_11_manifest_wrong_kind_denied(self):
        self.ready()
        self.mutate_manifest("mysql",lambda d:d.update(kind="files"))
        with self.assertRaises(core.DualOffsiteDenied):
            self.commit()

    def test_12_manifest_wrong_set_id_denied(self):
        self.ready()
        self.mutate_manifest("files",lambda d:d.update(set_id="mojplaywin_20261118T060000Z_bbbbbbbbbbbbbbbb"))
        with self.assertRaises(core.DualOffsiteDenied):
            self.commit()

    def test_13_fictitious_kind_part_count_denied(self):
        self.ready()
        self.mutate_manifest("mysql",lambda d:d.update(part_count=99))
        with self.assertRaises(core.DualOffsiteDenied):
            self.commit()

    def test_14_corrupt_cipher_chain_denied(self):
        self.ready()
        self.mutate_manifest("mysql",lambda d:d.update(cipher_hash_chain_sha256="0"*64))
        with self.assertRaises(core.DualOffsiteDenied):
            self.commit()

    def test_15_no_funded_account_or_payment_allowed(self):
        self.ready()
        r=self.commit()
        self.assertFalse(r["production_paid_challenge_available"])
        self.assertFalse(r["real_revenue_received"])

    def test_16_no_real_sql_or_media_restoration_automatically(self):
        self.ready()
        r=self.commit()
        self.assertFalse(r["isolated_real_sql_and_media_restore_proven"])
        self.assertFalse(r["source_db_and_media_co_snapshot_proven"])

    def test_17_technical_receipt_explicitly_disclaims_privkey_escrow(self):
        self.ready();r=self.commit()
        self.assertFalse(r["owner_recovery_escrow_proven"])

    def test_18_terminal_mysql_and_files_manifest_sha_are_pinned(self):
        self.ready();self.commit()
        full=json.loads(self.sinks[0].parts[self.base+"complete-set-technical.json"])
        self.assertEqual(full["technical_mysql"]["manifest_sha256"],
                         core.digest(self.sinks[0].parts[self.base+"mysql/manifest.json"]))
        self.assertEqual(full["technical_scoped_files"]["manifest_sha256"],
                         core.digest(self.sinks[0].parts[self.base+"files/manifest.json"]))

    def test_19_no_live_ssh_or_personal_data_from_this_pair_function(self):
        self.ready();r=self.commit()
        self.assertFalse(r["production_or_customer_write_performed"])

    def test_20_both_cloud_kind_manifest_divergence_refused(self):
        self.ready()
        self.sinks[1].parts[self.base+"files/manifest.json"]=b"{}"
        with self.assertRaises(core.DualOffsiteDenied):
            self.commit()


if __name__=="__main__":
    unittest.main()
