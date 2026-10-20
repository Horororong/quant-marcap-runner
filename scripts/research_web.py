"""Local-only saved research workspace over existing DSL/check/run/CURRENT.

One bounded child at a time; no shell/codegen/alternate backtester. Preview is
not authorization: the exact normalized DSL digest must be confirmed to queue.
Saved inputs/runs are append-only. Report/metrics are existing CURRENT outputs.
"""
import argparse,copy,csv,hashlib,json,mimetypes,os,re,subprocess,sys,threading,uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,unquote,parse_qs
sys.path.insert(0,str(Path(__file__).resolve().parent))
from research_language import translate,response,confirmation_digest,SUPPORT
from strategy_dsl import StrategySpec
ROOT=Path(__file__).resolve().parents[1]
VERSION='local-research-workspace-v1.1-json-transport'
def browser_numbers(value):
    """Match JSON.stringify's integral-number representation before preview.

    Keep this boundary local to the web transport. The engine's historical
    fingerprints and the CLI's normalized StrategySpec remain unchanged.
    """
    if isinstance(value,dict):return {k:browser_numbers(v)for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [browser_numbers(v)for v in value]
    if type(value)in {int,float}and abs(value)>9007199254740991 and (type(value)is int or value.is_integer()):
        raise ValueError('BROWSER_UNSAFE_INTEGER: 웹 JSON에서 정확히 보존할 수 없는 정수입니다')
    if isinstance(value,float)and value.is_integer():return int(value)
    return value
def browser_preview(result):
    spec=StrategySpec.from_dict(browser_numbers(result['strategy']))
    return response(spec,result.get('defaults_applied',[]),result.get('changed_conditions',[]))
def now():return datetime.now(timezone.utc).isoformat()
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.replace(tmp,path)
def read(path):return json.loads(path.read_text())
def identifier(s):
    if not isinstance(s,str)or not re.fullmatch('[a-f0-9]{32}',s):raise ValueError('잘못된 저장 ID')
    return s
def report_rows(directory):
    path=directory/'run/report/metrics_CURRENT.csv'
    if not path.is_file():return []
    with path.open(newline='',encoding='utf-8-sig')as f:return list(csv.DictReader(f))
def saved_run_provenance(directory):
    """Display the saved execution's inputs, never current editor/repo defaults."""
    run=directory/'run';paths={name:run/name for name in ['strategy_normalized.json','preflight.json','run_status.json']}
    missing=[name for name,p in paths.items()if not p.is_file()]
    if missing:return dict(status='unavailable',missing=missing,scope='Historical run provenance is absent; do not substitute current settings')
    spec=read(paths['strategy_normalized.json']);preflight=read(paths['preflight.json']);state=read(paths['run_status.json'])
    return dict(status='saved_execution_snapshot',strategy_id=spec['strategy_id'],strategy_fingerprint=state.get('strategy_fingerprint'),
        run_id=state.get('run_id'),period=spec['period'],cost_scenarios=spec['cost_scenarios'],benchmark=spec.get('benchmark'),
        data_files=preflight.get('source_files',[]),control_files=preflight.get('control_files',[]),versions=state.get('versions',{}),
        classification='RESEARCH_ONLY',investment_approved=False,scope='Saved source hashes and trading-cost assumptions; no new financial/PIT or cash-dividend total-return certification')
def requirements(root,payload):
    path=root/'config/research/evidence_requirements_v1.json'
    if not path.exists():return []
    pairs=set()
    def visit(v):
        if isinstance(v,dict):
            c=v.get('security')or v.get('asset');d=v.get('date')or v.get('event_date')
            if c and d:pairs.add((str(c),str(d)))
            for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(payload)
    return [e for e in read(path)['events']if(e['security'],e['date'])in pairs]
class Workspace:
    def __init__(self,root,store):
        self.root=Path(root).resolve();self.store=Path(store).resolve();self.store.mkdir(parents=True,exist_ok=True)
        self.pool=ThreadPoolExecutor(max_workers=1);self.lock=threading.Lock()
    def catalog(self):
        paths=['research_size_deciles_2019_2020_v1','research_momentum_top3_2020','research_size_top1_2024','research_size_deciles_2019_2025_event_deferred_v2']
        items=[]
        for name in paths:
            p=self.root/'config/strategies'/str(name+'.json')
            if p.is_file():items.append(dict(id=name,strategy=read(p),definition_path=str(p.relative_to(self.root))))
        return dict(version=VERSION,language=SUPPORT,examples=items,investment_approved=False,
            report_owner='CURRENT v2-18; exact complete requested NAV; no performance calculation in this service',
            running_limit=1,financial_source_only_eligible=False)
    def preview(self,o):
        if 'strategy'in o:
            spec=StrategySpec.from_dict(o['strategy']);return browser_preview(response(spec,[],[]))
        model=None;execution=None
        if o.get('model_example'):
            choices={x['id']:x for x in self.catalog()['examples']}
            if o['model_example']not in choices:raise ValueError('알 수 없는 명시적 연구 계약')
            base=choices[o['model_example']]['strategy'];model=base.get('research')
            execution={k:v for k,v in base.get('execution',{}).items()if k in {'nontradable_policy','data_loading'}}or None
        return browser_preview(translate(o['text'],research=model,execution_contract=execution,base=o.get('base')))
    def save_strategy(self,o):
        s=StrategySpec.from_dict(o['strategy']);name=o.get('name','저장한 전략')
        if not isinstance(name,str)or not name.strip()or len(name)>120:raise ValueError('전략 이름은 1~120자입니다')
        sid=uuid.uuid4().hex
        record=dict(id=sid,name=name,created_at=now(),strategy=s.to_dict(),fingerprint=s.fingerprint(),language_request=o.get('text',''),investment_approved=False)
        write(self.store/'strategies'/str(sid+'.json'),record);return record
    def saved(self,kind):
        if kind not in {'strategies','jobs'}:raise ValueError('알 수 없는 저장 유형')
        return [read(p)for p in sorted((self.store/kind).glob('*.json'),reverse=True)]
    def submit(self,o,mode):
        if mode not in {'check','run'}:raise ValueError('잘못된 실행 모드')
        browser_numbers(o['strategy'])  # reject unsafe integers without rewriting a confirmed snapshot
        s=StrategySpec.from_dict(o['strategy'])
        if o.get('confirmation_digest')!=confirmation_digest(s.to_dict()):raise ValueError('해석 조건이 변경됐거나 명시적 실행 확인이 없습니다. 다시 확인하세요')
        jid=uuid.uuid4().hex;folder=self.store/'runs'/jid;folder.mkdir(parents=True,exist_ok=False)
        write(folder/'strategy.json',s.to_dict())
        job=dict(id=jid,mode=mode,status='queued',created_at=now(),fingerprint=s.fingerprint(),period=s.period.to_dict()if hasattr(s.period,'to_dict')else s.to_dict()['period'],name=s.title,
            source_request=o.get('text',''),confirmed_digest=o['confirmation_digest'],workspace_contract=VERSION,investment_approved=False)
        write(self.store/'jobs'/str(jid+'.json'),job)
        self.pool.submit(self.execute,jid);return job
    def execute(self,jid):
        path=self.store/'jobs'/str(jid+'.json');job=read(path);folder=self.store/'runs'/jid
        job.update(status='running',started_at=now());write(path,job)
        command=[sys.executable,'-I',str(Path(__file__).resolve()),'--worker',jid,'--repo-root',str(self.root),'--store',str(self.store)]
        try:
            with(folder/'worker.log').open('wb')as log:
                child=subprocess.Popen(command,cwd=self.root,stdout=log,stderr=subprocess.STDOUT)
                code=child.wait(timeout=1800)
            result=read(folder/'worker_result.json')
            expected={'ok':0,'capability_gap':2,'data_gap':3,'failed':4}.get(result['status'])
            if expected!=code:raise ValueError('작업 종료 상태와 실제 명령 결과가 일치하지 않습니다')
            job.update(status=result['status'],result=result,exit_code=code,finished_at=now())
        except subprocess.TimeoutExpired:
            child.terminate()
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
            job.update(status='failed',finished_at=now(),error='WEB_JOB_BUDGET_EXHAUSTED; existing engine/postprocess budgets unchanged; source artifacts preserved')
        except Exception as e:job.update(status='failed',finished_at=now(),error=type(e).__name__+':'+str(e))
        write(path,job)
    def status(self,jid):
        jid=identifier(jid);job=read(self.store/'jobs'/str(jid+'.json'));folder=self.store/'runs'/jid
        actual=folder/'run/run_status.json'
        if actual.is_file():job['engine_status']=read(actual)
        if job['status']in {'ok','data_gap','failed','capability_gap'}:
            job['required_evidence']=requirements(self.root,job)
            if job['mode']=='run'and job['status']=='ok':
                state=job.get('engine_status',{})
                if not(state.get('nav_ready')and state.get('report_ready')):raise ValueError('실제 검증된 NAV/보고서 없는 실행은 성공으로 표시할 수 없습니다')
                job['metrics']=report_rows(folder);job['report_url']='/runs/'+jid+'/run/report/report_CURRENT.html'
                job['provenance']=saved_run_provenance(folder)
        return job
    def comparison(self,ids):
        if not 2<=len(ids)<=6 or len(ids)!=len(set(ids)):raise ValueError('서로 다른 성공 실행 2~6개를 선택하세요')
        jobs=[self.status(j)for j in ids]
        if any(j['mode']!='run'or j['status']!='ok'for j in jobs):raise ValueError('성공한 실제 실행만 비교할 수 있습니다')
        return dict(status='ok',runs=jobs,scope='CURRENT metrics and existing interactive reports side by side. Different periods remain explicitly labeled; no recalculation or implied common-period performance.',investment_approved=False)
def worker(root,store,jid):
    path=store/'jobs'/str(identifier(jid)+'.json');job=read(path);folder=store/'runs'/jid
    try:
        if job['mode']=='check':
            from research_workbench import check
            result=check(folder/'strategy.json',root)
        else:
            from strategy_dsl_run import run_checked_strategy
            result=run_checked_strategy(folder/'strategy.json',root,folder/'run',report_periods=root/'config/reports/research_continuous_2025.json',inspect_planned=True)
        result={k:v for k,v in result.items()if k!='artifacts'}
    except (ValueError,KeyError,TypeError)as e:result=dict(status='capability_gap',error=dict(type=type(e).__name__,message=str(e)),investment_approved=False)
    except Exception as e:result=dict(status='failed',error=dict(type=type(e).__name__,message=str(e)),investment_approved=False)
    write(folder/'worker_result.json',result)
    return {'ok':0,'capability_gap':2,'data_gap':3,'failed':4}.get(result['status'],4)
def handler(workspace):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,fmt,*args):pass
        def reply(self,obj,status=200):
            b=json.dumps(obj,ensure_ascii=False,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(b)
        def file(self,p):
            b=p.read_bytes();self.send_response(200);self.send_header('Content-Type',(mimetypes.guess_type(str(p))[0]or'application/octet-stream')+('; charset=utf-8'if p.suffix in {'.html','.js','.css'}else''));self.send_header('Content-Length',str(len(b)));self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(b)
        def do_GET(self):
            try:
                u=urlsplit(self.path);path=unquote(u.path)
                if path=='/api/catalog':return self.reply(workspace.catalog())
                if path=='/api/strategies':return self.reply(workspace.saved('strategies'))
                if path=='/api/jobs':return self.reply(workspace.saved('jobs'))
                if path.startswith('/api/jobs/'):return self.reply(workspace.status(path.rsplit('/',1)[-1]))
                if path=='/api/compare':return self.reply(workspace.comparison(parse_qs(u.query).get('id',[])))
                if path.startswith('/runs/'):
                    relative=Path(path.removeprefix('/runs/'));identifier(relative.parts[0]);base=(workspace.store/'runs').resolve();f=(base/relative).resolve()
                    if not f.is_relative_to(base)or f.suffix not in {'.html','.csv','.json','.txt'}or not f.is_file():raise ValueError('허용되지 않은 산출물 경로')
                    if 'report'in relative.parts or'artifacts'in relative.parts:
                        j=workspace.status(relative.parts[0])
                        if j['status']!='ok':raise ValueError('검증 성공 전 산출물은 보고서로 공개하지 않습니다')
                    return self.file(f)
                assets={'/':'index.html','/app.js':'app.js','/app.css':'app.css'}
                if path in assets:return self.file(workspace.root/'web/research'/assets[path])
                self.reply({'error':'없는 경로'},404)
            except(FileNotFoundError,ValueError,KeyError)as e:self.reply({'error':str(e)},400)
        def do_POST(self):
            try:
                # Local-only binding plus a non-simple request header; no CORS.
                if self.headers.get('X-Research-Request')!='1':raise ValueError('LOCAL_REQUEST_HEADER_REQUIRED')
                origin=self.headers.get('Origin')
                if origin and urlsplit(origin).netloc!=self.headers.get('Host'):raise ValueError('CROSS_ORIGIN_REQUEST_REJECTED')
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=1000000:raise ValueError('요청 크기 제한')
                o=json.loads(self.rfile.read(n));path=urlsplit(self.path).path
                if path=='/api/preview':return self.reply(workspace.preview(o))
                if path=='/api/strategies':return self.reply(workspace.save_strategy(o),201)
                if path in {'/api/check','/api/run'}:return self.reply(workspace.submit(o,path.rsplit('/',1)[-1]),202)
                self.reply({'error':'없는 경로'},404)
            except(ValueError,KeyError,TypeError,FileNotFoundError)as e:self.reply({'status':'rejected','error':str(e)},400)
    return Handler
def main():
    p=argparse.ArgumentParser();p.add_argument('--repo-root',type=Path,default=ROOT);p.add_argument('--store',type=Path,default=ROOT/'results/workspace');p.add_argument('--port',type=int,default=8765);p.add_argument('--worker');a=p.parse_args()
    if a.worker:return worker(a.repo_root.resolve(),a.store.resolve(),a.worker)
    server=ThreadingHTTPServer(('127.0.0.1',a.port),handler(Workspace(a.repo_root,a.store)))
    print(json.dumps(dict(status='ready',url='http://127.0.0.1:'+str(server.server_port),scope='Local RESEARCH_ONLY; no external model connected',version=VERSION)),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
    return 0
if __name__=='__main__':raise SystemExit(main())
