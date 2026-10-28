"""Regression tests for metadata/reference integrity only; never biological validation.

Run: python -m unittest discover -s research/quality_gates -p 'test_zm_r01_reference_preflight.py' -v
Synthetic short text fixtures are solely for negative parser tests, not RNA-seq results.
"""
import pathlib
import tempfile
import unittest

from zm_r01_preflight import GateError, check_gtf, fasta_contigs, valid_raw_integer_count, check_count_matrix


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



class RawCountIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.ids = {'L1', 'L2'}

    def matrix(self, contents):
        p = self.root / 'counts.tsv'
        p.write_text(contents, encoding='utf-8')
        return p

    def test_raw_count_accepts_r_integer_boundary(self):
        self.assertTrue(valid_raw_integer_count('0'))
        self.assertTrue(valid_raw_integer_count('0002147483647'))
        self.assertFalse(valid_raw_integer_count('2147483648'))

    def test_raw_count_rejects_oversized_and_non_ascii(self):
        self.assertFalse(valid_raw_integer_count('9' * 10000))
        self.assertFalse(valid_raw_integer_count('١٢'))
        self.assertFalse(valid_raw_integer_count('-1'))
        self.assertFalse(valid_raw_integer_count('1.5'))

    def test_count_matrix_accepts_unique_ids_and_counts(self):
        self.assertEqual(check_count_matrix(
            self.matrix('gene_id\\tL2\\tL1\\ngeneA\\t0\\t2147483647\\n'),
            self.ids), 1)

    def test_count_matrix_rejects_duplicate_library_columns(self):
        with self.assertRaisesRegex(GateError, 'each library ID exactly once'):
            check_count_matrix(
                self.matrix('gene_id\\tL1\\tL1\\ngeneA\\t1\\t2\\n'), self.ids)

    def test_count_matrix_rejects_overflow(self):
        with self.assertRaisesRegex(GateError, '32-bit'):
            check_count_matrix(
                self.matrix('gene_id\\tL1\\tL2\\ngeneA\\t2147483648\\t0\\n'), self.ids)

    def test_count_matrix_rejects_ambiguous_gene_id(self):
        with self.assertRaisesRegex(GateError, 'malformed'):
            check_count_matrix(
                self.matrix('gene_id\\tL1\\tL2\\ngene A\\t1\\t2\\n'), self.ids)


if __name__ == '__main__':
    unittest.main()
