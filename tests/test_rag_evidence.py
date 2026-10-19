"""Regression: semantic card identifiers must reach the actual synthesis prompt."""
import sys
import unittest
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from ngraph_rag_orchestrator import build_retrieval_bundle

class EvidenceRetrievalTests(unittest.TestCase):
    def test_semantic_card_id_is_not_an_entity_id(self):
        cards=pd.DataFrame([
            {'card_id':'card-1','entity_id':'core-A','card_type':'site','title':'Core A','summary':'Measured site context'},
            {'card_id':'card-2','entity_id':'core-B','card_type':'site','title':'Core B','summary':'Different context'}])
        result={'semantic_hits':pd.DataFrame([{'card_id':'card-1'}])}
        bundle=build_retrieval_bundle('Core A evidence',result,{'cards':cards})
        self.assertEqual(bundle['retrieved_cards'].iloc[0]['card_id'],'card-1')
        self.assertIn('[card-1]',bundle['prompt'])
        self.assertNotIn('[card-2]',bundle['prompt'])

if __name__=='__main__':unittest.main()
