import argparse
import importlib.util
from pathlib import Path
from unittest import mock
import tempfile
import unittest

src = Path(__file__).resolve().parents[1] / "scripts/f01_vps_console_snapshot_readonly_20261029.py"
spec = importlib.util.spec_from_file_location("f01_snapshot", src)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class SnapshotTests(unittest.TestCase):
    def test_missing_is_not_healthy(self):
        self.assertEqual(mod.stat_path("/unlikely/nonexistent/f01/20261029")["state"], "MISSING")
    def test_symlink_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "f"
            p.write_text("x")
            q = Path(d) / "l"
            q.symlink_to(p)
            self.assertEqual(mod.stat_path(q)["state"], "SYMLINK_NOT_FOLLOWED")
    def test_linked_ancestor_is_not_followed_for_filesystem_or_queue(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "actual"
            base.mkdir()
            (base / "private").mkdir()
            link = Path(d) / "alias"
            link.symlink_to(base, target_is_directory=True)
            self.assertEqual(mod.stat_path(link / "private")["state"], "SYMLINK_NOT_FOLLOWED")
            self.assertEqual(mod.mount(link / "private")["state"], "SYMLINK_NOT_FOLLOWED")
            self.assertEqual(mod.queue(link / "private")["state"], "SYMLINK_NOT_FOLLOWED")

    def test_sqlite_only_reads_header(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "db"
            p.write_bytes(b"SQLite format 3\0" + b"x" * 40)
            self.assertTrue(mod.sqlite(p)["sqlite_header_valid"])
            self.assertEqual(mod.sqlite(p)["integrity_check"], "NOT_RUN")
    def test_sqlite_linked_parent_is_never_followed(self):
        with tempfile.TemporaryDirectory() as d:
            private = Path(d) / "private"
            private.mkdir()
            (private / "db").write_bytes(b"SQLite format 3\0" + b"x" * 40)
            alias = Path(d) / "alias"
            alias.symlink_to(private, target_is_directory=True)
            result = mod.sqlite(alias / "db")
            self.assertEqual(result["state"], "UNAVAILABLE")
            self.assertNotIn("sqlite_header_valid", result)

    def test_sqlite_fifo_is_rejected_without_blocking(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            fifo = Path(d) / "pipe"
            os.mkfifo(fifo)
            result = mod.sqlite(fifo)
            self.assertEqual(result["state"], "UNAVAILABLE")

    def test_sqlite_uses_open_descriptor_not_prior_stat_path(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "db"
            db.write_bytes(b"SQLite format 3\0" + b"x" * 40)
            with mock.patch.object(mod, "stat_path", side_effect=AssertionError("unsafe pre-open stat")):
                result = mod.sqlite(db)
            self.assertEqual(result["state"], "PRESENT")
            self.assertTrue(result["sqlite_header_valid"])
            self.assertEqual(result["bytes"], 56)

    def test_no_deployment_claim(self):
        with tempfile.TemporaryDirectory() as d:
            a = argparse.Namespace(mount=[d], queue=[d], lock=[], sqlite=[], backup=[])
            x = mod.capture(a)
            self.assertFalse(x["deployment_authorized"])
            self.assertFalse(x["worker_running_verified"])
            self.assertEqual(x["offhost_backup_restored"], "NOT_VERIFIED")
    def test_private_path_labels_are_redacted(self):
        with tempfile.TemporaryDirectory() as d:
            a = argparse.Namespace(mount=[d], queue=[d], lock=[d], sqlite=[d], backup=[d])
            x = mod.capture(a)
            self.assertTrue(x["path_labels_redacted"])
            for category in ("filesystem", "queue", "locks", "sqlite", "backup"):
                self.assertEqual(list(x[category]), ["target_1"])
                self.assertNotIn(d, str(list(x[category])))

    def test_lsblk_mountpoint_never_requested_or_emitted(self):
        calls = []
        def fake_command(argv):
            calls.append(argv)
            if argv[0] == "lsblk":
                return {"state": "OBSERVED", "output": (
                    '{"blockdevices":[{"name":"vda","size":"42",'
                    '"mountpoint":"/PRIVATE/DO_NOT_LOG",'
                    '"children":[{"name":"vda1","mountpoints":["/secret"]}]}]}')}
            return {"state": "UNAVAILABLE"}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(mod, "command", side_effect=fake_command):
            args = argparse.Namespace(mount=[d], queue=[], lock=[], sqlite=[], backup=[])
            result = mod.capture(args)
        self.assertNotIn("MOUNTPOINT", str(calls[0]))
        self.assertNotIn("/PRIVATE", str(result))
        self.assertNotIn("/secret", str(result))
        self.assertEqual(result["block_topology"]["devices"]["blockdevices"][0]["name"], "vda")

    def test_sqlite_leaf_symlink_swap_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            real = Path(d) / "private"
            real.write_bytes(b"SQLite format 3\0" + b"data")
            link = Path(d) / "db"
            link.symlink_to(real)
            # Simulate a symlink swap after metadata validation.
            with mock.patch.object(mod, "stat_path", return_value={"state":"PRESENT", "is_file":True}):
                observed = mod.sqlite(link)
            self.assertEqual(observed["state"], "UNAVAILABLE")
            self.assertFalse(observed.get("sqlite_header_valid", False))

    def test_queue_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a").write_text("a")
            self.assertEqual(mod.queue(d)["entries_at_least"], 1)
    def test_queue_uses_directory_fd_not_preopen_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a").write_text("a")
            with mock.patch.object(mod, "stat_path", side_effect=AssertionError("unsafe path stat")):
                result = mod.queue(d)
            self.assertEqual(result["state"], "OBSERVED")
            self.assertEqual(result["entries_at_least"], 1)

    def test_queue_symlinked_parent_refuses_enumeration(self):
        with tempfile.TemporaryDirectory() as d:
            private = Path(d) / "private"
            private.mkdir()
            (private / "queue").mkdir()
            alias = Path(d) / "alias"
            alias.symlink_to(private, target_is_directory=True)
            result = mod.queue(alias / "queue")
            self.assertEqual(result["state"], "SYMLINK_NOT_FOLLOWED")


    def test_proc_stat_parser_handles_parentheses_and_rejects_short_input(self):
        fields = ["S", "1"] + ["0"] * 18
        fields[11], fields[12], fields[17] = "100", "50", "7"
        parsed = mod.parse_proc_stat("42 (worker (nested) name) " + " ".join(fields))
        self.assertEqual(parsed["state"], "S")
        self.assertEqual(parsed["ppid"], 1)
        self.assertEqual(parsed["cpu_ticks"], 150)
        self.assertEqual(parsed["threads"], 7)
        with self.assertRaises(ValueError):
            mod.parse_proc_stat("42 (bad) S 1")

    def test_coarse_age_buckets_and_clock_fail_closed(self):
        self.assertEqual(mod.process_age_bucket(9950, 100.0, 100), "lt_1m")
        self.assertEqual(mod.process_age_bucket(9000, 100.0, 100), "lt_1m")
        self.assertEqual(mod.process_age_bucket(1000, 100.0, 100), "1m_to_1h")
        self.assertEqual(mod.process_age_bucket(100, 5000.0, 100), "1h_to_1d")
        self.assertEqual(mod.process_age_bucket(100, 90000.0, 100), "gte_1d")
        self.assertEqual(mod.process_age_bucket(20000, 100.0, 100), "unknown")
        self.assertEqual(mod.process_age_bucket(10, None, 100), "unknown")
        self.assertEqual(mod.process_age_bucket(10, 100.0, 0), "unknown")

    def test_orphan_age_buckets_are_aggregate_and_non_authorizing(self):
        p = mod.process_pressure()
        self.assertEqual(p["state"], "OBSERVED")
        self.assertFalse(p["worker_health_verified"])
        self.assertTrue(p["pid_command_and_paths_redacted"])
        buckets = ("lt_1m", "1m_to_1h", "1h_to_1d", "gte_1d", "unknown")
        self.assertTrue(set(p["factory_age_buckets"]).issubset(buckets))
        self.assertTrue(set(p["init_parent_factory_age_buckets"]).issubset(buckets))
        self.assertEqual(sum(p["factory_age_buckets"].values()), p["factory_name_matches"])
        self.assertLessEqual(sum(p["init_parent_factory_age_buckets"].values()), p["factory_name_matches"])

    def test_process_pressure_is_redacted_and_not_worker_health_proof(self):
        observed = mod.process_pressure()
        self.assertEqual(observed["state"], "OBSERVED")
        self.assertTrue(observed["pid_command_and_paths_redacted"])
        self.assertFalse(observed["worker_health_verified"])
        self.assertNotIn("cmdline", str(observed).lower())

    def test_parent_origin_categories_are_fixed_and_redacted(self):
        self.assertEqual(mod.classify_process_origin("cron", b"/usr/sbin/cron"), "cron")
        self.assertEqual(mod.classify_process_origin("bash", b"factory/private/run.py --secret-token=hidden"), "factory")
        self.assertEqual(mod.classify_process_origin("python3", b"python3 worker.py"), "python")
        self.assertEqual(mod.classify_process_origin("systemd", b"/usr/lib/systemd/systemd"), "systemd")
        self.assertEqual(mod.classify_process_origin("bash", b"/bin/bash"), "shell")
        self.assertEqual(mod.classify_process_origin("bash", b"master-agent internal"), "master-agent")

    def test_init_parented_fanout_is_explicit_not_misreported(self):
        p = mod.dominant_parent_origin(1)
        self.assertEqual(p["state"], "INIT_PARENT")
        self.assertTrue(p["parent_is_init"])
        self.assertEqual(p["depth_observed"], 0)
        self.assertTrue(p["pid_argv_and_paths_redacted"])

    def test_dominant_parent_lineage_contains_no_pid_or_private_argv(self):
        p = mod.dominant_parent_origin(__import__("os").getpid())
        self.assertIn(p["state"], ("OBSERVED", "PARTIAL"))
        self.assertTrue(p["pid_argv_and_paths_redacted"])
        self.assertLessEqual(p["depth_observed"], 8)
        self.assertNotIn("pid", str(p.get("lineage", [])))
        for entry in p["lineage"]:
            self.assertEqual(set(entry), {"category", "state", "threads"})
            self.assertIn(entry["category"], ("cron", "systemd", "master-agent", "factory", "python", "shell", "other"))
        q = mod.process_pressure()
        self.assertIn("dominant_parent_origin", q)
        self.assertIn("dominant_parent_child_states", q)
        self.assertFalse(q["worker_health_verified"])

    def test_cron_fanout_counts_only_no_commands(self):
        lines = [
            "* * * * * /private/factory/launch --token=secret",
            "* * * * * /private/factory/launch --token=secret",
            "*/1 * * * * /private/master-agent/runner",
            "0 * * * * /usr/bin/echo hourly",
            "@reboot /usr/bin/echo startup",
        ]
        out = mod.cron_schedule_summary(lines)
        self.assertEqual(out["per_minute_entries"], 3)
        self.assertEqual(out["factory_per_minute_entries"], 3)
        self.assertEqual(out["exact_duplicate_entries"], 1)
        self.assertEqual(out["special_entries"], 1)
        self.assertNotIn("secret", str(out))
        self.assertTrue(out["commands_and_schedules_redacted"])

    def test_missing_command(self):
        self.assertEqual(mod.command(["/no-such-f01-command"])["state"], "UNAVAILABLE")

if __name__ == "__main__":
    unittest.main()
