"""Minimal reproduction of starting1000 modern tasks after legacy deadline."""
import unittest
from fast_backfill_phase_policy import modern_phase_decision
class Phase(unittest.TestCase):
 def test_previous_timeout_configuration_cannot_start_fresh_phase(self):
  # Observed failed regular jobs:1000 modern tasks configured after bounded
  # legacy phase. Old guard admitted every non-rate/non-fatal deadline stop.
  legacy=dict(legacy_rate_limited=False,legacy_stop_reason='DEADLINE')
  old_guard=1000>0 and not legacy['legacy_rate_limited'] and legacy['legacy_stop_reason']!='FATAL_API'
  self.assertTrue(old_guard);self.assertEqual(modern_phase_decision(1000,legacy),(False,'LEGACY_STOP_DEADLINE'))
 def test_other_stop_conditions_and_unknown_are_closed(self):
  for reason in ['SIGNAL','REQUEST_BUDGET','FATAL_API','ERROR',None]:self.assertFalse(modern_phase_decision(1000,dict(legacy_stop_reason=reason))[0])
  self.assertFalse(modern_phase_decision(1000,dict(legacy_stop_reason='BATCH_COMPLETE',legacy_rate_limited=True))[0])
 def test_natural_completion_still_allows_existing_modern_queue(self):
  self.assertEqual(modern_phase_decision(1000,dict(legacy_stop_reason='BATCH_COMPLETE',legacy_rate_limited=False)),(True,'LEGACY_BATCH_COMPLETE'))
  self.assertEqual(modern_phase_decision(0,dict(legacy_stop_reason='BATCH_COMPLETE')),(False,'DISABLED_BY_BATCH_LIMIT'))
if __name__=='__main__':unittest.main(verbosity=2)
