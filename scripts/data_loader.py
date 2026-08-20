from pathlib import Path
import pandas as pd


ROOT = Path("data")

PATHS = {
    "etf_us": ROOT / "etf_us",
    "etf_kr": ROOT / "etf_kr",
    "indices": ROOT / "indices",
    "macro": ROOT / "macro",
    "fx": ROOT / "fx",
    "derived_daily": ROOT / "derived" / "daily",
}


def load_csv(path):
    df = pd.read_csv(path, parse_dates=["Date"])
    return (
        df.sort_values("Date")
        .drop_duplicates("Date", keep="last")
        .reset_index(drop=True)
    )


def load_us_etf(ticker):
    path = PATHS["etf_us"] / f"{ticker}.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    return load_csv(path)


def load_kr_etf(code, name=None):
    if name:
        path = PATHS["etf_kr"] / f"{code}_{name}.csv"
    else:
        matches = list(PATHS["etf_kr"].glob(f"{code}_*.csv"))
        if len(matches) != 1:
            raise FileNotFoundError(
                f"{code}: expected one file, found {len(matches)}"
            )
        path = matches[0]

    return load_csv(path)


def load_index(name):
    path = PATHS["indices"] / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    return load_csv(path)


def load_macro(name):
    path = PATHS["macro"] / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    return load_csv(path)


def load_fx(name="USDKRW"):
    path = PATHS["fx"] / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    return load_csv(path)


def load_daily_panel(field="adj_close"):
    file_map = {
        "adj_close": "adj_close_daily.csv",
        "open": "open_daily.csv",
        "close": "close_daily.csv",
        "volume": "volume_daily.csv",
    }

    if field not in file_map:
        raise ValueError(
            f"field must be one of {list(file_map.keys())}"
        )

    path = PATHS["derived_daily"] / file_map[field]

    if not path.exists():
        raise FileNotFoundError(path)

    return (
        pd.read_csv(path, parse_dates=["Date"])
        .sort_values("Date")
        .drop_duplicates("Date", keep="last")
        .reset_index(drop=True)
    )


if __name__ == "__main__":

    print("SPY")
    print(load_us_etf("SPY").tail())

    print("\nKODEX200")
    print(load_kr_etf("069500").tail())

    print("\nKOSPI")
    print(load_index("KOSPI").tail())

    print("\nUS unemployment")
    print(load_macro("US_UNEMPLOYMENT").tail())

    print("\nUSD/KRW")
    print(load_fx().tail())
