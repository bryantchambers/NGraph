suppressPackageStartupMessages(library(data.table))
source('config_ngraph.R')
set.seed(42)
LOG <- ng_log_path('verify_filtering'); ng_start_log(LOG)
dirs <- ng_threshold_dirs(10)
tax <- fread(NG_DATA$tax_damage, select=c('label','subspecies','domain','is_dmg','n_reads','tax_abund_tad','tax_abund_read'))
meta <- fread(NG_DATA$metadata_file)
labels <- meta[core %in% NG_PARAMS$all_cores & y_bp <= 150000 & label != 'LV3003046968', label]
rows <- tax[is_dmg == 'Damaged' & n_reads >=100 & domain %in% c('d__Archaea','d__Bacteria','d__Viruses') & label %in% labels]
agg <- rows[, .(tad=sum(tax_abund_tad,na.rm=TRUE),read=sum(tax_abund_read,na.rm=TRUE)),by=.(subspecies,label)]
keep <- agg[fifelse(tad>0,tad,read)>0,.N,by=subspecies][N>=10,subspecies]
abund <- readRDS(file.path(dirs$matrices,'ngraph_tax_abundance_taxa_by_sample.rds'))
clr <- readRDS(file.path(dirs$matrices,'ngraph_clr_global.rds'))
stopifnot(setequal(keep,rownames(abund)),identical(rownames(clr),colnames(abund)),all(colSums(abund)>0))
expected <- matrix(0,nrow(abund),ncol(abund),dimnames=dimnames(abund))
a <- agg[subspecies %in% rownames(abund) & label %in% colnames(abund)]
expected[cbind(match(a$subspecies,rownames(expected)),match(a$label,colnames(expected)))] <- if (NG_PARAMS$abundance_mode == "hybrid_aggregated_tad_then_read") fifelse(a$tad>0,a$tad,a$read) else a$tad
stopifnot(identical(unname(expected),unname(abund)))
logs <- log(expected+.5); target <- t(sweep(logs,2,colMeans(logs),'-'))
stopifnot(max(abs(clr-target))<1e-12,all(apply(clr,2,var)>0))
# A duplicate observation with positive TAD prevents read fallback after aggregation.
fixture <- data.table(tad=c(2,0,0,0),read=c(0,9,4,3),taxon=c('a','a','b','b'),sample='s')
f <- fixture[,.(tad=sum(tad),read=sum(read)),by=.(taxon,sample)]
stopifnot(identical(f[,fifelse(tad>0,tad,read)],c(2,7)))
ng_log(LOG,'PASS: independent raw-to-CLR reconstruction; ',nrow(abund),' taxa, ',ncol(abund),' samples; ',sum(rowSums(readRDS(file.path(dirs$matrices,'ngraph_tax_abund_tad_taxa_by_sample.rds')))>0),' TAD-supported taxa')
