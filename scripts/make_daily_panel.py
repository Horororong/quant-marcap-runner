from pathlib import Path
import pandas as pd


INPUT_DIR = Path("data/etf_us")
OUTPUT_DIR = Path("data/derived/daily")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_field(field_name):
    series = {}

    for file in sorted(INPUT_DIR.glob("*.csv")):
        if file.name.startswith("_"):
            continue

        ticker = file.stem
        df = pd.read_csv(file, parse_dates=["Date"])

        if field_name not in df.columns:
            raise RuntimeError(f"{ticker}: {field_name} missing")

        s = (
            df[["Date", field_name]]
            .dropna()
            .drop_duplicates("Date")
            .sort_values("Date")
            .set_index("Date")[field_name]
        )

        series[ticker] = s

    panel = pd.DataFrame(series).sort_index()

    return panel


def main():

    adj_close = load_field("Adj Close")
    open_price = load_field("Open")
    close_price = load_field("Close")
    volume = load_field("Volume")

    adj_close.to_csv(
        OUTPUT_DIR / "adj_close_daily.csv"
    )

    open_price.to_csv(
        OUTPUT_DIR / "open_daily.csv"
    )

    close_price.to_csv(
        OUTPUT_DIR / "close_daily.csv"
    )

    volume.to_csv(
        OUTPUT_DIR / "volume_daily.csv"
    )

    # 간단 검증
    print("Daily panels created.")
    print(f"Tickers: {len(adj_close.columns)}")
    print(f"Start: {adj_close.index.min().date()}")
    print(f"End: {adj_close.index.max().date()}")
    print(f"Rows: {len(adj_close):,}")

    print("\nMissing values:")
    print(adj_close.isna().sum().sort_values(ascending=False))


if __name__ == "__main__":
    main()
