#!/usr/bin/env python3
"""Real HTTP functional evidence acceptance; use --gemini for bounded provider checks."""
import argparse,json,logging,time
from pathlib import Path
from urllib.request import Request,urlopen
from datetime import datetime,timezone


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=10292);ap.add_argument('--output',required=True);ap.add_argument('--gemini',action='store_true');args=ap.parse_args()
 out=Path(args.output);out.mkdir(parents=True,exist_ok=True);logging.basicConfig(filename=out/'http_acceptance.log',level=logging.INFO)
 responses=[]
 def ask(q,context=None,provider='local'):
  start=time.monotonic();request=Request(f'http://127.0.0.1:{args.port}/api/query',data=json.dumps(dict(query=q,context=context or {},llm_provider=provider)).encode(),headers={'Content-Type':'application/json'})
  result=json.load(urlopen(request,timeout=100));responses.append(dict(question=q,seconds=round(time.monotonic()-start,3),response=result));logging.info('query status=%s scope=%s',result.get('resolution_status'),result.get('scope'));return result
 checks=[]
 r=ask('Which functions are associated with module M3?');assert len(r['retrieved_cards'])==2 and not r['entities']['functions'];checks.append('M3 exact associations without definition-name collision')
 r=ask('Which modules support phosphatidylcholine biosynthesis?');assert r['entities']['functions']==['M00091'];checks.append('name resolution')
 carrier=ask('Which taxa support that?',r['context']);assert carrier['graph_evidence']['path_count']==110;checks.append('supporting carrier follow-up')
 profile=ask('Show that along depth in ST8',carrier['context']);assert profile['table_evidence']['total_count']==115 and profile['table_evidence']['profile_scope']=='sample_wide_function';checks.append('profile follow-up')
 other=ask('What about ST13?',profile['context']);assert other['intent']=='profiles' and other['core']=='ST13';checks.append('core follow-up')
 for q in ['Which functions support M99?','Which modules support unicorn metabolism?','Which functions support module:foreign:prev_10:pearson:vgae:M3?']:
  assert ask(q)['resolution_status'] in {'unknown','ambiguous'}
 checks.append('unknown names, IDs and foreign scoped modules')
 overview=ask('Summarize functional enrichment across all modules');assert len(overview['retrieved_cards'])==4;checks.append('all-module overview')
 compare=ask('Compare enrichment in M3 and M4');assert len(compare['retrieved_cards'])==4;checks.append('comparison')
 empty=ask('Which functions support module M6?');assert not any(g.get('paths') for g in empty['graph_results']);assert not any(c.get('observed_status')=='qualified_reference_potential' for c in empty['retrieved_cards']);checks.append('no unrelated positive evidence for empty module')
 central=ask('Which central taxa support M00091 in ST8?');assert central['table_evidence']['total_count']==29;checks.append('qualified central carriers')
 tested=ask('Show all tested results for M6');assert tested['table_evidence']['total_count']==159 and not tested.get('graph_results');checks.append('tested records distinct from assertions')
 components=ask('Which KOs support M00091?');assert components['table_evidence']['total_count']==1 and 'K00570' in components['table_evidence']['rows'][0]['recorded_ko_ids'];checks.append('recorded KO definition')
 alias=ask('Show module M3 profile by age in GeoB25202');assert alias['table_evidence']['total_count']>0 and {r['core'] for r in alias['table_evidence']['rows']}<= {'GeoB25202_R1','GeoB25202_R2'};checks.append('physical core aliases and age units')
 stale=dict(profile['context'],scope=dict(profile['scope'],kg_snapshot_id='other'));assert ask('Which taxa support that?',stale)['llm_status']=='context_reset';checks.append('snapshot context reset')
 member=ask('Which functions support S__3300000322_5 and M00091?');assert member['graph_evidence']['paths'][0]['carrier_status']=='no_complete_support_recorded';checks.append('member-only support limitation')
 if args.gemini:
  for q in ['Which modules support M00091?','Which functions are associated with module M4?']:
   result=ask(q,provider='gemini');assert result['llm_status']=='validated' and result.get('llm_claims')
  checks.append('two grounded live Gemini answers')
 report=dict(status='passed',checked_at=datetime.now(timezone.utc).isoformat(),port=args.port,checks=checks,kg_snapshot_id=profile['scope']['kg_snapshot_id'],seed=42)
 (out/'functional_rag_http.json').write_text(json.dumps(report,indent=2)+'\n');(out/'functional_rag_responses.json').write_text(json.dumps(responses,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
