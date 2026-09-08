import pandas as pd

import backtest_kang_k_allweather_original as b


def build_panel_fixed():
    months = pd.date_range(b.START - pd.offsets.MonthEnd(1), b.END, freq="ME")
    usdkrw = b.month_last(b.fred("DEXKOUS")).reindex(months).ffill()
    fx_ret = b.ret(usdkrw)
    switch = {}

    spy = b.month_last(b.yf_close("SPY", adjusted=True)).reindex(months).ffill()
    us, switch["미국주식"] = b.splice_returns(b.ret(spy * usdkrw), b.ETF["미국주식"], "미국주식")

    # 한국주식: KOSPI200 가격지수 → 2002년부터 KODEX200 조정종가(배당 반영) → 2018년부터 KOSEF/KIWOOM 200TR.
    # 서로 다른 지수 '수준'을 연결하지 않고 월수익률만 이어 붙여 레벨 점프를 방지한다.
    ks200 = b.month_last(b.yf_close("^KS200", adjusted=False)).reindex(months)
    kodex200 = b.month_last(b.yf_close("069500.KS", adjusted=True)).reindex(months)
    kr_proxy = b.ret(ks200.ffill())
    kodex_ret = b.ret(kodex200)
    kr_proxy.loc[kodex_ret.notna()] = kodex_ret.loc[kodex_ret.notna()]
    kr, switch["한국주식"] = b.splice_returns(kr_proxy, b.ETF["한국주식"], "한국주식")

    gc = b.month_last(b.yf_close("GC=F", adjusted=True)).reindex(months)
    gold_proxy = b.ret(gc)
    fallback_file = b.ROOT / "results" / "k_allweather_v3" / "asset_returns_monthly.csv"
    if fallback_file.exists() and gold_proxy.isna().any():
        old = pd.read_csv(fallback_file, index_col=0, parse_dates=True, encoding="utf-8-sig")
        old_gold = old["금"].reindex(months)
        hedged_spot = (1 + old_gold) / (1 + fx_ret) - 1
        mask = gold_proxy.isna() & hedged_spot.notna()
        gold_proxy.loc[mask] = hedged_spot.loc[mask]
        print(f"금 early fallback months from LBMA spot ex-FX: {int(mask.sum())}")
    gold, switch["금"] = b.splice_returns(gold_proxy, b.ETF["금"], "금")

    kr10_proxy = b.synthetic_bond_monthly(b.fred("IRLTLT01KRM156N"), 10).reindex(months).fillna(0.0)
    kr10, switch["한국10년국채"] = b.splice_returns(kr10_proxy, b.ETF["한국10년국채"], "한국10년국채")

    us10_local = b.synthetic_bond_monthly(b.fred("GS10"), 10).reindex(months).fillna(0.0)
    us10_proxy = (1 + us10_local) * (1 + fx_ret) - 1
    us10, switch["미국10년국채"] = b.splice_returns(us10_proxy, b.ETF["미국10년국채"], "미국10년국채")

    panel = pd.concat([
        us.rename("미국주식"),
        kr.rename("한국주식"),
        gold.rename("금"),
        kr10.rename("한국10년국채"),
        us10.rename("미국10년국채"),
    ], axis=1).reindex(months).loc[b.START:b.END]

    miss = panel.isna().sum()
    if miss.any():
        raise RuntimeError(f"Unresolved missing data: {miss[miss > 0].to_dict()}")
    return panel, switch


b.build_panel = build_panel_fixed
b.main()
