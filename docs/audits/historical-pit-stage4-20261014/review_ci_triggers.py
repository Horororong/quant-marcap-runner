"""Conservative review of this repository's simple push filters, without PyYAML.
Unsupported trigger shapes fail closed; no expression is executed or evaluated.
"""
import argparse,fnmatch,hashlib,json,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[3]
changed=subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=repo,text=True).splitlines()+subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=repo,text=True).splitlines()
def simple_list(s):return [v.strip().strip("'\"")for v in s[1:-1].split(',')]
review=[]
for path in sorted((repo/'.github/workflows').glob('*')):
 if path.suffix not in ['.yml','.yaml']:continue
 text=path.read_text();head=text.split('jobs:',1)[0]
 assert 'workflow_run:'not in head,(path,'Unreviewed chained trigger')
 if '\n  push:'not in head:continue
 block=head.split('\n  push:',1)[1];block=re.split(r'\n  [a-z_]+:',block,maxsplit=1)[0]
 branches=None;m=re.search(r'^    branches:\s*(\[[^\n]*\])',block,re.M)
 if m:branches=simple_list(m.group(1))
 elif re.search(r'^    branches:\s*$',block,re.M):
  branches=re.findall(r'^      -\s*[\x27\x22]?([^\n\x27\x22]+)',block.split('    branches:',1)[1].split('    paths:',1)[0],re.M)
 if branches and not any(fnmatch.fnmatchcase('fix/financial-accuracy-20261014',b.strip())for b in branches):continue
 pm=re.search(r'^    paths:\s*(\[[^\n]*\])',block,re.M)
 if pm:paths=simple_list(pm.group(1))
 else:
  assert '    paths:'in block,(path,'Unfiltered push')
  section=block.split('    paths:',1)[1];section=re.split(r'\n[^ ]|\n    [a-z_]+:',section,maxsplit=1)[0]
  paths=re.findall(r'^      -\s*[\x27\x22]([^\n\x27\x22]+)[\x27\x22]',section,re.M)
 matches=[x for x in changed if any(fnmatch.fnmatchcase(x,pattern)for pattern in paths)]
 if not matches:continue
 if path.name=='financial-accuracy-revalidation.yml':
  assert 'pip install'not in text and 'restore_before.py'in text and 'sandbox_runtime.py'in text
  state='original_offline_kit_only'
 elif path.name in ['test-strategy-dsl.yml','validate-legacy-parser.yml']:
  assert "github.ref_name != 'fix/financial-accuracy-20261014'"in text
  state='branch_guard_skips_internet_pip_jobs'
 else:raise AssertionError(('Unreviewed matching workflow',path.name,matches))
 review.append({'workflow':path.name,'state':state,'matching_paths':matches,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
assert any(x['workflow']=='financial-accuracy-revalidation.yml' for x in review),review
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps({'branch':'fix/financial-accuracy-20261014','changed_paths':sorted(set(changed)),'matching_workflows':review,'workflow_run_chaining':False,'internet_pip_allowed':False,'limitations':'Reviews the existing simple repository push grammar; unsupported/unfiltered shapes stop instead of assuming safety.'},indent=2)+'\n')
print(json.dumps({'reviewed_matches':[(x['workflow'],x['state'])for x in review],'unreviewed_matching_workflows':0}))
