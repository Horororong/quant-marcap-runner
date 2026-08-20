from pathlib import Path
import pandas as pd
import yfinance as yf

OUTPUT_DIR = Path("data/etf_kr")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TICKERS = {
    "069500.KS": "KODEX200"
}

def main():
    for yahoo_ticker, name in TICKERS.items():

        print(f"Downloading {name} ({yahoo_ticker}) ...")

        df = yf.download(
            yahoo_ticker,
            start="2000-01-01",
            interval="1d",
            auto_adjust=False,
            progress=False,
            actions=False,
            threads=False,
        )

        if df.empty:
            raise RuntimeError(f"{name}: no data")

        if isinstance(df.columns, pd.MultiIndex):
            if yahoo_ticker in df.columns.get_level_values(-1):
                df = df.xs(yahoo_ticker, axis=1, level=-1)
            else:
                df.columns = [
                    c[0] if isinstance(c, tuple) else c
                    for c in df.columns
                ]

        df = df.reset_index()

        cols = [
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
            "Adj Close",
            "Volume",
        ]

        missing = [c for c in cols if c not in df.columns]
        if missing:
            raise RuntimeError(f"{name}: missing {missing}")

        df = df[cols].copy()

        df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)

        df = (
            df.sort_values("Date")
            .drop_duplicates("Date", keep="last")
            .reset_index(drop=True)
        )

        out = OUTPUT_DIR / f"069500_{name}.csv"
        df.to_csv(out, index=False)

        print(
            f"OK: {name} "
            f"{df['Date'].min().date()} "
            f"~ {df['Date'].max().date()} "
            f"({len(df):,} rows)"
        )

if __name__ == "__main__":
    main()
