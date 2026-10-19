"""Independent scientific regression checks for functional interpretation."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ngraph_functional_statistics import ModuleDefinition, enrich_capabilities
from ngraph_functional_profiles import module_affinity, module_centrality


class PathwayInterpretationTests(unittest.TestCase):
    def test_multistep_alternatives_are_complete_routes(self):
        definition = ModuleDefinition("(K00001 K00002,K00003 K00004) K00005")
        for kos in ({"K00001", "K00002", "K00005"},
                    {"K00003", "K00004", "K00005"}):
            self.assertTrue(definition.evaluate(kos)["is_complete"])
        self.assertFalse(definition.evaluate({"K00001", "K00004", "K00005"})["is_complete"])

    def test_unknown_alternative_does_not_become_known_absence(self):
        result = ModuleDefinition("(K00001,--)").evaluate(set())
        self.assertTrue(result["unresolved_definition"])
        self.assertFalse(result["is_complete"])
        satisfied = ModuleDefinition("(K00001,--)").evaluate({"K00001"})
        self.assertTrue(satisfied["is_complete"])
        self.assertFalse(satisfied["unresolved_definition"])

    def test_fulfilled_route_has_no_missing_optional_or_unused_alternatives(self):
        for definition, kos in (("K00001-K00002", {"K00001"}),
                                ("(K00001,K00002)", {"K00001"})):
            result = ModuleDefinition(definition).evaluate(kos)
            self.assertTrue(result["is_complete"])
            self.assertEqual(result["missing_kos"], [])


class ConditionalNullTests(unittest.TestCase):
    def test_frozen_function_support_is_preserved_in_mixed_exchangeability(self):
        labels = np.array(["M1"] * 20 + ["M1"] * 20 + ["M2"] * 40)
        meta = pd.DataFrame({"domain": "Bacteria", "phylum": ["P1"] * 20 + ["P2"] * 60,
                             "tad_support": "tad", "prevalence_samples": 20,
                             "physical_core_count": 3})
        cap = pd.DataFrame({"F": [True] * 20 + [False] * 60})
        result, _ = enrich_capabilities(cap, labels, meta, permutations=99)
        self.assertTrue(result.p_value.eq(1).all())
        self.assertFalse(result.publish_kg.any())
        self.assertEqual(result.loc[result.module_id.eq("M1"), "exchangeable_fraction"].iloc[0], .5)

    def test_identical_capabilities_share_the_whole_row_null(self):
        labels = np.array(["M1"] * 20 + ["M2"] * 20)
        meta = pd.DataFrame({"domain": ["Bacteria"] * 40, "phylum": "P",
                             "tad_support": "tad", "prevalence_samples": 20,
                             "physical_core_count": 3})
        support = [True] * 15 + [False] * 5 + [True] * 5 + [False] * 15
        cap = pd.DataFrame({"F1": support, "F2": support})
        result, _ = enrich_capabilities(cap, labels, meta, permutations=199)
        for _, group in result.groupby("module_id"):
            self.assertEqual(group.p_value.nunique(), 1)
            self.assertEqual(group.q_value.nunique(), 1)


class ProfileInterpretationTests(unittest.TestCase):
    def fixture(self):
        n = 12
        levels = np.linspace(-1, 1, n)
        frame = pd.DataFrame({"a": levels, "b": levels ** 2,
                              "c": np.sin(4 * levels), "d": np.cos(3 * levels),
                              "outside": -levels, "absent": levels},
                             index=[f"S{i}" for i in range(n)])
        abundance = np.exp(frame)
        abundance["absent"] = 0.
        metadata = pd.DataFrame({"sample": frame.index, "core": "ST8",
                                 "depth_in_core_cm": np.arange(n), "y_bp": np.arange(n) * 1000})
        members = pd.DataFrame({"taxon": ["a", "b", "c", "d"], "module_id": "M1"})
        return frame, abundance, metadata, members

    def test_affinity_is_leave_one_out_and_includes_outsiders(self):
        frame, abundance, meta, members = self.fixture()
        affinity, _ = module_affinity(frame, abundance, meta, members)
        standardized = (frame - frame.mean()) / frame.std(ddof=0)
        expected_member = np.corrcoef(standardized.a, standardized[["b", "c", "d"]].mean(axis=1))[0, 1]
        expected_outside = np.corrcoef(standardized.outside,
                                      standardized[["a", "b", "c", "d"]].mean(axis=1))[0, 1]
        self.assertAlmostEqual(affinity.loc["a", "M1"], expected_member)
        self.assertAlmostEqual(affinity.loc["outside", "M1"], expected_outside)
        self.assertTrue(np.isnan(affinity.loc["absent", "M1"]))

    def test_geoB_pairing_does_not_double_the_number_of_physical_levels(self):
        frame, abundance, meta, members = self.fixture()
        paired_frame = pd.concat([frame, frame.rename(index=lambda s: s + "_R2")])
        paired_abundance = pd.concat([abundance, abundance.rename(index=lambda s: s + "_R2")])
        first = meta.assign(core="GeoB25202_R1")
        second = meta.assign(sample=lambda x: x["sample"] + "_R2", core="GeoB25202_R2")
        _, support = module_affinity(paired_frame, paired_abundance,
                                     pd.concat([first, second], ignore_index=True), members)
        self.assertTrue(support.unique_depths.eq(len(frame)).all())
        self.assertEqual(set(support.physical_core), {"GeoB25202"})

    def test_bootstrap_without_variation_does_not_report_a_rank_interval(self):
        frame, abundance, meta, members = self.fixture()
        edges = pd.DataFrame({"source_core": ["ST8"], "taxon_from": ["a"],
                              "taxon_to": ["b"], "signed_weight": [.7]})
        with patch("ngraph_functional_profiles.moving_block_indices",
                   side_effect=lambda n, rng: np.zeros(n, dtype=int)):
            result = module_centrality(edges, members, frame, abundance, meta, bootstraps=3)
        core_rows = result.loc[result.core.eq("ST8")]
        self.assertFalse(core_rows.central_candidate.any())
        self.assertTrue(core_rows.rank_lower.isna().all())
        self.assertTrue(core_rows.rank_upper.isna().all())


if __name__ == "__main__":
    unittest.main()
