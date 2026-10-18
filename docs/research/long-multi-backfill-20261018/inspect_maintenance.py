"""Read-only service-failure census, not a migration or reprocessing request."""
import argparse,json,re,sys
from pathlib import Path
import pandas as pd
HOME=Path(__file__).resolve().parent;sys.path.insert(0,str(HOME));from evidence_transport import emit
p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
x=pd.read_csv(a.evidence/'effective-state.csv',dtype=str,keep_default_na=False);errors=x[x.status.eq('ERROR')].copy();errors['maintenance800']=errors.error.str.contains(r'<status>\s*800\s*</status>',regex=True)
errors.to_csv(a.output/'error_census.csv',index=False)
result=dict(scope='Existing current effective state; no live API or attempt reset',total_error_receipts=len(errors),maintenance800=int(errors.maintenance800.sum()),other_errors=int((~errors.maintenance800).sum()),state_versions=errors.parser_version.value_counts().to_dict(),error_attempt_columns=[n for n in errors if 'attempt' in n],deployment_applied=False)
(a.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n');emit(a.output,'MAINTENANCE_CENSUS')
