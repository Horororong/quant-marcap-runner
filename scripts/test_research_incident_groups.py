import unittest
from research_incident_groups import summarize,summarize_saved
class Groups(unittest.TestCase):
 def issue(self,kind,day,through=None):return dict(kind=kind,date=day,affected_through=through or day,security='000001',portfolio='D01',occurrences=1,required='official fact',diagnostic_only=False)
 def test_duplicates_overlap_and_different_dates_are_not_one_action(self):
  a=self.issue('missing_held_quote','2001-05-01','2001-05-10');b=self.issue('missing_held_quote','2001-05-04','2001-05-12');c=self.issue('held_return_reference_gap','2001-05-04');d=self.issue('held_return_reference_gap','2001-05-07')
  r=summarize({'a':dict(issues=[a,c,d]),'b':dict(issues=[a,b])})
  self.assertEqual((r['records'],r['unique_cross_strategy_symptoms'],r['diagnostic_groups']),(5,4,3));self.assertEqual(r['certified_corporate_event_count'],0);self.assertEqual(r['groups'][0]['affected_strategy_count'],2)
 def test_future_path_never_certified_as_actual_holding(self):
  a=self.issue('held_return_reference_gap','2001-05-04');b=self.issue('held_return_reference_gap','2001-06-04')
  r=summarize({'a':dict(issues=[a,b])});self.assertEqual(r['exposure_records'],{'PLANNED_PREFIX_UNRESOLVED_BOUNDARY':1,'POTENTIAL_AFTER_UNRESOLVED_PATH':1});self.assertTrue(all(not g['executed_holding_certified']for g in r['groups']))
 def test_readiness_and_preflight_copies_are_not_double_counted(self):
  saved=dict(issues=[self.issue('missing_held_quote','2001-05-01')]);r=summarize_saved({'readiness_incidents.json':saved,'preflight.json':saved});self.assertEqual(r['records'],1);self.assertEqual(r['duplicate_input_envelopes_not_counted'],['preflight.json'])
if __name__=='__main__':unittest.main()
