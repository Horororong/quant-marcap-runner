from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "proxy_long" / "raw"
START_DATE = "1970-01-01"

FRED_SERIES = {
    "DGS20": "US_20Y_YIELD.csv",
    "DTB3": "US_3M_TBILL.csv",
}

LBMA_GOLD_URL = (
    "https://raw.githubusercontent.com/unbalancedparentheses/"
    "forex-centuries/main/data/sources/lbma/lbma_gold_daily.csv"
)


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

    first_valid = df.loc[df["Value"].notna(), "Date"].iloc[0].date()
    last_valid = df.loc[df["Value"].notna(), "Date"].iloc[-1].date()

    print(
        f"{series_id}: rows={len(df):,}, "
        f"first_valid={first_valid}, last_valid={last_valid}, "
        f"saved={output_path}"
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
        f"LBMA_GOLD: rows={len(df):,}, "
        f"first_date={df['Date'].iloc[0].date()}, "
        f"last_date={df['Date'].iloc[-1].date()}, "
        f"saved={output_path}"
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
        f"SP500_PRICE: rows={len(df):,}, "
        f"first_date={df['Date'].iloc[0].date()}, "
        f"last_date={df['Date'].iloc[-1].date()}, "
        f"saved={output_path}"
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    save_sp500_slice()

    for series_id, output_name in FRED_SERIES.items():
        download_fred_series(series_id, output_name)

    download_gold_lbma()


if __name__ == "__main__":
    main()
