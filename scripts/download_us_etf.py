from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf


# --------------------------------------------------
# 경로
# --------------------------------------------------
UNIVERSE_FILE = Path("config/etf_universe.csv")
OUTPUT_DIR = Path("data/etf_us")
SUMMARY_FILE = OUTPUT_DIR / "_data_summary.csv"

START_DATE = "1990-01-01"


# --------------------------------------------------
# ETF 1개 다운로드
# --------------------------------------------------
def download_etf(ticker):
    print(f"Downloading {ticker} ...")

    df = yf.download(
        ticker,
        start=START_DATE,
        interval="1d",
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=False,
    )

    if df.empty:
        raise RuntimeError(f"{ticker}: 다운로드된 데이터가 없습니다.")

    # yfinance MultiIndex 컬럼 대응
    if isinstance(df.columns, pd.MultiIndex):
        if ticker in df.columns.get_level_values(-1):
            df = df.xs(ticker, axis=1, level=-1)
        else:
            df.columns = [
                x[0] if isinstance(x, tuple) else x
                for x in df.columns
            ]

    df = df.reset_index()

    columns = [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Adj Close",
        "Volume",
    ]

    missing = [x for x in columns if x not in df.columns]

    if missing:
        raise RuntimeError(
            f"{ticker}: 필수 컬럼 누락 {missing}"
        )

    df = df[columns].copy()

    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)

    df = (
        df.sort_values("Date")
        .drop_duplicates("Date", keep="last")
        .reset_index(drop=True)
    )

    return df


# --------------------------------------------------
# 데이터 품질 요약
# --------------------------------------------------
def make_summary(ticker, df):

    price_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Adj Close",
    ]

    return {
        "ticker": ticker,
        "rows": len(df),
        "first_date": df["Date"].min().date(),
        "last_date": df["Date"].max().date(),
        "duplicate_dates": int(
            df["Date"].duplicated().sum()
        ),
        "missing_prices": int(
            df[price_columns].isna().sum().sum()
        ),
        "nonpositive_prices": int(
            (df[price_columns] <= 0).sum().sum()
        ),
        "updated_at_utc":
            datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            ),
    }


# --------------------------------------------------
# 전체 ETF 실행
# --------------------------------------------------
def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    universe = pd.read_csv(UNIVERSE_FILE)

    tickers = (
        universe["ticker"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )

    print(f"Total tickers: {len(tickers)}")

    summary = []
    failed = []

    for ticker in tickers:

        try:

            df = download_etf(ticker)

            output_file = (
                OUTPUT_DIR / f"{ticker}.csv"
            )

            df.to_csv(
                output_file,
                index=False
            )

            summary.append(
                make_summary(ticker, df)
            )

            print(
                f"OK: {ticker} "
                f"{df['Date'].min().date()} "
                f"~ {df['Date'].max().date()} "
                f"({len(df):,} rows)"
            )

        except Exception as e:

            failed.append({
                "ticker": ticker,
                "error": str(e)
            })

            print(
                f"ERROR: {ticker}: {e}"
            )

    # 품질검사 요약 저장
    if summary:

        pd.DataFrame(summary).to_csv(
            SUMMARY_FILE,
            index=False
        )

    # 하나라도 실패하면 GitHub Actions 실패 처리
    if failed:

        print("\nFAILED TICKERS")

        for item in failed:
            print(item)

        raise RuntimeError(
            f"{len(failed)} ticker(s) failed."
        )

    print("\nAll ETF data downloaded successfully.")


if __name__ == "__main__":
    main()
