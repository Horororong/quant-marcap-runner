from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "permanent_portfolio_long"

DAILY_PATH = RESULTS / "daily_nav.csv"
SUMMARY_PATH = RESULTS / "summary.csv"

CUM_PNG = RESULTS / "cumulative_return.png"
DD_PNG = RESULTS / "drawdown.png"
CHART_DATA_CSV = RESULTS / "chart_monthly.csv"


def main():
    if not DAILY_PATH.exists():
        raise FileNotFoundError(f"Missing file: {DAILY_PATH}")

    df = pd.read_csv(DAILY_PATH)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
    else:
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

    # 1) Cumulative-return PNG based on daily NAV.
    plt.figure(figsize=(12, 6))
    plt.plot(cumulative.index, cumulative.values)
    plt.title("Permanent Portfolio - Cumulative Return")
    plt.xlabel("Date")
    plt.ylabel("Cumulative Return")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(CUM_PNG, dpi=150)
    plt.close()

    # 2) Daily drawdown PNG.
    plt.figure(figsize=(12, 6))
    plt.plot(drawdown.index, drawdown.values)
    plt.title("Permanent Portfolio - Drawdown")
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(DD_PNG, dpi=150)
    plt.close()

    # 3) Compact monthly data for ChatGPT/other front ends.
    #    cumulative_return = last trading-day cumulative return of each month.
    #    drawdown = worst daily drawdown observed inside each month.
    chart = pd.DataFrame(
        {
            "cumulative_return": cumulative.resample("ME").last(),
            "drawdown": drawdown.resample("ME").min(),
        }
    ).dropna(how="all")
    chart.index.name = "Date"
    chart.to_csv(CHART_DATA_CSV, encoding="utf-8-sig")

    print(f"Saved: {CUM_PNG}")
    print(f"Saved: {DD_PNG}")
    print(f"Saved: {CHART_DATA_CSV}")


if __name__ == "__main__":
    main()
