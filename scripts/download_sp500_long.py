from pathlib import Path

import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "indices"
OUTPUT_FILE = OUTPUT_DIR / "SP500_LONG.csv"

TICKER = "^GSPC"
START_DATE = "1927-01-01"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = yf.download(
        TICKER,
        start=START_DATE,
        auto_adjust=False,
        actions=False,
        progress=False,
    )

    if df.empty:
        raise RuntimeError("S&P 500 long-history download returned no data.")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()

    required = [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Adj Close",
        "Volume",
    ]

    missing = [col for col in required if col not in df.columns]
    if missing:
        raise RuntimeError(f"Missing columns: {missing}")

    df = df[required].copy()

    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    df = df.sort_values("Date").drop_duplicates("Date")

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"Saved: {OUTPUT_FILE}")
    print(f"Rows: {len(df):,}")
    print(f"First date: {df['Date'].iloc[0]}")
    print(f"Last date: {df['Date'].iloc[-1]}")


if __name__ == "__main__":
    main()
