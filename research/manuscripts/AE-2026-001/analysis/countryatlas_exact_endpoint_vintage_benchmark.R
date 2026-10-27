# AE-2026-001: exact-endpoint countryatlas benchmark
# Prepared 2026-10-27. NOT EXECUTED or verified against 2024/2025 ZIPs.
# Does not treat the live "current" WDI release as the dated 2026 snapshot.
#
# Usage (after human verification of archive identity and unit compatibility):
#   AE_VINTAGES="2024-10,2025-10,2026-10" \
#   AE_COHORT_FILE="/path/to/verified_155_iso3c.csv" \
#   Rscript countryatlas_exact_endpoint_vintage_benchmark.R output.csv
#
# The cohort file must contain exactly 155 unique ISO3 codes in column iso3c,
# verified against the 2024/2025/2026 source-locked analysis.
# An API release ID is NOT proven byte-equivalent to a ZIP archive by matching
# its month. Do not label results an exact replication until source identity is
# separately reconciled with the source manifest and the source unit.

stopifnot(requireNamespace("countryatlas", quietly = TRUE))
stopifnot(as.character(utils::packageVersion("countryatlas")) == "3.0.0")
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1L) stop("Supply output CSV path as sole argument")
out_path <- args[[1]]
if (file.exists(out_path)) stop("Refusing to overwrite an existing benchmark file")
raw_v <- Sys.getenv("AE_VINTAGES", "")
v <- trimws(strsplit(raw_v, ",", fixed = TRUE)[[1]])
if (length(v) != 3L || any(!grepl("^20[0-9]{2}-[0-9]{2}$", v)) ||
    anyDuplicated(v) || any(v == "current"))
  stop("Supply three distinct pinned YYYY-MM releases; no current alias")
cohort_path <- Sys.getenv("AE_COHORT_FILE", "")
if (!nzchar(cohort_path) || !file.exists(cohort_path))
  stop("Supply an independently verified fixed 155-ISO3 cohort CSV")
cohort <- utils::read.csv(cohort_path, stringsAsFactors = FALSE)
if (!"iso3c" %in% names(cohort)) stop("Cohort CSV needs iso3c column")
ids <- sort(unique(toupper(trimws(as.character(cohort$iso3c)))))
if (length(ids) != 155L || any(!grepl("^[A-Z]{3}$", ids)))
  stop("Expected 155 distinct valid-looking ISO3 identifiers")
available <- countryatlas::wdi_vintages()
if (!all(c("vintage", "id", "label") %in% names(available)))
  stop("Unexpected WDI release metadata shape")
if (!all(v %in% available$vintage))
  stop(paste("Requested release not available; no substitute allowed:",
             paste(setdiff(v, available$vintage), collapse = ",")))
# Both years are queried explicitly; compare_vintages(year=NULL) is prohibited.
fetch_one <- function(y) {
  z <- countryatlas::compare_vintages("NV.AGR.EMPL.KD",
                                      vintages = v, year = y,
                                      countries = ids)
  need <- c("iso3c", "vintage", "value")
  if (!all(need %in% names(z))) stop("Unexpected compare_vintages columns")
  z <- as.data.frame(z[, need, drop = FALSE])
  z$iso3c <- toupper(as.character(z$iso3c))
  z$vintage <- as.character(z$vintage)
  z$value <- as.numeric(z$value)
  z <- z[z$iso3c %in% ids & z$vintage %in% v, , drop = FALSE]
  if (anyDuplicated(z[, c("iso3c", "vintage")]))
    stop("Duplicate country-vintage keys: cannot silently aggregate")
  names(z)[names(z) == "value"] <- paste0("value_", y)
  z
}
y0 <- fetch_one(2000L)
y1 <- fetch_one(2019L)
d <- merge(y0, y1, by = c("iso3c", "vintage"), all = FALSE)
d <- d[is.finite(d$value_2000) & d$value_2000 > 0 &
       is.finite(d$value_2019) & d$value_2019 > 0, , drop = FALSE]
if (nrow(d) != 155L * 3L)
  stop(paste("Incomplete endpoint coverage: observed", nrow(d),
             "of expected 465 country-vintage rows; do not impute"))
if (any(table(d$iso3c) != 3L) || any(table(d$vintage) != 155L))
  stop("Not the same 155 economies in every release")
d$growth_log_pp_year <- 100 * (log(d$value_2019) -
                              log(d$value_2000)) / 19
# Stable cross-vintage paired output; all three vintages required per country.
wide <- reshape(d[, c("iso3c", "vintage", "growth_log_pp_year")],
                idvar = "iso3c", timevar = "vintage", direction = "wide")
wide <- wide[order(wide$iso3c), , drop = FALSE]
for (name in v) {
  col <- paste0("growth_log_pp_year.", name)
  if (!col %in% names(wide) || any(!is.finite(wide[[col]])))
    stop("Unmatched country growth: stop rather than fabricate")
}
wide$revision_1_to_2 <- wide[[paste0("growth_log_pp_year.", v[2])]] -
                         wide[[paste0("growth_log_pp_year.", v[1])]]
wide$revision_2_to_3 <- wide[[paste0("growth_log_pp_year.", v[3])]] -
                         wide[[paste0("growth_log_pp_year.", v[2])]]
wide$revision_1_to_3 <- wide[[paste0("growth_log_pp_year.", v[3])]] -
                         wide[[paste0("growth_log_pp_year.", v[1])]]
# Source provenance and unit/series-label checks must be appended externally.
# These outputs are a benchmark of API archives, not automatically a
# byte-identical comparison with original downloaded WDI ZIP files.
utils::write.csv(wide, out_path, row.names = FALSE, na = "")
cat("EXPLORATORY API BENCHMARK ONLY; identity to original ZIPs UNVERIFIED\n")
cat("Release IDs:", paste(v, collapse = ", "), "\n")
cat("Rows:", nrow(wide), "\n")
