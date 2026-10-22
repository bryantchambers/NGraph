#!/usr/bin/env Rscript
# 04_ngraph_graph_of_graphs.R -- compare site graphs and build threshold-specific super-graphs.

suppressPackageStartupMessages({
  library(data.table)
  library(igraph)
  library(ggplot2)
})

source("config_ngraph.R")
set.seed(NG_PARAMS$seed)

LOG <- ng_log_path("04_ngraph_graph_of_graphs")
ng_start_log(LOG)
ng_log(LOG, "Starting graph-of-graphs construction")

edge_key <- function(edges) {
  if (nrow(edges) == 0) return(character())
  a <- pmin(edges$from, edges$to)
  b <- pmax(edges$from, edges$to)
  paste(a, b, sep = "--")
}

laplacian_signature <- function(g, k) {
  if (vcount(g) < 2 || ecount(g) == 0) {
    return(rep(NA_real_, k))
  }
  adj <- as.matrix(as_adjacency_matrix(g, attr = "weight", sparse = FALSE))
  deg <- rowSums(adj)
  inv_sqrt_deg <- ifelse(deg > 0, 1 / sqrt(deg), 0)
  norm_adj <- (inv_sqrt_deg * adj) * rep(inv_sqrt_deg, each = nrow(adj))
  lap <- diag(1, nrow = nrow(adj)) - norm_adj
  diag(lap)[deg == 0] <- 0
  ev <- sort(Re(eigen(lap, symmetric = TRUE, only.values = TRUE)$values))
  as.numeric(quantile(ev, probs = seq(0, 1, length.out = k), na.rm = TRUE, names = FALSE, type = 7))
}

compare_graph_pair <- function(g_a, g_b, k) {
  shared <- intersect(V(g_a)$name, V(g_b)$name)
  full_a <- edge_key(as_data_frame(g_a, what = "edges"))
  full_b <- edge_key(as_data_frame(g_b, what = "edges"))
  full_union <- length(union(full_a, full_b))
  full_jaccard <- if (full_union > 0) length(intersect(full_a, full_b)) / full_union else NA_real_
  a <- induced_subgraph(g_a, vids = shared)
  b <- induced_subgraph(g_b, vids = shared)
  ea <- edge_key(as_data_frame(a, what = "edges"))
  eb <- edge_key(as_data_frame(b, what = "edges"))
  inter <- length(intersect(ea, eb)); uni <- length(union(ea, eb))
  comparable <- length(shared) >= 2L && ecount(a) > 0L && ecount(b) > 0L
  jaccard <- if (comparable) inter / uni else NA_real_
  spectral_distance <- if (comparable) sqrt(sum((laplacian_signature(a, k) - laplacian_signature(b, k))^2)) else NA_real_
  full_distance <- sqrt(sum((laplacian_signature(g_a, k) - laplacian_signature(g_b, k))^2))
  data.table(nodes_a = vcount(g_a), nodes_b = vcount(g_b), shared_eligible_nodes = length(shared),
    eligible_node_jaccard = if (length(union(V(g_a)$name, V(g_b)$name)) > 0)
      length(shared) / length(union(V(g_a)$name, V(g_b)$name)) else NA_real_,
    shared_edges_a = ecount(a), shared_edges_b = ecount(b),
    shared_edge_fraction_a = if (ecount(g_a) > 0) ecount(a) / ecount(g_a) else NA_real_,
    shared_edge_fraction_b = if (ecount(g_b) > 0) ecount(b) / ecount(g_b) else NA_real_,
    edge_intersection = inter, edge_union = uni, edge_jaccard = jaccard,
    spectral_distance = spectral_distance, spectral_similarity = 1 / (1 + spectral_distance),
    full_edge_jaccard = full_jaccard, full_spectral_distance = full_distance,
    full_spectral_similarity = 1 / (1 + full_distance),
    comparison_status = if (comparable) "shared_eligible_nodes" else "insufficient_shared_edge_support")
}

all_sim <- list()
for (thr in NG_PARAMS$prevalence_thresholds) {
  dirs <- ng_threshold_dirs(thr)
  site_summary <- fread(file.path(dirs$tables, "ngraph_site_graph_summary.tsv"))
  methods <- unique(site_summary$method_suffix)

  sim_by_threshold <- list()
  for (method_suffix in methods) {
    graph_files <- file.path(dirs$graphs, paste0("ngraph_", NG_PARAMS$all_cores, "_", method_suffix, ".rds"))
    names(graph_files) <- NG_PARAMS$all_cores
    graph_files <- graph_files[file.exists(graph_files)]
    if (length(graph_files) < 2) {
      ng_log(LOG, "Threshold ", thr, " skipping graph-of-graphs for ", method_suffix, ": fewer than two site graphs")
      next
    }

    graphs <- lapply(graph_files, readRDS)
    pairs <- CJ(core_a = names(graphs), core_b = names(graphs))[core_a < core_b]
    sim <- rbindlist(lapply(seq_len(nrow(pairs)), function(i) {
      a <- pairs$core_a[i]
      b <- pairs$core_b[i]
      cbind(data.table(
        threshold = thr,
        method = method_suffix,
        core_a = a,
        core_b = b), compare_graph_pair(graphs[[a]], graphs[[b]], NG_PARAMS$spectral_k))
    }))
    sim[, super_weight := rowMeans(cbind(edge_jaccard, spectral_similarity), na.rm = TRUE)]
    sim[!is.finite(super_weight), super_weight := NA_real_]
    sim_by_threshold[[length(sim_by_threshold) + 1]] <- sim

    super_edges <- data.table(
      threshold = thr,
      from = sim$core_a,
      to = sim$core_b,
      method = method_suffix,
      weight = sim$super_weight,
      edge_jaccard = sim$edge_jaccard,
      spectral_similarity = sim$spectral_similarity
    )
    super_edges <- super_edges[is.finite(weight) & weight > 0]
    super_edge_cols <- c("from", "to", setdiff(names(super_edges), c("from", "to")))
    super_edges <- super_edges[, ..super_edge_cols]
    super_nodes <- data.table(name = names(graphs), core = names(graphs), method = method_suffix, threshold = thr)
    super_g <- graph_from_data_frame(super_edges, directed = FALSE, vertices = super_nodes)
    E(super_g)$weight <- super_edges$weight
    E(super_g)$edge_jaccard <- super_edges$edge_jaccard
    E(super_g)$spectral_similarity <- super_edges$spectral_similarity

    if ("cluster_leiden" %in% getNamespaceExports("igraph") && ecount(super_g) > 0) {
      cl <- cluster_leiden(super_g, objective_function = "modularity", weights = E(super_g)$weight)
      V(super_g)$leiden_module <- paste0("S", membership(cl))
    } else {
      V(super_g)$leiden_module <- "S1"
    }

    write_graph(super_g, file.path(dirs$graphs, paste0("ngraph_super_graph_", method_suffix, ".graphml")), format = "graphml")
    saveRDS(super_g, file.path(dirs$graphs, paste0("ngraph_super_graph_", method_suffix, ".rds")))
    fwrite(as.data.table(vertex_attr(super_g)), file.path(dirs$tables, paste0("ngraph_super_graph_nodes_", method_suffix, ".tsv")), sep = "\t")
    fwrite(super_edges, file.path(dirs$tables, paste0("ngraph_super_graph_edges_", method_suffix, ".tsv")), sep = "\t")

    layout_dt <- as.data.table(layout_with_fr(super_g, weights = E(super_g)$weight))
    setnames(layout_dt, c("x", "y"))
    layout_dt[, core := V(super_g)$name]
    node_dt <- merge(layout_dt, as.data.table(vertex_attr(super_g)), by.x = "core", by.y = "name", all.x = TRUE)
    edge_plot <- merge(super_edges, layout_dt, by.x = "from", by.y = "core")
    edge_plot <- merge(edge_plot, layout_dt, by.x = "to", by.y = "core", suffixes = c("_from", "_to"))

    p <- ggplot() +
      geom_segment(data = edge_plot, aes(x = x_from, y = y_from, xend = x_to, yend = y_to, linewidth = weight), alpha = 0.65, color = "#355c7d") +
      geom_point(data = node_dt, aes(x, y, fill = leiden_module), shape = 21, size = 9, color = "black") +
      geom_text(data = node_dt, aes(x, y, label = core), size = 3.4) +
      scale_linewidth(range = c(0.4, 2.8)) +
      labs(title = paste("NGraph graph-of-graphs:", method_suffix, "prevalence", thr), linewidth = "Similarity", fill = "Leiden") +
      theme_void(base_size = 11)
    ggsave(file.path(dirs$figures, paste0("ngraph_super_graph_", method_suffix, ".png")), p, width = 7, height = 5.2, dpi = 180)
  }

  sim_dt <- rbindlist(sim_by_threshold, fill = TRUE)
  fwrite(sim_dt, file.path(dirs$tables, "ngraph_graph_similarity.tsv"), sep = "\t")
  all_sim[[length(all_sim) + 1]] <- sim_dt

  report <- file.path(dirs$reports, "NGRAPH_GRAPH_OF_GRAPHS_REPORT.md")
  sink(report)
  cat("# NGraph Graph-of-Graphs Report\n\n")
  cat("- Generated: ", format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"), "\n", sep = "")
  cat("- Branch: `", NG$branch, "`\n", sep = "")
  cat("- Prevalence threshold: `", thr, "`\n", sep = "")
    cat("- Edge weight: mean of edge-Jaccard and normalized-Laplacian spectral-quantile similarity on pairwise shared eligible taxa. Empty comparisons remain unavailable; full-set metrics and overlap coverage are diagnostics.\n\n")
  cat(ng_md_table(sim_dt))
  sink()
}

fwrite(rbindlist(all_sim, fill = TRUE), file.path(NG$tables, "ngraph_all_threshold_graph_similarity.tsv"), sep = "\t")
ng_log(LOG, "Method Validated: threshold-specific graph-of-graphs outputs written")
ng_log(LOG, "Complete")
