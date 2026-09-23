from pathlib import Path
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

opt=Options()
opt.add_argument("--headless=new"); opt.add_argument("--no-sandbox"); opt.add_argument("--disable-dev-shm-usage")
out={}
try:
    d=webdriver.Chrome(options=opt)
    d.get("https://opendart.fss.or.kr/disclosureinfo/fnltt/dwld/main.do")
    out["url"]=d.current_url
    try:
        out["download_ext002"]=d.execute_script("return download_ext002.toString();")
    except Exception as e:
        out["function_error"]=repr(e)
    try:
        out["download_ext001"]=d.execute_script("return typeof download_ext001 === 'function' ? download_ext001.toString() : '';")
    except Exception as e:
        out["function1_error"]=repr(e)
    d.quit()
except Exception as e:
    out["driver_error"]=repr(e)
Path("analysis").mkdir(exist_ok=True)
Path("analysis/dart_download_function.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
