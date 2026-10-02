import unittest, tempfile, hashlib
from pathlib import Path
from unittest.mock import patch
from core.moj_1ro import executive_runtime as ex
from core.moj_1ro import self_improvement as si
from core.moj_1ro.operational_law import current, automatic_allowed, priority
from core.moj_1ro.constitution import Constitution
from core.moj_1ro.foundation_runtime import connect

def source(block):
    return 'def _format_capability_result(capability, result):\n'+block

class OperationalConstitutionTests(unittest.TestCase):
    def test_law_is_versioned_and_hash_verified(self):
        self.assertEqual(current()['version'],2)
        self.assertEqual(len(current()['sha256']),64)
        self.assertEqual(Constitution().operational_mission()['identity'],'moj_1ro_1')
    def test_primary_duty_is_real_goal(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=connect(Path(tmp)/'runtime.sqlite3')
            ex.schema(c)
            self.assertIn('self_improvement',ex.portfolio(c)['domains'])
            c.close()
        self.assertGreater(priority('self_improvement'),priority('business'))
    def test_automatic_arbitrary_patch_remains_rejected(self):
        self.assertFalse(automatic_allowed('site','apply_patch',{}))
        self.assertFalse(automatic_allowed('self_improvement','repair',{'recipe':'unknown'}))
        self.assertFalse(automatic_allowed('self_improvement','repair',{'recipe':si.RECIPE,'changes':[]}))
    def test_only_known_recipe_can_be_queued_automatically(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=connect(Path(tmp)/'runtime.sqlite3')
            r=ex.submit('self_improvement','repair',{'recipe':si.RECIPE},automatic=True,connection=c)
            self.assertEqual(r['state'],'ready')
            self.assertFalse(r['executed'])
            c.close()
    def test_protected_actions_preserved(self):
        self.assertTrue(Constitution().needs_owner_approval('real_account_trade'))
        self.assertTrue(Constitution().needs_owner_approval('fund_transfer'))
    def test_existing_false_clean_report_reproduced_and_repaired(self):
        old=source(si.OLD)
        self.assertFalse(si.verified(old))
        fixed=si.candidate(old)
        self.assertTrue(si.verified(fixed))
        self.assertIsNone(si.candidate(fixed))
    def test_unknown_code_preimage_cannot_be_rewritten(self):
        with self.assertRaises(ValueError):
            si.candidate('def _format_capability_result(capability,result):\n    return "unknown"\n')
    def test_law_preserves_repository_and_content_boundaries(self):
        b=current()['boundaries']
        self.assertEqual(b['games_repository'],'Bazei')
        self.assertTrue(b['blog_news_paused'])
        self.assertTrue(b['preserve_existing_project'])
    def test_recipe_cannot_accept_arbitrary_payload(self):
        with self.assertRaises(PermissionError):
            si.repair({'recipe':si.RECIPE,'content':'unbounded'})
    def test_repair_uses_fixed_target_preimage_and_verifies_after(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/si.TARGET;target.parent.mkdir(parents=True)
            original=source(si.OLD);target.write_text(original)
            def deploy(robot,payload):
                change=payload['changes'][0]
                self.assertEqual(change['path'],si.TARGET)
                self.assertEqual(change['expected_sha256'],hashlib.sha256(target.read_bytes()).hexdigest())
                target.write_text(change['content'])
                return {'ok':True}
            with patch.object(si,'ROOT',root),patch('core.moj_1ro.orchestrator.Moj1roOrchestrator'),patch('core.moj_1ro.host_cycle_dispatch.execute',side_effect=deploy):
                result=si.repair({'recipe':si.RECIPE})
            self.assertEqual(result['state'],'applied')
            self.assertTrue(si.verified(target.read_text()))
    def test_post_deployment_behavior_failure_restores_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/si.TARGET;target.parent.mkdir(parents=True)
            original=source(si.OLD);target.write_text(original);calls=[]
            def deploy(robot,payload):
                calls.append(payload)
                target.write_text('broken' if len(calls)==1 else payload['changes'][0]['content'])
                return {'ok':True}
            with patch.object(si,'ROOT',root),patch('core.moj_1ro.orchestrator.Moj1roOrchestrator'),patch('core.moj_1ro.host_cycle_dispatch.execute',side_effect=deploy):
                with self.assertRaises(ValueError):si.repair({'recipe':si.RECIPE})
            self.assertEqual(target.read_text(),original)
            self.assertEqual(len(calls),2)
