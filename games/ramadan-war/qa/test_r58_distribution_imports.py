"""Fail-closed runtime module dependency checks for offline R58 packages."""
import io
import unittest
import zipfile

from r58_distribution_gate import missing_local_modules


def module_gaps(files):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    data.seek(0)
    with zipfile.ZipFile(data) as archive:
        return missing_local_modules(archive, archive.namelist())


class RuntimeImportsTests(unittest.TestCase):
    def test_resolved_static_import(self):
        files = {
            "ramadan-war/game.js": "import {award} from './economy-reward.mjs';",
            "ramadan-war/economy-reward.mjs": "export const award = 1;",
        }
        self.assertEqual(module_gaps(files), [])

    def test_missing_static_import_blocks_release(self):
        self.assertEqual(module_gaps({
            "ramadan-war/game.js": "import {award} from './economy-reward.mjs';"
        }), ["ramadan-war/game.js->./economy-reward.mjs"])

    def test_missing_dynamic_import_blocks_release(self):
        self.assertEqual(module_gaps({
            "ramadan-war/game.js": "const module = import('./lazy-level.mjs');"
        }), ["ramadan-war/game.js->./lazy-level.mjs"])

    def test_nested_vendor_relative_import_resolves(self):
        files = {
            "ramadan-war/three-addons/loaders/GLTFLoader.js":
                "import {Scene} from '../../three.module.js';",
            "ramadan-war/three.module.js": "export const Scene = 1;",
        }
        self.assertEqual(module_gaps(files), [])

    def test_import_outside_game_tree_blocks_release(self):
        self.assertEqual(module_gaps({
            "ramadan-war/game.js": "export {foo} from '../untrusted.mjs';",
            "untrusted.mjs": "export const foo = 1;",
        }), ["ramadan-war/game.js->../untrusted.mjs"])


if __name__ == "__main__":
    unittest.main()
