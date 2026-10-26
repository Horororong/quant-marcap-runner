import json,tempfile,unittest,os
from unittest.mock import patch
from pathlib import Path
from scripts.financial_collection_outcome import observe
class Outcome(unittest.TestCase):
 def run_case(self,files,step='success',before=None,after=None):
  with tempfile.TemporaryDirectory()as t:
   p=Path(t)
   for n,v in files.items():(p/n).write_text(json.dumps(v))
   return observe(before or {'states':{'original':{'last_checkpoint':'A','completed_receipts':[]}}},after or {'states':{'original':{'last_checkpoint':'A'}}},p,step)
 def test_gate_success_is_no_collection(self):
  x=self.run_case({'gate.json':{'status':'NO_COLLECTION','reason':'EXPIRED'}});self.assertEqual(x['collection_status'],'NO_COLLECTION');self.assertEqual(x['new_raw_originals'],0);self.assertFalse(x['collection_started'])
 def test_success_without_evidence_never_completed(self):self.assertEqual(self.run_case({})['collection_status'],'NO_COLLECTION_OR_UNCONFIRMED')
 def test_q3_raw_success_is_not_pit(self):
  x=self.run_case({'Q3_STATE.json':{'executions_used':1,'durable_raw_documents':3,'HTTP_attempts':6,'normal_exit':True,'stop_reason':'FIXED_THREE_SOURCE_COMPLETE'}});self.assertEqual(x['new_raw_originals'],3);self.assertEqual(x['new_engine_eligible'],0);self.assertFalse(x['checkpoint_moved'])
 def test_failed_execution_never_raw_success(self):self.assertEqual(self.run_case({'Q3_STATE.json':{'executions_used':1,'durable_raw_documents':1}},'failure')['collection_status'],'COLLECTION_FAILED')
 def test_durable_source_gap_without_archive_is_not_raw(self):
  x=self.run_case({'summary.json':{'collection':[{'rcept_no':'1','source_status':'API014','archives':[]}],'candidate_fields':0}});self.assertEqual(x['new_raw_originals'],0);self.assertEqual(x['collection_status'],'PROCESSED_NO_NEW_RAW')
 def test_checkpoint_difference_and_raw_receipt(self):
  x=self.run_case({'summary.json':{'collection':[{'rcept_no':'1','source_status':'DURABLE','archives':[{}]}],'candidate_fields':9}},after={'states':{'original':{'last_checkpoint':'B'}}});self.assertTrue(x['checkpoint_moved']);self.assertEqual(x['new_raw_originals'],1)
 def test_existing_archive_receipt_not_counted_twice(self):
  x=self.run_case({'summary.json':{'collection':[{'rcept_no':'1','source_status':'DURABLE','archives':[{}]}]}},before={'states':{'original':{'completed_receipts':['1'],'last_checkpoint':'A'}}});self.assertEqual(x['new_raw_originals'],0)
 def test_FY_actual_HTTP_from_matching_durable_attempt(self):
  with patch.dict(os.environ,{'GITHUB_RUN_ID':'new'}):
   x=self.run_case({'summary.json':{'collection':[{'rcept_no':'1','source_status':'DURABLE','archives':[{}]}],'candidate_fields':7}},after={'states':{'original':{'last_checkpoint':'B'},'supplemental':{'attempts':[{'run_id':'old','HTTP_requests_observed':21},{'run_id':'new','HTTP_requests_observed':20}]}}})
  self.assertEqual(x['source_HTTP_observed'],20);self.assertEqual(x['new_raw_originals'],1);self.assertEqual(x['new_candidates_extracted'],7)
if __name__=='__main__':unittest.main()
