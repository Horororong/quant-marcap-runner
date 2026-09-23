from pathlib import Path
import json, time, zipfile, os, glob
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

base=Path("analysis/dart_sample").resolve()
base.mkdir(parents=True,exist_ok=True)
for f in base.glob("*"): f.unlink()

opt=Options()
opt.add_argument("--headless=new"); opt.add_argument("--no-sandbox"); opt.add_argument("--disable-dev-shm-usage")
opt.add_experimental_option("prefs",{
  "download.default_directory":str(base),
  "download.prompt_for_download":False,
  "download.directory_upgrade":True,
  "safebrowsing.enabled":True,
})
driver=webdriver.Chrome(options=opt)
out={"downloads":[]}
try:
    driver.get("https://opendart.fss.or.kr/disclosureinfo/fnltt/dwld/main.do")
    WebDriverWait(driver,30).until(EC.presence_of_element_located((By.CSS_SELECTOR,"table.tb01")))
    time.sleep(2)
    for st in ["BS","PL","CF"]:
        els=driver.find_elements(By.CSS_SELECTOR,"table.tb01 a")
        target=None
        for a in els:
            oc=a.get_attribute("onclick") or ""
            if "download_ext002('2023','FY', '"+st+"'" in oc:
                target=a; break
        if target is None: raise RuntimeError("target not found "+st)
        before=set(base.iterdir())
        driver.execute_script("arguments[0].click();",target)
        deadline=time.time()+90
        newfile=None
        while time.time()<deadline:
            files=set(base.iterdir())
            candidates=[p for p in files-before if p.suffix.lower()==".zip" and not p.name.endswith(".crdownload")]
            cr=list(base.glob("*.crdownload"))
            if candidates and not cr:
                newfile=sorted(candidates,key=lambda x:x.stat().st_mtime)[-1]; break
            time.sleep(1)
        if newfile is None: raise RuntimeError("download timeout "+st)
        rec={"statement":st,"zip":newfile.name,"size":newfile.stat().st_size,"members":[]}
        with zipfile.ZipFile(newfile) as z:
            for info in z.infolist():
                raw=info.filename
                try: nm=raw.encode("cp437").decode("euc-kr")
                except Exception: nm=raw
                data=z.read(info)
                tmp=base/("_tmp_"+st+".txt")
                tmp.write_bytes(data)
                parsed=None; err=None
                for enc in ["cp949","utf-8-sig","utf-8"]:
                    try:
                        df=pd.read_csv(tmp,sep="\t",encoding=enc,dtype=str,low_memory=False)
                        parsed=df; used=enc; break
                    except Exception as e: err=repr(e)
                item={"name":nm,"bytes":len(data)}
                if parsed is not None:
                    item["encoding"]=used
                    item["columns"]=list(parsed.columns)
                    item["rows"]=len(parsed)
                    item["head"]=parsed.head(3).fillna("").to_dict(orient="records")
                    item["markets"]=parsed.get("시장구분",pd.Series(dtype=str)).dropna().astype(str).value_counts().head(10).to_dict()
                    item["fs_types"]=parsed.get("재무제표종류",pd.Series(dtype=str)).dropna().astype(str).value_counts().head(10).to_dict()
                else:
                    item["error"]=err
                rec["members"].append(item)
        out["downloads"].append(rec)
finally:
    driver.quit()
Path("analysis/dart_bulk_sample_schema.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2)[:50000])
