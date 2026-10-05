# Permissive Hybrid `prev_10` Exploration

## Rule

This exploratory branch uses a permissive presence rule for matrix construction:

1. keep only rows with `is_dmg == "Damaged"`
2. require `n_reads >= 100`
3. define abundance per row as `tax_abund_tad` when `tax_abund_tad > 0`, otherwise `tax_abund_read`
4. count a taxon as present when that abundance is `> 0`
5. keep taxa present in at least `10` samples

The downstream transform remains sample-centered CLR with pseudocount `0.5`.

## Why This Matters

This rule is much more permissive than the strict `tax_abund_tad > 0` filter. It allows the older read-based abundance signal to rescue taxa when the TAD signal is zero, which dramatically expands the matrix.

From local replay on the NGraph sample set, the strict TAD-only path retained `173` taxa at `prev_10`, while the hybrid rule retained `1797`.

That means the fallback to `tax_abund_read` is not a minor edge case. It dominates the retained feature space and should be treated as the exploratory, sensitivity-oriented setting.

## Interpretation

The point of this branch is not to prove the hybrid rule is more correct. It is to see whether the network becomes saturated when the matrix is widened in this way.

The main questions after the run are:

- do site graphs become too dense?
- do connected components collapse into giant components?
- do graph-of-graphs similarities lose resolution?

If that happens, the permissive rule is still useful because it shows where the exploration boundary is.

## Implementation Notes

- The branch-specific NGraph outputs should live under `results/ngraph/permissive_hybrid_prev10/`.
- The run should be launched detached with a master log in `logs/`.
- The pipeline runner was corrected so step `11` uses `11_ngraph_build_evidence_cards.R`.
- Query and retrieval consumers now read their primary threshold from environment/config instead of assuming `prev_5`.

## Repository review update (2026-10-05)

The code-grounded current status, implementation gaps, validation limits, and prioritized acceptance criteria are maintained in [REPOSITORY_REVIEW_2026-10-05.md](REPOSITORY_REVIEW_2026-10-05.md). This dated pointer supplements the historical planning and learning notes above; retain their original context when reading them.
