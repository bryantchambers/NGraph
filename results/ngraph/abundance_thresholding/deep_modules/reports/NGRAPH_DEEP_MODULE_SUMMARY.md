# NGraph Deep Module Summary

- Generated: 2026-06-15 16:58:01 CEST
- Seed: `42`
- Branch: `abundance_thresholding`
- Primary threshold: `prev_5`
- Primary method: `pearson`
- Validation core: `GeoB25202_R2`

## Export Coverage

|threshold|method|taxon_nodes|site_nodes|taxon_taxon_edges|site_site_edges|taxon_site_edges|taxon_taxon_positive|taxon_taxon_negative|
|---|---|---|---|---|---|---|---|---|
|3|pearson|374|4|60630|6|1042|52190|8440|
|3|bicor|374|4|237200|6|1042|234300|2866|
|3|spearman|374|4|170600|6|1042|169300|1291|
|3|mi_aracne|374|4|86200|6|1042|86200|0|
|5|pearson|274|4|25070|6|851|20150|4924|
|5|bicor|274|4|116500|6|851|115300|1224|
|5|spearman|274|4|74980|6|851|74350|630|
|5|mi_aracne|274|4|35390|6|851|35390|0|
|10|pearson|173|4|7144|6|612|5102|2042|
|10|bicor|173|4|36090|6|612|35500|598|
|10|spearman|173|4|19500|6|612|19410|95|
|10|mi_aracne|173|4|8997|6|612|8997|0|

## VGAE Runs

|threshold|method|validation_core|best_epoch|best_heldout_auc|module_k|module_silhouette|
|---|---|---|---|---|---|---|
|prev_10|bicor|GeoB25202_R2|1|0.5|3|0.5429|
|prev_10|mi_aracne|GeoB25202_R2|2|0.7452|2|0.6737|
|prev_10|pearson|GeoB25202_R2|2|0.5812|2|0.3973|
|prev_10|spearman|GeoB25202_R2|5|0.7466|2|0.6292|
|prev_3|bicor|GeoB25202_R2|1|0.5014|4|0.5593|
|prev_3|mi_aracne|GeoB25202_R2|1|0.714|2|0.7468|
|prev_3|pearson|GeoB25202_R2|1|0.6608|2|0.6431|
|prev_3|spearman|GeoB25202_R2|1|0.5089|2|0.4914|
|prev_5|bicor|GeoB25202_R2|1|0.5|7|0.4671|
|prev_5|mi_aracne|GeoB25202_R2|1|0.7445|2|0.7278|
|prev_5|pearson|GeoB25202_R2|1|0.6719|2|0.6195|
|prev_5|spearman|GeoB25202_R2|1|0.5|3|0.4939|

## DiffPool Runs

|threshold|method|best_epoch|best_loss|assign_dim_1|assign_dim_2|n_taxa|n_sites|
|---|---|---|---|---|---|---|---|
|prev_10|bicor|5|7.62|13|6|173|4|
|prev_10|mi_aracne|5|4.987|13|6|173|4|
|prev_10|pearson|5|5.215|13|6|173|4|
|prev_10|spearman|5|5.734|13|6|173|4|
|prev_3|bicor|5|9.33|19|9|374|4|
|prev_3|mi_aracne|5|4.851|19|9|374|4|
|prev_3|pearson|5|4.991|19|9|374|4|
|prev_3|spearman|5|7.029|19|9|374|4|
|prev_5|bicor|5|8.217|17|8|274|4|
|prev_5|mi_aracne|5|4.991|17|8|274|4|
|prev_5|pearson|5|5.127|17|8|274|4|
|prev_5|spearman|5|6.313|17|8|274|4|

## Primary Module Snapshot

### functional_group

|module_kmeans|functional_group|N|
|---|---|---|
|M1|Virus_modulator|48|
|M1|Core_heterotrophy|36|
|M1|Pelagic_heterotroph|14|
|M1|Particle_heterotroph|12|
|M1|Nitrification_AOA|11|
|M1|NA|9|
|M1|Pelagic_heterotroph_MGII|8|
|M1|Sulfate_reduction_diagenetic|2|
|M1|Unknown|1|
|M2|Virus_modulator|39|
|M2|Core_heterotrophy|35|
|M2|Nitrification_AOA|16|
|M2|Pelagic_heterotroph_MGII|11|
|M2|Particle_heterotroph|7|
|M2|Dehalococcoidia|6|
|M2|Nitrite_oxidation_NOB|5|
|M2|Sulfate_reduction_diagenetic|5|
|M2|Pelagic_heterotroph|5|

### ecological_role

|module_kmeans|ecological_role|N|
|---|---|---|
|M1|Pelagic_heterotroph|66|
|M1|Modulator|48|
|M1|Nitrifier|11|
|M1|NA|9|
|M1|Heterotroph_general|3|
|M1|Diagenetic_SRB|2|
|M1|Unknown|2|
|M2|Pelagic_heterotroph|56|
|M2|Modulator|39|
|M2|Nitrifier|21|
|M2|Diagenetic_acetogen|6|
|M2|Diagenetic_SRB|5|
|M2|Anammox_N_cycle|2|
|M2|Unknown|2|
|M2|Primary_producer|1|
|M2|Heterotroph_general|1|

### tea_primary

|module_kmeans|tea_primary|N|
|---|---|---|
|M1|O2|81|
|M1||48|
|M1|NA|9|
|M1|SO4--|2|
|M1|Unknown|1|
|M2|O2|80|
|M2||39|
|M2|CO2|6|
|M2|SO4--|5|
|M2|NO2-/NH4+|2|
|M2|Unknown|1|

### guild_tier

|module_kmeans|guild_tier|N|
|---|---|---|
|M1|Tier1_taxonomy_conserved|86|
|M1|Tier1_kegg_present|42|
|M1|NA|9|
|M1|Tier2_taxonomy_broad|3|
|M1|Tier3_unknown|1|
|M2|Tier1_taxonomy_conserved|78|
|M2|Tier1_kegg_present|50|
|M2|Tier2_kegg_partial|3|
|M2|Tier3_unknown|1|
|M2|Tier2_taxonomy_broad|1|

### kegg_state

|module_kmeans|kegg_state|N|
|---|---|---|
|M1||90|
|M1|present|42|
|M1|NA|9|
|M2||83|
|M2|present|50|

### domain

|module_kmeans|domain|N|
|---|---|---|
|M1|d__Bacteria|62|
|M1|d__Viruses|48|
|M1|d__Archaea|22|
|M1|NA|9|
|M2|d__Bacteria|67|
|M2|d__Viruses|39|
|M2|d__Archaea|27|

### phylum

|module_kmeans|phylum|N|
|---|---|---|
|M1|p__Uroviricota|34|
|M1|p__Proteobacteria|23|
|M1|p__Bacteroidota|23|
|M1|p__Nucleocytoviricota|14|
|M1|p__Thermoproteota|12|
|M1|NA|9|
|M1|p__Thermoplasmatota|8|
|M1|p__Actinobacteriota|4|
|M1|p__Marinisomatota|4|
|M1|p__Verrucomicrobiota|3|
|M1|p__Planctomycetota|3|
|M1|p__Hadarchaeota|1|
|M1|p__KSB1|1|
|M1|p__SAR324|1|
|M1|p__Asgardarchaeota|1|
|M2|p__Uroviricota|28|
|M2|p__Proteobacteria|20|
|M2|p__Thermoproteota|16|

### class

|module_kmeans|class|N|
|---|---|---|
|M1|c__Caudoviricetes|34|
|M1|c__Bacteroidia|23|
|M1|c__Gammaproteobacteria|17|
|M1|c__Megaviricetes|14|
|M1|c__Nitrososphaeria|12|
|M1|NA|9|
|M1|c__Poseidoniia|8|
|M1|c__Alphaproteobacteria|6|
|M1|c__Marinisomatia|4|
|M1|c__Acidimicrobiia|3|
|M1|c__Verrucomicrobiae|3|
|M1|c__Planctomycetia|2|
|M1|c__Hadarchaeia|1|
|M1|c__UBA2214|1|
|M1|c__SAR324|1|
|M1|c__Phycisphaerae|1|
|M1|c__Humimicrobiia|1|
|M1|c__Lokiarchaeia|1|


## Core Stability

|taxa|mean_assignment_entropy|median_sites_present|
|---|---|---|
|274|0.8374|3|

## Method Agreement

|taxa|same_module|agreement_rate|
|---|---|---|
|274|0|0|

## Output Inventory

|file|bytes|
|---|---|
|results/ngraph/abundance_thresholding/deep_modules/prev_3/bicor/tables/hetero_taxon_taxon_edges.tsv|39420000|
|results/ngraph/abundance_thresholding/deep_modules/prev_3/spearman/tables/hetero_taxon_taxon_edges.tsv|28590000|
|results/ngraph/abundance_thresholding/deep_modules/prev_5/bicor/tables/hetero_taxon_taxon_edges.tsv|19510000|
|results/ngraph/abundance_thresholding/deep_modules/prev_3/mi_aracne/tables/hetero_taxon_taxon_edges.tsv|14760000|
|results/ngraph/abundance_thresholding/deep_modules/prev_5/spearman/tables/hetero_taxon_taxon_edges.tsv|12670000|
|results/ngraph/abundance_thresholding/deep_modules/prev_3/pearson/tables/hetero_taxon_taxon_edges.tsv|9213000|
|results/ngraph/abundance_thresholding/deep_modules/prev_10/bicor/tables/hetero_taxon_taxon_edges.tsv|6167000|
|results/ngraph/abundance_thresholding/deep_modules/prev_5/mi_aracne/tables/hetero_taxon_taxon_edges.tsv|6028000|
|results/ngraph/abundance_thresholding/deep_modules/prev_5/pearson/tables/hetero_taxon_taxon_edges.tsv|3936000|
|results/ngraph/abundance_thresholding/deep_modules/prev_10/spearman/tables/hetero_taxon_taxon_edges.tsv|3357000|
|results/ngraph/abundance_thresholding/deep_modules/prev_10/mi_aracne/tables/hetero_taxon_taxon_edges.tsv|1534000|
|results/ngraph/abundance_thresholding/deep_modules/prev_10/pearson/tables/hetero_taxon_taxon_edges.tsv|1220000|
|results/ngraph/abundance_thresholding/deep_modules/prev_10/bicor/models/vgae_model.pt|345200|
|results/ngraph/abundance_thresholding/deep_modules/prev_10/pearson/models/vgae_model.pt|345200|
|results/ngraph/abundance_thresholding/deep_modules/prev_10/spearman/models/vgae_model.pt|345200|
|results/ngraph/abundance_thresholding/deep_modules/prev_3/bicor/models/vgae_model.pt|345200|
|results/ngraph/abundance_thresholding/deep_modules/prev_3/pearson/models/vgae_model.pt|345200|
|results/ngraph/abundance_thresholding/deep_modules/prev_3/spearman/models/vgae_model.pt|345200|
|results/ngraph/abundance_thresholding/deep_modules/prev_5/bicor/models/vgae_model.pt|345200|
|results/ngraph/abundance_thresholding/deep_modules/prev_5/pearson/models/vgae_model.pt|345200|
