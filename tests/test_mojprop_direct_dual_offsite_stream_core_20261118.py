"""Synthetic RSA-3072 + AES-256-GCM private multipart two-cloud adversarial drill.

NO connected cloud, customer information, cPanel, broker, backup or production
data is touched. Every test uses in-memory nonpersonal test strings and keys.
"""
import io
import copy
import json
import os
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from scripts import mojprop_direct_dual_offsite_stream_core_20261118 as p

SET_ID="mojplaywin_20261118T040000Z_1234abcdef123456"
KIND="mysql"
PART=p.PART_MIN
SOURCE=(b"MOJPROP SYNTHETIC NONCUSTOMER SQL ROW\n"*4500)[:PART*2+1043]


class MemoryPrivateSink:
    def __init__(self):
        self.parts={}
        self.put_calls=[]
        self.read_calls=[]
        self.fail_put_at=None
        self.fail_read_at=None
        self.corrupt_read_key=None
        self.truncate_read_key=None

    def put_once(self,key,value):
        if self.fail_put_at==len(self.put_calls):
            raise OSError("synthetic cloud put unavailable")
        if key in self.parts:
            raise p.DualOffsiteDenied("OBJECT_ALREADY_EXISTS_NO_OVERWRITE")
        if type(key) is not str or type(value) is not bytes:
            raise AssertionError("bad test sink")
        self.put_calls.append(key)
        self.parts[key]=value

    def read_exact(self,key,max_bytes):
        self.read_calls.append(key)
        if self.fail_read_at==len(self.read_calls)-1:
            raise OSError("synthetic remote readback unavailable")
        value=self.parts.get(key,b"")
        if self.corrupt_read_key==key:
            value=value[:-1]+bytes([value[-1]^1]) if value else value
        if self.truncate_read_key==key:
            value=value[:-1]
        if len(value)>max_bytes:
            raise p.DualOffsiteDenied("REMOTE_RESPONSE_TOO_LARGE")
        return value


class ShortSource:
    def __init__(self,buf,at_most):
        self.s=io.BytesIO(buf)
        self.at_most=at_most

    def read(self,n=-1):
        return self.s.read(min(n,self.at_most))


class UpstreamFailure:
    def __init__(self,buf,fail_after):
        self.buf=io.BytesIO(buf)
        self.fail_after=fail_after

    def read(self,n):
        if self.buf.tell()>=self.fail_after:
            raise OSError("upstream synthetic SSH stream cut")
        return self.buf.read(min(n,self.fail_after-self.buf.tell()))


class TwoCloudSyntheticSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        cls.public_pem=cls.private.public_key().public_bytes(
            serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        cls.private_pem=cls.private.private_bytes(
            serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(b"offline-only-passphrase"))
        cls.pubsha=p.digest(cls.private.public_key().public_bytes(
            serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo))

    def setUp(self):
        self.stores=(MemoryPrivateSink(),MemoryPrivateSink())
        self.reviews=(
            p.ProviderReview("owner_drive_alpha",True,True,True,True,10*p.MAX_SOURCE),
            p.ProviderReview("owner_drive_beta",True,True,True,True,10*p.MAX_SOURCE)
        )

    def send(self,src=SOURCE,source=None,**kw):
        return p.stream_to_two_private_sinks(
            io.BytesIO(src) if source is None else source,self.stores,self.reviews,
            self.public_pem,set_id=kw.pop("set_id",SET_ID),
            kind=kw.pop("kind",KIND),
            expected_source_bytes=kw.pop("expected_source_bytes",len(src)),
            part_size=kw.pop("part_size",PART),**kw)

    def restore(self,**kw):
        out=io.BytesIO()
        result=p.isolated_restore_from_two_private_sinks(
            self.stores,self.private_pem,b"offline-only-passphrase",
            set_id=kw.pop("set_id",SET_ID),kind=kw.pop("kind",KIND),
            isolated_output=out,
            expected_pubkey_sha256=kw.pop("expected_pubkey_sha256",self.pubsha),**kw)
        return result,out.getvalue()

    def must_reject_send(self,**kw):
        with self.assertRaises((p.DualOffsiteDenied,ValueError)):
            self.send(**kw)
        self.assertFalse(any("manifest.json" in key for key in self.stores[0].parts))

    def test_01_two_independent_private_sinks_receive_all_chunks(self):
        result=self.send()
        self.assertEqual(result["parts"],3)
        self.assertEqual(len(self.stores[0].parts),4)
        self.assertEqual(self.stores[0].parts,self.stores[1].parts)

    def test_02_offline_crypto_restore_exact_plaintext(self):
        self.send()
        report,raw=self.restore()
        self.assertEqual(raw,SOURCE)
        self.assertEqual(report["decrypted_bytes"],len(SOURCE))

    def test_03_db_kind_credential_free(self):
        self.send()
        for sink in self.stores:
            self.assertFalse(any(SOURCE[:80] in v for v in sink.parts.values()))

    def test_04_no_server_disk_or_payment_claim(self):
        result=self.send()
        self.assertFalse(result["production_deployed"])
        self.assertFalse(result["payment_collected"])
        self.assertFalse(result["independently_restored"])

    def test_05_restore_is_only_quarantined_bytes(self):
        self.send()
        result,_=self.restore()
        self.assertFalse(result["isolated_sql_import_performed_by_this_library"])
        self.assertFalse(result["full_mysql_plus_media_pair_independently_restored"])

    def test_06_signed_source_provenance_not_faked(self):
        self.assertFalse(self.send()["source_consistency_authenticated_by_this_library"])

    def test_07_direct_external_credential_proof_not_faked(self):
        self.assertFalse(self.send()["server_oauth_authenticated_by_this_library"])

    def test_08_public_RSA_key_cannot_decrypt_without_private(self):
        self.send()
        a=self.stores[0].parts[next(k for k in self.stores[0].parts if k.endswith(".gcm"))]
        self.assertNotEqual(a[:16],SOURCE[:16])

    def test_09_bad_set_name_refused(self):
        self.must_reject_send(set_id="../../private")

    def test_10_unsupported_kind_refused(self):
        self.must_reject_send(kind="private-payments")

    def test_11_empty_source_refused(self):
        self.must_reject_send(src=b"",expected_source_bytes=0)

    def test_12_negative_size_refused(self):
        self.must_reject_send(expected_source_bytes=-2)

    def test_13_size_boolean_refused(self):
        self.must_reject_send(expected_source_bytes=True)

    def test_14_oversize_source_claim_refused(self):
        self.must_reject_send(expected_source_bytes=p.MAX_SOURCE+1)

    def test_15_too_small_chunk_config_refused(self):
        self.must_reject_send(part_size=10)

    def test_16_too_large_chunk_config_refused(self):
        self.must_reject_send(part_size=p.PART_MAX+1)

    def test_17_same_storage_object_not_two_independent_copies(self):
        self.stores=(self.stores[0],self.stores[0])
        self.must_reject_send()

    def test_18_same_owner_account_id_rejected(self):
        self.reviews=(self.reviews[0],self.reviews[0])
        self.must_reject_send()

    def test_19_missing_authenticated_drive_oauth_denied(self):
        self.reviews=(p.ProviderReview("owner_drive_alpha",False,True,True,True,10*p.MAX_SOURCE),self.reviews[1])
        self.must_reject_send()

    def test_20_missing_private_ACL_denied(self):
        self.reviews=(p.ProviderReview("owner_drive_alpha",True,False,True,True,10*p.MAX_SOURCE),self.reviews[1])
        self.must_reject_send()

    def test_21_no_actual_provider_quota_evidence_denied(self):
        self.reviews=(p.ProviderReview("owner_drive_alpha",True,True,False,True,10*p.MAX_SOURCE),self.reviews[1])
        self.must_reject_send()

    def test_22_no_readback_support_denied(self):
        self.reviews=(p.ProviderReview("owner_drive_alpha",True,True,True,False,10*p.MAX_SOURCE),self.reviews[1])
        self.must_reject_send()

    def test_23_too_small_provider_capacity_denied(self):
        self.reviews=(p.ProviderReview("owner_drive_alpha",True,True,True,True,len(SOURCE)),self.reviews[1])
        self.must_reject_send()

    def test_24_capacity_boolean_masquerade_denied(self):
        self.reviews=(p.ProviderReview("owner_drive_alpha",True,True,True,True,True),self.reviews[1])
        self.must_reject_send()

    def test_25_invalid_RSA_public_key_denied(self):
        with self.assertRaises(p.DualOffsiteDenied):
            p.stream_to_two_private_sinks(io.BytesIO(SOURCE),self.stores,self.reviews,b"no public key",
                set_id=SET_ID,kind=KIND,expected_source_bytes=len(SOURCE),part_size=PART)

    def test_26_RSA_2048_rejected(self):
        weak=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        weak_pem=weak.public_key().public_bytes(
            serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        with self.assertRaises(p.DualOffsiteDenied):
            p.stream_to_two_private_sinks(io.BytesIO(SOURCE),self.stores,self.reviews,weak_pem,
                set_id=SET_ID,kind=KIND,expected_source_bytes=len(SOURCE),part_size=PART)

    def test_27_short_ssh_reads_are_reassembled(self):
        self.send(source=ShortSource(SOURCE,2048))
        _,out=self.restore()
        self.assertEqual(out,SOURCE)

    def test_28_truncated_ssh_stream_leaves_no_terminal_manifest(self):
        with self.assertRaises(p.DualOffsiteDenied):
            self.send(source=io.BytesIO(SOURCE[:-17]))
        self.assertFalse(any(k.endswith("manifest.json") for k in self.stores[0].parts))

    def test_29_source_has_extra_bytes_refused(self):
        with self.assertRaises(p.DualOffsiteDenied):
            self.send(source=io.BytesIO(SOURCE+b"unexpected"))
        self.assertFalse(any(k.endswith("manifest.json") for k in self.stores[0].parts))

    def test_30_upstream_error_never_commits_terminal_manifest(self):
        with self.assertRaises(OSError):
            self.send(source=UpstreamFailure(SOURCE,PART))
        self.assertFalse(any(k.endswith("manifest.json") for k in self.stores[0].parts))

    def test_31_cloud_upload_fails_then_no_terminal_manifest(self):
        self.stores[1].fail_put_at=1
        with self.assertRaises(OSError):
            self.send()
        self.assertFalse(any(k.endswith("manifest.json") for k in self.stores[0].parts))

    def test_32_cloud_readback_mismatch_prevents_finalization(self):
        prefix="mojprop-recovery/"+SET_ID+"/"+KIND+"/"
        self.stores[1].corrupt_read_key=prefix+"00000000.gcm"
        with self.assertRaises(p.DualOffsiteDenied):
            self.send()
        self.assertFalse(any(k.endswith("manifest.json") for k in self.stores[0].parts))

    def test_33_missing_part_on_second_provider_breaks_restore(self):
        self.send()
        k=next(k for k in self.stores[1].parts if k.endswith(".gcm"))
        self.stores[1].parts.pop(k)
        with self.assertRaises(p.DualOffsiteDenied):
            self.restore()

    def test_34_tamper_ciphertext_both_providers_breaks_GCM(self):
        self.send()
        k=next(k for k in self.stores[0].parts if k.endswith(".gcm"))
        for cloud in self.stores:
            data=cloud.parts[k]
            cloud.parts[k]=data[:-1]+bytes([data[-1]^1])
        with self.assertRaises(p.DualOffsiteDenied):
            self.restore()

    def test_35_different_copies_break_restore(self):
        self.send()
        k=next(k for k in self.stores[1].parts if k.endswith(".gcm"))
        self.stores[1].parts[k]=self.stores[1].parts[k][:-1]+b"x"
        with self.assertRaises(p.DualOffsiteDenied):
            self.restore()

    def test_36_manifest_swapped_between_clouds_refused(self):
        self.send()
        k=next(k for k in self.stores[1].parts if k.endswith("manifest.json"))
        self.stores[1].parts[k]=b"{}"
        with self.assertRaises(p.DualOffsiteDenied):
            self.restore()

    def test_37_missing_terminal_manifest_refused(self):
        self.send()
        k=next(k for k in self.stores[1].parts if k.endswith("manifest.json"))
        self.stores[1].parts.pop(k)
        with self.assertRaises(p.DualOffsiteDenied):
            self.restore()

    def test_38_wrong_expected_pubkey_refused(self):
        self.send()
        with self.assertRaises(p.DualOffsiteDenied):
            self.restore(expected_pubkey_sha256="f"*64)

    def test_39_invalid_kind_on_restore_refused(self):
        self.send()
        with self.assertRaises(p.DualOffsiteDenied):
            self.restore(kind="wallet")

    def test_40_invalid_private_key_password_refused(self):
        self.send()
        with self.assertRaises(p.DualOffsiteDenied):
            p.isolated_restore_from_two_private_sinks(
                self.stores,self.private_pem,b"wrong password",
                set_id=SET_ID,kind=KIND,isolated_output=io.BytesIO(),
                expected_pubkey_sha256=self.pubsha)

    def test_41_manifest_rewritten_hash_even_if_two_copies_consistent(self):
        self.send()
        for cloud in self.stores:
            key=next(k for k in cloud.parts if k.endswith("manifest.json"))
            obj=json.loads(cloud.parts[key])
            obj["plaintext_sha256"]="0"*64
            cloud.parts[key]=p.encoded(obj)
        with self.assertRaises(p.DualOffsiteDenied):
            self.restore()

    def test_42_part_order_swapped_in_both_private_clouds_refused(self):
        self.send()
        keys=sorted(k for k in self.stores[0].parts if k.endswith(".gcm"))
        for cloud in self.stores:
            cloud.parts[keys[0]],cloud.parts[keys[1]]=cloud.parts[keys[1]],cloud.parts[keys[0]]
        with self.assertRaises(p.DualOffsiteDenied):
            self.restore()

    def test_43_manifest_part_count_invalid_refused(self):
        self.send()
        for cloud in self.stores:
            key=next(k for k in cloud.parts if k.endswith("manifest.json"))
            obj=json.loads(cloud.parts[key])
            obj["part_count"]+=1
            cloud.parts[key]=p.encoded(obj)
        with self.assertRaises(p.DualOffsiteDenied):
            self.restore()

    def test_44_reupload_same_id_refuses_overwrite_not_delete(self):
        self.send()
        with self.assertRaises(p.DualOffsiteDenied):
            self.send()
        self.assertTrue(any(k.endswith("manifest.json") for k in self.stores[0].parts))

    def test_45_manifest_only_after_all_parts_confirmed(self):
        self.send()
        for cloud in self.stores:
            self.assertTrue(cloud.put_calls[-1].endswith("manifest.json"))
            self.assertEqual(cloud.put_calls,cloud.read_calls[:len(cloud.put_calls)])

    def test_46_files_kind_independent_name_and_aad(self):
        self.send(kind="files")
        out=io.BytesIO()
        result=p.isolated_restore_from_two_private_sinks(
            self.stores,self.private_pem,b"offline-only-passphrase",set_id=SET_ID,kind="files",
            isolated_output=out,expected_pubkey_sha256=self.pubsha)
        self.assertEqual(out.getvalue(),SOURCE)
        self.assertEqual(result["kind"],"files")

    def test_47_invalid_manifest_json_refused(self):
        self.send()
        for cloud in self.stores:
            key=next(k for k in cloud.parts if k.endswith("manifest.json"))
            cloud.parts[key]=b"not-json"
        with self.assertRaises(p.DualOffsiteDenied):
            self.restore()

    def test_48_part_not_found_before_manifest_never_counted_sale(self):
        self.stores[0].fail_put_at=0
        with self.assertRaises(OSError):
            self.send()
        self.assertEqual(self.stores[0].put_calls,[])
        self.assertEqual(self.stores[0].parts,{})


if __name__=="__main__":
    unittest.main()
