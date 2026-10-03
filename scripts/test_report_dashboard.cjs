// Browser interaction assertions; NAV provenance is supplied by the caller.
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const source = path.resolve(process.argv[2]);
  const screen = process.argv[3] && path.resolve(process.argv[3]);
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROMIUM_EXECUTABLE || undefined,
    args:['--no-sandbox'],timeout:20000});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:980}});
    page.setDefaultTimeout(10000);
    const evidence=[];
    const errors = [];page.on('pageerror',e=>errors.push(e.message));
    await page.goto('file://'+source,{waitUntil:'load',timeout:30000});
    await page.waitForFunction(()=>window.reportRenderComplete===true,{timeout:30000});
    const contract = await page.evaluate(()=>{
      const data=window.quantReport;
      return {periods:Object.entries(data.periods).map(([id,p])=>({id,ready:p.ready})),
        costs:Array.from(document.querySelector('#cost').options).map(x=>x.value)};
    });
    let checked=0;
    for(const p of contract.periods){
      await page.selectOption('#period',p.id);
      await page.waitForFunction(id=>window.reportRenderComplete&&window.reportSelectedPeriod===id,p.id,{timeout:30000});
      const out=await page.evaluate(()=>{
        const data=window.quantReport.periods[document.querySelector('#period').value];
        const graphs=['wealth','log2','drawdown'].map(id=>document.getElementById(id));
        const rows=Array.from(document.querySelectorAll('#metrics tbody tr')).map(tr=>({series:tr.dataset.series,asset:tr.lastElementChild.textContent}));
        return {ready:data.ready,gapVisible:!document.querySelector('#gap').hidden,rows,
          traces:graphs.map(g=>g.data),axis:graphs[1].layout.yaxis,period:data,
          ending:document.querySelector('#ending-date').textContent};
      });
      if(!p.ready){assert.equal(out.gapVisible,true);assert.equal(out.rows.length,0);assert(out.traces.every(t=>t.length===0));continue;}
      assert.equal(out.gapVisible,false);assert(out.rows.length>0);assert.equal(out.axis.type,'log');
      assert.deepEqual(out.axis.tickvals,out.period.log_ticks.values);assert.deepEqual(out.axis.ticktext,out.period.log_ticks.labels);
      assert(out.ending.includes(out.period.ending_asset_date));
      const expectedFormat=v=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(v);
      for(let i=0;i<out.rows.length;i++){
        const s=out.period.series[out.rows[i].series],m=s.metrics,last=s.points.at(-1);
        assert.equal(out.rows[i].asset,expectedFormat(m.final_asset));assert.equal(out.traces[0][i].y.at(-1),m.final_asset);
        assert.equal(out.traces[1][i].y.at(-1),m.final_multiple);assert.equal(out.traces[1][i].customdata.at(-1)[1],m.final_asset);
        assert.equal(out.traces[1][i].customdata.at(-1)[0],m.final_multiple);
        assert.equal(out.traces[0][i].x.at(-1),out.period.actual_end);
        assert.deepEqual(out.traces[0][i].x,out.traces[1][i].x);assert.deepEqual(out.traces[0][i].x,out.traces[2][i].x);
        assert.equal(out.traces[2][i].y.at(-1),last.drawdown_pct);
        assert(out.traces[1][i].hovertemplate.includes('customdata[0]'));assert(out.traces[1][i].hovertemplate.includes('customdata[1]'));
        if(m.mdd!==null)assert(Math.abs(Math.min(...out.traces[2][i].y)/100-m.mdd)<1e-12);
      }
      // Relayout range synchronizes all three plots without recalculating metrics.
      await page.evaluate(async()=>{await Plotly.relayout(document.getElementById('wealth'),{'xaxis.range[0]':'2020-04-10','xaxis.range[1]':'2020-04-24'});});
      await page.waitForFunction(()=>document.getElementById('log2').layout.xaxis.range?.[0]==='2020-04-10');
      assert.equal(await page.evaluate(()=>document.getElementById('drawdown').layout.xaxis.range[1]),'2020-04-24');
      evidence.push({period:p.id,actual_start:out.period.actual_start,actual_end:out.period.actual_end,ending:out.ending,table:out.rows,chart_end_values:out.traces.map(t=>t.map(x=>x.y.at(-1)))});
      checked++;
    }
    const ready=contract.periods.find(p=>p.ready);assert(ready);
    await page.selectOption('#period',ready.id);
    await page.waitForFunction(id=>window.reportRenderComplete&&window.reportSelectedPeriod===id,ready.id);
    for(const cost of contract.costs){
      await page.selectOption('#cost',cost);
      await page.waitForFunction(cost=>window.reportRenderComplete&&document.getElementById('wealth').layout.uirevision.includes(':'+cost+':'),cost);
      const selected=await page.evaluate(()=>({rows:document.querySelectorAll('#metrics tbody tr').length,
        counts:['wealth','log2','drawdown'].map(id=>document.getElementById(id).data.length)}));
      assert(selected.counts.every(n=>n===selected.rows));assert(selected.rows>0);
    }
    await page.selectOption('#cost','all');
    await page.waitForFunction(()=>window.reportRenderComplete&&document.getElementById('wealth').layout.uirevision.includes(':all:'));
    // Plotly legend click actually hides the corresponding plotted line.
    const legend=page.locator('#wealth .legendtoggle').first();await legend.click();
    await page.waitForFunction(()=>document.getElementById('wealth').data[0].visible==='legendonly');await legend.click();
    await page.waitForFunction(()=>document.getElementById('wealth').data[0].visible!=='legendonly');
    // Move the real pointer over a plotted Log2 point and inspect its rendered popup.
    const hover=await page.evaluate(()=>{
      const g=document.getElementById('log2'),t=g.data[0],i=Math.floor(t.x.length*.65),r=g.getBoundingClientRect();
      return {x:r.left+g._fullLayout.xaxis._offset+g._fullLayout.xaxis.d2p(t.x[i]),
        y:r.top+g._fullLayout.yaxis._offset+g._fullLayout.yaxis.d2p(t.y[i]),
        date:t.x[i].slice(0,10),multiple:t.customdata[i][0].toFixed(6)+'배',
        asset:'$'+new Intl.NumberFormat('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}).format(t.customdata[i][1])};
    });
    await page.locator('#log2').scrollIntoViewIfNeeded();
    // Scrolling changes page-relative coordinates; measure the chart again.
    const bounds=await page.locator('#log2').boundingBox();
    const pointer=await page.evaluate(()=>{const g=document.getElementById('log2'),t=g.data[0],i=Math.floor(t.x.length*.65);return {x:g._fullLayout.xaxis._offset+g._fullLayout.xaxis.d2p(t.x[i]),y:g._fullLayout.yaxis._offset+g._fullLayout.yaxis.d2p(t.y[i])};});
    await page.mouse.move(bounds.x+pointer.x,bounds.y+pointer.y);
    await page.waitForFunction(h=>{const v=document.querySelector('#log2 .hoverlayer').textContent;return v.includes(h.date)&&v.includes(h.multiple)&&v.includes(h.asset);},hover);
    const hoverText=await page.locator('#log2 .hoverlayer').textContent();
    const hoverScreen=screen&&screen.replace(/\.png$/,'-hover.png');
    if(hoverScreen)await page.screenshot({path:hoverScreen,fullPage:true});
    await page.mouse.move(5,5);
    if(screen)await page.screenshot({path:screen,fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await page.waitForTimeout(300);
    const widths=await page.evaluate(()=>({body:document.body.scrollWidth,viewport:innerWidth,charts:['wealth','log2','drawdown'].map(id=>document.getElementById(id).getBoundingClientRect().width)}));
    assert(widths.body<=widths.viewport+2);assert(widths.charts.every(w=>w<=widths.viewport));
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({status:'passed',source,ready_periods_checked:checked,cost_options:contract.costs,
      checks:['period/table/three charts','ending wealth','true logarithmic axis/ticks/actual hover values','real pointer rendered Log2 hover popup','drawdown/MDD','shared zoom','cost/benchmark','legend','mobile width','missing periods'],period_evidence:evidence,rendered_hover:{expected:hover,text:hoverText,screenshot:hoverScreen||null},screenshot:screen||null}));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);console.log(JSON.stringify({status:'failed',error:e.message}));process.exit(1);});
