"""Isolated offline tests for MojPlayWin's read-only encrypted inquiry desk.
Fixtures are synthetic, no real inquiries, network, mail or server writes.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone

PHP = shutil.which('php')
SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/mpw_revenue_owner_inquiries_readonly_20261114.php'
SYNTHETIC = {
    'source': 'first_party_mpw_revenue', 'consent': True,
    'service': 'website-doctor', 'email': 'synthetic@client.example',
    'created_at': datetime.now(timezone.utc).isoformat(),
    'name': 'Synthetic Client', 'details': 'Synthetic scope. This is not an actual lead.',
}
GENERATOR = r'''$key=file_get_contents($argv[1]);$plain=stream_get_contents(STDIN);
$iv=random_bytes(12);$tag='';$ct=openssl_encrypt($plain,'aes-256-gcm',$key,OPENSSL_RAW_DATA,$iv,$tag);
if($ct===false)exit(2);echo json_encode(['v'=>1,'iv'=>base64_encode($iv),
'tag'=>base64_encode($tag),'cipher'=>base64_encode($ct)],JSON_THROW_ON_ERROR);'''

@unittest.skipUnless(PHP is not None, 'PHP CLI required')
class CommercialLeadDeskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mpw-lead-desk-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        self.key = self.root / '.inquiry-key'
        self.key.write_bytes(os.urandom(32))
        self.key.chmod(0o600)
        self.fixture = self.root / '.mpw-fixture'
        self.fixture.write_text('synthetic only')
        self.fixture.chmod(0o600)
        self.counter = 0

    def execute(self, *args, override=None):
        env = dict(os.environ, MPW_INQUIRY_TEST_MODE='1', MPW_INQUIRY_TEST_ROOT=str(self.root))
        if override: env.update(override)
        return subprocess.run([PHP, str(SCRIPT), *args], env=env,
                              capture_output=True, text=True, timeout=8)

    def payload(self, **overrides):
        self.counter += 1
        record = dict(SYNTHETIC, **overrides)
        raw = subprocess.run([PHP, '-r', GENERATOR, str(self.key)],
                             input=json.dumps(record), capture_output=True,
                             text=True, timeout=8, check=True).stdout
        filename = f"20261114-{self.counter:018X}.json"
        file = self.root / filename
        file.write_text(raw, encoding='utf-8')
        file.chmod(0o600)
        return file, filename

    def summary(self):
        proc = self.execute('summary')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.startswith('MPW_LEAD_DESK_READONLY='))
        return json.loads(proc.stdout.split('=', 1)[1])

    def test_01_empty_folder_is_readonly(self):
        v=self.summary();self.assertEqual(v['scanned'],0);self.assertTrue(v['read_only'])

    def test_02_no_email_or_orders_emitted(self):
        v=self.summary();self.assertEqual((v['emails_sent'],v['orders_created'],v['payments_created']),(0,0,0))

    def test_03_valid_encrypted_lead_decrypts(self):
        self.payload();v=self.summary();self.assertEqual((v['valid'],v['invalid']),(1,0))

    def test_04_summary_service_counts(self):
        self.payload(service='website-doctor');self.payload(service='ai-automation');v=self.summary()
        self.assertEqual(v['by_service'],{'ai-automation':1,'website-doctor':1})

    def test_05_no_contact_data_in_summary(self):
        self.payload();out=self.execute('summary').stdout
        self.assertNotIn('synthetic@client.example',out);self.assertNotIn('Synthetic Client',out)

    def test_06_inspect_by_reference_only(self):
        _,filename=self.payload();ref=filename[9:27];result=self.execute('inspect',ref)
        self.assertEqual(result.returncode,0,result.stderr)
        obj=json.loads(result.stdout.split('=',1)[1]);self.assertEqual(obj['record']['reference'],ref)

    def test_07_inspect_redacts_email_and_details(self):
        _,filename=self.payload();result=self.execute('inspect',filename[9:27]);self.assertEqual(result.returncode,0)
        self.assertNotIn('synthetic@client.example',result.stdout);self.assertNotIn('Synthetic scope',result.stdout)

    def test_08_nonexistent_reference_rejected(self):
        proc=self.execute('inspect','F'*18);self.assertEqual(proc.returncode,2)
        self.assertIn('REFERENCE_NOT_FOUND',proc.stderr)

    def test_09_path_traversal_rejected(self):
        proc=self.execute('inspect','../../etc/passwd');self.assertEqual(proc.returncode,2)
        self.assertIn('INVALID_REFERENCE',proc.stderr)

    def test_10_unknown_command_rejected(self):
        proc=self.execute('dispatch');self.assertEqual(proc.returncode,2)
        self.assertIn('USAGE_SUMMARY_OR_INSPECT',proc.stderr)

    def test_11_summary_extra_argument_rejected(self):
        proc=self.execute('summary','secret');self.assertEqual(proc.returncode,2)
        self.assertIn('INVALID_PAGE',proc.stderr)

    def test_12_malformed_json_counted_invalid(self):
        p=self.root/('20261114-'+'1'*18+'.json');p.write_text('{');p.chmod(0o600)
        v=self.summary();self.assertEqual(v['invalid'],1)

    def test_13_ciphertext_tamper_rejected(self):
        p,_=self.payload();obj=json.loads(p.read_text());obj['cipher']='AA'+obj['cipher'][2:]
        p.write_text(json.dumps(obj));v=self.summary();self.assertEqual(v['invalid'],1)

    def test_14_aead_tag_tamper_rejected(self):
        p,_=self.payload();obj=json.loads(p.read_text());obj['tag']='AA'+obj['tag'][2:]
        p.write_text(json.dumps(obj));v=self.summary();self.assertEqual(v['invalid'],1)

    def test_15_invalid_consent_rejected(self):
        self.payload(consent=False);v=self.summary();self.assertEqual(v['invalid'],1)

    def test_16_unrecognized_source_rejected(self):
        self.payload(source='unauthorized_source');v=self.summary();self.assertEqual(v['invalid'],1)

    def test_17_unknown_service_rejected(self):
        self.payload(service='fake-investment-service');v=self.summary();self.assertEqual(v['invalid'],1)

    def test_18_invalid_contact_email_rejected(self):
        self.payload(email='not-email');v=self.summary();self.assertEqual(v['invalid'],1)

    def test_19_wrong_key_length_fails_closed(self):
        self.key.write_bytes(b'123');r=self.execute('summary');self.assertEqual(r.returncode,2)
        self.assertIn('PRIVATE_KEY_UNSAFE',r.stderr)

    def test_20_world_readable_key_fails_closed(self):
        self.key.chmod(0o644);r=self.execute('summary');self.assertEqual(r.returncode,2)
        self.assertIn('PRIVATE_KEY_UNSAFE',r.stderr)

    def test_21_world_readable_private_root_rejected(self):
        self.root.chmod(0o755);r=self.execute('summary');self.assertEqual(r.returncode,2)
        self.assertIn('INVALID_TEST_FIXTURE',r.stderr)

    def test_22_symlink_record_ignored_not_followed(self):
        p,_=self.payload();alias=self.root/('20261114-'+'A'*18+'.json');alias.symlink_to(p)
        v=self.summary();self.assertEqual((v['valid'],v['invalid']),(1,1))

    def test_23_bad_envelope_version_rejected(self):
        p,_=self.payload();obj=json.loads(p.read_text());obj['v']=3;p.write_text(json.dumps(obj))
        self.assertEqual(self.summary()['invalid'],1)

    def test_24_oversized_envelope_rejected(self):
        p,_=self.payload();p.write_text('X'*12001);self.assertEqual(self.summary()['invalid'],1)

    def test_25_older_24h_and_72h_counters(self):
        ancient=(datetime.now(timezone.utc)-timedelta(days=4)).isoformat()
        recent=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
        self.payload(created_at=ancient);self.payload(created_at=recent)
        v=self.summary();self.assertEqual((v['older_than_24h'],v['older_than_72h']),(2,1))

    def test_26_marker_does_not_mean_customer_contacted(self):
        _,name=self.payload();import hashlib
        mark=self.root/('.owner-dispatched-'+hashlib.sha256(name.encode()).hexdigest()+'.json')
        mark.write_text('{"queued_at":"2026-11-14"}');mark.chmod(0o600)
        v=self.summary();self.assertEqual(v['notified_to_local_mta'],1)
        self.assertNotIn('customer_contacted',v)

    def test_27_no_marker_is_notified_zero(self):
        self.payload();v=self.summary();self.assertEqual(v['not_yet_notified'],1)

    def test_28_inspect_never_claims_payment(self):
        _,name=self.payload();v=self.execute('inspect',name[9:27]);j=json.loads(v.stdout.split('=',1)[1])
        self.assertEqual(j['record']['payment_received'],'unverified')

    def test_29_nonmatching_filenames_ignored(self):
        p=self.root/'unsafe-filename.json';p.write_text('broken')
        v=self.summary();self.assertEqual(v['scanned'],0)

    def test_30_fixture_marker_required(self):
        self.fixture.unlink();v=self.execute('summary');self.assertEqual(v.returncode,2)
        self.assertIn('INVALID_TEST_FIXTURE',v.stderr)

    def test_31_no_test_mode_rejects_non_owner(self):
        v=self.execute('summary',override={'MPW_INQUIRY_TEST_MODE':'0'})
        self.assertEqual(v.returncode,2)
        self.assertIn('WRONG_OS_USER',v.stderr)

    def test_32_repeated_summary_does_not_modify_files(self):
        self.payload();before={p.name:p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        self.summary();self.summary();after={p.name:p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        self.assertEqual(before,after)


    def test_33_pending_reference_list_is_pseudonymous(self):
        _,name=self.payload();v=self.summary()
        self.assertEqual(v['pending_references'],[name[9:27]])
        self.assertNotIn('synthetic@client.example',json.dumps(v))

    def test_34_recent_leads_prioritized(self):
        self.payload(service='website-doctor');_,newest=self.payload(service='ai-automation')
        v=self.summary();self.assertEqual(v['pending_references'][0],newest[9:27])

    def test_35_pending_references_bounded_to_25(self):
        for _ in range(30): self.payload()
        v=self.summary();self.assertEqual(len(v['pending_references']),25)
        self.assertTrue(v['pending_refs_truncated'])

    def test_36_pending_summary_excludes_notified_marker(self):
        _,name=self.payload();import hashlib
        mark=self.root/('.owner-dispatched-'+hashlib.sha256(name.encode()).hexdigest()+'.json')
        mark.write_text('notified');mark.chmod(0o600)
        v=self.summary();self.assertEqual(v['pending_references'],[])

    def test_37_invalid_page_0_rejected(self):
        x=self.execute('summary','0');self.assertEqual(x.returncode,2)
        self.assertIn('INVALID_PAGE',x.stderr)

    def test_38_invalid_page_10000_rejected(self):
        x=self.execute('summary','10000');self.assertEqual(x.returncode,2)
        self.assertIn('INVALID_PAGE',x.stderr)

    def test_39_page_two_scans_remaining_not_hidden(self):
        for i in range(501):
            name=f'20261114-{i+1:018X}.json'
            p=self.root/name;p.write_text('not-json');p.chmod(0o600)
        first=self.summary();second=self.execute('summary','2')
        self.assertEqual(second.returncode,0,second.stderr)
        v=json.loads(second.stdout.split('=',1)[1]);self.assertEqual(first['scanned'],500)
        self.assertEqual(v['scanned'],1);self.assertEqual(v['page'],2)
        self.assertEqual((v['total_files'],v['total_pages']),(501,2))
        self.assertTrue(v['backlog_truncated'])

    def test_40_page_outside_range_is_empty_not_misleading(self):
        self.payload();r=self.execute('summary','2');self.assertEqual(r.returncode,0)
        v=json.loads(r.stdout.split('=',1)[1]);self.assertEqual(v['scanned'],0)
        self.assertEqual(v['total_files'],1)


if __name__=='__main__':
    unittest.main(verbosity=2)
