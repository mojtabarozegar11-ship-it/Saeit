"""Transfer-only factory OFF: no-network checks for cPanel immutable backup bridge."""
import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import factory_cpanel_existing_nov5_two_drive as m


class FactoryCpanelOldBackupTransportTests(unittest.TestCase):
    def fixture_file(self, contents=b"SAFE", mode=0o600):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        p=Path(t.name)/"owner-only"
        p.write_bytes(contents)
        p.chmod(mode)
        return p

    def fake_known(self):
        raw=b"sample-ed25519-public-wire-format"
        key=base64.b64encode(raw)
        fp="SHA256:"+base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")
        p=self.fixture_file(m.CPANEL_HOST.encode()+b" ssh-ed25519 "+key+b"\n")
        return p,fp

    def test_01_catalog_only_two_immutable_original_snapshots(self):
        self.assertEqual(set(m.SOURCES),{"nov5-a","nov5-b"})
        for name,digest in m.SOURCES.values():
            self.assertTrue(name.endswith(".sqlite3"))
            self.assertEqual(len(digest),64)

    def test_02_original_source_bytes_are_constant(self):
        self.assertEqual(m.SOURCE_BYTES,1408634880)
        self.assertEqual(m.CHUNK_BYTES,8388608)

    def test_03_immutable_proof_remains_owner_root(self):
        self.assertEqual(m.GOOGLE_A_ROOT,"191sAkv4A01S9o6zhx-vM5xM7WO31qHPn")
        self.assertNotEqual(m.GOOGLE_A_ROOT,m.GOOGLE_B_ROOT)
        self.assertEqual(len(m.PROOF_SHA256),64)

    def test_04_original_source_code_never_calls_mysql(self):
        self.assertNotIn("mysqldump",m.REMOTE_PY)
        self.assertNotIn("sqlite3.connect",m.REMOTE_PY)
        self.assertIn("O_NOFOLLOW",m.REMOTE_PY)
        self.assertNotIn("unlink(",m.REMOTE_PY)

    def test_05_secure_owner_regular_file(self):
        p=self.fixture_file()
        self.assertEqual(m._secure_file(p,256),b"SAFE")

    def test_06_world_readable_config_denied(self):
        p=self.fixture_file(mode=0o644)
        with self.assertRaisesRegex(m.TransferHold,"OWNER_FILE_NOT_SECURE"):
            m._secure_file(p,256)

    def test_07_symlink_credential_denied(self):
        p=self.fixture_file()
        link=p.parent/"symlink"
        link.symlink_to(p)
        with self.assertRaisesRegex(m.TransferHold,"OWNER_FILE_NOT_SECURE"):
            m._secure_file(link,256)

    def test_08_relative_credential_denied(self):
        with self.assertRaisesRegex(m.TransferHold,"OWNER_FILE_MUST_BE_ABSOLUTE"):
            m._secure_file(Path("private"),256)

    def test_09_bounded_owner_file(self):
        p=self.fixture_file(b"A"*257)
        with self.assertRaisesRegex(m.TransferHold,"OWNER_FILE_NOT_SECURE"):
            m._secure_file(p,256)

    def test_10_missing_owner_file_denied(self):
        with self.assertRaisesRegex(m.TransferHold,"OWNER_FILE_UNAVAILABLE"):
            m._secure_file(Path("/nonexistent/factory-protected-config"),256)

    def test_11_genuine_ed25519_fingerprint_required(self):
        p,fp=self.fake_known()
        with patch.object(m,"PIN_SHA256",fp):
            m._verify_cpanel_known_host(p.read_bytes())

    def test_12_cpanel_host_mismatch_denied(self):
        p,fp=self.fake_known()
        raw=p.read_bytes().replace(m.CPANEL_HOST.encode(),b"[somewhere.example]:1396")
        with patch.object(m,"PIN_SHA256",fp):
            with self.assertRaisesRegex(m.TransferHold,"CPANEL_KNOWN_HOSTS_UNEXPECTED_ENTRY"):
                m._verify_cpanel_known_host(raw)

    def test_13_duplicate_host_keys_denied(self):
        p,fp=self.fake_known()
        with patch.object(m,"PIN_SHA256",fp):
            with self.assertRaisesRegex(m.TransferHold,"CPANEL_HOST_FINGERPRINT_MISMATCH"):
                m._verify_cpanel_known_host(p.read_bytes()*2)

    def test_14_host_public_key_fingerprint_mismatch_denied(self):
        p,_=self.fake_known()
        with self.assertRaisesRegex(m.TransferHold,"CPANEL_HOST_FINGERPRINT_MISMATCH"):
            m._verify_cpanel_known_host(p.read_bytes())

    def test_15_bad_base64_knownhost_denied(self):
        with self.assertRaisesRegex(m.TransferHold,"CPANEL_HOST_KEY_BAD_BASE64"):
            m._verify_cpanel_known_host(
                m.CPANEL_HOST.encode()+b" ssh-ed25519 !!!not-a-key!!!!")

    def test_16_no_arbitrary_filename_accepted(self):
        conf=self.fixture_file()
        known,fp=self.fake_known()
        with patch.object(m,"PIN_SHA256",fp):
            with self.assertRaisesRegex(m.TransferHold,"UNAPPROVED_SOURCE_OR_MODE"):
                m._ssh_command(conf,known,"../../private","stream")

    def test_17_no_arbitrary_ssh_mode_accepted(self):
        conf=self.fixture_file()
        known,fp=self.fake_known()
        with patch.object(m,"PIN_SHA256",fp):
            with self.assertRaisesRegex(m.TransferHold,"UNAPPROVED_SOURCE_OR_MODE"):
                m._ssh_command(conf,known,"nov5-a","delete")

    def test_18_ssh_must_enforce_host_and_no_agent(self):
        conf=self.fixture_file()
        known,fp=self.fake_known()
        with patch.object(m,"PIN_SHA256",fp):
            with patch.object(m.shutil,"which",return_value="/usr/bin/ssh"):
                argv=m._ssh_command(conf,known,"nov5-a","probe")
        self.assertIn("StrictHostKeyChecking=yes",argv)
        self.assertIn("ForwardAgent=no",argv)
        self.assertIn("BatchMode=yes",argv)
        self.assertIn("saeit-cpanel",argv)
        self.assertNotIn("rm -",str(argv))

    def fake_probe(self):
        return {"schema":"factory.immutable.cpanel.nov5.probe.v1",
                "size":m.SOURCE_BYTES,
                "owner_regular":True,"no_sidecars":True}

    def test_19_remote_probe_succeeds_only_expected_shape(self):
        payload=json.dumps(self.fake_probe())
        with patch.object(m,"_ssh_command",return_value=[
            sys.executable,"-c","print("+repr(payload)+")"]):
            self.assertEqual(m.probe_source(Path("/not-open"),Path("/not-open"),"nov5-a"),
                             self.fake_probe())

    def test_20_remote_probe_rejects_false_owner_status(self):
        d=self.fake_probe();d["owner_regular"]=False
        with patch.object(m,"_ssh_command",return_value=[
            sys.executable,"-c","print("+repr(json.dumps(d))+")"]):
            with self.assertRaisesRegex(m.TransferHold,"CPANEL_METADATA_NOT_VERIFIED"):
                m.probe_source(Path("/not-open"),Path("/not-open"),"nov5-b")

    def test_21_remote_probe_rejects_extra_fields(self):
        d=self.fake_probe();d["password"]="NEVER_EXPOSE"
        with patch.object(m,"_ssh_command",return_value=[
            sys.executable,"-c","print("+repr(json.dumps(d))+")"]):
            with self.assertRaisesRegex(m.TransferHold,"CPANEL_METADATA_NOT_VERIFIED") as cm:
                m.probe_source(Path("/not-open"),Path("/not-open"),"nov5-a")
            self.assertNotIn("NEVER_EXPOSE",str(cm.exception))

    def test_22_remote_probe_failed_exit_no_stderr_exposure(self):
        with patch.object(m,"_ssh_command",return_value=[
            sys.executable,"-c",
            "import sys;sys.stderr.write('PRIVATE_KEY');sys.exit(6)"]):
            with self.assertRaisesRegex(m.TransferHold,"CPANEL_METADATA_PROBE_FAILED") as cm:
                m.probe_source(Path("/not-open"),Path("/not-open"),"nov5-a")
            self.assertNotIn("PRIVATE_KEY",str(cm.exception))

    def test_23_remote_probe_abnormal_oversized_output_denied(self):
        with patch.object(m,"_ssh_command",return_value=[
            sys.executable,"-c","print('A'*1000)"]):
            with self.assertRaisesRegex(m.TransferHold,"CPANEL_METADATA_PROBE_FAILED"):
                m.probe_source(Path("/not-open"),Path("/not-open"),"nov5-a")

    def test_24_immutable_stream_real_child_success_small_fixture(self):
        blob=b"SQLite format 3\x00"+b"A"*34567
        with patch.object(m,"SOURCE_BYTES",len(blob)):
            with patch.dict(m.SOURCES,{"nov5-a":("fixture.sqlite3",hashlib.sha256(blob).hexdigest())}):
                with patch.object(m,"_ssh_command",return_value=[
                        sys.executable,"-c","import sys;sys.stdout.buffer.write("+repr(blob)+")"]):
                    with m.VerifiedCpanelStream(Path("/na"),Path("/na"),"nov5-a") as src:
                        out=b""
                        while True:
                            piece=src.read(8192)
                            if not piece:break
                            out+=piece
                        self.assertEqual(out,blob)
                        self.assertTrue(src.verified)
                        self.assertEqual(src.n,len(blob))

    def test_25_immutable_stream_partial_remote_detected(self):
        blob=b"SQLite format 3\x00"+b"A"*2000
        with patch.object(m,"SOURCE_BYTES",len(blob)+100):
            with patch.dict(m.SOURCES,{"nov5-a":("fixture.sqlite3",hashlib.sha256(blob).hexdigest())}):
                with patch.object(m,"_ssh_command",return_value=[
                    sys.executable,"-c","import sys;sys.stdout.buffer.write("+repr(blob)+")"]):
                    with m.VerifiedCpanelStream(Path("/na"),Path("/na"),"nov5-a") as src:
                        self.assertEqual(src.read(4096),blob)
                        with self.assertRaisesRegex(m.TransferHold,
                                          "CPANEL_SNAPSHOT_INTEGRITY_OR_SOURCE_CHANGED"):
                            src.read(4096)
                        self.assertFalse(src.verified)

    def test_26_immutable_stream_same_length_tamper_detected(self):
        blob=b"SQLite format 3\x00"+b"A"*2000
        other=blob[:-1]+b"B"
        with patch.object(m,"SOURCE_BYTES",len(blob)):
            with patch.dict(m.SOURCES,{"nov5-a":("fixture.sqlite3",hashlib.sha256(blob).hexdigest())}):
                with patch.object(m,"_ssh_command",return_value=[
                    sys.executable,"-c","import sys;sys.stdout.buffer.write("+repr(other)+")"]):
                    with m.VerifiedCpanelStream(Path("/na"),Path("/na"),"nov5-a") as src:
                        src.read(4096)
                        with self.assertRaisesRegex(m.TransferHold,
                                          "CPANEL_SNAPSHOT_INTEGRITY_OR_SOURCE_CHANGED"):
                            src.read(4096)

    def test_27_immutable_stream_nonzero_child_exit_denied(self):
        blob=b"SAFE"
        with patch.object(m,"SOURCE_BYTES",len(blob)):
            with patch.dict(m.SOURCES,{"nov5-a":("fixture",hashlib.sha256(blob).hexdigest())}):
                with patch.object(m,"_ssh_command",return_value=[
                    sys.executable,"-c","import sys;sys.stdout.buffer.write(b'SAFE');sys.exit(7)"]):
                    with m.VerifiedCpanelStream(Path("/na"),Path("/na"),"nov5-a") as src:
                        src.read(4096)
                        with self.assertRaisesRegex(m.TransferHold,
                                          "CPANEL_SNAPSHOT_INTEGRITY_OR_SOURCE_CHANGED"):
                            src.read(4096)

    def test_28_source_read_bounds_enforced(self):
        with patch.object(m,"_ssh_command",return_value=[sys.executable,"-c","pass"]):
            with m.VerifiedCpanelStream(Path("/na"),Path("/na"),"nov5-a") as src:
                for n in (0,-1,True,m.CHUNK_BYTES+1):
                    with self.assertRaisesRegex(m.TransferHold,"UNBOUNDED_SOURCE_READ_DENIED"):
                        src.read(n)

    def test_29_factory_runner_is_mandatory(self):
        args=SimpleNamespace(mode="probe",snapshot="nov5-a",
                             ssh_config="/na",known_hosts="/na")
        with patch.object(m.os,"geteuid",return_value=0):
            with self.assertRaisesRegex(m.TransferHold,"NONROOT_OWNER_TRANSFER_RUNNER_REQUIRED"):
                m.run_export(args)

    def test_30_probe_no_remote_source_contents_or_cloud_write(self):
        args=SimpleNamespace(mode="probe",snapshot="nov5-a",
                             ssh_config="/na",known_hosts="/na")
        with patch.object(m.os,"geteuid",return_value=1001):
            with patch.object(m,"probe_source",return_value=self.fake_probe()):
                with patch.object(m,"RcloneDualStore",side_effect=AssertionError("CLOUD_MUST_NOT_START")):
                    result=m.run_export(args)
        self.assertTrue(result["source_metadata_verified"])
        self.assertFalse(result["backup_uploaded"])
        self.assertFalse(result["source_deleted"])
        self.assertFalse(result["factory_started"])

    def test_31_provider_oauth_missing_aborts_before_source_stream(self):
        args=SimpleNamespace(mode="transfer",snapshot="nov5-a",
                ssh_config="/na",known_hosts="/na",public_pem="/na",
                rclone_config="/na",rclone_exe="/usr/bin/rclone",
                trusted_public_spki_sha256="a"*64)
        class Blocked:
            def __init__(self,*a,**kw): pass
            def preflight(self): raise m.TransferHold("OWNER_DRIVE_REMOTE_CONFIG_UNVERIFIED")
        with patch.object(m.os,"geteuid",return_value=1001):
            with patch.object(m,"probe_source",return_value=self.fake_probe()):
                with patch.object(m,"_secure_file",return_value=b"PUBLIC_KEY"):
                    with patch.object(m,"RcloneDualStore",Blocked):
                        with patch.object(m,"VerifiedCpanelStream",side_effect=AssertionError("SOURCE_MUST_NOT_OPEN")):
                            with self.assertRaisesRegex(m.TransferHold,"OWNER_DRIVE_REMOTE_CONFIG_UNVERIFIED"):
                                m.run_export(args)

    def test_32_cli_transfer_rejects_absent_encryption(self):
        with self.assertRaisesRegex(m.TransferHold,"MISSING_ENCRYPTION_OR_OWNER_PROVIDER_PREREQUISITES"):
            m.main(["--mode","transfer","--snapshot","nov5-a",
                    "--ssh-config","/na","--known-hosts","/na"])

    def test_33_cli_probe_has_no_cloud_requirements(self):
        with patch.object(m,"run_export",return_value={"backup_uploaded":False}) as f:
            v=m.main(["--mode","probe","--snapshot","nov5-b",
                "--ssh-config","/na","--known-hosts","/na"])
        self.assertFalse(v["backup_uploaded"])
        self.assertEqual(f.call_args.args[0].mode,"probe")

    def test_34_cli_rejects_unknown_backup(self):
        with self.assertRaises(SystemExit):
            m.main(["--mode","probe","--snapshot","other-file",
                    "--ssh-config","/na","--known-hosts","/na"])

    def test_35_probe_a_and_b_are_independent_names(self):
        self.assertNotEqual(m.SOURCES["nov5-a"][0],m.SOURCES["nov5-b"][0])
        self.assertNotEqual(m.SOURCES["nov5-a"][1],m.SOURCES["nov5-b"][1])


    def make_transport_shell(self):
        from scripts import factory_rclone_dual_parts as adapter
        o=object.__new__(adapter.RcloneDualStore)
        o._admission=object()
        o.remote_a="factory_a"
        o.remote_b="factory_b"
        o._callbacks_claimed=False
        calls=[]
        o._direct_child_names=lambda remote,directory: calls.append(("list",remote,directory)) or set()
        o._run=lambda *cmd,**kwargs: calls.append(("run",)+cmd) or b""
        return o,calls

    def test_36_historical_destination_exact_private_folders(self):
        store,calls=self.make_transport_shell()
        callbacks=store.callbacks("factory-historical-"+"a"*32,destination_kind="historical-nov5")
        self.assertEqual(len(callbacks),4)
        self.assertEqual(sum(x[0]=="list" for x in calls),4)
        self.assertTrue(all(
            ("historical-nov5-snapshots" in str(x)) for x in calls))
        self.assertFalse(any("current-backups" in str(x) for x in calls))

    def test_37_legacy_current_mode_is_not_altered(self):
        store,calls=self.make_transport_shell()
        self.assertEqual(len(store.callbacks("factory-current-"+"b"*32)),4)
        self.assertTrue(any("current-backups" in str(x) for x in calls))
        self.assertFalse(any("historical-nov5-snapshots" in str(x) for x in calls))

    def test_38_historical_mode_disallows_current_prefix(self):
        store,_=self.make_transport_shell()
        with self.assertRaisesRegex(m.TransferHold,"UNSAFE_RUN_PREFIX"):
            store.callbacks("factory-current-"+"c"*32,destination_kind="historical-nov5")

    def test_39_unknown_destination_kind_never_accepted(self):
        store,_=self.make_transport_shell()
        with self.assertRaisesRegex(m.TransferHold,"UNAPPROVED_BACKUP_AGE_OR_DESTINATION"):
            store.callbacks("factory-historical-"+"d"*32,destination_kind="arbitrary")

    def test_40_existing_remote_namespace_never_overwritten(self):
        store,calls=self.make_transport_shell()
        store._direct_child_names=lambda remote,folder: {"factory-historical-"+"e"*32}
        with self.assertRaisesRegex(m.TransferHold,"BACKUP_RUN_NAMESPACE_ALREADY_EXISTS"):
            store.callbacks("factory-historical-"+"e"*32,destination_kind="historical-nov5")
        self.assertFalse(any(x[0]=="run" for x in calls))

    def test_41_source_remote_script_never_starts_factory(self):
        for forbidden in ("systemctl start","crontab","subprocess.Popen","DELETE FROM",
                          "DROP TABLE","os.remove(","shutil.rmtree","tarfile.extract"):
            self.assertNotIn(forbidden,m.REMOTE_PY)

    def test_42_true_crypto_core_glue_still_cannot_delete_source(self):
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        key=rsa.generate_private_key(public_exponent=65537,key_size=3072,
                                     backend=default_backend())
        pub=key.public_key().public_bytes(
            serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        der=key.public_key().public_bytes(
            serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
        fp=hashlib.sha256(der).hexdigest()
        blob=(b"SQLite format 3\x00"+b"A"*12000)
        stored={"a":{},"b":{}}
        calls=[]
        class MemoryRemote:
            def __init__(self,*a,**kw): pass
            def preflight(self): return SimpleNamespace(free_a_before=10000000)
            def callbacks(self,namespace,*,destination_kind):
                calls.append((namespace,destination_kind))
                def up(k,n,p): stored[k][n]=p
                return (lambda n,p:up("a",n,p),lambda n,p:up("b",n,p),
                        lambda n:stored["a"][n],lambda n:stored["b"][n])
        class FakeRead:
            def __init__(self,*a,**kw):
                self.payload=blob;self.pos=0;self.n=0;self.verified=False
            def __enter__(self):return self
            def read(self,n):
                if self.pos>=len(self.payload):
                    self.verified=True;return b""
                chunk=self.payload[self.pos:self.pos+n]
                self.pos+=len(chunk);self.n+=len(chunk);return chunk
            def __exit__(self,*a):return False
        args=SimpleNamespace(mode="transfer",snapshot="nov5-a",
                ssh_config="/na",known_hosts="/na",public_pem="/na",
                rclone_config="/na",rclone_exe="/usr/bin/rclone",
                trusted_public_spki_sha256=fp)
        with patch.object(m,"SOURCE_BYTES",len(blob)),patch.object(m,"CHUNK_BYTES",4096):
            with patch.object(m.os,"geteuid",return_value=1001):
                with patch.object(m,"probe_source",return_value=self.fake_probe()):
                    with patch.object(m,"_secure_file",return_value=pub):
                        with patch.object(m,"RcloneDualStore",MemoryRemote):
                            with patch.object(m,"VerifiedCpanelStream",FakeRead):
                                result=m.run_export(args)
        self.assertTrue(result["backup_uploaded"])
        self.assertTrue(result["source_sha256_verified"])
        self.assertFalse(result["source_deleted"])
        self.assertFalse(result["safe_to_delete"])
        self.assertFalse(result["new_current_factory_backup_created"])
        self.assertEqual(result["source_bytes"],len(blob))
        self.assertEqual(len(stored["a"]),len(stored["b"]))
        self.assertTrue(all(stored["a"][name]==stored["b"][name] for name in stored["a"]))
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][1],"historical-nov5")
        self.assertTrue(calls[0][0].startswith("factory-historical-"))


    def _ephemeral_args(self, binary=None):
        return SimpleNamespace(mode="transfer",snapshot="nov5-b",
                ssh_config="/PRIVATE/ssh-config",known_hosts="/PRIVATE/known",
                public_pem="/PRIVATE/recovery-public",
                rclone_config="/PRIVATE/rclone.conf",rclone_exe=binary,
                trusted_public_spki_sha256="a"*64)

    def test_43_ephemeral_never_downloads_without_private_oauth_config(self):
        args=self._ephemeral_args()
        with patch.object(m.os,"geteuid",return_value=1001), \
             patch.object(m,"probe_source",return_value=self.fake_probe()), \
             patch.object(m,"_secure_file",return_value=b"owner-public-key"), \
             patch.object(m,"_mode_secure_file",return_value=False), \
             patch.object(m,"provision_verified_rclone",side_effect=AssertionError("NO_BINARY_DOWNLOAD")):
            with self.assertRaisesRegex(m.TransferHold,"OWNER_RCLONE_OAUTH_CONFIG_NOT_PRESENT"):
                m.run_export(args)

    def test_44_ephemeral_rejects_unverified_local_temp_before_download(self):
        args=self._ephemeral_args()
        with patch.object(m.os,"geteuid",return_value=1001), \
             patch.object(m,"probe_source",return_value=self.fake_probe()), \
             patch.object(m,"_secure_file",return_value=b"owner-public-key"), \
             patch.object(m,"_mode_secure_file",return_value=True), \
             patch.dict(m.os.environ,{"RUNNER_TEMP":"relative"},clear=True), \
             patch.object(m,"provision_verified_rclone",side_effect=AssertionError("NO_BINARY_DOWNLOAD")):
            with self.assertRaisesRegex(m.TransferHold,"OWNER_RUNNER_TEMP_UNAVAILABLE"):
                m.run_export(args)

    def test_45_verified_ephemeral_client_passed_to_transport_before_source(self):
        from contextlib import nullcontext
        args=self._ephemeral_args()
        seen=[]
        class FakeTransport:
            def __init__(self,*a,**kw):
                seen.append(kw["rclone_exe"])
            def preflight(self):
                raise m.TransferHold("NO_PROVIDER_OAUTH")
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m.os,"geteuid",return_value=1001), \
             patch.object(m,"probe_source",return_value=self.fake_probe()), \
             patch.object(m,"_secure_file",return_value=b"owner-public-key"), \
             patch.object(m,"_mode_secure_file",return_value=True), \
             patch.dict(m.os.environ,{"RUNNER_TEMP":tmp}), \
             patch.object(m,"provision_verified_rclone",return_value=nullcontext("/signed-temp/rclone")) as binary, \
             patch.object(m,"RcloneDualStore",FakeTransport), \
             patch.object(m,"VerifiedCpanelStream",side_effect=AssertionError("NO_SOURCE_READ_BEFORE_OAUTH")):
            with self.assertRaisesRegex(m.TransferHold,"NO_PROVIDER_OAUTH"):
                m.run_export(args)
        self.assertEqual(seen,["/signed-temp/rclone"])
        binary.assert_called_once_with(Path(tmp))

    def test_46_explicit_owner_binary_does_not_download_client(self):
        args=self._ephemeral_args(binary="/verified-local/rclone")
        seen=[]
        class FakeTransport:
            def __init__(self,*a,**kw):seen.append(kw["rclone_exe"])
            def preflight(self):raise m.TransferHold("PROVIDER_GATE")
        with patch.object(m.os,"geteuid",return_value=1001), \
             patch.object(m,"probe_source",return_value=self.fake_probe()), \
             patch.object(m,"_secure_file",return_value=b"owner-public-key"), \
             patch.object(m,"provision_verified_rclone",side_effect=AssertionError("EXPLICIT_BINARY_MUST_NOT_DOWNLOAD")), \
             patch.object(m,"RcloneDualStore",FakeTransport), \
             patch.object(m,"VerifiedCpanelStream",side_effect=AssertionError("NO_SOURCE_READ")):
            with self.assertRaisesRegex(m.TransferHold,"PROVIDER_GATE"):
                m.run_export(args)
        self.assertEqual(seen,["/verified-local/rclone"])


    def test_47_nonresponsive_cpanel_ssh_source_fails_closed_without_hanging(self):
        # The source process deliberately emits no bytes. select() reports no
        # activity; the code raises instead of hanging on .read(8 MiB).
        with patch.object(m,"_ssh_command",return_value=[
                sys.executable,"-c","import time;time.sleep(10)"]):
            with m.VerifiedCpanelStream(Path("/na"),Path("/na"),"nov5-a") as source:
                with patch.object(m.select,"select",return_value=([],[],[])):
                    with self.assertRaisesRegex(
                            m.TransferHold,"CPANEL_SOURCE_READ_IDLE_TIMEOUT"):
                        source.read(4096)
                self.assertFalse(source.verified)


if __name__=="__main__":
    unittest.main()


class FactoryHistoricalGzipTransitionTests(unittest.TestCase):
    """Exercise the actual remote producer on private local fixtures, never cPanel."""
    def run_fixture(self, kind, mode="stream"):
        import gzip
        import pwd
        import subprocess
        import sqlite3
        from pathlib import Path
        import tempfile
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            root=home/"restore-staging"/"factory"
            root.mkdir(parents=True, mode=0o700)
            name=m.SOURCES["nov5-a"][0]
            raw_path=root/name
            with sqlite3.connect(raw_path) as c:
                c.execute("CREATE TABLE fixture (value BLOB)")
                c.execute("INSERT INTO fixture VALUES (?)",(b"X"*3000000,))
            raw=raw_path.read_bytes()
            packed=gzip.compress(raw,mtime=0)
            zipped=raw_path.with_name(name+".gz")
            if kind!="raw":
                raw_path.unlink()
                disk=packed
                if kind=="corrupt": disk=packed[:-8]+bytes([packed[-8]^1])+packed[-7:]
                elif kind=="trailing": disk=packed+b"junk"
                elif kind=="truncated": disk=packed[:-8]
                elif kind=="other_gzip": disk=gzip.compress(raw[:-1]+bytes([raw[-1]^1]),mtime=0)
                zipped.write_bytes(disk)
                zipped.chmod(0o600)
            if kind=="unsafe_raw":
                raw_path.symlink_to(zipped)
            if kind=="world_readable":zipped.chmod(0o644)
            if kind=="sidecar":(root/(name+"-wal")).touch()
            if kind=="linked":
                os.link(zipped,root/"duplicate")
            src=m.REMOTE_PY.replace("/home/zomorod2",str(home)).replace(
                '!="zomorod2"', "!=" + repr(pwd.getpwuid(os.geteuid()).pw_name))
            src=src.replace("1408634880",str(len(raw))).replace(
                m.SOURCES["nov5-a"][1],hashlib.sha256(raw).hexdigest())
            src=src.replace("279659980",str(len(packed))).replace(
                "591a0b10b2f782cb7cb8db3fa340f4b3827b8d1db2960ca89a507098ccc35c78",
                hashlib.sha256(packed).hexdigest())
            proc=subprocess.run([sys.executable,"-B","-c",src,name,mode],
                                capture_output=True,timeout=15)
            return proc,raw

    def test_gzip_only_stream_exact_original(self):
        p,raw=self.run_fixture("gzip")
        self.assertEqual(p.returncode,0,p.stderr.decode(errors="replace"))
        self.assertEqual(p.stdout,raw)

    def test_gzip_only_probe_logical_size(self):
        p,raw=self.run_fixture("gzip","probe")
        self.assertEqual(p.returncode,0)
        self.assertEqual(json.loads(p.stdout)["size"],len(raw))

    def test_raw_legacy_stream_unchanged(self):
        p,raw=self.run_fixture("raw")
        self.assertEqual(p.returncode,0)
        self.assertEqual(p.stdout,raw)

    def test_invalid_gzip_or_unsafe_metadata_never_success(self):
        for kind in ("corrupt","trailing","truncated","other_gzip","unsafe_raw",
                     "world_readable","sidecar","linked"):
            with self.subTest(kind=kind):
                p,_=self.run_fixture(kind)
                self.assertNotEqual(p.returncode,0)
