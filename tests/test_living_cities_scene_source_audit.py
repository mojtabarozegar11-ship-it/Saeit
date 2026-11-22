import tempfile
import unittest
from pathlib import Path
from scripts.living_cities_scene_source_audit import audit


class SourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        for name in ('play/index.html', 'static/living_cities/app.mjs',
                     'static/living_cities/render.mjs', 'static/living_cities/style.css'):
            file = self.folder / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text('<canvas id="world"></canvas>' if name.endswith('.html') else 'const ready = true;')

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_original_assets(self):
        self.assertEqual(audit(self.folder)['issues'], [])

    def test_markup_hiding_scene_detected(self):
        (self.folder / 'play/index.html').write_text('<canvas id="world" style="display: none"></canvas>')
        self.assertIn('html_hides_world_canvas', audit(self.folder)['issues'])

    def test_runtime_hide_signal_requires_review(self):
        (self.folder / 'static/living_cities/app.mjs').write_text('world.style.display = "none";')
        self.assertIn('entry_has_canvas_hide_branch_review_required', audit(self.folder)['issues'])

    def test_missing_renderer_fails(self):
        (self.folder / 'static/living_cities/render.mjs').unlink()
        self.assertIn('missing_renderer', audit(self.folder)['issues'])

    def test_symlink_rejected(self):
        file = self.folder / 'static/living_cities/app.mjs'
        file.unlink()
        file.symlink_to(self.folder / 'play/index.html')
        result = audit(self.folder)
        self.assertIn('missing_entry', result['issues'])
        self.assertTrue(result['assets']['entry']['symlink_rejected'])


if __name__ == '__main__':
    unittest.main()
