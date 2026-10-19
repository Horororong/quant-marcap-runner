import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from financial_source_readiness_audit import publication_hashes
class AuditDeterminism(unittest.TestCase):
 def test_filesystem_creation_order_never_changes_manifest_bytes(self):
  with tempfile.TemporaryDirectory()as a,tempfile.TemporaryDirectory()as b:
   for root,names in [(a,['c','a','b']),(b,['b','a','c'])]:
    d=Path(root)/'data/financials/legacy_2000_2014/quality_v9/metrics';d.mkdir(parents=True)
    for name in names:(d/(name+'.json')).write_text(name)
   self.assertEqual(json.dumps(publication_hashes(Path(a))),json.dumps(publication_hashes(Path(b))))
if __name__=='__main__':unittest.main()
