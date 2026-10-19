"""Immutable file-backed KG bundles, selected by an atomically replaced pointer."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import sqlite3
import pandas as pd
from contextlib import closing


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def active_directory(kg_root):
    kg_root = Path(kg_root)
    pointer = kg_root / 'active_snapshot.json'
    if not pointer.exists():
        return kg_root
    selection = json.loads(pointer.read_text())
    identifier = selection['snapshot_id']
    if Path(identifier).name != identifier or identifier in {'.', '..'}:
        raise ValueError('Invalid KG snapshot identifier')
    directory = kg_root / 'snapshots' / identifier
    if not (directory / 'snapshot_manifest.json').is_file():
        raise ValueError('Active KG snapshot is incomplete')
    return directory


def publish(kg_root, nodes, edges, manifest, projection, evidence_directory=None, activate_snapshot=True):
    """Complete and hash all files before replacing the active selection."""
    kg_root = Path(kg_root)
    snapshots = kg_root / 'snapshots'; snapshots.mkdir(parents=True, exist_ok=True)
    source = active_directory(kg_root)
    temp = Path(tempfile.mkdtemp(prefix='.building-', dir=snapshots))
    try:
        shutil.copytree(source / 'tables', temp / 'tables')
        nodes.to_csv(temp / 'tables/kg_nodes.tsv', sep='\t', index=False)
        edges.to_csv(temp / 'tables/kg_edges.tsv', sep='\t', index=False)
        if evidence_directory is not None:
            index_dir = temp / 'indexes'; index_dir.mkdir(exist_ok=True)
            with closing(sqlite3.connect(index_dir / 'support_status.sqlite')) as connection, connection:
                connection.execute('CREATE TABLE support_status(taxon TEXT,function_id TEXT,is_carrier INTEGER,status TEXT,PRIMARY KEY(taxon,function_id))')
                connection.execute('CREATE TABLE inventory(taxon TEXT PRIMARY KEY,background_status TEXT)')
                capabilities = Path(evidence_directory) / 'tables/capabilities.tsv.gz'
                if capabilities.exists():
                    for chunk in pd.read_csv(capabilities, sep='\t', usecols=['taxon','function_id','is_carrier','status'], chunksize=50000):
                        connection.executemany('INSERT INTO support_status VALUES(?,?,?,?)',
                            ((r.taxon, r.function_id, int(str(r.is_carrier).lower() in {'true','1'}), r.status) for r in chunk.itertuples()))
                inventory = Path(evidence_directory) / 'tables/background_inventory.tsv'
                if inventory.exists():
                    frame = pd.read_csv(inventory, sep='\t', usecols=['taxon','background_status'])
                    connection.executemany('INSERT INTO inventory VALUES(?,?)', frame.itertuples(index=False, name=None))
        # Validation reports belong to a specific graph and cannot be inherited.
        (temp / 'tables/kg_substrate_validation.json').unlink(missing_ok=True)
        (temp / 'kg_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (temp / 'tables/kg_functional_projection.json').write_text(json.dumps(projection, indent=2) + '\n')
        if evidence_directory is not None:
            from ngraph_functional_retrieval import build
            build(temp, nodes, projection, evidence_directory)
        files = {p.relative_to(temp).as_posix(): sha256(p) for p in sorted(temp.rglob('*')) if p.is_file()}
        identifier = 'functional-' + hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:24]
        snapshot_manifest = {'schema': 'kg-bundle-1', 'snapshot_id': identifier, 'files': files,
                             'projection': projection['scope'], 'previous_snapshot': source.name if source != kg_root else 'legacy_file_backed',
                             'source_code_sha256': sha256(Path(__file__))}
        # The manifest does not contain volatile timestamps, so repeated publication is idempotent.
        snapshot_manifest.pop('previous_snapshot')
        (temp / 'snapshot_manifest.json').write_text(json.dumps(snapshot_manifest, indent=2) + '\n')
        for filename, digest in projection.get('projection_code_sha256', {}).items():
            if sha256(filename) != digest:
                raise ValueError('Projection source changed during publication')
        destination = snapshots / identifier
        if destination.exists():
            for filename, digest in files.items():
                if sha256(destination / filename) != digest:
                    raise ValueError('Existing KG snapshot failed integrity validation')
            shutil.rmtree(temp)
        else:
            temp.rename(destination)
        if activate_snapshot:
            activate(kg_root, identifier)
        return identifier
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def verify_active(kg_root):
    directory = active_directory(kg_root)
    return verify_directory(directory)

def verify_directory(directory):
    directory = Path(directory)
    manifest = directory / 'snapshot_manifest.json'
    if not manifest.exists():
        return {'status': 'legacy_unbundled'}
    specification = json.loads(manifest.read_text())
    for relative, digest in specification['files'].items():
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory.resolve()) or not path.is_file() or sha256(path) != digest:
            raise ValueError(f'KG snapshot integrity failed: {relative}')
    return {'status': 'passed', 'snapshot_id': directory.name, 'files': len(specification['files'])}

def activate(kg_root, identifier, require_validation=False):
    kg_root=Path(kg_root)
    if Path(identifier).name!=identifier:raise ValueError('Invalid snapshot ID')
    directory=kg_root/'snapshots'/identifier
    verify_directory(directory)
    if (directory/'indexes/functional/manifest.json').exists():
        from ngraph_functional_retrieval import FunctionalRetrieval
        FunctionalRetrieval(directory)
    if require_validation:
        report=kg_root/'validation_history'/f'{identifier}.json'
        specification=json.loads(report.read_text())
        if specification.get('status')!='passed' or specification.get('kg_snapshot_id')!=identifier:raise ValueError('Candidate graph has not passed validation')
        shutil.copy2(report,kg_root/'tables/kg_substrate_validation.json')
    pointer=kg_root/'.active_snapshot.tmp'
    pointer.write_text(json.dumps({'snapshot_id':identifier,'retrieval_in_bundle':(directory/'indexes/functional/manifest.json').exists()},indent=2)+'\n')
    os.replace(pointer,kg_root/'active_snapshot.json')

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--branch',required=True);ap.add_argument('--activate',required=True);args=ap.parse_args()
    activate(Path(__file__).resolve().parents[1]/'results/ngraph'/args.branch/'knowledge_graph',args.activate,require_validation=True)
