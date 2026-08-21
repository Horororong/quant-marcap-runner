from pathlib import Path
import math

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "permanent_portfolio_long"

DAILY_PATH = RESULTS / "daily_nav.csv"

CUM_PNG = RESULTS / "cumulative_return.png"
DD_PNG = RESULTS / "drawdown.png"
MONTHLY_CHART_CSV = RESULTS / "chart_monthly.csv"


def find_nav_column(df: pd.DataFrame) -> str:
    candidates = ["NAV", "nav", "PortfolioValue", "portfolio_value", "value"]
    for col in candidates:
        if col in df.columns:
            return col

    # 숫자형 컬럼 중 첫 번째를 fallback
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        return numeric_cols[0]

    raise RuntimeError("NAV column not found in daily_nav.csv")


def find_date_column(df: pd.DataFrame) -> str:
    candidates = ["Date", "date"]
    for col in candidates:
        if col in df.columns:
            return col

    # 첫 번째 컬럼을 날짜로 시도
    return df.columns[0]


def make_log2_ticks(max_multiple: float):
    if max_multiple <= 1:
        return [1]

    max_pow = int(math.ceil(math.log(max_multiple, 2)))
    ticks = [2 ** i for i in range(0, max_pow + 1)]

    if ticks[0] != 1:
        ticks = [1] + ticks

    return ticks


def main():
    if not DAILY_PATH.exists():
        raise FileNotFoundError(f"Missing file: {DAILY_PATH}")

    df = pd.read_csv(DAILY_PATH)

    date_col = find_date_column(df)
    nav_col = find_nav_column(df)

    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col).drop_duplicates(date_col).reset_index(drop=True)

    df = df[[date_col, nav_col]].copy()
    df.columns = ["Date", "NAV"]

    df["NAV"] = pd.to_numeric(df["NAV"], errors="coerce")
    df = df.dropna(subset=["NAV"]).copy()

    if df.empty:
        raise RuntimeError("No valid NAV data found")

    initial_capital = float(df["NAV"].iloc[0])

    if initial_capital <= 0:
        raise RuntimeError("Initial NAV must be positive")

    # 자산배수
    df["WealthMultiple"] = df["NAV"] / initial_capital

    # Drawdown 계산
    df["RollingMax"] = df["NAV"].cummax()
    df["Drawdown"] = df["NAV"] / df["RollingMax"] - 1.0

    # 월말 시각화용 CSV 생성
    monthly = (
        df.set_index("Date")[["WealthMultiple", "Drawdown"]]
        .resample("ME")
        .agg(
            {
                "WealthMultiple": "last",
                "Drawdown": "min",   # 해당 월의 최악 낙폭
            }
        )
        .dropna()
        .reset_index()
    )

    monthly.to_csv(MONTHLY_CHART_CSV, index=False, encoding="utf-8-sig")

    # -----------------------------
    # 1) 누적자산 그래프 (log2 배수축)
    # -----------------------------
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df["Date"], df["WealthMultiple"], linewidth=1.6)

    ax.set_yscale("log", base=2)

    max_multiple = float(df["WealthMultiple"].max())
    tick_vals = make_log2_ticks(max_multiple)

    ax.set_yticks(tick_vals)
    ax.set_yticklabels([f"{int(x)}x" if x >= 1 else f"{x:.2f}x" for x in tick_vals])

    ax.set_title("Permanent Portfolio - Cumulative Wealth (Log2 Scale)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Wealth Multiple")
    ax.grid(True, which="both", linestyle="--", alpha=0.35)

    plt.tight_layout()
    plt.savefig(CUM_PNG, dpi=150)
    plt.close()

    # -----------------------------
    # 2) 낙폭 그래프
    # -----------------------------
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df["Date"], df["Drawdown"] * 100, linewidth=1.6)

    ax.set_title("Permanent Portfolio - Drawdown")
    ax.set_xlabel("Date")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, linestyle="--", alpha=0.35)

    plt.tight_layout()
    plt.savefig(DD_PNG, dpi=150)
    plt.close()

    print(f"Saved: {CUM_PNG}")
    print(f"Saved: {DD_PNG}")
    print(f"Saved: {MONTHLY_CHART_CSV}")


if __name__ == "__main__":
    main()
