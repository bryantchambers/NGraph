#!/usr/bin/env python3
"""Offline reference-supported capability, central-member and depth analysis.

Legacy positives remain descriptive; only completed full-proteome annotations
enter the prespecified enrichment background. Output snapshots are immutable.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import numpy as np
import pandas as pd
from scipy.stats import fisher_exact
from ngraph_discovery_common import project_root, normalize_threshold_label
from ngraph_functional_statistics import ModuleDefinition, enrich_capabilities, ks_enrichment, bh_adjust, ko_fisher_baseline
from ngraph_functional_profiles import module_profiles, module_centrality, module_affinity, set_logratio, physical_core

from ngraph_functional_background import prepare_background, capability_matrix

ROOT=project_root()
RESULT_COLUMNS=["module_id","function_id","function_namespace","function_name","test_method",
    "capability_threshold","carrier_count","module_annotated_count","background_carrier_count",
    "background_annotated_count","odds_ratio","prevalence_difference","statistic","p_value","q_value",
    "annotation_coverage","exchangeable_fraction","status","publish_kg","db_snapshot"]
MEMBER_COLUMNS=["module_id","function_id","taxon","genome_id","completeness","is_carrier","gene_ids",
    "ko_ids","annotation_source","annotation_status","source_path","source_row","db_snapshot"]


def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()


def read(path, **kwargs):
    return pd.read_csv(path,sep="\t",keep_default_na=False,**kwargs)


def atomic_table(frame,path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(".pending-"+path.name)
    frame.to_csv(temp,sep="\t",index=False,compression="gzip" if path.suffix==".gz" else None)
    temp.replace(path)


def json_write(path,value):
    path=Path(path); temp=path.with_name(".pending-"+path.name)
    temp.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+"\n"); temp.replace(path)


def annotation_selection(reference):
    legacy=read(reference/"tables/reference_annotations.tsv.gz")
    run_path=reference/"annotation_run_kofam.json"
    fresh_path=reference/"tables/reference_annotations_kofam.tsv.gz"
    processed=set()
    if run_path.exists() and fresh_path.exists():
        run=json.loads(run_path.read_text())
        from ngraph_functional_references import parse_kofam
        retrieval=read(reference/"tables/retrieval_manifest.tsv")
        database_path=Path(run.get("database_fingerprint",{}).get("manifest_path",""))
        if not database_path.is_file():
            raise ValueError("Fresh annotations require a frozen database hash manifest")
        database=json.loads(database_path.read_text())
        if database.get("content_sha256")!=run.get("database_fingerprint",{}).get("content_sha256"):
            raise ValueError("Database snapshot fingerprint mismatch")
        reconstructed=[]
        for entry in run.get("runs",[]):
            output=Path(entry["output_path"])
            marker=output.with_name(entry["genome_id"]+".completed.json")
            if not marker.exists() or not output.exists():
                continue
            proof=json.loads(marker.read_text())
            if proof.get("output_sha256")!=digest(output) or proof.get("signature",{}).get("proteome_sha256")!=entry.get("proteome_sha256"):
                raise ValueError("Changed or incomplete full-proteome annotation evidence")
            if not entry.get("database_content_sha256") or entry.get("tool_version")!="1.3.0":
                raise ValueError("Fresh KO annotation lacks frozen database/tool provenance")
            keys=["command","proteome_sha256","db_snapshot","database_content_sha256","tool_version"]
            if proof.get("signature")!={key:entry.get(key) for key in keys}:
                raise ValueError("Full-proteome execution signature mismatch")
            if entry["database_content_sha256"]!=database["content_sha256"]:
                raise ValueError("Full-proteome database fingerprint mismatch")
            matches=retrieval.loc[retrieval.genome_id.eq(entry["genome_id"]) & retrieval.proteome_sha256.eq(entry["proteome_sha256"])]
            if matches.empty:
                raise ValueError("Fresh annotations lack matching retrieved reference")
            record=matches.iloc[-1]; fasta=Path(record.proteome_path)
            if not fasta.is_file() or digest(fasta)!=entry["proteome_sha256"]:
                raise ValueError("Fresh proteome differs from retrieved reference")
            with fasta.open() as handle:
                protein_ids=[line[1:].split()[0] for line in handle if line.startswith(">")]
                protein_count=len(protein_ids)
            if protein_count!=int(record.protein_count) or protein_count==0:
                raise ValueError("Fresh full-proteome sequence-count mismatch")
            protein_id_set=set(protein_ids)
            if len(protein_id_set)!=protein_count:
                raise ValueError("Full proteome has duplicate native sequence IDs")
            native=list(parse_kofam(output,entry["taxon"],entry["genome_id"],entry["db_snapshot"]))
            if any(row["gene_id"] not in protein_id_set for row in native):
                raise ValueError("Fresh KO output contains IDs outside the verified proteome")
            reconstructed.extend(native)
            processed.add(entry["genome_id"])
        fresh=read(fresh_path)
        fresh=fresh.loc[fresh.genome_id.isin(processed)]
        verified=pd.DataFrame(reconstructed,columns=fresh.columns)
        columns=["taxon","genome_id","gene_id","feature_namespace","feature_id","score","evalue","threshold","source_path","source_row","db_snapshot","tool_version"]
        def canonical(frame):
            return sorted(tuple(str(v) for v in row) for row in frame[columns].itertuples(index=False,name=None))
        if canonical(fresh)!=canonical(verified):
            raise ValueError("Fresh KO inventory differs from verified native annotation outputs")
        fresh=verified
        selected=pd.concat([legacy.loc[~legacy.genome_id.isin(processed)],fresh],ignore_index=True)
    else:
        selected=legacy
    return selected,processed


def capabilities_from_annotations(annotations,mapping,definitions,legacy_completeness,processed):
    kos=annotations.loc[annotations.feature_namespace.eq("KEGG_KO")].groupby("taxon").feature_id.apply(set).to_dict()
    observed={(row.taxon,row.module_id):row for row in legacy_completeness.itertuples()}
    parsed={}
    definition_status=[]
    for row in definitions.itertuples():
        try:
            parsed[row.module_id]=ModuleDefinition(row.module_definition)
            status="parsed_frozen_definition"
        except ValueError as error:
            status="unresolved_definition:"+str(error)
        definition_status.append(dict(function_id=row.module_id,status=status,definition_sha256=row.definition_sha256))
    native_paths=annotations.groupby("taxon",sort=False).source_path.first().to_dict()
    rows=[]
    for taxon in mapping.itertuples():
        if taxon.domain=="d__Viruses" or taxon.mapping_status!="exact_native_mapping": continue
        fresh=taxon.genome_id in processed
        for definition in definitions.itertuples():
            legacy=observed.get((taxon.taxon,definition.module_id))
            if not fresh and legacy is None: continue
            if definition.module_id not in parsed:
                continue
            evaluated=parsed[definition.module_id].evaluate(kos.get(taxon.taxon,set()))
            status="fresh_full_proteome_processed" if fresh else "legacy_module_scoped_unknown_release"
            if evaluated["unresolved_definition"]: status="unresolved_definition"
            rows.append(dict(taxon=taxon.taxon,genome_id=taxon.genome_id,function_id=definition.module_id,
                function_namespace=definition.module_namespace,completeness=evaluated["completeness"],
                is_carrier=evaluated["is_complete"],partial_support=evaluated["completeness"]>=.75,
                essential_steps=evaluated["essential_steps"],fulfilled_steps=evaluated["fulfilled_steps"],
                missing_essential_kos=";".join(evaluated["missing_kos"]),status=status,
                annotation_source="fresh_reference_kofam" if fresh else "unknown_legacy",
                source_path=str(native_paths.get(taxon.taxon, "") if fresh else getattr(legacy,"source_path","")),
                source_row=getattr(legacy,"source_row","") if not fresh else "",
                legacy_pathwise_completeness=getattr(legacy,"pathwise_module_completeness",np.nan)))
    return pd.DataFrame(rows),pd.DataFrame(definition_status)


def reference_path(legacy,annotations,taxon):
    if legacy is not None: return legacy.source_path
    matched=annotations.loc[annotations.taxon.eq(taxon),"source_path"]
    return matched.iloc[0] if len(matched) else ""


def descriptive_results(capabilities,memberships,definitions,mapping,snapshot):
    assigned=memberships.set_index("taxon").module_id
    nonviral=set(mapping.loc[mapping.domain.ne("d__Viruses"),"taxon"])
    total_members=memberships.loc[memberships.taxon.isin(nonviral)].groupby("module_id").size()
    capabilities=capabilities.loc[capabilities.taxon.isin(assigned.index) & capabilities.status.ne("unresolved_definition")].copy()
    capabilities["module_id"]=capabilities.taxon.map(assigned)
    names=definitions.set_index("module_id")
    rows=[]
    for function,group in capabilities.groupby("function_id",sort=True):
        for module in sorted(assigned.unique()):
            inside=group.loc[group.module_id.eq(module)]
            outside=group.loc[group.module_id.ne(module)]
            a=int(inside.is_carrier.sum()); c=int(outside.is_carrier.sum())
            b=len(inside)-a; d=len(outside)-c
            odds=fisher_exact([[a,b],[c,d]],alternative="greater").statistic if len(inside) and len(outside) else np.nan
            difference=a/len(inside)-c/len(outside) if len(inside) and len(outside) else np.nan
            rows.append(dict(module_id=module,function_id=function,function_namespace=names.loc[function,"module_namespace"],
                function_name=names.loc[function,"module_name"],test_method="descriptive_reference_support",
                capability_threshold=1.0,carrier_count=a,module_annotated_count=len(inside),background_carrier_count=c,
                background_annotated_count=len(outside),odds_ratio=odds,prevalence_difference=difference,
                statistic=difference,p_value=np.nan,q_value=np.nan,
                annotation_coverage=len(inside)/max(1,total_members.get(module,0)),exchangeable_fraction=np.nan,
                status="legacy_only_descriptive",publish_kg=False,db_snapshot=snapshot))
    return pd.DataFrame(rows,columns=RESULT_COLUMNS)


def supporting_members(capabilities,memberships,annotations,definitions,snapshot):
    assigned=memberships.set_index("taxon").module_id
    definition_kos={r.module_id:set(__import__("re").findall(r"K\d{5}",str(r.module_definition))) for r in definitions.itertuples()}
    by_taxon={taxon:group for taxon,group in annotations.groupby("taxon",sort=False)}
    rows=[]
    for capability in capabilities.loc[capabilities.is_carrier & capabilities.taxon.isin(assigned.index)].itertuples():
        evidence=by_taxon.get(capability.taxon)
        if evidence is None: continue
        native=evidence.loc[evidence.feature_namespace.eq("KEGG_KO") & evidence.feature_id.isin(definition_kos[capability.function_id])]
        rows.append(dict(module_id=assigned[capability.taxon],function_id=capability.function_id,taxon=capability.taxon,
            genome_id=capability.genome_id,completeness=capability.completeness,is_carrier=True,
            gene_ids=";".join(sorted(native.gene_id.astype(str).unique())),ko_ids=";".join(sorted(native.feature_id.unique())),
            annotation_source=capability.annotation_source,annotation_status=capability.status,
            source_path=";".join(sorted(native.source_path.unique())),source_row=";".join(sorted(native.source_row.astype(str).unique())),
            db_snapshot=snapshot))
    return pd.DataFrame(rows,columns=MEMBER_COLUMNS)


def functional_profiles(clr,abundance,metadata,capabilities,mapping):
    nonviral=set(mapping.loc[mapping.domain.ne("d__Viruses"),"taxon"])
    meta=metadata.set_index("sample").reindex(clr.index)
    rows=[]
    for function,group in capabilities.loc[capabilities.status.ne("unresolved_definition")].groupby("function_id",sort=True):
        universe=[t for t in group.taxon.unique() if t in clr and t in nonviral]
        members=group.loc[group.is_carrier,"taxon"].tolist()
        if len(members)<5 or len(universe)-len(members)<5: continue
        ratio=set_logratio(clr,members,universe)
        for sample in clr.index:
            info=meta.loc[sample]
            observed=set(abundance.columns[abundance.loc[sample].gt(0)]) & nonviral
            coverage=len(observed & set(universe))/max(1,len(observed))
            rows.append(dict(function_id=function,sample=sample,core=info.core,physical_core=physical_core(info.core),
                depth_cm=info.depth_in_core_cm,y_bp=info.y_bp,age_kyr=info.y_bp/1000,
                logratio=ratio.loc[sample],ssgsea_score=np.nan,annotation_coverage=coverage,
                carrier_taxa=len(members),annotated_universe=len(universe),
                status="reference_supported_potential_profile",abundance_mode=info.abundance_mode))
    return pd.DataFrame(rows)


def index_annotations(annotations,path):
    connection=sqlite3.connect(path)
    try:
        annotations.to_sql("annotations",connection,index=False,if_exists="replace",chunksize=10000)
        connection.execute("CREATE INDEX IF NOT EXISTS annotations_taxon ON annotations(taxon)")
        connection.execute("CREATE INDEX IF NOT EXISTS annotations_feature ON annotations(feature_namespace,feature_id)")
        connection.commit()
    finally: connection.close()


def draw_figures(results,profiles,centrality,output):
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    figures=output/"figures"; figures.mkdir(exist_ok=True)
    chosen=results.loc[results.carrier_count.ge(5)].sort_values("prevalence_difference",ascending=False)
    names=chosen.drop_duplicates("function_id").head(20).function_id.tolist()
    if names:
        chosen=chosen.loc[chosen.function_id.isin(names)]
        modules=sorted(chosen.module_id.unique())
        fig,ax=plt.subplots(figsize=(max(7,len(modules)),10))
        points=ax.scatter(chosen.module_id.map({m:i for i,m in enumerate(modules)}),
            chosen.function_id.map({f:i for i,f in enumerate(names)}),s=np.clip(chosen.carrier_count,5,150),
            c=chosen.prevalence_difference,cmap="PuOr",vmin=-1,vmax=1,alpha=.85)
        labels={r.function_id:r.function_name for r in chosen.itertuples()}
        ax.set_yticks(range(len(names)),[f+" · "+str(labels[f])[:65] for f in names]); ax.set_xticks(range(len(modules)),modules)
        ax.set_title("Reference-supported functional frameworks\nSize: carriers; colour: frequency difference")
        fig.colorbar(points,ax=ax,label="Carrier-frequency difference")
        if results.test_method.eq("descriptive_reference_support").all():
            fig.text(.02,.005,"Legacy reference evidence; no enrichment significance claims",fontsize=9)
        fig.tight_layout(); fig.savefig(figures/"module_function_overview.png",dpi=150); plt.close(fig)
    if len(profiles):
        cores=sorted(profiles.core.unique()); fig,axes=plt.subplots(1,len(cores),figsize=(4*len(cores),7),sharey=False,squeeze=False)
        for ax,core in zip(axes[0],cores):
            for module,group in profiles.loc[profiles.core.eq(core)].groupby("module_id",sort=True):
                group=group.sort_values("depth_cm")
                ax.plot(group.mean_clr,group.depth_cm,"o-",markersize=2,label=module,alpha=.8)
            ax.invert_yaxis();ax.set_title(core);ax.set_xlabel("Mean member CLR");ax.set_ylabel("Depth (cm)")
        axes[0][-1].legend(fontsize=8);fig.tight_layout();fig.savefig(figures/"module_core_profiles.png",dpi=150);plt.close(fig)
    if len(centrality):
        selected=centrality.loc[centrality.core.eq("all")].sort_values("positive_strength",ascending=False).head(20).iloc[::-1]
        fig,ax=plt.subplots(figsize=(10,7));ax.barh(selected.taxon,selected.positive_strength,color="#7965a8")
        ax.set_xlabel("Positive within-module strength (equal physical-core summary)");ax.set_title("Central members · descriptive network evidence")
        fig.tight_layout();fig.savefig(figures/"module_central_members.png",dpi=150);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch",required=True);parser.add_argument("--threshold",default="prev_10")
    parser.add_argument("--method",default="pearson");parser.add_argument("--model",choices=["vgae"],default="vgae")
    parser.add_argument("--reference-snapshot",required=True);parser.add_argument("--snapshot",required=True)
    parser.add_argument("--bootstraps",type=int,default=200);parser.add_argument("--permutations",type=int)
    parser.add_argument("--ks-permutations",type=int,default=100000)
    args=parser.parse_args();threshold=normalize_threshold_label(args.threshold)
    for value in [args.branch,args.reference_snapshot,args.snapshot,args.method]:
        if not value or Path(value).name!=value or value in (".",".."): raise ValueError("Invalid scoped identifier")
    reference=ROOT/"data/reference/functional"/args.reference_snapshot
    branch=ROOT/"results/ngraph"/args.branch
    output=branch/"functional_enrichment"/threshold/args.method/args.model/args.snapshot
    if (output/"manifest.json").exists():
        prior=json.loads((output/"manifest.json").read_text())
        if prior.get("run_status")=="completed": raise SystemExit("Completed functional snapshot is immutable; select a new --snapshot")
    tables=output/"tables";tables.mkdir(parents=True,exist_ok=True);(output/"indexes").mkdir(exist_ok=True)
    log=ROOT/"logs"/args.branch/("module_functions_"+args.snapshot+".log");log.parent.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(message)s",handlers=[logging.FileHandler(log),logging.StreamHandler()])
    logger=logging.getLogger("functional")
    inputs=branch/"functional_inputs"/threshold/"tables";combo=branch/"deep_modules"/threshold/args.method/"tables"
    clr=read(inputs/"clr_samples_by_taxa.tsv.gz").set_index("sample").astype(float)
    abundance=read(inputs/"abundance_samples_by_taxa.tsv.gz").set_index("sample").astype(float).reindex(index=clr.index,columns=clr.columns)
    metadata=read(inputs/"sample_metadata.tsv");metadata["depth_in_core_cm"]=pd.to_numeric(metadata.depth_in_core_cm,errors="coerce")
    metadata["y_bp"]=pd.to_numeric(metadata.y_bp,errors="coerce")
    memberships=read(combo/"vgae_taxon_modules.tsv").rename(columns={"module_kmeans":"module_id"})
    mapping=read(reference/"tables/taxon_reference_mapping.tsv");mapping=mapping.loc[mapping.taxon.isin(clr.columns)]
    definitions=read(reference/"tables/module_definitions.tsv")
    legacy=read(reference/"tables/legacy_module_completeness.tsv.gz")
    source_paths=[Path(__file__),ROOT/"scripts/ngraph_functional_statistics.py",ROOT/"scripts/ngraph_functional_profiles.py",ROOT/"scripts/ngraph_functional_background.py",ROOT/"scripts/ngraph_functional_references.py"]
    initial_source_hashes={str(p.relative_to(ROOT)):digest(p) for p in source_paths}
    annotations,processed=annotation_selection(reference)
    annotations=annotations.loc[annotations.taxon.isin(clr.columns)]
    logger.info("%d assigned taxa; %d native annotations; %d fully reannotated references",len(memberships),len(annotations),len(processed))
    capabilities,definition_qc=capabilities_from_annotations(annotations,mapping,definitions,legacy,processed)
    atomic_table(capabilities,tables/"capabilities.tsv.gz");atomic_table(definition_qc,tables/"definition_qc.tsv")
    atomic_table(mapping,tables/"taxon_reference_mapping.tsv");atomic_table(annotations,tables/"reference_annotations.tsv.gz")
    atomic_table(definitions,tables/"function_definitions.tsv")
    index_annotations(annotations,output/"indexes/reference_annotations.sqlite")
    functions=descriptive_results(capabilities,memberships,definitions,mapping,args.snapshot)
    primary_manifest={"status":"not_computed_no_fresh_full_proteome_inventory","hypotheses":0,"permutations":0}
    available,background_inventory,coverage_table=prepare_background(mapping,memberships,processed,
        read(branch/threshold/"tables/ngraph_taxon_retention.tsv"),abundance,metadata)
    ko_evidence=annotations.loc[annotations.feature_namespace.eq("KEGG_KO") & annotations.genome_id.isin(processed)]
    available["ko_richness"]=available.index.map(ko_evidence.groupby("taxon").feature_id.nunique()).fillna(0).astype(float)
    quality_path=reference/"tables/reference_quality.tsv"
    quality=read(quality_path).drop_duplicates("genome_id").set_index("genome_id").quality_status if quality_path.exists() else pd.Series(dtype=str)
    available["reference_quality_status"]=available.genome_id.map(quality).fillna("unknown")
    atomic_table(available.reset_index(),tables/"independent_annotation_units.tsv")
    atomic_table(background_inventory,tables/"background_inventory.tsv")
    atomic_table(coverage_table,tables/"background_coverage.tsv")
    matrix,function_background_qc=capability_matrix(capabilities,available)
    atomic_table(function_background_qc,tables/"function_background_qc.tsv")
    if len(available) and len(matrix.columns):
        coverage=coverage_table.set_index("module_id").annotation_coverage.to_dict()
        primary,primary_manifest=enrich_capabilities(matrix,available.module_id,available.reset_index(),permutations=args.permutations,
            annotation_coverage=coverage,declared_modules=memberships.module_id.unique(),progress=lambda done,total:logger.info("Primary permutations %d/%d",done,total))
        if len(primary):
            name_lookup=definitions.set_index("module_id").module_name
            primary["function_namespace"]="KEGG_MODULE";primary["function_name"]=primary.function_id.map(name_lookup)
            primary["capability_threshold"]=1.;primary["db_snapshot"]=args.snapshot
            functions=pd.concat([functions,primary],ignore_index=True)
        partial,partial_qc=capability_matrix(capabilities,available,threshold=.75)
        atomic_table(partial_qc,tables/"partial_function_background_qc.tsv")
        sensitivity,sensitivity_manifest=enrich_capabilities(partial,available.module_id,available.reset_index(),
            permutations=args.permutations,annotation_coverage=coverage,declared_modules=memberships.module_id.unique(),
            progress=lambda done,total:logger.info("Partial-support sensitivity %d/%d",done,total))
        if len(sensitivity):
            sensitivity["test_method"]="matched_permutation_partial_support_sensitivity"
            sensitivity["capability_threshold"]=.75;sensitivity["publish_kg"]=False
            atomic_table(sensitivity,tables/"module_function_partial_sensitivity.tsv")
        burden,burden_manifest=enrich_capabilities(matrix,available.module_id,available.reset_index(),
            permutations=args.permutations,annotation_coverage=coverage,annotation_burden_sensitivity=True,declared_modules=memberships.module_id.unique(),
            progress=lambda done,total:logger.info("Annotation-burden sensitivity %d/%d",done,total))
        if len(burden):
            burden["test_method"]="matched_permutation_annotation_burden_sensitivity";burden["publish_kg"]=False
            atomic_table(burden,tables/"module_function_annotation_burden_sensitivity.tsv")
        ko_sets=ko_evidence.groupby("taxon").feature_id.apply(set).to_dict()
        features=sorted(set(ko_evidence.feature_id))
        ko_matrix=pd.DataFrame([[feature in ko_sets.get(taxon,set()) for feature in features] for taxon in available.index],
                              index=available.index,columns=features,dtype=bool)
        secondary=ko_fisher_baseline(ko_matrix,available.module_id)
        if len(secondary):atomic_table(secondary,tables/"module_ko_secondary.tsv")
        primary_manifest["partial_support_sensitivity"]=sensitivity_manifest
        primary_manifest["annotation_burden_sensitivity"]=burden_manifest
        primary_manifest["secondary_ko_hypotheses"]=len(secondary)
        affinity,affinity_support=module_affinity(clr,abundance,metadata,memberships)
        atomic_table(affinity_support,tables/"module_affinity_support.tsv")
        affinity=affinity.reindex(matrix.index)
        ks=ks_enrichment(matrix,affinity,available.reset_index(drop=True),permutations=args.ks_permutations,
            progress=lambda module,done,total:logger.info("KS %s permutations %d/%d",module,done,total))
        if len(ks): atomic_table(ks,tables/"module_function_ks.tsv")
        primary_manifest["status"]="computed_exploratory"
    atomic_table(functions,tables/"module_functions.tsv")
    members=supporting_members(capabilities,memberships,annotations,definitions,args.snapshot)
    atomic_table(members,tables/"module_function_members.tsv")
    atomic_table(members[["function_id","taxon"]].drop_duplicates(),tables/"carrier_sets.tsv")
    profiles=module_profiles(clr,abundance,metadata,memberships);atomic_table(profiles,tables/"module_profiles.tsv")
    logger.info("Computing %d depth-block bootstrap centrality replicates",args.bootstraps)
    centrality=module_centrality(read(combo/"hetero_taxon_taxon_edges.tsv"),memberships,clr,abundance,metadata,bootstraps=args.bootstraps)
    atomic_table(centrality,tables/"module_centrality.tsv")
    functional_profiles_table=functional_profiles(clr,abundance,metadata,capabilities,mapping)
    atomic_table(functional_profiles_table,tables/"function_profiles.tsv")
    draw_figures(functions,profiles,centrality,output)
    input_paths=[inputs/"clr_samples_by_taxa.tsv.gz",inputs/"abundance_samples_by_taxa.tsv.gz",combo/"vgae_taxon_modules.tsv",
                 reference/"tables/module_definitions.tsv",reference/"tables/reference_annotations.tsv.gz",
                 inputs/"sample_metadata.tsv",combo/"hetero_taxon_taxon_edges.tsv",reference/"tables/taxon_reference_mapping.tsv",
                 reference/"tables/legacy_module_completeness.tsv.gz",branch/threshold/"tables/ngraph_taxon_retention.tsv"]
    if quality_path.exists():input_paths.append(quality_path)
    if processed: input_paths.extend([reference/"annotation_run_kofam.json",reference/"tables/reference_annotations_kofam.tsv.gz"])
    final_source_hashes={str(p.relative_to(ROOT)):digest(p) for p in source_paths}
    if final_source_hashes!=initial_source_hashes:
        raise RuntimeError("Analysis source changed during execution; rerun before completing this snapshot")
    manifest=dict(schema="functional-1",branch=args.branch,threshold=threshold,method=args.method,model=args.model,
        db_snapshot=args.snapshot,reference_snapshot=args.reference_snapshot,run_status="completed",
        created_utc=datetime.now(timezone.utc).isoformat(),seed=42,runtime_command=sys.argv,
        abundance_mode=metadata.abundance_mode.iloc[0],assigned_taxa=len(memberships),inventory_taxa=len(clr.columns),
        annotation_status="fresh_and_legacy_separate" if processed else "legacy_only_descriptive",
        fresh_references=len(processed),legacy_annotation_rows=int(annotations.source_kind.eq("unknown_legacy").sum()),
        primary=primary_manifest,qualified_associations=int(functions.publish_kg.sum()),
        kg_scope="qualified_matched_associations_and_complete_contributors",
        completeness_definition="fraction_of_fully_supported_essential_steps_on_best_route",
        archive_release="unknown_legacy",annotation_quality="reference_genotype_potential_not_measured_activity",
        centrality_scope="fixed_memberships_moving_depth_blocks_equal_physical_cores",
        ssgsea_status="not_computed_missing_GSVA",publication_gates=dict(q=.05,odds_ratio=1.5,prevalence_difference=.10,
            carriers=5,annotated_members=20,coverage=.70,exchangeable_fraction=.50),
        packages={p:importlib.metadata.version(p) for p in ["numpy","pandas","scipy","matplotlib"]},
        input_sha256={str(p.relative_to(ROOT)):digest(p) for p in input_paths},
        source_sha256=initial_source_hashes,source_unchanged_during_execution=True,
        artifacts={str(p.relative_to(output)):digest(p) for p in tables.iterdir() if p.is_file()},
        unresolved_references=int(mapping.reference_kind.ne("ncbi_versioned_assembly").sum()))
    json_write(output/"manifest.json",manifest)
    (output/"reports").mkdir(exist_ok=True)
    (output/"reports/FUNCTIONAL_ANALYSIS_REPORT.md").write_text(
        "# Reference-supported module functions\n\n"+f"Run `{args.branch}`: {len(memberships)} assigned taxa; {len(clr.columns)} inventory taxa.\n\n"+
        f"Annotation status: **{manifest['annotation_status']}**. Fresh full-proteome references: {len(processed)}. "
        f"Qualified graph associations: {manifest['qualified_associations']}.\n\n"+
        "Legacy reference positives are descriptive. Missing legacy annotation is unknown; no legacy p-value is manufactured. "
        "Functions indicate reference-supported potential, not measured sediment gene abundance or activity.\n\n"+
        "Primary enrichment shuffles whole annotation rows within taxonomy/detection strata and corrects the entire declared family. "
        "Centrality uses actual association edges and fixed-membership depth-block resampling; it does not establish causal drivers. "
        "GeoB libraries remain separate in plots and share physical-depth resampling.\n\n"+
        "Partial completeness counts fully supported essential steps on the best route; it is not identical to archived anvi'o partial-complex scores.\n")
    logger.info("Completed %s: %d function rows; %d contributors; %d qualified associations",args.snapshot,len(functions),len(members),manifest["qualified_associations"])
    print(json.dumps({k:manifest[k] for k in ["branch","db_snapshot","annotation_status","assigned_taxa","inventory_taxa","qualified_associations"]},indent=2))


if __name__=="__main__": main()
