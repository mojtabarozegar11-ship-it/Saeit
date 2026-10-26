# ZM-R01 C28 — Original URGI RefSeq v2.0 README identified; sequence access still gated

**26 October 2026 | Primary-source provenance check | NO COUNTS / NO DESeq2**

## New directly identified source artifact

The original URGI repository exposes an indexed PDF with the precise path:

https://urgi.versailles.inrae.fr/download/iwgsc/IWGSC_RefSeq_Assemblies/v2.0/iwgsc_refseqv2.0_README.pdf

The search-indexed original README states that IWGSC RefSeq v2.0 was released under the **Toronto data-access agreement** and that it **had not yet been annotated at the time of the README**. The README explicitly says **MD5 checksums are provided for data-transfer verification**, and names at least the following original v2.0 sequence resources:
- `iwgsc_refseqv2.0_chrUn.fa.zip` — a synthetic concatenated unplaced-scaffold pseudomolecule with 100 Ns as separators.
- `iwgsc_refseqv2.0_unplaced_scaffolds.fa.zip` — separate unanchored scaffolds.

**Important methodological implication:** the synthetic `chrUn` concatenation is **not interchangeable** with separate unplaced scaffolds for read alignment and multimapping accounting. Any eventual reference index must declare whether unplaced sequences are included, in which representation, and how ambiguous read pairs are handled. Including both representations simultaneously would introduce duplicate reference content and can distort mapping/counting.

## Independent official access evidence

The official IWGSC v2.0 notice explicitly requires registration and acceptance of the IWGSC General Data Access Agreement before URGI credentials are provided:
https://www.wheatgenome.org/resources/sequences/iwgsc-refseq-v2.0-now-available-at-urgi

The URGI announcement separately identifies this as **v2.0** rather than v2.1:
https://urgi.versailles.inrae.fr/About-us/News/2019/IWGSC-RefSeq-v2.0-assembly-available-to-download

The IWGSC v2.1 assembly and annotation are a distinct later release, publicly available:
https://www.wheatgenome.org/resources/annotations

The indexed v2.1 annotation README, dated September 2020, says **restricted at that time**; the consortium's April 2021 release later says v2.1 annotation is freely available. This is a **date-dependent access change**, not proof of v2.0 annotation access.

## Access and replication decision

1. **Provenance progress:** original v2.0 README location and at least two exact source filenames are now independently identified. This is a reference-source identity finding, not acquisition of FASTA, GTF or actual MD5 values.
2. **Unresolved:** no exact v2.0 FASTA+matching annotation/GTF+gene-ID mapping+license permission pair; no checksum verified against bytes. Search-indexed PDF snippets are not a complete publisher-approved gene model manifest.
3. **Next allowed action:** obtain rights to inspect the exact v2.0 directory and verify annotation availability; document checksum *values* and matching assembly metadata before any download of the genome. A rights agreement needs owner approval.
4. **Do not** treat v2.1 `GCA_018294505.1` or `GCF_018294505.1` as v2.0, use both `chrUn` and separate scaffolds as duplicate references, or claim DESeq2/FDR based on the 1,167 FPKM hypotheses.
5. No bulk FASTQ transfer (149.54GB), paid VPS compute, clinical/animal experimentation or site deployment.

**Scientific status:** reference identification improved; exact-original-reference replication remains BLOCKED. This note does not claim a newly generated count matrix or a publication-ready finding.
