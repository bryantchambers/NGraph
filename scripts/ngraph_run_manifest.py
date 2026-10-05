"""Record executable versions, source hashes, runtime settings and input hashes."""
import argparse, hashlib, importlib.metadata, json, os, platform, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
root = Path(__file__).resolve().parents[1]
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--branch',required=True); ap.add_argument('--status',required=True); args=ap.parse_args()
    destination=root/'results/ngraph'/args.branch/'run_manifest.json'; destination.parent.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(destination.read_text()) if destination.exists() else {}
    if args.status=='started' and manifest.get('status')=='completed': raise SystemExit('Completed branch is immutable; use a fresh NG_BRANCH')
    if not manifest:
        manifest={'started_utc':datetime.now(timezone.utc).isoformat(),'python':sys.executable,'python_version':platform.python_version(),'seed':42,
         'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
         'settings':{k:v for k,v in os.environ.items() if k.startswith('NG_') and 'KEY' not in k},
         'packages':{p:importlib.metadata.version(p) for p in ['numpy','pandas','torch','torch-geometric','scikit-learn']},
         'source_sha256':{str(p.relative_to(root)):digest(p) for p in list((root/'scripts').glob('*.py'))+list((root/'scripts').glob('*.R'))+[root/'config_ngraph.R',root/'config_kg_schema.json',root/'config_kg_units.tsv',root/'run_pipeline.sh',root/'run_mvp.sh']},
         'input_sha256':{str(p.relative_to(root)):digest(p) for p in (root/'data').rglob('*') if p.is_file()}}
    manifest.update(status=args.status,updated_utc=datetime.now(timezone.utc).isoformat())
    manifest['source_sha256_at_status']={str(p.relative_to(root)):digest(p) for p in list((root/'scripts').glob('*.py'))+list((root/'scripts').glob('*.R'))+[root/'config_ngraph.R',root/'config_kg_schema.json',root/'config_kg_units.tsv',root/'run_pipeline.sh',root/'run_mvp.sh']}
    manifest['r_version']=subprocess.check_output([os.environ.get('RSCRIPT', '/maps/projects/caeg/people/gfx654/miniforge3/envs/ngraph/bin/Rscript'),'--version'],stderr=subprocess.STDOUT,text=True).strip()
    destination.write_text(json.dumps(manifest,indent=2)+'\n')
if __name__=='__main__':main()
