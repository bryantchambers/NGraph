#!/usr/bin/env python3
"""Project qualified functional evidence into a bounded, file-backed KG.

The complete tested universe and gene-level inventory stay in the functional
artifacts. This projection never computes statistics or treats reference genome
potential as observed sample activity. Re-running replaces the previous
functional projection while retaining the site's original KG substrate. Build
as an immutable bundle before atomically activating the new snapshot. Historical
TSV artifacts and old snapshots remain intact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from pathlib import Path

import pandas as pd
from ngraph_kg_snapshots import active_directory, publish
from ngraph_functional_statistics import ModuleDefinition
from ngraph_validate_functional_graph import validate_functional_graph

ROOT = Path(__file__).resolve().parents[1]


def truth(value):
    return str(value).strip().lower() in {"true", "1"}


def stable(prefix, *parts):
    payload = json.dumps(parts, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}:{hashlib.sha256(payload.encode()).hexdigest()[:24]}"


def clean(value):
    return "" if value is None or pd.isna(value) else value


def project(branch, threshold, method, model, snapshot, activate_snapshot=True):
    code_paths = [Path(__file__), Path(__file__).with_name('ngraph_kg_snapshots.py'), Path(__file__).with_name('ngraph_validate_functional_graph.py')]
    code_paths.append(Path(__file__).with_name('ngraph_functional_retrieval.py'))
    code_paths.append(ROOT/'config_kg_schema.json')
    if (ROOT/'data/reference/functional/semantic_mappings.tsv').exists():code_paths.append(ROOT/'data/reference/functional/semantic_mappings.tsv')
    code_hashes = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths}
    directory = ROOT / "results" / "ngraph" / branch / "functional_enrichment" / threshold / method / model / snapshot
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    scope = (branch, threshold, method, model, snapshot)
    expected = {"branch": branch, "threshold": threshold, "method": method, "model": model, "db_snapshot": snapshot}
    for field, value in expected.items():
        if str(manifest.get(field)) != str(value):
            raise ValueError(f"Functional manifest scope mismatch for {field}")
    catalog_scope = manifest.get("evidence_scope") == "recorded_annotation_catalog"
    if catalog_scope:
        if not (manifest.get("schema") == "functional-2" and manifest.get("run_status") == "completed"
                and manifest.get("source_unchanged_during_execution") is True
                and manifest.get("abundance_weighting") is False
                and manifest.get("primary", {}).get("null") == "matched_whole_annotation_rows"):
            raise ValueError("Catalog projection requires a completed audited unweighted analysis")
        required = {"tables/module_functions.tsv", "tables/module_function_members.tsv",
                    "tables/reference_annotations.tsv.gz", "tables/independent_annotation_units.tsv"}
        artifacts = manifest.get("artifacts", {})
        if not required.issubset(artifacts):
            raise ValueError("Catalog projection is missing frozen evidence hashes")
        for relative, digest in artifacts.items():
            path = (directory / relative).resolve()
            if not path.is_relative_to(directory.resolve()) or not path.is_file():
                raise ValueError("Invalid catalog artifact path")
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError(f"Catalog artifact hash mismatch: {relative}")
    kg_root = ROOT / "results" / "ngraph" / branch / "knowledge_graph"
    tables = active_directory(kg_root) / "tables"
    nodes = pd.read_csv(tables / "kg_nodes.tsv", sep="\t", low_memory=False)
    edges = pd.read_csv(tables / "kg_edges.tsv", sep="\t", low_memory=False)
    # One active functional projection per branch. Historical full outputs remain scoped.
    if "functional_projection" in nodes:
        previous = set(nodes.loc[nodes.functional_projection.map(truth), "node_id"].astype(str))
        nodes = nodes[~nodes.node_id.astype(str).isin(previous)].copy()
        edges = edges[~edges.source_id.astype(str).isin(previous) & ~edges.target_id.astype(str).isin(previous)].copy()
    if "functional_projection" in edges:
        edges = edges[~edges.functional_projection.map(truth)].copy()
    functions = pd.read_csv(directory / "tables" / "module_functions.tsv", sep="\t", dtype={"module_id": str}, low_memory=False)
    members = pd.read_csv(directory / "tables" / "module_function_members.tsv", sep="\t", dtype={"module_id": str}, low_memory=False)
    qualified = functions[
        functions.publish_kg.map(truth) & functions.test_method.eq("matched_permutation")
        & (pd.to_numeric(functions.q_value, errors="coerce") <= .05)
        & (pd.to_numeric(functions.odds_ratio, errors="coerce") >= 1.5)
        & (pd.to_numeric(functions.prevalence_difference, errors="coerce") >= .10)
        & (pd.to_numeric(functions.carrier_count, errors="coerce") >= 5)
        & (pd.to_numeric(functions.module_annotated_count, errors="coerce") >= 20)
        & (pd.to_numeric(functions.annotation_coverage, errors="coerce") >= .70)
        & (pd.to_numeric(functions.exchangeable_fraction, errors="coerce") >= .50)
    ]
    native_ids = set(nodes.node_id.astype(str))
    node_types = dict(zip(nodes.node_id.astype(str), nodes.node_type.astype(str)))
    module_nodes = nodes[nodes.node_type.eq("Module")]
    added_nodes, added_edges = {}, {}
    evidence_source = (directory / "tables" / "module_function_members.tsv").relative_to(ROOT).as_posix()
    result_source = (directory / "tables" / "module_functions.tsv").relative_to(ROOT).as_posix()
    manifest_source = manifest_path.relative_to(ROOT).as_posix()
    rejected = []
    definition_path = directory / 'tables/function_definitions.tsv'
    definitions = pd.read_csv(definition_path, sep='\t') if definition_path.exists() else pd.DataFrame()
    if not definitions.empty:
        definitions = definitions.set_index('function_id' if 'function_id' in definitions else 'module_id')
    mapping_path=ROOT/'data/reference/functional/semantic_mappings.tsv'
    semantic_mappings=pd.read_csv(mapping_path,sep='\t').fillna('') if mapping_path.exists() else pd.DataFrame()
    units = pd.read_csv(directory / 'tables/independent_annotation_units.tsv', sep='\t', dtype=str) if catalog_scope else pd.DataFrame()
    if catalog_scope and (units.genome_id.isna().any() or not units.genome_id.is_unique):
        raise ValueError('Catalog background must identify unique independent references')

    def node(identifier, kind, label, **attributes):
        if identifier not in native_ids:
            added_nodes[identifier] = {"node_id": identifier, "node_type": kind, "label": label,
                "branch": branch, "functional_projection": True, "db_snapshot": snapshot,
                "functional_manifest": manifest_source, "threshold": threshold, "method": method, "module_system": model, **attributes}
            node_types[identifier] = kind
        return identifier

    def edge(predicate, source, target, **attributes):
        eid = stable("edge:functional", predicate, source, target, scope)
        added_edges[eid] = {"edge_id": eid, "edge_type": predicate, "source_id": source,
            "target_id": target, "source_node_type": node_types[source], "target_node_type": node_types[target],
            "weight": 1.0, "branch": branch, "threshold": threshold, "method": method,
            "module_system": model, "db_snapshot": snapshot, "functional_projection": True,
            "functional_manifest": manifest_source, **attributes}

    analysis_id = stable("analysis:functional", *scope)
    dataset_id = stable("dataset:functional", snapshot, manifest.get("annotation_status", "unknown"))
    for row in qualified.to_dict("records"):
        module_id, function_id = str(row["module_id"]), str(row["function_id"])
        carriers = members[members.module_id.astype(str).eq(module_id) & members.function_id.astype(str).eq(function_id) & members.is_carrier.map(truth)]
        statuses = carriers.annotation_status.fillna("").astype(str).str.strip() if "annotation_status" in carriers else pd.Series("", index=carriers.index)
        unknown = statuses.eq("") | statuses.str.contains("legacy|unknown|unverified|pending|failed|missing", case=False)
        fresh = carriers.annotation_source.fillna("").astype(str).isin({"kofam_scan", "fresh_reference_kofam"}) if "annotation_source" in carriers else pd.Series(False, index=carriers.index)
        matching = module_nodes[module_nodes.module_id.astype(str).eq(module_id) & module_nodes.module_system.astype(str).eq(model)]
        if "branch" in matching:
            matching = matching[matching.branch.astype(str).eq(branch)]
        for field, value in [('threshold', threshold), ('method', method)]:
            if field in matching:
                matching = matching[matching[field].isna() | matching[field].astype(str).eq(value)]
        distinct_references = carriers.genome_id.dropna().astype(str).nunique() if "genome_id" in carriers else 0
        catalog_valid = (catalog_scope and row.get("evidence_scope") == "recorded_annotation_catalog"
            and "evidence_scope" in carriers and carriers.evidence_scope.eq("recorded_annotation_catalog").all()
            and statuses.eq("recorded_catalog_supported_framework").all()
            and "annotation_source" in carriers and carriers.annotation_source.eq("unknown_legacy").all())
        source_valid = catalog_valid if catalog_scope else (not unknown.any() and fresh.all())
        if len(matching) != 1 or distinct_references < 5 or not source_valid:
            rejected.append({"module_id": module_id, "function_id": function_id, "reason": "Missing or ambiguous scoped module / insufficient scoped validated carrier evidence"})
            continue
        if catalog_scope:
            reference_units = units[units.genome_id.isin(carriers.genome_id.astype(str))]
            if len(reference_units) != distinct_references or not reference_units.module_id.eq(module_id).all():
                raise ValueError('Supporting references are outside the scoped independent background')
            if distinct_references != int(row['carrier_count']) or len(units[units.module_id.eq(module_id)]) != int(row['module_annotated_count']):
                raise ValueError('Stored carrier or module background count is incompatible with evidence')
            if function_id not in definitions.index:
                raise ValueError('Qualified catalog function is missing its frozen definition')
            definition = definitions.loc[function_id]
            expression = str(definition['module_definition'])
            if hashlib.sha256(expression.encode()).hexdigest() != str(definition['definition_sha256']):
                raise ValueError('Function definition hash mismatch')
            ModuleDefinition(expression)
        module_node = str(matching.node_id.iloc[0])
        native_members = set(edges.loc[edges.edge_type.eq('taxon_member_of_module') & edges.target_id.eq(module_node), 'source_id'])
        if not carriers.taxon.map(lambda t: 'taxon:' + str(t)).isin(native_members).all():
            raise ValueError('Supporting annotation taxon is not a member of the scoped module')
        node(analysis_id, "AnalysisRun", f"Functional enrichment {snapshot}", source_file=manifest_source,
             evidence_status="exploratory_reference_supported")
        node(dataset_id, "Dataset", f"Functional annotation snapshot {snapshot}", source_file=evidence_source,
             annotation_status=manifest.get("annotation_status", "unknown"))
        feature = node(stable("function", snapshot, row.get("function_namespace", ""), function_id), "FunctionalFeature",
            str(row.get("function_name") or function_id), function_id=function_id,
            function_namespace=clean(row.get("function_namespace")), function_name=clean(row.get("function_name")),
            evidence_status="reference_function_definition")
        concept_prefix = {'KEGG_MODULE': 'kegg.module', 'KEGG_KO': 'kegg.orthology'}.get(row.get('function_namespace'), 'ngraph.function')
        concept = node(f"{concept_prefix}:{function_id}", 'FunctionalConcept', str(row.get('function_name') or function_id),
                       function_id=function_id, function_namespace=row.get('function_namespace'), evidence_status='canonical_function_concept')
        edge('functional_feature_has_concept', feature, concept, source_file=str(definition_path.relative_to(ROOT)))
        if function_id in definitions.index:
            definition = definitions.loc[function_id].to_dict()
            added_nodes[feature]['definition_expression'] = clean(definition.get('module_definition', definition.get('definition')))
            added_nodes[feature]['definition_sha256'] = clean(definition.get('definition_sha256')) or hashlib.sha256(json.dumps(definition, sort_keys=True, default=str).encode()).hexdigest()
            added_nodes[feature]['definition_source_file'] = str(definition_path.relative_to(ROOT))
        added_nodes[feature]['definition_version'] = snapshot
        expression=added_nodes[feature].get('definition_expression','')
        for ko in sorted(set(re.findall(r'K\d{5}',str(expression)))):
            ko_node=node('kegg.orthology:'+ko,'FunctionalConcept',ko,function_id=ko,function_namespace='KEGG_KO',source_file=str(definition_path.relative_to(ROOT)),evidence_status='recorded_definition_component')
            edge('functional_definition_mentions_ko',feature,ko_node,source_file=str(definition_path.relative_to(ROOT)),interpretation='KO mention; preserve the complete AND/OR/optional definition. Not a separate enrichment test.')
        if function_id in definitions.index:
            native_definition=definitions.loc[function_id]
            for field in ['module_category','module_subcategory']:
                label=clean(native_definition.get(field))
                if label:
                    category=node(stable('functioncategory',snapshot,field,label),'FunctionalCategory',label,source_file=str(definition_path.relative_to(ROOT)),evidence_status='recorded_category_unknown_release')
                    edge('functional_definition_has_recorded_category',feature,category,source_file=str(definition_path.relative_to(ROOT)),interpretation='Recorded category; no inherited category enrichment q-value')
        if not semantic_mappings.empty:
            for mapping in semantic_mappings[semantic_mappings.function_id.eq(function_id)&semantic_mappings.review_status.eq('reviewed')].to_dict('records'):
                if mapping['mapping_type'] not in {'exact','related'} or not all(mapping.get(k) for k in ['source_path','source_row','reviewed_by','target_namespace','target_id']):raise ValueError('Reviewed semantic mapping lacks provenance')
                term=node(mapping['target_namespace']+':'+mapping['target_id'],'OntologyTerm',mapping['target_label'],namespace=mapping['target_namespace'],source_file=str(mapping_path.relative_to(ROOT)))
                mid=node(stable('functionalmapping',snapshot,function_id,mapping),'FunctionalSemanticMapping',mapping['mapping_type']+' mapping',**mapping,source_file=str(mapping_path.relative_to(ROOT)))
                edge('functional_feature_has_reviewed_mapping',feature,mid,source_file=str(mapping_path.relative_to(ROOT)))
                edge('functional_mapping_targets_term',mid,term,source_file=str(mapping_path.relative_to(ROOT)))
        association = node(stable("functionalassociation", *scope, module_id, function_id), "ModuleFunctionalAssociation",
            f"{module_id} associated with {function_id}", **{key: clean(value) for key, value in row.items() if key not in {"db_snapshot"}},
            biological_review_status="pending", annotation_status="recorded_catalog_support_unknown_release" if catalog_scope else "fresh_reference_annotation", source_file=result_source,
            evidence_status="exploratory_reference_supported")
        edge("module_has_functional_association", str(matching.node_id.iloc[0]), association, source_file=result_source)
        edge("association_with_function", association, feature, source_file=result_source)
        edge("association_derived_from_analysis", association, analysis_id, source_file=manifest_source)
        for carrier in carriers.to_dict("records"):
            taxon = str(carrier["taxon"])
            taxon_id = f"taxon:{taxon}"
            if taxon_id not in native_ids:
                raise ValueError(f"Carrier taxon is absent from KG: {taxon}")
            annotation = node(stable("referenceannotation", snapshot, taxon, carrier.get("genome_id", ""), function_id),
                "ReferenceFunctionalAnnotation", f"{taxon}: reference support for {function_id}",
                **{key: clean(value) for key, value in carrier.items() if key not in {"db_snapshot", "module_id", "function_id"}},
                function_id=function_id, source_file=evidence_source, evidence_status="reference_potential")
            reference = node(stable('referencegenome', snapshot, carrier.get('genome_id', '')), 'ReferenceGenome',
                             str(carrier.get('genome_id', '')), genome_id=carrier.get('genome_id'),
                             source_file=evidence_source, annotation_status=manifest.get('annotation_status'))
            edge('annotation_from_reference', annotation, reference, source_file=evidence_source)
            for ko in sorted(set(re.findall(r'K\d{5}',str(carrier.get('ko_ids',''))))):
                ko_node=node('kegg.orthology:'+ko,'FunctionalConcept',ko,function_id=ko,function_namespace='KEGG_KO',source_file=evidence_source,evidence_status='recorded_reference_KO')
                edge('annotation_records_ko',annotation,ko_node,source_file=evidence_source,interpretation='Recorded native reference KO support, not measured sample activity')
            edge("taxon_has_reference_annotation", taxon_id, annotation, source_file=evidence_source)
            edge("annotation_supports_function", annotation, feature, source_file=evidence_source)
            edge("association_supported_by_annotation", association, annotation, source_file=evidence_source)
            edge("annotation_derived_from_dataset", annotation, dataset_id, source_file=evidence_source)
    if added_nodes:
        nodes = pd.concat([nodes, pd.DataFrame(added_nodes.values())], ignore_index=True, sort=False)
        edges = pd.concat([edges, pd.DataFrame(added_edges.values())], ignore_index=True, sort=False)
    assert nodes.node_id.is_unique and edges.edge_id.is_unique
    assert edges.source_id.isin(nodes.node_id).all() and edges.target_id.isin(nodes.node_id).all()
    schema = json.loads((ROOT / "config_kg_schema.json").read_text())
    for predicate, group in edges.groupby("edge_type"):
        rule = schema["relations"][predicate]
        assert group.source_node_type.isin(rule["source"]).all() and group.target_node_type.isin(rule["target"]).all()
    validate_functional_graph(nodes, edges)
    kg_manifest_path = tables.parent / "kg_manifest.json"
    kg_manifest = json.loads(kg_manifest_path.read_text()) if kg_manifest_path.exists() else {}
    if isinstance(kg_manifest.get("counts"), dict):
        kg_manifest["counts"].update(nodes=len(nodes), edges=len(edges))
    kg_manifest.update(node_types=sorted(nodes.node_type.unique()), edge_types=sorted(edges.edge_type.unique()))
    kg_manifest.update(schema_version=schema["schema_version"], functional_projection={
        "scope": dict(zip(["branch", "threshold", "method", "model", "db_snapshot"], scope)),
        "added_nodes": len(added_nodes), "added_edges": len(added_edges), "qualified_results": len(qualified),
        "published_associations": sum(n["node_type"] == "ModuleFunctionalAssociation" for n in added_nodes.values()),
        "projection_code_sha256": code_hashes, "seed": 42,
        "evidence_scope": manifest.get("evidence_scope", "fresh_full_proteome"),
        "negative_interpretation": manifest.get("negative_interpretation", "Reference potential only"),
        "annotation_scope": "Only carriers supporting qualified associations are projected; complete inventory remains in scoped artifacts",
        "source_hashes": {name: hashlib.sha256((directory / "tables" / name).read_bytes()).hexdigest()
                          for name in ["module_functions.tsv", "module_function_members.tsv"]},
        "rejected": rejected, "full_inventory": str((directory / "tables" / "reference_annotations.tsv.gz").relative_to(ROOT)),
        "interpretation": "Reference potential; no measured activity or causal driver inference"})

    projection = kg_manifest["functional_projection"]
    projection["kg_snapshot_id"] = publish(kg_root, nodes, edges, kg_manifest, projection, directory, activate_snapshot=activate_snapshot)
    logging.info("Functional projection: %s", projection)
    return projection


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--threshold", default="prev_10")
    parser.add_argument("--method", default="pearson")
    parser.add_argument("--model", default="vgae")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument('--no-activate', action='store_true')
    args = parser.parse_args()
    logfile = ROOT / "logs" / args.branch / "functional_kg.log"
    logfile.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=logfile, level=logging.INFO)
    print(json.dumps(project(args.branch, args.threshold, args.method, args.model, args.snapshot, activate_snapshot=not args.no_activate), indent=2))
