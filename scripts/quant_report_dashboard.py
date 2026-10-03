"""Presentation only: render CURRENT's verified, precomputed report payload.

No investment metrics, wealth or drawdown are calculated here or in JavaScript.
Plotly is embedded from the pinned installed package; the HTML works offline.
"""
from pathlib import Path
import html
import json

from plotly.offline import get_plotlyjs


PAGE = r'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f6fa;color:#17243a;font:15px/1.6 system-ui,sans-serif}
main{max-width:1180px;margin:auto;padding:24px}h1{font-size:27px;margin:0 0 8px}h2{font-size:19px;margin:0}
.card{background:white;border:1px solid #dde3ed;border-radius:14px;margin:16px 0;padding:20px}
.controls{display:flex;gap:18px;flex-wrap:wrap}label{display:grid;gap:5px;font-weight:600}select{padding:9px;border:1px solid #b7c3d5;border-radius:7px;max-width:100%;font:inherit}
.note{color:#52617a;font-size:13px}.status{font-size:18px;font-weight:700}.gap{background:#fff4dc;color:#754b00;padding:14px;border-radius:8px}
.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;white-space:nowrap}th,td{padding:10px;text-align:right;border-bottom:1px solid #e7ebf2}th:first-child,td:first-child{text-align:left}
th{font-size:12px;color:#52617a}.chart{width:100%;height:350px}.chart-card{padding:18px 8px 2px}.chart-card h2{padding:0 12px}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}
@media(max-width:600px){main{padding:12px}h1{font-size:23px}.card{padding:14px}.chart-card{padding:12px 0}.chart{height:320px}.controls{gap:12px}label{width:100%}}
</style></head><body><main>
<h1>__TITLE__</h1><div class="card"><div id="conclusion" class="status"></div><div id="dates"></div><div id="summary"></div></div>
<div class="card controls"><label>분석기간<select id="period"></select></label><label>비용 비교<select id="cost"></select></label><label id="portfolio-label">포트폴리오<select id="portfolio"></select></label></div>
<div class="card"><h2>성과 비교</h2><div id="ending-date" class="note"></div><div class="table-wrap"><table id="metrics"><thead><tr>
<th>시리즈</th><th>CAGR<br>연복리수익률</th><th>누적수익률</th><th>MDD<br>최대낙폭</th><th>연환산 변동성</th><th>Sharpe 지수</th><th>최대 회복기간</th><th>해당 기간 종료자산</th>
</tr></thead><tbody></tbody></table></div><div id="gap" class="gap" hidden></div></div>
<div class="card chart-card"><h2>누적자산 · 초기 $10,000</h2><div id="wealth" class="chart"></div></div>
<div class="card chart-card"><h2>Log2 누적자산 · 시작자산 대비 배수</h2><div id="log2" class="chart"></div></div>
<div class="card chart-card"><h2>Drawdown · 고점 대비 하락률</h2><div id="drawdown" class="chart"></div></div>
<div class="card"><h2>핵심 한계와 계산 기준</h2><div id="limits"></div><div id="definitions" class="note"></div></div>
<details class="card"><summary>재현성·상세 진단</summary><pre id="diagnostics"></pre></details>
</main><script>__PLOTLY__</script><script id="report-data" type="application/json">__DATA__</script><script>
'use strict';
const report = JSON.parse(document.getElementById('report-data').textContent);
const $ = id => document.getElementById(id);
const graphIds=['wealth','log2','drawdown'];
const fmtPct=v=>v===null?'계산 불가/표본 부족':(v*100).toFixed(2)+'%';
const fmtMoney=v=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(v);
const text=(el,value)=>el.textContent=value;
const option=(value,label)=>{const o=document.createElement('option');o.value=value;o.textContent=label;return o;};
Object.entries(report.periods).forEach(([key,p])=>$('period').append(option(key,p.label+(p.ready?'':' · 데이터 부족'))));
const firstReady=Object.entries(report.periods).find(([,p])=>p.ready);if(firstReady)$('period').value=firstReady[0];
$('cost').append(option('all','비용 전·후 모두'));
Object.entries(report.cost_options).forEach(([key,label])=>$('cost').append(option(key,label)));
report.portfolios.forEach(p=>$('portfolio').append(option(p,p==='strategy'?'전략':p+' 분위')));
$('portfolio-label').hidden=report.portfolios.length<2;
text($('summary'),report.strategy_summary);
text($('definitions'),report.calculation_notes.join(' · '));
text($('diagnostics'),JSON.stringify(report.diagnostics,null,2));
const colors=['#2463d3','#dc7635','#2b9983','#7d5abe','#738095'];
let syncing=false,queue=Promise.resolve();
function selectedSeries(p){return Object.entries(p.series).filter(([key])=>{
 const meta=report.series_meta[key];return meta.kind==='benchmark'||(meta.portfolio===$('portfolio').value&&($('cost').value==='all'||meta.cost===$('cost').value));
});}
function traces(p,kind){return selectedSeries(p).map(([key,s],i)=>{
 const meta=report.series_meta[key],points=s.points;
 return {name:meta.label,x:points.map(r=>r.date),y:points.map(r=>kind==='wealth'?r.asset:kind==='log2'?r.multiple:r.drawdown_pct),
 customdata:points.map(r=>[r.multiple,r.asset,r.baseline?'기간 시작 직전 기준자산':'거래일 종가']),type:'scatter',mode:'lines',
 line:{color:meta.kind==='benchmark'?'#738095':colors[i%colors.length],width:2,dash:meta.kind==='benchmark'?'dash':'solid'},
 hovertemplate:kind==='drawdown'?'%{x|%Y-%m-%d}<br>%{y:.2f}%<extra>%{fullData.name}</extra>':
 '%{x|%Y-%m-%d}<br>%{customdata[0]:.6f}배<br>$%{customdata[1]:,.2f}<br>%{customdata[2]}<extra>%{fullData.name}</extra>'};
});}
function layout(p,kind){return {paper_bgcolor:'white',plot_bgcolor:'white',margin:{l:70,r:25,t:20,b:85},hovermode:'x unified',dragmode:'zoom',
 uirevision:$('period').value+':'+$('cost').value+':'+$('portfolio').value,
 legend:{orientation:'h',y:-.32},xaxis:{type:'date',rangeslider:{visible:true,thickness:.1},rangeselector:{buttons:[{count:1,label:'1개월',step:'month',stepmode:'backward'},{count:1,label:'1년',step:'year',stepmode:'backward'},{step:'all',label:'전체'}]}},
 yaxis:kind==='log2'?{type:'log',tickmode:'array',tickvals:p.log_ticks.values,ticktext:p.log_ticks.labels,title:{text:'시작자산 대비 배수'}}:
 kind==='drawdown'?{ticksuffix:'%',rangemode:'tozero',range:[null,0],zeroline:true,title:{text:'고점 대비 하락률'}}:{tickprefix:'$',title:{text:'표준화 자산 · 환율 미반영'}}};}
async function render(){
 const p=report.periods[$('period').value];window.reportRenderComplete=false;
 $('gap').hidden=p.ready; $('metrics').hidden=!p.ready;
 text($('ending-date'),'초기 $10,000 · 환율 미반영 · 추가 납입 없음');
 text($('dates'),p.ready?'실제 분석기간 '+p.actual_start+' ~ '+p.actual_end+' · 기준자산일 '+p.baseline_date:
 '요청기간 '+p.start+' ~ '+p.end);
 text($('conclusion'),p.ready?(p.monthly_statistical_samples!==null&&p.monthly_statistical_samples<12?'검증된 실행의 짧은 기간 보고입니다. 장기 투자 판단은 유보합니다.':'검증된 NAV의 기간별 성과입니다. 과거 성과는 미래 수익을 보장하지 않습니다.'):'데이터 부족으로 이 기간의 성과를 계산하지 않았습니다.');
 const limits=[...report.limitations,...(p.limitations||[])];
 if(report.report_complete===false)limits.unshift('요청한 일부 기간은 데이터 부족입니다. 기간 선택기에서 확인하세요.');
 text($('limits'),limits.join(' '));
 $('metrics').querySelector('tbody').replaceChildren();
 if(!p.ready){text($('gap'),p.reason);await Promise.all(graphIds.map(id=>Plotly.react($(id),[],{annotations:[{text:'데이터 부족 · 성과 계산 없음',showarrow:false}],xaxis:{visible:false},yaxis:{visible:false}},{responsive:true})));}
 else {
 text($('ending-date'),'해당 기간 종료자산 기준일: '+p.ending_asset_date+' · 초기 $10,000 · 환율 미반영 · 추가 납입 없음');
 selectedSeries(p).forEach(([key,s])=>{const m=s.metrics,tr=document.createElement('tr');tr.dataset.series=key;
 const values=[report.series_meta[key].label,fmtPct(m.cagr),fmtPct(m.cumulative_return),fmtPct(m.mdd),fmtPct(m.annual_volatility),m.sharpe===null?'계산 불가/표본 부족':m.sharpe.toFixed(3),m.recovery_days===null?'계산 불가/표본 부족':m.recovery_days+'일',fmtMoney(m.final_asset)];
 values.forEach((v,i)=>{const td=document.createElement('td');td.textContent=v;
 const metricKeys=[null,'cagr','cumulative_return','mdd','annual_volatility','sharpe','recovery_days','final_asset'];if(m.unavailable[metricKeys[i]])td.title=m.unavailable[metricKeys[i]];tr.append(td);});$('metrics').querySelector('tbody').append(tr);});
 await Promise.all(graphIds.map(id=>Plotly.react($(id),traces(p,id),layout(p,id),{responsive:true,scrollZoom:true,displaylogo:false})));
 }
 graphIds.forEach(id=>{const g=$(id);g.removeAllListeners('plotly_relayout');g.on('plotly_relayout',async ev=>{
 if(syncing)return;const update={};['xaxis.range[0]','xaxis.range[1]','xaxis.autorange'].forEach(k=>{if(k in ev)update[k]=ev[k];});
 if(Object.keys(update).length){syncing=true;try{await Promise.all(graphIds.filter(x=>x!==id).map(x=>Plotly.relayout($(x),update)));}finally{syncing=false;}}
 });});
 window.reportRenderComplete=true;window.reportSelectedPeriod=$('period').value;
}
['period','cost','portfolio'].forEach(id=>$(id).addEventListener('change',()=>{queue=queue.then(render);}));
queue=queue.then(render);window.quantReport=report;
</script></body></html>'''


def write_dashboard(payload: dict, output: Path) -> None:
    data = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    page = PAGE.replace('__TITLE__', html.escape(payload['title'])).replace('__DATA__', data).replace('__PLOTLY__', get_plotlyjs())
    Path(output).write_text(page, encoding='utf-8')
