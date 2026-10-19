"""Reuse original preservation owner with ONE explicitly proved code evolution.

Original849-file manifest and financial/NAV/source expectations remain immutable.
The derived manifest exists only in a temporary directory; changed arithmetic,
provider gates or any undeclared module change is rejected before validation.
"""
import argparse,copy,hashlib,importlib.util,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'scripts'))
from verify_factor_code_refactor import prove
def sha(b):return hashlib.sha256(b).hexdigest()
def main(out,originals,approval):
    a=json.loads(approval.read_text());name=a['path'];assert name=='scripts/dart_value_factor_adapter.py'
    old_home=ROOT/'docs/research/stage16-continuous-research-20261018';manifest_bytes=(old_home/'preservation_manifest.json').read_bytes();manifest=json.loads(manifest_bytes)
    assert sha(manifest_bytes)==a['original_manifest_sha256']
    before=(approval.parent/a['before_source']).read_bytes();after=(ROOT/name).read_bytes()
    assert manifest['files'][name]==a['before']
    assert dict(bytes=len(before),sha256=sha(before))==a['before']
    assert dict(bytes=len(after),sha256=sha(after))==a['after']
    proof=prove(before.decode(),after.decode())
    prefix=manifest['prior_registry_prefix'];assert sha((ROOT/'config/kr_corporate_actions.csv').read_bytes()[:prefix['bytes']])==prefix['sha256']
    derived=copy.deepcopy(manifest);derived['files'][name]=a['after']
    assert {k:v for k,v in derived['files'].items()if k!=name}=={k:v for k,v in manifest['files'].items()if k!=name}
    with tempfile.TemporaryDirectory(prefix='explicit-code-preservation-')as tmp:
        home=Path(tmp);raw=(json.dumps(derived,sort_keys=True,indent=2)+'\n').encode();(home/'preservation_manifest.json').write_bytes(raw)
        spec=importlib.util.spec_from_file_location('unchanged_preservation_owner',ROOT/'docs/research/stage15-research-environment-20261017/preserve.py');owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
        assert owner.ROOT==ROOT;owner.HOME=home
        argv=sys.argv;sys.argv=['unchanged_preservation_owner','--output',str(out),'--originals',str(originals)]
        try:code=owner.main()
        finally:sys.argv=argv
    record=dict(original_manifest_sha256=sha(manifest_bytes),original_manifest_modified=False,derived_manifest_sha256=sha(raw),changed_code_path=name,before=a['before'],after=a['after'],proof=proof,unchanged_original_file_pins=len(manifest['files'])-1,explicit_new_code_pin_count=1,owner_exit_code=code,investment_approved=False)
    (out/'code_contract_evolution.json').write_text(json.dumps(record,indent=2)+'\n');return code
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--originals',type=Path,required=True);p.add_argument('--approval',type=Path,required=True);a=p.parse_args();raise SystemExit(main(a.output,a.originals,a.approval))
