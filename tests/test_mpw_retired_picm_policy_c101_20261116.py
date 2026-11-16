"""Only the owner-attested E7 retirement may exclude PICM from active audits.

Real active child sites and buyer checkout paths remain independently monitored.
No network, payment, login or deployment is performed.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import mpw_subsite_continuity_guard_20261026 as continuity
from scripts import mojplaywin_public_subsite_smoke_baseline as baseline
from scripts.mpw_retired_subsite_policy import (
    MANIFEST, RETIRED_PATHS, RetirementPolicyUnavailable,
    assert_retired_picm_manifest, assert_no_retired_routes,
)


class PicmOwnerRetirementTests(unittest.TestCase):
    def _copy(self, mutator=None):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        path = Path(self._tmp.name) / "policy.json"
        data = json.loads(MANIFEST.read_text(encoding="utf8"))
        if mutator is not None:
            mutator(data)
        path.write_text(json.dumps(data), encoding="utf8")
        return path

    def test_exact_owner_retirement_exists_in_repository(self):
        assert_retired_picm_manifest()
        self.assertEqual(RETIRED_PATHS, frozenset(("/picm/", "/picm/login/")))

    def test_active_five_stay_required(self):
        self.assertEqual(
            set(continuity.PROTECTED_CHILDREN),
            {"/farnaz/", "/saman/", "/taniya/", "/studio.Roham/", "/zahra$$/"}
        )
        self.assertTrue(set(continuity.PROTECTED_CHILDREN).issubset(
            set(continuity.REQUIRED_PATHS)
        ))
        self.assertEqual(len(continuity.PERSONAL_PATHS), 11)
        assert_no_retired_routes(continuity.REQUIRED_PATHS)
        assert_no_retired_routes(continuity.REDIRECT_PATHS)
        assert_no_retired_routes(baseline.PUBLIC_PATHS)

    def test_retired_picm_cannot_be_requested_directly(self):
        for path in RETIRED_PATHS:
            with self.subTest(path=path):
                with patch.object(continuity.urllib.request, "build_opener") as opened:
                    with self.assertRaises(continuity.UnsafeRedirect):
                        continuity.get(continuity.ORIGIN + path, attempts=1)
                    opened.assert_not_called()
        for path in RETIRED_PATHS:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    baseline.probe(path, opener_factory=lambda handler: self.fail(
                        "Retired PICM should never make a GET"
                    ))

    def test_manifest_absence_or_symlink_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            missing = root / "missing.json"
            with self.assertRaises(RetirementPolicyUnavailable):
                assert_retired_picm_manifest(missing)
            linked = root / "linked.json"
            linked.symlink_to(MANIFEST)
            with self.assertRaises(RetirementPolicyUnavailable):
                assert_retired_picm_manifest(linked)

    def test_owner_reactivation_or_deployment_needs_new_explicit_policy(self):
        for mut in (
            lambda d: d.update(status="active"),
            lambda d: d.update(policy="active_queue"),
            lambda d: d["execution_policy"].update(reactivate=True),
            lambda d: d["execution_policy"].update(deploy=True),
            lambda d: d["execution_policy"].update(rebuild=True),
            lambda d: d["execution_policy"].update(
                delete_source_without_explicit_scope=True
            ),
            lambda d: d.update(name="OtherApp"),
            lambda d: d.update(version="1"),
        ):
            with self.subTest(mutation=mut):
                with self.assertRaises(RetirementPolicyUnavailable):
                    assert_retired_picm_manifest(self._copy(mut))

    def test_retired_policy_tamper_cannot_inflate_continuity_result(self):
        bad = self._copy(lambda d: d.update(status="active"))
        with patch("scripts.mpw_retired_subsite_policy.MANIFEST", bad):
            # Runtime uses default MANIFEST loaded when function was defined;
            # direct path remains explicit and must reject tampering.
            with self.assertRaises(RetirementPolicyUnavailable):
                assert_retired_picm_manifest(bad)
        assert_no_retired_routes(continuity.REQUIRED_PATHS)
        with self.assertRaises(RetirementPolicyUnavailable):
            assert_no_retired_routes(continuity.REQUIRED_PATHS + ("/picm/",))

    def test_anonymous_public_smoke_explicitly_denies_release(self):
        fake = lambda p: {"path": p, "status": 200}
        report = baseline.report(fake)
        self.assertTrue(report["retired_picm_excluded_from_active_queue"])
        self.assertFalse(report["all_protected_sites_verified"])
        self.assertFalse(report["release_permitted"])
        self.assertTrue(all(x["path"] not in RETIRED_PATHS for x in report["responses"]))


if __name__ == "__main__":
    unittest.main()
