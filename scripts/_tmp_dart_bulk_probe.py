from pathlib import Path
import json, time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

opt=Options()
opt.add_argument("--headless=new")
opt.add_argument("--no-sandbox")
opt.add_argument("--disable-dev-shm-usage")
opt.add_argument("--window-size=1920,1080")
driver=webdriver.Chrome(options=opt)
out=[]
try:
    driver.get("https://opendart.fss.or.kr/disclosureinfo/fnltt/dwld/main.do")
    WebDriverWait(driver,30).until(EC.presence_of_element_located((By.CSS_SELECTOR,"table.tb01")))
    time.sleep(2)
    for tr in driver.find_elements(By.CSS_SELECTOR,"table.tb01 tbody tr"):
        tds=tr.find_elements(By.TAG_NAME,"td")
        vals=[td.text.strip() for td in tds]
        if not vals: continue
        links=[]
        for a in tr.find_elements(By.TAG_NAME,"a"):
            links.append({
                "text":a.text.strip(),
                "href":a.get_attribute("href"),
                "onclick":a.get_attribute("onclick"),
            })
        out.append({"cells":vals,"links":links})
finally:
    driver.quit()
Path("analysis").mkdir(exist_ok=True)
Path("analysis/dart_bulk_selenium_probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(out[:10],ensure_ascii=False,indent=2))
