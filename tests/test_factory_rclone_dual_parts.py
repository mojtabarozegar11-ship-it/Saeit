"""Offline, no-network adversarial tests for owner Drive multipart transport."""
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import factory_rclone_dual_parts as m

PROOF = b'{"backup":"F01","safe":"manifest"}'
PROOF_HASH = hashlib.sha256(PROOF).hexdigest()
ROOT_A='191sAkv4A01S9o6zhx-vM5xM7WO31qHPn'
ROOT_B='1e6D3Ek4k-4JT_oyEoiY_JejErZFssrC_'
PROOF_PATH='F-01 Factory VPS encrypted recovery 2026-10-30/manifest.json'

class FakeDriveAdapter(m.RcloneDualStore):
    def _run(self,*argv,max_output=0,input_bytes=None):
        self.calls.append((argv, len(input_bytes) if input_bytes is not None else None))
        cmd=argv[0]
        if cmd=='cat':
            remote,path=argv[1].split(':',1)
            if path==PROOF_PATH: return self.proofs.get(remote,b'')
            return self.objects.get(argv[1],b'')
        if cmd=='about':
            remote=argv[2][:-1] if argv[2].endswith(':') else argv[2]
            return json.dumps({'free':self.free.get(remote)}).encode()
        if cmd=='mkdir':
            self.dirs.add(argv[1]);return b''
        if cmd=='rcat':
            self.objects[argv[1]]=input_bytes
            return b''
        raise AssertionError('unexpected rclone call')

class TestRcloneDualDrive(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'rclone.conf'
        self.write_config()
        self.fake=FakeDriveAdapter(self.path,remote_a='factory_a',remote_b='factory_b',
            expected_root_a=ROOT_A,expected_root_b=ROOT_B,
            proof_path=PROOF_PATH,proof_sha256=PROOF_HASH,
            max_source_bytes=15*1024*1024,chunk_bytes=4*1024*1024,
            free_reserve_bytes=1*1024*1024,rclone_exe=sys.executable)
        self.fake.calls=[]
        self.fake.proofs={'factory_a':PROOF,'factory_b':PROOF}
        self.fake.free={'factory_a':100*1024*1024,'factory_b':100*1024*1024}
        self.fake.objects={}
        self.fake.dirs=set()
    def write_config(self,a_token='{"refresh_token":"A"}',b_token='{"refresh_token":"B"}',ra=ROOT_A,rb=ROOT_B):
        self.path.write_text('[factory_a]\ntype = drive\nroot_folder_id = '+ra+'\ntoken = '+a_token+'\n'
                             '[factory_b]\ntype = drive\nroot_folder_id = '+rb+'\ntoken = '+b_token+'\n')
        self.path.chmod(0o600)
    def test_01_proven_quota_and_private_proof(self):
        p=self.fake.preflight()
        self.assertTrue(p.proof_readbacks_verified)
        self.assertFalse(p.current_backup_created)
        self.assertEqual(len([x for x in self.fake.calls if x[0][0]=='cat']),2)
    def test_02_preflight_no_cloud_write(self):
        self.fake.preflight()
        self.assertFalse(any(x[0][0] in ('mkdir','rcat') for x in self.fake.calls))
    def test_03_missing_config_holds(self):
        self.path.unlink()
        with self.assertRaisesRegex(m.TransferHold,'UNSAFE_OR_MISSING_OWNER_CONFIG'):self.fake.preflight()
    def test_04_world_readable_config_holds(self):
        self.path.chmod(0o644)
        with self.assertRaisesRegex(m.TransferHold,'UNSAFE_OR_MISSING_OWNER_CONFIG'):self.fake.preflight()
    def test_05_symlink_config_holds(self):
        actual=self.path.parent/'actual';self.path.rename(actual);self.path.symlink_to(actual)
        with self.assertRaisesRegex(m.TransferHold,'UNSAFE_OR_MISSING_OWNER_CONFIG'):self.fake.preflight()
    def test_06_wrong_root_a_holds(self):
        self.write_config(ra='WRONG_ROOT')
        with self.assertRaisesRegex(m.TransferHold,'OWNER_DRIVE_REMOTE_CONFIG_UNVERIFIED'):self.fake.preflight()
    def test_07_wrong_root_b_holds(self):
        self.write_config(rb='WRONG_ROOT')
        with self.assertRaisesRegex(m.TransferHold,'OWNER_DRIVE_REMOTE_CONFIG_UNVERIFIED'):self.fake.preflight()
    def test_08_same_oauth_token_holds(self):
        self.write_config(a_token='SAME',b_token='SAME')
        with self.assertRaisesRegex(m.TransferHold,'SAME_OAUTH_CREDENTIALS_REJECTED'):self.fake.preflight()
    def test_09_first_private_proof_missing_holds(self):
        self.fake.proofs['factory_a']=b''
        with self.assertRaisesRegex(m.TransferHold,'PRIVATE_OWNER_PROOF_MISMATCH'):self.fake.preflight()
    def test_10_second_private_proof_missing_holds(self):
        self.fake.proofs['factory_b']=b''
        with self.assertRaisesRegex(m.TransferHold,'PRIVATE_OWNER_PROOF_MISMATCH'):self.fake.preflight()
    def test_11_first_low_quota_holds(self):
        self.fake.free['factory_a']=100
        with self.assertRaisesRegex(m.TransferHold,'INSUFFICIENT_PROVIDER_VERIFIED_FREE_BYTES'):self.fake.preflight()
    def test_12_second_low_quota_holds(self):
        self.fake.free['factory_b']=100
        with self.assertRaisesRegex(m.TransferHold,'INSUFFICIENT_PROVIDER_VERIFIED_FREE_BYTES'):self.fake.preflight()
    def test_13_unknown_quota_holds(self):
        self.fake.free['factory_b']=None
        with self.assertRaisesRegex(m.TransferHold,'DRIVE_FREE_QUOTA_NOT_PROVEN'):self.fake.preflight()
    def test_14_negative_quota_holds(self):
        self.fake.free['factory_b']=-1
        with self.assertRaisesRegex(m.TransferHold,'DRIVE_FREE_QUOTA_NOT_PROVEN'):self.fake.preflight()
    def test_15_boolean_quota_holds(self):
        self.fake.free['factory_b']=True
        with self.assertRaisesRegex(m.TransferHold,'DRIVE_FREE_QUOTA_NOT_PROVEN'):self.fake.preflight()
    def test_16_same_remote_holds(self):
        with self.assertRaisesRegex(m.TransferHold,'UNTRUSTED_REMOTE_IDENTITY_OR_PROOF'):
            m.RcloneDualStore(self.path,remote_a='same',remote_b='same',expected_root_a=ROOT_A,expected_root_b=ROOT_B,
              proof_path=PROOF_PATH,proof_sha256=PROOF_HASH,max_source_bytes=10000,chunk_bytes=4096,
              free_reserve_bytes=1<<20,rclone_exe=sys.executable)
    def test_17_same_root_holds(self):
        with self.assertRaisesRegex(m.TransferHold,'UNTRUSTED_REMOTE_IDENTITY_OR_PROOF'):
            m.RcloneDualStore(self.path,remote_a='factory_a',remote_b='factory_b',expected_root_a=ROOT_A,expected_root_b=ROOT_A,
              proof_path=PROOF_PATH,proof_sha256=PROOF_HASH,max_source_bytes=10000,chunk_bytes=4096,
              free_reserve_bytes=1<<20,rclone_exe=sys.executable)
    def test_18_traversal_proof_holds(self):
        with self.assertRaisesRegex(m.TransferHold,'UNTRUSTED_REMOTE_IDENTITY_OR_PROOF'):
            m.RcloneDualStore(self.path,remote_a='factory_a',remote_b='factory_b',expected_root_a=ROOT_A,expected_root_b=ROOT_B,
              proof_path='../owner.pem',proof_sha256=PROOF_HASH,max_source_bytes=10000,chunk_bytes=4096,
              free_reserve_bytes=1<<20,rclone_exe=sys.executable)
    def test_19_missing_preflight_prevents_mkdir(self):
        with self.assertRaisesRegex(m.TransferHold,'MISSING_PROVIDER_PREFLIGHT'):
            self.fake.callbacks('factory-current-'+'f'*32)
        self.assertEqual(self.fake.calls,[])
    def test_20_unsafe_prefix_holds(self):
        self.fake.preflight()
        with self.assertRaisesRegex(m.TransferHold,'UNSAFE_RUN_PREFIX'):self.fake.callbacks('../escape')
    def test_21_callbacks_create_only_private_run_folders(self):
        self.fake.preflight(); self.fake.callbacks('factory-current-'+'a'*32)
        self.assertEqual(len(self.fake.dirs),2)
        self.assertTrue(all(':current-backups/factory-current-' in p for p in self.fake.dirs))
    def test_22_genuine_cipher_part_upload_and_readback_both(self):
        self.fake.preflight();a,b,ra,rb=self.fake.callbacks('factory-current-'+'b'*32)
        name='f01v2-abcdef-000001.enc';payload=m.F01_MAGIC+b'Z'*100
        a(name,payload);b(name,payload)
        self.assertEqual(ra(name),payload);self.assertEqual(rb(name),payload)
        self.assertEqual(len(self.fake.objects),2)
    def test_23_plaintext_upload_denied(self):
        self.fake.preflight();a,b,_,_=self.fake.callbacks('factory-current-'+'c'*32)
        with self.assertRaisesRegex(m.TransferHold,'PLAINTEXT_OR_OVERSIZED_PART_DENIED'):a('part.enc',b'PLAIN TEXT SQL SECRET'*30)
    def test_24_oversized_ciphertext_denied(self):
        self.fake.preflight();a,b,_,_=self.fake.callbacks('factory-current-'+'d'*32)
        with self.assertRaisesRegex(m.TransferHold,'PLAINTEXT_OR_OVERSIZED_PART_DENIED'):a('part.enc',m.F01_MAGIC+b'X'*m.MAX_CIPHER_PART_BYTES)
    def test_25_duplicate_upload_denied(self):
        self.fake.preflight();a,b,_,_=self.fake.callbacks('factory-current-'+'e'*32)
        a('part.enc',m.F01_MAGIC+b'X'*100)
        with self.assertRaisesRegex(m.TransferHold,'DUPLICATE_PART_UPLOAD'):a('part.enc',m.F01_MAGIC+b'X'*100)
    def test_26_unuploaded_readback_denied(self):
        self.fake.preflight();a,b,ra,rb=self.fake.callbacks('factory-current-'+'f'*32)
        with self.assertRaisesRegex(m.TransferHold,'UNUPLOADED_PART_READBACK_DENIED'):ra('notuploaded.enc')
    def test_27_valid_manifest_uploads_last_like_payload(self):
        self.fake.preflight();a,b,ra,rb=self.fake.callbacks('factory-current-'+'1'*32)
        a('f01v2-abc-manifest.json',b'{"schema":"something"}')
        self.assertEqual(ra('f01v2-abc-manifest.json'),b'{"schema":"something"}')
    def test_28_object_name_traversal_denied(self):
        self.fake.preflight();a,b,_,_=self.fake.callbacks('factory-current-'+'2'*32)
        with self.assertRaisesRegex(m.TransferHold,'INVALID_ENCRYPTED_PART'):a('../folder.enc',m.F01_MAGIC+b'X'*100)
    def test_29_upload_rejects_other_extension(self):
        self.fake.preflight();a,b,_,_=self.fake.callbacks('factory-current-'+'3'*32)
        with self.assertRaisesRegex(m.TransferHold,'UNEXPECTED_UPLOAD_OBJECT'):a('file.sql',b'not encrypted')
    def test_30_rejects_missing_rclone_binary(self):
        with self.assertRaisesRegex(m.TransferHold,'RCLONE_NOT_INSTALLED'):
            m.RcloneDualStore(self.path,remote_a='factory_a',remote_b='factory_b',expected_root_a=ROOT_A,expected_root_b=ROOT_B,
              proof_path=PROOF_PATH,proof_sha256=PROOF_HASH,max_source_bytes=10000,chunk_bytes=4096,
              free_reserve_bytes=1<<20,rclone_exe='relative/rclone')
    def test_31_runner_metadata_no_secrets(self):
        d=m.runner_metadata_only(self.path)
        self.assertFalse(d['oauth_tokens_read']);self.assertFalse(d['provider_queried'])
        self.assertFalse(d['new_backup_created'])
    def test_32_runner_metadata_missing_config(self):
        self.path.unlink();self.assertFalse(m.runner_metadata_only(self.path)['owner_local_config_secure_file_present'])
    def test_33_rclone_subprocess_no_shell_uses_bounded(self):
        with patch.object(m.subprocess,'run') as run:
            run.return_value.returncode=0;run.return_value.stdout=b'GOOD'
            self.assertEqual(m._rclone_call(['/usr/bin/rclone','about'],max_output=4),b'GOOD')
            self.assertFalse(run.call_args.kwargs.get('shell',False))
    def test_34_rclone_output_above_bound_holds(self):
        with patch.object(m.subprocess,'run') as run:
            run.return_value.returncode=0;run.return_value.stdout=b'TOO-LONG'
            with self.assertRaisesRegex(m.TransferHold,'RCLONE_OUTPUT_OVERSIZE'):
                m._rclone_call(['/usr/bin/rclone','cat'],max_output=3)
    def test_35_rclone_failure_redacted(self):
        with patch.object(m.subprocess,'run') as run:
            run.return_value.returncode=99;run.return_value.stdout=b'PRIVATE_PASSWORD'
            with self.assertRaisesRegex(m.TransferHold,'RCLONE_PROVIDER_OPERATION_FAILED'):
                m._rclone_call(['/usr/bin/rclone','cat'],max_output=100)
    def test_36_gzip_success_producer_no_shell(self):
        with m.VerifiedGzipSource([sys.executable,'-c',"import sys;sys.stdout.buffer.write(b'hello'*5000)"],
                                  gzip_executable='/usr/bin/gzip',process_timeout=60) as s:
            chunks=[]
            while True:
                x=s.read(4096)
                if not x:break
                chunks.append(x)
        import gzip
        self.assertEqual(gzip.decompress(b''.join(chunks)),b'hello'*5000)
    def test_37_failed_producer_does_not_report_EOF(self):
        with self.assertRaisesRegex(m.TransferHold,'BACKUP_SOURCE_OR_COMPRESSOR_FAILED'):
            with m.VerifiedGzipSource([sys.executable,'-c',"import sys;print('partial');sys.exit(7)"],
                                      gzip_executable='/usr/bin/gzip',process_timeout=60) as s:
                while s.read(4096):pass
    def test_38_source_invalid_read_bound_denied(self):
        with self.assertRaisesRegex(m.TransferHold,'INVALID_STREAM_READ'):
            m.VerifiedGzipSource([sys.executable,'-c','print(1)'],gzip_executable='/usr/bin/gzip').read(-1)
    def test_39_source_command_invalid_denied(self):
        with self.assertRaisesRegex(m.TransferHold,'UNVETTED_SOURCE_PROCESS'):
            m.VerifiedGzipSource([''],gzip_executable='/usr/bin/gzip')
    def test_40_source_process_cleans_up_on_early_stop(self):
        with m.VerifiedGzipSource([sys.executable,'-c',"import time;print('hello',flush=True);time.sleep(60)"],
                                  gzip_executable='/usr/bin/gzip',process_timeout=60) as s:
            self.assertFalse(s.finished)
        self.assertIsNotNone(s.producer.poll())
        self.assertIsNotNone(s.compressor.poll())

if __name__=='__main__':unittest.main()
