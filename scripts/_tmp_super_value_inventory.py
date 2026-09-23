from pathlib import Path
import json, re
import pandas as pd

root = Path(".")
fin = root/"data"/"financials"
out = {
  "financials_exists": fin.exists(),
  "full_history_exists": (fin/"full_history").exists(),
  "recent_batches_exists": (fin/"recent_batches").exists(),
  "full_history_files": [],
  "recent_batch_files": [],
  "candidate_factor_files": [],
  "coverage": {},
}
if (fin/"full_history").exists():
    out["full_history_files"] = [str(p) for p in sorted((fin/"full_history").glob("*"))]
if (fin/"recent_batches").exists():
    out["recent_batch_files"] = [str(p) for p in sorted((fin/"recent_batches").glob("*"))]
out["candidate_factor_files"] = [
    str(p) for p in sorted(fin.rglob("*"))
    if p.is_file() and any(k in p.name.lower() for k in ["factor","valuation","ratio","per","pbr","psr","pcr"])
]

def coverage(files):
    years=set(); periods=set(); fs=set(); min_fd=None; max_fd=None; rows=0; errors=[]
    for p in files:
        m=re.search(r"dart_full_(\d{4})_([A-Z0-9]+)_([A-Z]+)_", p.name)
        if m:
            years.add(int(m.group(1))); periods.add(m.group(2)); fs.add(m.group(3))
        try:
            df=pd.read_csv(p, compression="infer", usecols=lambda c: c in {"filing_date","stock_code","period","requested_year","fs_div"}, low_memory=False)
            rows += len(df)
            if "requested_year" in df:
                years |= set(pd.to_numeric(df["requested_year"], errors="coerce").dropna().astype(int).unique().tolist())
            if "period" in df:
                periods |= set(df["period"].dropna().astype(str).unique().tolist())
            if "fs_div" in df:
                fs |= set(df["fs_div"].dropna().astype(str).unique().tolist())
            if "filing_date" in df:
                x=pd.to_datetime(df["filing_date"], errors="coerce")
                if x.notna().any():
                    a=x.min(); b=x.max()
                    min_fd = a if min_fd is None or a<min_fd else min_fd
                    max_fd = b if max_fd is None or b>max_fd else max_fd
        except Exception as e:
            errors.append(f"{p}: {e!r}")
    return {
      "files": len(files), "rows": rows, "years": sorted(years),
      "periods": sorted(periods), "fs_div": sorted(fs),
      "min_filing_date": None if min_fd is None else str(min_fd.date()),
      "max_filing_date": None if max_fd is None else str(max_fd.date()),
      "errors": errors[:20],
    }

fh=[Path(p) for p in out["full_history_files"] if p.endswith((".csv",".csv.gz"))]
rb=[Path(p) for p in out["recent_batch_files"] if p.endswith((".csv",".csv.gz"))]
out["coverage"]["full_history"]=coverage(fh)
out["coverage"]["recent_batches"]=coverage(rb)

# KRX price status
p=root/"data"/"status"/"krx_equities_status.csv"
if p.exists():
    out["krx_status"]=pd.read_csv(p).tail(1).to_dict(orient="records")[0]

Path("analysis").mkdir(exist_ok=True)
Path("analysis/super_value_inventory.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(json.dumps(out["coverage"], ensure_ascii=False, indent=2))
