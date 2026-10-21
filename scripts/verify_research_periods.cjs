// Real browser -> HTTP -> existing Python runner -> CURRENT. Node built-ins only.
const fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert/strict');
const {spawn}=require('child_process');
const url=process.argv[2],output=path.resolve(process.argv[3]);fs.mkdirSync(output,{recursive:true});
const executable=process.env.CHROMIUM_EXECUTABLE||['/usr/bin/google-chrome','/usr/bin/google-chrome-stable','/usr/bin/chromium'].find(fs.existsSync);
if(!executable)throw Error('BROWSER_UNAVAILABLE: UNVERIFIED; no installation');
const profile=fs.mkdtempSync(path.join(os.tmpdir(),'workspace-browser-'));
const child=spawn(executable,['--headless','--no-sandbox','--disable-gpu','--no-startup-window','--disable-dev-shm-usage','--disable-background-networking','--no-first-run','--remote-debugging-pipe','--user-data-dir='+profile],{stdio:['ignore','ignore','pipe','pipe','pipe']});
let sequence=0,buffer='',session,stderr='';const pending=new Map(),errors=[],checks=[];
child.stderr.on('data',d=>stderr+=d);
child.on('exit',(code,signal)=>{for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('Browser exit '+code+'/'+signal));}pending.clear();});
child.stdio[4].on('data',d=>{buffer+=d.toString();let i;while((i=buffer.indexOf('\0'))>=0){const line=buffer.slice(0,i);buffer=buffer.slice(i+1);if(!line)continue;const m=JSON.parse(line);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);}});
function send(method,params={},target=session){return new Promise((resolve,reject)=>{const id=++sequence,timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout '+method));},30000);pending.set(id,{resolve,reject,timer});child.stdio[3].write(JSON.stringify({id,method,params,...(target?{sessionId:target}:{})})+'\0');});}
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
async function until(expression,ms=30000){const start=Date.now();while(Date.now()-start<ms){if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,200));}throw Error('UI timeout: '+expression+' / '+await evaluate("document.getElementById('error').textContent"));}
async function set(id,value,type='input'){await evaluate(`(()=>{const e=document.getElementById(${JSON.stringify(id)});e.value=${JSON.stringify(value)};e.dispatchEvent(new Event(${JSON.stringify(type)}));})()`);}
async function click(id){await until(`!document.getElementById(${JSON.stringify(id)}).disabled`);await evaluate(`document.getElementById(${JSON.stringify(id)}).click()`);}
function checkpoint(o){checks.push(o);fs.writeFileSync(path.join(output,'browser_checks.json'),JSON.stringify({checks,errors},null,2));console.log(JSON.stringify({step:o.step,status:o.status,id:o.id}));}
async function run(mode,expected='ok'){
 const previous=await evaluate('active');await click(mode);
 await until(`active!==null && active!==${JSON.stringify(previous)}`);
 const id=await evaluate('active');
 await until(`active===null && document.getElementById('status').textContent.includes(${JSON.stringify(id.slice(0,8))})`,1800000);
 const job=await evaluate(`api('/api/jobs/'+${JSON.stringify(id)})`);
 assert.equal(job.status,expected,JSON.stringify(job));
 if(expected==='ok'&&mode==='run'){
   assert(job.engine_status.nav_ready&&job.engine_status.report_ready);
   await until(`document.querySelector('#result iframe')?.getAttribute('src')===${JSON.stringify(job.report_url)}`);
   await until("document.querySelector('#result iframe')?.contentWindow?.reportRenderComplete===true");
 }
 checkpoint({step:mode,status:job.status,id,period:job.period,fingerprint:job.fingerprint,report_url:job.report_url});
 return job;
}

async function compareSaveReopen(ids,name){
 await evaluate("document.getElementById('refresh').onclick()");await until('document.querySelectorAll(".compare-choice").length>=2');
 await evaluate("document.querySelectorAll('.compare-choice').forEach(e=>{e.checked="+JSON.stringify(ids)+".includes(e.value);e.dispatchEvent(new Event('change'));})");
 const shownOrder=await evaluate("[...document.querySelectorAll('.compare-choice:checked')].map(e=>e.value)");assert.deepEqual([...shownOrder].sort(),[...ids].sort());
 await click('compare');await until("document.querySelectorAll('#comparison iframe').length===2");await set('comparison-name',name);await click('save-comparison');
 await until("document.getElementById('comparison-status').textContent.includes('비교 저장 완료')");const id=await evaluate("document.getElementById('saved-comparisons').value");
 await evaluate('window.workspaceReady=false');await send('Page.reload');await until('window.workspaceReady===true');await set('saved-comparisons',id,'change');await click('load-comparison');
 await until("document.getElementById('comparison-status').textContent.includes('해시 일치')");await until("document.querySelectorAll('#comparison iframe').length===2&&[...document.querySelectorAll('#comparison iframe')].every(f=>f.contentWindow.reportRenderComplete===true)");
 const reopened=await evaluate("api('/api/comparisons/'+"+JSON.stringify(id)+")");assert.deepEqual(reopened.saved_comparison.run_ids,shownOrder);
 assert.equal(reopened.runs.find(r=>r.id===ids[0]).period.start,'2020-01-01');assert.equal(reopened.runs.find(r=>r.id===ids[1]).period.start,'2019-12-02');
 return {id,periods:reopened.runs.map(r=>r.period),fingerprints:reopened.runs.map(r=>r.fingerprint)};
}
(async()=>{try{
 const target=await send('Target.createTarget',{url:'about:blank'},null);session=(await send('Target.attachToTarget',{targetId:target.targetId,flatten:true},null)).sessionId;
 await send('Page.enable');await send('Runtime.enable');await send('Page.navigate',{url});await until('window.workspaceReady===true');
 if(process.argv[4]){
  const prior=JSON.parse(fs.readFileSync(process.argv[4],'utf8'));
  const comparison=await compareSaveReopen([prior.momentum_source,prior.rerun_id],'모멘텀 기간 변경 전후');assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(output,'verification_resume.json'),JSON.stringify({status:'PASS_RERUN_COMPARISON_SAVE_REOPEN',comparison,engine_executions:0,source_HTTP:0,errors},null,2)+'\n');
  console.log(JSON.stringify({status:'PASS_RERUN_COMPARISON_SAVE_REOPEN',comparison}));return;
 }
 const jobs=await evaluate("api('/api/jobs')"),source=jobs.find(x=>x.period.start==='2024-01-01'),momentum=jobs.find(x=>x.period.start==='2020-01-01');assert(source&&momentum);
 async function open(id){await evaluate("(()=>{const row=[...document.querySelectorAll('#run-list .run-row')].find(x=>x.textContent.includes("+JSON.stringify(id.slice(0,8))+"));row.querySelector('button').click();})()");await until("document.querySelector('#result iframe')?.contentWindow.reportRenderComplete===true");}
 async function range(start,end){await evaluate("(()=>{document.querySelector('#result .analysis-start').value="+JSON.stringify(start)+";document.querySelector('#result .analysis-end').value="+JSON.stringify(end)+";})()");}
 await open(source.id);const metricsBefore=await evaluate("document.querySelector('#result table').textContent");
 await range('2024-06-03','2024-10-31');await evaluate("document.querySelector('#result .view-range').click()");
 await until("document.querySelector('#result .result-card').dataset.displayRange!==undefined");
 assert.equal((await evaluate("api('/api/jobs')")).length,jobs.length);assert.equal(await evaluate("document.querySelector('#result table').textContent"),metricsBefore);
 checkpoint({step:'display_range_only_no_job_no_metric_change',status:'ok'});
 await evaluate("document.querySelector('#result .analyze-range').click()");await until('active!==null');const aid=await evaluate('active');
 await until('active===null',300000);const analysis=await evaluate("api('/api/jobs/'+ "+JSON.stringify(aid)+")");
 assert.equal(analysis.status,'ok',JSON.stringify(analysis));assert.equal(analysis.mode,'analysis');assert.equal(analysis.engine_rerun,false);assert.equal(analysis.source_job_id,source.id);
 await until("document.querySelector('#result iframe')?.contentWindow.reportRenderComplete===true");
 const detail=await evaluate("(()=>{const f=document.querySelector('#result iframe');const d=f.contentDocument;const p=JSON.parse(d.getElementById('report-data').textContent);return {periods:Object.keys(p.periods),selected:f.contentWindow.reportSelectedPeriod,analysis:p.diagnostics['analysis_context.json'],charts:['wealth','log2','drawdown'].map(id=>d.getElementById(id).data.length),period:p.periods.selection};})()");
 assert.deepEqual(detail.periods,['selection','source_full']);assert.equal(detail.selected,'selection');assert.equal(detail.analysis.engine_rerun,false);assert(detail.charts.every(x=>x>0));
 await evaluate("(()=>{const d=document.querySelector('#result iframe').contentDocument;const e=d.getElementById('period');e.value='source_full';e.dispatchEvent(new Event('change'));})()");
 await until("document.querySelector('#result iframe').contentWindow.reportSelectedPeriod==='source_full'");
 checkpoint({step:'existing_nav_canonical_subperiod',status:'ok',id:aid,source:source.id,baseline:detail.period.baseline_date,ending:detail.period.ending_asset_date});
 await evaluate("document.querySelectorAll('.compare-choice').forEach(e=>{e.checked="+JSON.stringify([source.id,aid])+".includes(e.value);e.dispatchEvent(new Event('change'));})");
 await click('compare');await until("document.querySelectorAll('#comparison iframe').length===2");await set('comparison-name','전체 NAV와 하위 분석기간');await click('save-comparison');
 await until("document.getElementById('comparison-status').textContent.includes('비교 저장 완료')");const cid=await evaluate("document.getElementById('saved-comparisons').value");
 await evaluate('window.workspaceReady=false');await send('Page.reload');await until('window.workspaceReady===true');await set('saved-comparisons',cid,'change');await click('load-comparison');await until("document.getElementById('comparison-status').textContent.includes('해시 일치')");
 checkpoint({step:'analysis_and_original_comparison_saved_reopened',status:'ok',id:cid});
 await open(source.id);await range('2028-01-01','2028-12-31');await evaluate("document.querySelector('#result .analyze-range').click()");await until('active!==null');const gapId=await evaluate('active');await until('active===null',300000);
 const gap=await evaluate("api('/api/jobs/'+ "+JSON.stringify(gapId)+")");assert.equal(gap.status,'data_gap');assert.equal(await evaluate("document.querySelectorAll('#result iframe').length"),0);
 checkpoint({step:'missing_period_fail_closed_no_source_full_fallback',status:'ok',id:gapId});
 await open(momentum.id);await range('2019-12-02','2020-12-30');await evaluate("document.querySelector('#result .rerun-range').click()");await until("document.getElementById('status').textContent.includes('새 백테스트 조건')");
 assert.equal(await evaluate("current.strategy.period.start"),'2019-12-02');assert(await evaluate("document.getElementById('run').disabled"));assert.equal(await evaluate("document.getElementById('confirm').checked"),false);
 await click('confirm');const check=await run('check');const rerun=await run('run');
 assert.equal(rerun.operation.kind,'backtest_execution');assert.equal(rerun.operation.starting_holdings,'none');assert.equal(rerun.operation.rerun_from_job_id,momentum.id);assert.notEqual(rerun.fingerprint,momentum.fingerprint);
 const embedded=await evaluate("JSON.parse(document.querySelector('#result iframe').contentDocument.getElementById('report-data').textContent).diagnostics['workspace_operation.json']");
 assert.equal(embedded.kind,'backtest_execution');assert.equal(embedded.rerun_from_job_id,momentum.id);
 checkpoint({step:'new_period_common_engine_rerun_confirmed',status:'ok',id:rerun.id,period:rerun.period,initial:rerun.operation});
 const rerunComparison=await compareSaveReopen([momentum.id,rerun.id],'모멘텀 기간 변경 전후');checkpoint({step:'rerun_compared_saved_reopened',status:'ok',...rerunComparison});
 assert.deepEqual(errors,[]);
 const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(output,'period-workspace.png'),Buffer.from(shot.data,'base64'));
 fs.writeFileSync(path.join(output,'verification.json'),JSON.stringify({status:'PASS_PERIOD_BROWSER',source_run:source.id,momentum_source:momentum.id,analysis_id:aid,analysis_gap_id:gapId,comparison_id:cid,rerun_id:rerun.id,rerun_comparison:rerunComparison,analysis_detail:detail,checks,errors,investment_approved:false},null,2)+'\n');
 console.log(JSON.stringify({status:'PASS_PERIOD_BROWSER',analysis:aid,rerun:rerun.id}));
 }finally{child.kill();for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('browser closed'));}setTimeout(()=>fs.rmSync(profile,{recursive:true,force:true}),300);}
})().catch(e=>{fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({status:'FAIL',error:String(e),stderr},null,2));console.error(e);process.exitCode=1;});
