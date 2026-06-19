# NGraph Deep Knowledge Discovery Evidence Report

- Generated: 2026-06-19 14:16:57 CEST
- Seed: `42`
- Branch: `abundance_thresholding`
- Primary threshold: `prev_5`
- Primary method: `pearson`

## Card Inventory

|card_type|card_count|
|---|---|
|module|4|
|predicted_link|2320|
|sample|214|
|site|4|
|taxon|274|

## Inputs

- Sample abundance long table: `/src/results/ngraph/abundance_thresholding/deep_knowledge_discovery/tables/sample_taxon_abundance_long.tsv`
- Sample CLR long table: `/src/results/ngraph/abundance_thresholding/deep_knowledge_discovery/tables/sample_taxon_clr_long.tsv`
- Evidence cards TSV: `/src/results/ngraph/abundance_thresholding/deep_knowledge_discovery/cards/evidence_cards.tsv`
- Evidence cards JSONL: `/src/results/ngraph/abundance_thresholding/deep_knowledge_discovery/cards/evidence_cards.jsonl`

## VGAE Summary

|threshold|method|validation_core|best_epoch|best_heldout_auc|module_k|module_silhouette|
|---|---|---|---|---|---|---|
|prev_5|pearson|GeoB25202_R2|1|0.6719|2|0.6195|

## DiffPool Summary

|threshold|method|best_epoch|best_loss|assign_dim_1|assign_dim_2|n_taxa|n_sites|
|---|---|---|---|---|---|---|---|
|prev_5|pearson|5|5.127|17|8|274|4|
