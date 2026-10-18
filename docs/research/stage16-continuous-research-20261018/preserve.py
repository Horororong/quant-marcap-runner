"""Reuse prior financial/original preservation owner with additive frozen pins."""
import hashlib,importlib.util,json
from pathlib import Path
HOME=Path(__file__).resolve().parent;ROOT=HOME.parents[2]
if __name__=='__main__':
 pins=json.loads((HOME/'preservation_manifest.json').read_text());p=pins['prior_registry_prefix'];raw=(ROOT/'config/kr_corporate_actions.csv').read_bytes()[:p['bytes']]
 assert hashlib.sha256(raw).hexdigest()==p['sha256'],'old registry rows altered instead of additive evidence'
 s=importlib.util.spec_from_file_location('preservation_owner',HOME.parent/'stage15-research-environment-20261017/preserve.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.HOME=HOME;raise SystemExit(m.main())
