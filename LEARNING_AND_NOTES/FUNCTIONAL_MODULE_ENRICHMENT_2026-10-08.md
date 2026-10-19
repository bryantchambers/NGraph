# Functional enrichment and discovery repair — implementation checkpoint

Updated 2026-10-08. This is an additive checkpoint; earlier mixed-abundance and TAD-only results remain historical baselines.

## Confirmed discovery repair

The new run is `mvp_functional_20261008`, an explicitly permissive mixed aggregated TAD/read sensitivity. Its global sample-centered CLR retains 1,797 taxa and 214 samples. Core graphs require at least five positive modeled-abundance observations and a nonconstant CLR profile. Functional annotations are excluded from the learned feature input. Module discovery considers 2–8 clusters rather than forcing six.

There are 84,691 core-specific association edges. Six exploratory VGAE modules assign 1,717 association-supported taxa: M4=599, M6=346, M2=279, M3=206, M5=153, M1=134. Another 37 taxa fail local support and 43 are association isolates; these remain in the inventory and KG with explicit unassigned status. These are newly discovered modules, not the historical module assignments.

Stages 00–15 completed after a stage-10 repair restricted learned link scores to taxa with actual embeddings. The retrospective run manifest records the staged/resumed commands and distinguishes recording-time source hashes. MVP validation passed with 37,154 nodes, 361,259 edges and zero dangling references. Repeated KMeans on fixed embeddings is not module bootstrap validation; reconstruction performance is transductive. The 120-epoch training cap does not prove convergence.

## Functional outputs that actually exist

Reference snapshot: `data/reference/functional/functional_20261008`. The archive audit covers 1,650 nonviral taxa, 578,409 deduplicated native gene–KO annotations and 440 module definitions. Historical "complete" flags mean at least 75% coverage, not complete pathways. Thirty-two exact-version public proteomes were retrieved (97,423 proteins). Reference quality and retrieval failures are preserved; there has been no fresh Kofam/eggNOG annotation run.

Analysis: `results/ngraph/mvp_functional_20261008/functional_enrichment/prev_10/pearson/vgae/legacy_20261008/`. Its completed manifest labels it **legacy_only_descriptive**. It contains 2,328 module/function summary rows, 43,961 supporting taxon/function records, 6,488 centrality rows, and 1,284 native sample/module profile rows. Centrality uses actual signed core-graph edges and 200 depth-block bootstrap replicates on fixed memberships. GeoB libraries remain distinct in profile plots while physical-depth resampling is shared. Zero-variation resamples are excluded even where floating-point standard deviations are numerically positive.

Figures: `module_function_overview.png`, `module_central_members.png`, and `module_core_profiles.png`. Full annotations are served through an indexed SQLite inventory, without eagerly loading native genes into the KG. Reference capability and carrier-taxon logratios describe potential, not measured sediment gene abundance, expression, activity or causal drivers.

There are **zero qualified statistical associations**. Legacy tables contain no manufactured p/q values. Conditional enrichment and ranked-affinity KS code are implemented but have not run on fresh full-proteome annotations. ssGSEA is not computed because GSVA is missing. Supporting reference provenance is preserved, and fresh evidence must match execution signatures, output/proteome hashes, sequence counts and reconstructed native KO records before statistical eligibility.

## Portal and validation

Constellations functional views and scoped APIs are implemented. A temporary loopback preview on **10292** serves the repaired branch; functional summaries, centrality and profiles passed real-artifact API probes. Port **10291** remains the active established service on the earlier mixed MVP while browser review of the new analysis is pending. Port **10289** remains archived. Do not describe the new branch as already deployed on 10291.

The functional KG projector ran on the legacy snapshot and correctly added zero nodes/edges. Publication requires fresh reference support, matched-permutation q ≤0.05, odds ratio ≥1.5, prevalence difference ≥0.10, at least five carriers, twenty annotated members, 70% annotation coverage and 50% exchangeability. All supporting contributors and provenance must remain inspectable. These gates are implemented; passing real-data associations do not yet exist.

Focused functional tests passed (39 in the initial discovery, plus rechecks of 11 statistical and 8 scientific-review tests after repairs). Live browser validation and fresh-annotation scientific acceptance remain distinct open gates.

## Remaining work in order

1. Obtain the requested approval to install missing annotation tools into the separate environment defined by `environment_functional.yml`; AGENTS.md forbids automatic package installation. No packages were installed automatically.
2. Freeze licensed/authorized local database snapshots, annotate the 32-reference pilot, review fresh/legacy KO agreement, module definitions and diagnostic markers, then extend annotation coverage as supported by exact references.
3. Exercise and validate whole-annotation matched permutations, full-affinity KS, multiple-testing correction, partial-completeness and annotation-burden sensitivities, secondary KO tests and ssGSEA comparisons. Fresh evidence must be adequate; unavailable references stay unknown.
4. Complete stricter local-prevalence, mixed/TAD-only and discovery-stability comparisons. A stricter-core run was planned but is not yet complete. No independent core holdout is established.
5. Validate functional portal interactions and desktop/mobile figures, then promote the reviewed branch to the established 10291 service while preserving provider configuration.
6. Publish only qualifying fresh associations to the KG and rerun schema/provenance/integrity checks. Continue the pre-existing ordered MVP backlog in TODO.md. HMM niche modelling remains deferred.

Run an offline analysis with explicit branch/reference/output snapshot identifiers:

```bash
NG_BRANCH=mvp_functional_20261008 \
NG_FUNCTIONAL_REFERENCE_SNAPSHOT=functional_20261008 \
NG_FUNCTIONAL_SNAPSHOT=NEW_IMMUTABLE_SNAPSHOT \
bash run_functional.sh
```

The wrapper exports existing matrices, runs offline analysis, projects qualifying associations and validates the KG. It does not install tools or download databases. Completed analysis snapshots are immutable.

## Background, permutation and annotation follow-up — 2026-10-08

The new immutable analysis snapshot `legacy_background_20261008` completed and preserves the original `legacy_20261008`. Both remain descriptive. The newer snapshot additionally exports `background_inventory.tsv`, `background_coverage.tsv`, `independent_annotation_units.tsv` and `function_background_qc.tsv`. Fresh full-proteome eligibility is zero in all six modules; retrieval alone and legacy module-scoped evidence do not establish testable annotation absences.

Background units are distinct native references, not genes. Same-reference aliases within one module collapse deterministically; references shared across conflicting module assignments are excluded. Viruses, unresolved mappings and unassigned taxa are explicit separate statuses. Unknown capability cells exclude a function from the entire frozen background, instead of dropping unfavorable comparisons or treating unknowns as negatives. Primary correction declares all network modules, including modules without annotated units. Functions are filtered only by global carrier/noncarrier support, before module effects are considered.

The fixed whole-annotation-row null preserves pathway co-occurrence and taxonomy/read-support strata, coarsening known prevalence/core-count covariates without arbitrary tie splits. Unknown numerical matching covariates now fail validation. Monte Carlo p-values use `(1 + exceedances)/(1 + permutations)`, consistent with [Phipson and Smyth](https://pubmed.ncbi.nlm.nih.gov/21044043/). Primary BH correction covers the full declared family. A separate Benjamini–Yekutieli sensitivity accounts for arbitrary test dependence. Pointwise 95% Clopper–Pearson intervals and transformed upper-q diagnostics are retained; boundary-uncertain primary calls do not publish. These diagnostics are not simultaneous FDR confidence bounds.

The one-sided KS implementation sorts fixed affinities once and uses exact tie endpoints with vectorized cumulative counts. Its results match scalar ECDF calculations. Secondary KS has its own correction family and cannot publish automatically. Fresh-data analyses also produce separate 75%-essential-step support sensitivity, annotation-burden/reference-quality matched sensitivity, and exact individual-KO Fisher/BH/BY baselines. These code paths have not yet run on real fresh annotations. Partial support is not a complete pathway; KO richness is deliberately not a primary matching covariate.

Fresh annotation selection now verifies full-proteome hashes and sequence counts, frozen execution signatures and database fingerprints, native output hashes, and reconstructed gene–KO records. Annotation gene IDs must belong to the verified proteome. Complementary eggNOG parsing preserves GO, EC and individual COG category letters. Reference-level annotation comparison uses a frozen legacy KO universe, never native gene-ID joins across providers. The pilot comparison report correctly reports `not_computed_no_fresh_annotations`; diagnostic-marker acceptance remains open.

Synthetic validation artifacts are in `results/ngraph/mvp_functional_20261008/functional_statistics_validation/`. A 100,000-permutation planted signal was detected, correlated annotation columns retained identical nulls, and a taxonomy-confounded signal had p=1. Among 100 independent synthetic null datasets with 999 permutations each, two had any BH rejection (rate 0.02; 95% interval approximately 0.0024–0.0704). This limited calibration check does not establish biological validity, full phylogenetic control or universal FDR calibration. Focused tests reached 54 passing checks before the final native-ID assertion; a final recheck is recorded in the run logs.

No annotation tools or databases have been installed/downloaded automatically. A current dry-run preflight reports missing KofamScan, HMMER, Ruby, profiles and KO list. The isolated environment/database setup decision remains pending. ssGSEA and real fresh-annotation enrichment remain uncomputed.

Final follow-up checks: 55 focused functional tests passed, and post-background KG substrate validation passed with zero dangling references and zero functional associations. Future analysis manifests capture source hashes before computation, refuse completion if analysis source changes during execution, and include the metadata, actual association edges, retention, mapping, completeness and reference-quality input hashes. Earlier descriptive snapshots retain their original recording-time provenance and are not rewritten.

## User-directed scope correction — broad set enrichment

The user has explicitly rejected using the 32-reference proteome pilot as the foundation or prerequisite for module annotation. The active route is now broad module-versus-function-set enrichment using existing taxon/reference-to-KO evidence, with a cached reusable annotation layer. Fresh proteome reannotation is removed from the critical path; no pilot-derived statistical background is to replace the broadly mapped taxa. Existing downloaded pilot files and prior plans remain historical; do not delete them.

The principal unit is an eligible annotated taxon/reference, not individual pooled genes. Each community module is compared against the matched eligible annotated taxa in the same analysis. KO/pathway carrier sets are constructed from the existing evidence with explicit reporting scope, coverage and unknowns. First use overlap/over-representation with effect sizes and multiplicity correction, supplemented by whole-row conditional permutations. A KS/GSEA-style test is a separate ranked-affinity analysis requiring a continuous score over the full eligible taxon universe. Ranking functional labels after an overlap test does not itself require KS. Existing annotation/reporting completeness must still be audited; no unknown mapping is to be invented as a biological absence. Results describe module-associated reference functional potential, not measured activity or causal importance.

Scaling strategy: build/version sparse reusable taxon-to-function mappings, compute module-level count/score summaries, and reuse reference annotations as sites are added. Do not reannotate every reference proteome for every module or site. R scoring tools can remain useful; installed/downloaded optional annotation tooling does not change this selected analysis route.

## Approved primary analysis completed — 2026-10-08

This section supersedes the earlier fresh-pilot dependencies and zero-association checkpoint. Primary annotation is **unweighted** enrichment of recorded KEGG framework support. The broad historical KO export is reused; the 32-proteome pilot is not used as the background or a prerequisite. Weighted KS and ranked-affinity scoring remain the **next version**, in a separate statistical family. Abundance/depth/age profiles are descriptive and do not weight the primary annotation.

Completed immutable snapshot: `results/ngraph/mvp_functional_20261008/functional_enrichment/prev_10/pearson/vgae/catalog_unweighted_20261008/`. It contains 1,577 independent annotated nonviral references, six declared modules, 159 globally eligible KEGG frameworks and 954 hypotheses. There are 381,600 seed-42 whole-profile permutations conditioned on taxonomy and detection support. Eight results pass BH q <= 0.05; four also meet all effect/coverage/exchangeability/Monte Carlo publication gates. Four scoped associations and their native supporting annotations have been projected into the KG; integrity validation passes with zero dangling references.

Permutation Z is `(observed carrier count - empirical null mean) / empirical null SD`. Constant nulls have undefined Z, rather than an invented zero or infinity. Empirical permutation p-values and whole-family BH q-values determine the primary calls; Z describes their standardized direction/strength. BY, Fisher and pointwise Monte Carlo diagnostics are separate fields. The eligible background is frozen across modules, shared references are collapsed, conflicting aliases excluded, and unresolved definitions never become negative cells.

The four gated catalog associations are M3/M00169 (CAM light enzyme framework), M3/M00091 (PE-to-PC biosynthesis), M4/M00121 (glutamate-to-heme biosynthesis), and M4/M00053 (deoxyribonucleotide biosynthesis). **These are catalog-supported potential, not expression or activity.** In particular, bacterial enzymes satisfying the CAM definition do not demonstrate plant CAM metabolism; the biological specificity of these labels still needs review. The original annotation tool/database release is unknown and retained as such. A negative cell means no complete support recorded in this catalog, not biological absence.

The runner `run_functional.sh` now invokes `18_ngraph_catalog_enrichment.py`. Reuse the reference snapshot `functional_20261008` but supply a new analysis snapshot identifier for a new run; completed snapshots are immutable. The portal ranks by q then Z, exposes null moments and source evidence, pages results/carriers, and keeps depth/age profiles in a separate tab. Catalog KG projection requires the completed audited manifest and matching hashes of every registered table, including the native KO inventory. It preserves `unknown_legacy` source provenance and labels association confidence separately.

Validation: 57 focused functional tests plus four catalog/Z tests pass; KG substrate validation passes. Human biological review, independent-core generalization, mixed/TAD-only comparisons and full module stability remain open. Fixed-membership centrality bootstraps do not validate stability of the learned module assignments.

Optional annotation environment status: installation was authorized, but both split Conda transactions failed during package post-link steps (`gdk-pixbuf` and `openmpi`, `TypeError ... NoneType`). Do not treat those environments as installed/validated. No fresh proteome annotation was run. The approved broad-catalog analysis completed in the existing `ngraph` environment and does not depend on either optional environment or downloaded Kofam profiles.

### Enrichment service promotion — 2026-10-08

Constellations **10291** now serves `mvp_functional_20261008`, using the completed `catalog_unweighted_20261008` enrichment snapshot. `bash start_server.sh 10291` defaults to this repaired branch; `NG_BRANCH` still selects a historical run. Port **10289 remains archived**. The loopback 10292 service is a development preview, not the active user-facing endpoint.

Modules → Functions provides unweighted enrichment, permutation Z, empirical p/BH q, paginated carriers and native KO provenance. Modules → Core profiles keeps relative abundance/depth/age summaries separate. Weighted KS/affinity scoring is deferred to the next version. The catalog's original annotation release remains unknown; results describe recorded reference potential rather than measured activity.

Automated acceptance: all 12 interface browser checks and seven focused enrichment checks passed against the promoted build on the 10292 preview. The active 10291 endpoint is checked separately after startup. Reports/screenshots are in `results/ngraph/mvp_functional_20261008/functional_validation/20261008/`. Gemini grounding and biological interpretation still require human review; these checks do not establish those acceptance gates.


### Functional KG integration — 2026-10-09

The combined taxon→module→association→function and reverse searches, same-taxon carrier mode, scoped canonical function lookup, versioned definitions/reference genomes, atomic retained graph snapshots and deterministic proof-producing functional Query are implemented. The active bundle is `functional-ad4cacf8c1ea6bf29e130b66` for `mvp_functional_20261008`/`prev_10`/Pearson/VGAE/`catalog_unweighted_20261008`. Four qualified associations are retained; source enrichment statistics were not recomputed. Full validation passes with 38,218 nodes, 364,315 edges and zero dangling references.

Constellations **10291** serves the integration; **10289 remains archived**, and loopback 10292 is a development preview. Knowledge Graph → Metapath search includes **Example: taxon to function**, carrier/all-member modes and compact/expanded views. Modules → Functions links to the authoritative association and scoped path. Query recognizes explicit taxon/module/KEGG identifiers and supplies inspectable proof IDs, scope and source hashes. It never infers individual activity solely from membership; ordinary retrieval and independently processed conversation turns remain available.

M3/M00091 has 206 community members and 110 supporting carriers. Automated validation comprises 76 functional/catalog tests, 11 focused browser checks and 12 wider interface checks; evidence is saved in `results/ngraph/mvp_functional_20261008/functional_validation/20261009/`. Human/scientific acceptance, general entity resolution and multi-turn Query remain open. Biological label specificity, unknown original annotation release, mixed/TAD-only stability and independent-core generalization still need review. Weighted KS, HMMs, curated ontology mappings and full KG learning remain future work.

See [implementation, acceptance evidence and reproduction commands](FUNCTIONAL_KG_REASONING_PLAN_2026-10-09.md).


### Functional conversational integration 2026-10-12

The technical [functional RAG implementation](FUNCTIONAL_RAG_IMPLEMENTATION_PLAN_2026-10-12.md) is delivered on Constellations **10291**, joint bundle `functional-587688fa942779a82370eb1f`. Its 38,253 nodes, 367,509 edges and 2,602 evidence cards retain four qualified associations and the original enrichment statistics. Functional names, summaries/comparisons, supporting carriers, centrality, core profiles and bounded follow-ups now use shared scoped evidence. Gemini explanations have checked claim-level evidence and deterministic fallback. HTTP POST carries returned context; GET compatibility remains. Reindexing can rebuild the compatible KG/retrieval bundle without retraining or recomputing enrichment.

The KG adds selected native KO and recorded-category links. Reviewed semantic mapping infrastructure is present, but the GO/EC registry is empty pending supported curation. No biological equivalence, measured activity, fresh proteome remapping, weighted KS, HMM or KG-learning claim is implied. Biological specificity and original annotation release still require review.

Acceptance: 92 focused tests, 33 browser checks, full KG integrity/proxy validation and bounded HTTP/Gemini checks pass. Reports are in `results/ngraph/mvp_functional_20261008/functional_validation/20261012/`. Port 10289 remains archived; 10292 is a preview. Existing dated checkpoints are historical; the original scientific/proxy/generalization backlog remains open.
