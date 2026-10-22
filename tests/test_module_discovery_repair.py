import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from ngraph_training_validation import split_pairs


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VGAE = load("07_ngraph_train_vgae.py")
DIFFPOOL = load("08_ngraph_train_diffpool.py")


class DiscoveryRepairTests(unittest.TestCase):
    def fixture(self):
        taxa = pd.DataFrame({"taxon": ["isolate", "a", "b"], "taxon_index": [10, 20, 30]})
        for col in VGAE.TAXON_FEATURES:
            taxa[col] = [0., 1., 2.]
        taxa["has_kegg"] = [True, False, True]
        taxa["confidence_score"] = [0., 100., 1e9]
        taxa["group_completeness"] = [0., .8, 1.]
        site = pd.DataFrame({"core": ["core"]})
        for col in VGAE.SITE_FEATURES:
            site[col] = 1.
        edges = pd.DataFrame({"taxon_from": ["a"], "taxon_to": ["b"], "source_core": ["core"],
                              "edge_type": ["taxon_taxon__core__positive"], "abs_weight": [.9]})
        context = pd.DataFrame({"taxon": ["isolate", "a", "b"], "core": ["core"] * 3})
        for col in DIFFPOOL.CONTEXT_FEATURES:
            context[col] = [0., 1., 2.]
        return taxa, site, edges, pd.DataFrame(columns=["site_from", "site_to", "weight"]), context

    def test_mapping_and_functional_features_cannot_change_graph_inputs(self):
        taxa, sites, edges, site_edges, context = self.fixture()
        selected, local = VGAE.learner_taxon_tables(taxa, edges, context)
        self.assertEqual(selected.taxon.tolist(), ["a", "b"])
        self.assertEqual(selected.taxon_index.tolist(), [20, 30])
        graph, index, _, columns, _ = VGAE.build_hetero_graph(selected, sites, edges, site_edges, local)
        self.assertEqual(index, {"a": 0, "b": 1})
        self.assertFalse(set(["has_kegg", "confidence_score", "group_completeness"]) & set(columns))
        original = graph["taxon"].x.clone()
        selected[["has_kegg", "confidence_score", "group_completeness"]] = 999999
        changed, *_ = VGAE.build_hetero_graph(selected, sites, edges, site_edges, local)
        self.assertTrue(torch.equal(original, changed["taxon"].x))

    def test_diffpool_uses_same_supported_inventory_and_masked_context(self):
        taxa, sites, edges, site_edges, context = self.fixture()
        selected, local = DIFFPOOL.learner_taxon_tables(taxa, edges, context)
        x, adjacency, mask, _, names, _, _ = DIFFPOOL.build_site_graphs(selected, sites, edges, site_edges, local)
        self.assertEqual(names, ["a", "b"])
        self.assertEqual(x.shape[-1], len(DIFFPOOL.TAXON_FEATURES) + len(DIFFPOOL.CONTEXT_FEATURES))
        self.assertTrue(torch.all(mask == 1))
        self.assertGreater(adjacency[0, 0, 1].item(), 0)
        self.assertEqual(VGAE.TAXON_FEATURES, DIFFPOOL.TAXON_FEATURES)
        with self.assertRaises(ValueError):
            DIFFPOOL.build_site_graphs(selected, sites, edges, site_edges, local[local.taxon == "a"])

    def test_k_search_is_complete_and_does_not_impose_six_modules(self):
        rng = np.random.default_rng(42)
        embeddings = np.concatenate([rng.normal(-5, .1, (20, 3)), rng.normal(5, .1, (20, 3))])
        labels, chosen, _, search = VGAE.cluster_taxon_embeddings(embeddings, 2, 8)
        self.assertEqual(search.k.tolist(), list(range(2, 9)))
        self.assertEqual(chosen, 2)
        self.assertEqual(len(labels), 40)
        self.assertTrue((search.minimum_module_size > 0).all())

    def test_pair_holdouts_remain_unique_disjoint_and_exclude_known_positives(self):
        edges = [(i, j) for i in range(9) for j in range(i + 1, 9) if (i + j) % 2 == 0]
        repeated = edges + [(j, i) for i, j in edges] + edges[:4]
        split = split_pairs(repeated, 9, 42)
        positive = set(edges)
        seen = set()
        negative = set()
        for part in ["train", "validation", "test"]:
            current = {tuple(p) for p in split[part]}
            self.assertFalse(seen & current)
            seen |= current
            nonedges = {tuple(p) for p in split[part + "_negative"]}
            self.assertFalse(nonedges & positive)
            self.assertFalse(nonedges & negative)
            negative |= nonedges
        self.assertEqual(seen, positive)


if __name__ == "__main__":
    unittest.main()
