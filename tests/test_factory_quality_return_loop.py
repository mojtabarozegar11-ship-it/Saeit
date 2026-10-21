"""Real assessment -> work order -> changed ZIP -> reinspection, never approval."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('quality_return_test',
    Path(__file__).resolve().parents[1] / 'scripts/factory_product_rework.py')
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


class QualityReturnLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.recipe = 'example_product'
        self.archive = self.root / 'candidate.zip'
        self.write_zip('original bytes')
        self.old_sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.assessment = self.root / 'quality-excellence/rework' / self.recipe / 'current.json'
        self.order = self.root / 'quality-excellence/production-workorders' / self.recipe / 'current.json'
        self.assessment.parent.mkdir(parents=True)
        self.order.parent.mkdir(parents=True)
        self.assessment.write_text(json.dumps({'artifact_sha256': self.old_sha, 'defects': ['wrong formula']}))
        self.order.write_text(json.dumps({
            'schema': 'saeit.factory.production-rework-order.v1',
            'recipe': self.recipe, 'artifact_sha256': self.old_sha,
            'source_quality_receipt_sha256': hashlib.sha256(self.assessment.read_bytes()).hexdigest(),
            'status': 'NEEDS_REWORK'}))

    def write_zip(self, text):
        with zipfile.ZipFile(self.archive, 'w') as out:
            out.writestr('result.txt', text)

    def build_receipt(self):
        return {'recipe': self.recipe, 'qa_status': 'passed',
                'artifact_sha256': hashlib.sha256(self.archive.read_bytes()).hexdigest()}

    def test_real_changed_build_returns_to_review_without_closing_defect(self):
        order = repair.quality_returns(self.root)['orders'][0]
        self.write_zip('corrected formula and measured output')
        result = repair.record_quality_candidate(self.root, order, self.build_receipt(), archive_path=self.archive)
        self.assertEqual(result['status'], 'awaiting_independent_reinspection')
        self.assertTrue(result['genuinely_changed_artifact'])
        self.assertFalse(result['quality_defect_closed'])
        self.assertFalse(result['commercial_release_allowed'])
        self.assertEqual(len(repair.quality_returns(self.root)['orders']), 1)
        repair.record_quality_candidate(self.root, order, self.build_receipt(), archive_path=self.archive)
        self.assertEqual(len(list((self.root/'quality-return-candidates'/self.recipe).glob('*.json'))), 1)

    def test_unchanged_archive_is_not_a_repair(self):
        order = repair.quality_returns(self.root)['orders'][0]
        result = repair.record_quality_candidate(self.root, order, self.build_receipt(), archive_path=self.archive)
        self.assertEqual(result['status'], 'source_repair_still_required')
        self.assertFalse(result['genuinely_changed_artifact'])

    def test_modified_assessment_invalidates_workorder(self):
        self.assessment.write_text('{}')
        result = repair.quality_returns(self.root)
        self.assertEqual(result['orders'], [])
        self.assertEqual(result['invalid_orders'], 1)

    def test_assessment_changed_during_build_keeps_order_open(self):
        order = repair.quality_returns(self.root)['orders'][0]
        self.assessment.write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'CHANGED_DURING_BUILD'):
            repair.record_quality_candidate(self.root, order, self.build_receipt(), archive_path=self.archive)
        self.assertFalse((self.root/'quality-return-candidates').exists())

    def test_bad_sha_cannot_create_candidate(self):
        order = repair.quality_returns(self.root)['orders'][0]
        receipt = self.build_receipt()
        receipt['artifact_sha256'] = '0'*64
        with self.assertRaisesRegex(RuntimeError, 'BUILD_HASH_MISMATCH'):
            repair.record_quality_candidate(self.root, order, receipt, archive_path=self.archive)

    def test_failed_build_cannot_create_candidate(self):
        order = repair.quality_returns(self.root)['orders'][0]
        receipt = dict(self.build_receipt(), qa_status='failed')
        with self.assertRaisesRegex(RuntimeError, 'REQUIRES_REAL_PASSED_BUILD'):
            repair.record_quality_candidate(self.root, order, receipt, archive_path=self.archive)

    def test_symlinked_assessment_is_rejected(self):
        saved = self.root/'assessment.json'
        self.assessment.rename(saved)
        self.assessment.symlink_to(saved)
        self.assertEqual(repair.quality_returns(self.root)['invalid_orders'], 1)

    def test_missing_queue_is_empty(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(repair.quality_returns(empty), {'orders': [], 'invalid_orders': 0})


if __name__ == '__main__':
    unittest.main()
