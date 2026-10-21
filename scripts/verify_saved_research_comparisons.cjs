// Real browser -> local HTTP -> preserved CURRENT results. No engine rerun.
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

(async()=>{try{
 const target=await send('Target.createTarget',{url:'about:blank'},null);
 session=(await send('Target.attachToTarget',{targetId:target.targetId,flatten:true},null)).sessionId;
 await send('Page.enable');await send('Runtime.enable');await send('Page.navigate',{url});await until('window.workspaceReady===true');
 await evaluate("document.querySelectorAll('.compare-choice').forEach(e=>{if(!e.disabled){e.checked=true;e.dispatchEvent(new Event('change'));}})");
 await click('compare');await until("document.querySelectorAll('#comparison iframe').length===2");
 await until("[...document.querySelectorAll('#comparison iframe')].every(f=>f.contentWindow.reportRenderComplete===true)");
 const runs=await evaluate("comparisonIds");
 await set('comparison-name','비용 변경 전후 · 보존된 실제 2024 실행');await click('save-comparison');
 await until("document.getElementById('comparison-status').textContent.includes('비교 저장 완료')");
 const cid=await evaluate("document.getElementById('saved-comparisons').value");
 const record=await evaluate("api('/api/comparisons/'+document.getElementById('saved-comparisons').value)");
 assert.deepEqual(record.saved_comparison.run_ids,runs);assert.equal(record.saved_comparison.runs.length,2);
 assert(record.saved_comparison.runs.every(r=>r.files.length===(r.provenance.workspace_operation?8:7)&&r.files.every(f=>/^[0-9a-f]{64}$/.test(f.sha256))));
 const costs=record.runs.map(r=>r.provenance.cost_scenarios.fixed_cost.commission_bps).sort();
 assert.deepEqual(costs,[1.5,2.5]);
 checkpoint({step:'save_real_current_comparison',status:'ok',id:cid,runs,costs});
 await evaluate('window.workspaceReady=false');await send('Page.reload');await until('window.workspaceReady===true');
 assert.equal(await evaluate("document.querySelectorAll('#comparison iframe').length"),0);
 await set('saved-comparisons',cid,'change');await click('load-comparison');
 await until("document.getElementById('comparison-status').textContent.includes('해시 일치')");
 await until("[...document.querySelectorAll('#comparison iframe')].length===2&&[...document.querySelectorAll('#comparison iframe')].every(f=>f.contentWindow.reportRenderComplete===true)");
 const proof=await evaluate(`[...document.querySelectorAll('#comparison iframe')].map(f=>{
 const d=f.contentDocument,w=f.contentWindow,p=JSON.parse(d.getElementById('report-data').textContent);
 return {period_options:[...d.getElementById('period').options].map(o=>o.value),
 costs:[...d.getElementById('cost').options].map(o=>o.value),
 charts:['wealth','log2','drawdown'].map(id=>({id,traces:d.getElementById(id).data.length})),
 log_axis:d.getElementById('log2').layout.yaxis.type,
 metrics:document.querySelector('#comparison table').textContent.includes('Sharpe'),
 period:w.reportSelectedPeriod,report_version:p.performance_version||p.version};
})`);
 assert(proof.every(p=>p.period_options.length>=1&&p.charts.every(c=>c.traces>0)&&p.log_axis==='log'&&p.metrics));
 assert(proof.every(p=>p.costs.includes('net:fixed_cost')));
 await evaluate("(()=>{const d=document.querySelector('#comparison iframe').contentDocument;const s=d.getElementById('cost');s.value='net:fixed_cost';s.dispatchEvent(new Event('change'));})()");
 await until("document.querySelector('#comparison iframe').contentWindow.reportRenderComplete===true&&document.querySelector('#comparison iframe').contentDocument.getElementById('cost').value==='net:fixed_cost'");
 const reopened=await evaluate("api('/api/comparisons/'+document.getElementById('saved-comparisons').value)");
 assert.deepEqual(reopened.saved_comparison,record.saved_comparison);assert.deepEqual(errors,[]);
 checkpoint({step:'reload_reopen_current_three_charts_and_cost_control',status:'ok',id:cid,proof});
 const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
 fs.writeFileSync(path.join(output,'saved-comparison.png'),Buffer.from(shot.data,'base64'));
 fs.writeFileSync(path.join(output,'verification.json'),JSON.stringify({status:'PASS_REAL_SAVED_COMPARISON_BROWSER',saved_comparison_id:cid,run_ids:runs,record:record.saved_comparison,checks,errors,engine_rerun:false,source:'Copied previously validated real CURRENT runs; original files untouched',investment_approved:false},null,2)+'\n');
 console.log(JSON.stringify({status:'PASS_REAL_SAVED_COMPARISON_BROWSER',saved_comparison_id:cid}));
 }finally{child.kill();for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('browser closed'));}setTimeout(()=>fs.rmSync(profile,{recursive:true,force:true}),300);}
})().catch(e=>{fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({status:'FAIL',error:String(e),stderr},null,2));console.error(e);process.exitCode=1;});

