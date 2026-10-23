"""The historical owner pins stay immutable; only reviewed migration is accepted."""
import hashlib,json,sys,unittest,shutil,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
from check_source_core_increment import check_protected_owners, REVIEWED_94_FILES, HISTORICAL_OWNER_FILE
ROOT=Path(__file__).resolve().parents[1]
class OwnerMigrationTests(unittest.TestCase):
 def setUp(self):
  self.pins=json.loads((ROOT/'docs/research/source-core-batch3-20261023/evidence/UNCHANGED_PROTECTED_OWNERS.json').read_text())['files']
 def test_current_hashes_cannot_replace_historical_pins(self):
  actual={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in self.pins}
  with self.assertRaises(AssertionError):check_protected_owners(ROOT,actual)
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
 def thin_root(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
  for name in set(REVIEWED_94_FILES)|set(self.pins):
   f=root/name;f.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,f)
  return root
 def change_json(self,root,name,change):
  p=root/name;d=json.loads(p.read_text());change(d);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 def test_unapproved_parser_plus_rewritten_hash_links_rejected(self):
  root=self.thin_root();parser='scripts/legacy_native_financials.py';p=root/parser;p.write_bytes(p.read_bytes()+b'\n# unapproved edit\n');h=hashlib.sha256(p.read_bytes()).hexdigest()
  self.change_json(root,'config/financial_limited_resume_v1.json',lambda d:d['source_code_sha256'].__setitem__(parser,h))
  self.change_json(root,'docs/research/sbm-reference-pit-20261023/evidence/MIGRATION.json',lambda d:d.__setitem__('after_source_sha256',h))
  with self.assertRaises(AssertionError):check_protected_owners(root,self.pins)
 def test_financial_value_and_matching_mutable_proof_hash_rejected(self):
  root=self.thin_root();name='docs/research/sbm-reference-pit-20261023/evidence/SBM_SOURCE_REVIEW.json'
  self.change_json(root,name,lambda d:d['rows'][0].__setitem__('independent_amount_krw','1'))
  h=hashlib.sha256((root/name).read_bytes()).hexdigest()
  self.change_json(root,'docs/research/sbm-reference-pit-20261023/evidence/MIGRATION.json',lambda d:d.__setitem__('source_review_sha256',h))
  with self.assertRaises(AssertionError):check_protected_owners(root,self.pins)
 def test_wrong_before_hash_rejected(self):
  root=self.thin_root();self.change_json(root,'docs/research/sbm-reference-pit-20261023/evidence/MIGRATION.json',lambda d:d.__setitem__('before_source_sha256','0'*64))
  with self.assertRaises(AssertionError):check_protected_owners(root,self.pins)
 def test_wrong_after_hash_rejected(self):
  root=self.thin_root();self.change_json(root,'docs/research/sbm-reference-pit-20261023/evidence/MIGRATION.json',lambda d:d.__setitem__('after_source_sha256','0'*64))
  with self.assertRaises(AssertionError):check_protected_owners(root,self.pins)
 def test_missing_migration_rejected(self):
  root=self.thin_root();(root/'docs/research/sbm-reference-pit-20261023/evidence/MIGRATION.json').unlink()
  with self.assertRaises(AssertionError):check_protected_owners(root,self.pins)
 def test_contradictory_migration_version_rejected(self):
  root=self.thin_root();self.change_json(root,'docs/research/sbm-reference-pit-20261023/evidence/MIGRATION.json',lambda d:d.__setitem__('before_version',d['after_version']))
  with self.assertRaises(AssertionError):check_protected_owners(root,self.pins)
 def test_source_transfer_manifest_tamper_rejected(self):
  root=self.thin_root();name='data/financials/legacy_2000_2014/quality_v9/limited_resume_v1/runs/39248507369/manifest.json'
  self.change_json(root,name,lambda d:d['transfers'][0].__setitem__('compressed_sha256','0'*64))
  with self.assertRaises(AssertionError):check_protected_owners(root,self.pins)
 def test_changed_historical_owner_manifest_rejected(self):
  root=self.thin_root();self.change_json(root,HISTORICAL_OWNER_FILE,lambda d:d['files'].__setitem__('scripts/legacy_native_financials.py','0'*64))
  altered=json.loads((root/HISTORICAL_OWNER_FILE).read_text())['files']
  with self.assertRaises(AssertionError):check_protected_owners(root,altered)
if __name__=='__main__':unittest.main()
