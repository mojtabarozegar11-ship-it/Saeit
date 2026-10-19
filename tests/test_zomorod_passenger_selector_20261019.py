"""Prove CloudLinux Passenger P0 release remains strictly scoped and reversible."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ZomorodPassengerSelectorTests(unittest.TestCase):
    def test_existing_selector_is_preserved_and_virtualenv_is_repaired(self):
        s = (ROOT/".github/workflows/zomorod-app-pages-deploy.yml").read_text()
        install = s.split("      - name: Install Django app files", 1)[1]
        self.assertIn("""old=f'PassengerPython "{sys.argv[2]}"'""", install)
        self.assertIn("""new='PassengerPython "/opt/alt/python310/bin/lswsgi"'""", install)
        self.assertIn('text=text.replace(old,new,1)', install)
        self.assertIn('PASSENGER_PYTHON_SELECTED=selector_lswsgi', install)
        self.assertIn('PASSENGER_PYTHON_FINAL=verified_selector_lswsgi', install)
        self.assertIn('test -x /opt/alt/python310/bin/lswsgi', install)

    def test_existing_backup_and_rollback_paths_remain(self):
        s = (ROOT/".github/workflows/zomorod-app-pages-deploy.yml").read_text()
        for marker in ('htaccess.sha256', 'rollback()', 'PUBLIC_VERIFICATION_ROLLBACK=complete',
                       'PASSENGER_ROOT_MAPPING=verified', 'zomorodmelal.ir'):
            self.assertIn(marker, s)

    def test_wsgi_wheel_paths_match_current_python_minor(self):
        s = (ROOT/"passenger_wsgi.py").read_text()
        self.assertIn('sys.version_info.major', s)
        self.assertIn('("lib", "lib64")', s)
        self.assertIn('site-packages', s)
        self.assertNotIn('site.addsitedir(', s)
        compile(s, "passenger_wsgi.py", "exec")


if __name__ == "__main__":
    unittest.main()
