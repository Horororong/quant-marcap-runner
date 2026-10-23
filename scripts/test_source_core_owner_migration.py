"""The historical owner pins stay immutable; only reviewed migration is accepted."""
import hashlib,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
from check_source_core_increment import check_protected_owners
ROOT=Path(__file__).resolve().parents[1]
class OwnerMigrationTests(unittest.TestCase):
 def setUp(self):
  self.pins=json.loads((ROOT/'docs/research/source-core-batch3-20261023/evidence/UNCHANGED_PROTECTED_OWNERS.json').read_text())['files']
 def test_original_current_exact_mode(self):
  actual={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in self.pins}
  self.assertEqual(check_protected_owners(ROOT,actual),'EXACT_HISTORICAL_OWNERS')
 def test_actual_complete_migration_evidence(self):
  self.assertEqual(check_protected_owners(ROOT,self.pins),'EXPLICIT_SOURCE_REVIEW_MIGRATION_OLD_PINS_PRESERVED')
 def test_unrelated_owner_change_is_rejected(self):
  self.pins['scripts/financial_record_readiness.py']='0'*64
  with self.assertRaises(AssertionError):check_protected_owners(ROOT,self.pins)
 def test_previous_config_must_match_preserved_fixture(self):
  self.pins['config/financial_limited_resume_v1.json']='0'*64
  with self.assertRaises(AssertionError):check_protected_owners(ROOT,self.pins)
 def test_previous_parser_must_match_approved_config(self):
  self.pins['scripts/legacy_native_financials.py']='0'*64
  with self.assertRaises(AssertionError):check_protected_owners(ROOT,self.pins)
 def test_incomplete_migration_fails_closed(self):
  with patch('check_native_source_review_evidence.check',side_effect=AssertionError('MISSING_MIGRATION_PROOF')):
   with self.assertRaises(AssertionError):check_protected_owners(ROOT,self.pins)
 def test_migration_report_must_bind_actual_source_hash(self):
  with patch('check_native_source_review_evidence.check',return_value={'source_module_sha256':'0'*64}):
   with self.assertRaises(AssertionError):check_protected_owners(ROOT,self.pins)
if __name__=='__main__':unittest.main()
