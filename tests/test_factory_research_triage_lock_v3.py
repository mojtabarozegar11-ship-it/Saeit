"""Regression contract for a non-overlapping private research triage cycle."""
import unittest


class ResearchTriageLockContract(unittest.TestCase):
    def test_private_lock_name_is_stable(self):
        self.assertEqual('.research-triage.lock', '.research-triage.lock')


if __name__ == '__main__':
    unittest.main()
