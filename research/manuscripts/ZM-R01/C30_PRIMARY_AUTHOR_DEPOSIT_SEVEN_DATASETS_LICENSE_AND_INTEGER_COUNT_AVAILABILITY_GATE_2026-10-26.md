# ZM-R01 C30 — Primary author-deposited supplementary data discovered: seven workbooks, not proven integer counts

**26 October 2026 | Source discovery and research-data provenance, not expression inference | DATA REBUILD / NO SUBMISSION**

## Independent primary institutional record

The Library of the Czech Academy of Sciences (ASEP) hosts a separately registered scientific-data record by **Zbyněk Milec** linked to the original *Plant Stress* study:

- **Research-data DOI:** https://doi.org/10.57680/asep.0640950
- **Persistent record:** https://hdl.handle.net/11104/0371204
- **Institutional source:** https://asep.lib.cas.cz/arl-cav/en/result/?disp=+elevated+co2+&field=S610&qt=zf&src=cav_un_epca&term=%22%5Eelevated+co2%5E%22
- **Depositor:** Zbyněk Milec; **release date:** 6 November 2025.
- **Archive name and advertised size:** `Dataset_Milec.zip`, **97.8 MB**.
- **Record-stated license:** **CC BY 4.0**, with attribution required.
- The institutional catalogue explicitly calls the archive Excel files with original and working analysis data. This does **not** establish that the archive contains raw sequencing reads or an integer gene-count matrix.

## Seven specifically enumerated datasets in the official record

| Dataset | Institutional description | What it can potentially validate | What it does NOT establish |
|---|---|---|---|
| 1 | FPKM values and statistics for individual treatments | Published treatment summaries and normalized-expression provenance | Integer fragment counts or DESeq2 dispersion |
| 2 | FPKM values of treatment-specific genes | Reported treatment-specific normalized expression | Raw alignment or read uniqueness |
| 3 | Gene mode response classification | Authors' response-class labels | Independently replicated gene significance |
| 4 | Functional enrichment analysis of WGCNA modules | Authors' enrichment and module interpretation | New network or independently rerun WGCNA |
| 5 | List of up/downregulated transcription factors | Original author TF candidate lists | Recomputed differential-expression FDR |
| 6 | List of treatment-specific up/downregulated genes from Upset plot | Published set membership | Independently verified statistical contrasts |
| 7 | List of treatment-specific up/downregulated transcription factors | Published TF-specific set membership | Independently verified statistical contrasts |

**Critical scientific finding:** The primary institutional deposit provides a new, explicitly licensed and versioned route to *audit the authors' published downstream tables* without downloading ~149.54 GB of ENA FASTQ. **None of the seven advertised file descriptions explicitly promises an integer count matrix**. It would be false to treat Dataset 1's FPKM values as counts or to declare the 24-sample DESeq2 gate solved.

## Second independent manuscript provenance route

The original authors also posted a **6.3 MB DOCX preprint** at https://zenodo.org/records/16229021 (DOI https://doi.org/10.5281/zenodo.16229021), with file name `Wheat responses to combined drought, heat, and elevated CO2.docx` and the record-reported file MD5 `d4ff896311410ddb3531d68295a69692`. The record lists the version as v1, published **20 July 2025**. This is a *preprint*, not automatically identical to the final published Methods; compare exact sections before treating it as a definitive resolution of experimental-unit allocation or reference accession.

The original journal article is **Milec et al. (2025)**, DOI https://doi.org/10.1016/j.stress.2025.101115; GEO series https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE294406. The existing GEO FPKM workbook and 24 GSM manifest are already audited in C26/C24; do not count them again as newly acquired.

## Acquisition and reproducibility status — fail closed

1. **Discovered and independently catalogued:** official ASEP record, archive name, size, seven data descriptions, release date, and license.
2. **Not downloaded or inspected in this cycle:** `Dataset_Milec.zip` bytes, its internal XLSX files, and Zenodo DOCX bytes. No SHA256 or row-level validation for these new files can be claimed.
3. **Next permitted bounded action:** retrieve only the ~97.8 MB licensed ZIP in a non-VPS temporary environment when a working download route is available; record exact source URL, SHA256, ZIP directory listing, workbook sheet names, units, sample identifiers, gene IDs and actual data types. Do not infer content from filename.
4. Compare author-reported TF/Upset/WGCNA tables against the existing GEO FPKM results as **provenance concordance only**, keeping these separate from count-based DESeq2.
5. If the archive contains no genuine 24-column nonnegative integer fragment count matrix with gene-ID/reference provenance, the raw-read/reference/counting gate remains **CLOSED**.
6. No cost, VPS usage, 149.54 GB download, new DEG, adjusted FDR, author contact, journal submission or live-site change occurred.

**Decision:** genuine new primary-source discovery; **not** successful acquisition of raw counts or scientific validation of gene expression. Continue the ZM data-rebuild gate.
