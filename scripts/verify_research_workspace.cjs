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
(async()=>{try{
 const browserVersion=await send('Browser.getVersion',{},null);
 checkpoint({step:'browser_protocol_ready',status:'ok',executable,browser:browserVersion});
 const target=await send('Target.createTarget',{url:'about:blank'},null);session=(await send('Target.attachToTarget',{targetId:target.targetId,flatten:true},null)).sessionId;
 await send('Page.enable');await send('Runtime.enable');await send('Page.navigate',{url});await until('window.workspaceReady===true');
 const runs=[];
 for(const name of ['research_size_top1_2024','research_momentum_top3_2020','research_size_deciles_2019_2020_v1']){
  await set('example',name,'change');await click('interpret');await until("!document.getElementById('confirm').disabled");
  await set('name',name+' browser');await click('save');await until("document.getElementById('status').textContent.includes('snapshot')");
  await click('confirm');await run('check');const job=await run('run');runs.push({name,id:job.id});
  checkpoint({step:'example_complete',name,id:job.id,status:'ok'});
 }
 // Saved DSL reload must retain the exact interpretation and require a fresh check.
 const saved=await evaluate("api('/api/strategies')");const first=saved.find(x=>x.name==='research_size_top1_2024 browser');assert(first);
 await set('saved',first.id,'change');await click('load');await until("document.getElementById('status').textContent.includes('저장 전략을 불러왔습니다')");
 assert.equal(await evaluate('current.strategy_fingerprint'),first.fingerprint);
 assert(await evaluate("document.getElementById('run').disabled"));
 // Same confirmed normalized DSL through the JSON editor, not an alternate engine.
 await evaluate("document.querySelector('#json-input').closest('details').open=true");
 await click('preview-json');await until("document.getElementById('status').textContent.includes('조건·가정을 확인한 뒤')");await click('confirm');await run('check');const jsonRun=await run('run');
 runs.push({name:'json_same_top1',id:jsonRun.id});
 // Amend only the cost; the exact common engine will expose Gross/Net effects.
 await click('amend');await set('request','수수료를 2.5bp로 변경');await click('interpret');
 await until("!document.getElementById('confirm').disabled");assert.equal(await evaluate('current.strategy.cost_scenarios.fixed_cost.commission_bps'),2.5);
 await click('confirm');await run('check');const amended=await run('run');runs.push({name:'amended_top1',id:amended.id});
 await evaluate(`(()=>{const ids=${JSON.stringify([jsonRun.id,amended.id])};document.querySelectorAll('.compare-choice').forEach(e=>{if(ids.includes(e.value)){e.checked=true;e.dispatchEvent(new Event('change'));}});})()`);
 await click('compare');await until("document.querySelectorAll('#comparison iframe').length===2");checkpoint({step:'saved_reload_json_amend_compare',status:'ok'});
 // Unsupported language stays rejected; it never becomes a similar strategy.
 await set('request','손절 5%와 레버리지 2배 전략');await click('interpret');await until("!document.getElementById('error').hidden");assert(await evaluate("document.getElementById('run').disabled"));checkpoint({step:'unsupported_rejected',status:'ok'});
 await set('example','research_size_deciles_2019_2025_event_deferred_v2','change');await click('interpret');await until("!document.getElementById('confirm').disabled");await click('confirm');
 assert.equal(await evaluate("document.querySelectorAll('#result iframe').length"),0,'New/blocked input must not retain the preceding success report');
 const blocked=await run('check','data_gap');assert(JSON.stringify(blocked).includes('207940'));await run('run','data_gap');
 assert.deepEqual(errors,[]);
 const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(output,'workspace.png'),Buffer.from(shot.data,'base64'));
 fs.writeFileSync(path.join(output,'verification.json'),JSON.stringify({status:'PASS_BROWSER_ACTUAL_WORKSPACE',runs,blocked_id:blocked.id,checks,errors,investment_approved:false},null,2)+'\n');
 console.log(JSON.stringify({status:'PASS_BROWSER_ACTUAL_WORKSPACE',runs}));
 }finally{child.kill();for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('browser closed'));}setTimeout(()=>fs.rmSync(profile,{recursive:true,force:true}),300);}
})().catch(e=>{fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({status:'FAIL',error:String(e),stderr},null,2));console.error(e);process.exitCode=1;});
