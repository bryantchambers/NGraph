suppressPackageStartupMessages(library(data.table))
source('scripts/ngraph_proxy_matching.R')
core_to_site <- function(x) sub('_R[12]$', '', x)
p <- data.table(core='GeoB25202',depth_in_core_cm=c(0,4,20),v=c(0,8,40),total_count=c(1,2,3))
s <- data.table(sample_id=c('a','b','c','d','e'),core=c('GeoB25202_R1','GeoB25202_R2','GeoB25202_R1','GeoB25202_R1','GeoB25202_R1'),site_id='GeoB25202',depth_in_core_cm=c(4.5,4.5,10,30,4),y_bp=c(100,900,200,300,400),age_kyr=1)
r <- match_proxy_depth(p,s,c('v','total_count'),'fixture','fixture.tsv')
x <- r$values[variable=='v']
stopifnot(x[sample_id=='a',value]==8,x[sample_id=='b',value]==8,x[sample_id=='c',value]==20,
          x[sample_id=='c',interpolation_fraction]==.375,x[sample_id=='c',bracket_width_cm]==16,
          !'d' %in% x$sample_id, x[sample_id=='e',match_method]=='exact_depth',
          r$coverage[sample_id=='d' & variable=='v',status]=='outside_proxy_range',
          r$coverage[sample_id=='c' & variable=='total_count',status]=='discrete_variable_no_interpolation')
# Missing depths do not shift sample identities; duplicate source depths retain IDs.
p2 <- data.table(core='GeoB25202',depth_in_core_cm=c(0,0,1,2,3,40),v=c(0,2,2,4,6,80))
s2 <- copy(s[1:2]);s2[,depth_in_core_cm:=c(NA,10)]
y <- match_proxy_depth(p2,s2,'v','fixture','fixture.tsv')
stopifnot(nrow(y$values)==1,y$values$sample_id=='b',y$values$large_gap,
          y$coverage[sample_id=='a',status]=='missing_sample_depth')
print('PASS: aliases, depth tolerance, interpolation, provenance, no extrapolation, discrete values, missing depths and large-gap flag')
