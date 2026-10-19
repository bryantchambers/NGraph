"""Semantic checks for functional assertions and their same-module witnesses."""
import hashlib
from ngraph_functional_paths import SCOPE_FIELDS, text_value


def validate_functional_graph(nodes, edges):
    lookup = {r['node_id']: r for r in nodes.to_dict('records')}
    by = {}
    for e in edges.to_dict('records'):
        by.setdefault((e['source_id'], e['edge_type']), []).append(e['target_id'])
    for association in (r for r in lookup.values() if r['node_type'] == 'ModuleFunctionalAssociation'):
        aid = association['node_id']
        for field in SCOPE_FIELDS:
            if not text_value(association.get(field)):
                raise ValueError(f'Functional association is missing scope: {field}')
        functions = by.get((aid, 'association_with_function'), [])
        analyses = by.get((aid, 'association_derived_from_analysis'), [])
        modules = edges.loc[edges.edge_type.eq('module_has_functional_association') & edges.target_id.eq(aid), 'source_id'].tolist()
        if any(len(values) != 1 for values in (functions, analyses, modules)):
            raise ValueError('Functional assertion must have exactly one module, function and analysis')
        feature = functions[0]; module = modules[0]
        for identifier in (feature, analyses[0]):
            for field in SCOPE_FIELDS:
                if text_value(lookup[identifier].get(field)) != text_value(association.get(field)):
                    raise ValueError('Definition or analysis and assertion scopes differ')
        for field in ('branch', 'threshold', 'method', 'module_system'):
            value = text_value(lookup[module].get(field))
            if value and value != text_value(association.get(field)):
                raise ValueError('Community module and assertion scopes differ')
        definition = lookup[feature]
        if text_value(association.get('evidence_scope')) == 'recorded_annotation_catalog':
            expression = text_value(definition.get('definition_expression'))
            if not expression or hashlib.sha256(expression.encode()).hexdigest() != text_value(definition.get('definition_sha256')):
                raise ValueError('Frozen functional definition hash is missing or incompatible')
        references = set()
        for annotation in by.get((aid, 'association_supported_by_annotation'), []):
            row = lookup[annotation]
            if by.get((annotation, 'annotation_supports_function'), []) != [feature]:
                raise ValueError('Witness supports a different or ambiguous functional definition')
            for field in SCOPE_FIELDS:
                if text_value(row.get(field)) != text_value(association.get(field)):
                    raise ValueError('Witness and assertion scopes differ')
            taxa = edges.loc[edges.edge_type.eq('taxon_has_reference_annotation') & edges.target_id.eq(annotation), 'source_id'].tolist()
            if len(taxa) != 1 or module not in by.get((taxa[0], 'taxon_member_of_module'), []):
                raise ValueError('Witness must belong to a member of this community module')
            if not text_value(row.get('source_file')) or not text_value(row.get('ko_ids')) or not text_value(row.get('gene_ids')):
                raise ValueError('Witness lacks native KO/gene provenance')
            genomes = by.get((annotation, 'annotation_from_reference'), [])
            if len(genomes) != 1 or text_value(lookup[genomes[0]].get('genome_id')) != text_value(row.get('genome_id')):
                raise ValueError('Witness must identify exactly one matching reference genome')
            references.add(text_value(row.get('genome_id')))
        if '' in references or len(references) < 5:
            raise ValueError('Qualified assertion requires five independent reference witnesses')
        if len(by.get((feature, 'functional_feature_has_concept'), [])) != 1:
            raise ValueError('Versioned functional definition lacks its canonical concept')
    return {'status': 'passed', 'rule': 'functional-semantics-1'}
