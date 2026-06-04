#!/usr/bin/env Rscript
# 04_ngraph_graph_of_graphs.R -- compare site graphs and build a super-graph.

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
    return(rep(0, k))
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

site_summary <- fread(file.path(NG$tables, "ngraph_site_graph_summary.tsv"))
methods <- unique(site_summary$method_suffix)

all_sim <- list()
for (method_suffix in methods) {
  graph_files <- file.path(NG$graphs, paste0("ngraph_", NG_PARAMS$all_cores, "_", method_suffix, ".rds"))
  names(graph_files) <- NG_PARAMS$all_cores
  graph_files <- graph_files[file.exists(graph_files)]
  if (length(graph_files) < 2) {
    ng_log(LOG, "Skipping graph-of-graphs for ", method_suffix, ": fewer than two site graphs")
    next
  }

  graphs <- lapply(graph_files, readRDS)
  edge_sets <- lapply(names(graph_files), function(core_id) {
    fread(file.path(NG$graphs, paste0("ngraph_edges_", core_id, "_", method_suffix, ".tsv")))
  })
  names(edge_sets) <- names(graph_files)
  edge_sets <- lapply(edge_sets, edge_key)

  signatures <- lapply(graphs, laplacian_signature, k = NG_PARAMS$spectral_k)
  pairs <- CJ(core_a = names(graphs), core_b = names(graphs))[core_a < core_b]
  sim <- rbindlist(lapply(seq_len(nrow(pairs)), function(i) {
    a <- pairs$core_a[i]
    b <- pairs$core_b[i]
    inter <- length(intersect(edge_sets[[a]], edge_sets[[b]]))
    uni <- length(union(edge_sets[[a]], edge_sets[[b]]))
    jaccard <- ifelse(uni == 0, NA_real_, inter / uni)
    spectral_distance <- sqrt(sum((signatures[[a]] - signatures[[b]])^2))
    data.table(
      method = method_suffix,
      core_a = a,
      core_b = b,
      edge_intersection = inter,
      edge_union = uni,
      edge_jaccard = jaccard,
      spectral_distance = spectral_distance,
      spectral_similarity = 1 / (1 + spectral_distance)
    )
  }))

  sim[, super_weight := rowMeans(cbind(edge_jaccard, spectral_similarity), na.rm = TRUE)]
  all_sim[[length(all_sim) + 1]] <- sim

  super_edges <- data.table(
    from = sim$core_a,
    to = sim$core_b,
    method = method_suffix,
    weight = sim$super_weight,
    edge_jaccard = sim$edge_jaccard,
    spectral_similarity = sim$spectral_similarity
  )
  super_nodes <- data.table(name = names(graphs), core = names(graphs), method = method_suffix)
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

  write_graph(super_g, file.path(NG$graphs, paste0("ngraph_super_graph_", method_suffix, ".graphml")), format = "graphml")
  saveRDS(super_g, file.path(NG$graphs, paste0("ngraph_super_graph_", method_suffix, ".rds")))
  fwrite(as.data.table(vertex_attr(super_g)), file.path(NG$tables, paste0("ngraph_super_graph_nodes_", method_suffix, ".tsv")), sep = "\t")
  fwrite(super_edges, file.path(NG$tables, paste0("ngraph_super_graph_edges_", method_suffix, ".tsv")), sep = "\t")

  if (method_suffix == "spearman") {
    write_graph(super_g, file.path(NG$graphs, "ngraph_super_graph.graphml"), format = "graphml")
    saveRDS(super_g, file.path(NG$graphs, "ngraph_super_graph.rds"))
    fwrite(as.data.table(vertex_attr(super_g)), file.path(NG$tables, "ngraph_super_graph_nodes.tsv"), sep = "\t")
    fwrite(super_edges, file.path(NG$tables, "ngraph_super_graph_edges.tsv"), sep = "\t")
  }

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
    labs(title = paste("NGraph graph-of-graphs:", method_suffix), linewidth = "Similarity", fill = "Leiden") +
    theme_void(base_size = 11)
  ggsave(file.path(NG$figures, paste0("ngraph_super_graph_", method_suffix, ".png")), p, width = 7, height = 5.2, dpi = 180)
  if (method_suffix == "spearman") {
    ggsave(file.path(NG$figures, "ngraph_super_graph.png"), p, width = 7, height = 5.2, dpi = 180)
  }
}

sim <- rbindlist(all_sim, fill = TRUE)
fwrite(sim, file.path(NG$tables, "ngraph_graph_similarity.tsv"), sep = "\t")

report <- file.path(NG$reports, "NGRAPH_GRAPH_OF_GRAPHS_REPORT.md")
sink(report)
cat("# NGraph Graph-of-Graphs Report\n\n")
cat("- Generated: ", format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"), "\n", sep = "")
cat("- Nodes: site-specific taxon graphs.\n")
cat("- Edge weight: mean of edge-Jaccard similarity and normalized-Laplacian spectral-quantile similarity.\n")
cat("- Methods compared: `", paste(methods, collapse = "`, `"), "`.\n\n", sep = "")
cat("## Similarity Table\n\n")
cat(ng_md_table(sim))
cat("\n## Outputs\n\n")
cat("- `results/ngraph/graphs/ngraph_super_graph_<method>.graphml`\n")
cat("- `results/ngraph/tables/ngraph_graph_similarity.tsv`\n")
cat("- `results/ngraph/figures/ngraph_super_graph_<method>.png`\n")
sink()

ng_log(LOG, "Method Validated: graph-of-graphs figure and GraphML written")
ng_log(LOG, "Complete")
