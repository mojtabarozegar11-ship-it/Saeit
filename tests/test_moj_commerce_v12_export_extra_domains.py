"""Synthetic source-only tests: never connect to or back up a live account."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import moj_commerce_v12_export_extra_domains as exp


class ExtraRootBackupTests(unittest.TestCase):
    def test_only_three_distinct_account_owned_public_roots(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            stage=home/'Saeit-staging'
            covered=home/'mojplaywin.com'
            others=[home/('extra-site-'+str(n)) for n in range(3)]
            for p in [stage,covered,*others]:
                p.mkdir()
            entries=[{'documentroot':str(covered)}]+[
                {'documentroot':str(p)} for p in others]
            with patch.object(exp,'HOME',home), patch.object(exp,'BACKED',(stage,covered)):
                found=exp.roots_for_backup({'result':{'status':1,'data':entries}})
            self.assertEqual(set(found),set(others))

    def test_denies_private_dot_directories_and_foreign_roots(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            stage=home/'Saeit-staging'
            covered=home/'mojplaywin.com'
            for p in (stage,covered,home/'.ssh',home/'normal1',home/'normal2'):
                p.mkdir()
            payload={'result':{'status':1,'data':[
                {'documentroot':str(covered)},
                {'documentroot':str(home/'.ssh')},
                {'documentroot':str(home/'normal1')},
                {'documentroot':str(home/'normal2')} ]}}
            with patch.object(exp,'HOME',home), patch.object(exp,'BACKED',(stage,covered)):
                with self.assertRaises(RuntimeError):
                    exp.roots_for_backup(payload)

    def test_missing_domain_api_refuses_backup(self):
        with self.assertRaises(RuntimeError):
            exp.roots_for_backup({'result':{'status':0,'data':[]}})


if __name__=='__main__':
    unittest.main()
