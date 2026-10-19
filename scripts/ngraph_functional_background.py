"""Freeze independent annotation units and their label-independent backgrounds.

Only successfully processed full proteomes establish testable absences. Legacy
and retrieved-but-unprocessed references remain outside the statistical null.
"""
import numpy as np
import pandas as pd


def prepare_background(mapping, memberships, processed, retention, abundance, metadata, *, evidence_scope="fresh_full_proteome"):
    if evidence_scope not in {"fresh_full_proteome","recorded_annotation_catalog"}:
        raise ValueError("Unknown annotation evidence scope")
    catalog=evidence_scope=="recorded_annotation_catalog"
    if not mapping.taxon.is_unique or not memberships.taxon.is_unique:
        raise ValueError('Taxon mapping and membership must be unique')
    labels=memberships.set_index('taxon').module_id
    inventory=mapping.copy()
    inventory['module_id']=inventory.taxon.map(labels)
    inventory['processed_full_proteome']=inventory.genome_id.isin(processed) & (not catalog)
    inventory['available_annotation_profile']=inventory.genome_id.isin(processed)
    inventory['evidence_scope']=evidence_scope
    inventory['background_status']='unassigned_inventory_taxon'
    assigned=inventory.module_id.notna()
    inventory.loc[assigned,'background_status']='no_catalog_annotation_profile' if catalog else 'no_fresh_full_proteome_annotation'
    candidates=assigned & inventory.available_annotation_profile & inventory.domain.ne('d__Viruses') & inventory.mapping_status.eq('exact_native_mapping')
    inventory.loc[assigned & inventory.domain.eq('d__Viruses'),'background_status']='viral_separate_background'
    inventory.loc[assigned & inventory.mapping_status.ne('exact_native_mapping'),'background_status']='unresolved_reference_mapping'
    available=inventory.loc[candidates].copy()
    collisions=available.groupby('genome_id').module_id.nunique()
    conflicting=set(collisions[collisions.gt(1)].index)
    inventory.loc[candidates & inventory.genome_id.isin(conflicting),'background_status']='shared_reference_conflicting_modules'
    available=available.loc[~available.genome_id.isin(conflicting)].sort_values('taxon')
    duplicates=available.duplicated('genome_id')
    inventory.loc[inventory.taxon.isin(available.loc[duplicates,'taxon']),'background_status']='shared_reference_collapsed_alias'
    available=available.loc[~duplicates].copy()
    inventory.loc[inventory.taxon.isin(available.taxon),'background_status']='eligible_independent_catalog_reference' if catalog else 'eligible_independent_fresh_reference'
    retention=retention.set_index('subspecies')
    positive=abundance.groupby(metadata.set_index('sample').reindex(abundance.index).physical_core).max().gt(0).sum()
    available['prevalence_samples']=available.taxon.map(retention.prevalence_samples).astype(float)
    available['tad_support']=np.where(available.taxon.map(retention.tad_positive_samples).astype(float).gt(0),'tad_positive','read_fallback_only')
    available['physical_core_count']=available.taxon.map(positive).astype(float)
    if not np.isfinite(available[['prevalence_samples','physical_core_count']].to_numpy(float)).all():
        raise ValueError('Fresh reference lacks known detection covariates')
    denominator=inventory.loc[assigned & inventory.domain.ne('d__Viruses')].groupby('module_id').size()
    eligible_counts=available.groupby('module_id').size()
    coverage=pd.DataFrame({'module_id':sorted(labels.unique())})
    coverage['nonviral_assigned_taxa']=coverage.module_id.map(denominator).fillna(0).astype(int)
    coverage['independent_fresh_references']=coverage.module_id.map(eligible_counts).fillna(0).astype(int)
    coverage['annotation_coverage']=coverage.independent_fresh_references/coverage.nonviral_assigned_taxa.replace(0,np.nan)
    coverage['minimum_publication_coverage']=.70
    coverage['coverage_pass']=coverage.annotation_coverage.ge(.70)
    if catalog:coverage=coverage.rename(columns={"independent_fresh_references":"independent_catalog_references"})
    return available.set_index('taxon'), inventory, coverage


def capability_matrix(capabilities, background, *, threshold=1.0):
    """One frozen unit universe; unknown cells exclude a function globally."""
    if not 0<threshold<=1:
        raise ValueError('Capability threshold must lie within (0,1]')
    fresh=capabilities.loc[capabilities.status.eq('fresh_full_proteome_processed') & capabilities.function_namespace.eq('KEGG_MODULE') & capabilities.taxon.isin(background.index)].copy()
    if fresh[['taxon','function_id']].duplicated().any():
        raise ValueError('Duplicate unit/function capability decisions')
    fresh['carriage']=fresh.is_carrier if threshold==1 else fresh.completeness.ge(threshold)
    matrix=fresh.pivot(index='taxon',columns='function_id',values='carriage').reindex(background.index)
    known=matrix.notna().all()
    qc=pd.DataFrame({'function_id':matrix.columns,'background_units':len(background),'known_units':matrix.notna().sum().to_numpy(),'eligible_complete_background':known.to_numpy(),'capability_threshold':threshold})
    return matrix.loc[:,known].astype(bool),qc
