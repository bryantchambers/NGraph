"""Unweighted module enrichment against an existing recorded annotation catalog.

The null tests association of recorded annotation profiles with frozen module
membership. It does not infer biological absence from an unreported KO, establish
metabolic activity, or replace the annotation catalog with a proteome pilot.
"""
import argparse,hashlib,importlib.util,importlib.metadata,json,logging,sys
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from ngraph_functional_background import prepare_background
from ngraph_functional_statistics import ModuleDefinition,enrich_capabilities,ko_fisher_baseline
from ngraph_functional_profiles import module_profiles,module_centrality
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('functional_io',ROOT/'scripts/17_ngraph_module_functions.py');io=importlib.util.module_from_spec(spec);spec.loader.exec_module(io)

def catalog_capabilities(annotations,mapping,definitions):
    evidence=annotations[annotations.feature_namespace.eq('KEGG_KO')]
    kos=evidence.groupby('taxon').feature_id.apply(set).to_dict()
    provenance=evidence.groupby('taxon').agg(source_path=('source_path','first'),source_row=('source_row','first')).to_dict('index')
    parsers={};qc=[]
    for definition in definitions.itertuples():
        try:parsers[definition.module_id]=ModuleDefinition(definition.module_definition);status='parsed'
        except ValueError:status='unresolved_grammar'
        qc.append(dict(function_id=definition.module_id,status=status,definition_sha256=definition.definition_sha256))
    rows=[]
    for taxon in mapping.itertuples():
        if taxon.domain=='d__Viruses' or taxon.taxon not in kos:continue
        for definition in definitions.itertuples():
            parser=parsers.get(definition.module_id)
            if parser is None:continue
            result=parser.evaluate(kos[taxon.taxon])
            rows.append(dict(taxon=taxon.taxon,genome_id=taxon.genome_id,function_id=definition.module_id,function_namespace=definition.module_namespace,
                completeness=result['completeness'],is_carrier=result['is_complete'],partial_support=result['completeness']>=.75,
                status='unresolved_definition' if result['unresolved_definition'] else 'recorded_catalog_supported_framework',
                annotation_source='unknown_legacy',evidence_scope='recorded_annotation_catalog',
                source_path=provenance[taxon.taxon]['source_path'],source_row=provenance[taxon.taxon]['source_row']))
    return pd.DataFrame(rows),pd.DataFrame(qc)

def catalog_matrix(capabilities,background):
    selected=capabilities[capabilities.function_namespace.eq('KEGG_MODULE') & capabilities.taxon.isin(background.index)].copy()
    selected['known_carriage']=selected.is_carrier.astype(object)
    selected.loc[selected.status.eq('unresolved_definition'),'known_carriage']=np.nan
    matrix=selected.pivot(index='taxon',columns='function_id',values='known_carriage').reindex(background.index)
    known=matrix.notna().all()
    qc=pd.DataFrame(dict(function_id=matrix.columns,background_units=len(background),known_units=matrix.notna().sum().to_numpy(),eligible_complete_background=known.to_numpy()))
    return matrix.loc[:,known].astype(bool),qc

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--branch',required=True);ap.add_argument('--reference-snapshot',default='functional_20261008');ap.add_argument('--snapshot',required=True)
    ap.add_argument('--threshold',default='prev_10');ap.add_argument('--method',default='pearson');ap.add_argument('--permutations',type=int);ap.add_argument('--bootstraps',type=int,default=200)
    args=ap.parse_args()
    for value in [args.branch,args.reference_snapshot,args.snapshot,args.threshold,args.method]:
        if Path(value).name!=value or value in ('.','..'):raise ValueError('Invalid run identifier')
    branch=ROOT/'results/ngraph'/args.branch;reference=ROOT/'data/reference/functional'/args.reference_snapshot
    output=branch/'functional_enrichment'/args.threshold/args.method/'vgae'/args.snapshot
    if (output/'manifest.json').exists():raise SystemExit('Analysis snapshot is immutable; choose a new identifier')
    tables=output/'tables';tables.mkdir(parents=True,exist_ok=True);(output/'indexes').mkdir(exist_ok=True)
    log=ROOT/'logs'/args.branch/f'catalog_enrichment_{args.snapshot}.log';log.parent.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s',handlers=[logging.FileHandler(log),logging.StreamHandler()])
    source_paths=[Path(__file__),ROOT/'scripts/17_ngraph_module_functions.py',ROOT/'scripts/ngraph_functional_statistics.py',ROOT/'scripts/ngraph_functional_profiles.py',ROOT/'scripts/ngraph_functional_background.py']
    initial_sources={str(p.relative_to(ROOT)):io.digest(p) for p in source_paths}
    inputs=branch/'functional_inputs'/args.threshold/'tables';combo=branch/'deep_modules'/args.threshold/args.method/'tables'
    clr=io.read(inputs/'clr_samples_by_taxa.tsv.gz').set_index('sample').astype(float)
    abundance=io.read(inputs/'abundance_samples_by_taxa.tsv.gz').set_index('sample').astype(float).reindex(index=clr.index,columns=clr.columns)
    metadata=io.read(inputs/'sample_metadata.tsv')
    for column in ['depth_in_core_cm','y_bp']:metadata[column]=pd.to_numeric(metadata[column],errors='coerce')
    memberships=io.read(combo/'vgae_taxon_modules.tsv').rename(columns={'module_kmeans':'module_id'})
    mapping=io.read(reference/'tables/taxon_reference_mapping.tsv');mapping=mapping[mapping.taxon.isin(clr.columns)]
    annotations=io.read(reference/'tables/reference_annotations.tsv.gz');annotations=annotations[annotations.taxon.isin(mapping.taxon)]
    definitions=io.read(reference/'tables/module_definitions.tsv')
    eligible_genomes=set(annotations.loc[annotations.feature_namespace.eq('KEGG_KO'),'genome_id'])
    background,inventory,coverage=prepare_background(mapping,memberships,eligible_genomes,io.read(branch/args.threshold/'tables/ngraph_taxon_retention.tsv'),abundance,metadata,evidence_scope='recorded_annotation_catalog')
    logging.info('Catalog background: %s independent references; %s assigned taxa',len(background),len(memberships))
    capabilities,definition_qc=catalog_capabilities(annotations,mapping,definitions)
    matrix,function_qc=catalog_matrix(capabilities,background)
    logging.info('Resolved KEGG definitions: %s; computing unweighted fixed-budget permutations',len(matrix.columns))
    results,primary=enrich_capabilities(matrix,background.module_id,background.reset_index(),permutations=args.permutations,
        annotation_coverage=coverage.set_index('module_id').annotation_coverage.to_dict(),declared_modules=memberships.module_id.unique(),
        progress=lambda done,total:logging.info('Primary permutations %s/%s',done,total))
    if results.empty:raise ValueError('No globally testable function sets')
    results['function_namespace']='KEGG_MODULE';results['function_name']=results.function_id.map(definitions.set_index('module_id').module_name)
    results['capability_threshold']=1.;results['db_snapshot']=args.snapshot;results['evidence_scope']='recorded_annotation_catalog'
    results['annotation_confidence']='existing_catalog_unknown_original_release';results['abundance_weighted']=False
    results=results.sort_values(['q_value','permutation_z_score','prevalence_difference'],ascending=[True,False,False],na_position='last')
    results['rank_within_module']=results.groupby('module_id').cumcount()+1
    members=io.supporting_members(capabilities,memberships,annotations,definitions,args.snapshot)
    members['evidence_scope']='recorded_annotation_catalog'
    profiles=module_profiles(clr,abundance,metadata,memberships)
    logging.info('Computing %s fixed-membership depth-block centrality replicates',args.bootstraps)
    centrality=module_centrality(io.read(combo/'hetero_taxon_taxon_edges.tsv'),memberships,clr,abundance,metadata,bootstraps=args.bootstraps)
    function_profiles=io.functional_profiles(clr,abundance,metadata,capabilities,mapping)
    records={'module_functions.tsv':results,'module_function_members.tsv':members,'background_inventory.tsv':inventory,'background_coverage.tsv':coverage,
        'independent_annotation_units.tsv':background.reset_index(),'function_background_qc.tsv':function_qc,'definition_qc.tsv':definition_qc,
        'capabilities.tsv.gz':capabilities,'reference_annotations.tsv.gz':annotations,'function_definitions.tsv':definitions,'taxon_reference_mapping.tsv':mapping,
        'carrier_sets.tsv':members[['function_id','taxon']].drop_duplicates(),'module_profiles.tsv':profiles,'function_profiles.tsv':function_profiles,'module_centrality.tsv':centrality}
    for name,frame in records.items():io.atomic_table(frame,tables/name)
    io.index_annotations(annotations,output/'indexes/reference_annotations.sqlite');io.draw_figures(results,profiles,centrality,output)
    final_sources={str(p.relative_to(ROOT)):io.digest(p) for p in source_paths}
    if final_sources!=initial_sources:raise RuntimeError('Source changed during execution; rerun before completing snapshot')
    input_paths=[inputs/'clr_samples_by_taxa.tsv.gz',inputs/'abundance_samples_by_taxa.tsv.gz',inputs/'sample_metadata.tsv',combo/'vgae_taxon_modules.tsv',combo/'hetero_taxon_taxon_edges.tsv',branch/args.threshold/'tables/ngraph_taxon_retention.tsv',reference/'tables/taxon_reference_mapping.tsv',reference/'tables/reference_annotations.tsv.gz',reference/'tables/module_definitions.tsv']
    manifest=dict(schema='functional-2',branch=args.branch,threshold=args.threshold,method=args.method,model='vgae',db_snapshot=args.snapshot,reference_snapshot=args.reference_snapshot,
        run_status='completed',created_utc=datetime.now(timezone.utc).isoformat(),seed=42,runtime_command=sys.argv,
        assigned_taxa=len(memberships),inventory_taxa=len(clr.columns),independent_annotation_units=len(background),
        annotation_status='existing_catalog_enrichment_unknown_original_release',evidence_scope='recorded_annotation_catalog',
        negative_interpretation='No complete support recorded in this catalog; not a biological absence claim',
        primary=primary,qualified_associations=int(results.publish_kg.sum()),abundance_weighting=False,
        weighted_ks_status='planned_next_version_not_computed',affinity_status='planned_next_version_not_computed',
        abundance_mode=metadata.abundance_mode.iloc[0],kg_scope='qualified_associations_of_recorded_catalog_support_with_native_provenance',
        source_sha256=initial_sources,source_unchanged_during_execution=True,input_sha256={str(p.relative_to(ROOT)):io.digest(p) for p in input_paths},
        artifacts={str(p.relative_to(output)):io.digest(p) for p in tables.iterdir() if p.is_file()},
        packages={p:importlib.metadata.version(p) for p in ['numpy','pandas','scipy','matplotlib']})
    io.json_write(output/'manifest.json',manifest);(output/'reports').mkdir(exist_ok=True)
    (output/'reports/FUNCTIONAL_ANALYSIS_REPORT.md').write_text('# Unweighted catalog enrichment\n\n'+f'{len(background)} independent existing reference annotations; {primary["hypotheses"]} module/function tests; {primary["permutations"]} permutations; {manifest["qualified_associations"]} gated associations.\n\n'+'Results test over-representation of recorded functional support under a taxonomy/detection-conditioned whole-profile null. Original annotation release is unknown. Catalog negatives are not biological absence claims. Empirical p-values and whole-family BH q-values determine significance; permutation Z-scores summarize direction and departure from the actual null. BY and Fisher statistics are separately labelled baselines. Abundance profiles and network centrality are separate exploratory summaries. Weighted KS is planned for the next version and was not run.\n')
    print(json.dumps({k:manifest[k] for k in ['branch','db_snapshot','independent_annotation_units','qualified_associations','weighted_ks_status']},indent=2))
if __name__=='__main__':main()
