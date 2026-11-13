"""Exercise shell orchestration across R numeric and Python path-label thresholds."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

class FunctionalRunnerTests(unittest.TestCase):
    def invoke(self,threshold,label=None):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            shutil.copy2(Path(__file__).resolve().parents[1]/'run_functional.sh',root/'run_functional.sh')
            fake=root/'runtime'
            fake.write_text('#!'+sys.executable+'\n'+'''import os,sys,json
with open(os.environ['TRACE'],'a') as out:out.write(json.dumps({'args':sys.argv[1:],'threshold':os.environ.get('NG_PRIMARY_THRESHOLD')})+'\\n')
if sys.argv[1]=='-c':print('fixture')
elif sys.argv[1].endswith('ngraph_functional_kg.py'):print(json.dumps({'kg_snapshot_id':'fixture'}))
''')
            fake.chmod(0o700)
            env={k:v for k,v in os.environ.items() if not k.startswith('NG_')}
            env.update(PYTHON=str(fake),RSCRIPT=str(fake),TRACE=str(root/'trace.jsonl'),NG_BRANCH='fixture',NG_FUNCTIONAL_REFERENCE_SNAPSHOT='reference',NG_FUNCTIONAL_SNAPSHOT='analysis',NG_PRIMARY_THRESHOLD=threshold)
            if label:env['NG_PRIMARY_THRESHOLD_LABEL']=label
            result=subprocess.run(['bash',str(root/'run_functional.sh')],env=env,capture_output=True,text=True,timeout=10)
            calls=[json.loads(row) for row in (root/'trace.jsonl').read_text().splitlines()] if (root/'trace.jsonl').exists() else []
            return result,calls
    def check(self,threshold,label=None):
        result,calls=self.invoke(threshold,label)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(calls[0]['threshold'],'10')
        for call in calls:
            if '--threshold' in call['args']:
                self.assertEqual(call['args'][call['args'].index('--threshold')+1],'prev_10')
        self.assertTrue(any('--activate' in call['args'] for call in calls))
    def test_numeric_setting(self):self.check('10')
    def test_label_setting(self):self.check('prev_10')
    def test_explicit_label_precedence(self):self.check('5','prev_10')
    def test_invalid_setting_stops_before_analysis(self):
        result,calls=self.invoke('invalid')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(calls,[])
        self.assertIn('Invalid functional prevalence threshold',result.stderr)
