import unittest
from pathlib import Path
from verify_factor_code_refactor import prove
ROOT=Path(__file__).resolve().parents[1]
class Refactor(unittest.TestCase):
 def sources(self):return (ROOT/'docs/research/source-readiness-20261019/prior_factor_owner.py.txt').read_text(),(ROOT/'scripts/dart_value_factor_adapter.py').read_text()
 def test_real_before_after_are_exact_statement_move_only(self):
  a,b=self.sources();self.assertEqual(prove(a,b)['status'],'PASS_EXACT_AST_EXTRACTION')
 def test_equation_gate_and_undeclared_import_changes_are_rejected(self):
  a,b=self.sources()
  edits=[b.replace('out["equity"] / out["Marcap"]','out["equity"] * out["Marcap"]'),b.replace('self.coverage_report(signal)','pass'),b+'\nimport fractions\n']
  for altered in edits:
   self.assertNotEqual(b,altered)
   with self.assertRaises(AssertionError):prove(a,altered)
if __name__=='__main__':unittest.main()
