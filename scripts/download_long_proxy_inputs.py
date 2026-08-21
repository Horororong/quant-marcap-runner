from pathlib import Path
import io
import re
import urllib.parse
import urllib.request

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "proxy_long" / "raw"
START_DATE = "1970-01-01"

# DGS10/DGS30 are retained because the official DGS20 series has a historical
# gap (1987-01-01 through 1993-09-30). The Fed previously estimated that gap
# as the average of the 10-year and 30-year constant-maturity rates.
FRED_SERIES = {
    "DGS10": "US_10Y_YIELD.csv",
    "DGS20": "US_20Y_YIELD.csv",
    "DGS30": "US_30Y_YIELD.csv",
    "DTB3": "US_3M_TBILL.csv",
}

LBMA_GOLD_URL = (
    "https://raw.githubusercontent.com/unbalancedparentheses/"
    "forex-centuries/main/data/sources/lbma/lbma_gold_daily.csv"
)
SHILLER_PAGE_URL = "https://shillerdata.com/"


def download_fred_series(series_id: str, output_name: str) -> None:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    df = pd.read_csv(url)

    if df.empty:
        raise RuntimeError(f"FRED download returned no data: {series_id}")

    date_col = df.columns[0]
    value_col = df.columns[1]
    df = df.rename(columns={date_col: "Date", value_col: "Value"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    df = df.dropna(subset=["Date"])
    df = df[df["Date"] >= pd.Timestamp(START_DATE)]
    df = df.sort_values("Date").drop_duplicates("Date")

    if df["Value"].notna().sum() == 0:
        raise RuntimeError(f"No valid numeric observations after {START_DATE}: {series_id}")

    output_path = OUTPUT_DIR / output_name
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    valid = df.loc[df["Value"].notna(), "Date"]
    print(
        f"{series_id}: rows={len(df):,}, first_valid={valid.iloc[0].date()}, "
        f"last_valid={valid.iloc[-1].date()}, saved={output_path}"
    )


def download_gold_lbma() -> None:
    df = pd.read_csv(LBMA_GOLD_URL)
    required = {"date", "gold_pm_usd"}
    if not required.issubset(df.columns):
        raise RuntimeError(f"Unexpected LBMA gold columns: {list(df.columns)}")

    df = df.rename(columns={"date": "Date", "gold_pm_usd": "Close"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Date", "Close"])
    df = df[df["Date"] >= pd.Timestamp(START_DATE)]
    df = df.sort_values("Date").drop_duplicates("Date")

    if df.empty:
        raise RuntimeError(f"No valid LBMA gold observations after {START_DATE}.")

    output_path = OUTPUT_DIR / "GOLD_LBMA_PM_USD.csv"
    df[["Date", "Close"]].to_csv(output_path, index=False, encoding="utf-8-sig")
    print(
        f"LBMA_GOLD: rows={len(df):,}, first_date={df['Date'].iloc[0].date()}, "
        f"last_date={df['Date'].iloc[-1].date()}, saved={output_path}"
    )


def _find_shiller_xls_url() -> str:
    req = urllib.request.Request(
        SHILLER_PAGE_URL,
        headers={"User-Agent": "Mozilla/5.0 quant-research-data-loader"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        html = response.read().decode("utf-8", errors="ignore")

    # GoDaddy-hosted download URL changes over time, so discover it from the page.
    matches = re.findall(r'href=["\']([^"\']*ie_data\.xls[^"\']*)["\']', html, flags=re.I)
    if not matches:
        raise RuntimeError("Could not find ie_data.xls download link on shillerdata.com")
    return urllib.parse.urljoin(SHILLER_PAGE_URL, matches[0].replace("&amp;", "&"))


def _parse_shiller_date(value):
    if pd.isna(value):
        return pd.NaT
    try:
        x = float(value)
    except (TypeError, ValueError):
        return pd.NaT
    year = int(x)
    month = int(round((x - year) * 100))
    if not 1 <= month <= 12:
        return pd.NaT
    return pd.Timestamp(year=year, month=month, day=1)


def download_shiller_monthly() -> None:
    xls_url = _find_shiller_xls_url()
    req = urllib.request.Request(
        xls_url,
        headers={"User-Agent": "Mozilla/5.0 quant-research-data-loader"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        payload = response.read()

    df = pd.read_excel(io.BytesIO(payload), sheet_name="Data", skiprows=7, engine="xlrd")
    required = {"Date", "P", "D"}
    if not required.issubset(df.columns):
        raise RuntimeError(f"Unexpected Shiller columns: {list(df.columns)}")

    out = df[["Date", "P", "D"]].copy()
    out["Date"] = out["Date"].apply(_parse_shiller_date)
    out["PriceMonthlyAvg"] = pd.to_numeric(out["P"], errors="coerce")
    out["DividendAnnualized"] = pd.to_numeric(out["D"], errors="coerce")
    out = out.drop(columns=["P", "D"])
    out = out.dropna(subset=["Date", "PriceMonthlyAvg", "DividendAnnualized"])
    out = out[out["Date"] >= pd.Timestamp(START_DATE)]
    out = out.sort_values("Date").drop_duplicates("Date")

    if out.empty:
        raise RuntimeError("No valid Shiller observations after 1970-01-01")

    output_path = OUTPUT_DIR / "SHILLER_SP500_MONTHLY.csv"
    out.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(
        f"SHILLER: rows={len(out):,}, first_date={out['Date'].iloc[0].date()}, "
        f"last_date={out['Date'].iloc[-1].date()}, saved={output_path}"
    )


def save_sp500_slice() -> None:
    source = ROOT / "data" / "indices" / "SP500_LONG.csv"
    if not source.exists():
        raise FileNotFoundError(f"Missing source file: {source}")

    df = pd.read_csv(source)
    if "Date" not in df.columns or "Close" not in df.columns:
        raise RuntimeError("SP500_LONG.csv must contain Date and Close columns")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    df = df[df["Date"] >= pd.Timestamp(START_DATE)]
    df = df.sort_values("Date").drop_duplicates("Date")

    output_path = OUTPUT_DIR / "SP500_PRICE.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(
        f"SP500_PRICE: rows={len(df):,}, first_date={df['Date'].iloc[0].date()}, "
        f"last_date={df['Date'].iloc[-1].date()}, saved={output_path}"
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_sp500_slice()
    for series_id, output_name in FRED_SERIES.items():
        download_fred_series(series_id, output_name)
    download_gold_lbma()
    download_shiller_monthly()


if __name__ == "__main__":
    main()
