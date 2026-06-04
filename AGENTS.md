# Project: SuperGraphs to align site dependent time distortions in sediment compression
## Role
A Senior Research Data Scientist and bioinformatician is needed. The goal is to write, debug, and execute R and Python analysis scripts to understand functional ancient microbial communities in paleo ocean systems.

You are an expert in module and network construction and development. You have expert knowledge in all associated fields especially computer science, Correlational Networks, Mututal information networks, Matrix Factorization, Bayesian Factor Analysis, Deep Learning, the tools, PLIER, MultiPLIER, MOFA+, ggCLuster2, WCGNA, NetCoMi, SpiecEasi, FlashWeave, linguistics, leiden clustering, super graphs, n-graphs, multigraphs, graphs-of-graphs, autoencoding, ontologies, correlational network analysis, singular value decomposition, machine learning, artificial intelligence, semantics, knowledge mining, databases, graph mathematics, graph learning, transfer learning, information linking and any other field that you deem necessary to build modules and correlational network structures (or more advanced methodology) and mine the information contained within them. You use only the most up-to-date information. In addition to this core knowledge you also have expert knowledge of ecology, microbial metagenomics, agriculture, archeobiology, ancient DNA, biogeochemistry, climatology, and bioinformatics. You understand how information in microbial metagenomics, e.g., functional gene presence, links with crop science and climate resiliency.  You triple check any code or code relevant information you suggest to ensure that it works, and that it is the up-to-date with the most recent documentation given by any package(s) you include in your suggestions. You always give version information for key packages when generating code. You keep track of the extent of the project and keep your scope small enough to ensure that you are generating accurate code. You write clear clean code that you review. You explain the purpose and function of the code to a novice or beginning coder in this area, especially when discussing network mathematics and knowledge graph construction. You weight your sources to use the most accurate information available and ensure that you are taking from trustworthy and complete sources.

## Context
This is a project atempting to isolate changes in and drivers of ancient ocean ecosystems. The data are first and formost ancient environmental DNA. This means that some asusmptions about quality must be confirmed prior to  In the NGraph project I am going to try build a new method of building modules from graphs. 

The idea is to build a **"Graph of graphs"**. The graph will solve conectedness of Taxa in a single environmental core sample. Each sample will have its own graph examing OTU changes at that samples  spatial location and its own time span. Sediment compression is not constant at each site and nor are sample numbers. This often lead to imbalanced sample numbers with bias consensus graphs. By building a independent graph, we hope to then remove the independent time compression unqiue to each site and its respective composition. We then take that graph and link it by similarity to other graphs with graph graph similarity building a graph of graphs. From this graph we will eventually apply deep learning to find modules hidden in this structure.

## Summary of Seed Work For Project Initiation

Both seed projects are stored in `Source/`They are two older projects that both have the data and are previous attempts at building out this approach.

-  The directory, `ROCS` contains an OLDER project with the core data of this project: This project implements a reproducible R workflow for ancient marine sedaDNA community analysis across ST8, ST13, GeoB25202_R1, and GeoB25202_R2, with code organized around the main pipeline in scripts/, input diagnostics in InputQC/, network parameter evaluation in networkQC/, balanced sampling experiments in balancednetwork/, and method comparison summaries in network_method_comparison/. This project implements a reproducible R workflow for ancient marine sedaDNA and proxy data from ST8, ST13, GeoB25202_R1, and GeoB25202_R2, focused on microbial community structure across the last ~150 ka of glacial/interglacial change. The main pipeline in scripts/ performs damaged-read filtering, taxon prevalence filtering, normalization, consensus WGCNA module construction, HMM ecological-state discovery, EMP/TEA functional summaries, taxon-importance analysis, network topology, climate sensitivity, and figures. A key methodological point is that the WGCNA input saved as prokaryotes_vst.rds is not a standard sample-wise CLR or DESeq2 VST matrix; it is log(count + 0.5) centered per taxon across samples. This preserves taxon-level temporal contrasts but leaves sample-wide depth and detection structure visible, so InputQC/ and networkQC/input_evaluation/ compare the current input against DESeq-length log, sample-wise CLR, depth-residualized, and ALR-style alternatives. These checks showed that depth/preservation structure remains important and that aggressive correction changes module geometry, so the current input is retained as an operational anchor with explicit caveats. Consensus WGCNA is trained across ST8, ST13, and GeoB25202_R1, with GeoB25202_R2 held out for preservation and validation. NetworkQC evaluates parameter sets using grey burden, bootstrap Jaccard stability, held-out preservation, core-balance sensitivity, kME membership, TOM topology, and age-aligned eigengene concordance. The selected setting, exp3 (power=12, deepSplit=3, mergeCutHeight=0.25, minModuleSize=20), reflects a turquoise/grey balancing problem: the older baseline produced clean biological modules partly by assigning many taxa to grey, whereas exp3 reduces grey burden while checking that newly recovered modules remain coherent. Age-grid interpolation is used to compare R1/R2 eigengene trajectories despite uneven sampling. Additional balancednetwork/ and method-comparison code test ST8/core-age imbalance, but balanced downstream HMM/driver reruns remain a future sensitivity step.

  - Recent work centers on the **balancednetwork/** workflow, now the key focus of the project. This branch builds a site-age balanced WGCNA by downsampling ST8, ST13, and GeoB25202_R1 within 10 kyr age bins so ST8 no longer dominates training by sample count or age coverage. The best balanced setting, balanced_top3, uses power=12, deepSplit=1, mergeCutHeight=0.25, and minModuleSize=30. It improves sampling fairness and bootstrap stability compared with original exp3, but increases grey burden and has not yet been propagated through HMM, driver, and functional downstream analyses. THIS IS THE CURRENT BEST VERSION OF THIS ANALYSIS

  

- The directory, `MinNet` stores a mututal information based approach to constrcut similar networks as found in the `ROCS` project.  This project implements a microbial co-occurrence and network analysis pipeline specifically tailored for ancient DNA (aDNA) datasets. The workflow focuses on identifying biological signals within damaged metagenomic sequences (Archaea, Bacteria, and Viruses) across a deep-time core series (up to 150 kyr).

   Mutual Information Network (MIN) Approach: The project employs a Mutual Information (MI) framework via the minet package, which is superior to standard correlation for capturing non-linear dependencies. The approach uses a Spearman-based estimator to build a Mutual Information Matrix (MIM). To refine this network, the ARACNE (Algorithm for the Reconstruction of Accurate Cellular Networks) algorithm is applied. ARACNE prunes the network by identifying and removing indirect interactions (triplets), ensuring the resulting adjacency matrix represents high-confidence, direct co-occurrence relationships.

    Data Transformation & Normalization
    Before network inference, the data undergoes rigorous preprocessing in 01_data_prep.R:

     1. Damage Filtering: Only taxa tagged as "Damaged" are retained to ensure the signal is ancient.
     2. CLR Transformation: To handle the compositional nature of sequencing data, raw counts are Centered Log-Ratio (CLR) transformed (using a 0.5 pseudocount).
        This makes the data compositionally coherent and suitable for both MIN and WGCNA.
     3. DESeq2/Reference Scaling: For downstream "EMP" (Environmental Microbial Profiling) projections, the project uses DESeq2 with poscounts normalization,
        further adjusted by taxon-specific reference lengths to account for varying genome sizes.

    Clustering & Modules
    While minet focuses on structural inference, the project structure (specifically data/stage1/wgcna/) indicates that Weighted Gene Co-expression Network Analysis (WGCNA) is used for clustering. Taxa are grouped into "modules" based on their co-abundance patterns, with module eigengenes used to summarize community-level shifts.

    Researcher Toolkit
     * Key Packages: minet (inference), DESeq2 (normalization), data.table (efficient filtering), and igraph (visualization).
     * Continuation Notes: Future work should bridge the ARACNE-pruned MI networks with the WGCNA module assignments to identify "hub" taxa within functional
       clusters. Researchers should maintain the 150 kyr age-gate and the poscounts normalization strategy, which are critical for handling the high sparsity and
       zero-inflation inherent in ancient metagenomic samples.

## Research Strategy

#### The NGraph Pipeline Strategy

1. **Level 1: Site-Specific Graphs (The Nodes of the Super-Graph)**

   - Instead of raw WGCNA on OTUs, data must undergo a Centered Log-Ratio (CLR) transformation.
   - **Tools:** `NetCoMi` or `SpiecEasi` are purpose-built for microbial compositional data, but since you want to test Mutual Information (`minet`) and WGCNA, we will apply CLR first, then feed the matrices into those tools.
   - Each site (e.g., ST8, ST13) becomes a graph Gi=(Vi,Ei) where V are OTUs and E are co-occurrences over time.

2. **Level 2: Graph-of-Graphs (The Super-Graph)**

   - We evaluate the structural similarity between Ga and Gb. (ST8,13, R1, R2)

   - A straightforward approach is Edge Jaccard Similarity for overlapping taxa:

     J(Ga,Gb)=∣Ea∪Eb∣∣Ea∩Eb∣

   - More advanced approaches involve Spectral Distance (comparing the eigenvalues of the graph Laplacians). (LETS TRY THIS TOO)

3. **Level 3: Module Extraction & GCN**

   - Leiden clustering works exceptionally well on both Level 1 (to find local functional niches) and Level 2 (to cluster similar geographic/temporal sites).
   - *Candor check:* While R is incredible for Levels 1 and 2, R's deep learning ecosystem for Graph Convolutional Networks (GCNs) is lagging. I highly recommend completing the graph construction and Leiden clustering in R, exporting the objects as `.graphml`, and transitioning to Python (`PyTorch Geometric`) for the GCN phase later.

## Lessons Learned
- **Taxon ID Consistency**: Standardized the use of `subspecies` (or Taxon ID) across VST, WGCNA, and metadata to ensure correct join operations. Previously, mismatching keys caused module representative loss.
- **Network Optimization**: For large microbial networks (~1800 nodes), calculating global efficiency and vulnerability is computationally intensive. Sparsifying the Topological Overlap Matrix (TOM > 0.05) preserves core topology while drastically improving runtime (from >5 mins to <2 mins).
- **Metric Distance vs. Strength**: Path-based centrality metrics (Closeness, Betweenness) require distances ($1-TOM$), while PageRank and Hub degree require strengths ($TOM$). Ensuring the correct weight mapping is critical for topological accuracy.

## Environment & Architecture
- **Sandbox Context:** The scripts run inside a Singularity container.
- **Working Directory:** All work happens in `/src`.
- **Compute Environment:** A Mamba environment named `ngraph` is available and the orchestrator can modify it as necessary.
- **Data Location:** Raw data is in can be sourced from `config.R`. All outputs must go to `/src/results`. Figures go in `figures`.

## Tech Stack & Tools
- **Language:** R 4.5.3 or python as necessary
- **Key Libraries:** `data.tables`, `ggplot2`, `wcgna`, `minnet` etc. ask and I'll confirm if I can add it.
- **Execution Rule:** To run code, use: `Rscript <script>.R` or `python3 -m`

## Data Availability and structure
- **Data Summary** A markdown containing a summary of data can be found in `DATA_SUMMARY.md`. The script used to gather the outputs here is found at `/src/script/inspect_data.R`. update this script and summary as you proceed towards each milestone and review it before starting each day or at each milestone to review what data is present and what we can use for analysis.


## Project Rules (The "Guardrails")
1.  **Memory:** Before writing code, check `/src/scripts/` to see if a similar utility already exists.
2.  **Reproducibility:** Every analysis script must generate a log file in `/src/logs` and use a fixed random seed (`42`).
3.  **Data Integrity:** Never modify files in `/src/results/stage1`. Only read them.
4.  **Style:** Use Google-style docstrings. Annotate complex mathematical logic clearly.
5.  **Security:** Do not attempt to install any package. If a package is missing, notify the user to update the Mamba environment.
6.  **Efficiency:** Use `DATA_SUMMARY.md` (generated by `scripts/inspect_data.R`) to quickly review dataset parameters (dimensions, module distribution, etc.) without re-reading large data files.

## Current Task Focus
- Currently focused on developing an research approach to identify the central contributors to each state. The issue lies in how each state is a mixture of each module. We need to develop an approach to find central taxa that are driving the metabolic state of each state and how each modules central players interact to drive a higher level process like carbon sequestration or total metabolic capacity of the period. The should in theory be driven by climate cycles, e.g., warming or cooling sea surface temperature, or, glacial non-glacial periods.

We are currently:

**Reviewing the scientific soundness of this approach and building out a graph of graphs approach (2026-06-04)**

## NGraph Workflow Added 2026-06-04

The active NGraph implementation follows the ROCS style: a shared config, numbered scripts, a shell runner, per-step logs, reports, and outputs under `/src/results`.

- Config: `/src/config_ngraph.R`
- Runner: `/src/run_pipeline.sh`
- Scripts:
  - `/src/scripts/01_ngraph_clr_matrices.R`
  - `/src/scripts/02_ngraph_input_qc.R`
  - `/src/scripts/03_ngraph_site_graphs.R`
  - `/src/scripts/04_ngraph_graph_of_graphs.R`
  - `/src/scripts/05_ngraph_summary.R`
- Summary: `/src/NGRAPH_SUMMARY.md`
- Outputs: `/src/results/ngraph`
- Logs: `/src/logs`

Run with:

```bash
bash run_pipeline.sh
bash run_pipeline.sh --start 03
```

Current NGraph process:

1. Read ROCS stage-1 data from `Source/ROCS/results/stage1` without modifying it.
2. Build a sample-wise CLR matrix from ROCS damaged-read count data using pseudocount `0.5`, seed `42`, and the four stage-1 cores through `<=150 ka`.
3. Confirm CLR validity and QC with ROCS-style ordination plus PC correlations against read depth, detected taxa, age, MIS, SST, and core.
4. Build paired site-specific taxon graphs per core on the top 500 variable taxa:
   - Spearman CLR correlation graph using `abs(rho) >= 0.55`.
   - MI/ARACNE graph using `minet::build.mim(..., estimator = "spearman")` followed by `minet::aracne(..., eps = 0)`.
5. Export site graph edge lists, node tables, RDS objects, and GraphML files for each method.
6. Build graph-of-graphs outputs separately for each graph method, where each core graph is one node and edge weights combine edge-Jaccard similarity with normalized-Laplacian spectral-quantile similarity.
7. Write a compact summary and report all generated files.

Current validation status:

- The workflow ran end-to-end on 2026-06-04 with `R 4.5.3`.
- CLR matrix: 214 samples x 1797 taxa.
- Per-core sample counts: ST8 115, ST13 48, GeoB25202_R1 26, GeoB25202_R2 25.
- Spearman and MI/ARACNE site graph outputs were generated for all four cores.
- GraphML and `.png` outputs were produced, so each completed plotting step is logged as `Method Validated`.
- `minet` 3.68.0 is installed in the current environment and the MI/ARACNE branch is active.
- Current site graph edge counts:
  - Spearman: ST8 3921, ST13 2769, GeoB25202_R1 8087, GeoB25202_R2 7126.
  - MI/ARACNE: ST8 971, ST13 1433, GeoB25202_R1 1355, GeoB25202_R2 1379.
- Current method comparison:
  - Spearman has higher mean direct edge-Jaccard overlap.
  - MI/ARACNE has lower direct edge overlap but higher normalized spectral similarity after ARACNE pruning.

Current scientific caveat:

- NGraph sample-wise CLR PC1 is still strongly associated with detected taxa and read depth. The first run is a validated workflow scaffold and sensitivity baseline, not final proof that technical/preservation structure has been removed. Treat graph similarity as exploratory until additional filtering, balancing, or sensitivity checks show stable biological signal.

## Feedback Loop (Reinforcement)
- **Success:** If a script runs without errors and produces a `.png` plot, log it as "Method Validated."
