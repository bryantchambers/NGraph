#!/usr/bin/env python3
"""Versioned reference-genome functional evidence, using only Python stdlib.

The archive is a module-scoped export, not a complete KO inventory. A missing
hit means unknown. Native (genome, gene, feature) identifiers are deduplicated
before expansion to taxa. Fresh public retrieval never substitutes GCA/GCF
prefixes or accession versions. All scores concern reference potential, not
measured activity in sediment samples. External annotation tools are preflighted
and never installed or accompanied by an automatic database download.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import logging
import os
from pathlib import Path
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BRANCH = "mvp_permissive_mixed_20261005"
DEFAULT_ARCHIVE = ROOT / "Source/ROCS/data/functional/kegg-modules-summary-rocs.tsv.gz"
DEFAULT_REFERENCE = ROOT / "data/reference/prokaryote_function_assigned.tsv"
NCBI_API = "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession"
ACCESSION = re.compile(r"^GC[AF]_\d+\.\d+$")
KO = re.compile(r"^K\d{5}$")
NA = {"", "NA", "N/A", "NaN", "nan", "None", "none", "null", '""'}
ANNOTATION_FIELDS = ["taxon", "genome_id", "gene_id", "feature_namespace", "feature_id",
                     "source_kind", "annotation_status", "score", "evalue", "threshold",
                     "source_path", "source_row", "db_snapshot", "archive_occurrences", "tool_version"]
MAPPING_FIELDS = ["taxon", "genome_id", "domain", "phylum", "reference_kind", "mapping_status",
                  "reference_annotation_status", "reference_source_path", "reference_source_row",
                  "taxa_source_path", "taxa_source_row", "archive_status"]
COMPLETENESS_FIELDS = ["taxon", "genome_id", "module_id", "module_namespace",
                       "stepwise_module_completeness", "pathwise_module_completeness",
                       "legacy_stepwise_is_complete", "legacy_pathwise_is_complete",
                       "source_kind", "source_path", "source_row", "db_snapshot", "warnings"]
PILOT_FIELDS = MAPPING_FIELDS + ["selection_rank", "selection_stratum", "retrieval_status"]
RETRIEVAL_FIELDS = ["taxon", "genome_id", "requested_accession", "resolved_accession", "status",
                    "report_url", "download_url", "proteome_path", "proteome_sha256",
                    "package_sha256", "protein_count", "reported_protein_coding_count",
                    "protein_count_status", "assembly_status", "organism_name", "retrieved_at", "error"]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def open_text(path, mode="rt"):
    return gzip.open(path, mode, encoding="utf-8", newline="") if str(path).endswith(".gz") else Path(path).open(mode.replace("t", ""), encoding="utf-8", newline="")


def read_tsv(path):
    with open_text(path) as handle:
        yield from csv.DictReader(handle, delimiter="\t")


def write_tsv(path, fields, rows):
    """Atomic table publication; the temporary suffix preserves gzip handling."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(".tmp-" + path.name)
    with open_text(temp, "wt") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(".tmp-" + path.name)
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temp.replace(path)


def reference_kind(genome):
    if ACCESSION.fullmatch(genome):
        return "ncbi_versioned_assembly"
    if re.fullmatch(r"GC[AF]_\d+", genome):
        return "ncbi_unversioned_unresolved"
    if re.fullmatch(r"\d+(?:_\d+)?", genome):
        return "img_native_unresolved"
    return "other_native_unresolved" if genome else "missing"


def make_mapping(taxa_rows, reference_rows, taxa_path="", reference_path=""):
    lookup = defaultdict(list)
    for number, row in enumerate(reference_rows, 2):
        lookup[row["taxon"]].append((number, row))
    result = []
    for number, row in enumerate(taxa_rows, 2):
        taxon = row["taxon"]
        matches = lookup.get(taxon, [])
        ids = {r.get("genome_id", "").strip() for _, r in matches}
        ids.discard("")
        metadata_id = row.get("genome_id", "").strip()
        if metadata_id:
            ids.add(metadata_id)
        genome = next(iter(ids)) if len(ids) == 1 else ""
        state = "exact_native_mapping" if genome else "conflicting_mapping" if len(ids) > 1 else "missing_mapping"
        first = matches[0] if matches else ("", {})
        domain = row.get("domain") or first[1].get("domain", "")
        kind = reference_kind(genome)
        result.append({"taxon": taxon, "genome_id": genome, "domain": domain,
                       "phylum": row.get("phylum") or first[1].get("phylum", ""),
                       "reference_kind": kind, "mapping_status": state,
                       "reference_annotation_status": "viral_separate_reference_layer" if domain == "d__Viruses" else "unknown",
                       "reference_source_path": str(reference_path), "reference_source_row": first[0],
                       "taxa_source_path": str(taxa_path), "taxa_source_row": number,
                       "archive_status": "not_audited"})
    if len({r["taxon"] for r in result}) != len(result):
        raise ValueError("The selected taxa table contains duplicate taxon identifiers")
    return result


def module_namespace(module):
    return "KEGG_MODULE" if re.fullmatch(r"M\d{5}", module) else "CUSTOM_MODULE" if re.fullmatch(r"W\d{5}", module) else "OTHER_MODULE"


def paired_native_hits(row):
    """Do not zip/truncate mismatched enzyme and native gene lists."""
    enzymes = [x.strip() for x in row.get("enzyme_hits_in_module", "").split(",") if x.strip() not in NA]
    genes = [x.strip() for x in row.get("gene_caller_ids_in_module", "").split(",") if x.strip() not in NA]
    if len(enzymes) != len(genes):
        raise ValueError("mismatched_gene_and_enzyme_lists")
    return [(gene, "KEGG_KO" if KO.fullmatch(enzyme) else "LEGACY_FEATURE", enzyme) for gene, enzyme in zip(genes, enzymes)]


def audit_archive(archive, snapshot, mapping, *, force=False):
    """Single streaming pass; SQLite holds selected native hits and provenance."""
    archive, snapshot = Path(archive), Path(snapshot)
    tables = snapshot / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    digest = sha256_file(archive)
    mapping_digest = hashlib.sha256(json.dumps(mapping, sort_keys=True).encode()).hexdigest()
    summary_path = snapshot / "archive_audit.json"
    if summary_path.exists() and not force:
        saved = json.loads(summary_path.read_text())
        if saved.get("archive_sha256") != digest or saved.get("mapping_sha256") != mapping_digest:
            raise ValueError("Snapshot inputs changed: select a new snapshot instead of overwriting an audit")
        if all((tables / name).exists() for name in saved["output_tables"]):
            if any(sha256_file(tables / name) != digest for name, digest in saved.get("output_sha256", {}).items()):
                raise ValueError("Published audit output hash changed; do not reuse a corrupted snapshot")
            if not (snapshot / "native_annotations.sqlite").exists():
                raise ValueError("Published audit lost its native SQLite cache")
            return saved
    db_path = snapshot / "native_annotations.sqlite"
    temp_db = snapshot / ".native_annotations.pending.sqlite"
    temp_db.unlink(missing_ok=True)
    connection = sqlite3.connect(temp_db)
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute("CREATE TABLE hits(genome TEXT,gene TEXT,namespace TEXT,feature TEXT,source_row INTEGER,occurrences INTEGER,PRIMARY KEY(genome,gene,namespace,feature)) WITHOUT ROWID")
    genome_taxa = defaultdict(list)
    for row in mapping:
        if row["mapping_status"] == "exact_native_mapping":
            genome_taxa[row["genome_id"]].append(row["taxon"])
    archive_genomes, selected_found = set(), set()
    definitions, counter, flags = {}, Counter(), {}
    inserts = []
    comp_path = tables / "legacy_module_completeness.tsv.gz"
    comp_temp = comp_path.with_name(".tmp-" + comp_path.name)
    insert_sql = "INSERT INTO hits VALUES(?,?,?,?,?,1) ON CONFLICT(genome,gene,namespace,feature) DO UPDATE SET occurrences=occurrences+1"
    try:
        with open_text(comp_temp, "wt") as output, open_text(archive) as source:
            writer = csv.DictWriter(output, fieldnames=COMPLETENESS_FIELDS, delimiter="\t")
            writer.writeheader()
            reader = csv.DictReader(source, delimiter="\t")
            required = {"module", "genome_name", "module_definition", "enzyme_hits_in_module", "gene_caller_ids_in_module"}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError("Archive lacks required module/genome/native gene fields")
            for source_row, row in enumerate(reader, 2):
                counter["archive_rows"] += 1
                genome, module = row["genome_name"], row["module"]
                archive_genomes.add(genome)
                definition = row["module_definition"]
                key = (module, definition)
                if key not in definitions:
                    definitions[key] = {"module_id": module, "module_namespace": module_namespace(module),
                                        "module_name": row.get("module_name", ""), "module_definition": definition,
                                        "module_class": row.get("module_class", ""), "module_category": row.get("module_category", ""),
                                        "module_subcategory": row.get("module_subcategory", ""),
                                        "definition_sha256": hashlib.sha256(definition.encode()).hexdigest(),
                                        "source_kind": "unknown_legacy", "source_path": str(archive),
                                        "source_row": source_row, "db_snapshot": snapshot.name}
                for score_key, flag_key in [("stepwise_module_completeness", "stepwise_module_is_complete"), ("pathwise_module_completeness", "pathwise_module_is_complete")]:
                    try:
                        score = float(row.get(score_key, ""))
                    except ValueError:
                        continue
                    if row.get(flag_key, "").upper() in {"TRUE", "FALSE"}:
                        flag = flag_key + ":" + row[flag_key].upper()
                        aggregate = flags.setdefault(flag, {"min": score, "max": score, "n": 0})
                        aggregate["min"] = min(aggregate["min"], score)
                        aggregate["max"] = max(aggregate["max"], score)
                        aggregate["n"] += 1
                if genome not in genome_taxa:
                    continue
                counter["selected_archive_rows"] += 1
                selected_found.add(genome)
                for taxon in genome_taxa[genome]:
                    writer.writerow({"taxon": taxon, "genome_id": genome, "module_id": module,
                                     "module_namespace": module_namespace(module),
                                     "stepwise_module_completeness": row.get("stepwise_module_completeness", ""),
                                     "pathwise_module_completeness": row.get("pathwise_module_completeness", ""),
                                     "legacy_stepwise_is_complete": row.get("stepwise_module_is_complete", ""),
                                     "legacy_pathwise_is_complete": row.get("pathwise_module_is_complete", ""),
                                     "source_kind": "unknown_legacy", "source_path": str(archive), "source_row": source_row,
                                     "db_snapshot": snapshot.name, "warnings": row.get("warnings", "")})
                    counter["taxon_module_rows"] += 1
                try:
                    hits = paired_native_hits(row)
                except ValueError:
                    counter["mismatched_gene_enzyme_rows"] += 1
                    continue
                for gene, namespace, feature in hits:
                    inserts.append((genome, gene, namespace, feature, source_row))
                    counter["selected_hit_occurrences"] += 1
                if len(inserts) >= 10000:
                    connection.executemany(insert_sql, inserts)
                    inserts.clear()
                if counter["archive_rows"] % 250000 == 0:
                    logging.info("Archive streamed rows=%s selected=%s", counter["archive_rows"], counter["selected_archive_rows"])
            if inserts:
                connection.executemany(insert_sql, inserts)
            connection.commit()
        comp_temp.replace(comp_path)
        native_count = connection.execute("SELECT COUNT(*) FROM hits").fetchone()[0]
        native_ko_count = connection.execute("SELECT COUNT(*) FROM hits WHERE namespace='KEGG_KO'").fetchone()[0]
        hit_genomes = {r[0] for r in connection.execute("SELECT DISTINCT genome FROM hits WHERE namespace='KEGG_KO'")}
        features = connection.execute("SELECT COUNT(DISTINCT feature) FROM hits WHERE namespace='KEGG_KO'").fetchone()[0]

        def annotations():
            for genome, gene, namespace, feature, source_row, occurrences in connection.execute("SELECT * FROM hits ORDER BY genome,gene,namespace,feature"):
                for taxon in genome_taxa[genome]:
                    counter["taxon_annotation_rows"] += 1
                    yield {"taxon": taxon, "genome_id": genome, "gene_id": gene, "feature_namespace": namespace,
                           "feature_id": feature, "source_kind": "unknown_legacy", "annotation_status": "present_reference",
                           "score": "", "evalue": "", "threshold": "", "source_path": str(archive), "source_row": source_row,
                           "db_snapshot": snapshot.name, "archive_occurrences": occurrences, "tool_version": "unknown"}

        write_tsv(tables / "reference_annotations.tsv.gz", ANNOTATION_FIELDS, annotations())
        def_fields = ["module_id", "module_namespace", "module_name", "module_definition", "module_class", "module_category", "module_subcategory", "definition_sha256", "source_kind", "source_path", "source_row", "db_snapshot"]
        write_tsv(tables / "module_definitions.tsv", def_fields, sorted(definitions.values(), key=lambda x: (x["module_id"], x["definition_sha256"])))
        enriched = []
        for row in mapping:
            row = dict(row)
            genome = row["genome_id"]
            row["archive_status"] = "module_scoped_KO_present" if genome in hit_genomes else "archive_rows_without_KO" if genome in selected_found else "missing_unknown"
            enriched.append(row)
        write_tsv(tables / "taxon_reference_mapping.tsv", MAPPING_FIELDS, enriched)
        module_variants = Counter(k[0] for k in definitions)
        summary = {"created_at": utc_now(), "seed": 42, "archive_path": str(archive), "archive_sha256": digest,
                   "mapping_sha256": mapping_digest, "counts": dict(counter), "archive_native_genomes": len(archive_genomes),
                   "selected_native_genomes": len(genome_taxa), "selected_genomes_in_archive": len(selected_found),
                   "selected_genomes_with_KO": len(hit_genomes), "native_unique_gene_features": native_count,
                   "native_unique_gene_KO": native_ko_count, "unique_KO_features": features,
                   "duplicate_module_hit_occurrences_removed": counter["selected_hit_occurrences"] - native_count,
                   "definition_variants": len(definitions), "modules": len(module_variants),
                   "conflicting_module_definition_ids": sorted(k for k, v in module_variants.items() if v > 1),
                   "legacy_complete_score_ranges": flags,
                   "completion_policy": "Preserve exported boolean and continuous score; true does not mean 100 percent. Original threshold/tool/database version unknown.",
                   "missing_policy": "Missing archive KO is unknown; export contains only module-associated features.",
                   "provenance_policy": "First source row plus occurrence count; native genome/gene/feature dedup before taxon expansion; legacy origin not promoted.",
                   "output_tables": ["taxon_reference_mapping.tsv", "reference_annotations.tsv.gz", "module_definitions.tsv", "legacy_module_completeness.tsv.gz"]}
        connection.close()
        temp_db.replace(db_path)
        summary["output_sha256"] = {name: sha256_file(tables / name) for name in summary["output_tables"]}
        write_json(summary_path, summary)
        return summary
    except BaseException:
        connection.close()
        raise


def stratified_candidates(mapping, count, seed=42):
    """Round-robin domain/phylum sampling, one native genome per candidate."""
    groups = defaultdict(list)
    seen = set()
    for row in sorted(mapping, key=lambda r: r["taxon"]):
        genome = row["genome_id"]
        if row["mapping_status"] != "exact_native_mapping" or row["reference_kind"] != "ncbi_versioned_assembly" or row["domain"] == "d__Viruses" or genome in seen:
            continue
        seen.add(genome)
        groups[(row["domain"], row["phylum"])].append(dict(row))
    rng = random.Random(seed)
    for group in groups.values():
        rng.shuffle(group)
    # Alternate domains and prioritize larger phyla within each domain. An
    # alphabetical truncation would exclude common phyla when count < strata.
    by_domain = defaultdict(list)
    for key in groups:
        by_domain[key[0]].append(key)
    for domain in by_domain:
        by_domain[domain].sort(key=lambda key: (-len(groups[key]), key[1]))
    order = []
    for index in range(max((len(keys) for keys in by_domain.values()), default=0)):
        for domain in sorted(by_domain):
            if index < len(by_domain[domain]):
                order.append(by_domain[domain][index])
    result = []
    while order and len(result) < count:
        remaining = []
        for stratum in order:
            if not groups[stratum]:
                continue
            row = groups[stratum].pop()
            row.update(selection_rank=len(result) + 1, selection_stratum="|".join(stratum), retrieval_status="pending")
            result.append(row)
            if groups[stratum]:
                remaining.append(stratum)
            if len(result) >= count:
                break
        order = remaining
    return result


def exact_ncbi_report(document, accession):
    matches = [r for r in document.get("reports", []) if r.get("accession") == accession]
    if len(matches) != 1:
        raise ValueError("NCBI returned no unique exact accession/version; aliases are not substituted")
    return matches[0]


def request_json(url, timeout=45):
    request = urllib.request.Request(url, headers={"User-Agent": "NGraph-functional-reference/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def bounded_download(url, destination, max_bytes, timeout=60):
    temp = Path(destination).with_name(".pending-" + Path(destination).name)
    total = 0
    request = urllib.request.Request(url, headers={"User-Agent": "NGraph-functional-reference/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, temp.open("wb") as output:
            for block in iter(lambda: response.read(1024 * 1024), b""):
                total += len(block)
                if total > max_bytes:
                    raise ValueError("Reference package exceeds configured resource budget")
                output.write(block)
        temp.replace(destination)
    finally:
        temp.unlink(missing_ok=True)
    return total


def fasta_count(path):
    count, ids = 0, set()
    with Path(path).open() as handle:
        for line in handle:
            if line.startswith(">"):
                native_id = line[1:].split()[0]
                if not native_id or native_id in ids:
                    raise ValueError("Proteome has empty or duplicate native protein identifiers")
                ids.add(native_id)
                count += 1
    if not count:
        raise ValueError("No proteins in reference FASTA")
    return count


def extract_exact_proteome(package, accession, destination):
    """Extract only the exact selected member, never arbitrary zip paths."""
    with zipfile.ZipFile(package) as archive:
        target = f"ncbi_dataset/data/{accession}/protein.faa"
        if target not in archive.namelist():
            raise ValueError("Exact assembly package contains no annotated protein FASTA")
        info = archive.getinfo(target)
        if info.file_size > 100 * 1024 * 1024:
            raise ValueError("Proteome exceeds pilot extraction budget")
        report_path = "ncbi_dataset/data/assembly_data_report.jsonl"
        if report_path not in archive.namelist():
            raise ValueError("Package lacks assembly provenance report")
        reports = [json.loads(line) for line in archive.read(report_path).decode().splitlines() if line.strip()]
        if len(reports) != 1 or reports[0].get("accession") != accession:
            raise ValueError("Downloaded package accession/version differs from requested reference")
        temp = Path(destination).with_name(".pending-" + Path(destination).name)
        with archive.open(target) as source, temp.open("wb") as output:
            shutil.copyfileobj(source, output)
        count = fasta_count(temp)
        temp.replace(destination)
        return count, reports[0]


def retrieve_reference(row, snapshot, *, max_package_bytes=20 * 1024 * 1024, timeout=45, retry_failed=False):
    genome = row["genome_id"]
    result = {k: "" for k in RETRIEVAL_FIELDS}
    result.update(taxon=row["taxon"], genome_id=genome, requested_accession=genome, retrieved_at=utc_now())
    if not ACCESSION.fullmatch(genome):
        result.update(status="unresolved_native_reference", error="Exact versioned public assembly accession required")
        return result
    folder = Path(snapshot) / "references" / genome
    folder.mkdir(parents=True, exist_ok=True)
    cached = folder / "retrieval.json"
    if cached.exists():
        existing = json.loads(cached.read_text())
        fasta = Path(existing.get("proteome_path", "/missing"))
        if existing.get("status") == "retrieved":
            package = folder / "ncbi_dataset.zip"
            if existing.get("resolved_accession") == genome and fasta.is_file() and package.is_file() and sha256_file(fasta) == existing.get("proteome_sha256") and sha256_file(package) == existing.get("package_sha256"):
                return existing
            result.update(status="cache_integrity_failed", error="Published reference cache hash/accession changed; choose a new snapshot")
            return result
        if not retry_failed:
            return existing
    report_url = f"{NCBI_API}/{urllib.parse.quote(genome)}/dataset_report"
    download_url = f"{NCBI_API}/{urllib.parse.quote(genome)}/download?include_annotation_type=PROT_FASTA"
    result.update(report_url=report_url, download_url=download_url)
    try:
        doc = request_json(report_url, timeout)
        report = exact_ncbi_report(doc, genome)
        write_json(folder / "ncbi_report.json", doc)
        expected = report.get("annotation_info", {}).get("stats", {}).get("gene_counts", {}).get("protein_coding", "")
        package = folder / "ncbi_dataset.zip"
        bounded_download(download_url, package, max_package_bytes, timeout)
        fasta = folder / "protein.faa"
        count, package_report = extract_exact_proteome(package, genome, fasta)
        write_json(folder / "package_report.json", package_report)
        result.update(resolved_accession=genome, status="retrieved", proteome_path=str(fasta),
                      proteome_sha256=sha256_file(fasta), package_sha256=sha256_file(package), protein_count=count,
                      reported_protein_coding_count=expected,
                      protein_count_status="matches_report" if expected != "" and count == int(expected) else "different_from_report" if expected != "" else "report_count_unknown",
                      assembly_status=report.get("assembly_info", {}).get("assembly_status", "unknown"),
                      organism_name=report.get("organism", {}).get("organism_name", ""))
    except (urllib.error.URLError, ValueError, zipfile.BadZipFile, OSError, json.JSONDecodeError) as error:
        result.update(status="retrieval_failed_unknown", error=f"{type(error).__name__}: {error}")
    write_json(cached, result)
    return result


def export_reference_quality(snapshot, retrieval_rows):
    fields = ["taxon", "genome_id", "retrieval_status", "quality_status", "checkm_completeness_percent",
              "checkm_contamination_percent", "checkm_version", "checkm_marker_set", "assembly_level",
              "assembly_status", "assembly_release_date", "annotation_name", "annotation_provider",
              "annotation_release_date", "annotation_software_version", "protein_count", "reported_protein_coding_count",
              "protein_count_status", "proteome_sha256", "source_path", "source_sha256"]
    rows = []
    for retrieved in retrieval_rows:
        row = {key: "" for key in fields}
        row.update({key: retrieved.get(key, "") for key in ["taxon", "genome_id", "protein_count", "reported_protein_coding_count", "protein_count_status", "proteome_sha256"]})
        row.update(retrieval_status=retrieved["status"], quality_status="no_validated_proteome" if retrieved["status"] != "retrieved" else "unknown_reference_quality")
        source = Path(snapshot) / "references" / retrieved["genome_id"] / "ncbi_report.json"
        if source.is_file() and retrieved["status"] == "retrieved":
            report = exact_ncbi_report(json.loads(source.read_text()), retrieved["genome_id"])
            checkm, info, annotation = report.get("checkm_info", {}), report.get("assembly_info", {}), report.get("annotation_info", {})
            row.update(checkm_completeness_percent=checkm.get("completeness", ""), checkm_contamination_percent=checkm.get("contamination", ""),
                       checkm_version=checkm.get("checkm_version", ""), checkm_marker_set=checkm.get("checkm_marker_set", ""),
                       assembly_level=info.get("assembly_level", ""), assembly_status=info.get("assembly_status", ""), assembly_release_date=info.get("release_date", ""),
                       annotation_name=annotation.get("name", ""), annotation_provider=annotation.get("provider", ""),
                       annotation_release_date=annotation.get("release_date", ""), annotation_software_version=annotation.get("software_version", ""),
                       source_path=str(source), source_sha256=sha256_file(source))
            if "completeness" in checkm and "contamination" in checkm:
                completeness, contamination = float(checkm["completeness"]), float(checkm["contamination"])
                row["quality_status"] = "high_completeness_low_contamination_metrics" if completeness >= 90 and contamination <= 5 else "partial_reference_metrics" if completeness >= 50 and contamination <= 10 else "limited_reference_metrics"
        rows.append(row)
    write_tsv(Path(snapshot) / "tables/reference_quality.tsv", fields, rows)
    return dict(Counter(row["quality_status"] for row in rows))


def preflight_annotation(tool, env_prefix=None, database_dir=None, ko_list=None):
    commands = ["exec_annotation", "hmmsearch", "ruby"] if tool == "kofam" else ["emapper.py", "diamond"]
    prefix = Path(env_prefix) / "bin" if env_prefix else None
    binaries = {name: str(prefix / name) if prefix and (prefix / name).exists() else shutil.which(name) for name in commands}
    expected = "1.3.0" if tool == "kofam" else "2.1.14"
    output = {"tool": tool, "expected_version": expected, "binaries": binaries, "missing_commands": [k for k, v in binaries.items() if not v], "missing_database_paths": [], "version": "unknown", "ready": False}
    directory = Path(database_dir) if database_dir else None
    required = ([directory] if tool == "kofam" else [directory / "eggnog.db", directory / "eggnog_proteins.dmnd"]) if directory else []
    if directory is None:
        output["missing_database_paths"].append("database directory not configured")
    for path in required:
        if not path.exists():
            output["missing_database_paths"].append(str(path))
    if tool == "kofam":
        if not ko_list or not Path(ko_list).is_file():
            output["missing_database_paths"].append(str(ko_list or "KO list not configured"))
        if directory and directory.exists() and not any(directory.glob("*.hmm")):
            output["missing_database_paths"].append(str(directory / "*.hmm"))
    primary = binaries[commands[0]]
    if primary:
        try:
            env = dict(os.environ)
            if prefix:
                env["PATH"] = str(prefix) + os.pathsep + env.get("PATH", "")
            run = subprocess.run([primary, "--version"], capture_output=True, text=True, timeout=30, env=env)
            output["version_output"] = (run.stdout + run.stderr).strip()[:2000]
            output["version"] = expected if re.search(r"(?<![\d.])" + re.escape(expected) + r"(?![\d.])", output["version_output"]) else "unverified"
        except (OSError, subprocess.TimeoutExpired) as error:
            output["version_output"] = str(error)
    output["ready"] = not output["missing_commands"] and not output["missing_database_paths"] and output["version"] == expected
    return output


def database_fingerprint(tool, directory, snapshot, ko_list=None):
    """Hash actual database content once; reuse hashes only for unchanged files.

    No files are downloaded. This can take time for an existing eggNOG database,
    so the versioned snapshot retains the per-file manifest for resumed runs.
    """
    directory = Path(directory).resolve()
    manifest_path = Path(snapshot) / f"database_hash_manifest_{tool}.json"
    cached = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    previous = {r["path"]: r for r in cached.get("files", [])}
    paths = sorted(directory.rglob("*.hmm")) + [Path(ko_list).resolve()] if tool == "kofam" else sorted(directory.glob("*.db")) + sorted(directory.glob("*.dmnd"))
    rows = []
    for path in paths:
        stat = path.stat()
        key = str(path.resolve())
        old = previous.get(key, {})
        metadata = {"path": key, "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}
        digest = old.get("sha256") if all(old.get(k) == value for k, value in metadata.items()) else None
        metadata["sha256"] = digest or sha256_file(path)
        rows.append(metadata)
    if not rows:
        raise ValueError("No database content available to fingerprint")
    identities = [(str(Path(r["path"]).relative_to(directory)) if Path(r["path"]).is_relative_to(directory) else "ko_list", r["sha256"]) for r in rows]
    content_sha256 = hashlib.sha256(json.dumps(identities, separators=(",", ":")).encode()).hexdigest()
    manifest = {"created_at": utc_now(), "tool": tool, "directory": str(directory), "content_sha256": content_sha256,
                "files": rows, "total_size_bytes": sum(r["size_bytes"] for r in rows),
                "policy": "Actual local file SHA256; unchanged size/mtime cache reused. No download or installation."}
    write_json(manifest_path, manifest)
    return {"manifest_path": str(manifest_path), "content_sha256": content_sha256, "file_count": len(rows), "total_size_bytes": manifest["total_size_bytes"]}


def parse_kofam(path, taxon, genome, snapshot, version="1.3.0"):
    """Kofam detail-tsv: retain only assignments passing adaptive KO thresholds."""
    seen = set()
    with Path(path).open() as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip() or line.startswith("#"):
                continue
            pieces = line.rstrip("\n").split("\t")
            if len(pieces) < 6 or pieces[0].strip() != "*":
                continue
            gene, feature, threshold, score, evalue = [x.strip() for x in pieces[1:6]]
            if not KO.fullmatch(feature):
                continue
            if float(score) < float(threshold):
                continue
            key = (gene, feature)
            if key in seen:
                continue
            seen.add(key)
            yield {"taxon": taxon, "genome_id": genome, "gene_id": gene, "feature_namespace": "KEGG_KO", "feature_id": feature,
                   "source_kind": "fresh_reference_kofam", "annotation_status": "present_reference", "score": score,
                   "evalue": evalue, "threshold": threshold, "source_path": str(path), "source_row": number,
                   "db_snapshot": snapshot, "archive_occurrences": 1, "tool_version": version}


def parse_eggnog(path, taxon, genome, snapshot, version="2.1.14"):
    headers, seen = None, set()
    with Path(path).open() as handle:
        for number, line in enumerate(handle, 1):
            if line.startswith("#query\t"):
                headers = line.strip().lstrip("#").split("\t")
                continue
            if line.startswith("#") or not line.strip():
                continue
            if headers is None:
                raise ValueError("eggNOG annotation output lacks a named #query header")
            row = dict(zip(headers, line.rstrip("\n").split("\t")))
            for namespace, key in [("KEGG_KO", "KEGG_ko"), ("EGGNOG_OG", "eggNOG_OGs"), ("COG_CATEGORY", "COG_category"), ("PFAM", "PFAMs"), ("GO", "GOs"), ("EC", "EC")]:
                values = list(row.get(key, "-")) if namespace == "COG_CATEGORY" else row.get(key, "-").split(",")
                for feature in values:
                    feature = feature.strip().removeprefix("ko:")
                    if feature in {"-", ""} or namespace == "KEGG_KO" and not KO.fullmatch(feature):
                        continue
                    identity = (row["query"], namespace, feature)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    yield {"taxon": taxon, "genome_id": genome, "gene_id": row["query"], "feature_namespace": namespace,
                           "feature_id": feature, "source_kind": "fresh_reference_eggnog", "annotation_status": "present_reference",
                           "score": row.get("score", ""), "evalue": row.get("evalue", ""), "threshold": "orthology_transfer",
                           "source_path": str(path), "source_row": number, "db_snapshot": snapshot,
                           "archive_occurrences": 1, "tool_version": version}


def annotate_retrieved(args, snapshot):
    tool = args.tool
    preflight = preflight_annotation(tool, args.annotation_env_prefix, args.database_dir, args.ko_list)
    write_json(snapshot / f"annotation_preflight_{tool}.json", preflight)
    if args.dry_run or not preflight["ready"]:
        return {"status": "ready" if preflight["ready"] else "blocked_missing_tool_or_database", "preflight": preflight, "dry_run": args.dry_run}
    if not args.db_snapshot:
        raise ValueError("Fresh annotation requires an explicit versioned --db-snapshot identifier")
    database = database_fingerprint(tool, args.database_dir, snapshot, args.ko_list)
    retrieved = [r for r in read_tsv(snapshot / "tables/retrieval_manifest.tsv") if r["status"] == "retrieved"]
    output_dir = snapshot / "annotations" / tool
    output_dir.mkdir(parents=True, exist_ok=True)
    run_manifest = {"created_at": utc_now(), "seed": 42, "tool": tool, "db_snapshot": args.db_snapshot,
                    "database_dir": str(Path(args.database_dir).resolve()), "ko_list_sha256": sha256_file(args.ko_list) if tool == "kofam" else None,
                    "preflight": preflight, "database_fingerprint": database, "runs": []}
    env = dict(os.environ)
    if args.annotation_env_prefix:
        env["PATH"] = str(Path(args.annotation_env_prefix) / "bin") + os.pathsep + env.get("PATH", "")
    for row in retrieved[:args.limit]:
        genome = row["genome_id"]
        fasta = Path(row["proteome_path"])
        if sha256_file(fasta) != row["proteome_sha256"]:
            raise ValueError("Retrieved reference hash changed before annotation")
        if tool == "kofam":
            output = output_dir / f"{genome}.detail.tsv"
            command = [preflight["binaries"]["exec_annotation"], "-p", str(Path(args.database_dir).resolve()), "-k", str(Path(args.ko_list).resolve()), "--cpu", str(args.cpu), "-f", "detail-tsv", "-o", str(output), str(fasta)]
        else:
            output = output_dir / f"{genome}.emapper.annotations"
            command = [preflight["binaries"]["emapper.py"], "-i", str(fasta), "--itype", "proteins", "--data_dir", str(Path(args.database_dir).resolve()), "--cpu", str(args.cpu), "-m", "diamond", "--output_dir", str(output_dir), "-o", genome]
        marker = output_dir / f"{genome}.completed.json"
        signature = {"command": command, "proteome_sha256": row["proteome_sha256"], "db_snapshot": args.db_snapshot,
                     "database_content_sha256": database["content_sha256"], "tool_version": preflight["version"]}
        cached = json.loads(marker.read_text()) if marker.exists() else {}
        if not (output.exists() and cached.get("signature") == signature and cached.get("output_sha256") == sha256_file(output)):
            started = output_dir / f"{genome}.started.json"
            if output.exists():
                prior = json.loads(started.read_text()) if started.exists() else {}
                if marker.exists() or prior.get("signature") != signature:
                    raise ValueError("Existing annotation is incompatible with this run; use a new snapshot")
                # Only remove an incomplete file created by this exact recorded
                # tool invocation. Published or foreign output is preserved.
                output.unlink()
            write_json(started, {"signature": signature, "started_at": utc_now()})
            execution_command = command + ["--resume"] if tool == "eggnog" and (output_dir / f"{genome}.emapper.seed_orthologs").exists() else command
            with (output_dir / f"{genome}.tool.log").open("w") as log:
                completed = subprocess.run(execution_command, stdout=log, stderr=subprocess.STDOUT, env=env)
            if completed.returncode or not output.exists():
                raise RuntimeError(f"{tool} failed for {genome}; inspect tool log")
            write_json(marker, {"signature": signature, "execution_command": execution_command, "output_sha256": sha256_file(output), "completed_at": utc_now()})
        completed_record = json.loads(marker.read_text())
        run_manifest["runs"].append({"genome_id": genome, "taxon": row["taxon"], "output_path": str(output),
                                     "execution_command": completed_record.get("execution_command", command), **signature})
        write_json(snapshot / f"annotation_run_{tool}.json", run_manifest)

    def records():
        parser = parse_kofam if tool == "kofam" else parse_eggnog
        for run in run_manifest["runs"]:
            yield from parser(run["output_path"], run["taxon"], run["genome_id"], args.db_snapshot, preflight["version"])
    write_tsv(snapshot / "tables" / f"reference_annotations_{tool}.tsv.gz", ANNOTATION_FIELDS, records())
    return {"status": "completed", "tool": tool, "annotated_genomes": len(run_manifest["runs"]), "db_snapshot": args.db_snapshot}


def snapshot_manifest(snapshot, command, args, result):
    path = snapshot / "snapshot_manifest.json"
    value = json.loads(path.read_text()) if path.exists() else {"snapshot": snapshot.name, "created_at": utc_now(), "seed": 42, "python_version": sys.version.split()[0], "commands": []}
    record = {"recorded_at": utc_now(), "command": command, "argv": sys.argv[1:],
              "script_sha256": sha256_file(Path(__file__)),
              "runtime_command": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
              "status": result.get("status", "completed")}
    if command in {"map", "audit"}:
        taxa = args.taxa or ROOT / "results/ngraph" / args.branch / args.threshold / "tables/ngraph_taxa_metadata.tsv"
        record["inputs"] = {str(path.resolve()): sha256_file(path) for path in [taxa, args.reference]}
        if command == "audit":
            record["inputs"][str(args.archive.resolve())] = result["archive_sha256"]
    value["commands"].append(record)
    value["updated_at"] = utc_now()
    value["evidence_kind"] = "reference_genome_functional_potential"
    value["activity_measured"] = False
    write_json(path, value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["map", "audit", "pilot", "retrieve", "annotate"])
    parser.add_argument("--snapshot", default="functional_20261008")
    parser.add_argument("--snapshot-root", type=Path, default=ROOT / "data/reference/functional")
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument("--threshold", default="prev_10")
    parser.add_argument("--taxa", type=Path)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--size", type=int, default=32)
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--attempt-limit", type=int, default=96)
    parser.add_argument("--max-download-mb", type=int, default=512)
    parser.add_argument("--max-package-mb", type=int, default=20)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--retry-failed", action="store_true", help="Explicitly retry cached public reference failures")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--tool", choices=["kofam", "eggnog"], default="kofam")
    parser.add_argument("--annotation-env-prefix", type=Path)
    parser.add_argument("--database-dir", type=Path)
    parser.add_argument("--ko-list", type=Path)
    parser.add_argument("--db-snapshot")
    parser.add_argument("--cpu", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if Path(args.snapshot).name != args.snapshot or args.snapshot in {"", ".", ".."}:
        parser.error("snapshot must be a directory label, not a path")
    if min(args.size, args.limit, args.attempt_limit, args.max_download_mb, args.max_package_mb, args.timeout, args.cpu) <= 0:
        parser.error("resource limits must be positive")
    random.seed(42)
    snapshot = (args.snapshot_root / args.snapshot).resolve()
    snapshot.mkdir(parents=True, exist_ok=True)
    tables = snapshot / "tables"
    tables.mkdir(exist_ok=True)
    log_dir = ROOT / "logs" / args.snapshot
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_dir / "functional_references.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("command=%s seed=42 python=%s snapshot=%s", args.command, sys.version.split()[0], snapshot)
    csv.field_size_limit(16 * 1024 * 1024)
    taxa = args.taxa or ROOT / "results/ngraph" / args.branch / args.threshold / "tables/ngraph_taxa_metadata.tsv"
    mapping_path = tables / "taxon_reference_mapping.tsv"
    if args.command in {"map", "audit"}:
        mapping = make_mapping(list(read_tsv(taxa)), list(read_tsv(args.reference)), str(taxa.resolve()), str(args.reference.resolve()))
        if args.command == "map":
            audit_path = snapshot / "archive_audit.json"
            if audit_path.exists():
                audited = json.loads(audit_path.read_text())
                digest = hashlib.sha256(json.dumps(mapping, sort_keys=True).encode()).hexdigest()
                if digest != audited["mapping_sha256"]:
                    raise ValueError("Mapping inputs differ from the published audit; select a new snapshot")
                if not mapping_path.exists() or sha256_file(mapping_path) != audited["output_sha256"][mapping_path.name]:
                    raise ValueError("Published mapping table changed; do not overwrite provenance")
                mapping = list(read_tsv(mapping_path))
            else:
                write_tsv(mapping_path, MAPPING_FIELDS, mapping)
            result = {"taxa": len(mapping), "mapping_status": dict(Counter(r["mapping_status"] for r in mapping)), "reference_kind": dict(Counter(r["reference_kind"] for r in mapping))}
        else:
            result = audit_archive(args.archive.resolve(), snapshot, mapping, force=args.force)
    elif args.command == "pilot":
        mapping = list(read_tsv(mapping_path))
        pilot = stratified_candidates(mapping, args.size)
        write_tsv(tables / "pilot_references.tsv", PILOT_FIELDS, pilot)
        result = {"selected": len(pilot), "strata": dict(Counter(r["selection_stratum"] for r in pilot)), "scope": "Exact versioned public nonviral proteomes; unresolved IMG identifiers remain in mapping table"}
        write_json(snapshot / "pilot_selection.json", result)
    elif args.command == "retrieve":
        mapping = list(read_tsv(mapping_path))
        initial_path = tables / "pilot_selection.tsv"
        if not initial_path.exists() and (tables / "pilot_references.tsv").exists():
            # Preserve the initial selection even when failed candidates must be
            # replaced to obtain the requested number of public proteomes.
            shutil.copyfile(tables / "pilot_references.tsv", initial_path)
        existing = list(read_tsv(initial_path)) if initial_path.exists() else []
        candidates = existing + stratified_candidates(mapping, args.attempt_limit)
        attempted, used = [], set()
        successes = downloaded_bytes = 0
        for row in candidates:
            genome = row["genome_id"]
            if genome in used:
                continue
            used.add(genome)
            remaining = args.max_download_mb * 1024 * 1024 - downloaded_bytes
            if remaining <= 0 or len(attempted) >= args.attempt_limit or successes >= args.limit:
                break
            was_cached = (snapshot / "references" / genome / "retrieval.json").exists() and not args.retry_failed
            result_row = retrieve_reference(row, snapshot, max_package_bytes=min(remaining, args.max_package_mb * 1024 * 1024), timeout=args.timeout, retry_failed=args.retry_failed)
            attempted.append(result_row)
            if result_row["status"] == "retrieved":
                successes += 1
                package = snapshot / "references" / genome / "ncbi_dataset.zip"
                downloaded_bytes += package.stat().st_size
            write_tsv(tables / "retrieval_manifest.tsv", RETRIEVAL_FIELDS, attempted)
            logging.info("retrieval accession=%s status=%s successes=%s", genome, result_row["status"], successes)
            if not was_cached:
                time.sleep(0.4)
        quality = export_reference_quality(snapshot, attempted)
        mapping_by_genome = {r["genome_id"]: r for r in mapping}
        selected, failed = [], []
        for index, row in enumerate(attempted, 1):
            mapped = dict(mapping_by_genome[row["genome_id"]])
            mapped.update(selection_rank=index, selection_stratum="|".join([mapped["domain"], mapped["phylum"]]), retrieval_status=row["status"])
            (selected if row["status"] == "retrieved" else failed).append(mapped)
        write_tsv(tables / "pilot_references.tsv", PILOT_FIELDS, selected)
        write_tsv(tables / "failed_pilot_candidates.tsv", PILOT_FIELDS, failed)
        result = {"status": "completed" if successes >= args.limit else "partial_reference_coverage", "retrieved": successes, "attempted": len(attempted), "package_bytes": downloaded_bytes, "requested": args.limit, "reference_quality_status": quality, "failures": dict(Counter(r["error"] for r in attempted if r["status"] != "retrieved"))}
        write_json(snapshot / "retrieval_summary.json", result)
    else:
        result = annotate_retrieved(args, snapshot)
    snapshot_manifest(snapshot, args.command, args, result)
    logging.info("completed %s", json.dumps(result, sort_keys=True))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
