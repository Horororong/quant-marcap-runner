from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "permanent_portfolio_long"

DAILY_PATH = RESULTS / "daily_nav.csv"
SUMMARY_PATH = RESULTS / "summary.csv"

CUM_PNG = RESULTS / "cumulative_return.png"
DD_PNG = RESULTS / "drawdown.png"


def main():
    if not DAILY_PATH.exists():
        raise FileNotFoundError(f"Missing file: {DAILY_PATH}")

    df = pd.read_csv(DAILY_PATH)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
    else:
        # 혹시 인덱스가 unnamed로 저장된 경우 대응
        first_col = df.columns[0]
        df[first_col] = pd.to_datetime(df[first_col])
        df = df.set_index(first_col)

    if "NAV" not in df.columns or "Drawdown" not in df.columns:
        raise RuntimeError("daily_nav.csv must contain NAV and Drawdown columns")

    nav = pd.to_numeric(df["NAV"], errors="coerce").dropna()
    drawdown = pd.to_numeric(df["Drawdown"], errors="coerce").reindex(nav.index)

    if nav.empty:
        raise RuntimeError("NAV series is empty")

    cumulative = nav / nav.iloc[0] - 1.0

    # 1) 누적수익률 그래프
    plt.figure(figsize=(12, 6))
    plt.plot(cumulative.index, cumulative.values)
    plt.title("Permanent Portfolio - Cumulative Return")
    plt.xlabel("Date")
    plt.ylabel("Cumulative Return")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(CUM_PNG, dpi=150)
    plt.close()

    # 2) 낙폭 그래프
    plt.figure(figsize=(12, 6))
    plt.plot(drawdown.index, drawdown.values)
    plt.title("Permanent Portfolio - Drawdown")
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(DD_PNG, dpi=150)
    plt.close()

    print(f"Saved: {CUM_PNG}")
    print(f"Saved: {DD_PNG}")


if __name__ == "__main__":
    main()
