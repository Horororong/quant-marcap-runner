from pathlib import Path
import pandas as pd
from pykrx import stock

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"krx_tr_diagnostic"
OUT.mkdir(parents=True,exist_ok=True)

rows=[]
for market in ["KOSPI","KOSDAQ","KRX","테마"]:
    try:
        tickers=stock.get_index_ticker_list(market=market)
    except Exception:
        continue
    for t in tickers:
        try:
            n=stock.get_index_ticker_name(t)
        except Exception:
            n=""
        if ("TR" in str(n).upper()) or ("총수익" in str(n)) or ("KOSPI" in str(n).upper()) or ("코스피" in str(n)):
            rows.append({"market":market,"ticker":t,"name":n})
pd.DataFrame(rows).to_csv(OUT/"index_candidates.csv",index=False,encoding="utf-8-sig")

targets=[]
for r in rows:
    n=str(r["name"]).upper().replace(" ","")
    if n in {"KOSPITR","코스피TR"} or ("KOSPI" in n and n.endswith("TR")):
        targets.append(r)

logs=[]
for r in targets:
    try:
        df=stock.get_index_ohlcv("19900101","20260918",r["ticker"])
        logs.append({"ticker":r["ticker"],"name":r["name"],"rows":len(df),"start":str(df.index.min()),"end":str(df.index.max()),"columns":"|".join(map(str,df.columns))})
        if len(df):
            df.to_csv(OUT/f'{r["ticker"]}_{str(r["name"]).replace("/","_")}.csv',encoding="utf-8-sig")
    except Exception as e:
        logs.append({"ticker":r["ticker"],"name":r["name"],"error":repr(e)})
pd.DataFrame(logs).to_csv(OUT/"fetch_log.csv",index=False,encoding="utf-8-sig")
print(pd.DataFrame(rows).to_string(index=False))
print(pd.DataFrame(logs).to_string(index=False))
