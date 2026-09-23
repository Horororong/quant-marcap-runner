from pathlib import Path
import json, time, zipfile
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

base=Path("analysis/dart_sample").resolve()
base.mkdir(parents=True,exist_ok=True)
for f in base.glob("*"): f.unlink()
out={"ok":False,"files":[]}
d=None
try:
    opt=Options()
    opt.add_argument("--headless=new"); opt.add_argument("--no-sandbox"); opt.add_argument("--disable-dev-shm-usage")
    opt.add_argument("--window-size=1920,1080")
    opt.add_experimental_option("prefs", {"download.default_directory":str(base),"download.prompt_for_download":False})
    d=webdriver.Chrome(options=opt)
    d.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior":"allow","downloadPath":str(base)})
    d.get("https://opendart.fss.or.kr/disclosureinfo/fnltt/dwld/main.do")
    WebDriverWait(d,30).until(EC.presence_of_element_located((By.CSS_SELECTOR,"table.tb01")))
    time.sleep(2)
    out["function"]=d.execute_script("return download_ext002.toString();")
    target=None
    for a in d.find_elements(By.CSS_SELECTOR,"table.tb01 a"):
        oc=a.get_attribute("onclick") or ""
        if "download_ext002('2023','FY', 'PL'" in oc:
            target=a; out["onclick"]=oc; break
    if target is None: raise RuntimeError("target not found")
    d.execute_script("arguments[0].click();",target)
    deadline=time.time()+90
    while time.time()<deadline:
        files=list(base.iterdir())
        if files and not list(base.glob("*.crdownload")):
            break
        time.sleep(1)
    out["files"]=[{"name":f.name,"size":f.stat().st_size} for f in base.iterdir()]
    zips=list(base.glob("*.zip"))
    if zips:
        zp=zips[0]
        out["zip"]=zp.name
        out["members"]=[]
        with zipfile.ZipFile(zp) as z:
            for info in z.infolist():
                data=z.read(info)
                item={"raw_name":info.filename,"size":len(data)}
                for enc in ("cp949","euc-kr","utf-8-sig","utf-8"):
                    try:
                        text=data.decode(enc)
                        item["encoding"]=enc
                        tmp=base/"tmp.txt"; tmp.write_text(text,encoding="utf-8")
                        df=pd.read_csv(tmp,sep="\t",dtype=str,low_memory=False)
                        item["columns"]=list(df.columns)
                        item["rows"]=len(df)
                        item["head"]=df.head(2).fillna("").to_dict(orient="records")
                        break
                    except Exception as e:
                        item["last_error"]=repr(e)
                out["members"].append(item)
        out["ok"]=True
except Exception as e:
    out["error"]=repr(e)
finally:
    if d is not None:
        try:d.quit()
        except:pass
Path("analysis").mkdir(exist_ok=True)
Path("analysis/dart_download_function.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2)[:50000])
