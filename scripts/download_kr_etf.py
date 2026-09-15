from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf


UNIVERSE_FILE = Path("config/kr_etf_universe.csv")
OUTPUT_DIR = Path("data/etf_kr")
SUMMARY_FILE = OUTPUT_DIR / "_data_summary.csv"
START_DATE = "2000-01-01"


def download_etf(yahoo_ticker: str) -> pd.DataFrame:
    df = yf.download(
        yahoo_ticker,
        start=START_DATE,
        interval="1d",
        auto_adjust=False,
        progress=False,
        actions=False,
        threads=False,
    )
    if df.empty:
        raise RuntimeError(f"{yahoo_ticker}: no data")

    if isinstance(df.columns, pd.MultiIndex):
        if yahoo_ticker in df.columns.get_level_values(-1):
            df = df.xs(yahoo_ticker, axis=1, level=-1)
        else:
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    df = df.reset_index()
    cols = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise RuntimeError(f"{yahoo_ticker}: missing {missing}")

    df = df[cols].copy()
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return (
        df.sort_values("Date")
        .drop_duplicates("Date", keep="last")
        .reset_index(drop=True)
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    universe = pd.read_csv(UNIVERSE_FILE, dtype={"code": str})
    universe["code"] = universe["code"].str.zfill(6)

    summary = []
    failed = []

    for row in universe.itertuples(index=False):
        print(f"Downloading {row.name} ({row.yahoo_ticker}) ...")
        try:
            df = download_etf(row.yahoo_ticker)
            out = OUTPUT_DIR / f"{row.code}_{row.name}.csv"
            df.to_csv(out, index=False)
            summary.append({
                "yahoo_ticker": row.yahoo_ticker,
                "code": row.code,
                "name": row.name,
                "role": row.role,
                "proxy_quality": row.proxy_quality,
                "rows": len(df),
                "first_date": df["Date"].min().date(),
                "last_date": df["Date"].max().date(),
                "duplicate_dates": int(df["Date"].duplicated().sum()),
                "missing_prices": int(df[["Open", "High", "Low", "Close", "Adj Close"]].isna().sum().sum()),
                "updated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })
            print(f"OK: {row.name} {df['Date'].min().date()} ~ {df['Date'].max().date()} ({len(df):,} rows)")
        except Exception as exc:
            failed.append({"ticker": row.yahoo_ticker, "name": row.name, "error": repr(exc)})
            print(f"ERROR: {row.name}: {exc}")

    if summary:
        pd.DataFrame(summary).to_csv(SUMMARY_FILE, index=False)

    if failed:
        for item in failed:
            print(item)
        raise RuntimeError(f"{len(failed)} Korean ETF ticker(s) failed.")

    print("All Korean ETF data downloaded successfully.")


if __name__ == "__main__":
    main()
