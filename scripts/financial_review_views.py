"""Raw review views, not an extractor. Never opens production row amounts."""
import argparse,base64,hashlib,io,json,re,sys,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from financial_review_gate import unpack,grids
from financial_validation_batch import review_selection
def main(root,out,selection=None):
    manifest=json.loads((root/'source_manifest.json').read_text());files={};plans=[]
    for pack in manifest['packs']:
        data=unpack(root/pack['path'],pack['compressed_sha256'])
        # Source files and status counts only. No results/*.json access here.
        files.update({k:v for k,v in data.items()if not k.startswith('results/')})
        if 'batch_plan.json'in data:plans.append(json.loads(data['batch_plan.json']))
    if not plans or any(p!=plans[0]for p in plans):raise ValueError('BATCH_PLAN_MISMATCH')
    plan=plans[0];statuses={Path(k).stem:json.loads(v)for k,v in files.items()if k.startswith('quality/')}
    selected=json.loads(selection.read_text())['receipts']if selection else review_selection(plan,statuses)
    if not set(selected).issubset({s['rcept_no']for s in plan['samples']}):raise ValueError('REVIEW_OUTSIDE_AUTHORIZED100')
    out.mkdir(parents=True,exist_ok=False)
    (out/'selection.json').write_text(json.dumps(dict(receipts=selected,selection_sha256=plan['selection_sha256'],rule=plan['independent_review_rule'],before_production_amounts=True),indent=2)+'\n')
    profiles=[];pattern=re.compile(r'자본총계|자본합계|매출액|영업수익|당기순이익|당기순손실|영업활동.*현금|영업활동으로')
    for receipt in selected:
        data=grids(files,receipt);members=[]
        for member,(g,msha,asha)in data.items():
            tables=[]
            for t in g.tables:
                found=[dict(row=i,cells=row)for i,row in enumerate(t['rows'])if row and pattern.search(row[0])]
                if found:tables.append(dict(table=t['index'],context=t['context'][-1000:],head=t['rows'][:2],rows=found))
            members.append(dict(member=member,member_sha256=msha,archive_sha256=asha,cover=' '.join(g.history[:1600].split()),tables=tables))
        (out/f'{receipt}.json').write_text(json.dumps(dict(receipt=receipt,quality=statuses.get(receipt),members=members),ensure_ascii=False,indent=2)+'\n')
        profiles.append(dict(receipt=receipt,state=statuses.get(receipt,{}).get('extraction_state'),candidate_count=statuses.get(receipt,{}).get('field_count'),members=len(members)))
    (out/'profiles.json').write_text(json.dumps(profiles,ensure_ascii=False,indent=2)+'\n');print(json.dumps(profiles))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--selection',type=Path);a=p.parse_args();main(a.root,a.output,a.selection)
