#!/usr/bin/env Rscript
# GSE294406: prespecified 2x2x2 integer-count interaction analysis.
# INPUTS MUST BE RAW UNNORMALIZED INTEGER GENE COUNTS, NOT FPKM/TPM.
# Usage: Rscript full_factorial_integer_counts.R raw_gene_counts.tsv verified_manifest.csv output_dir
suppressPackageStartupMessages(library(DESeq2))
args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 3L) stop("Usage: Rscript full_factorial_integer_counts.R counts.tsv manifest.csv output_dir")
counts_file <- args[[1L]]; manifest_file <- args[[2L]]; outdir <- args[[3L]]
if (!file.exists(counts_file) || !file.exists(manifest_file)) stop("Input file not found")
dir.create(outdir, showWarnings=FALSE, recursive=TRUE)
manifest <- read.csv(manifest_file, check.names=FALSE, stringsAsFactors=FALSE)
required <- c("GSM","SRR","GEO_sample_title")
if (!all(required %in% names(manifest))) stop("Manifest lacks GSM/SRR/GEO_sample_title")
if (nrow(manifest) != 24L || anyDuplicated(manifest$GSM) || anyDuplicated(manifest$SRR))
  stop("Expected exactly 24 unique GSM/SRR libraries")
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
             paste("Caveat: inferential analysis requires biological/technical QC, annotation and independent novelty audit.")),
           file.path(outdir, "analysis_provenance.txt"))
capture.output(sessionInfo(), file=file.path(outdir, "R_session_info.txt"))
