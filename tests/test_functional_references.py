"""Reference provenance, native deduplication and accession safety regressions."""
import csv
from argparse import Namespace
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ngraph_functional_references as functional


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.snapshot = self.root / "snapshot"
        self.snapshot.mkdir()

    def tearDown(self):
        self.directory.cleanup()

    def mapping(self, genome="GCA_000001.1", taxon="taxon", domain="d__Bacteria", phylum="p__A"):
        return functional.make_mapping([{"taxon": taxon, "genome_id": genome, "domain": domain, "phylum": phylum}],
                                       [{"taxon": taxon, "genome_id": genome}], "taxa.tsv", "reference.tsv")[0]

    def archive(self, rows):
        fields = ["module", "genome_name", "module_name", "module_definition", "stepwise_module_completeness", "pathwise_module_completeness", "stepwise_module_is_complete", "pathwise_module_is_complete", "enzyme_hits_in_module", "gene_caller_ids_in_module"]
        path = self.root / "archive.tsv.gz"
        with gzip.open(path, "wt", newline="") as handle:
            # TSV separator is explicit; the fixture checks native source-row counting.
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            for row in rows:
                writer.writerow({"module_name": "module", "stepwise_module_completeness": "0.75", "pathwise_module_completeness": "0.75", "stepwise_module_is_complete": "TRUE", "pathwise_module_is_complete": "TRUE", **row})
        return path

    def test_native_gene_dedup_keeps_distinct_genes_and_provenance(self):
        common = {"genome_name": "GCA_000001.1", "module_definition": "K00001"}
        archive = self.archive([
            {**common, "module": "M00001", "enzyme_hits_in_module": "K00001,K00001", "gene_caller_ids_in_module": "7,8"},
            {**common, "module": "W00001", "enzyme_hits_in_module": "K00001", "gene_caller_ids_in_module": "7"},
            {**common, "module": "M00002", "enzyme_hits_in_module": "K00001,K00002", "gene_caller_ids_in_module": "9"},
        ])
        result = functional.audit_archive(archive, self.snapshot, [self.mapping(), self.mapping(taxon="alias")])
        self.assertEqual(result["native_unique_gene_KO"], 2)
        self.assertEqual(result["duplicate_module_hit_occurrences_removed"], 1)
        self.assertEqual(result["counts"]["mismatched_gene_enzyme_rows"], 1)
        annotations = list(functional.read_tsv(self.snapshot / "tables/reference_annotations.tsv.gz"))
        self.assertEqual(len(annotations), 4)
        first = next(r for r in annotations if r["taxon"] == "taxon" and r["gene_id"] == "7")
        self.assertEqual(first["source_row"], "2")
        self.assertEqual(first["archive_occurrences"], "2")
        self.assertEqual(first["source_kind"], "unknown_legacy")
        self.assertEqual(first["annotation_status"], "present_reference")
        completeness = list(functional.read_tsv(self.snapshot / "tables/legacy_module_completeness.tsv.gz"))
        self.assertEqual(completeness[0]["legacy_stepwise_is_complete"], "TRUE")
        self.assertEqual(completeness[0]["stepwise_module_completeness"], "0.75")
        definitions = list(functional.read_tsv(self.snapshot / "tables/module_definitions.tsv"))
        self.assertEqual(next(r for r in definitions if r["module_id"] == "W00001")["module_namespace"], "CUSTOM_MODULE")

    def test_same_native_gene_number_in_different_genomes_is_distinct(self):
        rows = [{"genome_name": g, "module": "M00001", "module_definition": "K00001", "enzyme_hits_in_module": "K00001", "gene_caller_ids_in_module": "7"} for g in ["GCA_000001.1", "GCA_000002.1"]]
        summary = functional.audit_archive(self.archive(rows), self.snapshot,
                                           [self.mapping(), self.mapping("GCA_000002.1", "second"), self.mapping("3300000123_1", "missing")])
        self.assertEqual(summary["native_unique_gene_KO"], 2)
        mapping = list(functional.read_tsv(self.snapshot / "tables/taxon_reference_mapping.tsv"))
        missing = next(r for r in mapping if r["taxon"] == "missing")
        self.assertEqual(missing["archive_status"], "missing_unknown")
        self.assertEqual(missing["reference_annotation_status"], "unknown")

    def test_resume_rejects_corrupted_published_annotation_table(self):
        rows = [{"genome_name": "GCA_000001.1", "module": "M00001", "module_definition": "K00001", "enzyme_hits_in_module": "K00001", "gene_caller_ids_in_module": "7"}]
        archive = self.archive(rows)
        mapping = [self.mapping()]
        first = functional.audit_archive(archive, self.snapshot, mapping)
        self.assertEqual(functional.audit_archive(archive, self.snapshot, mapping), first)
        (self.snapshot / "tables/reference_annotations.tsv.gz").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            functional.audit_archive(archive, self.snapshot, mapping)

    def test_conflicting_metadata_mapping_is_not_resolved_by_prefix_swap(self):
        result = functional.make_mapping([{"taxon": "one", "genome_id": "GCA_000001.1"}],
                                         [{"taxon": "one", "genome_id": "GCF_000001.1"}])[0]
        self.assertEqual(result["mapping_status"], "conflicting_mapping")
        self.assertEqual(result["genome_id"], "")
        self.assertEqual(functional.reference_kind("GCA_000001"), "ncbi_unversioned_unresolved")

    def test_exact_ncbi_accession_and_version_required(self):
        requested = "GCA_000001.1"
        for replacement in ["GCF_000001.1", "GCA_000001.2"]:
            with self.assertRaisesRegex(ValueError, "exact accession"):
                functional.exact_ncbi_report({"reports": [{"accession": replacement}]}, requested)
        self.assertEqual(functional.exact_ncbi_report({"reports": [{"accession": requested}]}, requested)["accession"], requested)

    def package(self, genome="GCA_000001.1", report_genome=None):
        path = self.root / "package.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(f"ncbi_dataset/data/{genome}/protein.faa", ">proteinA native description\nMAAA\n>proteinB\nMXXX\n")
            archive.writestr("ncbi_dataset/data/assembly_data_report.jsonl", json.dumps({"accession": report_genome or genome}) + "\n")
            archive.writestr("../../outside.faa", "bad")
        return path

    def test_retrieval_extracts_only_exact_full_proteome(self):
        fasta = self.root / "protein.faa"
        count, report = functional.extract_exact_proteome(self.package(), "GCA_000001.1", fasta)
        self.assertEqual(count, 2)
        self.assertEqual(report["accession"], "GCA_000001.1")
        self.assertFalse((self.root.parent / "outside.faa").exists())
        with self.assertRaisesRegex(ValueError, "differs"):
            functional.extract_exact_proteome(self.package(report_genome="GCF_000001.1"), "GCA_000001.1", fasta)

    def test_retrieval_is_cacheable_only_with_matching_hash(self):
        package = self.package()
        report = {"reports": [{"accession": "GCA_000001.1", "annotation_info": {"stats": {"gene_counts": {"protein_coding": 2}}}}]}
        def copy_package(url, destination, max_bytes, timeout):
            destination.write_bytes(package.read_bytes())
            return destination.stat().st_size
        with mock.patch.object(functional, "request_json", return_value=report), mock.patch.object(functional, "bounded_download", side_effect=copy_package):
            first = functional.retrieve_reference(self.mapping(), self.snapshot)
        self.assertEqual(first["status"], "retrieved")
        self.assertEqual(first["protein_count_status"], "matches_report")
        with mock.patch.object(functional, "request_json", side_effect=AssertionError("cache must avoid network")):
            self.assertEqual(functional.retrieve_reference(self.mapping(), self.snapshot), first)
        Path(first["proteome_path"]).write_text(">changed\nMAA\n")
        with mock.patch.object(functional, "request_json", side_effect=AssertionError("corrupt snapshot must not silently replace a reference")):
            changed = functional.retrieve_reference(self.mapping(), self.snapshot)
        self.assertEqual(changed["status"], "cache_integrity_failed")
        self.assertEqual(changed["resolved_accession"], "")

    def test_stratified_pilot_preserves_native_ids_and_excludes_viruses(self):
        mapping = [self.mapping(f"GCA_{i:06}.1", f"t{i}", phylum=f"p__{i % 3}") for i in range(1, 10)]
        mapping += [self.mapping("3300001_1", "img"), self.mapping("GCA_000020.1", "virus", domain="d__Viruses")]
        first = functional.stratified_candidates(mapping, 6)
        self.assertEqual(first, functional.stratified_candidates(mapping, 6))
        self.assertEqual(len(first), 6)
        self.assertEqual(len({r["genome_id"] for r in first}), 6)
        self.assertFalse({"img", "virus"} & {r["taxon"] for r in first})
        self.assertEqual(len({r["phylum"] for r in first[:3]}), 3)

    def test_kofam_only_threshold_passing_native_hits(self):
        path = self.root / "kofam.tsv"
        path.write_text("# header\n*\tproteinA\tK00001\t20\t21\t1e-8\tdescription\n\tproteinB\tK00002\t20\t19\t1e-3\tdescription\n*\tproteinA\tK00001\t20\t21\t1e-8\tduplicate\n*\tproteinC\tK00003\t20\t19\t1e-3\tinconsistent marker\n")
        hits = list(functional.parse_kofam(path, "taxon", "GCA_000001.1", "kofam-20261008"))
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["gene_id"], "proteinA")
        self.assertEqual(hits[0]["source_kind"], "fresh_reference_kofam")

    def test_eggnog_keeps_namespaces_separate(self):
        path = self.root / "emapper.annotations"
        path.write_text("## metadata\n#query\tseed_ortholog\tevalue\tscore\teggNOG_OGs\tCOG_category\tKEGG_ko\tPFAMs\nproteinA\tref\t1e-9\t55\tOG1@1\tJ\tko:K00001,ko:K00002\tPF00001\n")
        hits = list(functional.parse_eggnog(path, "taxon", "GCA_000001.1", "eggnog-v5"))
        self.assertEqual({r["feature_id"] for r in hits if r["feature_namespace"] == "KEGG_KO"}, {"K00001", "K00002"})
        self.assertEqual({r["feature_namespace"] for r in hits}, {"KEGG_KO", "EGGNOG_OG", "COG_CATEGORY", "PFAM"})

    def test_missing_annotation_dependencies_do_not_install_or_crash(self):
        with mock.patch.object(functional.shutil, "which", return_value=None), mock.patch.object(functional.subprocess, "run", side_effect=AssertionError("must not install or execute absent tools")):
            result = functional.preflight_annotation("kofam")
        self.assertFalse(result["ready"])
        self.assertEqual(result["missing_commands"], ["exec_annotation", "hmmsearch", "ruby"])
        self.assertIn("database directory not configured", result["missing_database_paths"])

    def test_database_content_fingerprint_changes_with_profile_content(self):
        profiles = self.root / "profiles"
        profiles.mkdir()
        (profiles / "K00001.hmm").write_text("profile one")
        ko_list = self.root / "ko_list"
        ko_list.write_text("knum threshold\n")
        first = functional.database_fingerprint("kofam", profiles, self.snapshot, ko_list)
        self.assertEqual(first["file_count"], 2)
        repeated = functional.database_fingerprint("kofam", profiles, self.snapshot, ko_list)
        self.assertEqual(first["content_sha256"], repeated["content_sha256"])
        (profiles / "K00001.hmm").write_text("changed profile content")
        changed = functional.database_fingerprint("kofam", profiles, self.snapshot, ko_list)
        self.assertNotEqual(first["content_sha256"], changed["content_sha256"])

    def test_annotation_resume_requires_unchanged_proteome_and_database(self):
        profiles = self.root / "profiles"
        profiles.mkdir()
        profile = profiles / "K00001.hmm"
        profile.write_text("one profile")
        ko_list = self.root / "ko_list"
        ko_list.write_text("one threshold")
        fasta = self.root / "protein.faa"
        fasta.write_text(">proteinA\nMAAA\n")
        functional.write_tsv(self.snapshot / "tables/retrieval_manifest.tsv", functional.RETRIEVAL_FIELDS,
                             [{"taxon": "one", "genome_id": "GCA_000001.1", "status": "retrieved", "proteome_path": str(fasta), "proteome_sha256": functional.sha256_file(fasta)}])
        args = Namespace(tool="kofam", annotation_env_prefix=None, database_dir=profiles, ko_list=ko_list,
                         dry_run=False, db_snapshot="kofam-test", limit=1, cpu=1)
        preflight = {"ready": True, "version": "1.3.0", "binaries": {"exec_annotation": "/fake/exec_annotation"}}
        def fake_tool(command, **kwargs):
            Path(command[command.index("-o") + 1]).write_text("*\tproteinA\tK00001\t20\t21\t1e-8\tdescription\n")
            return Namespace(returncode=0)
        with mock.patch.object(functional, "preflight_annotation", return_value=preflight), mock.patch.object(functional.subprocess, "run", side_effect=fake_tool) as run:
            self.assertEqual(functional.annotate_retrieved(args, self.snapshot)["status"], "completed")
            self.assertEqual(functional.annotate_retrieved(args, self.snapshot)["status"], "completed")
            self.assertEqual(run.call_count, 1)
            profile.write_text("changed profile content")
            with self.assertRaisesRegex(ValueError, "incompatible"):
                functional.annotate_retrieved(args, self.snapshot)
        annotated = list(functional.read_tsv(self.snapshot / "tables/reference_annotations_kofam.tsv.gz"))
        self.assertEqual(len(annotated), 1)
        self.assertEqual(annotated[0]["source_kind"], "fresh_reference_kofam")


if __name__ == "__main__":
    unittest.main()
