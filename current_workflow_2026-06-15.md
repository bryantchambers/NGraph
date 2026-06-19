# Current NGraph Workflow v3

- Last updated: 2026-06-19 11:55:12 UTC
- Version: v3

```mermaid
flowchart TD
  A[Start: run_pipeline.sh] --> B[00_ngraph_import_feedstock.R]
  B --> B1[Copy feedstock from Source/ROCS into /src/data]
  B1 --> B2[Validate required columns and write provenance]
  B2 --> C[01_ngraph_clr_matrices.R]

  C --> C1[Load imported damage table, metadata, and reference annotations]
  C1 --> C2[Filter damaged Archaea/Bacteria/Viruses to core set and <=150 ka]
  C2 --> C3[Aggregate by subspecies x sample using tax_abund_tad]
  C3 --> C4[Apply prevalence thresholds: prev_3, prev_5, prev_10]
  C4 --> C5[Build sample-centered CLR with pseudocount 0.5]
  C5 --> C6[Save threshold-specific CLR matrices and sample QC tables]
  C6 --> D[02_ngraph_input_qc.R]

  D --> D1[Ordination on each threshold-specific CLR matrix]
  D1 --> D2[PC correlations with technical and biological covariates]
  D2 --> D3[PC1/PC2 plots by core, raw reads, and TAD abundance]
  D3 --> D4[Write QC tables, heatmaps, and reports]
  D4 --> E[03_ngraph_site_graphs.R]

  E --> E1[For each threshold and core, select top variable taxa]
  E1 --> E2{Build site graphs for each method}
  E2 --> E3[pearson: abs Pearson correlation threshold >= 0.55]
  E2 --> E4[bicor: abs bicor threshold >= 0.55]
  E2 --> E5[spearman: abs Spearman threshold >= 0.55]
  E2 --> E6[mi_aracne: minet MIM with spearman estimator + ARACNE]
  E3 --> E7[Export edge list, node table, RDS, GraphML]
  E4 --> E7
  E5 --> E7
  E6 --> E7
  E7 --> E8[Summarize nodes, edges, density, components]
  E8 --> F[04_ngraph_graph_of_graphs.R]

  F --> F1[Load all site graphs for each threshold and method]
  F1 --> F2[Compute edge Jaccard overlap between core graphs]
  F2 --> F3[Compute normalized-Laplacian spectral quantile similarity]
  F3 --> F4[Combine similarities into super-edge weights]
  F4 --> F5[Build threshold-specific graph-of-graphs]
  F5 --> F6[Run Leiden clustering on the super-graph]
  F6 --> F7[Export super-graph edge/node tables, RDS, GraphML, and figure]
  F7 --> G[05_ngraph_summary.R]

  G --> G1[Read threshold matrix summaries, QC, site graphs, graph similarity, and deep-module exports]
  G1 --> G2[Write branch summary markdown]
  G2 --> G3[Write output inventory]
  G3 --> H[06_ngraph_build_heterograph.R]
  H --> H1[Export heterograph tables per threshold/method]
  H1 --> H2[Write heterograph manifests and export inventory]
  H2 --> I[07_ngraph_train_vgae.py]
  I --> I1[Train relation-aware VGAE/GAE on exported heterographs]
  I1 --> I2[Write taxon embeddings, module calls, and model checkpoint]
  I2 --> J[08_ngraph_train_diffpool.py]
  J --> J1[Train batched DiffPool on per-site graphs]
  J1 --> J2[Write soft assignments, consensus modules, and model checkpoint]
  J2 --> K[09_ngraph_deep_module_summary.R]
  K --> K1[Summarize module stability, enrichment, and run metrics]
  K1 --> K2[Write deep-module report, plot, and inventory]
  K2 --> L[10_ngraph_link_prediction.py]
  L --> L1[Calibrate latent link scores from VGAE embeddings]
  L1 --> L2[Export absent taxon-taxon and taxon-site hypotheses]
  L2 --> M[11_ngraph_build_evidence_cards.R]
  M --> M1[Create sample, site, taxon, module, and predicted-link cards]
  M1 --> M2[Write long-form abundance and CLR context tables]
  M2 --> N[12_ngraph_build_retrieval_index.py]
  N --> N1[Build TF-IDF evidence-card index]
  N1 --> N2[Build nearest-neighbor index over learned embeddings]
  N2 --> O[13_ngraph_query_engine.py]
  O --> Q1out[Run canonical natural-language discovery queries]
  Q1out --> Q2out[Write grounded answers, query bundles, and report]
  Q2out --> P[End: results/ngraph/abundance_thresholding/deep_knowledge_discovery]
  Q2out --> R[14_ngraph_local_browser.py]
  R --> R1[Serve local browser on 0.0.0.0:8000]

  subgraph Inputs
    I1[Source/ROCS damage table]
    I2[Source/ROCS metadata]
    I3[Source/ROCS reference annotation]
  end

  subgraph Threshold Loop
    T1[prev_3]
    T2[prev_5]
    T3[prev_10]
  end

  subgraph Method Loop
    M1a[pearson]
    M2a[bicor]
    M3a[spearman]
    M4a[mi_aracne]
  end

  subgraph Deep Toolkit
    D1a[PyG HeteroData]
    D1b[VGAE / GAE]
    D1c[DiffPool]
    D1d[R summary + ggplot2]
  end

  subgraph Discovery Layer
    Q1[Evidence cards]
    Q2[TF-IDF semantic index]
    Q3[Latent embedding neighbors]
    Q4[Grounded query answers]
  end

  subgraph Key Outputs
    Kout1[results/ngraph/abundance_thresholding/prev_5/tables/ngraph_site_graph_summary.tsv]
    Kout2[results/ngraph/abundance_thresholding/deep_modules/heterograph_export_summary.tsv]
    Kout3[results/ngraph/abundance_thresholding/deep_modules/vgae_run_summary.tsv]
    Kout4[results/ngraph/abundance_thresholding/deep_modules/diffpool_run_summary.tsv]
    Kout5[results/ngraph/abundance_thresholding/deep_modules/reports/NGRAPH_DEEP_MODULE_SUMMARY.md]
    Kout6[results/ngraph/abundance_thresholding/deep_knowledge_discovery/cards/evidence_cards.tsv]
    Kout7[results/ngraph/abundance_thresholding/deep_knowledge_discovery/query_results.tsv]
    Kout8[results/ngraph/abundance_thresholding/deep_knowledge_discovery/reports/NGRAPH_QUERY_REPORT.md]
  end

  I1 --> B1
  I2 --> B1
  I3 --> B1
  T1 -. applies to .-> C4
  T2 -. applies to .-> C4
  T3 -. applies to .-> C4
  M1a -. used in .-> E2
  M2a -. used in .-> E2
  M3a -. used in .-> E2
  M4a -. used in .-> E2
  H --> D1a
  I --> D1b
  J --> D1c
  K --> D1d
  M --> Q1
  N --> Q2
  N --> Q3
  O --> Q4
  H2 --> Kout2
  I2 --> Kout3
  J2 --> Kout4
  K2 --> Kout5
  M2 --> Kout6
  Q2out --> Kout7
  Q2out --> Kout8

  classDef step fill:#f8f9fa,stroke:#444,stroke-width:1px,color:#111;
  classDef loop fill:#eef6ff,stroke:#3b6ea8,stroke-width:1px,color:#111;
  classDef input fill:#fff4e6,stroke:#c27c00,stroke-width:1px,color:#111;
  classDef output fill:#eef9f0,stroke:#2d7d46,stroke-width:1px,color:#111;
  classDef toolkit fill:#f3ecff,stroke:#6b4fb3,stroke-width:1px,color:#111;
  classDef artifact fill:#fff7ea,stroke:#a66a00,stroke-width:1px,color:#111;

  class A,B,B1,B2,C,C1,C2,C3,C4,C5,C6,D,D1,D2,D3,D4,E,E1,E2,E3,E4,E5,E6,E7,E8,F,F1,F2,F3,F4,F5,F6,F7,G,G1,G2,G3,H,H1,H2,I,I1,I2,J,J1,J2,K,K1,K2,L,L1,L2,M,M1,M2,N,N1,N2,O,Q1out,Q2out,P,R step;
  class T1,T2,T3,M1a,M2a,M3a,M4a loop;
  class I1,I2,I3 input;
  class D1a,D1b,D1c,D1d toolkit;
  class Q1,Q2,Q3,Q4,R1 artifact;
  class Kout1,Kout2,Kout3,Kout4,Kout5,Kout6,Kout7,Kout8 artifact;
  class P output;
```

## Key Results

- Site-graph summaries: `results/ngraph/abundance_thresholding/prev_3|prev_5|prev_10/tables/ngraph_site_graph_summary.tsv`
- Graph-of-graphs summaries: `results/ngraph/abundance_thresholding/prev_3|prev_5|prev_10/tables/ngraph_graph_similarity.tsv`
- Heterograph exports: `results/ngraph/abundance_thresholding/deep_modules/heterograph_export_summary.tsv`
- VGAE outputs: `results/ngraph/abundance_thresholding/deep_modules/vgae_run_summary.tsv`, `vgae_embeddings.tsv`, `vgae_taxon_modules.tsv`, `models/vgae_model.pt`
- DiffPool outputs: `results/ngraph/abundance_thresholding/deep_modules/diffpool_run_summary.tsv`, `diffpool_site_taxon_assignments.tsv`, `diffpool_consensus_modules.tsv`, `models/diffpool_model.pt`
- Link prediction outputs: `results/ngraph/abundance_thresholding/deep_knowledge_discovery/link_prediction_summary.tsv`, `link_prediction_top_candidates.tsv`
- Evidence cards: `results/ngraph/abundance_thresholding/deep_knowledge_discovery/cards/evidence_cards.tsv`, `evidence_cards.jsonl`
- Retrieval index: `results/ngraph/abundance_thresholding/deep_knowledge_discovery/indexes/card_tfidf_matrix.npz`, `card_tfidf_vectorizer.pkl`, `vgae_nearest_neighbors.pkl`
- Query outputs: `results/ngraph/abundance_thresholding/deep_knowledge_discovery/query_results.tsv`, `query_results.jsonl`, `reports/NGRAPH_QUERY_REPORT.md`
- Local browser: `scripts/14_ngraph_local_browser.py` bound to `0.0.0.0:8000`, browsing cards, predicted links, modules, embeddings, super-graph views, and live queries

## Coverage Check

- Import step: included
- Canonical `/src/data` feedstock: included
- Threshold loop: `prev_3`, `prev_5`, `prev_10`: included
- CLR build: sample-centered with `tax_abund_tad`: included
- QC step: included
- Site graph methods: `pearson`, `bicor`, `spearman`, `mi_aracne`: included
- Graph-of-graphs step: included
- Deep-module step: included
- Learned link prediction: included
- Evidence cards and retrieval index: included
- Query engine: included
- Local browser: included
