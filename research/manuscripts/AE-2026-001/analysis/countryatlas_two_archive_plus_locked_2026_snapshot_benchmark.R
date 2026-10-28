# AE-2026-001: historical countryatlas API releases versus exact local 2026 WDI snapshot.
# Prepared 2026-10-27; source-identity gate strengthened C49 2026-10-28. NOT EXECUTED. Not a claim of byte-identical archive equivalence.
# This removes the unjustified requirement that a 2026-10 API vintage must exist.
#
# Usage:
# AE_HISTORICAL_VINTAGES="2024-10,2025-10" \
# AE_COHORT_FILE="/path/to/source_verified_155_iso3c.csv" \
# Rscript countryatlas_two_archive_plus_locked_2026_snapshot_benchmark.R output.csv
#
# A cohort file must be independently derived from the *three* verified source
# releases and contain exactly 155 unique ISO3 keys. Never invent a cohort.
# Requires countryatlas 3.0.0 and digest installed, plus API access.

stopifnot(requireNamespace("countryatlas", quietly=TRUE))
stopifnot(as.character(utils::packageVersion("countryatlas"))=="3.0.0")
stopifnot(requireNamespace("digest", quietly=TRUE))
args <- commandArgs(trailingOnly=TRUE)
if(length(args)!=1L || file.exists(args[1])) stop("Exactly one NEW output CSV path required")
out_path <- args[1]
v <- trimws(strsplit(Sys.getenv("AE_HISTORICAL_VINTAGES",""),",",fixed=TRUE)[[1]])
if(length(v)!=2L || anyDuplicated(v) || any(!grepl("^20[0-9]{2}-[0-9]{2}$",v)))
  stop("Exactly two distinct pinned historical API vintages required")
cohort_file <- Sys.getenv("AE_COHORT_FILE","")
if(!file.exists(cohort_file)) stop("Missing independently verified 155-country cohort CSV")
# C49 source-identity hardening: cohort input must be frozen by an independently
# reviewed SHA256; this checksum alone does NOT establish scientific validity.
cohort_expected_sha <- tolower(Sys.getenv("AE_COHORT_SHA256", ""))
if(!grepl("^[0-9a-f]{64}$", cohort_expected_sha))
  stop("AE_COHORT_SHA256 must pin independently reviewed 155-country cohort; NO BENCHMARK")
if(!identical(digest::digest(cohort_file, algo="sha256", file=TRUE, serialize=FALSE),
              cohort_expected_sha))
  stop("Cohort SHA256 mismatch; NO BENCHMARK")
cohort <- utils::read.csv(cohort_file,stringsAsFactors=FALSE)
if(!"iso3c" %in% names(cohort) || anyNA(cohort$iso3c))
  stop("Cohort CSV must contain nonmissing iso3c")
ids <- toupper(trimws(as.character(cohort$iso3c)))
if(length(ids)!=155L || anyDuplicated(ids) || any(!grepl("^[A-Z]{3}$",ids)))
  stop("Cohort must contain exactly 155 distinct ISO3-like keys")

snapshot <- Sys.getenv("AE_2026_SNAPSHOT_FILE", "")
if(!nzchar(snapshot)) stop("Set AE_2026_SNAPSHOT_FILE to the committed source-locked CSV path")
if(!file.exists(snapshot)) stop("Missing committed source-locked 2026 snapshot")
expected_sha <- "715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169"
actual_sha <- digest::digest(snapshot,algo="sha256",file=TRUE,serialize=FALSE)
if(!identical(actual_sha,expected_sha)) stop("2026 CSV SHA256 mismatch; refuse to continue")
d26 <- utils::read.csv(snapshot,stringsAsFactors=FALSE,check.names=FALSE)
if(nrow(d26)!=217L || anyDuplicated(d26$country_iso3))
  stop("Unexpected 2026 snapshot shape or duplicate keys")
col0 <- "ag_value_added_per_worker_2000_constant2015usd"
col1 <- "ag_value_added_per_worker_2019_constant2015usd"
if(!all(c("country_iso3",col0,col1) %in% names(d26)))
  stop("Unexpected 2026 indicator columns")
d26 <- d26[match(ids,d26$country_iso3),]
if(anyNA(d26$country_iso3)) stop("Verified 155 cohort missing from 2026 snapshot")
x0 <- suppressWarnings(as.numeric(d26[[col0]]))
x1 <- suppressWarnings(as.numeric(d26[[col1]]))
if(any(!is.finite(x0)|x0<=0|!is.finite(x1)|x1<=0))
  stop("Missing/nonpositive 2026 endpoints in independently supplied cohort")
g26 <- 100*(log(x1)-log(x0))/19

available <- countryatlas::wdi_vintages()
if(!all(c("vintage","id","label") %in% names(available)))
  stop("Unexpected archive metadata; do not infer release identity")
if(!all(v %in% available$vintage))
  stop(paste("Historical API release absent:",paste(setdiff(v,available$vintage),collapse=",")))
# A human-readable month is not by itself the API source-57 release identity.
# Verify the World Bank archive's exact YYYYMM IDs before comparing levels.
selected <- available[match(v, available$vintage), , drop=FALSE]
if(!identical(as.character(selected$id), gsub("-", "", v, fixed=TRUE)))
  stop("Historical WDI archive release ID mismatch; NO BENCHMARK")
fetch_one <- function(y) {
  # Fail closed on API warnings (including countryatlas_unit_mismatch,
  # missing release/indicator coverage or partial observations).
  z <- withCallingHandlers(
    countryatlas::compare_vintages("NV.AGR.EMPL.KD",vintages=v,year=y,countries=ids),
    warning=function(w) stop(paste("Archive/API warning; NO BENCHMARK:",
                                   conditionMessage(w))))
  need <- c("iso3c","vintage","value")
  if(!all(need %in% names(z))) stop("Unexpected compare_vintages columns")
  z <- as.data.frame(z[,need,drop=FALSE])
  z$iso3c <- toupper(as.character(z$iso3c))
  z$vintage <- as.character(z$vintage)
  z$value <- suppressWarnings(as.numeric(z$value))
  z <- z[z$iso3c %in% ids & z$vintage %in% v,,drop=FALSE]
  if(anyDuplicated(z[,c("iso3c","vintage")]))
    stop("Duplicate ISO3-release rows; no silent aggregation")
  names(z)[3] <- paste0("value_",y)
  z
}
z <- merge(fetch_one(2000L),fetch_one(2019L),by=c("iso3c","vintage"))
if(nrow(z)!=310L || any(!is.finite(z$value_2000)|z$value_2000<=0|
                        !is.finite(z$value_2019)|z$value_2019<=0))
  stop("Expected all 155 x 2 historical archive endpoint pairs")
z$g <- 100*(log(z$value_2019)-log(z$value_2000))/19
wide <- reshape(z[,c("iso3c","vintage","g")],
                idvar="iso3c",timevar="vintage",direction="wide")
wide <- wide[match(ids,wide$iso3c),]
if(nrow(wide)!=155L || anyNA(wide$iso3c)) stop("Historical cohort mismatch")
for(k in v) if(any(!is.finite(wide[[paste0("g.",k)]]))) stop("Missing historical growth")
wide$g_2026_source_locked <- g26
wide$revision_old_to_new <- wide[[paste0("g.",v[2])]]-wide[[paste0("g.",v[1])]]
wide$revision_old_to_2026 <- g26-wide[[paste0("g.",v[1])]]
wide$revision_new_to_2026 <- g26-wide[[paste0("g.",v[2])]]
utils::write.csv(wide,out_path,row.names=FALSE,na="")
cat("EXPLORATORY benchmark completed; API-vs-ZIP historical equivalence NOT VERIFIED\n")
cat("2026 locked CSV SHA256:",actual_sha,"; historical API releases:",paste(v,collapse=", "), "\n")
cat("Matched country rows:",nrow(wide),"\n")
