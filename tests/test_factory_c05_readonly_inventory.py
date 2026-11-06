"""Realistic local fixtures for the read-only VPS mapping probe."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from factory_c05_live_readonly_inventory import summarize


class ReadOnlyInventoryTests(unittest.TestCase):
    def test_missing_runtime_is_finite_and_does_not_create_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'factory-runtime'
            before = tuple(Path(directory).rglob('*'))
            output = summarize(root)
            self.assertFalse(output['filesystem_root_exists'])
            self.assertFalse(output['slot']['exists'])
            self.assertFalse(output['artifact']['exists'])
            self.assertEqual(before, tuple(Path(directory).rglob('*')))

    def test_completed_single_product_is_not_wrongly_classified_as_active(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'factory-runtime'
            source = root / 'operations' / 'single-product-runtime' / 'product_recipes' / 'farm_enterprise_economics'
            source.mkdir(parents=True)
            (source / 'README.md').write_text('example', encoding='utf-8')
            slot = root / 'private/autonomous-product-cycle/quality-excellence/product-flow/active-slots/current.json'
            slot.parent.mkdir(parents=True)
            slot.write_text(json.dumps({'line_id': 41, 'capacity': 1, 'active': [], 'waiting': [],
                'technical_exited': {'farm_enterprise_economics': {
                    'source_sha256': 'a' * 64, 'artifact_sha256': 'b' * 64}}, 'commercial_release': False}))
            output = summarize(root)
            self.assertEqual(output['slot']['active_recipe_names'], [])
            self.assertTrue(output['slot']['flagship_technical_exited'])
            self.assertEqual(output['slot']['flagship_exit_source_sha256'], 'a' * 64)
            self.assertTrue(output['paths']['single-product-runtime']['exists'])
            self.assertEqual(output['paths']['single-product-runtime']['source_file_count'], 1)


if __name__ == '__main__':
    unittest.main()
