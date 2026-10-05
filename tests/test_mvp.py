import importlib.util
import math
from pathlib import Path
import sys
import unittest
import numpy as np
import torch
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'scripts'))
from ngraph_kg_connectivity import ConnectivityIndex
from ngraph_training_validation import split_pairs

def load(name):
    spec=importlib.util.spec_from_file_location(name,root/'scripts'/name)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class ConnectivityTests(unittest.TestCase):
    def setUp(self):
        nodes=[{'node_id':n} for n in ['site','s1','s2','taxon','other','measure','variable']]
        triples=[('site','site_has_sample','s1'),('site','site_has_sample','s2'),('s1','sample_observed_taxon','taxon'),('s2','sample_observed_taxon','taxon'),('s1','sample_has_measurement','measure'),('measure','measurement_of_variable','variable')]
        self.graph=ConnectivityIndex(nodes,[{'edge_id':str(i),'source_id':a,'edge_type':p,'target_id':b,'source_file':'fixture'} for i,(a,p,b) in enumerate(triples)])
    def test_counts_and_degree_weights(self):
        r=self.graph.search('site','taxon','site_taxon')
        self.assertEqual(r['path_count'],2)
        self.assertAlmostEqual(r['dwpc'],1.0)
        self.assertFalse(r['truncated'])
        self.assertEqual(r['paths'][0]['edges'][0]['source_file'],'fixture')
    def test_reverse_proxy_and_bounds(self):
        r=self.graph.search('taxon','variable','taxon_proxy')
        self.assertEqual(r['path_count'],1)
        self.assertAlmostEqual(r['dwpc'],1/math.sqrt(2))
        r=self.graph.search('site','taxon','site_taxon',max_paths=1)
        self.assertTrue(r['truncated']);self.assertEqual(r['count_status'],'lower_bound')
    def test_missing_and_empty(self):
        self.assertEqual(self.graph.search('missing','taxon','site_taxon')['status'],'missing')
        self.assertEqual(self.graph.search('site','other','site_taxon')['path_count'],0)

class TrainingTests(unittest.TestCase):
    def test_splits_no_positive_negative_or_partition_leakage(self):
        pairs=[(i,j) for i in range(8) for j in range(i+1,8) if (i+j)%2==0]
        a=split_pairs(pairs,8);b=split_pairs(pairs,8)
        positive=set(pairs);allseen=set()
        for k in ['validation','test','train']:
            current={tuple(p) for p in a[k]};self.assertFalse(allseen&current);allseen |= current
            self.assertTrue(np.array_equal(a[k],b[k]))
        self.assertEqual(allseen,positive)
        negseen=set()
        for k in ['validation_negative','test_negative','train_negative']:
            current={tuple(p) for p in a[k]};self.assertFalse(positive&current);self.assertFalse(negseen&current);negseen |= current
    def test_checkpoint_copy_survives_optimizer_update(self):
        import copy
        model=torch.nn.Linear(2,1);saved=copy.deepcopy(model.state_dict());before=saved['weight'].clone()
        opt=torch.optim.SGD(model.parameters(),lr=1)
        model(torch.ones(1,2)).sum().backward();opt.step()
        self.assertTrue(torch.equal(saved['weight'],before));self.assertFalse(torch.equal(model.weight,before))
    def test_scaling_and_diffpool_logits(self):
        import pandas as pd
        m=load('08_ngraph_train_diffpool.py')
        scaled,_=m.numeric_feature_frame(pd.DataFrame({'small':[1,2,3],'large':[1e6,2e6,3e6]}),[])
        self.assertTrue(np.allclose(scaled.small,scaled.large))
        captured=[];original=m.dense_diff_pool
        def capture(x,adj,s,mask):
            captured.append(s.detach());return original(x,adj,s,mask)
        m.dense_diff_pool=capture
        model=m.DiffPoolNet(2,4,3,2)
        x=torch.randn(1,5,2);adj=torch.eye(5)[None];mask=torch.ones(1,5)
        expected=model.assign1(x,adj,mask).detach()
        out=model(x,adj,mask)
        self.assertTrue(torch.allclose(captured[0],expected));self.assertTrue(torch.allclose(out['s1'],expected.softmax(-1)))
if __name__=='__main__':unittest.main()
