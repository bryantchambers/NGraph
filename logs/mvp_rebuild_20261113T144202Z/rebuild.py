import os,sys,json,subprocess,hashlib,urllib.request,traceback
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2]
LOG=Path(__file__).resolve().parent
BRANCH=LOG.name
PY='/maps/projects/caeg/people/gfx654/miniforge3/envs/ngraph/bin/python'
RS='/maps/projects/caeg/people/gfx654/miniforge3/envs/ngraph/bin/Rscript'
def now():return datetime.now(timezone.utc).isoformat()
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save():
 temp=LOG/'workflow.tmp';temp.write_text(json.dumps(manifest,indent=2)+'\n');temp.replace(LOG/'workflow.json')
env=dict(os.environ,NG_BRANCH=BRANCH,NG_LOG_SCOPE=BRANCH,NG_ABUNDANCE_MODE='hybrid_aggregated_tad_then_read',NG_PREVALENCE_THRESHOLDS='10',NG_PRIMARY_THRESHOLD='10',NG_PRIMARY_THRESHOLD_LABEL='prev_10',NG_SITE_GRAPH_METHODS='pearson',NG_LOCAL_MIN_POSITIVE_SAMPLES='5',NG_LOCAL_PREVALENCE_FRACTION='0',NG_MODULE_K_MIN='2',NG_MODULE_K_MAX='8',NG_TRAIN_EPOCHS='120',NG_FUNCTIONAL_REFERENCE_SNAPSHOT='functional_20261008',NG_FUNCTIONAL_SNAPSHOT='catalog_unweighted_'+BRANCH,NG_FUNCTIONAL_BOOTSTRAPS='200',NG_LLM_PROVIDER='local',PYTHON=PY,RSCRIPT=RS,OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',PYTHONUNBUFFERED='1')
manifest=dict(schema='mvp-rebuild-1',branch=BRANCH,status='running',started_utc=now(),seed=42,settings={k:v for k,v in env.items() if k.startswith('NG_') and 'KEY' not in k},git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),stages=[],source_sha256={str(p.relative_to(ROOT)):digest(p) for p in [ROOT/'run_mvp.sh',ROOT/'run_pipeline.sh',ROOT/'run_functional.sh',Path(__file__)]},reference_manifest_sha256=digest(ROOT/'data/reference/functional/functional_20261008/snapshot_manifest.json'))
try:
 if (ROOT/'results/ngraph'/BRANCH).exists():raise RuntimeError('Fresh run directory already exists')
 with urllib.request.urlopen('http://127.0.0.1:10291/api/health',timeout=10) as response:manifest['served_baseline']=json.load(response)
 save()
 phases=[('discovery_and_proxy_KG',['bash','run_mvp.sh']),('functional_enrichment_and_joint_evidence',['bash','run_functional.sh']),('final_KG_integrity',[PY,'scripts/ngraph_validate_kg_substrate.py','--branch',BRANCH]),('final_MVP_and_demonstrations',[PY,'scripts/ngraph_validate_mvp.py','--branch',BRANCH]),('final_run_manifest',[PY,'scripts/ngraph_run_manifest.py','--branch',BRANCH,'--status','completed'])]
 for name,command in phases:
  stage=dict(name=name,command=command,started_utc=now(),status='running');manifest['stages'].append(stage);save();print(now(),name,'START',flush=True)
  with (LOG/(name+'.log')).open('ab') as stream:
   result=subprocess.run(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=stream)
  stage.update(returncode=result.returncode,finished_utc=now(),status='completed' if result.returncode==0 else 'failed');save()
  if result.returncode:raise RuntimeError(name+' failed: '+str(result.returncode))
  print(now(),name,'COMPLETE',flush=True)
 manifest.update(status='completed_pending_comparison',finished_utc=now());save()
except Exception as exc:
 manifest.update(status='failed',finished_utc=now(),error=str(exc));save();traceback.print_exc();sys.exit(1)
