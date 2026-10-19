"""Scoped artifact serving and conservative functional KG publication checks."""
import hashlib
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("functional_browser_test", ROOT / "scripts" / "14_ngraph_local_browser.py")
browser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser)
import ngraph_functional_kg as kg
from ngraph_kg_snapshots import active_directory


class FunctionalPortalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.original = browser.PROJECT_ROOT, kg.ROOT
        browser.PROJECT_ROOT = kg.ROOT = self.root
        self.directory = self.root / "results/ngraph/demo/functional_enrichment/prev_10/pearson/vgae/fresh"
        (self.directory / "tables").mkdir(parents=True)
        self.manifest = {"branch": "demo", "threshold": "prev_10", "method": "pearson", "model": "vgae",
                         "db_snapshot": "fresh", "run_status": "completed", "annotation_status": "fresh_validated"}
        (self.directory / "manifest.json").write_text(json.dumps(self.manifest))
        self.app = object.__new__(browser.ConstellationsService)
        self.app.branch = "demo"
        self.app.global_dir = self.root / "results/ngraph"

    def tearDown(self):
        browser.PROJECT_ROOT, kg.ROOT = self.original
        browser.ConstellationsService.functional_table.cache_clear()
        self.temp.cleanup()

    def write(self, name, rows):
        pd.DataFrame(rows).to_csv(self.directory / "tables" / name, sep="\t", index=False)

    def test_scope_pagination_and_missing_snapshot(self):
        self.write("module_functions.tsv", [{"module_id": "M1", "function_id": f"F{i}", "q_value": i / 100,
                    "publish_kg": i < 3} for i in range(12)])
        response = self.app.functional_payload("functions", limit=4, offset=4)
        self.assertEqual(response["total_count"], 12)
        self.assertEqual(response["returned_count"], 4)
        self.assertTrue(response["truncated"])
        self.assertEqual(response["rows"][0]["function_id"], "F4")
        self.assertEqual(self.app.functional_payload("functions", qualified_only=True)["total_count"], 3)
        self.assertEqual(self.app.functional_payload("functions", snapshot="../../escape")["status"], "not_computed")
        self.assertEqual(self.app.functional_payload("functions", kind="diffpool")["status"], "not_computed")

    def test_reference_profiles_do_not_inherit_module_filter(self):
        self.write("function_profiles.tsv", [{"function_id": "F1", "sample": "S1", "core": "GeoB25202_R1",
                   "depth_cm": 4.5, "age_kyr": 1., "logratio": .2}])
        response = self.app.functional_payload("profiles", function_id="F1", module_id="M1")
        self.assertEqual(response["total_count"], 1)
        self.assertEqual(response["rows"][0]["core"], "GeoB25202_R1")

    def test_indexed_inventory_is_paged_and_parameterized(self):
        directory = self.directory / "indexes"
        directory.mkdir()
        with closing(sqlite3.connect(directory / "reference_annotations.sqlite")) as connection:
            connection.execute("CREATE TABLE annotations (taxon TEXT,gene_id TEXT,feature_namespace TEXT,feature_id TEXT)")
            connection.executemany("INSERT INTO annotations VALUES (?,?,?,?)", [("T1", f"gene{i}", "KO", f"K{i:05}") for i in range(6)])
            connection.execute("CREATE INDEX taxon_lookup ON annotations(taxon)")
            connection.commit()
        response = self.app.taxon_function_payload("T1", limit=2, offset=2)
        self.assertEqual(response["total_count"], 6)
        self.assertEqual(response["returned_count"], 2)
        self.assertTrue(response["truncated"])
        self.assertEqual(response["feature_namespaces"], ["KO"])
        self.assertEqual(self.app.taxon_function_payload("T1' OR 1=1 --")["total_count"], 0)
        self.assertEqual(self.app.taxon_function_payload("T1", snapshot="../fresh")["status"], "not_computed")

    def prepare_kg(self, annotation_status="validated", publish=True):
        (self.root / "config_kg_schema.json").write_text((ROOT / "config_kg_schema.json").read_text())
        tables = self.root / "results/ngraph/demo/knowledge_graph/tables"
        tables.mkdir(parents=True, exist_ok=True)
        nodes = [{"node_id": "module:demo:prev_10:pearson:vgae:M1", "node_type": "Module", "label": "M1",
                  "module_id": "M1", "module_system": "vgae", "branch": "demo"}]
        nodes += [{"node_id": f"taxon:T{i}", "node_type": "Taxon", "label": f"T{i}", "branch": "demo"} for i in range(5)]
        pd.DataFrame(nodes).to_csv(tables / "kg_nodes.tsv", sep="\t", index=False)
        pd.DataFrame([{ "edge_id": f"e{i}", "edge_type": "taxon_member_of_module", "source_id": f"taxon:T{i}",
                        "target_id": nodes[0]["node_id"], "source_node_type": "Taxon", "target_node_type": "Module"} for i in range(5)]).to_csv(tables / "kg_edges.tsv", sep="\t", index=False)
        self.write("module_functions.tsv", [{"module_id": "M1", "function_id": "M12345", "function_namespace": "KEGG_MODULE",
                    "function_name": "Demo potential", "test_method": "matched_permutation", "q_value": .01,
                    "p_value": .005, "prevalence_difference": .4, "odds_ratio": 2., "carrier_count": 5,
                    "module_annotated_count": 20, "annotation_coverage": .8, "exchangeable_fraction": .7, "publish_kg": publish}])
        self.write("module_function_members.tsv", [{"module_id": "M1", "function_id": "M12345", "taxon": f"T{i}",
                   "genome_id": f"G{i}", "is_carrier": True, "completeness": 1., "gene_ids": f"gene:{i}",
                   "ko_ids": "K00001", "annotation_source": "kofam_scan", "annotation_status": annotation_status,
                   "source_path": "native.tsv", "source_row": i} for i in range(5)])
        return tables

    def test_qualified_projection_is_idempotent_and_retains_native_evidence(self):
        tables = self.prepare_kg()
        first = kg.project("demo", "prev_10", "pearson", "vgae", "fresh")
        second = kg.project("demo", "prev_10", "pearson", "vgae", "fresh")
        self.assertEqual(first["published_associations"], 1)
        self.assertEqual(first["added_nodes"], second["added_nodes"])
        nodes = pd.read_csv(active_directory(tables.parent) / "tables/kg_nodes.tsv", sep="\t")
        self.assertTrue(nodes.node_id.is_unique)
        self.assertEqual(nodes.node_type.eq("ReferenceFunctionalAnnotation").sum(), 5)
        self.assertFalse(nodes.node_type.eq("Gene").any())
        self.assertIn("gene:0", nodes.gene_ids.dropna().tolist())

    def prepare_catalog(self):
        self.prepare_kg(annotation_status="recorded_catalog_supported_framework")
        for filename in ["module_functions.tsv", "module_function_members.tsv"]:
            path = self.directory / "tables" / filename
            frame = pd.read_csv(path, sep="\t")
            frame["evidence_scope"] = "recorded_annotation_catalog"
            if "annotation_source" in frame:
                frame["annotation_source"] = "unknown_legacy"
            frame.to_csv(path, sep="\t", index=False)
        self.write('function_definitions.tsv', [{'module_id': 'M12345', 'module_definition': 'K00001',
                    'definition_sha256': hashlib.sha256(b'K00001').hexdigest()}])
        self.write('independent_annotation_units.tsv', [{'taxon': f'T{i}', 'genome_id': f'G{i}', 'module_id': 'M1'} for i in range(20)])
        for filename in ["reference_annotations.tsv.gz"]:
            (self.directory / "tables" / filename).write_bytes(b"frozen fixture evidence")
        manifest = dict(self.manifest, schema="functional-2", evidence_scope="recorded_annotation_catalog",
                        source_unchanged_during_execution=True, abundance_weighting=False,
                        primary={"null": "matched_whole_annotation_rows"})
        manifest["artifacts"] = {"tables/" + path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in (self.directory / "tables").iterdir()}
        (self.directory / "manifest.json").write_text(json.dumps(manifest))

    def test_audited_catalog_projects_without_claiming_fresh_annotation(self):
        self.prepare_catalog()
        result = kg.project("demo", "prev_10", "pearson", "vgae", "fresh")
        self.assertEqual(result["published_associations"], 1)
        nodes = pd.read_csv(active_directory(self.root / "results/ngraph/demo/knowledge_graph") / "tables/kg_nodes.tsv", sep="\t")
        association = nodes[nodes.node_type.eq("ModuleFunctionalAssociation")].iloc[0]
        self.assertEqual(association.annotation_status, "recorded_catalog_support_unknown_release")
        self.assertTrue(nodes[nodes.node_type.eq("ReferenceFunctionalAnnotation")].annotation_source.eq("unknown_legacy").all())

    def test_catalog_tampering_rejected_before_kg_write(self):
        self.prepare_catalog()
        path = self.directory / "tables/module_function_members.tsv"
        path.write_text(path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            kg.project("demo", "prev_10", "pearson", "vgae", "fresh")

    def test_frozen_catalog_background_scope_must_match_carriers(self):
        self.prepare_catalog()
        path = self.directory / 'tables/independent_annotation_units.tsv'
        frame = pd.read_csv(path, sep='\t')
        frame.loc[frame.genome_id.eq('G0'), 'module_id'] = 'M2'
        frame.to_csv(path, sep='\t', index=False)
        manifest_path = self.directory / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['artifacts']['tables/independent_annotation_units.tsv'] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'outside the scoped independent background'):
            kg.project('demo', 'prev_10', 'pearson', 'vgae', 'fresh')

    def test_legacy_and_false_string_do_not_publish(self):
        self.prepare_kg(annotation_status="unknown_legacy")
        self.assertEqual(kg.project("demo", "prev_10", "pearson", "vgae", "fresh")["published_associations"], 0)
        self.prepare_kg(publish="false")
        self.assertEqual(kg.project("demo", "prev_10", "pearson", "vgae", "fresh")["published_associations"], 0)

    def test_each_publication_gate_is_enforced_independently(self):
        self.prepare_kg()
        path = self.directory / "tables" / "module_functions.tsv"
        valid = pd.read_csv(path, sep="\t")
        for field, bad in [("q_value", .06), ("odds_ratio", 1.4), ("prevalence_difference", .09),
                           ("carrier_count", 4), ("module_annotated_count", 19), ("annotation_coverage", .69),
                           ("exchangeable_fraction", .49), ("test_method", "fisher")]:
            with self.subTest(field=field):
                changed = valid.copy()
                changed.loc[0, field] = bad
                changed.to_csv(path, sep="\t", index=False)
                self.assertEqual(kg.project("demo", "prev_10", "pearson", "vgae", "fresh")["published_associations"], 0)

    def test_module_graph_uses_signed_associations(self):
        self.app.module_summary = lambda *args, **kwargs: (pd.DataFrame([{"module_id": "M1", "taxa": 3}]),
                                  pd.DataFrame([{"taxon": f"T{i}"} for i in range(3)]), "M1")
        associations = pd.DataFrame([{"source_core": "ST8", "taxon_from": "T0", "taxon_to": "T1", "signed_weight": .7, "abs_weight": .7},
                                     {"source_core": "ST8", "taxon_from": "T0", "taxon_to": "T2", "signed_weight": -.8, "abs_weight": .8}])
        self.app.combo_context = lambda *args: {"taxon_taxon_edges": associations}
        graph = self.app.build_module_payload(core="ST8")
        self.assertEqual(graph["graph_total_edges"], 2)
        self.assertIn(-.8, [edge["weight"] for edge in graph["graph_edges"]])
        self.assertFalse(any(n["type"] == "module" for n in graph["graph_nodes"]))


if __name__ == "__main__":
    unittest.main()
