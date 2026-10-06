import json
import argparse
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
root=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--branch',default='mvp_permissive_mixed_20261005');ap.add_argument('--port',type=int,default=10291);args=ap.parse_args()
branch=root/'results/ngraph'/args.branch
report=json.loads((branch/'knowledge_graph/tables/mvp_validation_and_demo.json').read_text())
base=f'http://127.0.0.1:{args.port}'
def get(path,**params):
    with urllib.request.urlopen(base+path+'?'+urllib.parse.urlencode(params),timeout=30) as response:
        return json.load(response)
checks={}
checks['health']=get('/api/health')
checks['catalog']=get('/api/kg/metapaths')
for q in report['questions']:
    a=q['answer'];result=get('/api/kg/connectivity',source=a['source'],target=a['target'],metapath=a['metapath'],limit=3)
    assert result['path_count']>0 and len(result['paths'])<=3
    assert all(path['node_details'] for path in result['paths'])
    checks[q['question']]={k:result[k] for k in ['path_count','dwpc','count_status','evidence_truncated']}
first=get('/api/kg/neighborhood',id='ST8',depth=1,edge_type='site_has_sample,sample_observed_taxon',limit=1000)
second=get('/api/kg/neighborhood',id='ST8',depth=2,edge_type='site_has_sample,sample_observed_taxon',limit=1000)
assert len(second['nodes'])>len(first['nodes'])
checks['neighborhood_depth']=[len(first['nodes']),len(second['nodes'])]
bounded=get('/api/kg/neighborhood',id='ST8',depth=2,limit=15)
assert len(bounded['nodes'])<=15
ids={n['node_id'] for n in bounded['nodes']}
assert all(e['source_id'] in ids and e['target_id'] in ids for e in bounded['edges'])
checks['neighborhood_limit']='passed'
visual=get('/api/kg/neighborhood',id='site:ST8',depth=2,limit=70)
assert {'Sample','Taxon','Module'}.issubset({row['node_type'] for row in visual['nodes']})
checks['visual_neighborhood_types']=sorted({row['node_type'] for row in visual['nodes']})
links=get('/api/links',threshold='prev_10',method='pearson',relation_type='taxon_site',limit=3)
assert len(links['rows'])==3;checks['taxon_site_links']='passed'
emb=get('/api/embedding',limit=3)
assert len(emb['rows'])==3;checks['embedding_limit']='passed'
empty=get('/api/kg/connectivity',source='missing',target='ST8',metapath='site_taxon');assert empty['status']=='missing'
try:get('/api/kg/connectivity',metapath='invalid')
except urllib.error.HTTPError as error:assert error.code==400
else:raise AssertionError('Invalid metapath accepted')
overview=get('/api/overview')
assert overview['branch']==args.branch
assert overview['counts']['cores'] == 4 and overview['counts']['samples'] > 0
assert overview['counts']['physical_sites'] == len(overview['locations'])
assert any(not item['active'] for item in overview['registered_locations'])
checks['overview']='derived from active branch'
modules=get('/api/modules',threshold='prev_10',method='pearson',kind='vgae',limit=1000)
chosen=next(row for row in modules['summary'] if row['module_id']==modules['module_id'])
assert len(modules['members'])==chosen['taxa']
checks['module_member_pagination_source']=len(modules['members'])
catalog=get('/api/data/catalog')['files']
assert catalog and any(f['category']=='Figures' for f in catalog)
checks['data_catalog']=len(catalog)
for route in ['/', '/overview', '/knowledge-graph?view=browser', '/knowledge-graph?view=metapaths', '/query', '/modules', '/data']:
    with urllib.request.urlopen(base+route) as response:
        html=response.read().decode();assert response.status==200 and '<title>Constellations</title>' in html
with urllib.request.urlopen(base+'/kg/paths') as response:
    assert response.url.endswith('/knowledge-graph?view=metapaths')
checks['constellations_ui']='routes, assets and legacy redirect served; headless visual inspection recorded separately'
for asset in ['/assets/constellations/app.js','/assets/constellations/styles.css','/assets/vendor/cytoscape.min.js']:
    with urllib.request.urlopen(base+asset) as response:
        assert response.status==200 and len(response.read())>100
try:get('/api/data/file',id='../AGENTS.md')
except urllib.error.HTTPError as error:assert error.code==404
else:raise AssertionError('Unlisted file exposed')
(branch/'knowledge_graph/tables/mvp_http_validation.json').write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps(checks,indent=2))
