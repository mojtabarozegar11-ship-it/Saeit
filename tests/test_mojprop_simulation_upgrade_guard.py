"""Migration-plan guard regressions: no production connection or DDL."""
from unittest import TestCase
from prop_firm.simulation_upgrade_guard import APP,BASELINE,UPGRADE,TARGET,UpgradePlanDenied,validate_upgrade_plan

class SimulationUpgradeGuardTests(TestCase):
    def setUp(self):
        self.applied={(APP,n) for n in BASELINE}|{("auth","0001_initial")}
        self.disk={(APP,n) for n in BASELINE+UPGRADE}|{("auth","0001_initial")}
        self.plan=[((APP,n),False) for n in UPGRADE]
        self.leaves=[TARGET]
    def check(self):
        return validate_upgrade_plan(self.applied,self.disk,self.plan,self.leaves)
    def test_exact_plan(self):
        self.assertEqual(self.check(),tuple((APP,n) for n in UPGRADE))
    def test_partial_upgrade_denied(self):
        self.applied.add((APP,UPGRADE[0]))
        with self.assertRaises(UpgradePlanDenied):self.check()
    def test_missing_baseline_denied(self):
        self.applied.remove((APP,BASELINE[0]))
        with self.assertRaises(UpgradePlanDenied):self.check()
    def test_unreviewed_disk_denied(self):
        self.disk.add((APP,"0018_unknown"))
        with self.assertRaises(UpgradePlanDenied):self.check()
    def test_unrelated_dependency_denied(self):
        self.plan.insert(0,(("auth","0002_unknown"),False))
        with self.assertRaises(UpgradePlanDenied):self.check()
    def test_reverse_denied(self):
        self.plan[0]=(self.plan[0][0],True)
        with self.assertRaises(UpgradePlanDenied):self.check()
    def test_reordered_plan_denied(self):
        self.plan.reverse()
        with self.assertRaises(UpgradePlanDenied):self.check()
    def test_multiple_leaves_denied(self):
        self.leaves.append((APP,"0017_other"))
        with self.assertRaises(UpgradePlanDenied):self.check()
