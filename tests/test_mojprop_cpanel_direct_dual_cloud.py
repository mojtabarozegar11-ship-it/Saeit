"""No-network, no-database tests for cPanel -> two owner-Drive stream adapter.

Real cryptographic, independent in-memory remote readback is already covered
by test_factory_rclone_dual_parts; these cases test SOURCE trust and safety
of the new integration rather than repeat the encryption core.
"""
import base64
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import mojprop_cpanel_direct_dual_cloud as bridge

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / bridge.SOURCE_FILE
KNOWN = {
    "host": "[178.239.147.125]:1396 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIE9vaKJLZ+5IhpcoTWOpsR9jauZVBqxOUpBHXS7Rh/Ia",
    "vps": "178.239.147.150 ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDJgT6PLND+DAA2JFptwG3gddczxCq19hWDragqn9oOZl1T6JpUTTptwKtAxALH6onbD/NIt1Kqg7QhJp5RHFek06mDPps5vO5okRf0q6uq7iGLJCd4zJHCIq1vmppLm1I1KmKvkmuG9VXxv07siYAUNlaZChhTXju9EzpmP6mAwkkiF76Q4/GCay545j7P4FmMezY7nqMAKvSgvU47/zA7w43WxtGjfmneAI0GBydwy22931IYkfjRr3dtDrfreJqhFQMdHDN7TOqlCFf0/F8Ri7VGOKLhwoZd1rTnK6MJcdSlNeXfNFOxaEw3Vt0MBSi4y9ahnjvRCsaUbDfUKbaGOhtepT/V/jrLsGOsrfgWaKoPaaq5TeP86FxH3oxB40QqHBUiIzPdvDqS3sirBLT0TsQ4/502IhymU/FX7dAMVyD+xYHGDKXeuqNH1wp+KJULvatTzOi41P28YDtZKsgRLKI7SY+AIYf+KCTTbYkt960bftKrSRmBWXl7XO/nzHU=",
}


class DirectCPanelDualDriveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = Path(self.tmp.name)
        self.config = p / "pinned_ssh.config"
        self.cpanel_known = p / "host.known"
        self.vps_known = p / "vps.known"
        self.cpanel_known.write_text(KNOWN["host"] + "\n")
        self.vps_known.write_text(KNOWN["vps"] + "\n")
        self.cpanel_private = p / "cpanel.key"
        self.vps_private = p / "vps.key"
        for key in (self.cpanel_private, self.vps_private):
            key.write_bytes(b"owner-secret-key-shape-only-" + b"x" * 128)
            key.chmod(0o600)
        self.conf = (
            "Host saeit-vps\n"
            "  HostName 178.239.147.150\n"
            "  User githubops\n"
            "  Port 22\n"
            "  IdentityFile " + str(p / "vps.key") + "\n"
            "  UserKnownHostsFile " + str(self.vps_known) + "\n"
            "Host saeit-cpanel\n"
            "  HostName 178.239.147.125\n"
            "  User zomorod2\n"
            "  Port 1396\n"
            "  ProxyJump saeit-vps\n"
            "  IdentityFile " + str(p / "cpanel.key") + "\n"
            "  UserKnownHostsFile " + str(self.cpanel_known) + "\n"
            "Host *\n"
            "  StrictHostKeyChecking yes\n"
            "  IdentitiesOnly yes\n"
            "  BatchMode yes\n"
            "  ForwardAgent no\n"
        )
        self.config.write_text(self.conf)
        self.config.chmod(0o600)
        self.goodhost = patch.object(bridge, "_verify_pinned_host_key", return_value=None)
        self.goodhost.start()
        self.addCleanup(self.goodhost.stop)

    def _modify(self, text):
        self.config.write_text(text)
        self.config.chmod(0o600)

    def test_01_actual_repo_source_sha_matches_reviewed_git_blob(self):
        self.assertEqual(bridge._git_blob(SOURCE.read_bytes()),
                         bridge.REVIEWED_SOURCE_BLOB)
        self.assertLess(len(bridge._source_bytes(SOURCE)), 65536)

    def test_02_ssh_config_and_two_host_aliases_are_present(self):
        allowed = bridge.admission("mysql", source_path=SOURCE,
                                   ssh_config=self.config)
        self.assertTrue(allowed.source_blob_verified)
        self.assertTrue(allowed.pinned_ssh_config_owner_only)
        self.assertFalse(allowed.complete_current_backup_verified)

    def test_03_reject_modified_exporter_even_if_regular_file(self):
        other = Path(self.tmp.name) / "backup_script.py"
        other.write_bytes(SOURCE.read_bytes() + b"\n# modification\n")
        with self.assertRaisesRegex(bridge.BackupHold, "UNAPPROVED_CPANEL_EXPORTER_CHANGE"):
            bridge._source_bytes(other)

    def test_04_reject_symlinked_exporter(self):
        other = Path(self.tmp.name) / "linked.py"
        other.symlink_to(SOURCE)
        with self.assertRaisesRegex(bridge.BackupHold, "UNSAFE_SOURCE_PATH"):
            bridge._source_bytes(other)

    def test_05_reject_wrong_backup_scope(self):
        with self.assertRaisesRegex(bridge.BackupHold, "UNKNOWN_BACKUP_SCOPE"):
            bridge.admission("all-databases", source_path=SOURCE,
                             ssh_config=self.config)

    def test_06_ssh_config_must_be_private_and_owner_only(self):
        self.config.chmod(0o644)
        with self.assertRaisesRegex(bridge.BackupHold, "UNSAFE_OWNER_FILE"):
            bridge.admission("mysql", source_path=SOURCE,
                             ssh_config=self.config)

    def test_07_ssh_config_symlink_is_rejected(self):
        target = self.config.with_suffix(".real")
        self.config.rename(target)
        self.config.symlink_to(target)
        with self.assertRaisesRegex(bridge.BackupHold, "UNSAFE_LOCAL_PATH"):
            bridge.admission("mysql", source_path=SOURCE,
                             ssh_config=self.config)

    def test_08_ssh_match_exec_is_denied_without_evaluating_it(self):
        self._modify(self.conf + "Match exec /bin/true\n")
        with self.assertRaises(bridge.BackupHold):
            bridge.admission("files", source_path=SOURCE, ssh_config=self.config)

    def test_09_ssh_proxycommand_is_denied(self):
        self._modify(self.conf + "  ProxyCommand echo unsafe\n")
        with self.assertRaisesRegex(bridge.BackupHold, "UNSAFE_SSH_CONFIG_OPTION"):
            bridge.admission("mysql", source_path=SOURCE, ssh_config=self.config)

    def test_10_ssh_different_hostname_is_denied(self):
        self._modify(self.conf.replace("HostName 178.239.147.125", "HostName example.org"))
        with self.assertRaisesRegex(bridge.BackupHold, "SSH_IDENTITY_CONTRACT_MISMATCH"):
            bridge.admission("mysql", source_path=SOURCE, ssh_config=self.config)

    def test_11_ssh_dynamic_shell_or_percent_values_denied(self):
        self._modify(self.conf.replace("HostName 178.239.147.125",
                                       "HostName $(id)"))
        with self.assertRaisesRegex(bridge.BackupHold, "DYNAMIC_SSH_CONFIG_VALUE"):
            bridge.admission("mysql", source_path=SOURCE, ssh_config=self.config)

    def test_12_ssh_port_and_batchmode_must_remain_pinned(self):
        self._modify(self.conf.replace("Port 1396", "Port 22"))
        with self.assertRaisesRegex(bridge.BackupHold, "SSH_IDENTITY_CONTRACT_MISMATCH"):
            bridge.admission("mysql", source_path=SOURCE, ssh_config=self.config)
        self._modify(self.conf.replace("BatchMode yes", "BatchMode no"))
        with self.assertRaisesRegex(bridge.BackupHold, "SSH_IDENTITY_CONTRACT_MISMATCH"):
            bridge.admission("mysql", source_path=SOURCE, ssh_config=self.config)

    def test_13_approved_command_uses_fixed_ssh_and_no_secret(self):
        with patch.object(bridge.shutil, "which", return_value="/usr/bin/ssh"):
            argv = bridge.build_producer_argv(
                "mysql", source_path=SOURCE, ssh_config=self.config)
        self.assertEqual(argv[:4], ["/usr/bin/ssh", "-T", "-F", str(self.config)])
        self.assertEqual(argv[-2], "saeit-cpanel")
        self.assertIn("StrictHostKeyChecking=yes", argv)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", argv[-1])
        self.assertIn("'mysql'", argv[-1])
        self.assertNotIn("DATABASE_URL", argv[-1])
        self.assertNotIn("MYSQL_PWD", argv[-1])
        self.assertNotIn("REFRESH_TOKEN", argv[-1])
        encoded = re.search(r"'([A-Za-z0-9+/=]{1000,})' 'mysql'$", argv[-1])
        self.assertIsNotNone(encoded)
        self.assertEqual(base64.b64decode(encoded.group(1)),
                         SOURCE.read_bytes())

    def test_14_no_runtime_auto_backup_invoked_by_metadata_cli(self):
        record = bridge.readiness()
        self.assertTrue(record["reviewed_source_blob_present"])
        self.assertFalse(record["current_backup_created"])
        self.assertFalse(record["restore_performed"])
        self.assertFalse(record["production_modified"])
        self.assertFalse(record["provider_quota_verified"])
        self.assertFalse(record["payment_created"])

    def test_15_missing_case_approval_prevents_preflight_or_source(self):
        with patch.object(bridge, "build_producer_argv",
                          side_effect=AssertionError("source was reached")):
            with self.assertRaisesRegex(bridge.BackupHold, "EXPLICIT_ONE_TIME_APPROVAL_MISSING"):
                bridge.transfer_approved_scope(
                    owner_approval="NOT_APPROVED", mode="mysql",
                    source_path=SOURCE, ssh_config=self.config,
                    verified_ssh_identity=True,
                    verified_passenger_database=True,
                    verified_complete_scope=True,
                    independently_recoverable_private_key=True,
                    store=SimpleNamespace(max_source_bytes=10000),
                    gzip_executable="/usr/bin/gzip", approved_public_pem=b"x",
                    approved_public_spki_sha256="a" * 64,
                    pseudonymous_owner_a="a", pseudonymous_owner_b="b",
                    run_subdirectory="factory-current-" + "0" * 32)

    def test_16_missing_exact_prerequisites_hold_before_any_source_read(self):
        base = dict(owner_approval=bridge.OWNER_ARM, mode="mysql",
                    source_path=SOURCE, ssh_config=self.config,
                    verified_ssh_identity=True,
                    verified_passenger_database=True,
                    verified_complete_scope=True,
                    independently_recoverable_private_key=True,
                    store=SimpleNamespace(max_source_bytes=10000),
                    gzip_executable="/usr/bin/gzip",
                    approved_public_pem=b"x",
                    approved_public_spki_sha256="a" * 64,
                    pseudonymous_owner_a="a", pseudonymous_owner_b="b",
                    run_subdirectory="factory-current-" + "a" * 32)
        with patch.object(bridge, "build_producer_argv",
                          side_effect=AssertionError("source launched")):
            for field in ("verified_ssh_identity",
                          "verified_passenger_database",
                          "verified_complete_scope",
                          "independently_recoverable_private_key"):
                with self.subTest(field=field):
                    props = dict(base)
                    props[field] = False
                    with self.assertRaisesRegex(bridge.BackupHold,
                                                "UNPROVEN_PRODUCTION_OR_RECOVERY_PREREQUISITE"):
                        bridge.transfer_approved_scope(**props)

    def test_17_duplicate_run_namespace_and_wrong_key_format_denied(self):
        with self.assertRaisesRegex(bridge.BackupHold, "UNSAFE_OR_REUSED_NAMESPACE"):
            bridge.transfer_approved_scope(
                owner_approval=bridge.OWNER_ARM, mode="mysql",
                source_path=SOURCE, ssh_config=self.config,
                verified_ssh_identity=True, verified_passenger_database=True,
                verified_complete_scope=True,
                independently_recoverable_private_key=True,
                store=SimpleNamespace(max_source_bytes=10000),
                gzip_executable="/usr/bin/gzip", approved_public_pem=b"x",
                approved_public_spki_sha256="a" * 64,
                pseudonymous_owner_a="a", pseudonymous_owner_b="b",
                run_subdirectory="../existing-backup")

    def test_18_pinned_ssh_host_key_rejects_fake_public_key(self):
        self.goodhost.stop()
        self.addCleanup(lambda: None)
        invalid_path = Path(self.tmp.name) / "wrong.known"
        invalid_path.write_text(KNOWN["host"].replace(
            "AAAAC3", "AAAAB3") + "\n")
        with self.assertRaises(bridge.BackupHold):
            bridge._verify_pinned_host_key(
                invalid_path,
                "[178.239.147.125]:1396",
                "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04",
            )

    def test_19_runtime_source_limit_is_not_automatically_raised(self):
        self.assertEqual(bridge.SOURCE_MODES, {"mysql", "files"})
        self.assertEqual(bridge.REVIEWED_SOURCE_BLOB,
                         "7b330168b4ca1d597616e8724bc634910e769ea5")
        self.assertEqual(bridge.OWNER_ARM,
                         "OWNER_APPROVES_ONE_OFFSITE_BACKUP_SET_WITHOUT_DEPLOY")



    def test_20_missing_cpanel_private_key_denied(self):
        self.cpanel_private.unlink()
        with self.assertRaisesRegex(bridge.BackupHold, "MISSING_SSH_IDENTITY_FILE"):
            bridge.admission("mysql", source_path=SOURCE, ssh_config=self.config)

    def test_21_world_readable_vps_private_key_denied(self):
        self.vps_private.chmod(0o644)
        with self.assertRaisesRegex(bridge.BackupHold, "UNSAFE_SSH_PRIVATE_KEY_PERMISSIONS"):
            bridge.admission("mysql", source_path=SOURCE, ssh_config=self.config)

    def test_22_symlinked_ssh_identity_denied(self):
        target = self.cpanel_private.with_suffix(".real")
        self.cpanel_private.rename(target)
        self.cpanel_private.symlink_to(target)
        with self.assertRaisesRegex(bridge.BackupHold, "UNSAFE_SSH_IDENTITY_PATH"):
            bridge.admission("files", source_path=SOURCE, ssh_config=self.config)

    def test_23_unknown_key_filename_in_config_denied(self):
        self._modify(self.conf.replace(
            "IdentityFile " + str(self.cpanel_private),
            "IdentityFile /tmp/unapproved-key-that-does-not-exist"))
        with self.assertRaisesRegex(bridge.BackupHold, "MISSING_SSH_IDENTITY_FILE"):
            bridge.admission("mysql", source_path=SOURCE, ssh_config=self.config)


    def _approved_params(self):
        return dict(
            owner_approval=bridge.OWNER_ARM,
            mode="mysql",
            source_path=SOURCE,
            ssh_config=self.config,
            verified_ssh_identity=True,
            verified_passenger_database=True,
            verified_complete_scope=True,
            independently_recoverable_private_key=True,
            store=SimpleNamespace(max_source_bytes=128 * 1024 * 1024),
            gzip_executable="/usr/bin/gzip",
            approved_public_pem=b"dummy-owner-public-pem",
            approved_public_spki_sha256="a" * 64,
            pseudonymous_owner_a="a" * 32,
            pseudonymous_owner_b="b" * 32,
            run_subdirectory="factory-current-" + "f" * 32,
        )

    def test_24_approved_transfer_delegates_once_to_existing_dual_encryption_core(self):
        from unittest.mock import sentinel
        params = self._approved_params()
        with patch("factory_dual_stream_v2._public_fingerprint",
                   return_value=(object(), "a" * 64)), \
             patch.object(bridge, "build_producer_argv",
                          return_value=["/usr/bin/ssh", "pinned-source"]), \
             patch("factory_rclone_dual_parts.encrypt_verified_pipe_to_two_owner_drives",
                   return_value=sentinel.encrypted_dual_store_receipt) as encrypt:
            value = bridge.transfer_approved_scope(**params)
            self.assertIs(value, sentinel.encrypted_dual_store_receipt)
            encrypt.assert_called_once()
            args = encrypt.call_args
            self.assertIs(args.args[0], params["store"])
            self.assertEqual(args.kwargs["vetted_producer_argv"],
                             ["/usr/bin/ssh", "pinned-source"])
            self.assertEqual(args.kwargs["run_subdirectory"],
                             params["run_subdirectory"])

    def test_25_mismatched_owner_public_key_denies_transfer(self):
        params = self._approved_params()
        with patch("factory_dual_stream_v2._public_fingerprint",
                   return_value=(object(), "f" * 64)), \
             patch.object(bridge, "build_producer_argv",
                          side_effect=AssertionError("must never start source")):
            with self.assertRaisesRegex(bridge.BackupHold,
                                        "WRONG_PUBLIC_RECOVERY_KEY"):
                bridge.transfer_approved_scope(**params)

    def test_26_above_original_source_stream_bound_fails_before_cloud(self):
        params = self._approved_params()
        params["store"] = SimpleNamespace(max_source_bytes=49 * 1024**3)
        with patch("factory_dual_stream_v2._public_fingerprint",
                   return_value=(object(), "a" * 64)), \
             patch.object(bridge, "build_producer_argv",
                          return_value=["ssh", "source"]), \
             patch("factory_rclone_dual_parts.encrypt_verified_pipe_to_two_owner_drives",
                   side_effect=AssertionError("must not upload")):
            with self.assertRaisesRegex(bridge.BackupHold,
                                        "SOURCE_STREAM_EXCEEDS_CPANEL_SAFETY_CAP"):
                bridge.transfer_approved_scope(**params)


    def test_27_reject_early_wildcard_precedence_attack(self):
        # Move the existing wildcard block to the front instead of creating
        # an invalid duplicate Host * block that would fail even earlier.
        self._modify(
            "Host *\n"
            "  HostName malicious.example\n"
            "  StrictHostKeyChecking yes\n"
            "  IdentitiesOnly yes\n"
            "  BatchMode yes\n"
            "  ForwardAgent no\n"
            + self.conf.split("Host *\n")[0]
        )
        with self.assertRaisesRegex(bridge.BackupHold, "SSH_IDENTITY_CONTRACT_MISMATCH"):
            bridge.admission("mysql", source_path=SOURCE, ssh_config=self.config)

    def test_28_reject_early_wildcard_weak_host_validation(self):
        self._modify(
            "Host *\n"
            "  StrictHostKeyChecking no\n"
            "  IdentitiesOnly yes\n"
            "  BatchMode yes\n"
            "  ForwardAgent no\n"
            + self.conf.split("Host *\n")[0]
        )
        with self.assertRaisesRegex(bridge.BackupHold, "SSH_IDENTITY_CONTRACT_MISMATCH"):
            bridge.admission("mysql", source_path=SOURCE, ssh_config=self.config)

    def test_29_block_nested_relay_to_unexpected_jump_host(self):
        self._modify(
            self.conf.replace("  User githubops\n",
                              "  User githubops\n  ProxyJump untrusted-relay\n")
        )
        with self.assertRaisesRegex(bridge.BackupHold, "NESTED_SSH_PROXY_OR_INTERACTIVE_TTY_DENIED"):
            bridge.admission("files", source_path=SOURCE, ssh_config=self.config)

    def test_30_block_relay_forward_agent_even_if_cpanel_disallows_it(self):
        self._modify(
            self.conf.replace("  User githubops\n",
                              "  User githubops\n  ForwardAgent yes\n")
        )
        with self.assertRaisesRegex(bridge.BackupHold, "SSH_RELAY_IDENTITY_CONTRACT_MISMATCH"):
            bridge.admission("mysql", source_path=SOURCE, ssh_config=self.config)

    def test_31_block_tty_on_relay_or_cpanel(self):
        for host in ("Host saeit-vps\n", "Host saeit-cpanel\n"):
            with self.subTest(host=host):
                self._modify(self.conf.replace(host, host + "  RequestTTY yes\n"))
                with self.assertRaisesRegex(bridge.BackupHold, "NESTED_SSH_PROXY_OR_INTERACTIVE_TTY_DENIED"):
                    bridge.admission("files", source_path=SOURCE, ssh_config=self.config)

    def test_32_block_ssh_control_master_or_path_config(self):
        for option in ("ControlMaster auto", "ControlPath /tmp/any.sock",
                       "ControlPersist 10m"):
            with self.subTest(option=option):
                self._modify(self.conf.replace(
                    "Host saeit-cpanel\n",
                    "Host saeit-cpanel\n  " + option + "\n",
                ))
                with self.assertRaisesRegex(bridge.BackupHold, "UNSAFE_SSH_CONFIG_OPTION"):
                    bridge.admission("mysql", source_path=SOURCE, ssh_config=self.config)

    def test_33_reject_omitted_relay_block_even_if_wildcard_spoofs_it(self):
        start = self.conf.index("Host saeit-vps\n")
        end = self.conf.index("Host saeit-cpanel\n")
        self._modify(self.conf[:start] + self.conf[end:])
        with self.assertRaisesRegex(bridge.BackupHold, "MISSING_EXPLICIT_SSH_HOST_BLOCK"):
            bridge.admission("mysql", source_path=SOURCE, ssh_config=self.config)

    def test_34_reject_cpanel_proxyjump_to_untrusted_host(self):
        self._modify(self.conf.replace("  ProxyJump saeit-vps", "  ProxyJump other-relay"))
        with self.assertRaisesRegex(bridge.BackupHold, "SSH_IDENTITY_CONTRACT_MISMATCH"):
            bridge.admission("mysql", source_path=SOURCE, ssh_config=self.config)

if __name__ == "__main__":
    unittest.main()
