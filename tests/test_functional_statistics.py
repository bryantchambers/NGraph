import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ngraph_functional_statistics import ModuleDefinition, bh_adjust, matched_groups, enrich_capabilities, ks_high_affinity


class DefinitionTests(unittest.TestCase):
    def test_alternative_does_not_bypass_later_essential_step(self):
        definition = ModuleDefinition("K00001,K00002 K00003")
        self.assertFalse(definition.evaluate({"K00001"})["is_complete"])
        self.assertEqual(definition.evaluate({"K00001"})["completeness"], .5)
        self.assertTrue(definition.evaluate({"K00002", "K00003"})["is_complete"])

    def test_complex_optional_and_nested_alternatives(self):
        definition = ModuleDefinition("(K00001+K00002,K00003) K00004-K00005")
        self.assertFalse(definition.evaluate({"K00001", "K00004"})["is_complete"])
        self.assertTrue(definition.evaluate({"K00003", "K00004"})["is_complete"])
        self.assertTrue(definition.evaluate({"K00001", "K00002", "K00004"})["is_complete"])

    def test_unknown_essential_steps_cannot_be_complete(self):
        result = ModuleDefinition("K00001 --").evaluate({"K00001"})
        self.assertTrue(result["unresolved_definition"])
        self.assertFalse(result["is_complete"])

    def test_whole_route_alternatives_and_missing_only_selected_route(self):
        result=ModuleDefinition("(K00001 K00002,K00003 K00004)").evaluate({"K00001","K00002"})
        self.assertTrue(result["is_complete"])
        self.assertEqual(result["missing_kos"],[])
        result=ModuleDefinition("((K00001,K00002) K00003,K00004) K00005-K00006").evaluate({"K00004","K00005"})
        self.assertTrue(result["is_complete"])
        self.assertEqual(result["missing_kos"],[])
        self.assertTrue(ModuleDefinition("(K00001,--)").evaluate(set())["unresolved_definition"])

    def test_invalid_definition_rejected(self):
        with self.assertRaises(ValueError): ModuleDefinition("(K00001+)")


class EnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.meta = pd.DataFrame(dict(domain=["Bacteria"]*40, phylum=["P"]*40,
                                     tad_support=["tad"]*40, prevalence_samples=[10]*40,
                                     physical_core_count=[3]*40))
        self.labels = np.array(["M1"]*20+["M2"]*20)
        self.cap = pd.DataFrame({"M00001": [True]*20+[False]*20,
                                 "M00002": [True, False]*20})

    def test_bh_known_values_and_missing(self):
        np.testing.assert_allclose(bh_adjust([.01, .04, .03, np.nan])[:3], [.03, .04, .04])
        self.assertTrue(np.isnan(bh_adjust([np.nan])[0]))

    def test_effect_null_reproducibility_and_publication_gate(self):
        a, manifest = enrich_capabilities(self.cap, self.labels, self.meta, permutations=999)
        b, _ = enrich_capabilities(self.cap, self.labels, self.meta, permutations=999)
        pd.testing.assert_frame_equal(a, b)
        hit = a[(a.module_id == "M1") & (a.function_id == "M00001")].iloc[0]
        self.assertEqual(hit.prevalence_difference, 1)
        self.assertTrue(hit.publish_kg)
        self.assertEqual(manifest["hypotheses"], 4)
        self.assertEqual(hit.p_value, .001)
        failed, _ = enrich_capabilities(self.cap, self.labels, self.meta, permutations=99,
                                       annotation_coverage={"M1": .5})
        hit = failed[(failed.module_id == "M1") & (failed.function_id == "M00001")].iloc[0]
        self.assertFalse(hit.publish_kg)
        self.assertIn("insufficient_coverage", hit.status)

    def test_taxonomy_frozen_null_prevents_confounding_claim(self):
        self.meta.loc[20:, "phylum"] = "OTHER"
        result, _ = enrich_capabilities(self.cap, self.labels, self.meta, permutations=99)
        self.assertTrue((result.p_value == 1).all())
        self.assertTrue((result.exchangeable_fraction == 0).all())
        self.assertFalse(result.publish_kg.any())

    def test_unknown_annotations_rejected_and_global_filter(self):
        self.cap["RARE"] = [True]*4+[False]*36
        result, _ = enrich_capabilities(self.cap, self.labels, self.meta, permutations=9)
        self.assertNotIn("RARE", set(result.function_id))
        self.cap["M00001"] = self.cap["M00001"].astype(object)
        self.cap.loc[0, "M00001"] = np.nan
        with self.assertRaises(ValueError): enrich_capabilities(self.cap, self.labels, self.meta, permutations=9)

    def test_strata_do_not_split_ties_or_merge_phyla(self):
        groups = matched_groups(self.meta)
        self.assertEqual(len(groups), 1)
        self.meta.loc[20:, "phylum"] = "OTHER"
        groups = matched_groups(self.meta)
        self.assertEqual(len(groups), 2)
        self.assertEqual(sum(map(len, groups)), 40)

    def test_ks_direction_and_ties(self):
        self.assertEqual(ks_high_affinity([1, 1, 2, 2], [False, False, True, True]), 1)
        self.assertEqual(ks_high_affinity([1, 1, 2, 2], [True, False, True, False]), 0)
        self.assertEqual(ks_high_affinity([1, 2, 3, 4], [True, True, False, False]), 0)


if __name__ == "__main__": unittest.main()
