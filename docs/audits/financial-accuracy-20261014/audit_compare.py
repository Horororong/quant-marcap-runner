"""Independent Decimal source audit. No operating parser imports."""
import argparse,csv,hashlib,json,os,re,sys,zipfile
from collections import Counter
from decimal import Decimal,InvalidOperation
from pathlib import Path
p=argparse.ArgumentParser()
for name in ("workdir","review","controls","output"):p.add_argument("--"+name,type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
verify=json.loads((a.workdir/"verify.json").read_text())
assert verify["status"]=="ok"
assert verify["kit_id"]=="26e4ec02e56943ccc497cef786e2972dafc44f213ba805849769e9f0789686cd"
assert Path(sys.executable).parent.parent.name==".venv"
sel=json.loads((a.review/"selection.json").read_text())
ctl=json.loads(a.controls.read_text())
metrics=json.loads((a.review/"selected_metrics.json").read_text())
manifest=json.loads((a.review/"source_manifest.json").read_text())
assert len(sel["samples"])==40 and len({s["rcept_no"] for s in sel["samples"]})==40 and len(metrics)==565
sha=lambda b:hashlib.sha256(b).hexdigest()
for e in manifest:
    paths=list((a.workdir/"review"/"originals").glob(e["rcept_no"]+"-*.zip"))
    assert len(paths)==1 and sha(paths[0].read_bytes())==e["sha256"]==e["expected_sha256"]
    with zipfile.ZipFile(paths[0]) as z:
        assert z.testzip() is None
        for member in e["members"]:assert sha(z.read(member["name"]))==member["sha256"]
norm=lambda s:re.sub(r"\s+","",s or "")
scale={"원":Decimal(1),"천원":Decimal(1000),"백만원":Decimal(1000000),"억원":Decimal(100000000)}
def number(raw,label="",metric=""):
    s=norm(raw).replace(",","").replace("−","-").replace("–","-")
    if s in {"","-","—","―","ㆍ"}:return None
    negative=False
    if s.startswith(("△","Δ","▲")):negative=True;s=s[1:]
    if s.startswith("(-)"):negative=True;s=s[3:]
    elif s.startswith("(") and s.endswith(")"):negative=True;s=s[1:-1]
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?",s):return None
    try:v=Decimal(s)
    except InvalidOperation:return None
    if negative:v=-abs(v)
    if metric in {"net_income","operating_income","gross_profit"} and "손실" in norm(label) and "이익" not in norm(label) and v>0:v=-v
    return v
def verdict(ss):return "FAIL" if "FAIL" in ss else "UNVERIFIED" if "UNVERIFIED" in ss else "PASS"
def table(sid,t):return json.loads((a.review/(sid+"-member00-table-"+str(t).zfill(4)+".json")).read_text())
def loc(sid,t,r,c):return "review/"+sid+"-member00-table-"+str(t).zfill(4)+".json#rows["+str(r)+"].cells["+str(c)+"]"
def ds(v):return "" if v is None else format(v,"f")
def numeric_status(expected,actual):
    return "UNVERIFIED" if expected is None else "FAIL" if actual is None or expected!=actual else "PASS"
detail=[];fields=[];checks=[];sample_results=[]
def check(s,key,status,original,extracted,reason,evidence,applicable=True):
    r={"row_type":"CHECK","sample_id":s["sample_id"],"category":s["category"],"corp_name":s["corp_name"],"stock_code":s["stock_code"],"corp_code":s["corp_code"],"rcept_no":s["rcept_no"],"accounting_period":s["period"],"original_period_end":ctl["samples"][s["sample_id"]]["original_period_end"],"extracted_period_end":s["period_end"],"financial_field":"@"+key,"check":key,"original_value":original,"extracted_value":extracted,"unit":"","verdict":status,"reason":reason,"evidence_location":evidence,"applicable":str(applicable)}
    detail.append(r);checks.append(r)
for s in sel["samples"]:
    sid=s["sample_id"];e=next(e for e in manifest if e["sample_id"]==sid)
    sm=json.loads((a.review/(sid+"-source-map.json")).read_text())
    assert sm["members"][0]["sha256"]==e["members"][0]["sha256"]
    cik=next(t["attributes"]["aregcik"] for t in sm["members"][0]["metadata_tags"] if t["tag"]=="company-name")
    assert cik==ctl["samples"][sid]["cik"]
    own=[f for f in metrics if f["sample_id"]==sid];fs=[]
    for f in own:
        ti,ri,ci=map(int,(f["table_index"],f["row_index"],f["value_col"]))
        t=table(sid,ti);tc=ctl["tables"][sid+":"+str(ti)]
        cells=[c["text"] for c in t["rows"][ri]["cells"]];raw=cells[ci];label=cells[0]
        unit=tc["unit"];mul=scale.get(unit);actual=number(f["amount_krw"])
        literal=number(raw,label,f["metric"]);literal_krw=literal*mul if literal is not None and mul is not None else None
        ls=numeric_status(literal_krw,actual)
        us="UNVERIFIED" if mul is None else "PASS" if f["unit"]==unit and number(f["unit_multiplier"])==mul else "FAIL"
        ss="PASS" if f["scope"]==tc["scope"] else "FAIL"
        cs="PASS" if ci in tc["current_group_cols"] else "FAIL"
        choices=[c for c in tc["current_group_cols"] if c<len(cells) and cells[c]!=""]
        numeric_choices=[c for c in choices if number(cells[c],label,f["metric"]) is not None]
        ec=numeric_choices[0] if numeric_choices else choices[0] if choices else None;er=cells[ec] if ec is not None else ""
        expected=number(er,label,f["metric"]);et,ei=ti,ri;correction="PASS";reasons=[]
        target=ctl.get("correction_remap",{}).get(sid,{}).get(str(ti))
        if target is not None:
            corrected=table(sid,target)
            matches=[(i,r) for i,r in enumerate(corrected["rows"]) if r["cells"] and norm(r["cells"][0]["text"])==norm(label)]
            if len(matches)==1:
                et=target;ei,row=matches[0];ec=1;er=row["cells"][ec]["text"];expected=number(er,label,f["metric"])
                correction="PASS" if sid=="S24" and ti==7 and ci>=3 else "FAIL"
                if sid=="S24" and ti==7 and ci>=3:cs="PASS"
                if correction=="FAIL":reasons.append("정정 전 영역 선택; 정정 후 본문과 대조")
            else:correction="UNVERIFIED";reasons.append("정정 후 계정 대응 근거 부족")
        ek=expected*mul if expected is not None and mul is not None else None
        vs=numeric_status(ek,actual)
        if cs=="FAIL":vs="FAIL";reasons.append("현재 열이 아닌 비교기간 열 선택; 대시를 0으로 가정하지 않음")
        ks="FAIL" if tc["kind"] in {"segment","historical_merger","foreign_currency_subset"} else "PASS"
        if ks=="FAIL":reasons.append("당기 전체 기업 재무항목이 아닌 "+tc["kind"])
        if sid=="S24" and f["metric"]=="current_liabilities":
            vs="UNVERIFIED";reasons.append("원문 7,205,734,7733 오기/합계 모순; 진실 금액 검증불가")
        amount=verdict([vs,ks,ss])
        ps="PASS" if f["period_end"]==tc["period_end"] else "FAIL"
        window="UNVERIFIED" if tc["has_three_month_and_cumulative_header"] else "PASS"
        if ps=="FAIL":reasons.append("기간 종료일 불일치")
        if ls=="FAIL":reasons.append("선택 원문 셀과 원화 정규화값 불일치")
        if us=="FAIL":reasons.append("단위/배수 불일치 또는 누락")
        if ss=="FAIL":reasons.append("연결/별도/사업부문 분류 불일치")
        if window=="UNVERIFIED":reasons.append("3개월/누적 혼재, 측정 시작일/길이 메타데이터 없음")
        overall=verdict([amount,us,ss,ps,correction,window])
        r={"row_type":"FIELD","sample_id":sid,"category":s["category"],"corp_name":s["corp_name"],"stock_code":s["stock_code"],"corp_code":s["corp_code"],"rcept_no":s["rcept_no"],"accounting_period":f["period"],"fiscal_year":f["fiscal_year"],"original_period_end":tc["period_end"],"extracted_period_end":f["period_end"],"financial_field":f["metric"],"scope_original":tc["scope"],"scope_extracted":f["scope"],"original_account_name":label,"extracted_account_name":f["account_name"],"original_value":er,"original_amount_krw":ds(ek),"extracted_value":f["amount_krw"],"extracted_reported_value":f["amount_reported"],"unit":unit,"extracted_unit":f["unit"],"verdict":overall,"amount_verdict":amount,"literal_original_value":raw,"literal_amount_krw":ds(literal_krw),"literal_amount_verdict":ls,"unit_verdict":us,"period_verdict":ps,"scope_verdict":ss,"current_column_verdict":cs,"correction_verdict":correction,"measurement_window_verdict":window,"evidence_location":loc(sid,et,ei,ec if ec is not None else ci),"literal_evidence_location":loc(sid,ti,ri,ci),"source_zip_sha256":e["sha256"],"source_member_sha256":e["members"][0]["sha256"],"reason":"; ".join(reasons),"applicable":"True"}
        fields.append(r);fs.append(r);detail.append(r)
    check(s,"1_identity","FAIL" if cik!=s["corp_code"] else "UNVERIFIED",cik,s["corp_code"],"AREgCIK 일치; 과거 종목코드/사명변경의 독립 자료 미확보. 이름 차이만으로 오류 단정하지 않음.",sid+"-source-map.json#metadata_tags")
    end=ctl["samples"][sid]["original_period_end"]
    check(s,"2_receipt_report_period","FAIL" if s["period_end"]!=end else "UNVERIFIED",end,s["period_end"],"원문 표지/재무제표 종료일 불일치. 접수번호는 원본 XML명·manifest와 일치; 별도 실시간 접수 API 인증은 미수행.",sid+"-source-map.json#document_text_head")
    check(s,"3_amounts",verdict([r["amount_verdict"] for r in fs]) if fs else "UNVERIFIED",str(len(fs))+" source comparisons",str(len(own))+" rows","당기 열/정정후/범위를 대조. 종료일은 항목2에 별도 판정. NO_METRICS에는 추출값이 없음.",sid+"-extracted.json; per-table originals")
    check(s,"4_units",verdict([r["unit_verdict"] for r in fs]) if fs else "UNVERIFIED","원문 단위","stored unit/multiplier","Decimal 정확 비교; 허용오차 0원, 근거 부족 UNVERIFIED.",sid+"-source-map.json; per-table titles")
    check(s,"5_scope",verdict([r["scope_verdict"] for r in fs]) if fs else "UNVERIFIED","CFS/OFS/segment","stored scope","연결/개별 표제 직접 확인. 과거 연간 CFS의 기간 문제는 항목2; 추출값이 없으면 처리범위 검증불가.",sid+"-source-map.json")
    check(s,"6_corrections","FAIL" if any(r["correction_verdict"]=="FAIL" for r in fs) else "UNVERIFIED","원문 정정전/정정후","stored candidate selection","정정전 영역 선택은 FAIL. 그 외 원공시·전체 정정 접수 체인 독립 확보 미완료로 UNVERIFIED.",sid+"-source-map.json; manual correction_remap")
    if sid in ctl["financial_absence_evidence"]:
        ne=ctl["financial_absence_evidence"][sid]
        check(s,"7_no_metrics","FAIL",ne["source_numeric_block"],"NO_METRICS",ne["reason"]+" 숫자 블록 임의 분리 미수행.",loc(sid,ne["table"],ne["row"],ne["column"]))
    else:check(s,"7_no_metrics","UNVERIFIED","","","비적용: NO_METRICS 표본 아님; 적용항목 집계 제외.","",False)
    check(s,"8_point_in_time","UNVERIFIED","공개시각·수정 이력 필요","filing_date="+s["rcept_dt"],"실제 전략 신호일/조회시각/원공시 수정 체인 미확보; 접수일·회계종료일로 대체하지 않음.",s["rcept_no"]+"; no PIT evidence")
    ownchecks=[r for r in checks if r["sample_id"]==sid and r["applicable"]=="True"]
    sample_results.append({"sample_id":sid,"category":s["category"],"corp_name":s["corp_name"],"rcept_no":s["rcept_no"],"field_count":len(fs),"verdict":verdict([r["verdict"] for r in ownchecks]),"checks":{r["check"]:r["verdict"] for r in ownchecks}})
count=lambda rs,k:dict(Counter(r[k] for r in rs))
summary={"samples":40,"financial_fields":565,"sample_verdict":count(sample_results,"verdict"),"field_verdict":count(fields,"verdict"),"originals_verified":len(manifest),"all_requested_items_verified":False,"seed":sel["seed"],"cohort_count":sel["cohort_count"],"cohort_status_counts":sel["cohort_status_counts"],"runtime_python":sys.executable,"runtime_verify_status":verify["status"],"kit_id":verify["kit_id"],"audit_code_commit":os.getenv("GITHUB_SHA",""),"audit_run_id":os.getenv("GITHUB_RUN_ID",""),"manual_controls_sha256":sha(a.controls.read_bytes()),"metric_input_sha256":sha((a.review/"selected_metrics.json").read_bytes()),"samples_detail":sample_results}
for k in ("amount_verdict","literal_amount_verdict","unit_verdict","scope_verdict","current_column_verdict","correction_verdict","period_verdict","measurement_window_verdict"):summary[k]=count(fields,k)
summary["applicable_check_verdict"]=count([r for r in checks if r["applicable"]=="True"],"verdict")
summary["check_breakdown"]={k:count([r for r in checks if r["check"]==k and r["applicable"]=="True"],"verdict") for k in sorted({r["check"] for r in checks})}
assert sum(summary["field_verdict"].values())==565 and sum(summary["sample_verdict"].values())==40
columns=list(dict.fromkeys(k for r in detail for k in r))
with (a.output/"audit_details.csv").open("w",encoding="utf-8-sig",newline="") as h:
    w=csv.DictWriter(h,fieldnames=columns);w.writeheader();w.writerows(detail)
(a.output/"audit_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
def countrow(name,c):
    denom=sum(c.values());rate=Decimal(c.get("PASS",0))*100/Decimal(denom) if denom else Decimal(0)
    return "|"+name+"|"+"|".join(str(c.get(k,0)) for k in ["PASS","FAIL","UNVERIFIED"])+"|"+format(rate,".4f")+"%|\n"
report="# 재무데이터 독립 정확성 감사\n\n**결론: 정확성 통과 불가. 신규 legacy 재무 데이터는 현재 투자 백테스트 입력으로 부적합하다.** 운영 코드·원본 데이터·main을 변경하지 않았다.\n\n## 실제 결과\n\n|집계 대상|PASS|FAIL|UNVERIFIED|PASS/전체|\n|---|---:|---:|---:|---:|\n"
for name,k in [("표본 종합 (40)","sample_verdict"),("추출 필드 종합 (565)","field_verdict"),("선택 셀의 금액·단위 산술 (565)","literal_amount_verdict"),("당기·정정·대상 반영 금액 (565)","amount_verdict"),("단위·배수 (565)","unit_verdict"),("기간 종료일 (565)","period_verdict")]:report+=countrow(name,summary[k])
report+="\n8항목의 적용 체크 총290개 (CHECK7 비적용30개 제외): "+json.dumps(summary["applicable_check_verdict"],ensure_ascii=False)+".\n\n|검증 항목|PASS|FAIL|UNVERIFIED|PASS/전체|\n|---|---:|---:|---:|---:|\n"
for key,c in summary["check_breakdown"].items():report+=countrow(key,c)
report+="\n"+(a.output/"audit_narrative.md").read_text()
report+="\n## 실행 및 보존 증거\n\n- 감사 코드 commit: "+summary["audit_code_commit"]+"\n- Actions run: https://github.com/Horororong/quant-marcap-runner/actions/runs/"+summary["audit_run_id"]+"\n- 실제 dedicated Python: "+sys.executable+"\n- sandbox_runtime verify: "+verify["status"]+", kit_id "+verify["kit_id"]+"\n- 원본 40개 ZIP SHA256/CRC와 XML member SHA 확인, FIELD565/CHECK320 결과 행 검증.\n- controls SHA256: "+summary["manual_controls_sha256"]+"\n- metric inputs SHA256: "+summary["metric_input_sha256"]+"\n"
report+="\n## 표본별 목록\n\n|ID|범주|기업(저장명)|접수번호|필드 수|종합|\n|---|---|---|---|---:|---|\n"
for s in sample_results:report+="|"+"|".join(str(s[k]) for k in ["sample_id","category","corp_name","rcept_no","field_count","verdict"])+"|\n"
(a.output/"audit_report.md").write_text(report,encoding="utf-8")
repro=(a.output/"reproduction_template.md").read_text()
repro+="\n실행 증거: code="+summary["audit_code_commit"]+", run="+summary["audit_run_id"]+", Python="+sys.executable+", verify="+verify["status"]+".\n\ncontrols SHA="+summary["manual_controls_sha256"]+"; metrics SHA="+summary["metric_input_sha256"]+".\n"
(a.output/"audit_reproduction.md").write_text(repro,encoding="utf-8")
files=["audit_report.md","audit_details.csv","audit_reproduction.md","audit_summary.json"]
(a.output/"audit_artifact_manifest.json").write_text(json.dumps({n:{"sha256":sha((a.output/n).read_bytes()),"bytes":(a.output/n).stat().st_size} for n in files},indent=2)+"\n")
print(json.dumps({k:v for k,v in summary.items() if k!="samples_detail"},ensure_ascii=False),flush=True)
