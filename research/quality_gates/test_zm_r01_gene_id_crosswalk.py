"""Synthetic parser-only regressions; not biological data or DEG results.
Run: python -m unittest discover -s research/quality_gates -p 'test_zm_r01_gene_id_crosswalk.py' -v
"""
import pathlib
import tempfile
import unittest
from zm_r01_preflight import GateError, gtf_gene_ids, check_count_matrix

class GeneIdProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)

    def write(self, name, text):
        p = self.root / name
        p.write_text(text, encoding="utf-8")
        return p

    def test_gtf_ids_crosswalk_existing_counts(self):
        gtf = self.write("ref.gtf", 'chr1\tsrc\tgene\t1\t3\t.\t+\t.\tgene_id "g1";\n')
        ids = gtf_gene_ids(gtf)
        matrix = self.write("counts.tsv", "gene_id\tL1\tL2\ng1\t0\t2\n")
        self.assertEqual(check_count_matrix(matrix, {"L1","L2"}, ids), 1)

    def test_reject_foreign_count_gene(self):
        gtf = self.write("ref.gtf", 'chr1\tsrc\tgene\t1\t3\t.\t+\t.\tgene_id "g1";\n')
        matrix = self.write("counts.tsv", "gene_id\tL1\tL2\nforeign\t1\t2\n")
        with self.assertRaisesRegex(GateError, "absent from GTF"):
            check_count_matrix(matrix, {"L1","L2"}, gtf_gene_ids(gtf))

    def test_reject_missing_gtf_gene_id(self):
        gtf = self.write("ref.gtf", 'chr1\tsrc\tgene\t1\t3\t.\t+\t.\tName=g1;\n')
        with self.assertRaisesRegex(GateError, "Missing GTF gene_id"):
            gtf_gene_ids(gtf)

if __name__ == "__main__":
    unittest.main()
