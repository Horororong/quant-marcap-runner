from __future__ import annotations

from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

from quant_backtest_template_v2_9 import (
    BacktestConfig,
    combine_period_payloads,
    run_four_periods,
    save_chat_payload,
)

AS_OF = pd.Timestamp("2026-09-18")
LATEST_COMPLETE_MONTH = pd.Timestamp("2026-08-31")
INITIAL_CAPITAL = 10_000.0
TARGET = np.array([0.25, 0.25, 0.25, 0.25], dtype=float)
BASE_COST_BPS = 5.0
COST_SCENARIOS_BPS = (0.0, 5.0, 15.0)
BOOK_START = "1970-01-01"
BOOK_END = "2021-12-31"

OUT = Path("results/permanent_template_v29")
OUT.mkdir(parents=True, exist_ok=True)

POFO_BASE = "https://raw.githubusercontent.com/bpineau/pofo/master/pkg/datasets"
PROXY_URLS = {
    "Stock": f"{POFO_BASE}/simdata/SP500.csv",
    "LongTreasury": f"{POFO_BASE}/simdata/TLT.csv",
    "Gold": f"{POFO_BASE}/simdata/XAUUSD.csv",
}
TBILL_URL = f"{POFO_BASE}/refdata/TBILL-3M.csv"
ACTUAL_FILES = {
    "Stock": "data/etf_us/SPY.csv",
    "LongTreasury": "data/etf_us/TLT.csv",
    "Gold": "data/etf_us/GLD.csv",
    "Cash": "data/etf_us/BIL.csv",
}


def load_proxy(url: str, name: str) -> pd.Series:
    df = pd.read_csv(url, comment="#")
    if not {"date", "close"}.issubset(df.columns):
        raise RuntimeError(f"{name}: proxy columns missing: {list(df.columns)}")
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    s = (
        df.dropna(subset=["date", "close"])
        .drop_duplicates("date")
        .set_index("date")["close"]
        .sort_index()
        .rename(name)
    )
    if s.empty or (s <= 0).any():
        raise RuntimeError(f"{name}: invalid proxy data")
    return s


def load_tbill_rate(url: str) -> pd.Series:
    # pofo refdata/TBILL-3M.csv: comment lines + headerless date,rate rows.
    df = pd.read_csv(url, comment="#", header=None, names=["date", "rate"])
    df["date"] = pd.to_datetime(df["date"])
    df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
    s = (
        df.dropna(subset=["date", "rate"])
        .drop_duplicates("date")
        .set_index("date")["rate"]
        .sort_index()
    )
    if s.empty:
        raise RuntimeError("TBILL-3M rate data is empty")
    return s


def tbill_rate_to_daily_cash(rate_monthly: pd.Series, end: pd.Timestamp) -> pd.Series:
    """Approximate a 3-month T-bill total-return cash index.

    TB3MS is a 3-month T-bill bank-discount yield. For each month:
      price = 1 - d * 91/360
      91-day HPR = (1-price)/price
      annual effective = (1+HPR)^(365/91)-1
      business-day accrual = (1+annual effective)^(1/252)-1

    The monthly average rate is held constant within the month. This is a
    pre-BIL reconstruction only; actual BIL adjusted-close returns are grafted
    from BIL inception onward.
    """
    m = rate_monthly.copy()
    m.index = m.index.to_period("M")
    idx = pd.bdate_range(m.index.min().to_timestamp(), end)
    periods = idx.to_period("M")
    rates = pd.Series(periods, index=idx).map(m)
    rates = pd.to_numeric(rates, errors="coerce").ffill().bfill()

    d = rates / 100.0
    price = 1.0 - d * (91.0 / 360.0)
    if (price <= 0).any():
        raise RuntimeError("invalid T-bill discount price")
    hpr_91 = (1.0 - price) / price
    annual_eff = np.power(1.0 + hpr_91, 365.0 / 91.0) - 1.0
    daily = np.power(1.0 + annual_eff, 1.0 / 252.0) - 1.0

    level = (1.0 + daily).cumprod()
    level.iloc[0] = 1.0
    return level.rename("Cash_proxy")


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
    if s.empty or (s <= 0).any():
        raise RuntimeError(f"{name}: invalid actual ETF data")
    return s


def stitch_proxy_to_actual(proxy: pd.Series, actual: pd.Series, end: pd.Timestamp) -> pd.Series:
    idx = pd.bdate_range(proxy.index.min(), end)
    p = proxy.reindex(idx).ffill()
    a = actual.reindex(idx).ffill()
    first = actual.index[actual.index <= end].min()

    if pd.isna(first):
        return p.loc[:end]
    if pd.isna(p.loc[first]) or pd.isna(a.loc[first]):
        raise RuntimeError(f"splice failure at {first.date()}")

    scale = float(p.loc[first]) / float(a.loc[first])
    out = p.copy()
    out.loc[first:] = a.loc[first:] * scale
    return out.loc[:end]


def build_asset_levels() -> tuple[pd.DataFrame, dict[str, str]]:
    stock_proxy = load_proxy(PROXY_URLS["Stock"], "Stock_proxy")
    long_proxy = load_proxy(PROXY_URLS["LongTreasury"], "LongTreasury_proxy")
    gold_proxy = load_proxy(PROXY_URLS["Gold"], "Gold_proxy")
    cash_proxy = tbill_rate_to_daily_cash(load_tbill_rate(TBILL_URL), LATEST_COMPLETE_MONTH)

    actual = {
        k: load_actual(v, k)
        for k, v in ACTUAL_FILES.items()
    }

    stock = stitch_proxy_to_actual(stock_proxy, actual["Stock"], LATEST_COMPLETE_MONTH).rename("Stock")
    long_bond = stitch_proxy_to_actual(long_proxy, actual["LongTreasury"], LATEST_COMPLETE_MONTH).rename("LongTreasury")
    gold = stitch_proxy_to_actual(gold_proxy, actual["Gold"], LATEST_COMPLETE_MONTH).rename("Gold")
    cash = stitch_proxy_to_actual(cash_proxy, actual["Cash"], LATEST_COMPLETE_MONTH).rename("Cash")

    common_start = max(x.index.min() for x in (stock, long_bond, gold, cash))
    idx = pd.bdate_range(common_start, LATEST_COMPLETE_MONTH)
    levels = pd.concat(
        [
            stock.reindex(idx).ffill(),
            long_bond.reindex(idx).ffill(),
            gold.reindex(idx).ffill(),
            cash.reindex(idx).ffill(),
        ],
        axis=1,
    ).dropna()

    if levels.index[-1] < LATEST_COMPLETE_MONTH:
        raise RuntimeError(
            f"asset data ends too early: {levels.index[-1].date()} < {LATEST_COMPLETE_MONTH.date()}"
        )

    starts = {k: v.index.min().date().isoformat() for k, v in actual.items()}
    return levels, starts


def simulate_annual_equal_weight(
    levels: pd.DataFrame,
    cost_bps: float,
) -> tuple[pd.Series, pd.DataFrame]:
    """25/25/25/25, annual rebalance at calendar-year turn.

    Signal/information timing: the rebalance target is known before the first
    business-day close-to-close return of the new calendar year. Cost is
    charged only on gross rebalancing notional; initial deployment is excluded.
    """
    ret = levels.pct_change().fillna(0.0)
    values = TARGET.copy()
    nav_rows: list[tuple[pd.Timestamp, float]] = []
    trade_rows: list[dict] = []
    prev_year = levels.index[0].year

    for i, (dt, row) in enumerate(ret.iterrows()):
        if i > 0 and dt.year != prev_year:
            pre_nav = float(values.sum())
            target_values = TARGET * pre_nav
            gross_notional = float(np.abs(target_values - values).sum())
            cost = gross_notional * cost_bps / 10_000.0
            post_nav = pre_nav - cost
            values = TARGET * post_nav
            trade_rows.append(
                {
                    "Date": dt,
                    "GrossTurnover": gross_notional / pre_nav if pre_nav > 0 else np.nan,
                    "CostNAV": cost,
                }
            )
            prev_year = dt.year

        if i > 0:
            values *= 1.0 + row.to_numpy(dtype=float)

        nav_rows.append((dt, float(values.sum())))

    nav = pd.Series(dict(nav_rows), dtype=float).sort_index()
    nav /= float(nav.iloc[0])
    return nav, pd.DataFrame(trade_rows)


def stock_benchmark(levels: pd.DataFrame) -> pd.Series:
    s = levels["Stock"].astype(float)
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


def create_dashboard(results: dict) -> None:
    def period_data(key: str) -> dict:
        r = results[key]
        m = r["monthly_nav"][["영구포트폴리오 비용후(5bp)", "S&P500 100%"]]
        d = r["daily_nav"][["영구포트폴리오 비용후(5bp)", "S&P500 100%"]]
        dd = d / d.cummax() - 1.0
        metrics = r["metrics"]
        monthly = []
        for dt, row in m.iterrows():
            p = float(row["영구포트폴리오 비용후(5bp)"])
            b = float(row["S&P500 100%"])
            monthly.append(
                {
                    "date": dt.strftime("%Y-%m-%d"),
                    "p": p,
                    "b": b,
                    "plog": float(np.log2(p)),
                    "blog": float(np.log2(b)),
                    "p_asset": p * INITIAL_CAPITAL,
                    "b_asset": b * INITIAL_CAPITAL,
                }
            )
        drawdown = [
            {
                "date": dt.strftime("%Y-%m-%d"),
                "pdd": float(row["영구포트폴리오 비용후(5bp)"] * 100.0),
                "bdd": float(row["S&P500 100%"] * 100.0),
            }
            for dt, row in dd.iterrows()
        ]
        def metric_row(name: str) -> dict:
            x = metrics.loc[name]
            return {
                "CAGR": float(x["CAGR"] * 100.0),
                "MDD": float(x["MDD"] * 100.0),
                "Sharpe": float(x["Sharpe"]),
                "Vol": float(x["연환산_표준편차"] * 100.0),
                "Recovery": float(x["최대회복기간_개월"]),
                "Final": float(x["최종자산"]),
            }
        return {
            "label": r["label"],
            "monthly": monthly,
            "drawdown": drawdown,
            "metrics": {
                "p": metric_row("영구포트폴리오 비용후(5bp)"),
                "b": metric_row("S&P500 100%"),
            },
        }

    dashboard_data = {
        "longest": period_data("longest"),
        "from_2001": period_data("from_2001"),
        "from_2021": period_data("from_2021"),
    }
    (OUT / "interactive_dashboard_data.json").write_text(
        json.dumps(dashboard_data, ensure_ascii=False), encoding="utf-8"
    )

    from plotly.offline import get_plotlyjs
    plotly_js = get_plotlyjs()
    data_json = json.dumps(dashboard_data, ensure_ascii=False)

    html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>영구 포트폴리오 백테스트</title>
<style>
:root {{ color-scheme: light dark; }}
body {{ font-family:"Noto Sans KR","Malgun Gothic","Apple SD Gothic Neo",sans-serif; margin:0; background:#f4f6f8; color:#111; }}
.wrap {{ max-width:1280px; margin:0 auto; padding:20px; }}
.toolbar {{ display:flex; gap:12px; align-items:center; flex-wrap:wrap; }}
select {{ font:inherit; padding:10px 14px; border-radius:10px; border:1px solid #bbb; background:white; color:#111; }}
.cards {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; margin:14px 0; }}
.card,.chart {{ background:white; border-radius:12px; box-shadow:0 1px 4px rgba(0,0,0,.08); }}
.card {{ padding:14px 16px; }}
.card h3 {{ margin:0 0 8px; font-size:15px; }}
.metrics {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:8px; font-size:13px; }}
.metric b {{ display:block; font-size:16px; margin-top:2px; }}
.chart {{ height:430px; margin:12px 0; }}
.note {{ font-size:12px; color:#666; margin:8px 0; }}
@media(max-width:800px){{.cards{{grid-template-columns:1fr}}.metrics{{grid-template-columns:repeat(2,minmax(0,1fr))}}.chart{{height:360px}}}}
@media(prefers-color-scheme:dark){{body{{background:#111315;color:#f5f5f5}}.card,.chart{{background:#1d2024}}select{{background:#1d2024;color:#f5f5f5;border-color:#555}}.note{{color:#aaa}}}}
</style>
<script>{plotly_js}</script>
</head>
<body><div class="wrap">
<div class="toolbar"><strong>3번 영구 포트폴리오</strong><label for="period">분석기간</label>
<select id="period"><option value="longest">최장~현재</option><option value="from_2001" selected>2001~현재</option><option value="from_2021">2021~현재</option></select></div>
<div id="periodLabel" class="note"></div>
<div class="cards">
<div class="card"><h3>영구포트폴리오 비용후(5bp)</h3><div id="pm" class="metrics"></div></div>
<div class="card"><h3>S&P500 100%</h3><div id="bm" class="metrics"></div></div>
</div>
<div id="cum" class="chart"></div><div id="log" class="chart"></div><div id="dd" class="chart"></div>
<div class="note">SPY/TLT/GLD/BIL 각 25%, 연 1회 리밸런싱. 누적자산·Log2는 월별 NAV, Drawdown은 일별 NAV. 거래비용 5bp는 연간 리밸런싱 총 거래금액에 적용.</div>
</div>
<script>
const DATA={data_json}; const cfg={{responsive:true,displaylogo:false,scrollZoom:true}};
function f(v,d=2){{return Number(v).toLocaleString('ko-KR',{{minimumFractionDigits:d,maximumFractionDigits:d}})}}
function mh(m){{return [['CAGR',f(m.CAGR)+'%'],['MDD',f(m.MDD)+'%'],['Sharpe',f(m.Sharpe)],['변동성',f(m.Vol)+'%'],['회복기간',f(m.Recovery,1)+'개월']].map(x=>'<div class="metric">'+x[0]+'<b>'+x[1]+'</b></div>').join('')}}
function render(k){{
 const q=DATA[k],m=q.monthly,d=q.drawdown,x=m.map(r=>r.date);
 periodLabel.textContent=q.label; pm.innerHTML=mh(q.metrics.p); bm.innerHTML=mh(q.metrics.b);
 Plotly.react('cum',[
  {{x,y:m.map(r=>r.p),name:'영구포트폴리오 비용후(5bp)',mode:'lines',customdata:m.map(r=>r.p_asset),hovertemplate:'%{{x}}<br>%{{y:.3f}}배<br>$%{{customdata:,.0f}}<extra></extra>'}},
  {{x,y:m.map(r=>r.b),name:'S&P500 100%',mode:'lines',customdata:m.map(r=>r.b_asset),hovertemplate:'%{{x}}<br>%{{y:.3f}}배<br>$%{{customdata:,.0f}}<extra></extra>'}}
 ],{{title:'① 누적자산',yaxis:{{title:'배수'}},xaxis:{{rangeslider:{{visible:true}}}},hovermode:'x unified',margin:{{l:60,r:20,t:55,b:45}}}},cfg);
 const vals=m.flatMap(r=>[r.plog,r.blog]),lo=Math.min(0,Math.floor(Math.min(...vals))),hi=Math.max(1,Math.ceil(Math.max(...vals))),tv=[],tt=[];
 for(let i=lo;i<=hi;i++){{tv.push(i);tt.push((2**i).toLocaleString('ko-KR',{{maximumFractionDigits:3}})+'배')}}
 Plotly.react('log',[
  {{x,y:m.map(r=>r.plog),name:'영구포트폴리오 비용후(5bp)',mode:'lines'}},
  {{x,y:m.map(r=>r.blog),name:'S&P500 100%',mode:'lines'}}
 ],{{title:'② Log2 누적자산',yaxis:{{title:'누적자산 배수',tickmode:'array',tickvals:tv,ticktext:tt}},xaxis:{{rangeslider:{{visible:true}}}},hovermode:'x unified',margin:{{l:70,r:20,t:55,b:45}}}},cfg);
 const xd=d.map(r=>r.date);
 Plotly.react('dd',[
  {{x:xd,y:d.map(r=>r.pdd),name:'영구포트폴리오 비용후(5bp)',mode:'lines',hovertemplate:'%{{x}}<br>%{{y:.2f}}%<extra></extra>'}},
  {{x:xd,y:d.map(r=>r.bdd),name:'S&P500 100%',mode:'lines',hovertemplate:'%{{x}}<br>%{{y:.2f}}%<extra></extra>'}}
 ],{{title:'③ Drawdown (일별)',yaxis:{{title:'Drawdown (%)',rangemode:'tozero'}},xaxis:{{rangeslider:{{visible:true}}}},hovermode:'x unified',margin:{{l:70,r:20,t:55,b:45}}}},cfg);
}}
period.addEventListener('change',e=>render(e.target.value)); render('from_2001');
</script></body></html>"""
    (OUT / "interactive_dashboard.html").write_text(html, encoding="utf-8")


def main() -> None:
    levels, actual_starts = build_asset_levels()

    gross, trades_0 = simulate_annual_equal_weight(levels, 0.0)
    net_5, trades_5 = simulate_annual_equal_weight(levels, BASE_COST_BPS)
    benchmark = stock_benchmark(levels)

    daily_nav = pd.concat(
        [
            gross.rename("영구포트폴리오 비용전"),
            net_5.rename("영구포트폴리오 비용후(5bp)"),
            benchmark,
        ],
        axis=1,
    ).dropna()
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

    # 모든 기간 절단/재기준화/성과·위험지표/채팅 payload는 v2-9 표준 템플릿에 위임.
    results = run_four_periods(monthly_nav, config, daily_nav)
    summary = flatten_four_period_results(results)
    summary.to_csv(OUT / "summary_four_periods_template.csv", index=False, encoding="utf-8-sig")

    combined_payload = combine_period_payloads(
        *[
            results[k]["chat_payload"]
            for k in ["book_validation", "from_2001", "from_2021", "longest"]
        ]
    )
    save_chat_payload(combined_payload, str(OUT / "chat_payload_four_periods.json"))

    daily_nav.to_csv(OUT / "daily_nav_full.csv.gz", compression="gzip")
    monthly_nav.to_csv(OUT / "monthly_nav_full.csv", encoding="utf-8-sig")
    create_dashboard(results)

    sensitivity_rows = []
    for bps in COST_SCENARIOS_BPS:
        nav, trades = simulate_annual_equal_weight(levels, bps)
        d = pd.DataFrame({f"영구포트폴리오_{bps:g}bp": nav})
        m = month_end_nav(d)
        rr = run_four_periods(m, config, d)
        for key, result in rr.items():
            metric = result["metrics"].iloc[0]
            start = pd.Timestamp(result["start"])
            end = pd.Timestamp(result["end"])
            tt = trades[(trades["Date"] >= start) & (trades["Date"] <= end)] if len(trades) else trades
            sensitivity_rows.append(
                {
                    "Period": key,
                    "Cost_bps": bps,
                    "CAGR": metric["CAGR"],
                    "MDD": metric["MDD"],
                    "Sharpe": metric["Sharpe"],
                    "Annualized_Std": metric["연환산_표준편차"],
                    "Max_Recovery_Months": metric["최대회복기간_개월"],
                    "Final_Asset_USD": metric["최종자산"],
                    "MDD_Source": metric["MDD_source"],
                    "Avg_Annual_Gross_Turnover": float(tt["GrossTurnover"].mean()) if len(tt) else 0.0,
                }
            )
    pd.DataFrame(sensitivity_rows).to_csv(
        OUT / "cost_sensitivity_template.csv", index=False, encoding="utf-8-sig"
    )

    book = results["book_validation"]["metrics"].loc["영구포트폴리오 비용전"]
    pd.DataFrame(
        [
            {"Metric": "Final_Asset_USD", "Book": 762_000.0, "Template_Backtest": float(book["최종자산"])},
            {"Metric": "CAGR", "Book": 0.088, "Template_Backtest": float(book["CAGR"])},
            {"Metric": "MDD", "Book": -0.127, "Template_Backtest": float(book["MDD"])},
            {"Metric": "Sharpe", "Book": 0.57, "Template_Backtest": float(book["Sharpe"])},
        ]
    ).to_csv(OUT / "book_verification_template.csv", index=False, encoding="utf-8-sig")

    # ETF-only robustness: BIL inception 이후 네 ETF 실제 수정주가만 사용한 전략과
    # stitched series가 동일한 일간 수익률 경로를 만드는지 확인.
    actual_levels = pd.concat(
        [
            load_actual(ACTUAL_FILES["Stock"], "Stock"),
            load_actual(ACTUAL_FILES["LongTreasury"], "LongTreasury"),
            load_actual(ACTUAL_FILES["Gold"], "Gold"),
            load_actual(ACTUAL_FILES["Cash"], "Cash"),
        ],
        axis=1,
        join="inner",
    ).dropna().loc[:LATEST_COMPLETE_MONTH]
    actual_nav, _ = simulate_annual_equal_weight(actual_levels, 0.0)
    hybrid_levels = levels.reindex(actual_levels.index).ffill().dropna()
    hybrid_nav, _ = simulate_annual_equal_weight(hybrid_levels, 0.0)
    overlap = pd.concat(
        [actual_nav.rename("Actual"), hybrid_nav.rename("Hybrid")], axis=1
    ).dropna()
    overlap_ret = overlap.pct_change().dropna()
    overlap_check = {
        "start": overlap.index[0].date().isoformat(),
        "end": overlap.index[-1].date().isoformat(),
        "max_abs_daily_return_diff": float((overlap_ret["Actual"] - overlap_ret["Hybrid"]).abs().max()),
        "final_multiple_actual": float(overlap["Actual"].iloc[-1] / overlap["Actual"].iloc[0]),
        "final_multiple_hybrid": float(overlap["Hybrid"].iloc[-1] / overlap["Hybrid"].iloc[0]),
    }
    (OUT / "actual_etf_overlap_check.json").write_text(
        json.dumps(overlap_check, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    template_path = Path("scripts/quant_backtest_template_v2_9.py")
    metadata = {
        "as_of": AS_OF.date().isoformat(),
        "latest_complete_month": LATEST_COMPLETE_MONTH.date().isoformat(),
        "strategy": "SPY 25% + TLT 25% + GLD 25% + BIL 25%, annual rebalance",
        "book_validation": "1970-01 through 2021-12",
        "initial_capital_usd": INITIAL_CAPITAL,
        "risk_free_rate_for_template_sharpe": 0.0,
        "base_cost_bps_on_gross_rebalance_notional": BASE_COST_BPS,
        "initial_deployment_cost_included": False,
        "taxes_included": False,
        "execution_assumption": "rebalance at calendar-year turn before first business-day close-to-close return",
        "proxy_sources": PROXY_URLS | {"Cash_rate": TBILL_URL},
        "actual_sources": ACTUAL_FILES,
        "actual_etf_starts": actual_starts,
        "pre_bil_cash_method": "FRED TB3MS bank-discount yield via pofo; converted to 91-day HPR, annual effective, then 252-business-day accrual; actual BIL grafted from inception",
        "standard_template": str(template_path),
        "standard_template_sha256": hashlib.sha256(template_path.read_bytes()).hexdigest(),
        "notes": [
            "Pre-ETF history is reconstructed and not an executable ETF history.",
            "Gold before GLD uses XAU/USD spot; no storage/ETF fee is deducted before GLD inception.",
            "BIL before inception is an approximation from 3-month T-bill rates, not a historical BIL quote series.",
            "Book Sharpe convention is unspecified; template Sharpe uses rf=0 and monthly returns.",
        ],
    }
    (OUT / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(summary.to_string(index=False))
    print("\nMDD sources")
    print(summary[["Period", "전략", "MDD_source"]].to_string(index=False))
    print("\nTemplate SHA256:", metadata["standard_template_sha256"])


if __name__ == "__main__":
    main()
