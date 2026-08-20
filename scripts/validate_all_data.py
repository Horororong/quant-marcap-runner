from pathlib import Path
from datetime import datetime, timezone

import pandas as pd


ROOT = Path("data")

US_ETF_DIR = ROOT / "etf_us"
KR_ETF_DIR = ROOT / "etf_kr"
INDEX_DIR = ROOT / "indices"
MACRO_DIR = ROOT / "macro"
STATUS_DIR = ROOT / "status"

UNIVERSE_FILE = Path("config/etf_universe.csv")

REPORT_FILE = STATUS_DIR / "data_validation_report.csv"


# --------------------------------------------------
# 공통 CSV 검사
# --------------------------------------------------
def validate_price_file(path, asset_type, name):
    result = {
        "asset_type": asset_type,
        "name": name,
        "path": str(path),
        "exists": path.exists(),
        "rows": 0,
        "first_date": "",
        "last_date": "",
        "duplicate_dates": "",
        "missing_price_cells": "",
        "nonpositive_price_cells": "",
        "max_abs_daily_return": "",
        "status": "ERROR",
        "error": "",
    }

    if not path.exists():
        result["error"] = "file missing"
        return result

    try:
        df = pd.read_csv(path, parse_dates=["Date"])

        if "Date" not in df.columns:
            raise RuntimeError("Date column missing")

        df = df.sort_values("Date").reset_index(drop=True)

        result["rows"] = len(df)
        result["first_date"] = str(df["Date"].min().date())
        result["last_date"] = str(df["Date"].max().date())
        result["duplicate_dates"] = int(df["Date"].duplicated().sum())

        price_cols = [
            c for c in
            ["Open", "High", "Low", "Close", "Adj Close"]
            if c in df.columns
        ]

        if price_cols:
            result["missing_price_cells"] = int(
                df[price_cols].isna().sum().sum()
            )

            result["nonpositive_price_cells"] = int(
                (df[price_cols] <= 0).sum().sum()
            )

        if "Adj Close" in df.columns:
            ret = df["Adj Close"].pct_change()
        elif "Close" in df.columns:
            ret = df["Close"].pct_change()
        else:
            ret = pd.Series(dtype=float)

        if len(ret.dropna()):
            result["max_abs_daily_return"] = float(
                ret.abs().max()
            )

        result["status"] = "OK"

    except Exception as e:
        result["error"] = repr(e)

    return result


# --------------------------------------------------
# 지수/매크로 파일 검사
# --------------------------------------------------
def validate_generic_file(path, asset_type, name):
    result = {
        "asset_type": asset_type,
        "name": name,
        "path": str(path),
        "exists": path.exists(),
        "rows": 0,
        "first_date": "",
        "last_date": "",
        "duplicate_dates": "",
        "missing_price_cells": "",
        "nonpositive_price_cells": "",
        "max_abs_daily_return": "",
        "status": "ERROR",
        "error": "",
    }

    if not path.exists():
        result["error"] = "file missing"
        return result

    try:
        df = pd.read_csv(path, parse_dates=["Date"])

        result["rows"] = len(df)
        result["first_date"] = str(df["Date"].min().date())
        result["last_date"] = str(df["Date"].max().date())
        result["duplicate_dates"] = int(
            df["Date"].duplicated().sum()
        )

        result["status"] = "OK"

    except Exception as e:
        result["error"] = repr(e)

    return result


def main():
    STATUS_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    # --------------------------------------------------
    # 미국 ETF 28개
    # --------------------------------------------------
    universe = pd.read_csv(UNIVERSE_FILE)

    expected_tickers = (
        universe["ticker"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )

    for ticker in expected_tickers:
        path = US_ETF_DIR / f"{ticker}.csv"

        results.append(
            validate_price_file(
                path,
                "US_ETF",
                ticker
            )
        )

    # --------------------------------------------------
    # 한국 ETF
    # --------------------------------------------------
    results.append(
        validate_price_file(
            KR_ETF_DIR / "069500_KODEX200.csv",
            "KR_ETF",
            "KODEX200"
        )
    )

    # --------------------------------------------------
    # 필수 지수
    # --------------------------------------------------
    required_indices = [
        "KOSPI",
        "KOSDAQ",
        "KOSPI200",
        "SP500",
        "NASDAQ_COMPOSITE",
        "VIX",
    ]

    for name in required_indices:
        results.append(
            validate_generic_file(
                INDEX_DIR / f"{name}.csv",
                "INDEX",
                name
            )
        )

    # --------------------------------------------------
    # 필수 매크로
    # --------------------------------------------------
    required_macro = [
        "US10Y",
        "US2Y",
        "US10Y2Y_SPREAD",
        "FED_FUNDS_EFFECTIVE",
        "US_CPI",
        "US_UNEMPLOYMENT",
        "US_INDUSTRIAL_PRODUCTION",
    ]

    for name in required_macro:
        results.append(
            validate_generic_file(
                MACRO_DIR / f"{name}.csv",
                "MACRO",
                name
            )
        )

    report = pd.DataFrame(results)

    report["validated_at_utc"] = (
        datetime.now(timezone.utc).isoformat()
    )

    report.to_csv(
        REPORT_FILE,
        index=False,
        encoding="utf-8-sig"
    )
    # --------------------------------------------------
    # 핵심 실패 조건
    # --------------------------------------------------
    # 숫자형 검증 컬럼을 안전하게 숫자로 변환
    numeric_check_cols = [
        "duplicate_dates",
        "missing_price_cells",
        "nonpositive_price_cells",
    ]

    for col in numeric_check_cols:
        report[col] = pd.to_numeric(
            report[col],
            errors="coerce"
        ).fillna(0)

    hard_fail = (
        (report["exists"] == False)
        | (report["status"] != "OK")
        | (report["duplicate_dates"] > 0)
        | (report["missing_price_cells"] > 0)
        | (report["nonpositive_price_cells"] > 0)
    )

    failures = report[hard_fail]

    print("\nDATA VALIDATION REPORT")
    print(report.to_string(index=False))
