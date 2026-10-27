# ZM-R01 / C36 — IWGSC reference/annotation identity and rights-provenance audit

**27 October 2026 | Internal AI source-level audit; metadata only. No genome, FASTQ, archive or large annotation download.**

## Official sources checked
1. IWGSC RefSeq v2.0 announcement, https://www.wheatgenome.org/resources/sequences/iwgsc-refseq-v2.0-now-available-at-urgi : the initially announced v2.0 assembly was **not yet annotated** and access required registration and an IWGSC data access agreement. The historical announcement is not proof of current access status.
2. IWGSC annotations index, https://www.wheatgenome.org/resources/annotations : the consortium says RefSeq **v2.1 assembly and annotation** are freely available through URGI and NCBI under PRJNA669381.
3. Official URGI v2.1 annotation directory, https://urgi.versailles.inrae.fr/download/iwgsc/IWGSC_RefSeq_Annotations/v2.1/ : lists `iwgsc_refseqv2.1_gene_annotation_200916.zip` (approximately 397 MB) and a corresponding `.md5.txt` sidecar. The directory listing establishes **sidecar availability, not successful local checksum verification**.
4. Official URGI v2.1 assembly directory, https://urgi.versailles.inrae.fr/download/iwgsc/IWGSC_RefSeq_Assemblies/v2.1/ : lists `iwgsc_refseqv2.1_assembly.fa.zip` (approximately 4.1 GB) with `.md5.txt` sidecar. **Not downloaded.**
5. URGI v2.1 annotation README, https://urgi.versailles.inrae.fr/download/iwgsc/IWGSC_RefSeq_Annotations/v2.1/iwgsc_refseqv2.1_annotation_README.pdf : a historical embedded disclaimer says data are restricted to IWGSC sponsors, whereas the current consortium public announcement says v2.1 is freely available. This **rights-text mismatch** may reflect a stale README; it is **not** evidence that current access is prohibited or permitted for every downstream reuse. The README identifies **HC/LC GFF3**, not an assured GTF, and says annotation was transferred from v1.2. File formats must not be silently conflated.
6. Ensembl Plants archive, https://jun2026-plants.ensembl.org/Triticum_aestivum_refseqv2/Info/Annotation : its `refseqv2` URL label actually reports assembly **IWGSC_RefSeq_v2.1 / GCA_018294505.1**, as documented in C35.

## New concrete findings
- A downloadable **v2.1** assembly archive and **v2.1** annotation archive have official filenames and published MD5 sidecar locations; this does **not** establish the exact **v2.0** FASTA+annotation pair used by Milec et al., nor the validity of any local files.
- **Assembly v2.0 at initial release lacked annotation**. Therefore, a claim of exact v2.0 replication must identify which later annotation release was aligned to v2.0 and demonstrate chromosome/coordinate compatibility; using v2.1 GFF3 without declaring a changed reference is not exact replication.
- Public availability and rights to downstream redistribution are distinct; the official public-release notice and historical sponsor-only README require a dated, explicit rights check. No agreement, registration, download or contact has been initiated.
- MD5 sidecars exist for the named **v2.1 ZIP files**. They do **not** prove FASTQ MD5, uncompressed FASTA checksum, exact Milec input files, mapping settings, or integer counts.

## Release gate / required evidence
Record the exact original study's assembly release/accession, filename, author pipeline and matching annotation release; document terms and a reproducible manifest with source URL, byte size, published sidecar digest, local computed digest (if later lawfully acquired), and sequence-contig/GFF3 compatibility. Verify multimapping, strandedness, biological replicate allocation and integer gene counts before any DEG/FDR claim. A separately disclosed v2.1 sensitivity analysis is permissible only with real data, provenance and approvals, never as a relabelled v2.0 replication.

**Status: DATA REBUILD / NO SUBMISSION.** No 149.54 GB bulk download, no VPS, no payment, no fabricated MD5/DEG/FDR, no author or journal approval.
