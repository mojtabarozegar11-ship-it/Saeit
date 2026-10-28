"""Regression tests for metadata/reference integrity only; never biological validation.

Run: python -m unittest discover -s research/quality_gates -p 'test_zm_r01_reference_preflight.py' -v
Synthetic short text fixtures are solely for negative parser tests, not RNA-seq results.
"""
import pathlib
import tempfile
import unittest

from zm_r01_preflight import GateError, check_gtf, fasta_contigs


class ReferenceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)

    def file(self, name, contents):
        p = self.root / name
        p.write_text(contents, encoding='utf-8')
        return p

    def test_fasta_contig_lengths(self):
        p = self.file('ref.fa', '>chr1 description\nACGTRYSWKMBDHVN\n>chr2\nacgt\n')
        self.assertEqual(fasta_contigs(p), {'chr1': 15, 'chr2': 4})

    def test_fasta_rejects_sequence_without_header(self):
        with self.assertRaisesRegex(GateError, 'before header'):
            fasta_contigs(self.file('ref.fa', 'ACGT\n>chr1\nACGT\n'))

    def test_fasta_rejects_duplicate_contig(self):
        with self.assertRaisesRegex(GateError, 'duplicate'):
            fasta_contigs(self.file('ref.fa', '>chr1\nAC\n>chr1\nGT\n'))

    def test_fasta_rejects_empty_contig(self):
        with self.assertRaisesRegex(GateError, 'empty contigs'):
            fasta_contigs(self.file('ref.fa', '>chr1\n>chr2\nAC\n'))

    def test_fasta_rejects_invalid_bases(self):
        with self.assertRaisesRegex(GateError, 'Invalid DNA alphabet'):
            fasta_contigs(self.file('ref.fa', '>chr1\nACGT12\n'))

    def test_gtf_accepts_valid_interval(self):
        gtf = self.file('ref.gtf', 'chr1\tsrc\tgene\t1\t4\t.\t+\t.\tgene_id "g1";\n')
        self.assertEqual(check_gtf(gtf, {'chr1': 4}), 1)

    def test_gtf_rejects_out_of_range_end(self):
        gtf = self.file('ref.gtf', 'chr1\tsrc\tgene\t1\t5\t.\t+\t.\tgene_id "g1";\n')
        with self.assertRaisesRegex(GateError, 'outside FASTA'):
            check_gtf(gtf, {'chr1': 4})

    def test_gtf_rejects_reverse_coordinates(self):
        gtf = self.file('ref.gtf', 'chr1\tsrc\tgene\t4\t2\t.\t+\t.\tgene_id "g1";\n')
        with self.assertRaisesRegex(GateError, 'outside FASTA'):
            check_gtf(gtf, {'chr1': 4})

    def test_gtf_rejects_unknown_contig(self):
        gtf = self.file('ref.gtf', 'chrX\tsrc\tgene\t1\t2\t.\t+\t.\tgene_id "g1";\n')
        with self.assertRaisesRegex(GateError, 'absent from FASTA'):
            check_gtf(gtf, {'chr1': 4})

    def test_gtf_rejects_invalid_strand(self):
        gtf = self.file('ref.gtf', 'chr1\tsrc\tgene\t1\t2\t.\tX\t.\tgene_id "g1";\n')
        with self.assertRaisesRegex(GateError, 'strand/frame'):
            check_gtf(gtf, {'chr1': 4})

    def test_gtf_rejects_invalid_columns(self):
        gtf = self.file('ref.gtf', 'chr1\tsrc\tgene\t1\t2\t.\t+\t.\n')
        with self.assertRaisesRegex(GateError, 'nine columns'):
            check_gtf(gtf, {'chr1': 4})


if __name__ == '__main__':
    unittest.main()
