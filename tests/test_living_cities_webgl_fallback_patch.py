import hashlib
import subprocess
import sys
import unittest

from scripts.living_cities_webgl_fallback_patch import patch_source, REPLACEMENTS


ORIGINAL = '\n'.join(old for old, _ in REPLACEMENTS)


class OriginalWorldFallbackPatchTests(unittest.TestCase):
    def test_original_world_is_preserved_and_fallback_uses_same_build_state(self):
        candidate = patch_source(ORIGINAL)
        self.assertIn('function renderFallbackWorld()', candidate)
        self.assertIn('cityById(game)', candidate)
        self.assertIn('isBuildable(city,x,z)', candidate)
        self.assertIn('selection={x,z}', candidate)
        self.assertIn('renderFallbackWorld();}', candidate)
        self.assertIn('renderer=new WorldRenderer', candidate)
        self.assertIn('role","region', candidate)
        self.assertIn('aria-pressed', candidate)
        self.assertNotIn('3D unavailable";', candidate)

    def test_fails_closed_on_changed_release_and_duplicate_patch(self):
        with self.assertRaisesRegex(ValueError, 'unexpected_original_source_signature'):
            patch_source(ORIGINAL.replace('function update()', 'function rerender()'))
        with self.assertRaisesRegex(ValueError, 'already_patched'):
            patch_source(patch_source(ORIGINAL))

    def test_cli_pins_source_hash_and_refuses_bad_hash(self):
        tool = 'scripts/living_cities_webgl_fallback_patch.py'
        expected = hashlib.sha256(ORIGINAL.encode()).hexdigest()
        command = [sys.executable, tool, '--source', '-', '--expected-sha256', expected]
        result = subprocess.run(command, input=ORIGINAL.encode(), capture_output=True, check=True)
        self.assertIn(b'function renderFallbackWorld()', result.stdout)
        rejected = subprocess.run(command[:-1] + ['0' * 64], input=ORIGINAL.encode(), capture_output=True)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(rejected.stdout, b'')


if __name__ == '__main__':
    unittest.main()
