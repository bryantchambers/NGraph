# Sample-centric physical-depth matching. No age-only join or extrapolation.
# The caller must provide data.table and a core_to_site alias function.
match_proxy_depth <- function(proxy, sample_key, value_cols, source_table, source_file,
                              tolerance_cm = 0.5, gap_factor = 3) {
  proxy <- copy(proxy)
  proxy[, source_row := seq_len(.N)]
  proxy[, physical_core := core_to_site(core)]
  samples <- copy(sample_key)
  samples[, physical_core := core_to_site(core)]
  raw <- melt(proxy, id.vars = intersect(c("source_row", "physical_core", "core", "depth_in_core_cm", "y_bp"), names(proxy)),
              measure.vars = intersect(value_cols, names(proxy)), variable.name = "variable", value.name = "value", variable.factor = FALSE)
  raw[, value := as.numeric(value)]
  raw[, source_observation_id := paste("proxy_source", source_table, source_row, variable, sep = ":")]
  raw[, `:=`(source_table = source_table, source_file = source_file)]
  values <- list(); coverage <- list()
  for (physical in unique(samples$physical_core)) {
    sam <- samples[physical_core == physical]
    for (variable_name in intersect(value_cols, names(proxy))) {
      input <- raw[physical_core == physical & variable == variable_name & is.finite(depth_in_core_cm) & is.finite(value)]
      grid <- input[, .(value = mean(value),
                        source_ids = paste(source_observation_id, collapse = ","),
                        source_rows = paste(source_row, collapse = ","),
                        source_min = min(value), source_max = max(value)), by = depth_in_core_cm][order(depth_in_core_cm)]
      median_gap <- if (nrow(grid) > 1) median(diff(grid$depth_in_core_cm)) else NA_real_
      for (i in seq_len(nrow(sam))) {
        sample <- sam[i]; depth <- sample$depth_in_core_cm
        status <- "no_finite_proxy_values"; left <- right <- NA_integer_; fraction <- 0
        delta <- width <- NA_real_; result <- NA_real_; tie <- FALSE
        if (!is.finite(depth)) status <- "missing_sample_depth"
        else if (nrow(grid)) {
          distances <- abs(grid$depth_in_core_cm - depth)
          nearest <- which.min(distances)
          delta <- distances[nearest]
          if (delta <= tolerance_cm + 1e-10) {
            left <- right <- nearest; result <- grid$value[nearest]
            width <- 0; status <- if (delta < 1e-10) "exact_depth" else "within_depth_tolerance"
            tie <- sum(abs(distances - delta) < 1e-10) > 1
          } else {
            below <- which(grid$depth_in_core_cm < depth); above <- which(grid$depth_in_core_cm > depth)
            if (!length(below) || !length(above)) status <- "outside_proxy_range"
            else if (grepl("(^|_)count$", variable_name)) status <- "discrete_variable_no_interpolation"
            else {
              left <- max(below); right <- min(above)
              width <- grid$depth_in_core_cm[right] - grid$depth_in_core_cm[left]
              fraction <- (depth - grid$depth_in_core_cm[left]) / width
              result <- (1 - fraction) * grid$value[left] + fraction * grid$value[right]
              status <- "linear_depth_interpolation"
            }
          }
        }
        covered <- is.finite(result)
        coverage[[length(coverage) + 1L]] <- data.table(source_table, source_file, sample_id = sample$sample_id,
          core = sample$core, physical_core = physical, variable = variable_name,
          sample_depth_cm = depth, status, matched = covered)
        if (!covered) next
        values[[length(values) + 1L]] <- data.table(sample_id = sample$sample_id, site_id = sample$site_id,
          core = sample$core, physical_core = physical, matched_core = sample$core,
          y_bp = sample$y_bp, age_kyr = sample$age_kyr, depth_in_core_cm = depth,
          variable = variable_name, value = result, dataset_id = paste0("dataset:", source_table),
          source_table, source_file, match_method = status, match_delta = delta,
          depth_left_cm = grid$depth_in_core_cm[left], depth_right_cm = grid$depth_in_core_cm[right],
          value_left = grid$value[left], value_right = grid$value[right], interpolation_fraction = fraction,
          bracket_width_cm = width, median_proxy_spacing_cm = median_gap,
          large_gap_threshold_cm = gap_factor * median_gap,
          large_gap = is.finite(width) && is.finite(median_gap) && width > gap_factor * median_gap,
          depth_tie = tie, duplicate_depth_conflict = grid$source_min[left] != grid$source_max[left] || grid$source_min[right] != grid$source_max[right],
          source_observation_ids_left = grid$source_ids[left], source_observation_ids_right = grid$source_ids[right],
          source_rows_left = grid$source_rows[left], source_rows_right = grid$source_rows[right])
      }
    }
  }
  list(values = rbindlist(values, fill = TRUE), coverage = rbindlist(coverage, fill = TRUE), source_observations = raw)
}
