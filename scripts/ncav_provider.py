"""Source-bound reviewed NCAV provider. Coverage data never bypasses PIT admission."""
import json,hashlib
from decimal import Decimal
from pathlib import Path
import pandas as pd

class NcavProvider:
    source='reviewed_ncav'
    def __init__(self,repo_root):
        self.root=Path(repo_root);path=self.root/'config/sandbox/ncav_dataset.json'
        if not path.is_file():raise RuntimeError('NCAV_DATA_GAP: reviewed NCAV dataset is not configured')
        self.data=json.loads(path.read_text())
        if 'dataset_path'in self.data:
            target=Path(self.data['dataset_path'])
            if target.is_absolute()or '..'in target.parts:raise ValueError('NCAV dataset path must stay inside repository')
            source=self.root/target
            if hashlib.sha256(source.read_bytes()).hexdigest()!=self.data['sha256']:raise ValueError('NCAV_DATASET_CHANGED')
            self.data=json.loads(source.read_text())
        if self.data.get('contract')!='reviewed-ncav-v1':raise ValueError('NCAV dataset contract mismatch')
    def _query(self,code,signal):
        rows=[r for r in self.data['observations']if code in r['securities']]
        if not rows:raise RuntimeError('NCAV_DATA_GAP: '+code+' has no admitted issuer/account pair')
        candidates=[]
        for r in rows:
            if r.get('currency')!='KRW' or r.get('fs')not in {'CFS','OFS'}:raise RuntimeError('NCAV_SCOPE_CURRENCY')
            a=r.get('admission')
            if not a:raise RuntimeError('NCAV_PIT_HOLD: '+code+' publication/correction/dated issuer link/period-unit admission missing')
            proofs=a.get('proofs',{})
            for kind in ['accounts','publication','correction_chain','issuer_link','period_unit']:
                proof=proofs.get(kind)
                if not proof:raise RuntimeError('NCAV_PIT_HOLD: '+code+' missing '+kind+' proof')
                p=Path(proof['path']);p=p if p.is_absolute()else self.root/p
                if not p.is_file()or hashlib.sha256(p.read_bytes()).hexdigest()!=proof['sha256']:raise RuntimeError('NCAV_EVIDENCE_CHANGED: '+kind)
                v=json.loads(p.read_text())
                if v.get('status')!='reviewed' or v.get('binding')!=a.get('binding'):raise RuntimeError('NCAV_EVIDENCE_BINDING: '+kind)
                expected={k:r[k]for k in ['corp','rcept_no','fs','bsns_year','reprt_code','thstrm_nm','currency','current_assets','total_liabilities']}
                if v.get('observation')!=expected:raise RuntimeError('NCAV_EVIDENCE_OBSERVATION: '+kind)
                if kind=='issuer_link' and (code not in v.get('securities',[])or not v['valid_from']<=signal<=v['valid_until']):raise RuntimeError('NCAV_ISSUER_INTERVAL: '+code)
                if kind=='publication' and (v.get('available_from')!=a.get('available_from') or v.get('public_at','')>a.get('available_from','')):raise RuntimeError('NCAV_PUBLICATION_TIME')
                if kind=='correction_chain' and (v.get('complete_through','')<signal or r['rcept_no']not in v.get('versions',[])):raise RuntimeError('NCAV_CORRECTION_COVERAGE')
                if kind=='period_unit' and (v.get('unit_multiplier')!='1' or v.get('period_end','')>a.get('available_from','')):raise RuntimeError('NCAV_PERIOD_UNIT')
                if kind=='accounts' and Decimal(v.get('current_assets','NaN'))-Decimal(v.get('total_liabilities','NaN'))!=Decimal(r['ncav']):raise RuntimeError('NCAV_ACCOUNT_VALUES')
            if a['available_from']<=signal and (not a.get('valid_until')or signal<a['valid_until']):candidates.append(r)
        if not candidates:raise RuntimeError('NCAV_NOT_YET_AVAILABLE: '+code)
        chosen=max(candidates,key=lambda r:r['admission']['available_from'])
        if len([r for r in candidates if r['admission']['available_from']==chosen['admission']['available_from']])!=1:raise RuntimeError('NCAV_AMBIGUOUS_VERSION')
        return chosen
    def factor_frame(self,signal,cross_section,fields,securities=None):
        if set(fields)-{'ncav','ncav_to_market_cap'}:raise ValueError('Unsupported NCAV field')
        signal=pd.Timestamp(signal).strftime('%Y-%m-%dT%H:%M:%S');out=[]
        if cross_section.Code.duplicated().any():raise ValueError('Duplicate security in NCAV cross section')
        subjects=cross_section
        if securities is not None:
            if set(securities)-set(cross_section.Code):raise RuntimeError('NCAV_FIXED_COHORT_MISSING')
            subjects=cross_section[cross_section.Code.isin(securities)]
        for row in subjects.to_dict('records'):
            obs=self._query(str(row['Code']),signal);value=Decimal(obs['ncav']);record={'Code':row['Code']}
            if 'ncav'in fields:record['ncav']=float(value)
            if 'ncav_to_market_cap'in fields:
                proof=obs['admission']['proofs']['issuer_link'];proofpath=Path(proof['path']);proofpath=proofpath if proofpath.is_absolute()else self.root/proofpath
                identity=json.loads(proofpath.read_text());codes=identity.get('capitalization_securities',[])
                if identity.get('complete_capitalization_universe')is not True or not codes:raise RuntimeError('NCAV_ISSUER_CAP_SCOPE_UNVERIFIED')
                market=cross_section.set_index('Code')
                if not set(codes).issubset(set(market.index)):raise RuntimeError('NCAV_ISSUER_CAP_CLASS_MISSING')
                caps=[Decimal(str(market.loc[c,'Marcap']))for c in codes]
                if any(not c.is_finite()or c<=0 for c in caps):raise RuntimeError('NCAV_MARKET_CAP_GAP')
                cap=sum(caps,Decimal(0))
                if not cap.is_finite()or cap<=0:raise RuntimeError('NCAV_MARKET_CAP_GAP: '+row['Code'])
                record['ncav_to_market_cap']=float(value/cap)
            out.append(record)
        return pd.DataFrame(out,columns=['Code',*fields])
    def coverage_report(self,signal,fields,securities=None,cross_section=None):
        codes=sorted(set(securities)if securities is not None else{c for r in self.data['observations']for c in r['securities']});issues=[]
        for c in codes:
            try:self._query(c,pd.Timestamp(signal).strftime('%Y-%m-%dT%H:%M:%S'))
            except (RuntimeError,ValueError,KeyError)as e:issues.append({'Code':c,'reason':str(e)})
        if cross_section is not None and not issues:
            try:self.factor_frame(signal,cross_section,fields,securities=codes)
            except (RuntimeError,ValueError,KeyError)as e:issues.append({'Code':'fixed_cohort','reason':str(e)})
        return [dict(source=self.source,signal_date=pd.Timestamp(signal),raw_ok=bool(codes)and not issues,ratio=(len(codes)-len(issues))/len(codes)if codes else 0,issue_count=len(issues),reason='; '.join(x['Code']+':'+x['reason']for x in issues[:12]))]
