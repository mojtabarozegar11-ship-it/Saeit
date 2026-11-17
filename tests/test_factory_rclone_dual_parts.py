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
        if cmd=='lsf':
            return self.listings.get(argv[1], b'')
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
        self.fake.listings={}
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
        a,b,ra,rb,part,payload,manifest_name,manifest=self._ready_one_cipher('1')
        a(manifest_name,manifest)
        b(manifest_name,manifest)
        self.assertEqual(ra(manifest_name),manifest)
        self.assertEqual(rb(manifest_name),manifest)
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

    def test_41_existing_a_run_directory_denied_before_mkdir(self):
        self.fake.preflight()
        run_id='factory-current-'+'4'*32
        self.fake.listings['factory_a:current-backups/']=(run_id+'/\n').encode()
        with self.assertRaisesRegex(m.TransferHold,'BACKUP_RUN_NAMESPACE_ALREADY_EXISTS'):
            self.fake.callbacks(run_id)
        self.assertEqual(self.fake.dirs,set())
    def test_42_existing_b_run_directory_denied_before_mkdir(self):
        self.fake.preflight()
        run_id='factory-current-'+'5'*32
        self.fake.listings['factory_b:current-backups/']=(run_id.upper()+'/\n').encode()
        with self.assertRaisesRegex(m.TransferHold,'BACKUP_RUN_NAMESPACE_ALREADY_EXISTS'):
            self.fake.callbacks(run_id)
        self.assertEqual(self.fake.dirs,set())
    def test_43_unreadable_run_listing_denied_before_mkdir(self):
        self.fake.preflight()
        run_id='factory-current-'+'6'*32
        self.fake.listings['factory_b:current-backups/']=b'\xff\xff'
        with self.assertRaisesRegex(m.TransferHold,'REMOTE_NAMESPACE_LIST_UNREADABLE'):
            self.fake.callbacks(run_id)
        self.assertFalse(self.fake.dirs)
    def test_44_pre_existing_files_after_mkdir_holds(self):
        self.fake.preflight()
        run_id='factory-current-'+'7'*32
        self.fake.listings['factory_a:current-backups/'+run_id+'/']=b'000001.enc\n'
        with self.assertRaisesRegex(m.TransferHold,'NEW_BACKUP_RUN_NAMESPACE_NOT_EMPTY'):
            self.fake.callbacks(run_id)
        self.assertEqual(len(self.fake.dirs),2)
        self.assertEqual(self.fake.objects,{})
    def test_45_reused_callbacks_denied_even_with_new_namespace(self):
        self.fake.preflight()
        self.fake.callbacks('factory-current-'+'8'*32)
        with self.assertRaisesRegex(m.TransferHold,'MULTIPLE_RUNS_ON_SAME_TRANSPORT_DENIED'):
            self.fake.callbacks('factory-current-'+'9'*32)
        self.assertEqual(len(self.fake.dirs),2)
    def test_46_failure_not_treated_as_empty(self):
        self.fake.preflight()
        run_id='factory-current-'+'a'*32
        orig=self.fake._run
        def unreachable(*argv,**kwargs):
            if argv[0]=='lsf':raise m.TransferHold('RCLONE_PROVIDER_OPERATION_FAILED')
            return orig(*argv,**kwargs)
        with patch.object(self.fake,'_run',side_effect=unreachable):
            with self.assertRaisesRegex(m.TransferHold,'RCLONE_PROVIDER_OPERATION_FAILED'):
                self.fake.callbacks(run_id)
        self.assertFalse(self.fake.dirs)


    def _new_cipher_callbacks(self, letter):
        self.fake.preflight()
        return self.fake.callbacks('factory-current-'+letter*32)

    def _manifest_fixture(self, part_name, payload, **updates):
        run=part_name.split('-')[1]
        name='f01v2-'+run+'-manifest.json'
        plain_len=len(payload)-len(m.F01_MAGIC)-41
        data={
            'schema':'factory.dual-encrypted-stream.f01v2',
            'run_id':run,'public_key_spki_sha256':'e'*64,
            'wrapped_key':'A'*128,'nonce_prefix':'QUFBQUFBQUE=',
            'chunk_limit':4096,'plain_total':plain_len,
            'cipher_total':len(payload),
            'parts':[{'name':part_name,'index':1,'cipher_bytes':len(payload),
                      'cipher_sha256':m._sha(payload),'plain_bytes':plain_len}],
            'owner_refs':['a'*32,'b'*32],
            'source_consistency_external':False,'restore_verified':False,
            'manifest_mac_sha256':'c'*64,
        }
        data.update(updates)
        return name,json.dumps(data,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode('ascii')

    def _ready_one_cipher(self, letter):
        a,b,ra,rb=self._new_cipher_callbacks(letter)
        part_name='f01v2-'+'a'*32+'-000001.enc'
        payload=m.F01_MAGIC+b'X'*100
        a(part_name,payload);b(part_name,payload)
        self.assertEqual(ra(part_name),payload)
        self.assertEqual(rb(part_name),payload)
        manifest_name,manifest=self._manifest_fixture(part_name,payload)
        return a,b,ra,rb,part_name,payload,manifest_name,manifest

    def test_47_manifest_first_is_denied(self):
        a,b,ra,rb=self._new_cipher_callbacks('b')
        with self.assertRaisesRegex(m.TransferHold,'MANIFEST_BEFORE_DUAL_PART_READBACK_DENIED'):
            a('done-manifest.json',b'{}')
        self.assertFalse(any(':done-manifest.json' in x for x in self.fake.objects))

    def test_48_one_provider_cipher_only_denies_manifest(self):
        a,b,ra,rb=self._new_cipher_callbacks('c')
        a('one.enc',m.F01_MAGIC+b'0'*100)
        with self.assertRaisesRegex(m.TransferHold,'MANIFEST_BEFORE_DUAL_PART_READBACK_DENIED'):
            a('done-manifest.json',b'{}')

    def test_49_dual_upload_without_readback_denies_manifest(self):
        a,b,ra,rb=self._new_cipher_callbacks('d')
        part=m.F01_MAGIC+b'1'*100
        a('one.enc',part);b('one.enc',part)
        with self.assertRaisesRegex(m.TransferHold,'MANIFEST_BEFORE_DUAL_PART_READBACK_DENIED'):
            a('done-manifest.json',b'{}')

    def test_50_partial_readback_denies_manifest(self):
        a,b,ra,rb=self._new_cipher_callbacks('e')
        part=m.F01_MAGIC+b'2'*100
        a('one.enc',part);b('one.enc',part);ra('one.enc')
        with self.assertRaisesRegex(m.TransferHold,'MANIFEST_BEFORE_DUAL_PART_READBACK_DENIED'):
            b('done-manifest.json',b'{}')

    def test_51_different_cipher_across_destinations_denies_manifest(self):
        a,b,ra,rb=self._new_cipher_callbacks('f')
        a('one.enc',m.F01_MAGIC+b'3'*100)
        b('one.enc',m.F01_MAGIC+b'4'*100)
        ra('one.enc');rb('one.enc')
        with self.assertRaisesRegex(m.TransferHold,'MANIFEST_BEFORE_DUAL_PART_READBACK_DENIED'):
            a('done-manifest.json',b'{}')

    def test_52_corrupted_remote_readback_does_not_count(self):
        a,b,ra,rb=self._new_cipher_callbacks('0')
        part=m.F01_MAGIC+b'5'*100
        a('one.enc',part);b('one.enc',part)
        self.fake.objects['factory_a:current-backups/factory-current-'+'0'*32+'/one.enc']=m.F01_MAGIC+b'6'*100
        with self.assertRaisesRegex(m.TransferHold,'REMOTE_CIPHERTEXT_READBACK_MISMATCH'):
            ra('one.enc')
        rb('one.enc')
        with self.assertRaisesRegex(m.TransferHold,'MANIFEST_BEFORE_DUAL_PART_READBACK_DENIED'):
            b('done-manifest.json',b'{}')

    def test_53_no_ciphertext_after_first_manifest(self):
        a,b,ra,rb,part,payload,name,manifest=self._ready_one_cipher('1')
        a(name,manifest)
        with self.assertRaisesRegex(m.TransferHold,'CIPHERTEXT_AFTER_MANIFEST_DENIED'):
            b('two.enc',payload)

    def test_54_two_manifest_names_conflict_denied(self):
        a,b,ra,rb,part,payload,name,manifest=self._ready_one_cipher('2')
        a(name,manifest)
        with self.assertRaisesRegex(m.TransferHold,'CONFLICTING_COMPLETION_MANIFEST_DENIED'):
            b('second-manifest.json',manifest)

    def test_55_multi_part_partial_readback_denies_manifest(self):
        a,b,ra,rb=self._new_cipher_callbacks('3')
        for name,number in (('one.enc',b'9'),('two.enc',b'A')):
            part=m.F01_MAGIC+number*100
            a(name,part);b(name,part)
        ra('one.enc');rb('one.enc');ra('two.enc')
        with self.assertRaisesRegex(m.TransferHold,'MANIFEST_BEFORE_DUAL_PART_READBACK_DENIED'):
            a('done-manifest.json',b'{}')


    def test_56_provider_a_b_manifest_content_difference_denied(self):
        a,b,ra,rb,part,payload,name,manifest=self._ready_one_cipher('4')
        a(name,manifest)
        alt=json.loads(manifest)
        alt['wrapped_key']='B'*128
        divergent=json.dumps(alt,sort_keys=True,separators=(',',':')).encode()
        with self.assertRaisesRegex(m.TransferHold,'TWO_DRIVES_MANIFEST_CONTENT_MISMATCH'):
            b(name,divergent)

    def test_57_corrupt_manifest_provider_readback_denied(self):
        a,b,ra,rb,part,payload,name,manifest=self._ready_one_cipher('5')
        a(name,manifest)
        key='factory_a:current-backups/factory-current-'+'5'*32+'/'+name
        self.fake.objects[key]=manifest[:-1]+b'0'
        with self.assertRaisesRegex(m.TransferHold,'REMOTE_MANIFEST_READBACK_MISMATCH'):
            ra(name)

    def test_58_manifest_wrong_part_name_denied(self):
        a,b,ra,rb,part,payload,name,manifest=self._ready_one_cipher('6')
        entries=json.loads(manifest)['parts']
        entries[0]['name']='wrong-000001.enc'
        bad_name,bad=self._manifest_fixture(part,payload,parts=entries)
        with self.assertRaisesRegex(m.TransferHold,'INVALID_OR_UNBOUND_COMPLETION_MANIFEST'):
            a(bad_name,bad)

    def test_59_manifest_wrong_sha_denied(self):
        a,b,ra,rb,part,payload,name,manifest=self._ready_one_cipher('7')
        entries=json.loads(manifest)['parts']
        entries[0]['cipher_sha256']='1'*64
        _,bad=self._manifest_fixture(part,payload,parts=entries)
        with self.assertRaisesRegex(m.TransferHold,'INVALID_OR_UNBOUND_COMPLETION_MANIFEST'):
            a(name,bad)

    def test_60_manifest_false_restore_claim_enforced(self):
        a,b,ra,rb,part,payload,name,manifest=self._ready_one_cipher('8')
        _,bad=self._manifest_fixture(part,payload,restore_verified=True)
        with self.assertRaisesRegex(m.TransferHold,'INVALID_OR_UNBOUND_COMPLETION_MANIFEST'):
            a(name,bad)

    def test_61_manifest_unknown_field_denied(self):
        a,b,ra,rb,part,payload,name,manifest=self._ready_one_cipher('9')
        _,bad=self._manifest_fixture(part,payload,untrusted_extra='x')
        with self.assertRaisesRegex(m.TransferHold,'INVALID_OR_UNBOUND_COMPLETION_MANIFEST'):
            a(name,bad)

    def test_62_manifest_duplicate_json_keys_denied(self):
        a,b,ra,rb,part,payload,name,manifest=self._ready_one_cipher('a')
        dup=manifest.replace(b'"schema":',b'"schema":"wrong","schema":',1)
        with self.assertRaisesRegex(m.TransferHold,'INVALID_OR_UNBOUND_COMPLETION_MANIFEST'):
            a(name,dup)

    def test_63_manifest_noncanonical_json_denied(self):
        a,b,ra,rb,part,payload,name,manifest=self._ready_one_cipher('b')
        noncanonical=json.dumps(json.loads(manifest),indent=2).encode()
        with self.assertRaisesRegex(m.TransferHold,'INVALID_OR_UNBOUND_COMPLETION_MANIFEST'):
            a(name,noncanonical)

    def test_64_manifest_wrong_plain_total_denied(self):
        a,b,ra,rb,part,payload,name,manifest=self._ready_one_cipher('c')
        _,bad=self._manifest_fixture(part,payload,plain_total=123456)
        with self.assertRaisesRegex(m.TransferHold,'INVALID_OR_UNBOUND_COMPLETION_MANIFEST'):
            a(name,bad)

    def test_65_manifest_missing_extra_part_denied(self):
        a,b,ra,rb,part,payload,name,manifest=self._ready_one_cipher('d')
        second='f01v2-'+'a'*32+'-000002.enc'
        a(second,payload);b(second,payload);ra(second);rb(second)
        with self.assertRaisesRegex(m.TransferHold,'INVALID_OR_UNBOUND_COMPLETION_MANIFEST'):
            a(name,manifest)

if __name__=='__main__':unittest.main()
