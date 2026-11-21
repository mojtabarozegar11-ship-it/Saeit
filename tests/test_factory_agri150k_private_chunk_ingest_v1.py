import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/factory_agri150k_private_chunk_ingest_v1.py'
spec = importlib.util.spec_from_file_location('private_ingest', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class PrivateChunkIngestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'factory'
        self.root.mkdir()
        self.area = self.root / 'production-instructions/stage-05/doctoral-monographs-150k-en-v1'
        self.area.mkdir(parents=True)
        gate = mod.gate_module()
        (self.area / 'AGRI-001.json').write_text(json.dumps(gate.plan(),ensure_ascii=False,sort_keys=True,indent=2)+'\n')
        self.source = Path(self.tmp.name) / 'original.md'
        self.source.write_text(' '.join('diagnostic'+str(i)+' hydraulic'+str(i)+' substrate'+str(i) for i in range(320)))

    def test_private_import_idempotent_and_never_publishes(self):
        first = mod.ingest(self.root, self.source, 1, 1)
        self.assertEqual(first['state'], 'PRIVATE_QA_UNREVIEWED')
        self.assertGreater(first['unreviewed_words'], 600)
        self.assertFalse(first['published'])
        self.assertFalse(first['qc1000_approved'])
        second = mod.ingest(self.root, self.source, 1, 1)
        self.assertEqual(second['state'], 'EXISTING_IDENTICAL_PRIVATE_DRAFT')
        self.assertEqual(first['sha256'], second['sha256'])
        self.assertEqual(len(list((self.area/'authored-chunks/AGRI-001').glob('*.md'))), 1)

    def test_mutated_existing_chunk_rejected(self):
        mod.ingest(self.root, self.source, 1, 1)
        self.source.write_text(self.source.read_text()+' extra')
        with self.assertRaisesRegex(ValueError,'IMMUTABLE_CHUNK_CONFLICT'):
            mod.ingest(self.root, self.source, 1, 1)

    def test_missing_plan_fails_closed(self):
        (self.area/'AGRI-001.json').unlink()
        with self.assertRaisesRegex(ValueError,'AGRI_PLAN_NOT_INSTALLED'):
            mod.ingest(self.root, self.source, 1, 1)

    def test_source_symlink_and_short_draft_rejected(self):
        symlink = Path(self.tmp.name)/'link.md'
        symlink.symlink_to(self.source)
        with self.assertRaisesRegex(ValueError,'UNSAFE_SOURCE_LINK'):
            mod.ingest(self.root, symlink, 1, 1)
        self.source.write_text('too short')
        with self.assertRaisesRegex(ValueError,'INVALID_CHUNK_SIZE|CHUNK_WORD_COUNT'):
            mod.ingest(self.root, self.source, 1, 1)

    def test_cross_chunk_repetition_rejected(self):
        mod.ingest(self.root, self.source, 1, 1)
        with self.assertRaisesRegex(ValueError,'CHUNK_DUPLICATES_PRIOR'):
            mod.ingest(self.root, self.source, 1, 2)

    def test_unsafe_intermediate_directory_rejected(self):
        (self.root/'production-instructions/stage-05').rename(self.root/'production-instructions/stage-05-old')
        (self.root/'production-instructions/stage-05').symlink_to(self.root/'production-instructions/stage-05-old',target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'UNSAFE_PRIVATE_DIRECTORY'):
            mod.ingest(self.root,self.source,1,1)


if __name__=='__main__':
    unittest.main()
