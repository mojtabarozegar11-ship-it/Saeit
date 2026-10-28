# ZM-R01 C32 — Published-paper author postprint identified, distinct from Zenodo v1 preprint

**26 October 2026 | Original institutional publication-file discovery | NO claim of full-text extraction or chamber replication**

## Two independent institutional evidence routes

1. **Czech Academy of Sciences (ASEP), final article record 0641134:** https://asep.lib.cas.cz/arl-cav/cs/detail-cav_un_epca-0641134-Integrative-morphophysiological-and-transcriptomic-insights-into-wheat-responses-to-combined-drough/ . The institution identifies the **published** Milec et al. *Plant Stress* 18 (2025), article 101115, DOI https://doi.org/10.1016/j.stress.2025.101115 and lists a separately hosted file `1-s2.0-S2667064X25003823-main.pdf`, approximately **6.5 MB**, marked **CC BY**, **author postprint**, access permitted.
2. **Rothamsted Research repository direct PDF route:** https://repository.rothamsted.ac.uk/id/eprint/33667/2/1-s2.0-S2667064X25003823-main.pdf . Public search-index text confirms that the file is a **Plant Stress 18 (2025) 101115** PDF with a `Materials and methods` and `Plant materials and initial growth conditions` section.

The **Zenodo 20 July 2025 v1 DOCX preprint**, DOI https://doi.org/10.5281/zenodo.16229021, remains a distinct version. Do **not** assume its Methods and the final publication are identical. The ASEP data deposit DOI https://doi.org/10.57680/asep.0640950 is a **third** object, a separate seven-workbook data archive.

## Access attempts and bounded result

The public institutional catalogue and search-index metadata were read. A direct request for the Rothamsted PDF returned **restricted/fetch failure** in the available reader, and a separate bounded binary download attempt also failed. **No final PDF bytes, SHA256, PDF page images or full Materials and methods were obtained.** The search-index excerpt is insufficient to establish growth-chamber count, plant/pot randomization, independent treatment-assignment units, library batch or a precise RefSeq v2.0 FASTA/GTF accession. These remain explicitly **UNVERIFIED**.

## Why this is scientifically relevant

This is a more appropriate **published-version provenance route** for the independent-unit and exact reference-assembly gates than relying only on a July preprint or GEO `biol_rep` labels. It can help adjudicate whether 24 libraries represent 24 independently randomized treatment units or clustered/technical subsamples. The discovery alone **does not** resolve pseudoreplication or authorize a DESeq2 model.

## Exact next acquisition gate

1. Retrieve the **permitted 6.5 MB author-postprint** in a non-VPS bounded environment through an authorized working source; verify file bytes, SHA256, publisher DOI and page count.
2. Extract exact Methods sentences/table for number of growth chambers, pots/plants per chamber, experimental blocks, randomization, repeated treatment allocation, sample pooling, plant IDs, timepoints and library batches. Report missing fields as missing.
3. Separately extract exact read-processing, HISAT2/Trim Galore, RefSeq v2.0 assembly FASTA and gene annotation source accession/version, strand protocol and unique/multimapping policy. Verify against URGI reference metadata.
4. Reconcile with the 24 GSM labels, the published 2×2×2 design and the C31 conditional df analysis; **do not** infer unit independence from three replicate labels.
5. Only after independently valid units, source-licensed reference and real integer counts exist can count-based DESeq2/FDR be considered.

**Decision: provenance route found; independent-unit, genome-reference and raw-count gates remain CLOSED.** No FASTQ bulk download, VPS/cPanel deployment, paid access, gene significance claim, submission or live-site edit.
