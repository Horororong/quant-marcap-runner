from pathlib import Path
import math

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "permanent_portfolio_long"

DAILY_PATH = RESULTS / "daily_nav.csv"

CUM_PNG = RESULTS / "cumulative_return.png"
DD_PNG = RESULTS / "drawdown.png"
MONTHLY_CHART_CSV = RESULTS / "chart_monthly.csv"


def setup_korean_font():
    preferred_fonts = [
        "Noto Sans CJK KR",
        "Noto Sans KR",
        "NanumGothic",
        "Malgun Gothic",
        "AppleGothic",
    ]

    available = {f.name for f in fm.fontManager.ttflist}

    for font_name in preferred_fonts:
        if font_name in available:
            plt.rcParams["font.family"] = font_name
            break

    plt.rcParams["axes.unicode_minus"] = False


def find_nav_column(df: pd.DataFrame) -> str:
    candidates = ["NAV", "nav", "PortfolioValue", "portfolio_value", "value"]
    for col in candidates:
        if col in df.columns:
            return col

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        return numeric_cols[0]

    raise RuntimeError("daily_nav.csv에서 NAV 컬럼을 찾지 못했습니다.")


def find_date_column(df: pd.DataFrame) -> str:
    candidates = ["Date", "date"]
    for col in candidates:
        if col in df.columns:
            return col

    return df.columns[0]


def make_log2_ticks(max_multiple: float):
    if max_multiple <= 1:
        return [1]

    max_pow = int(math.ceil(math.log(max_multiple, 2)))
    return [2 ** i for i in range(0, max_pow + 1)]


def main():
    setup_korean_font()

    if not DAILY_PATH.exists():
        raise FileNotFoundError(f"파일이 없습니다: {DAILY_PATH}")

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
        raise RuntimeError("유효한 NAV 데이터가 없습니다.")

    initial_capital = float(df["NAV"].iloc[0])

    if initial_capital <= 0:
        raise RuntimeError("초기 NAV는 0보다 커야 합니다.")

    df["WealthMultiple"] = df["NAV"] / initial_capital

    df["RollingMax"] = df["NAV"].cummax()
    df["Drawdown"] = df["NAV"] / df["RollingMax"] - 1.0

    monthly = (
        df.set_index("Date")[["WealthMultiple", "Drawdown"]]
        .resample("ME")
        .agg(
            {
                "WealthMultiple": "last",
                "Drawdown": "min",
            }
        )
        .dropna()
        .reset_index()
    )

    monthly.to_csv(MONTHLY_CHART_CSV, index=False, encoding="utf-8-sig")

    # 누적 자산 그래프: 1배, 2배, 4배, 8배 ... log2 축
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df["Date"], df["WealthMultiple"], linewidth=1.6)

    ax.set_yscale("log", base=2)

    max_multiple = float(df["WealthMultiple"].max())
    tick_vals = make_log2_ticks(max_multiple)

    ax.set_yticks(tick_vals)
    ax.set_yticklabels([f"{int(x)}배" for x in tick_vals])

    ax.set_title("영구 포트폴리오 누적 자산", fontsize=15)
    ax.set_xlabel("연도")
    ax.set_ylabel("초기자산 대비 배수")
    ax.grid(True, which="both", linestyle="--", alpha=0.35)

    plt.tight_layout()
    plt.savefig(CUM_PNG, dpi=150)
    plt.close()

    # 일별 낙폭 그래프
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df["Date"], df["Drawdown"] * 100, linewidth=1.6)

    ax.set_title("영구 포트폴리오 낙폭", fontsize=15)
    ax.set_xlabel("연도")
    ax.set_ylabel("낙폭 (%)")
    ax.grid(True, linestyle="--", alpha=0.35)

    plt.tight_layout()
    plt.savefig(DD_PNG, dpi=150)
    plt.close()

    print(f"저장 완료: {CUM_PNG}")
    print(f"저장 완료: {DD_PNG}")
    print(f"저장 완료: {MONTHLY_CHART_CSV}")


if __name__ == "__main__":
    main()
