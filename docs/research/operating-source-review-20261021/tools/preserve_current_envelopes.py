"""Freeze current12 output envelopes for future comparison, not a historical match."""
import hashlib,json,shutil
from pathlib import Path
P=Path(__file__).parent;source=Path('/workspace/quant-integration-20261021/frozen-final');out=P/'future-baseline-305';out.mkdir(exist_ok=False);rows=[]
for run in ['original','momentum2020','size2024']:
 for name in ['postprocess.log','run_status.json','report/chat_manifest_CURRENT.json','report/report_CURRENT.html']:
  rel=run+'/'+name;raw=(source/rel).read_bytes();dest=out/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);rows.append(dict(path=rel,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),past_original_comparison='UNVERIFIED',future_baseline='EXACT_PRESERVED_CURRENT_BYTES'))
proof=json.loads((source/'frozen-regression.json').read_text());assert proof['exact_files']==130
record=dict(baseline_version='current-integration-305-envelopes-v1',code_commit='305cb673f4768907945bc2752753810c4975c37c',fixed_kit_id='26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd',local_run_source=str(source),execution_provenance='Local exact-input executions from the working tree subsequently committed as305cb; production strategy/engine/input files identical. Final exact-target remote CI39540516627 independently passes130 strict bytes, not an assertion these12 are remote artifact bytes.',CI='https://github.com/Horororong/quant-marcap-runner/actions/runs/39540516627',files=rows,strict_old_regression=dict(exact=130,explicit_contract_changes=9,past_envelopes_unverified=12),old_baseline_modified=False,past_original_bytes_newly_obtained=False,past_detail_comparison='UNVERIFIED_ALL12',new_full_CI_or_strategy_run=False,classification='RESEARCH_ONLY')
(P/'future-baseline-305-manifest.json').write_text(json.dumps(record,indent=2)+'\n');print('Preserved12current envelopes',sum(x['bytes']for x in rows),'bytes. Past12stillUNVERIFIED.')
