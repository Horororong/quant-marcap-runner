from __future__ import annotations

from pathlib import Path
from io import StringIO
import json
import urllib.request
import zipfile
import numpy as np
import pandas as pd

from quant_backtest_template_v2_9 import (
    BacktestConfig,
    run_four_periods,
    combine_period_payloads,
    save_chat_payload,
)

AS_OF = pd.Timestamp("2026-09-18")
LATEST_COMPLETE_MONTH = pd.Timestamp("2026-08-31")
INITIAL_CAPITAL = 10_000.0
ASSETS = ["SPY", "TLT", "GLD", "BIL"]
TARGET_WEIGHTS = {k: 0.25 for k in ASSETS}
BASE_COST_BPS = 5.0
COST_SCENARIOS_BPS = (0.0, 5.0, 15.0)

BOOK_START = "1970-01-01"
BOOK_END = "2021-12-31"

OUT = Path("results/permanent_portfolio_v29")
OUT.mkdir(parents=True, exist_ok=True)

POFO = {
    "SPY": "https://raw.githubusercontent.com/bpineau/pofo/master/pkg/datasets/simdata/SP500.csv",
    "TLT": "https://raw.githubusercontent.com/bpineau/pofo/master/pkg/datasets/simdata/TLT.csv",
    "GLD": "https://raw.githubusercontent.com/bpineau/pofo/master/pkg/datasets/simdata/XAUUSD.csv",
}
FF_DAILY_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip"


def load_proxy(url: str, name: str) -> pd.Series:
    df = pd.read_csv(url, comment="#")
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    s = (
        df.dropna(subset=["date", "close"])
        .drop_duplicates("date")
        .set_index("date")["close"]
        .sort_index()
        .rename(name)
    )
    if s.empty:
        raise RuntimeError(f"{name}: proxy data is empty")
    return s


def load_actual(path: str, name: str) -> pd.Series:
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"])
    col = "Adj Close" if "Adj Close" in df.columns else "Close"
    df[col] = pd.to_numeric(df[col], errors="coerce")
    s = (
        df.dropna(subset=["Date", col])
        .drop_duplicates("Date")
        .set_index("Date")[col]
        .sort_index()
        .rename(name)
    )
    if s.empty:
        raise RuntimeError(f"{name}: actual ETF data is empty")
    return s


def load_ff_daily_cash_proxy() -> pd.Series:
    """Build a daily cash total-return index from Kenneth French daily RF."""
    with urllib.request.urlopen(FF_DAILY_URL, timeout=60) as resp:
        raw_zip = resp.read()

    import io
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as zf:
        names = zf.namelist()
        csv_name = next(n for n in names if n.lower().endswith(".csv"))
        lines = zf.read(csv_name).decode("latin-1").splitlines()

    header_i = None
    for i, line in enumerate(lines):
        if "Mkt-RF" in line and "RF" in line:
            header_i = i
            break
    if header_i is None:
        raise RuntimeError("Kenneth French daily RF header not found")

    data_lines = [lines[header_i]]
    for line in lines[header_i + 1:]:
        if not line.strip():
            break
        first = line.split(",", 1)[0].strip()
        if not (first.isdigit() and len(first) == 8):
            break
        data_lines.append(line)

    df = pd.read_csv(StringIO("\n".join(data_lines)))
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col].astype(str).str.strip(), format="%Y%m%d")
    df["RF"] = pd.to_numeric(df["RF"], errors="coerce") / 100.0
    df = df.dropna(subset=[date_col, "RF"]).set_index(date_col).sort_index()

    level = (1.0 + df["RF"]).cumprod()
    level.name = "BIL_proxy"
    return level


def stitch_proxy_to_actual(proxy: pd.Series, actual: pd.Series, end: pd.Timestamp) -> pd.Series:
    start = min(proxy.index.min(), actual.index.min())
    idx = pd.bdate_range(start, end)
    p = proxy.reindex(idx).ffill()
    a = actual.reindex(idx).ffill()

    first = actual.index.min()
    first = idx[idx >= first][0]
    if pd.isna(p.loc[first]) or pd.isna(a.loc[first]):
        raise RuntimeError(f"splice failure for {actual.name} at {first.date()}")

    scale = float(p.loc[first]) / float(a.loc[first])
    out = p.copy()
    out.loc[first:] = a.loc[first:] * scale
    return out.loc[:end]


def build_asset_levels() -> tuple[pd.DataFrame, dict[str, str]]:
    actual = {k: load_actual(f"data/etf_us/{k}.csv", k) for k in ASSETS}

    proxies = {
        "SPY": load_proxy(POFO["SPY"], "SPY_proxy"),
        "TLT": load_proxy(POFO["TLT"], "TLT_proxy"),
        "GLD": load_proxy(POFO["GLD"], "GLD_proxy"),
        "BIL": load_ff_daily_cash_proxy(),
    }

    stitched = {}
    for k in ASSETS:
        stitched[k] = stitch_proxy_to_actual(proxies[k], actual[k], LATEST_COMPLETE_MONTH).rename(k)

    levels = pd.concat(stitched.values(), axis=1).dropna()
    levels = levels.loc[:LATEST_COMPLETE_MONTH]

    if levels.index[-1] < LATEST_COMPLETE_MONTH:
        raise RuntimeError(
            f"asset data ends too early: {levels.index[-1].date()} < {LATEST_COMPLETE_MONTH.date()}"
        )

    starts = {k: actual[k].index.min().date().isoformat() for k in ASSETS}
    return levels, starts


def simulate_annual_equal_weight(levels: pd.DataFrame, cost_bps: float) -> tuple[pd.Series, pd.DataFrame]:
    ret = levels.pct_change().fillna(0.0)

    values = {k: TARGET_WEIGHTS[k] for k in ASSETS}
    nav_rows: list[tuple[pd.Timestamp, float]] = []
    trade_rows: list[dict] = []
    prev_year = levels.index[0].year

    for i, (dt, row) in enumerate(ret.iterrows()):
        if i > 0 and dt.year != prev_year:
            pre_nav = sum(values.values())
            targets = {k: pre_nav * TARGET_WEIGHTS[k] for k in ASSETS}
            gross_notional = sum(abs(targets[k] - values[k]) for k in ASSETS)
            cost = gross_notional * cost_bps / 10_000.0
            post_nav = pre_nav - cost
            values = {k: post_nav * TARGET_WEIGHTS[k] for k in ASSETS}
            trade_rows.append(
                {
                    "Date": dt,
                    "GrossTurnover": gross_notional / pre_nav if pre_nav > 0 else np.nan,
                    "CostNAV": cost,
                }
            )
            prev_year = dt.year

        if i > 0:
            for k in ASSETS:
                values[k] *= 1.0 + float(row[k])

        nav_rows.append((dt, sum(values.values())))

    nav = pd.Series(dict(nav_rows), dtype=float).sort_index()
    nav /= float(nav.iloc[0])
    return nav, pd.DataFrame(trade_rows)


def stock_benchmark(levels: pd.DataFrame) -> pd.Series:
    s = levels["SPY"].astype(float)
    return (s / float(s.iloc[0])).rename("S&P500 100%")


def month_end_nav(daily: pd.DataFrame) -> pd.DataFrame:
    m = daily.groupby(daily.index.to_period("M")).tail(1).copy()
    m.index = m.index.to_period("M").to_timestamp("M")
    return m.loc[:LATEST_COMPLETE_MONTH]


def flatten_four_period_results(results: dict) -> pd.DataFrame:
    rows = []
    for period_key, result in results.items():
        metrics = result["metrics"].copy().reset_index()
        metrics.insert(0, "Period", period_key)
        metrics.insert(1, "PeriodLabel", result["label"])
        metrics.insert(2, "Start", result["start"].strftime("%Y-%m-%d"))
        metrics.insert(3, "End", result["end"].strftime("%Y-%m-%d"))
        rows.append(metrics)
    return pd.concat(rows, ignore_index=True)


def build_selectable_dashboard(results: dict) -> None:
    def period_data(period_key: str) -> dict:
        r = results[period_key]
        m = r["monthly_nav"][["영구포트폴리오 비용후(5bp)", "S&P500 100%"]].copy()
        d = r["daily_nav"][["영구포트폴리오 비용후(5bp)", "S&P500 100%"]].copy()
        dd = d / d.cummax() - 1.0

        monthly = []
        for dt, row in m.iterrows():
            net = float(row["영구포트폴리오 비용후(5bp)"])
            sp = float(row["S&P500 100%"])
            monthly.append({
                "date": dt.strftime("%Y-%m-%d"),
                "net": net,
                "sp": sp,
                "net_log2": float(np.log2(net)),
                "sp_log2": float(np.log2(sp)),
                "net_asset": net * INITIAL_CAPITAL,
                "sp_asset": sp * INITIAL_CAPITAL,
            })

        drawdown = [{
            "date": dt.strftime("%Y-%m-%d"),
            "net_dd": float(row["영구포트폴리오 비용후(5bp)"] * 100.0),
            "sp_dd": float(row["S&P500 100%"] * 100.0),
        } for dt, row in dd.iterrows()]

        metric = r["metrics"]
        def met(name: str) -> dict:
            return {
                "CAGR": float(metric.loc[name, "CAGR"] * 100),
                "MDD": float(metric.loc[name, "MDD"] * 100),
                "Sharpe": float(metric.loc[name, "Sharpe"]),
                "Vol": float(metric.loc[name, "연환산_표준편차"] * 100),
                "Recovery": float(metric.loc[name, "최대회복기간_개월"]),
                "Final": float(metric.loc[name, "최종자산"]),
            }

        return {
            "label": r["label"],
            "monthly": monthly,
            "drawdown": drawdown,
            "metrics": {
                "net": met("영구포트폴리오 비용후(5bp)"),
                "sp": met("S&P500 100%"),
            },
        }

    data = {
        "longest": period_data("longest"),
        "from_2001": period_data("from_2001"),
        "from_2021": period_data("from_2021"),
    }
    (OUT / "interactive_dashboard_data.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )

    from plotly.offline import get_plotlyjs
    plotly_js = get_plotlyjs()
    data_json = json.dumps(data, ensure_ascii=False)

    html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>영구 포트폴리오 백테스트</title>
<style>
body{{font-family:"Noto Sans KR","Malgun Gothic",sans-serif;margin:0;background:#f4f6f8;color:#111}}
.wrap{{max-width:1280px;margin:auto;padding:20px}} .toolbar{{display:flex;gap:12px;align-items:center;flex-wrap:wrap}}
select{{font:inherit;padding:10px 14px;border-radius:10px;border:1px solid #bbb;background:white}}
.cards{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:14px 0}}
.card,.chart{{background:white;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,.08)}} .card{{padding:14px 16px}}
.metrics{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;font-size:13px}} .metric b{{display:block;font-size:16px;margin-top:2px}}
.chart{{height:430px;margin:12px 0}} .note{{font-size:12px;color:#666;margin-top:8px}}
@media(max-width:800px){{.cards{{grid-template-columns:1fr}}.metrics{{grid-template-columns:repeat(2,minmax(0,1fr))}}.chart{{height:360px}}}}
</style>
<script>{plotly_js}</script>
</head>
<body><div class="wrap">
<div class="toolbar"><strong>3번 영구 포트폴리오</strong><label for="period">분석기간</label>
<select id="period"><option value="longest">최장~현재</option><option value="from_2001" selected>2001~현재</option><option value="from_2021">2021~현재</option></select></div>
<div id="periodLabel" class="note"></div>
<div class="cards"><div class="card"><h3>영구포트폴리오 비용후(5bp)</h3><div id="netMetrics" class="metrics"></div></div>
<div class="card"><h3>S&P500 100%</h3><div id="spMetrics" class="metrics"></div></div></div>
<div id="cumChart" class="chart"></div><div id="logChart" class="chart"></div><div id="ddChart" class="chart"></div>
<div class="note">SPY/TLT/GLD/BIL 25%씩, 연 1회 리밸런싱. 누적자산·Log2는 월별 NAV, Drawdown은 일별 NAV. 초기자산 $10,000.</div>
</div>
<script>
const DATA={data_json}; const cfg={{responsive:true,displaylogo:false,scrollZoom:true}};
function fmt(v,d=2){{return Number(v).toLocaleString('ko-KR',{{minimumFractionDigits:d,maximumFractionDigits:d}})}}
function metricHTML(m){{return [['CAGR',fmt(m.CAGR)+'%'],['MDD',fmt(m.MDD)+'%'],['Sharpe',fmt(m.Sharpe)],['변동성',fmt(m.Vol)+'%'],['회복기간',fmt(m.Recovery,1)+'개월']].map(x=>'<div class="metric">'+x[0]+'<b>'+x[1]+'</b></div>').join('')}}
function render(key){{
 const p=DATA[key],m=p.monthly,d=p.drawdown,x=m.map(r=>r.date);
 document.getElementById('periodLabel').textContent=p.label;
 document.getElementById('netMetrics').innerHTML=metricHTML(p.metrics.net); document.getElementById('spMetrics').innerHTML=metricHTML(p.metrics.sp);
 Plotly.react('cumChart',[{{x,y:m.map(r=>r.net),name:'영구포트폴리오 비용후(5bp)',mode:'lines',customdata:m.map(r=>r.net_asset),hovertemplate:'%{{x}}<br>%{{y:.3f}}배<br>$%{{customdata:,.0f}}<extra></extra>'}},{{x,y:m.map(r=>r.sp),name:'S&P500 100%',mode:'lines',customdata:m.map(r=>r.sp_asset),hovertemplate:'%{{x}}<br>%{{y:.3f}}배<br>$%{{customdata:,.0f}}<extra></extra>'}}],{{title:'① 누적자산',yaxis:{{title:'배수'}},xaxis:{{rangeslider:{{visible:true}}}},hovermode:'x unified'}},cfg);
 const vals=m.flatMap(r=>[r.net_log2,r.sp_log2]); const mi=Math.min(0,Math.floor(Math.min(...vals))),ma=Math.max(1,Math.ceil(Math.max(...vals))); const tv=[],tt=[]; for(let i=mi;i<=ma;i++){{tv.push(i);tt.push((2**i).toLocaleString('ko-KR',{{maximumFractionDigits:3}})+'배')}}
 Plotly.react('logChart',[{{x,y:m.map(r=>r.net_log2),name:'영구포트폴리오 비용후(5bp)',mode:'lines'}},{{x,y:m.map(r=>r.sp_log2),name:'S&P500 100%',mode:'lines'}}],{{title:'② Log2 누적자산',yaxis:{{title:'누적자산 배수',tickmode:'array',tickvals:tv,ticktext:tt}},xaxis:{{rangeslider:{{visible:true}}}},hovermode:'x unified'}},cfg);
 const xd=d.map(r=>r.date); Plotly.react('ddChart',[{{x:xd,y:d.map(r=>r.net_dd),name:'영구포트폴리오 비용후(5bp)',mode:'lines'}},{{x:xd,y:d.map(r=>r.sp_dd),name:'S&P500 100%',mode:'lines'}}],{{title:'③ Drawdown (일별)',yaxis:{{title:'Drawdown (%)',rangemode:'tozero'}},xaxis:{{rangeslider:{{visible:true}}}},hovermode:'x unified'}},cfg);
}}
document.getElementById('period').addEventListener('change',e=>render(e.target.value)); render('from_2001');
</script></body></html>"""
    (OUT / "interactive_dashboard.html").write_text(html, encoding="utf-8")


def main() -> None:
    levels, actual_starts = build_asset_levels()

    gross, trades_gross = simulate_annual_equal_weight(levels, 0.0)
    net5, trades5 = simulate_annual_equal_weight(levels, BASE_COST_BPS)
    benchmark = stock_benchmark(levels)

    daily_nav = pd.concat([
        gross.rename("영구포트폴리오 비용전"),
        net5.rename("영구포트폴리오 비용후(5bp)"),
        benchmark,
    ], axis=1).dropna()
    monthly_nav = month_end_nav(daily_nav)

    config = BacktestConfig(
        title="거인의 포트폴리오 3번 - 영구 포트폴리오",
        initial_capital=INITIAL_CAPITAL,
        periods_per_year=12,
        risk_free_rate=0.0,
        book_start=BOOK_START,
        book_end=BOOK_END,
        standard_end_year=2026,
        as_of_date=str(AS_OF.date()),
    )

    results = run_four_periods(monthly_nav, config, daily_nav)
    summary = flatten_four_period_results(results)
    summary.to_csv(OUT / "summary_four_periods_template.csv", index=False, encoding="utf-8-sig")

    combined = combine_period_payloads(
        *[results[k]["chat_payload"] for k in ["book_validation", "from_2001", "from_2021", "longest"]]
    )
    save_chat_payload(combined, str(OUT / "chat_payload_four_periods.json"))
    build_selectable_dashboard(results)

    daily_nav.to_csv(OUT / "daily_nav_full.csv.gz", compression="gzip")
    monthly_nav.to_csv(OUT / "monthly_nav_full.csv", encoding="utf-8-sig")

    sensitivity = []
    for bps in COST_SCENARIOS_BPS:
        nav, trades = simulate_annual_equal_weight(levels, bps)
        d = pd.DataFrame({f"Permanent_{bps:g}bp": nav})
        m = month_end_nav(d)
        rr = run_four_periods(m, config, d)
        for period_key, result in rr.items():
            x = result["metrics"].iloc[0]
            p0, p1 = pd.Timestamp(result["start"]), pd.Timestamp(result["end"])
            tt = trades[(trades["Date"] >= p0) & (trades["Date"] <= p1)] if len(trades) else trades
            sensitivity.append({
                "Period": period_key, "Cost_bps": bps,
                "CAGR": x["CAGR"], "MDD": x["MDD"], "Sharpe": x["Sharpe"],
                "Annualized_Std": x["연환산_표준편차"],
                "Max_Recovery_Months": x["최대회복기간_개월"],
                "Final_Asset_USD": x["최종자산"], "MDD_Source": x["MDD_source"],
                "Avg_Annual_Gross_Turnover": float(tt["GrossTurnover"].mean()) if len(tt) else 0.0,
            })
    pd.DataFrame(sensitivity).to_csv(OUT / "cost_sensitivity_template.csv", index=False, encoding="utf-8-sig")

    bm = results["book_validation"]["metrics"].loc["영구포트폴리오 비용전"]
    book_compare = pd.DataFrame([
        {"Metric":"Final_Asset_USD","Book":762_000.0,"Template_Backtest":float(bm["최종자산"])},
        {"Metric":"CAGR","Book":0.088,"Template_Backtest":float(bm["CAGR"])},
        {"Metric":"MDD","Book":-0.127,"Template_Backtest":float(bm["MDD"])},
        {"Metric":"Sharpe","Book":0.57,"Template_Backtest":float(bm["Sharpe"])},
    ])
    book_compare.to_csv(OUT / "book_verification_template.csv", index=False, encoding="utf-8-sig")

    # Actual-ETF-only robustness from common inception.
    actual_levels = pd.concat(
        [load_actual(f"data/etf_us/{k}.csv", k) for k in ASSETS],
        axis=1, join="inner"
    ).dropna().loc[:LATEST_COMPLETE_MONTH]
    actual_nav, _ = simulate_annual_equal_weight(actual_levels, 0.0)
    hybrid_same, _ = simulate_annual_equal_weight(levels.reindex(actual_levels.index).ffill().dropna(), 0.0)
    ov = pd.DataFrame({"Actual_all4":actual_nav,"Hybrid_same_dates":hybrid_same}).dropna()
    ovret = ov.pct_change().dropna()
    overlap = {
        "start": ov.index[0].date().isoformat(),
        "end": ov.index[-1].date().isoformat(),
        "max_abs_daily_return_diff": float((ovret["Actual_all4"]-ovret["Hybrid_same_dates"]).abs().max()),
        "final_multiple_actual": float(ov["Actual_all4"].iloc[-1]/ov["Actual_all4"].iloc[0]),
        "final_multiple_hybrid": float(ov["Hybrid_same_dates"].iloc[-1]/ov["Hybrid_same_dates"].iloc[0]),
    }
    (OUT / "actual_etf_overlap_check.json").write_text(json.dumps(overlap, ensure_ascii=False, indent=2), encoding="utf-8")

    metadata = {
        "as_of": AS_OF.date().isoformat(),
        "latest_complete_month": LATEST_COMPLETE_MONTH.date().isoformat(),
        "strategy": "SPY/TLT/GLD/BIL 25% each, annual rebalance",
        "book_validation": "1970-01 through 2021-12",
        "initial_capital_usd": INITIAL_CAPITAL,
        "risk_free_rate_for_template_sharpe": 0.0,
        "base_cost_bps_on_gross_rebalance_notional": BASE_COST_BPS,
        "initial_deployment_cost_included": False,
        "taxes_included": False,
        "execution_assumption": "rebalance at calendar-year turn before first business-day close-to-close return",
        "actual_etf_inception": actual_starts,
        "pre_inception_proxies": {
            "SPY": "pofo SP500 total-return reconstruction",
            "TLT": "pofo TLT long-Treasury reconstruction",
            "GLD": "pofo XAUUSD/LBMA gold spot reconstruction",
            "BIL": "Kenneth French daily RF cumulative cash return",
        },
        "proxy_sources": [*POFO.values(), FF_DAILY_URL],
        "actual_sources": [f"data/etf_us/{k}.csv" for k in ASSETS],
        "standard_template": "scripts/quant_backtest_template_v2_9.py",
        "notes": [
            "Pre-ETF history is reconstructed proxy history and is not directly executable ETF history.",
            "Gold pre-GLD history is spot gold, while actual GLD includes fund expenses.",
            "BIL pre-inception history uses Kenneth French daily risk-free return as a cash proxy.",
            "Book Sharpe methodology is not stated; template Sharpe uses monthly returns with rf=0.",
        ],
    }
    (OUT / "run_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(summary.to_string(index=False))
    print("\nPERIOD SELECTOR:", combined["period_selector"])
    print("\nBOOK COMPARISON")
    print(book_compare.to_string(index=False))
    print("\nACTUAL-ETF OVERLAP")
    print(json.dumps(overlap, indent=2))


if __name__ == "__main__":
    main()
