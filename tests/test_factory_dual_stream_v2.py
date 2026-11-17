"""Free, local F01V2 crypto and dual store fixtures; NEVER real Drive/backups."""
import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from factory_dual_stream_v2 import (
    encrypt_stream_to_dual_stores, decrypt_to_isolated_file,
    DualStoreReceipt, SCHEMA, MAGIC, AAD_META_LEN,
    MIN_CHUNK, MAX_CHUNK, _public_fingerprint, _canonical,
)

class FakeStore:
    def __init__(self):
        self.items={}
        self.fail_next=False
        self.corrupt_next=False
        self.writes=0
    def upload(self, name, payload):
        if self.fail_next:
            raise RuntimeError('provider unavailable')
        self.items[name] = (b'?' + payload[1:]) if self.corrupt_next else payload
        self.writes+=1
    def read(self, name):return self.items[name]

class PartialReader(io.BytesIO):
    def read(self, n=-1):return super().read(min(n,17))

class TestDualEncryptedStreaming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        cls.public=cls.key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo)
        cls.private=cls.key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption())
        cls.fp=_public_fingerprint(cls.public)[1]
        cls.other=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        cls.other_priv=cls.other.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption())
    def setUp(self):
        self.a=FakeStore();self.b=FakeStore()
        self.raw=(b'snapshot-offline-source-only-'*1000) + b'FINAL'
    def create(self, *, source=None, **kwargs):
        args=dict(source=source if source is not None else io.BytesIO(self.raw),
                  public_pem=self.public, trusted_public_spki_sha256=self.fp,
                  owner_a='Drive-A',owner_b='Drive-B',
                  upload_a=self.a.upload,upload_b=self.b.upload,
                  read_a=self.a.read,read_b=self.b.read,chunk_bytes=4096)
        args.update(kwargs)
        return encrypt_stream_to_dual_stores(**args)
    def manifest(self):
        return next(v for n,v in self.a.items.items() if n.endswith('manifest.json'))
    def restore(self, base, *, manifest=None, **kwargs):
        args=dict(read_chunk=self.a.read,private_pem=self.private,
                  private_password=None,expected_public_spki_sha256=self.fp,
                  output_path=Path(base)/'restored-backup.bin')
        args.update(kwargs)
        return decrypt_to_isolated_file(
            self.manifest() if manifest is None else manifest, **args)
    def test_01_3chunk_happy_path_authentic_dual_readback(self):
        r=self.create()
        self.assertIsInstance(r,DualStoreReceipt)
        self.assertTrue(r.cipher_parts_mirrored_and_readback_verified)
        self.assertFalse(r.restores_verified)
        self.assertFalse(r.commercial_release_authorized)
        self.assertEqual(r.plaintext_bytes,len(self.raw))
        self.assertEqual(r.parts,len(self.a.items)-1)
        self.assertEqual(self.a.items,self.b.items)
    def test_02_offline_round_trip_exact_bytes(self):
        self.create()
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.restore(d),len(self.raw))
            self.assertEqual((Path(d)/'restored-backup.bin').read_bytes(),self.raw)
    def test_03_no_client_identifiers_in_manifest(self):
        self.create(owner_a='owner.first@example.invalid',owner_b='owner.second@example.invalid')
        m=self.manifest()
        self.assertNotIn(b'owner.first',m)
        self.assertNotIn(b'owner.second',m)
        self.assertNotIn(self.raw[:32],m)
    def test_04_manifest_is_not_restore_proof(self):
        self.create()
        m=json.loads(self.manifest())
        self.assertFalse(m['restore_verified'])
        self.assertFalse(m['source_consistency_external'])
        self.assertEqual(m['schema'],SCHEMA)
    def test_05_wrong_owner_public_fingerprint_denied_before_write(self):
        with self.assertRaises(ValueError):self.create(trusted_public_spki_sha256='0'*64)
        self.assertEqual(self.a.writes,0)
    def test_06_weak_public_key_denied(self):
        weak=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        pem=weak.public_key().public_bytes(serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo)
        with self.assertRaises(ValueError):self.create(public_pem=pem)
    def test_07_same_owner_denied(self):
        with self.assertRaises(ValueError):self.create(owner_b='drive-a')
    def test_08_same_callback_denied(self):
        with self.assertRaises(ValueError):self.create(upload_b=self.a.upload)
    def test_09_invalid_chunk_size_denied(self):
        with self.assertRaises(ValueError):self.create(chunk_bytes=1)
    def test_10_oversized_chunk_size_denied(self):
        with self.assertRaises(ValueError):self.create(chunk_bytes=MAX_CHUNK+1)
    def test_11_empty_input_denied(self):
        with self.assertRaises(ValueError):self.create(source=io.BytesIO(b''))
    def test_12_non_binary_input_denied(self):
        with self.assertRaises(ValueError):self.create(source=io.StringIO('unsafe'))
    def test_13_short_partial_reads_preserve_plaintext(self):
        self.create(source=PartialReader(self.raw))
        with tempfile.TemporaryDirectory() as d:
            self.restore(d)
            self.assertEqual((Path(d)/'restored-backup.bin').read_bytes(),self.raw)
    def test_14_source_exceeds_admitted_bytes_prevents_final_manifest(self):
        with self.assertRaises(ValueError):self.create(max_source_bytes=5000)
        self.assertFalse(any(n.endswith('manifest.json') for n in self.a.items))
    def test_15_provider_b_unavailable_prevents_completion(self):
        self.b.fail_next=True
        with self.assertRaises(RuntimeError):self.create()
        self.assertFalse(any(n.endswith('manifest.json') for n in self.a.items))
    def test_16_ciphertext_corruption_in_provider_a_fails(self):
        self.a.corrupt_next=True
        with self.assertRaises(ValueError):self.create()
        self.assertFalse(any(n.endswith('manifest.json') for n in self.a.items))
    def test_17_ciphertext_corruption_in_provider_b_fails(self):
        self.b.corrupt_next=True
        with self.assertRaises(ValueError):self.create()
        self.assertFalse(any(n.endswith('manifest.json') for n in self.b.items))
    def test_18_ciphertext_not_plaintext(self):
        self.create()
        parts=[v for k,v in self.a.items.items() if k.endswith('.enc')]
        self.assertTrue(all(v.startswith(MAGIC) for v in parts))
        self.assertTrue(all(self.raw[:24] not in v for v in parts))
    def test_19_restore_denies_tampered_manifest_mac(self):
        self.create()
        x=json.loads(self.manifest());x['manifest_mac_sha256']='f'*64
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):self.restore(d,manifest=_canonical(x))
            self.assertFalse((Path(d)/'restored-backup.bin').exists())
    def test_20_restore_denies_wrong_private_key(self):
        self.create()
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Exception):self.restore(d,private_pem=self.other_priv)
            self.assertFalse((Path(d)/'restored-backup.bin').exists())
    def test_21_restore_denies_wrong_public_fingerprint(self):
        self.create()
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):self.restore(d,expected_public_spki_sha256='f'*64)
    def test_22_restore_denies_missing_remote_ciphertext(self):
        self.create(); k=next(k for k in self.a.items if k.endswith('.enc'));del self.a.items[k]
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(KeyError):self.restore(d)
            self.assertFalse((Path(d)/'restored-backup.bin').exists())
    def test_23_restore_denies_modified_remote_ciphertext(self):
        self.create(); k=next(k for k in self.a.items if k.endswith('.enc'))
        self.a.items[k]=b'Z'+self.a.items[k][1:]
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):self.restore(d)
            self.assertFalse((Path(d)/'restored-backup.bin').exists())
    def test_24_existing_destination_is_not_overwritten(self):
        self.create()
        with tempfile.TemporaryDirectory() as d:
            dst=Path(d)/'restored-backup.bin';dst.write_bytes(b'OWNER ORIGINAL')
            with self.assertRaises(FileExistsError):self.restore(d)
            self.assertEqual(dst.read_bytes(),b'OWNER ORIGINAL')
    def test_25_restored_file_permissions_owner_only(self):
        self.create()
        with tempfile.TemporaryDirectory() as d:
            self.restore(d)
            self.assertEqual((Path(d)/'restored-backup.bin').stat().st_mode & 0o777,0o600)
    def test_26_invalid_json_manifest_denied(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Exception):self.restore(d,manifest=b'not-json')
    def test_27_ciphertext_belongs_to_one_run_id(self):
        a=self.create()
        self.assertEqual(a.parts,len([k for k in self.a.items if k.endswith('.enc')]))
        self.assertEqual(set(self.a.items),set(self.b.items))
    def test_28_manifest_last_on_each_store(self):
        self.create()
        self.assertEqual(len([n for n in self.a.items if n.endswith('manifest.json')]),1)
        self.assertEqual(len([n for n in self.b.items if n.endswith('manifest.json')]),1)
    def test_29_limits_include_exact_min_chunk(self):
        self.assertEqual(MIN_CHUNK,4096)
        self.create(chunk_bytes=MIN_CHUNK)
    def test_30_remote_manifest_readback_mismatch_aborts(self):
        class ManifestCorruptStore(FakeStore):
            def upload(self, name,payload):
                if name.endswith('manifest.json'):
                    payload=b'!' + payload[1:]
                super().upload(name,payload)
        self.b=ManifestCorruptStore()
        with self.assertRaises(ValueError):self.create()
    def test_31_missing_callback_denied(self):
        with self.assertRaises(ValueError):self.create(read_b=None)
    def test_32_oversized_manifest_fails_before_offline_restore(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):self.restore(d,manifest=b'1'*(2*1024*1024+1))

    def test_33_encrypted_private_pem_password_protected_recovery(self):
        self.create()
        private_enc=self.key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(b'correct-private-owner-pass'))
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.restore(d,private_pem=private_enc,
                                          private_password=b'correct-private-owner-pass'),len(self.raw))
    def test_34_encrypted_private_pem_wrong_password_fails(self):
        self.create()
        private_enc=self.key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(b'correct-private-owner-pass'))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Exception):
                self.restore(d,private_pem=private_enc,private_password=b'incorrect')
            self.assertFalse((Path(d)/'restored-backup.bin').exists())
    def test_35_gcm_final_tag_tampering_fails_without_recoverable_output(self):
        self.create()
        name=next(n for n in self.a.items if n.endswith('.enc'))
        blob=self.a.items[name]
        self.a.items[name]=blob[:-1]+bytes([blob[-1]^1])
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):self.restore(d)
            self.assertFalse((Path(d)/'restored-backup.bin').exists())
    def test_36_single_source_zero_bytes_not_misreported_as_backup(self):
        with self.assertRaises(ValueError):self.create(source=PartialReader(b''))
        self.assertEqual(self.a.writes,0)
    def test_37_source_max_must_be_nonzero_integer(self):
        with self.assertRaises(ValueError):self.create(max_source_bytes=0)
    def test_38_boolean_chunk_size_denied(self):
        with self.assertRaises(ValueError):self.create(chunk_bytes=True)
    def test_39_source_metadata_never_claims_independent_restore_success(self):
        receipt=self.create()
        self.assertFalse(receipt.restores_verified)
        self.assertFalse(receipt.commercial_release_authorized)
        self.assertFalse(json.loads(self.manifest())['restore_verified'])
    def test_40_dual_independence_is_not_provider_legal_proof(self):
        receipt=self.create()
        self.assertEqual(receipt.claimed_owner_a,'Drive-A')
        self.assertEqual(receipt.claimed_owner_b,'Drive-B')
        self.assertNotIn(b'private-key',self.manifest())

    def test_41_never_report_verified_cloud_identity_without_oauth_adapter(self):
        receipt=self.create()
        self.assertFalse(receipt.cloud_account_identity_verified_by_this_code)
        self.assertFalse(receipt.current_source_consistency_verified)
    def test_42_no_generic_complete_or_live_ready_property(self):
        receipt=self.create()
        self.assertFalse(hasattr(receipt,'complete'))
        self.assertFalse(hasattr(receipt,'payable'))
        self.assertFalse(receipt.commercial_release_authorized)

if __name__=='__main__':unittest.main()
