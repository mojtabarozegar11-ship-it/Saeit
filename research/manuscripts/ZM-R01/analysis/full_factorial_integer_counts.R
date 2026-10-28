#!/usr/bin/env Rscript
# GSE294406: prespecified 2x2x2 integer-count interaction analysis.
# INPUTS MUST BE RAW UNNORMALIZED INTEGER GENE COUNTS, NOT FPKM/TPM.
# Usage: Rscript full_factorial_integer_counts.R counts.tsv manifest.csv independent_units.csv provenance.json output_dir refseq_v2.fasta matching_annotation.gtf 48_fastq_manifest.tsv
# FAIL-CLOSED: this unblocked DESeq2 design is forbidden without source-verified
# raw-count provenance and 24 independently assigned chambers. Shared-chamber
# designs require a different prespecified, cluster-aware analysis.
suppressPackageStartupMessages(library(DESeq2))
args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 8L)
  stop("Usage: Rscript full_factorial_integer_counts.R counts.tsv manifest.csv independent_units.csv provenance.json output_dir refseq_v2.fasta matching_annotation.gtf 48_fastq_manifest.tsv")
counts_file <- args[[1L]]; manifest_file <- args[[2L]]
units_file <- args[[3L]]; provenance_file <- args[[4L]]; outdir <- args[[5L]]
reference_file <- args[[6L]]; annotation_file <- args[[7L]]
fastq_manifest_file <- args[[8L]]
if (!all(file.exists(c(counts_file, manifest_file, units_file, provenance_file,
                       reference_file, annotation_file, fastq_manifest_file))))
  stop("Missing counts, manifest, unit evidence, provenance, reference FASTA or matching annotation GTF; NO DESeq2")
if (!requireNamespace("digest", quietly=TRUE) || !requireNamespace("jsonlite", quietly=TRUE))
  stop("digest and jsonlite required for source integrity checks")
manifest <- read.csv(manifest_file, check.names=FALSE, stringsAsFactors=FALSE)
required <- c("GSM","SRR","GEO_sample_title")
if (!all(required %in% names(manifest))) stop("Manifest lacks GSM/SRR/GEO_sample_title")
if (nrow(manifest) != 24L || anyDuplicated(manifest$GSM) || anyDuplicated(manifest$SRR))
  stop("Expected exactly 24 unique GSM/SRR libraries")
# These structural checks cannot independently authenticate experimental-unit
# records; source documents and real allocation must still be critically reviewed.
units <- read.csv(units_file, check.names=FALSE, stringsAsFactors=FALSE)
unit_fields <- c("GSM", "assignment_unit_id", "chamber_id",
                 "assignment_unit_type", "source_uri", "verification_status")
if (!all(unit_fields %in% names(units)) || nrow(units) != 24L ||
    anyNA(units[,unit_fields,drop=FALSE]) ||
    !setequal(units$GSM, manifest$GSM) || anyDuplicated(units$GSM))
  stop("Missing or invalid 24-row independent-unit evidence; NO DESeq2")
if (any(!nzchar(trimws(as.character(units$assignment_unit_id)))) ||
    anyDuplicated(units$assignment_unit_id) ||
    any(!nzchar(trimws(as.character(units$chamber_id)))) ||
    anyDuplicated(units$chamber_id))
  stop("Repeated/missing treatment-assignment unit or chamber: unblocked design invalid")
if (any(units$assignment_unit_type != "independently_assigned_chamber") ||
    any(units$verification_status != "SOURCE_DOCUMENT_VERIFIED") ||
    any(!grepl("^https://", units$source_uri)))
  stop("Source-verifiable independent chamber assignment not documented")
prov <- jsonlite::fromJSON(provenance_file, simplifyVector=FALSE)
needed_true <- c("raw_unnormalized_gene_counts", "all_24_fastq_md5_recomputed_from_bytes",
                 "refseq_v2_assembly_fasta_verified", "matching_annotation_gtf_verified",
                 "multimapping_policy_independently_validated",
                 "gene_universe_consistent", "independent_units_evidence_verified")
if (any(!vapply(needed_true, function(k) identical(prov[[k]], TRUE), logical(1))))
  stop("Missing positive primary-data/reference/multimapping provenance; NO DESeq2")
for (k in c("counts_sha256", "unit_evidence_sha256", "reference_fasta_sha256",
            "annotation_gtf_sha256", "fastq_manifest_sha256")) {
  if (!is.character(prov[[k]]) || length(prov[[k]]) != 1L ||
      !grepl("^[0-9a-f]{64}$", prov[[k]]))
    stop(paste("Missing/invalid source digest", k))
}
if (!identical(digest::digest(counts_file, algo="sha256", file=TRUE, serialize=FALSE),
               prov$counts_sha256) ||
    !identical(digest::digest(units_file, algo="sha256", file=TRUE, serialize=FALSE),
               prov$unit_evidence_sha256))
  stop("Count or unit evidence SHA256 mismatch; NO DESeq2")
# A JSON declaration is not byte-level verification of the reference/annotation.
# Require actual local reference files and independently hash both before fitting.
if (!identical(digest::digest(reference_file, algo="sha256", file=TRUE, serialize=FALSE),
               prov$reference_fasta_sha256) ||
    !identical(digest::digest(annotation_file, algo="sha256", file=TRUE, serialize=FALSE),
               prov$annotation_gtf_sha256))
  stop("Reference FASTA or annotation GTF SHA256 mismatch; NO DESeq2")
# Do not accept a self-declared all-FASTQ-MD5 flag as proof of real byte verification.
# The 48 FASTQ files must already be locally available under an independently
# authorized acquisition; this script NEVER downloads them or uses a VPS.
# This expensive check runs only after the cheap provenance/reference gates.
if (!identical(digest::digest(fastq_manifest_file, algo="sha256", file=TRUE, serialize=FALSE),
               prov$fastq_manifest_sha256))
  stop("FASTQ manifest SHA256 mismatch; NO DESeq2")
fq <- read.delim(fastq_manifest_file, check.names=FALSE, stringsAsFactors=FALSE)
fq_required <- c("SRR", "read", "fastq_path", "ena_md5")
if (!all(fq_required %in% names(fq)) || nrow(fq) != 48L ||
    anyNA(fq[, fq_required, drop=FALSE]))
  stop("Expected 48 nonmissing SRR/read/path/ENA-MD5 records; NO DESeq2")
fq$SRR <- trimws(as.character(fq$SRR))
fq$read <- trimws(as.character(fq$read))
fq$fastq_path <- trimws(as.character(fq$fastq_path))
fq$ena_md5 <- tolower(trimws(as.character(fq$ena_md5)))
if (any(!nzchar(fq$SRR)) || any(!nzchar(fq$fastq_path)) ||
    !setequal(unique(fq$SRR), manifest$SRR) ||
    any(!fq$read %in% c("R1", "R2")) ||
    anyDuplicated(paste(fq$SRR, fq$read, sep=":")) ||
    any(table(factor(fq$SRR, levels=manifest$SRR)) != 2L) ||
    anyDuplicated(fq$fastq_path) ||
    any(!grepl("^[0-9a-f]{32}$", fq$ena_md5)) ||
    !all(file.exists(fq$fastq_path)))
  stop("FASTQ run/read pairing, paths, ENA MD5 or local bytes invalid; NO DESeq2")
for (run in manifest$SRR) {
  if (!setequal(fq$read[fq$SRR == run], c("R1", "R2")))
    stop("Each SRR must have exactly R1 and R2; NO DESeq2")
}
# C48: A self-consistent user-supplied MD5 list is NOT evidence of ENA provenance.
# Before hashing 149.54 GB of local files, match each run/read MD5 to the
# exact independently retained ENA metadata snapshot pinned by Git blob SHA1.
# The pinned repository snapshot is a source traceability gate, not proof that
# ENA itself has not changed or that the original sample design is valid.
script_flags <- grep("^--file=", commandArgs(trailingOnly=FALSE), value=TRUE)
if (length(script_flags) != 1L)
  stop("Cannot locate Rscript path for pinned ENA source; NO DESeq2")
script_path <- normalizePath(sub("^--file=", "", script_flags[[1L]]), mustWork=TRUE)
ena_source_file <- file.path(dirname(dirname(script_path)),
                             "ENA_PRJNA1249400_OFFICIAL_24_RUN_PAIRED_FASTQ_MD5_2026-10-25.tsv")
if (!file.exists(ena_source_file))
  stop("Pinned repository ENA manifest missing; NO DESeq2")
ena_size <- file.info(ena_source_file)$size
if (!is.finite(ena_size) || ena_size < 1L || ena_size > 1000000L)
  stop("Pinned ENA manifest size invalid; NO DESeq2")
ena_raw <- readBin(ena_source_file, what="raw", n=as.integer(ena_size))
ena_git_blob <- digest::digest(c(charToRaw(paste0("blob ", length(ena_raw))),
                                 as.raw(0), ena_raw),
                                algo="sha1", serialize=FALSE)
if (!identical(ena_git_blob, "d9231121dc27bc13999e120349a80af05aad5e15"))
  stop("Pinned ENA source Git blob SHA1 mismatch; NO DESeq2")
ena <- read.delim(ena_source_file, check.names=FALSE, stringsAsFactors=FALSE)
ena_fields <- c("run_accession", "sample_accession", "fastq1_md5", "fastq2_md5")
if (!all(ena_fields %in% names(ena)) || nrow(ena) != 24L ||
    anyNA(ena[, ena_fields, drop=FALSE]) ||
    anyDuplicated(ena$run_accession) ||
    !setequal(ena$run_accession, manifest$SRR))
  stop("Pinned ENA metadata does not match 24 SRR libraries; NO DESeq2")
# C49: validate the GEO GSM-to-SRR-to-BioSample crosswalk against pinned
# source snapshots, rather than accepting an arbitrary permutation of the
# 24 GSM/SRR pairs. This is source traceability, NOT independent verification
# of biological replicates or treatment-assignment units.
geo_sheet_file <- file.path(dirname(dirname(script_path)),
                            "ZM-R01_24_LIBRARY_FACTORIAL_SAMPLE_SHEET_DESIGN_ONLY_2026-10-27.tsv")
if (!file.exists(geo_sheet_file))
  stop("Pinned GEO factorial crosswalk missing; NO DESeq2")
geo_size <- file.info(geo_sheet_file)$size
if (!is.finite(geo_size) || geo_size < 1L || geo_size > 1000000L)
  stop("Pinned GEO crosswalk size invalid; NO DESeq2")
geo_raw <- readBin(geo_sheet_file, what="raw", n=as.integer(geo_size))
geo_blob <- digest::digest(c(charToRaw(paste0("blob ", length(geo_raw))),
                             as.raw(0), geo_raw),
                           algo="sha1", serialize=FALSE)
if (!identical(geo_blob, "988be37b2b8ae02f3c3c3546fb5e6f49865b2099"))
  stop("Pinned GEO crosswalk Git blob SHA1 mismatch; NO DESeq2")
# Preserve leading zeros in nominal factorial cell labels (000, 001, ...).
geo <- read.delim(geo_sheet_file, check.names=FALSE, stringsAsFactors=FALSE,
                  colClasses="character")
geo_fields <- c("gsm", "biosample", "srr", "D", "H", "C", "cell")
if (!all(geo_fields %in% names(geo)) || nrow(geo) != 24L ||
    anyNA(geo[, geo_fields, drop=FALSE]) ||
    anyDuplicated(geo$gsm) || anyDuplicated(geo$srr) ||
    anyDuplicated(geo$biosample) ||
    !setequal(geo$gsm, manifest$GSM) ||
    !setequal(geo$srr, manifest$SRR))
  stop("GEO crosswalk lacks 24 unique GSM/SRR/BioSample mappings; NO DESeq2")
geo_by_gsm <- geo[match(manifest$GSM, geo$gsm), , drop=FALSE]
if (!identical(as.character(geo_by_gsm$srr), as.character(manifest$SRR)))
  stop("Submitted manifest GSM-to-SRR pairing differs from pinned GEO; NO DESeq2")
ena_by_srr <- ena[match(geo_by_gsm$srr, ena$run_accession), , drop=FALSE]
if (anyNA(ena_by_srr$sample_accession) ||
    !identical(as.character(geo_by_gsm$biosample),
               as.character(ena_by_srr$sample_accession)))
  stop("Pinned GEO/ENA BioSample crosswalk mismatch; NO DESeq2")
if (any(!geo$D %in% c("0","1")) || any(!geo$H %in% c("0","1")) ||
    any(!geo$C %in% c("0","1")) ||
    !identical(as.character(geo$cell), paste0(geo$D, geo$H, geo$C)) ||
    any(table(factor(geo$cell, levels=c("000","001","010","011",
                                       "100","101","110","111"))) != 3L))
  stop("Pinned GEO nominal factorial cells inconsistent; NO DESeq2")
# The pinned sheet records nominal treatment labels, not validated chamber
# independence. The separate independent-unit evidence gate still applies.
ena_md5_values <- tolower(trimws(c(ena$fastq1_md5, ena$fastq2_md5)))
ena_keys <- c(paste(ena$run_accession, "R1", sep=":"),
              paste(ena$run_accession, "R2", sep=":"))
if (any(!grepl("^[0-9a-f]{32}$", ena_md5_values)) ||
    anyDuplicated(ena_keys))
  stop("Pinned ENA run/read MD5 entries invalid; NO DESeq2")
expected_ena_md5 <- setNames(ena_md5_values, ena_keys)
submitted_keys <- paste(fq$SRR, fq$read, sep=":")
if (!setequal(names(expected_ena_md5), submitted_keys) ||
    !identical(unname(expected_ena_md5[submitted_keys]), fq$ena_md5))
  stop("Local FASTQ manifest differs from pinned ENA source MD5; NO DESeq2")
# Only now incur the expensive local byte-level FASTQ MD5 verification.
observed_fastq_md5 <- unname(tools::md5sum(fq$fastq_path))
if (anyNA(observed_fastq_md5) ||
    !identical(tolower(observed_fastq_md5), fq$ena_md5))
  stop("One or more FASTQ byte-level MD5 values differ from ENA manifest; NO DESeq2")
# A match authenticates local bytes against supplied MD5s, not the independent
# authenticity or release provenance of the supplied ENA metadata.

# Matching file digests do not themselves prove that FASTA/GTF versions are compatible.
# Source release identifiers, licensing, gene ID namespace and counting policy
# require independent scientific verification beyond these mechanical checks.
# Refuse to mix a new analysis with stale files from a previous attempt.
# Do not create an output directory until every input gate and DESeq2 fit succeeds.
if (dir.exists(outdir) && length(list.files(outdir, all.files=TRUE, no..=TRUE)) > 0L)
  stop("Output directory is nonempty: refuse overwrite or mixed scientific results")
titles <- manifest$GEO_sample_title
replicate <- suppressWarnings(as.integer(sub(".*_biol_rep([123])$", "\\1", titles)))
if (anyNA(replicate) || !all(grepl("_biol_rep[123]$", titles)))
  stop("Invalid biological replicate labels")
D <- as.integer(grepl("drought", titles, fixed=TRUE))
H <- as.integer(grepl("elevated-temp", titles, fixed=TRUE))
C <- as.integer(grepl("elevated-CO2", titles, fixed=TRUE))
cell <- paste0(D,H,C)
cell_counts <- table(factor(cell, levels=c("000","001","010","011","100","101","110","111")))
if (any(cell_counts != 3L)) stop("Each of eight factorial cells must have exactly three libraries")
if (any(tapply(replicate, cell, function(z) !identical(sort(z), 1:3))))
  stop("Replicate labels 1,2,3 not found exactly once in every cell")
coldata <- data.frame(
  row.names=manifest$GSM, D=factor(D, levels=c(0,1)),
  H=factor(H, levels=c(0,1)), C=factor(C, levels=c(0,1)),
  GSM=manifest$GSM, SRR=manifest$SRR, replicate_label=replicate
)
design <- model.matrix(~ D*H*C, coldata)
if (qr(design)$rank != 8L || nrow(design)-qr(design)$rank != 16L)
  stop("Full factorial design is not identifiable")
raw <- read.delim(counts_file, check.names=FALSE, stringsAsFactors=FALSE, quote="")
if (ncol(raw) != 25L || anyDuplicated(names(raw))) stop("Expected gene_id plus 24 GSM columns")
gene <- as.character(raw[[1L]])
if (anyNA(gene) || any(!nzchar(gene)) || anyDuplicated(gene))
  stop("Gene identifiers must be nonempty, unique and nonmissing")
if (!setequal(names(raw)[-1L], manifest$GSM))
  stop("Count matrix columns must exactly match the 24 manifest GSM accessions")
mat <- as.matrix(raw[, manifest$GSM, drop=FALSE])
suppressWarnings(storage.mode(mat) <- "double")
if (any(!is.finite(mat)) || any(mat < 0) || any(mat != floor(mat)))
  stop("Counts must be finite, nonnegative, unnormalized INTEGERS; FPKM/TPM prohibited")
if (any(mat > .Machine$integer.max)) stop("Count exceeds integer range")
storage.mode(mat) <- "integer"; rownames(mat) <- gene
if (any(colSums(mat) == 0)) stop("Zero-library sample")
keep <- rowSums(mat >= 10L) >= 3L
if (sum(keep) < 100L) stop("Too few genes after prespecified filter")
dds <- DESeqDataSetFromMatrix(countData=mat[keep,,drop=FALSE],
                              colData=coldata, design=~ D*H*C)
dds <- DESeq(dds, parallel=FALSE)
names_available <- resultsNames(dds)
triple <- grep("D.*H.*C", names_available, value=TRUE)
if (length(triple) != 1L) stop(paste("Cannot uniquely identify D:H:C coefficient:",paste(names_available,collapse=", ")))
res <- results(dds, name=triple, alpha=0.05, independentFiltering=TRUE)
# The first output-side effect occurs only after successful primary checks and fit.
if (!dir.exists(outdir) && !dir.create(outdir, showWarnings=FALSE, recursive=TRUE))
  stop("Unable to create fresh analysis output directory")
tab <- data.frame(gene_id=rownames(res), as.data.frame(res), row.names=NULL)
tab <- tab[order(tab$padj, na.last=TRUE), , drop=FALSE]
write.csv(tab, file.path(outdir, "DHC_integer_count_DESeq2_all_genes.csv"), row.names=FALSE)
write.csv(data.frame(GSM=rownames(coldata), SRR=coldata$SRR, D=D, H=H, C=C,
                     replicate_label=replicate, library_size=colSums(mat)),
          file.path(outdir, "sample_design_and_library_sizes.csv"), row.names=FALSE)
writeLines(c(paste("Input:",normalizePath(counts_file)),
             paste("Gene rows before filter:",nrow(mat)),
             paste("Gene rows after filter:",sum(keep)),
             paste("Design rank:",qr(design)$rank),
             paste("Residual degrees of freedom:",nrow(design)-qr(design)$rank),
             paste("Interaction coefficient:",triple),
             paste("FDR<0.05:",sum(!is.na(res$padj)&res$padj<0.05)),
             paste("Unit-evidence SHA256:", prov$unit_evidence_sha256),
             paste("Counts SHA256:", prov$counts_sha256),
             paste("Reference FASTA SHA256 (local bytes verified):", prov$reference_fasta_sha256),
             paste("Annotation GTF SHA256 (local bytes verified):", prov$annotation_gtf_sha256),
             paste("Caveat: machine checks verify metadata structure and selected hashes, NOT truth of chamber assignment, reference identity or author approval."),
             paste("Caveat: human scientific review and publication authorization remain mandatory.")),
           file.path(outdir, "analysis_provenance.txt"))
capture.output(sessionInfo(), file=file.path(outdir, "R_session_info.txt"))
