suppressPackageStartupMessages({library(data.table); library(igraph)})

# Load only pure helpers, avoiding execution of numbered pipeline entrypoints.
load_helpers <- function(path, names) {
  for (expr in parse(path)) {
    if (is.call(expr) && identical(expr[[1]], as.name("<-")) &&
        is.symbol(expr[[2]]) && as.character(expr[[2]]) %in% names) eval(expr, envir = .GlobalEnv)
  }
}
load_helpers("scripts/03_ngraph_site_graphs.R", c("local_taxon_eligibility", "build_correlation_edges"))
load_helpers("scripts/04_ngraph_graph_of_graphs.R", c("edge_key", "laplacian_signature", "compare_graph_pair"))

raw <- rbind(a = 1:10, b = 11:20, absent = rep(0, 10),
             sparse = c(1, 2, rep(0, 8)), boundary = c(1:5, rep(0, 5)), flat_raw = rep(3, 10))
colnames(raw) <- paste0("s", 1:10)
logs <- log(raw + 0.5)
clr <- t(sweep(logs, 2, colMeans(logs), "-"))
stopifnot(var(clr[, "absent"]) > 0) # Denominator-induced variance must not establish support.
e <- local_taxon_eligibility(clr, raw, colnames(raw), "fixture")
stopifnot(!e[taxon == "absent", eligible], !e[taxon == "sparse", eligible],
          e[taxon == "boundary", eligible], e[taxon == "flat_raw", constant_raw_abundance])
edges <- build_correlation_edges(clr[, e[eligible == TRUE, taxon]], 10, "pearson", "pearson", "pearson", .55)
stopifnot(!any(edges$from %in% c("absent", "sparse")), !any(edges$to %in% c("absent", "sparse")))
fraction <- local_taxon_eligibility(clr, raw, colnames(raw), "fixture", min_positive = 5, min_fraction = .6)
stopifnot(!fraction[taxon == "boundary", eligible], all(fraction$min_positive_samples == 6))
bad <- clr; bad[, "a"] <- 0; bad[1, "b"] <- NA_real_
e2 <- local_taxon_eligibility(bad, raw, colnames(raw), "fixture")
stopifnot(e2[taxon == "a", exclusion_reason] == "constant_clr_profile",
          e2[taxon == "b", exclusion_reason] == "nonfinite_profile")

ga <- graph_from_data_frame(data.frame(from = c("a", "a"), to = c("b", "c"), weight = 1), directed = FALSE)
gb <- graph_from_data_frame(data.frame(from = c("a", "b"), to = c("b", "d"), weight = 1), directed = FALSE)
pair <- compare_graph_pair(ga, gb, 5)
stopifnot(pair$shared_eligible_nodes == 2, pair$edge_jaccard == 1,
          abs(pair$full_edge_jaccard - 1/3) < 1e-10, pair$spectral_similarity == 1)
empty <- make_empty_graph(2, directed = FALSE); V(empty)$name <- c("a", "b")
none <- compare_graph_pair(empty, empty, 5)
stopifnot(is.na(none$edge_jaccard), is.na(none$spectral_similarity),
          is.na(none$full_spectral_similarity), none$comparison_status == "insufficient_shared_edge_support")
disjoint <- gb; V(disjoint)$name <- paste0("different_", V(disjoint)$name)
stopifnot(is.na(compare_graph_pair(ga, disjoint, 5)$spectral_similarity))
cat("PASS: local positivity gates, CLR-denominator artifacts, variance checks, shared-universe comparisons, empty/disjoint graphs\n")
