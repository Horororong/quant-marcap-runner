"""
quant_backtest_template_CURRENT.py

표준 퀀트 백테스트 템플릿 v2-16 / CURRENT (2026-09 KRX PIT 연결)

핵심 원칙
1) 성과 산출: 월별 NAV 기준
   - CAGR
   - Sharpe Ratio
   - 연환산 표준편차
2) 위험 산출: 일별 NAV 우선
   - MDD
   - 최대 손실 회복기간
   - Drawdown 그래프
   - 일별 NAV가 없을 때만 월별 NAV로 자동 fallback
3) 표준 검증기간은 항상 4개
   - 책 기간 검증
   - 2000~가용 최신일
   - 2021~가용 최신일
   - 가능한 최장기간~가용 최신일
4) 월말 NAV만으로 일별 MDD를 추정하거나 보간하지 않는다.
5) 로그2 차트는 log2(NAV)를 직접 계산해 1배/2배/4배/8배... 동일 간격을 보장한다.
6) 채팅 출력은 "실제로 보이는 인터랙티브 차트"를 최우선한다.
   - 버전 2(fallback): 네이티브 기간 선택 UI가 지원되면 3개 기본 차트 각각에 기간 선택 버튼을 제공한다.
   - 버전 1(우선): 버전 1을 기본으로 사용해 3기간 x 3차트 = 9개 인라인 차트를 모두 표시한다.
   - 버전 1/2 모두 책 검증기간은 성과표에만 포함하고 차트 기간 선택/표시에서는 제외한다.
   - 다운로드형 HTML은 보조수단이며 채팅 인라인 차트를 대체하지 않는다.

주의
- '책 기간'의 시작/종료일은 전략마다 다르므로 반드시 book_start/book_end를 명시한다.
- 2026년 종료일은 실제 데이터의 최신 가용일을 사용한다. 존재하지 않는 미래 데이터를 생성하지 않는다.
- 일별 데이터가 없으면 결과 표에 MDD_source='monthly_fallback'으로 명시한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple, Sequence, Iterable
from pathlib import Path
import json
import math
import os

import numpy as np
import pandas as pd

TEMPLATE_VERSION = "v2-16"
CHAT_PAYLOAD_MAX_DRAWDOWN_POINTS = 480


# =========================================================
# 0. 프로젝트 데이터 소스 계약 (v2-16)
# =========================================================

PROJECT_GITHUB_REPO = "Horororong/quant-marcap-runner"
PROJECT_DATA_PRIORITY = [
    "data/krx_equities/yearly/",
    "data/financials/full_history/",
    "data/derived/daily/",
    "data/etf_us/",
    "data/etf_kr/",
    "data/indices/",
    "data/fx/",
    "data/macro/",
    "data/proxy_long/",
]
PROJECT_COLLECTION_REGISTRIES = {
    "us_etf": "config/etf_universe.csv",
    "kr_etf": "config/kr_etf_universe.csv",
    "strategy_long_or_missing": "config/strategy_data_collection.csv",
}
PROJECT_COLLECTION_WORKFLOWS = {
    "krx_equities": ".github/workflows/update-quant-data.yml",
    "dart_financials": ".github/workflows/update-quant-data.yml",
    "us_etf": ".github/workflows/update-etf-data.yml",
    "market_and_proxy": ".github/workflows/update-market-data.yml",
}

BACKTEST_EXECUTION_CONTRACT = """
사용자가 '백테스트해줘', '백테스트', '전략 검증' 등 백테스트 실행을 요청하면 다음 순서를 기본 강제한다.

1) 항상 이 CURRENT v2-16 템플릿의 계산/검증/출력 규칙을 사용한다.
2) 한국 개별주 전략이면 먼저 load_korean_equity_backtest_data()/load_krx_equity_panel()로
   data/krx_equities/yearly 의 PIT 패널을 사용한다. 현재 상장종목 목록으로 과거 유니버스를 만들지 않는다.
2-A) 미국/한국 ETF 전략은 load_etf_backtest_data()로 data/etf_us 또는 data/etf_kr를 읽고,
   Adj Close와 원시 OHLC의 용도를 구분한다. 요구기간 부족을 조용히 축약하지 않는다.
2-B) 회전율이 발생하는 전략은 TradingCostAssumptions + apply_trading_costs_to_returns() 또는
   동등한 일별 체결 엔진으로 비용 전/후 NAV를 모두 만든다. 비용 가정이 없으면 이를 명시하고
   최소/기준/보수적 시나리오를 전략 레이어에서 정의한다.
2-C) 일별 MDD 검증 시 한국 거래소는 XKRX, 미국 주식/ETF는 XNYS 캘린더를 기본 지정한다.
   교차시장 전략은 실제 NAV 생성에 사용한 거래일 캘린더를 명시한다.
3) 필요한 가격, 지수, 환율, 거시, 재무, 프록시 데이터가 이미 사용자 GitHub 저장소
   Horororong/quant-marcap-runner 에 존재하는지 먼저 탐색한다.
4) GitHub에 존재하는 데이터가 충분하면 외부 데이터 제공업체를 우선 사용하지 않는다.
5) 필요한 데이터가 GitHub에 없거나 요구기간이 부족하면 데이터를 임의 생성하지 않는다.
6) 누락 데이터가 반복수집 가능한 자산/시계열이면 자동수집 레지스트리에 추가한다.
   - 미국 ETF: config/etf_universe.csv
   - 한국 ETF: config/kr_etf_universe.csv
   - 장기 프록시/전략별 미수집 데이터: config/strategy_data_collection.csv
7) 레지스트리 추가만으로 기존 수집기가 처리 가능한 경우, 해당 주간 GitHub Actions가 이후 자동 갱신하도록 한다.
8) 기존 수집기가 해당 데이터 유형을 처리하지 못하면, 적절한 수집 스크립트와 workflow를 추가/수정하여
   자동 갱신 경로를 함께 만든다. 단, API 키/유료 권한/법적 접근이 필요한 경우에는 임의로 대체하지 않고 한계를 명시한다.
9) 수집기 추가/수정 후에는 데이터 저장 경로, 시작일, 빈도, 수정주가/총수익 여부, 결측치, 기업행위 반영 여부를 기록한다.
10) 데이터가 아직 확보되지 않은 상태에서 백테스트 수치를 만들지 않는다. 확보 가능한 구간만 조용히 축약하지 않고
   표준기간 충족 실패를 명시하거나, 검증 가능한 대체 프록시를 별도 '탐색적' 결과로 구분한다.
11) 모든 백테스트 산출물은 비용 전/후를 구분하고, 4개 표준기간을 유지한다.
12) 차트 출력은 버전 1을 기본으로 한다.
    - 2000~현재: 누적자산 / Log2 누적자산 / Drawdown
    - 2021~현재: 누적자산 / Log2 누적자산 / Drawdown
    - 최장~현재: 누적자산 / Log2 누적자산 / Drawdown
    총 9개 인라인 차트.
13) 버전 1을 현재 채팅 UI에서 안정적으로 렌더링할 수 없을 때만 버전 2로 fallback한다.
    - 누적자산 / Log2 / Drawdown 3개 차트
    - 각 차트에 2000 / 2021 / 최장 기간 선택 UI
14) 책 검증기간은 성과표 및 책 수치 비교에 포함하지만 기본 차트에서는 제외한다.
15) 전략별 코드의 책임은 일별 NAV 산출까지다. CAGR/MDD/Sharpe/회복기간/성과표/채팅 차트를 전략별 코드에서 재구현하지 않는다.
16) 성과 및 위험지표는 반드시 이 CURRENT의 run_four_periods()/calculate_metrics()를 단일 계산원(single source of truth)으로 사용한다.
17) 채팅 출력용 payload는 build_chat_payload()/combine_period_payloads()만 사용한다. 계산 정확도와 표시량을 분리하며,
    MDD/회복기간은 전체 일별 NAV로 계산하고 Drawdown 표시용 데이터만 보존형 축약을 허용한다.
18) 동일한 전략/데이터/비용 가정이면 모델의 사고 수준이나 대화에 관계없이 같은 성과 수치가 나와야 한다.
19) 표준 체결은 신호일 종가 이후 최소 1개 거래세션이 지난 시점에만 허용한다. 기본 범용 엔진은 next-session close 체결이다.
20) 목표비중 신호를 simulate_target_weight_portfolio()에 전달하면 비중 drift, 매수/매도 turnover, 비용, gross/net 일별 NAV를 표준 방식으로 생성한다.
21) run_execution_backtest()는 체결 결과를 최근 완결월까지만 정식 성과기간으로 변환해 run_four_periods()에 연결하고, 최근 거래일 NAV는 참고 스냅샷으로 분리한다.
22) 거래정지/상장폐지/기업행위 때문에 보유종목 수익률이 정의되지 않으면 조용히 0% 처리하지 않는다. 명시적 tradable mask 또는 delisting return/기업행위 조정 자료가 없으면 실패한다.
23) KRX 원천 가격만으로 현금배당·상폐 회수액을 임의 추정하지 않는다. 총수익 데이터가 필요한 전략은 검증된 배당/기업행위 원천을 별도로 제공해야 한다.
24) OOS/워크포워드는 generate_expanding_walk_forward_windows()로 시간 순서를 보존하고 embargo를 적용할 수 있다.
"""


# =========================================================
# 0-A. 한국 개별주 PIT 데이터 계약 / 로더 (v2-16)
# =========================================================

KRX_EQUITY_YEARLY_DIR = "data/krx_equities/yearly"
KRX_EQUITY_STATUS_FILE = "data/status/krx_equities_status.csv"
DART_FULL_HISTORY_DIR = "data/financials/full_history"
ETF_US_DIR = "data/etf_us"
ETF_KR_DIR = "data/etf_kr"
ETF_US_REGISTRY = "config/etf_universe.csv"
ETF_KR_REGISTRY = "config/kr_etf_universe.csv"

KRX_EQUITY_CANONICAL_COLUMNS = [
    "Date", "Code", "Name", "Market", "Dept", "MarketId", "Rank",
    "Open", "High", "Low", "Close", "Volume", "Amount",
    "Changes", "ChangeCode", "ChangesRatio", "Marcap", "Stocks",
    "Change", "UpDown", "Comp",
]

KRX_BACKTEST_DATA_CONTRACT = r"""
한국 개별주 백테스트 데이터 계약:

1) 가격/유니버스 기본 원천은 data/krx_equities/yearly/marcap-YYYY.parquet 이다.
2) 현재 상장종목 목록으로 과거 유니버스를 재구성하지 않는다. 각 날짜의 원본 횡단면을 그대로 사용한다.
3) KOSPI/KOSDAQ, 보통주/우선주 등 원천에 존재하는 증권은 로더 단계에서 임의 제거하지 않는다.
   전략별 제외조건(우선주/스팩/리츠/금융업/신규상장/관리종목 등)은 백테스트 설계에서 명시적으로 적용한다.
4) 신호일 t의 종가/시총/거래대금 등으로 만든 신호를 같은 종가에 체결하지 않는다. 기본 체결은 t+1의 거래 가능한 가격이다.
5) 재무 팩터는 fiscal period 종료일이 아니라 실제 filing_date 이후에만 사용할 수 있다.
6) DART 원천 행은 data/financials/full_history에서 읽되, PBR/ROE/ROIC 등 팩터 계산은
   계정 정의와 공시시차를 명시한 표준화 테이블에서 수행한다.
7) 수정주가가 아닌 원천 가격을 사용할 수 있으므로 수익률 계산 시 ChangesRatio/Change와 기업행위를 점검한다.
8) 상장폐지/거래정지/가격제한폭/유동성 부족 종목은 조용히 삭제하지 않는다.
9) 데이터 파일 누락, 중복 Date+Code, 요구기간 부족은 즉시 오류로 처리한다.
"""


def _resolve_project_root(repo_root: Optional[str | Path] = None) -> Path:
    """Horororong/quant-marcap-runner 로컬 체크아웃의 루트를 찾는다."""
    candidates: list[Path] = []
    if repo_root is not None:
        candidates.append(Path(repo_root).expanduser())
    env_root = os.getenv("QUANT_REPO_ROOT", "").strip()
    if env_root:
        candidates.append(Path(env_root).expanduser())
    candidates.append(Path.cwd())
    try:
        candidates.append(Path(__file__).resolve().parent)
    except NameError:
        pass

    expanded: list[Path] = []
    for c in candidates:
        c = c.resolve()
        expanded.append(c)
        expanded.extend(c.parents)

    seen: set[Path] = set()
    for root in expanded:
        if root in seen:
            continue
        seen.add(root)
        if (root / KRX_EQUITY_YEARLY_DIR).exists():
            return root

    raise FileNotFoundError(
        "한국 개별주 데이터 저장소를 찾지 못했습니다. "
        "Horororong/quant-marcap-runner 체크아웃에서 실행하거나 "
        "repo_root 또는 QUANT_REPO_ROOT를 지정하십시오."
    )


def _normalize_stock_codes(codes: Optional[Iterable[str]]) -> Optional[set[str]]:
    if codes is None:
        return None
    out = {str(x).strip().zfill(6) for x in codes if str(x).strip()}
    return out or None


def krx_available_years(repo_root: Optional[str | Path] = None) -> list[int]:
    root = _resolve_project_root(repo_root)
    years = []
    for p in sorted((root / KRX_EQUITY_YEARLY_DIR).glob("marcap-*.parquet")):
        try:
            years.append(int(p.stem.split("-")[-1]))
        except ValueError:
            continue
    if not years:
        raise FileNotFoundError(f"{root / KRX_EQUITY_YEARLY_DIR}에 연도별 parquet가 없습니다.")
    return sorted(set(years))


def read_krx_equity_status(repo_root: Optional[str | Path] = None) -> Dict[str, Any]:
    root = _resolve_project_root(repo_root)
    p = root / KRX_EQUITY_STATUS_FILE
    if not p.exists():
        return {}
    st = pd.read_csv(p)
    if st.empty:
        return {}
    row = st.iloc[-1].to_dict()
    return {str(k): v for k, v in row.items()}


def load_krx_equity_panel(
    start: Optional[str | pd.Timestamp] = None,
    end: Optional[str | pd.Timestamp] = None,
    codes: Optional[Iterable[str]] = None,
    markets: Sequence[str] = ("KOSPI", "KOSDAQ"),
    columns: Optional[Sequence[str]] = None,
    repo_root: Optional[str | Path] = None,
    require_all_year_files: bool = True,
) -> pd.DataFrame:
    """
    한국 개별주 PIT 일별 패널을 연도별 parquet에서 읽는다.

    반환 기본키: Date + Code.
    현재 상장종목 마스터로 과거 종목을 필터링하지 않으므로 상장폐지 종목이 보존된다.
    """
    root = _resolve_project_root(repo_root)
    yearly_dir = root / KRX_EQUITY_YEARLY_DIR
    available = krx_available_years(root)

    start_ts = pd.Timestamp(start).normalize() if start is not None else None
    end_ts = pd.Timestamp(end).normalize() if end is not None else None
    if start_ts is not None and end_ts is not None and start_ts > end_ts:
        raise ValueError("start가 end보다 늦습니다.")

    first_year = start_ts.year if start_ts is not None else min(available)
    last_year = end_ts.year if end_ts is not None else max(available)
    requested_years = list(range(first_year, last_year + 1))
    missing_years = [y for y in requested_years if y not in available]
    if require_all_year_files and missing_years:
        raise FileNotFoundError(
            f"요구기간의 KRX 연도 파일이 누락되었습니다: {missing_years}. "
            "기간을 조용히 축약하지 않습니다."
        )

    wanted = list(columns) if columns is not None else list(KRX_EQUITY_CANONICAL_COLUMNS)
    mandatory = ["Date", "Code", "Market"]
    for c in reversed(mandatory):
        if c not in wanted:
            wanted.insert(0, c)

    code_set = _normalize_stock_codes(codes)
    market_set = {str(x).upper().strip() for x in markets}
    chunks: list[pd.DataFrame] = []
    missing_requested_columns: set[str] = set()

    for year in requested_years:
        path = yearly_dir / f"marcap-{year}.parquet"
        if not path.exists():
            continue

        # 연도별 원천 스키마가 조금씩 달라도 읽을 수 있도록 실제 컬럼과 교집합만 읽는다.
        try:
            import pyarrow.parquet as pq  # type: ignore
            schema_cols = set(pq.ParquetFile(path).schema.names)
            read_cols = [c for c in wanted if c in schema_cols]
            missing_requested_columns.update(c for c in wanted if c not in schema_cols)
            df = pd.read_parquet(path, columns=read_cols)
        except ImportError:
            df = pd.read_parquet(path)
            read_cols = [c for c in wanted if c in df.columns]
            missing_requested_columns.update(c for c in wanted if c not in df.columns)
            df = df[read_cols].copy()

        for c in mandatory:
            if c not in df.columns:
                raise AssertionError(f"{path.name}: 필수 컬럼 {c}가 없습니다.")

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.normalize()
        df["Code"] = df["Code"].astype(str).str.zfill(6)
        df["Market"] = df["Market"].astype(str).str.upper().str.strip()
        df = df[df["Date"].notna()]
        if start_ts is not None:
            df = df[df["Date"] >= start_ts]
        if end_ts is not None:
            df = df[df["Date"] <= end_ts]
        df = df[df["Market"].isin(market_set)]
        if code_set is not None:
            df = df[df["Code"].isin(code_set)]
        if len(df):
            chunks.append(df)

    if not chunks:
        raise ValueError("조건에 해당하는 KRX 개별주 관측치가 없습니다.")

    out = pd.concat(chunks, ignore_index=True, sort=False)
    out = out.sort_values(["Date", "Code"]).reset_index(drop=True)
    if out.duplicated(["Date", "Code"]).any():
        dup = out.loc[out.duplicated(["Date", "Code"], keep=False), ["Date", "Code"]].head(10)
        raise AssertionError(f"KRX 패널에 중복 Date+Code가 있습니다. 예시:\n{dup.to_string(index=False)}")

    # 사용자가 명시적으로 요청한 컬럼은 모든 로드 연도에 존재해야 한다.
    # 일부 연도에서만 빠진 컬럼을 concat의 NaN으로 조용히 채우는 것도 금지한다.
    if columns is not None:
        absent = [c for c in columns if c not in out.columns]
        if absent:
            raise KeyError(f"요청 컬럼이 KRX 패널에 없습니다: {absent}")
        if missing_requested_columns:
            raise KeyError(
                "요청 컬럼이 일부 KRX 연도 파일에서 누락되었습니다: "
                f"{sorted(missing_requested_columns)}. 스키마를 먼저 정규화하십시오."
            )

    out.attrs["source"] = "FinanceData/marcap via Horororong/quant-marcap-runner"
    out.attrs["market_calendar"] = "XKRX"
    out.attrs["point_in_time_universe"] = True
    out.attrs["survivorship_filter_applied"] = False
    out.attrs["requested_start"] = None if start_ts is None else str(start_ts.date())
    out.attrs["requested_end"] = None if end_ts is None else str(end_ts.date())
    out.attrs["loaded_years"] = [y for y in requested_years if y in available]
    out.attrs["status"] = read_krx_equity_status(root)
    if missing_requested_columns:
        out.attrs["schema_columns_missing_in_some_years"] = sorted(missing_requested_columns)
    return out


def krx_field_matrix(panel: pd.DataFrame, field: str = "Close") -> pd.DataFrame:
    """Long PIT 패널을 Date x Code 행렬로 변환한다."""
    required = {"Date", "Code", field}
    missing = required.difference(panel.columns)
    if missing:
        raise KeyError(f"필드 행렬 생성에 필요한 컬럼이 없습니다: {sorted(missing)}")
    x = panel[["Date", "Code", field]].copy()
    x[field] = pd.to_numeric(x[field], errors="coerce")
    out = x.pivot(index="Date", columns="Code", values=field).sort_index()
    out.attrs["source"] = panel.attrs.get("source")
    out.attrs["market_calendar"] = panel.attrs.get("market_calendar", "XKRX")
    out.attrs["field"] = field
    return out


def krx_month_end_cross_sections(panel: pd.DataFrame) -> pd.DataFrame:
    """시장 전체의 실제 마지막 거래일 기준 월말 횡단면을 반환한다."""
    if not {"Date", "Code"}.issubset(panel.columns):
        raise KeyError("panel에는 Date와 Code가 필요합니다.")
    x = panel.copy()
    x["Date"] = pd.to_datetime(x["Date"]).dt.normalize()
    x["Month"] = x["Date"].dt.to_period("M")
    market_month_end = x.groupby("Month", observed=True)["Date"].max().rename("MarketMonthEnd")
    x = x.join(market_month_end, on="Month")
    out = x[x["Date"] == x["MarketMonthEnd"]].copy()
    return out.drop(columns=["MarketMonthEnd"]).sort_values(["Date", "Code"]).reset_index(drop=True)


def load_korean_equity_backtest_data(
    start: Optional[str | pd.Timestamp] = None,
    end: Optional[str | pd.Timestamp] = None,
    codes: Optional[Iterable[str]] = None,
    markets: Sequence[str] = ("KOSPI", "KOSDAQ"),
    matrix_fields: Sequence[str] = ("Close",),
    repo_root: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """한국 개별주 전략 연구용 기본 번들. 필요한 행렬만 생성해 메모리 사용을 통제한다."""
    needed = [
        "Date", "Code", "Name", "Market", "Open", "High", "Low", "Close",
        "Volume", "Amount", "Marcap", "Stocks", "Changes", "ChangeCode",
        "ChangesRatio", "Change", "UpDown", "Comp",
    ]
    for field in matrix_fields:
        if field not in needed:
            needed.append(field)
    panel = load_krx_equity_panel(
        start=start, end=end, codes=codes, markets=markets, columns=needed, repo_root=repo_root
    )
    matrices = {field: krx_field_matrix(panel, field) for field in matrix_fields}
    return {
        "panel": panel,
        "matrices": matrices,
        "month_end_cross_sections": krx_month_end_cross_sections(panel),
        "market_calendar": "XKRX",
        "status": panel.attrs.get("status", {}),
        "data_contract": KRX_BACKTEST_DATA_CONTRACT,
    }



def _normalize_etf_market(market: str) -> str:
    m = str(market).upper().strip()
    aliases = {
        "US": "US_ETF", "US_ETF": "US_ETF", "USA": "US_ETF",
        "KR": "KR_ETF", "KR_ETF": "KR_ETF", "KOREA": "KR_ETF",
    }
    if m not in aliases:
        raise ValueError("market은 US/US_ETF 또는 KR/KR_ETF 중 하나여야 합니다.")
    return aliases[m]


def _resolve_kr_etf_symbol(registry: pd.DataFrame, symbol: str) -> tuple[str, str, str]:
    """입력 별칭(코드/yahoo_ticker/이름)을 (code, name, yahoo_ticker)로 정규화."""
    sym = str(symbol).strip()
    code_sym = sym.zfill(6) if sym.isdigit() else sym
    for row in registry.itertuples(index=False):
        code = str(row.code).zfill(6)
        name = str(row.name)
        yahoo = str(row.yahoo_ticker)
        if sym in {code, name, yahoo} or code_sym == code:
            return code, name, yahoo
    raise KeyError(f"한국 ETF 레지스트리에 없는 종목입니다: {symbol}")


def load_etf_backtest_data(
    symbols: Sequence[str],
    market: str = "US",
    start: Optional[str | pd.Timestamp] = None,
    end: Optional[str | pd.Timestamp] = None,
    fields: Sequence[str] = ("Adj Close",),
    repo_root: Optional[str | Path] = None,
    alignment: str = "outer",
    require_requested_coverage: bool = True,
) -> Dict[str, Any]:
    """
    프로젝트 저장소의 미국/한국 ETF CSV를 공통 형식으로 읽는다.

    - 미국 ETF: data/etf_us/{ticker}.csv
    - 한국 ETF: config/kr_etf_universe.csv를 통해 code/name/yahoo_ticker를 해석하고
      data/etf_kr/{code}_{name}.csv를 읽는다.
    - 기본 성과 필드는 yfinance가 제공한 'Adj Close'. 배당/분할 조정의 정확한 정의는
      수집원(yfinance/Yahoo)에 의존하므로 결과 보고에서 source/basis를 그대로 기록한다.
    - 기간 부족을 조용히 축약하지 않는다. start/end를 지정하면 각 자산의 커버리지를 검사한다.
    """
    if not symbols:
        raise ValueError("symbols가 비어 있습니다.")
    if alignment not in {"outer", "inner"}:
        raise ValueError("alignment는 'outer' 또는 'inner'여야 합니다.")

    root = _resolve_project_root(repo_root)
    mkt = _normalize_etf_market(market)
    start_ts = pd.Timestamp(start).normalize() if start is not None else None
    end_ts = pd.Timestamp(end).normalize() if end is not None else None
    if start_ts is not None and end_ts is not None and start_ts > end_ts:
        raise ValueError("start가 end보다 늦습니다.")

    requested_fields = list(dict.fromkeys(str(x) for x in fields))
    if not requested_fields:
        raise ValueError("fields가 비어 있습니다.")

    registry_rows = []
    resolved: list[tuple[str, Path]] = []
    if mkt == "US_ETF":
        reg_path = root / ETF_US_REGISTRY
        if not reg_path.exists():
            raise FileNotFoundError(f"미국 ETF 레지스트리가 없습니다: {reg_path}")
        reg = pd.read_csv(reg_path)
        known = set(reg["ticker"].dropna().astype(str).str.strip())
        for symbol in symbols:
            ticker = str(symbol).strip().upper()
            if ticker not in known:
                raise KeyError(f"미국 ETF 레지스트리에 없는 티커입니다: {ticker}")
            path = root / ETF_US_DIR / f"{ticker}.csv"
            resolved.append((ticker, path))
            row = reg.loc[reg["ticker"].astype(str).str.strip() == ticker].iloc[0].to_dict()
            registry_rows.append({"symbol": ticker, **row})
    else:
        reg_path = root / ETF_KR_REGISTRY
        if not reg_path.exists():
            raise FileNotFoundError(f"한국 ETF 레지스트리가 없습니다: {reg_path}")
        reg = pd.read_csv(reg_path, dtype={"code": str})
        reg["code"] = reg["code"].astype(str).str.zfill(6)
        for symbol in symbols:
            code, name, yahoo = _resolve_kr_etf_symbol(reg, str(symbol))
            matches = sorted((root / ETF_KR_DIR).glob(f"{code}_*.csv"))
            if len(matches) != 1:
                raise FileNotFoundError(
                    f"한국 ETF 파일을 유일하게 찾을 수 없습니다: code={code}, matches={matches}"
                )
            resolved.append((code, matches[0]))
            row = reg.loc[reg["code"] == code].iloc[0].to_dict()
            registry_rows.append({"symbol": code, **row})

    field_series: Dict[str, Dict[str, pd.Series]] = {f: {} for f in requested_fields}
    frames: Dict[str, pd.DataFrame] = {}
    coverage_rows = []

    for canonical, path in resolved:
        if not path.exists():
            raise FileNotFoundError(f"ETF 데이터 파일이 없습니다: {path}")
        df = pd.read_csv(path)
        if "Date" not in df.columns:
            raise KeyError(f"{path.name}: Date 컬럼이 없습니다.")
        missing = [f for f in requested_fields if f not in df.columns]
        if missing:
            raise KeyError(f"{path.name}: 요청 필드 누락 {missing}")

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.normalize()
        if df["Date"].isna().any():
            raise AssertionError(f"{path.name}: 해석 불가능한 Date가 있습니다.")
        if df["Date"].duplicated().any():
            raise AssertionError(f"{path.name}: 중복 날짜가 있습니다.")
        df = df.sort_values("Date").reset_index(drop=True)

        for f in requested_fields:
            df[f] = pd.to_numeric(df[f], errors="coerce")
            if df[f].isna().any():
                raise AssertionError(f"{path.name}: {f} 결측치가 있습니다.")
            if f in {"Open", "High", "Low", "Close", "Adj Close"} and (df[f] <= 0).any():
                raise AssertionError(f"{path.name}: {f}에 0 이하 가격이 있습니다.")

        first_date = pd.Timestamp(df["Date"].iloc[0])
        last_date = pd.Timestamp(df["Date"].iloc[-1])
        if require_requested_coverage and start_ts is not None and first_date > start_ts + pd.Timedelta(days=7):
            raise ValueError(
                f"{canonical}: 요청 시작일 {start_ts.date()}을 충족하지 못합니다. "
                f"첫 데이터={first_date.date()}. 장기 프록시/백필을 먼저 준비하십시오."
            )
        if require_requested_coverage and end_ts is not None and last_date < end_ts - pd.Timedelta(days=7):
            raise ValueError(
                f"{canonical}: 요청 종료일 {end_ts.date()}을 충족하지 못합니다. "
                f"마지막 데이터={last_date.date()}. 최신 데이터를 먼저 갱신하십시오."
            )

        x = df.copy()
        if start_ts is not None:
            x = x[x["Date"] >= start_ts]
        if end_ts is not None:
            x = x[x["Date"] <= end_ts]
        if x.empty:
            raise ValueError(f"{canonical}: 요청기간에 ETF 관측치가 없습니다.")
        frames[canonical] = x
        for f in requested_fields:
            field_series[f][canonical] = x.set_index("Date")[f]
        coverage_rows.append({
            "symbol": canonical,
            "file": str(path.relative_to(root)),
            "first_date": first_date,
            "last_date": last_date,
            "rows_loaded": len(x),
        })

    join = "outer" if alignment == "outer" else "inner"
    panels = {
        f: pd.concat(series_map, axis=1, join=join).sort_index()
        for f, series_map in field_series.items()
    }
    for f, panel in panels.items():
        panel.attrs["source"] = "yfinance/Yahoo files in Horororong/quant-marcap-runner"
        panel.attrs["market"] = mkt
        panel.attrs["market_calendar"] = "XNYS" if mkt == "US_ETF" else "XKRX"
        panel.attrs["field"] = f
        panel.attrs["adjustment_basis"] = (
            "Adj Close as supplied by yfinance/Yahoo; use for distribution/split-adjusted return research"
            if f == "Adj Close" else "raw market field as supplied by yfinance/Yahoo"
        )
        panel.attrs["alignment"] = alignment

    return {
        "market": mkt,
        "market_calendar": "XNYS" if mkt == "US_ETF" else "XKRX",
        "symbols": [x[0] for x in resolved],
        "fields": panels,
        "frames": frames,
        "registry": pd.DataFrame(registry_rows),
        "coverage": pd.DataFrame(coverage_rows),
        "data_contract": (
            "ETF 백테스트는 Adj Close/원시 OHLC의 정의를 구분하고, "
            "요구기간 부족을 조용히 축약하지 않으며, 신호일과 체결일을 분리한다."
        ),
    }


def load_dart_financial_rows(
    years: Sequence[int],
    periods: Sequence[str] = ("FY",),
    fs_div: str = "CFS",
    stock_codes: Optional[Iterable[str]] = None,
    repo_root: Optional[str | Path] = None,
) -> pd.DataFrame:
    """
    DART full-history 원천행을 읽는다. 이 함수는 재무 팩터를 임의 계산하지 않는다.
    반환된 filing_date 이후에만 해당 공시를 사용할 수 있다.
    """
    root = _resolve_project_root(repo_root)
    base = root / DART_FULL_HISTORY_DIR
    if not base.exists():
        raise FileNotFoundError(f"DART full_history 경로가 없습니다: {base}")

    fs = str(fs_div).upper().strip()
    periods_u = [str(x).upper().strip() for x in periods]
    code_set = _normalize_stock_codes(stock_codes)
    files: list[Path] = []
    for year in sorted(set(int(y) for y in years)):
        for period in periods_u:
            files.extend(sorted(base.glob(f"dart_full_{year}_{period}_{fs}_*.csv.gz")))
    if not files:
        raise FileNotFoundError(
            f"조건에 맞는 DART 파일이 없습니다: years={list(years)}, periods={periods_u}, fs_div={fs}"
        )

    chunks: list[pd.DataFrame] = []
    for path in files:
        df = pd.read_csv(path, low_memory=False)
        if "stock_code" not in df.columns:
            raise AssertionError(f"{path.name}: stock_code가 없습니다.")
        df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
        if code_set is not None:
            df = df[df["stock_code"].isin(code_set)]
        if "filing_date" not in df.columns and "rcept_no" in df.columns:
            df["filing_date"] = df["rcept_no"].astype(str).str.slice(0, 8)
        if "filing_date" in df.columns:
            df["filing_date"] = pd.to_datetime(df["filing_date"], format="%Y%m%d", errors="coerce")
        if len(df):
            chunks.append(df)
    if not chunks:
        raise ValueError("선택한 DART 조건에 해당하는 재무행이 없습니다.")
    out = pd.concat(chunks, ignore_index=True, sort=False)
    out.attrs["point_in_time_key"] = "filing_date"
    out.attrs["raw_financial_rows"] = True
    return out


def pit_asof_join(
    observations: pd.DataFrame,
    factors: pd.DataFrame,
    observation_date: str = "Date",
    code_col: str = "Code",
    factor_available_date: str = "available_date",
    factor_code_col: str = "Code",
) -> pd.DataFrame:
    """표준화된 팩터 테이블을 실제 이용가능일 기준으로 과거 방향 as-of join한다."""
    for c in (observation_date, code_col):
        if c not in observations.columns:
            raise KeyError(f"observations에 {c}가 없습니다.")
    for c in (factor_available_date, factor_code_col):
        if c not in factors.columns:
            raise KeyError(f"factors에 {c}가 없습니다.")

    left = observations.copy()
    right = factors.copy()
    left[observation_date] = pd.to_datetime(left[observation_date], errors="coerce")
    right[factor_available_date] = pd.to_datetime(right[factor_available_date], errors="coerce")
    if left[observation_date].isna().any():
        raise AssertionError("observations에 해석 불가능한 관측일이 있습니다.")
    if right[factor_available_date].isna().any():
        raise AssertionError("factors에 해석 불가능한 이용가능일이 있습니다.")
    left[code_col] = left[code_col].astype(str).str.zfill(6)
    right[factor_code_col] = right[factor_code_col].astype(str).str.zfill(6)
    if factor_code_col != code_col:
        if code_col in right.columns:
            raise KeyError(f"factors에 {factor_code_col}와 {code_col}가 동시에 있어 코드키가 모호합니다.")
        right = right.rename(columns={factor_code_col: code_col})
    if right.duplicated([code_col, factor_available_date]).any():
        dup = right.loc[
            right.duplicated([code_col, factor_available_date], keep=False),
            [code_col, factor_available_date],
        ].head(10)
        raise AssertionError(
            "표준화 팩터 테이블에 동일 종목/이용가능일 중복이 있습니다. "
            "공시 정정/우선순위를 먼저 결정하십시오. 예시:\n" + dup.to_string(index=False)
        )

    left = left.sort_values([observation_date, code_col])
    right = right.sort_values([factor_available_date, code_col])
    out = pd.merge_asof(
        left, right, left_on=observation_date, right_on=factor_available_date,
        by=code_col, direction="backward", allow_exact_matches=True
    )
    bad = out[factor_available_date].notna() & (out[factor_available_date] > out[observation_date])
    if bad.any():
        raise AssertionError("PIT as-of join에서 미래 공시가 결합되었습니다.")
    return out


# =========================================================
# 1. 설정
# =========================================================

@dataclass
class BacktestConfig:
    title: str = "퀀트 백테스트"
    initial_capital: float = 10_000_000.0
    periods_per_year: int = 12
    risk_free_rate: float = 0.0

    # 전략별 책 원전 검증기간. 반드시 전략에 맞춰 입력.
    book_start: Optional[str] = None
    book_end: Optional[str] = None

    # 데이터 유효성 검증용(선택)
    expected_start: Optional[str] = None   # 예: "2000-01"
    expected_end: Optional[str] = None     # 예: "2026-08"
    expected_months: Optional[int] = None

    # 표준 분석의 마지막 연도. 기본값은 실행 시점의 현재 연도이며
    # 실제 종료일은 데이터 최신일로 제한된다.
    standard_end_year: int = field(default_factory=lambda: pd.Timestamp.today().year)
    # 데이터 가용성 기준일. None이면 실행일을 사용한다.
    as_of_date: Optional[str] = None
    # 일별 NAV 완전성 검사용 거래소 캘린더. 예: XKRX, XNYS.
    # None이면 보수적 휴리스틱을 사용한다.
    market_calendar: Optional[str] = None

    def __post_init__(self) -> None:
        if not np.isfinite(float(self.initial_capital)) or self.initial_capital <= 0:
            raise ValueError("initial_capital은 0보다 큰 유한한 값이어야 합니다.")
        if not isinstance(self.periods_per_year, int) or self.periods_per_year <= 0:
            raise ValueError("periods_per_year는 1 이상의 정수여야 합니다.")
        if not np.isfinite(float(self.risk_free_rate)) or self.risk_free_rate <= -1.0:
            raise ValueError("risk_free_rate는 -100%보다 큰 유한한 연이율이어야 합니다.")
        if not isinstance(self.standard_end_year, int) or self.standard_end_year < 1900:
            raise ValueError("standard_end_year는 유효한 연도 정수여야 합니다.")
        if self.as_of_date is not None:
            try:
                pd.Timestamp(self.as_of_date)
            except Exception as e:
                raise ValueError("as_of_date는 pandas가 해석 가능한 날짜여야 합니다.") from e
        if self.market_calendar is not None and not str(self.market_calendar).strip():
            raise ValueError("market_calendar는 None 또는 비어 있지 않은 캘린더 이름이어야 합니다.")



@dataclass(frozen=True)
class TradingCostAssumptions:
    """거래비용 가정. 모든 값은 '거래대금 대비 bp' 단위의 비음수 값."""
    commission_bps: float = 0.0
    sell_tax_bps: float = 0.0
    spread_bps: float = 0.0
    slippage_bps: float = 0.0
    market_impact_bps: float = 0.0

    def __post_init__(self) -> None:
        for name in (
            "commission_bps", "sell_tax_bps", "spread_bps",
            "slippage_bps", "market_impact_bps",
        ):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value < 0:
                raise ValueError(f"{name}은 0 이상의 유한한 bp 값이어야 합니다.")


def calculate_trading_cost_fraction(
    buy_turnover: pd.Series,
    sell_turnover: pd.Series,
    assumptions: TradingCostAssumptions,
) -> pd.Series:
    """
    리밸런싱 시점의 거래비용률을 계산한다.

    buy_turnover / sell_turnover 정의:
    - 각 값은 해당 시점 NAV 대비 실제 매수/매도 거래대금 비율이다.
      예: NAV의 30%를 사고 30%를 팔면 각각 0.30.
    - commission/spread/slippage/market_impact는 매수+매도 양쪽 거래대금에 적용한다.
    - sell_tax는 매도 거래대금에만 적용한다.
    - spread_bps는 '실효 거래비용 bp'로 넣는다. 호가의 왕복 스프레드 자체를 넣을 경우
      전략의 체결가 정의에 따라 1/2 적용 여부를 upstream에서 먼저 정한다.
    """
    b = pd.to_numeric(buy_turnover, errors="coerce").astype(float)
    s = pd.to_numeric(sell_turnover, errors="coerce").astype(float)
    idx = b.index.union(s.index)
    b = b.reindex(idx)
    s = s.reindex(idx)
    if b.isna().any() or s.isna().any():
        raise AssertionError("매수/매도 turnover 인덱스가 일치하지 않거나 결측치가 있습니다.")
    if (b < 0).any() or (s < 0).any():
        raise ValueError("turnover는 음수일 수 없습니다.")

    common_bps = (
        assumptions.commission_bps
        + assumptions.spread_bps
        + assumptions.slippage_bps
        + assumptions.market_impact_bps
    )
    cost = (b + s) * (common_bps / 10_000.0) + s * (assumptions.sell_tax_bps / 10_000.0)
    if (cost >= 1.0).any():
        raise ValueError("한 시점의 거래비용이 NAV의 100% 이상입니다. turnover/bp 가정을 확인하십시오.")
    cost.name = "cost_fraction"
    return cost


def apply_trading_costs_to_returns(
    gross_returns: pd.Series,
    buy_turnover: pd.Series,
    sell_turnover: pd.Series,
    assumptions: TradingCostAssumptions,
) -> pd.DataFrame:
    """
    gross 수익률에 리밸런싱 거래비용을 적용해 net 수익률/NAV를 만든다.

    비용은 해당 수익기간 시작 시점에 차감한 것으로 처리:
        net_gross = (1 - cost_fraction) * (1 + gross_return)
    전략의 실제 체결시점이 다르면 upstream 포트폴리오 엔진에서 일별로 직접 반영한다.
    """
    r = pd.to_numeric(gross_returns, errors="coerce").astype(float)
    if r.isna().any() or not np.isfinite(r.to_numpy()).all():
        raise AssertionError("gross_returns에 결측/비정상 값이 있습니다.")
    if (r <= -1.0).any():
        raise ValueError("gross_return은 -100% 이하여서는 안 됩니다.")

    b = pd.to_numeric(buy_turnover, errors="coerce").astype(float).reindex(r.index)
    s = pd.to_numeric(sell_turnover, errors="coerce").astype(float).reindex(r.index)
    if b.isna().any() or s.isna().any():
        raise AssertionError("gross_returns와 turnover의 날짜가 일치하지 않습니다.")
    cost = calculate_trading_cost_fraction(b, s, assumptions).reindex(r.index)
    net = (1.0 - cost) * (1.0 + r) - 1.0

    out = pd.DataFrame({
        "gross_return": r,
        "buy_turnover": b,
        "sell_turnover": s,
        "cost_fraction": cost,
        "net_return": net,
        "gross_nav": (1.0 + r).cumprod(),
        "net_nav": (1.0 + net).cumprod(),
    })
    out.attrs["cost_assumptions"] = {
        "commission_bps": assumptions.commission_bps,
        "sell_tax_bps": assumptions.sell_tax_bps,
        "spread_bps": assumptions.spread_bps,
        "slippage_bps": assumptions.slippage_bps,
        "market_impact_bps": assumptions.market_impact_bps,
    }
    return out


# =========================================================
# 1-A. 표준 체결 / 포트폴리오 엔진 (v2-16)
# =========================================================

@dataclass(frozen=True)
class ExecutionAssumptions:
    """범용 목표비중 전략의 표준 체결 가정.

    기본값은 신호일 종가로 신호를 만든 뒤 다음 거래세션 종가에 리밸런싱한다.
    이 엔진은 next-close 기준의 보수적 공통 기준선이며, next-open/VWAP처럼 장중
    체결이 필요한 전략은 별도 체결 엔진을 사용하되 동일한 출력 계약을 맞춘다.
    """
    execution_lag_sessions: int = 1
    execution_price: str = "next_close"
    allow_short: bool = False
    max_gross_exposure: float = 1.0
    weight_tolerance: float = 1e-10

    def __post_init__(self) -> None:
        if not isinstance(self.execution_lag_sessions, int) or self.execution_lag_sessions < 1:
            raise ValueError("execution_lag_sessions는 선견편향 방지를 위해 1 이상의 정수여야 합니다.")
        if self.execution_price != "next_close":
            raise ValueError("범용 엔진은 현재 next_close만 지원합니다. next_open/VWAP은 별도 체결 엔진이 필요합니다.")
        if not np.isfinite(float(self.max_gross_exposure)) or self.max_gross_exposure <= 0:
            raise ValueError("max_gross_exposure는 0보다 큰 유한한 값이어야 합니다.")
        if self.weight_tolerance < 0:
            raise ValueError("weight_tolerance는 0 이상이어야 합니다.")


def _validate_target_weights(
    target_weights: pd.DataFrame,
    assets: Sequence[str],
    assumptions: ExecutionAssumptions,
) -> pd.DataFrame:
    if not isinstance(target_weights, pd.DataFrame) or target_weights.empty:
        raise ValueError("target_weights는 비어 있지 않은 DataFrame이어야 합니다.")
    w = target_weights.copy()
    w.index = pd.to_datetime(w.index).normalize()
    if w.index.duplicated().any():
        raise AssertionError("target_weights에 중복 신호일이 있습니다.")
    w = w.sort_index()
    missing = [c for c in assets if c not in w.columns]
    extra = [c for c in w.columns if c not in assets]
    if missing or extra:
        raise KeyError(f"target_weights/가격 자산열 불일치: missing={missing}, extra={extra}")
    w = w[list(assets)].apply(pd.to_numeric, errors="coerce")
    if w.isna().any().any() or not np.isfinite(w.to_numpy(dtype=float)).all():
        raise AssertionError("target_weights에 결측/비정상 값이 있습니다.")
    tol = assumptions.weight_tolerance
    if not assumptions.allow_short and (w < -tol).any().any():
        raise ValueError("allow_short=False인데 음수 목표비중이 있습니다.")
    gross = w.abs().sum(axis=1)
    if (gross > assumptions.max_gross_exposure + tol).any():
        bad = gross[gross > assumptions.max_gross_exposure + tol].iloc[0]
        raise ValueError(f"목표 총익스포저가 한도를 초과합니다: {bad:.6f}")
    if not assumptions.allow_short and (w.sum(axis=1) > 1.0 + tol).any():
        raise ValueError("롱온리 목표비중 합계가 1을 초과합니다.")
    return w


def _schedule_signal_execution_dates(
    trading_index: pd.DatetimeIndex,
    signal_index: pd.DatetimeIndex,
    lag_sessions: int,
) -> Dict[pd.Timestamp, pd.Timestamp]:
    """신호일 이후 lag_sessions번째 거래세션을 체결일로 매핑한다."""
    idx = pd.DatetimeIndex(pd.to_datetime(trading_index)).normalize().sort_values().unique()
    out: Dict[pd.Timestamp, pd.Timestamp] = {}
    used_exec: set[pd.Timestamp] = set()
    for signal_date in pd.DatetimeIndex(signal_index):
        signal_date = pd.Timestamp(signal_date).normalize()
        first_future = int(idx.searchsorted(signal_date, side="right"))
        pos = first_future + lag_sessions - 1
        if pos >= len(idx):
            raise ValueError(f"신호일 {signal_date.date()}의 t+{lag_sessions} 체결일 데이터가 없습니다.")
        execution_date = pd.Timestamp(idx[pos])
        if execution_date in used_exec:
            raise ValueError(f"서로 다른 신호가 같은 체결일 {execution_date.date()}에 매핑됩니다.")
        used_exec.add(execution_date)
        out[signal_date] = execution_date
    return out


def simulate_target_weight_portfolio(
    close_prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    cost_assumptions: Optional[TradingCostAssumptions] = None,
    execution_assumptions: Optional[ExecutionAssumptions] = None,
    tradable_mask: Optional[pd.DataFrame] = None,
    explicit_delisting_returns: Optional[pd.DataFrame] = None,
    initial_capital: float = 1.0,
) -> Dict[str, Any]:
    """목표비중 신호를 t+1 체결, drift, turnover, 비용, 일별 NAV로 변환한다.

    시점 규칙:
    - signal t: t 종가까지 이용 가능한 정보로 목표비중을 만든다.
    - execution t+1(default): t+1 종가 수익은 기존 포지션이 먼저 받는다.
      그 종가에서 새 목표비중으로 리밸런싱한 뒤 다음 세션부터 새 비중 수익이 반영된다.
    - 따라서 t 종가 신호를 t 종가에 체결하거나 t+1 close-to-close 수익을 새 포지션에
      소급 적용하는 선견편향을 허용하지 않는다.

    한계:
    - 원천 가격 결측을 거래정지/상폐라고 임의 해석하지 않는다.
    - 보유 중 결측 수익률은 explicit_delisting_returns 등 검증된 명시적 자료가 없으면 실패한다.
    """
    if not isinstance(close_prices, pd.DataFrame) or close_prices.empty:
        raise ValueError("close_prices는 비어 있지 않은 DataFrame이어야 합니다.")
    ex = execution_assumptions or ExecutionAssumptions()
    costs = cost_assumptions or TradingCostAssumptions()
    if not np.isfinite(float(initial_capital)) or initial_capital <= 0:
        raise ValueError("initial_capital은 0보다 커야 합니다.")

    px = close_prices.copy()
    px.index = pd.to_datetime(px.index).normalize()
    px = px.sort_index()
    if px.index.duplicated().any():
        raise AssertionError("close_prices에 중복 날짜가 있습니다.")
    px = px.apply(pd.to_numeric, errors="coerce")
    if (px.dropna() <= 0).any().any():
        raise AssertionError("close_prices에 0 이하 가격이 있습니다.")
    assets = list(px.columns)
    weights_signal = _validate_target_weights(target_weights, assets, ex)
    schedule = _schedule_signal_execution_dates(px.index, weights_signal.index, ex.execution_lag_sessions)
    execution_targets = {exec_dt: weights_signal.loc[sig].astype(float) for sig, exec_dt in schedule.items()}

    mask = None
    if tradable_mask is not None:
        mask = tradable_mask.copy()
        mask.index = pd.to_datetime(mask.index).normalize()
        mask = mask.reindex(index=px.index, columns=assets)
        if mask.isna().any().any():
            raise AssertionError("tradable_mask가 전체 가격 날짜/자산을 덮지 못합니다.")
        mask = mask.astype(bool)

    rets = px.pct_change(fill_method=None)
    if len(rets):
        rets.iloc[0] = 0.0
    if explicit_delisting_returns is not None:
        dr = explicit_delisting_returns.copy()
        dr.index = pd.to_datetime(dr.index).normalize()
        dr = dr.reindex(index=px.index, columns=assets)
        fill = rets.isna() & dr.notna()
        rets = rets.where(~fill, dr)

    current_w = pd.Series(0.0, index=assets, dtype=float)
    gross_nav = float(initial_capital)
    net_nav = float(initial_capital)
    nav_rows = []
    trade_rows = []
    weight_rows = []

    for i, dt in enumerate(px.index):
        r = rets.loc[dt].astype(float)
        held = current_w.abs() > ex.weight_tolerance
        if held.any() and r[held].isna().any():
            bad = list(r[held][r[held].isna()].index)
            raise RuntimeError(
                f"보유종목의 일별 수익률이 정의되지 않았습니다: date={dt.date()}, assets={bad}. "
                "거래정지/상장폐지/기업행위라면 명시적 처리자료를 제공하십시오. 0%로 조용히 대체하지 않습니다."
            )
        r = r.fillna(0.0)
        if (r < -1.0).any():
            raise ValueError(f"-100% 미만 자산수익률이 있습니다: {dt.date()}")

        portfolio_return = float((current_w * r).sum())
        if portfolio_return <= -1.0:
            raise RuntimeError(f"포트폴리오 NAV가 0 이하가 됩니다: {dt.date()}")
        gross_nav *= 1.0 + portfolio_return
        net_nav *= 1.0 + portfolio_return

        denom = 1.0 + portfolio_return
        current_w = current_w * (1.0 + r) / denom

        buy_to = sell_to = cost_fraction = 0.0
        signal_date = None
        if dt in execution_targets:
            target = execution_targets[dt].copy()
            if mask is not None:
                changing = (target - current_w).abs() > ex.weight_tolerance
                blocked = changing & (~mask.loc[dt])
                if blocked.any():
                    raise RuntimeError(
                        f"체결일에 거래불가 자산의 비중 변경을 시도했습니다: date={dt.date()}, "
                        f"assets={list(blocked[blocked].index)}"
                    )
            diff = target - current_w
            buy_to = float(diff.clip(lower=0.0).sum())
            sell_to = float((-diff.clip(upper=0.0)).sum())
            cost_fraction = float(calculate_trading_cost_fraction(
                pd.Series([buy_to], index=[dt]),
                pd.Series([sell_to], index=[dt]),
                costs,
            ).iloc[0])
            net_nav *= 1.0 - cost_fraction
            current_w = target
            signal_date = next(sig for sig, exdt in schedule.items() if exdt == dt)

        if gross_nav <= 0 or net_nav <= 0:
            raise RuntimeError(f"비용 반영 후 NAV가 0 이하입니다: {dt.date()}")

        nav_rows.append({
            "Date": dt,
            "Gross": gross_nav / initial_capital,
            "Net": net_nav / initial_capital,
            "portfolio_return_before_cost": portfolio_return,
            "cost_fraction": cost_fraction,
        })
        trade_rows.append({
            "Date": dt,
            "signal_date": signal_date,
            "buy_turnover": buy_to,
            "sell_turnover": sell_to,
            "traded_fraction": buy_to + sell_to,
            "one_way_turnover": 0.5 * (buy_to + sell_to),
            "cost_fraction": cost_fraction,
        })
        wr = {"Date": dt, **{a: float(current_w[a]) for a in assets}}
        wr["Cash"] = float(1.0 - current_w.sum())
        weight_rows.append(wr)

    daily_nav = pd.DataFrame(nav_rows).set_index("Date")
    trades = pd.DataFrame(trade_rows).set_index("Date")
    weights = pd.DataFrame(weight_rows).set_index("Date")
    schedule_df = pd.DataFrame([
        {"signal_date": sig, "execution_date": exdt}
        for sig, exdt in schedule.items()
    ])
    daily_nav.attrs["execution_assumptions"] = {
        "execution_lag_sessions": ex.execution_lag_sessions,
        "execution_price": ex.execution_price,
    }
    daily_nav.attrs["cost_assumptions"] = {
        "commission_bps": costs.commission_bps,
        "sell_tax_bps": costs.sell_tax_bps,
        "spread_bps": costs.spread_bps,
        "slippage_bps": costs.slippage_bps,
        "market_impact_bps": costs.market_impact_bps,
    }
    return {
        "daily_nav": daily_nav[["Gross", "Net"]],
        "daily_detail": daily_nav,
        "weights": weights,
        "trades": trades,
        "execution_schedule": schedule_df,
        "annualized_one_way_turnover": float(trades["one_way_turnover"].mean() * 252.0),
    }


def complete_monthly_nav_from_daily(
    daily_nav: pd.DataFrame,
    as_of_date: Optional[str | pd.Timestamp] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """정식 성과는 최근 완결월까지만, 최신 일별 NAV는 별도 스냅샷으로 분리한다."""
    d = validate_daily_nav(daily_nav)
    as_of = (pd.Timestamp(as_of_date) if as_of_date is not None else pd.Timestamp.today()).normalize()
    last_complete_month = (as_of.to_period("M") - (0 if as_of == as_of.to_period("M").end_time.normalize() else 1))
    cutoff = last_complete_month.to_timestamp("M")
    formal_daily = d.loc[d.index <= cutoff].copy()
    if formal_daily.empty:
        raise ValueError(f"최근 완결월 {cutoff.date()}까지 일별 NAV가 없습니다.")
    monthly = formal_daily.groupby(formal_daily.index.to_period("M")).tail(1).copy()
    monthly.index = monthly.index.to_period("M").to_timestamp("M")
    latest = d.iloc[-1]
    meta = {
        "formal_performance_end": cutoff,
        "latest_daily_date": d.index[-1],
        "latest_daily_nav": latest.to_dict(),
        "partial_current_month_excluded_from_formal_metrics": d.index[-1] > cutoff,
    }
    return formal_daily, monthly, meta


def run_execution_backtest(
    close_prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    config: BacktestConfig,
    cost_scenarios: Dict[str, TradingCostAssumptions],
    execution_assumptions: Optional[ExecutionAssumptions] = None,
    tradable_mask: Optional[pd.DataFrame] = None,
    explicit_delisting_returns: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """체결→비용→NAV→최근 완결월→4기간 성과를 한 번에 연결한다."""
    if not cost_scenarios:
        raise ValueError(
            "cost_scenarios가 비어 있습니다. 비용을 임의로 숨겨 결정하지 않습니다. "
            "최소/기준/보수적 가정을 명시적으로 전달하십시오."
        )
    combined_daily = None
    executions: Dict[str, Any] = {}
    gross_reference = None
    for name, cost in cost_scenarios.items():
        exout = simulate_target_weight_portfolio(
            close_prices=close_prices,
            target_weights=target_weights,
            cost_assumptions=cost,
            execution_assumptions=execution_assumptions,
            tradable_mask=tradable_mask,
            explicit_delisting_returns=explicit_delisting_returns,
            initial_capital=config.initial_capital,
        )
        executions[name] = exout
        d = exout["daily_nav"]
        if gross_reference is None:
            gross_reference = d["Gross"].copy()
            combined_daily = pd.DataFrame({"Gross": gross_reference})
        elif not np.allclose(gross_reference.to_numpy(), d["Gross"].to_numpy(), rtol=0, atol=1e-12):
            raise AssertionError("비용 시나리오에 따라 Gross NAV가 달라졌습니다.")
        combined_daily[f"Net_{name}"] = d["Net"]

    formal_daily, monthly, latest_meta = complete_monthly_nav_from_daily(
        combined_daily,
        as_of_date=config.as_of_date,
    )
    formal_daily.attrs["market_calendar"] = config.market_calendar
    monthly.attrs["market_calendar"] = config.market_calendar
    period_results = run_four_periods(monthly, config, formal_daily)
    return {
        "period_results": period_results,
        "formal_daily_nav": formal_daily,
        "formal_monthly_nav": monthly,
        "latest_daily_snapshot": latest_meta,
        "execution_scenarios": executions,
        "cost_scenarios": {
            k: {
                "commission_bps": v.commission_bps,
                "sell_tax_bps": v.sell_tax_bps,
                "spread_bps": v.spread_bps,
                "slippage_bps": v.slippage_bps,
                "market_impact_bps": v.market_impact_bps,
            } for k, v in cost_scenarios.items()
        },
    }


def generate_expanding_walk_forward_windows(
    index: Iterable[Any],
    min_train_observations: int,
    test_observations: int,
    step_observations: Optional[int] = None,
    embargo_observations: int = 0,
) -> pd.DataFrame:
    """시간 순서를 보존하는 expanding-window OOS 분할표를 생성한다."""
    idx = pd.DatetimeIndex(pd.to_datetime(list(index))).sort_values().unique()
    if min_train_observations < 2 or test_observations < 1:
        raise ValueError("min_train_observations>=2, test_observations>=1 이어야 합니다.")
    if embargo_observations < 0:
        raise ValueError("embargo_observations는 0 이상이어야 합니다.")
    step = step_observations or test_observations
    if step < 1:
        raise ValueError("step_observations는 1 이상이어야 합니다.")
    rows = []
    train_end_pos = min_train_observations - 1
    fold = 0
    while True:
        test_start_pos = train_end_pos + 1 + embargo_observations
        test_end_pos = test_start_pos + test_observations - 1
        if test_end_pos >= len(idx):
            break
        rows.append({
            "fold": fold,
            "train_start": idx[0],
            "train_end": idx[train_end_pos],
            "embargo_observations": embargo_observations,
            "test_start": idx[test_start_pos],
            "test_end": idx[test_end_pos],
            "train_observations": train_end_pos + 1,
            "test_observations": test_observations,
        })
        fold += 1
        train_end_pos += step
    if not rows:
        raise ValueError("주어진 길이로 생성 가능한 walk-forward fold가 없습니다.")
    return pd.DataFrame(rows)


def summarize_robustness_results(
    named_results: Dict[str, Dict[str, Dict[str, Any]]],
    period_key: str = "from_2000",
) -> pd.DataFrame:
    """시작일/리밸런싱/종목수/비용 등 여러 시나리오의 CURRENT 지표를 한 표로 결합한다."""
    rows = []
    for scenario, four_period in named_results.items():
        if period_key not in four_period:
            raise KeyError(f"{scenario}: period_key={period_key}가 없습니다.")
        m = four_period[period_key]["metrics"].reset_index().rename(columns={"index": "전략"})
        m.insert(0, "scenario", scenario)
        rows.append(m)
    return pd.concat(rows, ignore_index=True)


def calculate_benchmark_statistics(
    monthly_nav: pd.DataFrame,
    strategy_col: str,
    benchmark_col: str,
    config: BacktestConfig,
) -> Dict[str, float]:
    """월별 NAV 기준 tracking error / IR / alpha / beta / downside capture를 계산한다."""
    m = validate_monthly_nav(monthly_nav[[strategy_col, benchmark_col]], config, enforce_expected=False)
    rs = monthly_returns_from_nav(m[strategy_col])
    rb = monthly_returns_from_nav(m[benchmark_col])
    x = pd.concat([rs.rename("s"), rb.rename("b")], axis=1).dropna()
    active = x["s"] - x["b"]
    te = float(active.std(ddof=1) * np.sqrt(config.periods_per_year)) if len(active) > 1 else np.nan
    ir = float(active.mean() / active.std(ddof=1) * np.sqrt(config.periods_per_year)) if len(active) > 1 and active.std(ddof=1) > 0 else np.nan
    beta = float(x["s"].cov(x["b"]) / x["b"].var(ddof=1)) if len(x) > 1 and x["b"].var(ddof=1) > 0 else np.nan
    rf_m = (1.0 + config.risk_free_rate) ** (1.0 / config.periods_per_year) - 1.0
    alpha = float(((x["s"] - rf_m).mean() - beta * (x["b"] - rf_m).mean()) * config.periods_per_year) if np.isfinite(beta) else np.nan
    down = x[x["b"] < 0]
    downside_capture = float(down["s"].mean() / down["b"].mean()) if len(down) and down["b"].mean() != 0 else np.nan
    return {
        "tracking_error": te,
        "information_ratio": ir,
        "beta": beta,
        "alpha_annualized_arithmetic": alpha,
        "downside_capture": downside_capture,
    }


KRX_TOTAL_RETURN_LIMITATION = """
현재 data/krx_equities/yearly의 원천 가격/시총 패널만으로 현금배당, 상장폐지 회수액,
모든 합병/분할/증자 효과를 완전한 투자자 총수익률로 자동 복원한다고 가정하지 않는다.
한국 개별주 전략에서 total return이 필요하면 검증된 배당/기업행위/상폐 처리 원천을 추가하고,
그 정의와 이용가능일을 기록해야 한다. 해당 원천이 없으면 price-return 기반 결과로 명시하거나
분석을 중단한다. 임의의 배당률/상폐손실을 생성하지 않는다.
"""


# =========================================================
# 2. 데이터 검증
# =========================================================

def _basic_nav_checks(df: pd.DataFrame, name: str) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{name}는 pandas.DataFrame이어야 합니다.")
    if df.empty:
        raise ValueError(f"{name}가 비어 있습니다.")
    if df.index.duplicated().any():
        raise AssertionError(f"{name}: 중복 날짜가 존재합니다.")
    if not df.index.is_monotonic_increasing:
        raise AssertionError(f"{name}: 날짜가 오름차순이 아닙니다.")
    if df.isna().any().any():
        raise AssertionError(f"{name}: 결측치가 있습니다.")
    if not np.isfinite(df.to_numpy(dtype=float)).all():
        raise AssertionError(f"{name}: 무한대/비정상 값이 있습니다.")
    if not (df > 0).all().all():
        raise AssertionError(f"{name}: NAV는 0보다 커야 합니다.")


def validate_monthly_nav(nav: pd.DataFrame, config: BacktestConfig, enforce_expected: bool = True) -> pd.DataFrame:
    df = nav.copy()
    raw_index = pd.to_datetime(df.index)

    # 실행일(또는 명시한 as_of_date)보다 뒤의 월말은 아직 완결되지 않은 미래 월이다.
    # 단순히 9/17 자료를 9/30으로 라벨만 바꾸어 통과시키는 것을 차단한다.
    as_of = (pd.Timestamp(config.as_of_date) if config.as_of_date is not None else pd.Timestamp.today()).normalize()
    raw_month_end = raw_index.to_period("M").to_timestamp("M")
    if len(raw_month_end) and raw_month_end[-1].normalize() > as_of:
        raise AssertionError(
            f"monthly_nav: 아직 끝나지 않은 월을 포함할 수 없습니다. "
            f"마지막 월말={raw_month_end[-1].date()}, 기준일={as_of.date()}. "
            "완결된 마지막 월까지만 사용하십시오."
        )

    # 월별 NAV 계약: 각 관측치는 해당 월의 완결된 월말 값이어야 한다.
    # 실제 마지막 거래일 라벨은 허용하되, 월말에서 7일 이상 떨어진 중간월 값은
    # 임의로 월말 NAV로 승격시키지 않는다.
    month_end = raw_index.to_period("M").to_timestamp("M")
    days_to_month_end = (month_end.normalize() - raw_index.normalize()).days
    if (days_to_month_end > 7).any():
        bad_i = int(np.flatnonzero(days_to_month_end > 7)[0])
        raise AssertionError(
            f"monthly_nav: 월 중간 관측치를 월말 NAV로 사용할 수 없습니다. "
            f"날짜={raw_index[bad_i].date()}, 해당 월말={month_end[bad_i].date()}. "
            "완결된 월말(또는 월말에 충분히 가까운 마지막 거래일) 자료를 사용하십시오."
        )

    # 마지막 관측월은 뒤에 다음 달 자료가 없어 '그 달이 실제로 끝났는지'를
    # 데이터 자체로 증명할 수 없다. 따라서 마지막 관측치는 명시적인 월말 라벨만
    # 허용한다. 실제 마지막 거래일 자료를 쓸 때는 월별 집계 후 Period(M)->month-end로
    # 라벨을 정규화해 전달해야 한다. 이 규칙으로 9/25 같은 미완결 월 자료가
    # 9/30 월말 NAV로 조용히 승격되는 것을 막는다.
    if len(raw_index) > 0 and raw_index[-1].normalize() != month_end[-1].normalize():
        raise AssertionError(
            f"monthly_nav: 마지막 관측월은 명시적인 월말 라벨이어야 합니다. "
            f"마지막 날짜={raw_index[-1].date()}, 해당 월말={month_end[-1].date()}. "
            "미완결 월을 포함하지 말고, 완결된 월별 자료는 월말 라벨로 정규화하십시오."
        )

    df.index = month_end
    df = df.sort_index()
    _basic_nav_checks(df, "monthly_nav")

    actual = df.index.to_period("M")
    expected_full = pd.period_range(actual[0], actual[-1], freq="M")
    if len(actual) != len(expected_full):
        raise AssertionError(
            f"monthly_nav: 중간 월이 누락되었습니다. "
            f"연속기간 기대 {len(expected_full)}개 / 실제 {len(actual)}개"
        )

    if enforce_expected and config.expected_start is not None:
        e = pd.Period(config.expected_start, freq="M")
        if actual[0] != e:
            raise AssertionError(f"시작월 불일치: 기대 {e}, 실제 {actual[0]}")

    if enforce_expected and config.expected_end is not None:
        e = pd.Period(config.expected_end, freq="M")
        if actual[-1] != e:
            raise AssertionError(f"종료월 불일치: 기대 {e}, 실제 {actual[-1]}")

    if enforce_expected and config.expected_months is not None and len(df) != config.expected_months:
        raise AssertionError(
            f"관측치 수 불일치: 기대 {config.expected_months}개 / 실제 {len(df)}개"
        )
    return df


def validate_daily_nav(nav: pd.DataFrame) -> pd.DataFrame:
    """거래일 NAV 검증. 주말/휴일이 있으므로 달력상 연속일을 강제하지 않는다."""
    attrs = dict(getattr(nav, "attrs", {}))
    df = nav.copy()
    df.index = pd.to_datetime(df.index).normalize()
    df = df.sort_index()
    _basic_nav_checks(df, "daily_nav")
    df.attrs.update(attrs)
    return df


# =========================================================
# 3. 표준 기간 4개
# =========================================================

def standard_period_windows(
    monthly_nav: pd.DataFrame,
    config: BacktestConfig,
) -> Dict[str, Tuple[pd.Timestamp, pd.Timestamp, str]]:
    """
    표준 4개 기간 생성.

    1. book_validation : 책 기간 검증
    2. from_2000       : 2000~가용 최신일(최대 standard_end_year)
    3. from_2021       : 2021~가용 최신일(최대 standard_end_year)
    4. longest         : 가능한 최장기간~가용 최신일(최대 standard_end_year)
    """
    m = validate_monthly_nav(monthly_nav, config)
    data_start = m.index[0]
    data_end = min(m.index[-1], pd.Timestamp(f"{config.standard_end_year}-12-31"))

    if config.book_start is None or config.book_end is None:
        raise ValueError("책 기간 검증을 위해 config.book_start와 config.book_end를 지정해야 합니다.")

    book_start_raw = pd.Timestamp(config.book_start)
    book_end_raw = pd.Timestamp(config.book_end)
    # 월별 NAV이므로 책 시작/종료일은 해당 월의 월말로 정규화한다.
    book_start = book_start_raw.to_period("M").to_timestamp("M")
    requested_book_end = book_end_raw.to_period("M").to_timestamp("M")
    if requested_book_end > data_end:
        raise ValueError(
            f"책 검증 종료월 {requested_book_end:%Y-%m}까지 데이터가 필요하지만 "
            f"실제 데이터는 {data_end:%Y-%m}까지만 있습니다. 책 기간을 조용히 축약하지 않습니다."
        )
    book_end = requested_book_end
    if book_start.to_period("M") < data_start.to_period("M"):
        raise ValueError(
            f"책 검증 시작월 {book_start:%Y-%m}이 데이터 시작월 {data_start:%Y-%m}보다 빠릅니다. "
            "장기 프록시/백필 데이터를 먼저 준비하십시오."
        )
    if book_end < book_start:
        raise ValueError("책 검증 종료일이 시작일보다 빠릅니다.")

    starts = {
        "book_validation": book_start,
        "from_2000": pd.Timestamp("2000-01-01"),
        "from_2021": pd.Timestamp("2021-01-01"),
        "longest": data_start,
    }

    # 고정 기간은 데이터가 부족하다고 조용히 뒤로 당기지 않는다.
    # 필요한 과거 자료가 없으면 프록시/백필을 먼저 준비하도록 명시적으로 실패한다.
    if data_start.to_period("M") > pd.Period("2000-01", freq="M"):
        raise ValueError(
            f"2000~기간 고정 조건을 충족할 수 없습니다. 데이터 시작월={data_start:%Y-%m}. "
            "2000-01부터의 프록시/백필 데이터를 준비하십시오."
        )
    if data_start.to_period("M") > pd.Period("2021-01", freq="M"):
        raise ValueError(
            f"2021~기간 고정 조건을 충족할 수 없습니다. 데이터 시작월={data_start:%Y-%m}. "
            "2021-01부터의 데이터를 준비하십시오."
        )

    return {
        "book_validation": (book_start, book_end, f"책 검증 {book_start:%Y-%m}~{book_end:%Y-%m}"),
        "from_2000": (starts["from_2000"], data_end, f"2000~{data_end:%Y-%m}"),
        "from_2021": (starts["from_2021"], data_end, f"2021~{data_end:%Y-%m}"),
        "longest": (data_start, data_end, f"최장 {data_start:%Y-%m}~{data_end:%Y-%m}"),
    }


def _slice_and_rebase(nav: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """기간을 자르고 각 전략 NAV를 기간 시작 직전 기준 1.0으로 재기준화."""
    x = nav.loc[(nav.index >= start) & (nav.index <= end)].copy()
    if x.empty:
        raise ValueError(f"선택 기간에 데이터가 없습니다: {start.date()}~{end.date()}")

    # 첫 관측값 자체를 1로 만들어 첫 기간 수익을 누락시키지 않도록,
    # 가능하면 직전 관측값을 기준으로 나눈다.
    pos = nav.index.searchsorted(x.index[0])
    if pos > 0:
        base = nav.iloc[pos - 1].astype(float)
        baseline_date = nav.index[pos - 1]
    else:
        base = pd.Series(1.0, index=nav.columns)
        baseline_date = None
    out = x.astype(float).div(base, axis=1)
    out.attrs.update(getattr(nav, "attrs", {}))
    out.attrs["baseline_date"] = baseline_date
    return out


# =========================================================
# 4. 성과/위험 지표
# =========================================================

def monthly_returns_from_nav(nav: pd.Series) -> pd.Series:
    prior_date = nav.index[0] - pd.offsets.MonthEnd(1)
    extended = pd.concat([pd.Series([1.0], index=[prior_date]), nav.astype(float)])
    return extended.pct_change().dropna()


def drawdown_series(nav: pd.Series) -> pd.Series:
    running_peak = np.maximum.accumulate(np.r_[1.0, nav.to_numpy(dtype=float)])[1:]
    return pd.Series(nav.to_numpy(dtype=float) / running_peak - 1.0, index=nav.index)


def max_recovery_duration(nav: pd.Series) -> Dict[str, Any]:
    """
    일별/월별 공용. 고점 이후 이전 고점을 회복할 때까지의 최대 기간.
    기간 첫 관측치가 1 미만이면 실제 고점은 첫 관측 직전의 기준 NAV=1 시점이므로
    빈도에 맞는 직전 기준시점을 추정해 회복기간을 과소계상하지 않는다.
    """
    s = nav.astype(float).sort_index()
    inherited_baseline = nav.attrs.get("baseline_date") if hasattr(nav, "attrs") else None
    if inherited_baseline is not None:
        baseline_date = pd.Timestamp(inherited_baseline)
    else:
        if len(s) >= 2:
            median_days = float(np.median(np.diff(s.index.values).astype('timedelta64[D]').astype(int)))
        else:
            median_days = 1.0
        if median_days >= 20:
            baseline_date = (s.index[0].to_period("M") - 1).to_timestamp("M")
        else:
            # 실제 직전 거래일을 모르는 독립 입력에서는 최소한 주말을 건너뛴
            # 직전 영업일을 기준점으로 사용한다.
            baseline_date = s.index[0] - pd.offsets.BDay(1)

    peak_value = 1.0
    peak_date = baseline_date
    underwater_start: Optional[pd.Timestamp] = None
    longest_days = 0

    for dt, value in s.items():
        if value >= peak_value:
            if underwater_start is not None:
                longest_days = max(longest_days, (dt - underwater_start).days)
                underwater_start = None
            peak_value = value
            peak_date = dt
        else:
            if underwater_start is None:
                underwater_start = peak_date

    if underwater_start is not None:
        longest_days = max(longest_days, (s.index[-1] - underwater_start).days)

    return {
        "days": int(longest_days),
        "months": round(longest_days / 30.4375, 1),
    }


def _daily_full_coverage(
    dnav: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    allow_partial_first_month: bool = False,
    market_calendar: Optional[str] = None,
) -> bool:
    """일별 자료가 위험측정 구간을 충분히 덮는지 확인한다.

    우선순위:
    1) market_calendar(XKRX/XNYS 등)가 주어지면 exchange_calendars의 실제 세션과 정확히 대조한다.
    2) 캘린더가 없을 때만 평일 수 기반 보수적 휴리스틱으로 fallback한다.

    이렇게 해야 한국의 추석/설 연휴처럼 정상적인 장기 휴장을 데이터 누락으로 오판하지 않는다.
    """
    effective_start = start if allow_partial_first_month else start.to_period("M").start_time
    effective_end = end.to_period("M").end_time
    x = dnav.loc[(dnav.index >= effective_start) & (dnav.index <= effective_end)]
    if x.empty:
        return False
    sm, em = start.to_period("M"), end.to_period("M")
    if x.index[0].to_period("M") != sm or x.index[-1].to_period("M") != em:
        return False

    calendar_name = market_calendar or dnav.attrs.get("market_calendar")
    if calendar_name:
        try:
            import exchange_calendars as xcals  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                f"market_calendar={calendar_name}를 사용하려면 exchange-calendars가 필요합니다."
            ) from e
        try:
            cal = xcals.get_calendar(str(calendar_name))
        except Exception as e:
            raise ValueError(f"알 수 없는 market_calendar입니다: {calendar_name}") from e

        expected_start = pd.Timestamp(effective_start).normalize()
        expected_end = pd.Timestamp(effective_end).normalize()
        expected = pd.DatetimeIndex(cal.sessions_in_range(expected_start, expected_end))
        if expected.tz is not None:
            expected = expected.tz_localize(None)
        actual = pd.DatetimeIndex(x.index).normalize().unique().sort_values()
        missing = expected.difference(actual)
        # 명시한 거래소 캘린더에 없는 추가 날짜도 일별 NAV 생성 로직 오류 가능성이 있으므로 차단한다.
        extra = actual.difference(expected)
        return len(missing) == 0 and len(extra) == 0

    # 캘린더를 지정하지 않은 경우에만 휴리스틱을 사용한다.
    if not allow_partial_first_month and x.index[0].day > 7:
        return False
    if (x.index[-1].to_period("M").end_time.normalize() - x.index[-1]).days > 7:
        return False

    counts = pd.Series(1, index=x.index.to_period("M")).groupby(level=0).sum()
    months = pd.period_range(sm, em, freq="M")
    counts = counts.reindex(months, fill_value=0)
    weekday_counts = pd.Series(
        {m: len(pd.bdate_range(m.start_time, m.end_time)) for m in months}, dtype=float
    )
    coverage_ratio = counts.astype(float) / weekday_counts
    coverage_to_check = coverage_ratio.iloc[1:] if allow_partial_first_month else coverage_ratio
    if (coverage_to_check < 0.85).any():
        return False

    check_x = x
    if allow_partial_first_month and len(months) > 1:
        check_x = x[x.index.to_period("M") != months[0]]
    if len(check_x) >= 2:
        gaps = pd.Series(check_x.index[1:] - check_x.index[:-1])
        if (gaps.dt.days > 7).any():
            return False
    return True

def _check_daily_monthly_consistency(mnav: pd.DataFrame, dnav: pd.DataFrame, tolerance: float = 5e-4) -> None:
    """같은 전략의 월말 NAV가 일별 NAV의 월말 값과 일치하는지 확인."""
    daily_month_end = dnav.groupby(dnav.index.to_period("M")).tail(1).copy()
    daily_month_end.index = daily_month_end.index.to_period("M")
    mm = mnav.copy(); mm.index = mm.index.to_period("M")
    common = mm.index.intersection(daily_month_end.index)
    if len(common) == 0:
        raise AssertionError("daily_nav와 monthly_nav의 겹치는 월이 없습니다.")
    for c in mnav.columns:
        a = mm.loc[common, c].astype(float)
        b = daily_month_end.loc[common, c].astype(float)
        rel = (a / b - 1.0).abs()
        bad = rel[rel > tolerance]
        if not bad.empty:
            p = bad.index[0]
            raise AssertionError(
                f"daily/monthly NAV 불일치: 전략={c}, 월={p}, 상대오차={bad.iloc[0]:.6f}. "
                "성과와 위험지표에 서로 다른 NAV를 사용하고 있을 가능성이 있습니다."
            )


def calculate_metrics(
    monthly_nav: pd.DataFrame,
    config: BacktestConfig,
    daily_nav: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    CAGR/Sharpe/변동성 = 월별 NAV
    MDD/회복기간 = 일별 NAV 우선, 없으면 월별 fallback
    """
    mnav = validate_monthly_nav(monthly_nav, config, enforce_expected=False)
    dnav = validate_daily_nav(daily_nav) if daily_nav is not None else None

    if dnav is not None:
        missing = [c for c in mnav.columns if c not in dnav.columns]
        if missing:
            raise AssertionError(f"daily_nav에 전략 열이 없습니다: {missing}")

        # 공개 함수 calculate_metrics()를 직접 호출하더라도 월/일 NAV를
        # 서로 다른 전략에서 섞어 쓰지 못하게 한다.
        if dnav.attrs.get("coverage_verified", False):
            _check_daily_monthly_consistency(mnav, dnav)
        elif not _daily_full_coverage(
            dnav, mnav.index[0], mnav.index[-1], market_calendar=config.market_calendar
        ):
            dnav = None
        else:
            _check_daily_monthly_consistency(mnav, dnav)

    rows = []
    for name in mnav.columns:
        s_month = mnav[name].astype(float)
        r = monthly_returns_from_nav(s_month)
        # 일반적인 완전월 자료는 월수/12가 정확하고 재현성이 높다.
        # 다만 데이터 inception이 월 중간인 최장기간처럼 실제 기준일을 알고 있는 경우에는
        # 짧은 첫 달을 1개월로 과대계상하지 않도록 실제 경과일수로 CAGR을 연환산한다.
        # 완전월 구간은 월수/periods_per_year로 연환산한다. 실제 일수 연환산은
        # 월중 inception처럼 명시적으로 performance_baseline_date를 복원한 경우에만 사용한다.
        performance_baseline = mnav.attrs.get("performance_baseline_date")
        if performance_baseline is not None:
            elapsed_days = (s_month.index[-1] - pd.Timestamp(performance_baseline)).days
            if elapsed_days <= 0:
                raise AssertionError("CAGR 기준일이 종료일보다 늦거나 같습니다.")
            years = elapsed_days / 365.2425
        else:
            years = len(r) / config.periods_per_year
        final_multiple = float(s_month.iloc[-1])
        cagr = final_multiple ** (1.0 / years) - 1.0

        # inception이 월중이면 첫 월 수익은 완전한 한 달 수익이 아니다.
        # CAGR에는 실제 경과일수로 반영하되 Sharpe/변동성의 월별 표본에서는 제외한다.
        stats_r = r
        if performance_baseline is not None and len(r) > 0:
            pb = pd.Timestamp(performance_baseline)
            if pb.to_period("M") == s_month.index[0].to_period("M"):
                stats_r = r.iloc[1:]
        if len(stats_r) < 2:
            annual_std = np.nan
            sharpe = np.nan
        else:
            annual_std = float(stats_r.std(ddof=1) * np.sqrt(config.periods_per_year))
            monthly_rf = (1.0 + config.risk_free_rate) ** (1.0 / config.periods_per_year) - 1.0
            excess = stats_r - monthly_rf
            denom = float(excess.std(ddof=1))
            sharpe = float(excess.mean() / denom * np.sqrt(config.periods_per_year)) if denom > 0 else np.nan

        if dnav is not None:
            risk_s = dnav[name].astype(float)
            risk_source = "daily"
        else:
            risk_s = s_month
            risk_source = "monthly_fallback"

        dd = drawdown_series(risk_s)
        recovery = max_recovery_duration(risk_s)
        downside = np.minimum(excess.to_numpy(dtype=float), 0.0) if len(stats_r) >= 2 else np.array([])
        downside_dev = float(np.sqrt(np.mean(np.square(downside))) * np.sqrt(config.periods_per_year)) if len(downside) else np.nan
        annual_excess_mean = float(excess.mean() * config.periods_per_year) if len(stats_r) >= 2 else np.nan
        sortino = annual_excess_mean / downside_dev if np.isfinite(downside_dev) and downside_dev > 0 else np.nan
        mdd_value = float(dd.min())
        calmar = cagr / abs(mdd_value) if mdd_value < 0 else np.nan
        monthly_win_rate = float((r > 0).mean()) if len(r) else np.nan

        rows.append({
            "전략": name,
            "CAGR": cagr,
            "누적수익률": final_multiple - 1.0,
            "MDD": mdd_value,
            "MDD_source": risk_source,
            "Sharpe": sharpe,
            "Sortino": sortino,
            "Calmar": calmar,
            "월간승률": monthly_win_rate,
            "연환산_표준편차": annual_std,
            "최대회복기간_개월": recovery["months"],
            "최대회복기간_일": recovery["days"],
            "최종배수": final_multiple,
            "최종자산": final_multiple * config.initial_capital,
        })

    return pd.DataFrame(rows).set_index("전략")


# =========================================================
# 5. 표준 4기간 실행
# =========================================================

def _enforce_input_nav_scale(monthly_nav: pd.DataFrame) -> None:
    """원본 monthly NAV는 inception 직전 1.0 기준 누적배수여야 한다.

    월별 NAV만으로 임의의 상수배 스케일을 완벽히 역추론할 수는 없다. 따라서
    템플릿 계약상 첫 월 NAV는 1.0 부근이어야 하며, 명백한 2/100/1000 기준
    wealth index는 차단한다. 월간 ±50%를 넘는 전략은 반드시 직전 기준 NAV=1.0
    행을 포함하거나 upstream에서 1.0 기준 누적배수로 정규화해 전달한다.
    """
    first = monthly_nav.iloc[0].astype(float)
    if ((first < 0.5) | (first > 1.5)).any():
        raise ValueError(
            "monthly_nav는 데이터 inception 직전 기준 1.0의 누적배수여야 합니다. "
            f"첫 관측 NAV 범위={first.min():.6g}~{first.max():.6g}. "
            "2/100/1000 기준 wealth index나 임의 스케일은 먼저 1.0 기준으로 변환하십시오."
        )


def run_four_periods(
    monthly_nav: pd.DataFrame,
    config: BacktestConfig,
    daily_nav: Optional[pd.DataFrame] = None,
) -> Dict[str, Dict[str, Any]]:
    """4개 표준 기간을 모두 계산한다."""
    mnav = validate_monthly_nav(monthly_nav, config)
    _enforce_input_nav_scale(mnav)
    dnav = validate_daily_nav(daily_nav) if daily_nav is not None else None
    windows = standard_period_windows(mnav, config)

    results: Dict[str, Dict[str, Any]] = {}
    for key, (start, end, label) in windows.items():
        m_slice = _slice_and_rebase(mnav, start, end)

        # 일별 위험지표는 해당 기간 전체 월을 실제 일별 데이터가 덮을 때만 사용한다.
        # 일부 기간만 일별로 존재하는 경우에는 MDD를 과소평가할 수 있으므로 월별 fallback.
        d_slice = None
        if dnav is not None:
            risk_start_month = start.to_period("M")
            risk_end_month = end.to_period("M")
            is_global_start = risk_start_month == mnav.index[0].to_period("M")

            # 고정기간은 월초부터 완전 커버를 요구한다. 최장기간이 데이터 inception 월과
            # 같을 때만 실제 첫 일별 관측일부터 시작하는 부분월을 허용한다.
            if key == "longest" and is_global_start and dnav.index[0].to_period("M") == risk_start_month:
                risk_start = dnav.index[0]
                allow_partial_first = True
            else:
                risk_start = risk_start_month.start_time
                allow_partial_first = False
            risk_end = risk_end_month.end_time

            has_prior_daily = bool((dnav.index < risk_start).any())
            if _daily_full_coverage(
                dnav, risk_start, risk_end, allow_partial_first_month=allow_partial_first,
                market_calendar=config.market_calendar,
            ) and (has_prior_daily or is_global_start):
                d_slice = _slice_and_rebase(dnav, risk_start, risk_end)
                d_slice.attrs["coverage_verified"] = True
                _check_daily_monthly_consistency(m_slice, d_slice)
                # 월별 시계열에 직전 기준월이 없는 inception 구간은 일별 첫 관측일로
                # 실제 성과 시작 직전 기준일을 복원해 partial-month CAGR 왜곡을 막는다.
                if m_slice.attrs.get("baseline_date") is None:
                    m_slice.attrs["performance_baseline_date"] = d_slice.index[0] - pd.offsets.BDay(1)

        metrics = calculate_metrics(m_slice, config, d_slice)
        payload = build_chat_payload(m_slice, config, key, label, d_slice)
        results[key] = {
            "label": label,
            "start": start,
            "end": end,
            "monthly_nav": m_slice,
            "daily_nav": d_slice,
            "metrics": metrics,
            "chat_payload": payload,
        }
    return results


# =========================================================
# 6. ChatGPT 인터랙티브 차트 payload
# =========================================================

def _compress_drawdown_for_chat(
    dd: pd.Series,
    max_points: int = CHAT_PAYLOAD_MAX_DRAWDOWN_POINTS,
) -> pd.Series:
    """채팅 렌더링 전용 Drawdown 축약.

    중요: MDD와 최대회복기간 계산에는 원본 일별 NAV/Drawdown을 그대로 사용한다.
    이 함수는 화면에 그릴 점 수만 줄인다. 각 구간의 최저점과 구간 끝점을 보존해
    단순 등간격 샘플링보다 저점과 회복 형태를 잘 유지한다.
    """
    x = dd.dropna().astype(float).sort_index()
    if len(x) <= max_points:
        return x
    if max_points < 8:
        raise ValueError("max_points는 8 이상이어야 합니다.")

    interior = x.iloc[1:-1]
    bucket_count = max(1, (max_points - 2) // 2)
    edges = np.linspace(0, len(interior), bucket_count + 1, dtype=int)
    keep = {x.index[0], x.index[-1]}

    for i in range(bucket_count):
        chunk = interior.iloc[edges[i]:edges[i + 1]]
        if chunk.empty:
            continue
        keep.add(chunk.idxmin())
        keep.add(chunk.index[-1])

    out = x.loc[sorted(keep)]
    if len(out) > max_points:
        pos = np.linspace(0, len(out) - 1, max_points, dtype=int)
        out = out.iloc[np.unique(pos)]
    return out

def build_chat_payload(
    monthly_nav: pd.DataFrame,
    config: BacktestConfig,
    period_key: str = "default",
    period_label: Optional[str] = None,
    daily_nav: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    누적자산/로그2 = 월별 NAV
    Drawdown = 일별 NAV 우선, 없으면 월별 NAV
    """
    mnav = validate_monthly_nav(monthly_nav, config, enforce_expected=False)
    dnav = validate_daily_nav(daily_nav) if daily_nav is not None else None
    if dnav is not None:
        missing = [c for c in mnav.columns if c not in dnav.columns]
        if missing:
            raise AssertionError(f"daily_nav에 전략 열이 없습니다: {missing}")
        if dnav.attrs.get("coverage_verified", False):
            _check_daily_monthly_consistency(mnav, dnav)
        elif not _daily_full_coverage(
            dnav, mnav.index[0], mnav.index[-1], market_calendar=config.market_calendar
        ):
            dnav = None
        else:
            _check_daily_monthly_consistency(mnav, dnav)
    metrics = calculate_metrics(mnav, config, dnav)

    series_payload: Dict[str, Any] = {}
    for name in mnav.columns:
        s = mnav[name].astype(float)
        monthly_rows = [{
            "date": dt.strftime("%Y-%m-%d"),
            "nav_multiple": round(float(v), 10),
            "asset_value": round(float(v * config.initial_capital), 2),
            "log2_nav": round(float(np.log2(v)), 10),
        } for dt, v in s.items()]

        risk_s = dnav[name].astype(float) if dnav is not None else s
        dd = drawdown_series(risk_s)
        # 계산은 전체 일별 데이터로 완료한 뒤, 채팅 표시용 점만 축약한다.
        dd_chat = _compress_drawdown_for_chat(dd)
        drawdown_rows = [{
            "date": dt.strftime("%Y-%m-%d"),
            "drawdown_pct": round(float(v * 100.0), 6),
        } for dt, v in dd_chat.items()]

        m = metrics.loc[name]
        series_payload[name] = {
            "metrics": {
                "CAGR_pct": round(float(m["CAGR"] * 100.0), 4),
                "cumulative_return_pct": round(float(m["누적수익률"] * 100.0), 4),
                "MDD_pct": round(float(m["MDD"] * 100.0), 4),
                "MDD_source": str(m["MDD_source"]),
                "Sharpe": None if pd.isna(m["Sharpe"]) else round(float(m["Sharpe"]), 4),
                "Sortino": None if pd.isna(m["Sortino"]) else round(float(m["Sortino"]), 4),
                "Calmar": None if pd.isna(m["Calmar"]) else round(float(m["Calmar"]), 4),
                "monthly_win_rate_pct": None if pd.isna(m["월간승률"]) else round(float(m["월간승률"] * 100.0), 4),
                "annual_std_pct": round(float(m["연환산_표준편차"] * 100.0), 4),
                "max_recovery_months": float(m["최대회복기간_개월"]),
                "max_recovery_days": int(m["최대회복기간_일"]),
                "final_multiple": round(float(m["최종배수"]), 6),
                "final_asset": round(float(m["최종자산"]), 2),
            },
            "monthly_rows": monthly_rows,
            "drawdown_rows": drawdown_rows,
        }

    min_log2 = min(row["log2_nav"] for s in series_payload.values() for row in s["monthly_rows"])
    max_log2 = max(row["log2_nav"] for s in series_payload.values() for row in s["monthly_rows"])
    tick_min = min(0, math.floor(min_log2))
    tick_max = max(1, math.ceil(max_log2))

    return {
        "schema_version": 3,
        "render_target": "chatgpt_chart",
        "title": config.title,
        "period_key": period_key,
        "period_label": period_label or f"{mnav.index[0]:%Y-%m}~{mnav.index[-1]:%Y-%m}",
        "initial_capital": config.initial_capital,
        "monthly_start": mnav.index[0].strftime("%Y-%m-%d"),
        "monthly_end": mnav.index[-1].strftime("%Y-%m-%d"),
        "monthly_observations": len(mnav),
        "risk_frequency": "daily" if dnav is not None else "monthly_fallback",
        "risk_start": (dnav.index[0] if dnav is not None else mnav.index[0]).strftime("%Y-%m-%d"),
        "risk_end": (dnav.index[-1] if dnav is not None else mnav.index[-1]).strftime("%Y-%m-%d"),
        "risk_observations": len(dnav) if dnav is not None else len(mnav),
        "drawdown_chart_observations": max(len(v["drawdown_rows"]) for v in series_payload.values()),
        "drawdown_chart_max_points": CHAT_PAYLOAD_MAX_DRAWDOWN_POINTS,
        "series_order": list(mnav.columns),
        "log2_axis": {
            "tick_values": list(range(tick_min, tick_max + 1)),
            "tick_labels": [f"{2**p:g}배" for p in range(tick_min, tick_max + 1)],
        },
        "series": series_payload,
    }


def combine_period_payloads(*payloads: Dict[str, Any]) -> Dict[str, Any]:
    """
    기간별 payload를 3개 기본 그래프(누적자산 / Log2 / Drawdown)로 묶는다.

    채팅 UI 계약
    - 버전 2(fallback): 기본 그래프 3개(누적자산 / Log2 / Drawdown)를 렌더링하고, 각 그래프 상단에 기간 버튼을 둔다.
    - 기간 버튼: 2000~현재 / 2021~현재 / 최장~현재
    - 기본 선택: 2000~현재
    - 버전 1(우선): 기간 선택 UI를 안정적으로 구현할 수 없으면 3기간 x 3차트 = 총 9개 인라인 차트를 모두 렌더링한다.
    - 버전 1 차트 순서: 기간별로 누적자산 -> Log2 -> Drawdown, 기간 순서는 2000 -> 2021 -> 최장.
    - 전략/벤치마크 시리즈는 가능한 경우 체크박스/토글로 켜고 끌 수 있게 한다.
    - 책 검증기간은 성과표에는 포함하지만 차트 기간 버튼/9개 fallback에서는 제외한다.
    """
    if not payloads:
        raise ValueError("최소 1개의 payload가 필요합니다.")

    periods = {p["period_key"]: p for p in payloads}
    selector_labels = {
        "from_2000": "2000~현재",
        "from_2021": "2021~현재",
        "longest": "최장~현재",
    }
    selector_order = [k for k in ("from_2000", "from_2021", "longest") if k in periods]
    if not selector_order:
        raise ValueError("기간 선택용 payload(longest/from_2000/from_2021)가 최소 1개 필요합니다.")

    default_period = "from_2000" if "from_2000" in periods else selector_order[0]
    selector_options = [{"key": k, "label": selector_labels[k]} for k in selector_order]

    chart_defs = [
        {
            "chart_key": "cumulative_wealth",
            "label": "누적자산",
            "y_mode": "linear",
            "source": "monthly_rows",
            "series_fields": {"value": "nav_multiple", "asset": "asset_value"},
        },
        {
            "chart_key": "log2_wealth",
            "label": "Log2 누적자산",
            "y_mode": "log2",
            "source": "monthly_rows",
            "series_fields": {"value": "log2_nav", "asset": "asset_value"},
        },
        {
            "chart_key": "drawdown",
            "label": "Drawdown",
            "y_mode": "drawdown_pct",
            "source": "drawdown_rows",
            "series_fields": {"value": "drawdown_pct"},
        },
    ]

    return {
        "schema_version": 8,
        "render_target": "chatgpt_interactive_backtest_dashboard",
        "presentation_versions": {
            "version_2": {
                "label": "3개 차트 + 기간 선택 UI",
                "priority": 2,
                "inline_chart_count": 3,
                "requires_native_period_selector": True,
            },
            "version_1": {
                "label": "3기간 x 3차트 = 9개 인라인 차트",
                "priority": 1,
                "inline_chart_count": 9,
                "use_when": "default",
                "period_order": ["from_2000", "from_2021", "longest"],
                "chart_order_per_period": ["cumulative_wealth", "log2_wealth", "drawdown"],
            },
        },
        "title": payloads[0]["title"],
        "period_order": [p["period_key"] for p in payloads],
        "periods": periods,
        "controls": {
            "period_buttons": {
                "enabled": True,
                "style": "buttons",
                "default_period": default_period,
                "options": selector_options,
                "apply_to_each_chart": True,
            },
            "series_toggles": {
                "enabled": True,
                "style": "checkboxes",
                "default_all_on": True,
            },
        },
        "charts": chart_defs,
        "chat_render_policy": {
            "preferred_version": "version_1",
            "fallback_version": "version_2",
            "version_2": {
                "priority": "three_interactive_charts_with_period_buttons",
                "inline_chart_count": 3,
                "chart_order": [c["chart_key"] for c in chart_defs],
                "same_period_buttons_on_each_chart": True,
                "period_button_order": selector_order,
                "default_period": default_period,
            },
            "version_1": {
                "priority": "nine_inline_charts_no_period_selector",
                "inline_chart_count": 9,
                "period_order": [k for k in ("from_2000", "from_2021", "longest") if k in periods],
                "chart_order_per_period": [c["chart_key"] for c in chart_defs],
                "render_all_periods": True,
                "trigger": "default",
            },
            "series_toggles_required_when_supported": True,
            "static_matplotlib_disallowed": True,
            "require_korean_labels": True,
            "book_period_charts_excluded": True,
            "download_dashboard_role": "secondary_only",
            "must_not_claim_unrendered_chart": True,
        },
    }


def save_chat_payload(payload: Dict[str, Any], output_path: str) -> str:
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return output_path


# =========================================================
# 7. 단일기간 호환 실행
# =========================================================

def run_standard_backtest(
    monthly_nav: pd.DataFrame,
    config: BacktestConfig,
    period_key: str = "default",
    period_label: Optional[str] = None,
    daily_nav: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    mnav = validate_monthly_nav(monthly_nav, config)
    # 원본 NAV 스케일 계약을 단일기간/4기간 실행 모두 동일하게 강제한다.
    _enforce_input_nav_scale(mnav)
    dnav = validate_daily_nav(daily_nav) if daily_nav is not None else None
    d_slice = None
    if dnav is not None and _daily_full_coverage(
        dnav, mnav.index[0], mnav.index[-1], market_calendar=config.market_calendar
    ):
        d_slice = _slice_and_rebase(
            dnav, mnav.index[0].to_period("M").start_time, mnav.index[-1].to_period("M").end_time
        )
        d_slice.attrs["coverage_verified"] = True
        _check_daily_monthly_consistency(mnav, d_slice)
        if mnav.attrs.get("baseline_date") is None:
            mnav.attrs["performance_baseline_date"] = d_slice.index[0] - pd.offsets.BDay(1)
    metrics = calculate_metrics(mnav, config, d_slice)
    payload = build_chat_payload(mnav, config, period_key, period_label, d_slice)
    return {
        "monthly_nav": mnav,
        "daily_nav": d_slice,
        "metrics": metrics,
        "chat_payload": payload,
    }


# =========================================================
# 8. ChatGPT 출력 규칙
# =========================================================

CHATGPT_RENDERING_RULES = """
백테스트 최종 응답 규칙:

1. 기본 검증기간은 반드시 4개다.
   A. 책 기간 검증
   B. 2000~현재
   C. 2021~현재
   D. 가능한 최장기간~현재
2. 존재하지 않는 과거/미래 데이터를 생성하지 않는다.
3. CAGR / Sharpe / 연환산 표준편차는 월별 수익률 기준으로 계산한다.
4. MDD / 최대 회복기간 / Drawdown 그래프는 일별 NAV가 있으면 반드시 일별 기준으로 계산한다.
5. 일별 NAV를 구할 수 없는 경우에만 월별 기준으로 fallback하고 결과에 '월별 fallback'을 명시한다.
6. 월별 NAV로 일별 MDD를 보간/추정하지 않는다.
7. 기본 성과표는 CAGR / 누적수익률 / 연환산 표준편차 / MDD / 최대회복기간 / Sharpe를 포함하고 비용 전·후를 구분한다.
8. 채팅 기본 그래프 종류는 정확히 3개다.
   - 누적자산
   - Log2 누적자산
   - Drawdown
9. 차트 출력 방식은 다음 2개 버전으로 정의한다.
   - 버전 2(fallback): 위 3개 차트 각각에 동일한 기간 선택 UI를 제공한다.
     · 2000~현재 / 2021~현재 / 최장~현재
     · 기본 선택은 2000~현재
     · 총 인라인 차트 수는 3개다.
   - 버전 1(우선): 버전 2의 네이티브 기간 선택 UI를 사용할 수 없거나 안정적 렌더링이 불가능하면
     2000~현재 / 2021~현재 / 최장~현재의 3기간 각각에 누적자산 / Log2 / Drawdown을 모두 표시한다.
     · 총 인라인 차트 수는 9개다.
     · 순서: 2000 3개 -> 2021 3개 -> 최장 3개.
10. 버전 1을 반드시 우선한다. 버전 1의 9개 인라인 차트를 안정적으로 렌더링할 수 없는 경우에만 버전 2로 fallback한다.
11. 버전 1이 불가능하면 사용자에게 추가 확인을 요구하지 않고 자동으로 버전 2로 fallback한다.
12. 각 그래프에서 전략과 벤치마크 시리즈는 위젯이 지원하는 경우 체크박스/범례 토글로 켜고 끌 수 있게 한다.
13. 책 검증기간은 성과표와 책 수치 비교에는 포함하지만 버전 1/2의 기본 차트에서는 제외한다.
14. 기본 출력 형태는 '성과표 + 버전 1', 버전 1이 불가능하면 '성과표 + 버전 2'이다.
15. matplotlib 정적그래프를 기본 수단으로 사용하지 않는다. 한글 깨짐 위험 때문에 채팅 내 인터랙티브 렌더링을 우선한다.
16. HTML/PNG/CSV 다운로드는 보조자료이며 채팅 인라인 그래프를 대체하지 않는다.
17. 차트가 화면에 실제로 나타나지 않았으면 '그래프를 제공했다'고 간주하거나 표현하지 않는다.
18. Log2 차트는 log2(NAV)를 직접 그려 1배, 2배, 4배, 8배...가 동일 간격이어야 한다.
19. 그래프 렌더링 전에 기간, 관측치, 누락치, 열 정렬을 검증한다.
20. 한글 제목, 범례, 축 라벨을 기본으로 사용한다.
21. 새 대화에서도 사용자가 단순히 '백테스트해줘'라고 요청하면 별도 지시 없이 이 CURRENT v2-16 템플릿의 계산 및 출력 규칙을 적용한다.
22. 백테스트에 필요한 데이터는 사용자 GitHub 저장소 Horororong/quant-marcap-runner 를 최우선으로 탐색한다.
23. GitHub에 필요한 데이터가 없거나 기간이 부족하면 임의 데이터로 대체하지 않는다.
24. 반복 수집 가능한 누락 데이터는 config/etf_universe.csv, config/kr_etf_universe.csv 또는 config/strategy_data_collection.csv 중 적절한 자동수집 레지스트리에 추가한다.
25. 기존 수집기가 처리하지 못하는 데이터 유형이면 수집 스크립트/workflow도 함께 보완하여 이후 자동 업데이트 경로를 만든다.
26. 외부 데이터는 GitHub 데이터가 없거나 품질/기간상 불충분하고, 출처·정의·시점 정합성을 검증할 수 있을 때만 보조적으로 사용한다.
27. 자동수집 레지스트리나 workflow를 변경했다면 무엇을 왜 추가했는지 최종 보고에 명시한다.
28. 한국 개별주 백테스트는 data/krx_equities/yearly 연도별 PIT 패널을 기본 원천으로 사용한다.
29. 현재 상장종목으로 과거 유니버스를 재구성하지 않는다.
30. 재무 팩터는 filing_date 이후에만 사용할 수 있도록 PIT as-of join을 적용한다.
31. 한국 개별주 유니버스의 우선주/스팩/리츠/금융업/신규상장/관리종목 제외 여부를 결과에 명시한다.
32. 전략별 스크립트는 일별 NAV까지만 산출한다. CAGR/MDD/Sharpe/최대회복기간/성과표를 별도로 재계산하지 않는다.
33. 최종 성과표는 반드시 CURRENT의 run_four_periods()/calculate_metrics() 결과를 사용한다.
34. 9개 차트용 데이터는 CURRENT의 build_chat_payload()/combine_period_payloads()에서만 생성한다.
35. MDD/최대회복기간은 전체 일별 NAV로 계산하고, 렌더링 병목 방지를 위해 Drawdown 표시점만 CHAT_PAYLOAD_MAX_DRAWDOWN_POINTS 이하로 축약한다.
36. 사용자가 백테스트를 요청하면 데이터 확인→신호→t+1 체결→drift/turnover→비용→일별 NAV→CURRENT 표준계산→4기간 성과표→9개 차트 순서를 에이전트가 한 번에 수행한다.
    사용자가 이 단계를 따로 지시하도록 요구하지 않는다.
37. 범용 목표비중 전략은 simulate_target_weight_portfolio()/run_execution_backtest()를 우선 사용해 체결과 비용을 표준화한다.
38. 정식 성과지표는 최근 완결월까지만 계산하고, 최신 거래일 NAV는 참고 스냅샷으로 분리한다.
39. 비용 시나리오는 임의 수치로 숨겨 결정하지 않는다. 최소/기준/보수 가정은 전략/시장에 맞게 명시적으로 전달한다.
40. OOS/워크포워드 검증은 시간순서를 보존하며 generate_expanding_walk_forward_windows()를 사용할 수 있다.
41. KRX 배당·상폐 회수액·기업행위 원천이 없으면 total return을 임의 복원하지 않는다. KRX_TOTAL_RETURN_LIMITATION을 따른다.
"""


# =========================================================
# 9. 간단 자체검증
# =========================================================

def _self_test() -> None:
    # 거래일 샘플을 먼저 만들고, 동일 NAV에서 월말 자료를 추출해 정합성을 보장한다.
    di = pd.bdate_range("2000-01-03", "2026-08-31")
    daily = pd.DataFrame({"전략": np.cumprod(np.full(len(di), 1.0002))}, index=di)
    monthly = daily.groupby(daily.index.to_period("M")).tail(1).copy()
    monthly.index = monthly.index.to_period("M").to_timestamp("M")
    assert len(monthly) == 320

    cfg = BacktestConfig(
        title="self-test",
        book_start="2000-01-01",
        book_end="2021-12-31",
        expected_start="2000-01",
        expected_end="2026-08",
        expected_months=320,
        as_of_date="2026-09-17",
    )
    out = run_four_periods(monthly, cfg, daily)
    assert list(out.keys()) == ["book_validation", "from_2000", "from_2021", "longest"]
    assert out["from_2000"]["metrics"].loc["전략", "MDD_source"] == "daily"

    out_fallback = run_standard_backtest(monthly, cfg)
    assert out_fallback["metrics"].loc["전략", "MDD_source"] == "monthly_fallback"

    # 일별 데이터가 기간 중간부터만 있으면 장기구간은 월별 fallback이어야 한다.
    partial_daily = daily.loc["2021-01-01":].copy()
    out_partial = run_four_periods(monthly, cfg, partial_daily)
    assert out_partial["book_validation"]["metrics"].loc["전략", "MDD_source"] == "monthly_fallback"
    assert out_partial["from_2000"]["metrics"].loc["전략", "MDD_source"] == "monthly_fallback"
    assert out_partial["from_2021"]["metrics"].loc["전략", "MDD_source"] == "monthly_fallback"
    assert out_partial["longest"]["metrics"].loc["전략", "MDD_source"] == "monthly_fallback"

    # 2000 이후에 시작하는 월별 데이터로 2000~ 기간을 조용히 축약하면 안 된다.
    late_monthly = monthly.loc["2005-01-31":].copy()
    late_cfg = BacktestConfig(title="late", book_start="2005-01-01", book_end="2021-12-31")
    try:
        run_four_periods(late_monthly, late_cfg)
        raise AssertionError("2000 고정기간 데이터 부족을 감지하지 못했습니다.")
    except ValueError as e:
        assert "2000~기간 고정 조건" in str(e)

    # 회귀 테스트: 100 기준 wealth index를 누적배수로 오인하지 않아야 한다.
    wealth = monthly.copy() * 100.0
    try:
        run_standard_backtest(wealth, cfg)
        raise AssertionError("100 기준 wealth index 오입력을 감지하지 못했습니다.")
    except ValueError as e:
        assert "누적배수" in str(e)

    # 책 종료월이 데이터보다 늦으면 조용히 축약하지 않아야 한다.
    short_monthly = monthly.loc[:"2025-12-31"].copy()
    bad_book_cfg = BacktestConfig(title="badbook", book_start="2000-01-01", book_end="2026-12-31")
    try:
        standard_period_windows(short_monthly, bad_book_cfg)
        raise AssertionError("책 기간 종료 데이터 부족을 감지하지 못했습니다.")
    except ValueError as e:
        assert "조용히 축약하지 않습니다" in str(e)

    # 시작월 말일에야 시작하는 일별 자료는 full coverage로 인정하면 안 된다.
    late_daily_start = daily.loc["2000-01-31":].copy()
    assert not _daily_full_coverage(late_daily_start, pd.Timestamp("2000-01-01"), pd.Timestamp("2026-08-31"))

    # 미완결 월(예: 9/17)을 월말 NAV로 조용히 승격하면 안 된다.
    partial_idx = list(pd.date_range("2000-01-31", "2026-08-31", freq="ME")) + [pd.Timestamp("2026-09-17")]
    partial_month = pd.DataFrame({"전략": np.cumprod(np.full(len(partial_idx), 1.001))}, index=partial_idx)
    try:
        validate_monthly_nav(partial_month, BacktestConfig(), enforce_expected=False)
        raise AssertionError("미완결 월 관측치를 감지하지 못했습니다.")
    except AssertionError as e:
        assert ("월 중간 관측치" in str(e)) or ("아직 끝나지 않은 월" in str(e))

    # 월말 7일 이내라도 마지막 관측월이 아직 끝나지 않은 부분월이면 허용하면 안 된다.
    near_end_idx = list(pd.date_range("2000-01-31", "2026-08-31", freq="ME")) + [pd.Timestamp("2026-09-25")]
    near_end_month = pd.DataFrame({"전략": np.cumprod(np.full(len(near_end_idx), 1.001))}, index=near_end_idx)
    try:
        validate_monthly_nav(near_end_month, BacktestConfig(), enforce_expected=False)
        raise AssertionError("월말 근처의 미완결 마지막 월을 감지하지 못했습니다.")
    except AssertionError as e:
        assert ("마지막 관측월" in str(e)) or ("아직 끝나지 않은 월" in str(e))

    # calculate_metrics 직접 호출에서도 서로 다른 월/일 NAV를 혼합하면 안 된다.
    mm_idx = pd.date_range("2021-01-31", "2021-12-31", freq="ME")
    mm = pd.DataFrame({"전략": np.cumprod(np.full(len(mm_idx), 1.01))}, index=mm_idx)
    dd_idx = pd.bdate_range("2021-01-01", "2021-12-31")
    wrong = np.ones(len(dd_idx)); wrong[50:100] = 0.2; wrong[100:] = 1.2
    wrong_daily = pd.DataFrame({"전략": wrong}, index=dd_idx)
    try:
        calculate_metrics(mm, BacktestConfig(), wrong_daily)
        raise AssertionError("서로 다른 월/일 NAV 혼합을 감지하지 못했습니다.")
    except AssertionError as e:
        assert "daily/monthly NAV 불일치" in str(e)

    # 최장기간이 실제 데이터 inception 월의 말미에서 시작해도, 그 날짜부터 일별 자료가
    # 완전하다면 첫 부분월 때문에 전체를 monthly fallback으로 내리면 안 된다.
    inception_daily = daily.loc["2000-01-28":].copy()
    inception_monthly = inception_daily.groupby(inception_daily.index.to_period("M")).tail(1).copy()
    inception_monthly.index = inception_monthly.index.to_period("M").to_timestamp("M")
    inc_cfg = BacktestConfig(title="inception", book_start="2000-01-01", book_end="2021-12-31")
    inc_out = run_four_periods(inception_monthly, inc_cfg, inception_daily)
    assert inc_out["longest"]["metrics"].loc["전략", "MDD_source"] == "daily"
    # 고정 2000~ 구간은 2000-01 전체 일별 커버리지가 없으므로 보수적으로 fallback한다.
    assert inc_out["from_2000"]["metrics"].loc["전략", "MDD_source"] == "monthly_fallback"

    # partial inception CAGR: 실제 첫 일별 관측일이 월말 직전이면 짧은 첫 달을
    # 한 달 전체로 계산하지 않는다.
    pi_daily_idx = pd.bdate_range("2000-01-28", "2026-08-31")
    pi_daily = pd.DataFrame({"전략": np.ones(len(pi_daily_idx)) * 1.10}, index=pi_daily_idx)
    pi_daily.iloc[0, 0] = 1.0
    pi_monthly = pi_daily.groupby(pi_daily.index.to_period("M")).tail(1).copy()
    pi_monthly.index = pi_monthly.index.to_period("M").to_timestamp("M")
    pi_cfg = BacktestConfig(title="partial-cagr", book_start="2000-01-01", book_end="2021-12-31")
    pi_out = run_four_periods(pi_monthly, pi_cfg, pi_daily)
    actual_cagr = float(pi_out["longest"]["metrics"].loc["전략", "CAGR"])
    elapsed = (pd.Timestamp("2026-08-31") - (pi_daily_idx[0] - pd.offsets.BDay(1))).days / 365.2425
    expected_cagr = 1.10 ** (1.0 / elapsed) - 1.0
    assert abs(actual_cagr - expected_cagr) < 1e-12


    # 4기간 실행에서도 100 기준 wealth index를 허용하면 longest CAGR이 폭발한다.
    wealth4 = monthly.copy() * 100.0
    try:
        run_four_periods(wealth4, cfg)
        raise AssertionError("4기간 실행의 100 기준 wealth index 오입력을 감지하지 못했습니다.")
    except ValueError as e:
        assert "누적배수" in str(e)

    # 기준일보다 뒤의 월말 라벨은 아직 완결되지 않은 미래 월이므로 차단한다.
    future_idx = list(pd.date_range("2000-01-31", "2026-08-31", freq="ME")) + [pd.Timestamp("2026-09-30")]
    future_month = pd.DataFrame({"전략": np.cumprod(np.full(len(future_idx), 1.001))}, index=future_idx)
    try:
        validate_monthly_nav(future_month, BacktestConfig(as_of_date="2026-09-17"), enforce_expected=False)
        raise AssertionError("미완결 미래 월말 라벨을 감지하지 못했습니다.")
    except AssertionError as e:
        assert "아직 끝나지 않은 월" in str(e)

    # 월중 inception의 첫 부분월은 Sharpe/변동성 월표본에서 제외한다.
    ps_idx = pd.bdate_range("2000-01-28", "2026-08-31")
    ps_ret = np.full(len(ps_idx), 0.0001); ps_ret[0] = 0.0; ps_ret[1] = 0.10
    ps_daily = pd.DataFrame({"전략": np.cumprod(1.0 + ps_ret)}, index=ps_idx)
    ps_monthly = ps_daily.groupby(ps_daily.index.to_period("M")).tail(1).copy()
    ps_monthly.index = ps_monthly.index.to_period("M").to_timestamp("M")
    ps_cfg = BacktestConfig(title="partial-stats", book_start="2000-01-01", book_end="2021-12-31", as_of_date="2026-09-17")
    ps_metrics = run_four_periods(ps_monthly, ps_cfg, ps_daily)["longest"]["metrics"].loc["전략"]
    ps_r = ps_monthly["전략"].pct_change().dropna()
    ps_expected_vol = float(ps_r.std(ddof=1) * np.sqrt(12))
    ps_expected_sharpe = float(ps_r.mean() / ps_r.std(ddof=1) * np.sqrt(12))
    assert abs(float(ps_metrics["연환산_표준편차"]) - ps_expected_vol) < 1e-12
    assert abs(float(ps_metrics["Sharpe"]) - ps_expected_sharpe) < 1e-12

    # build_chat_payload 직접 호출에서도 불완전한 일별 자료는 차트까지 월별 fallback이어야 한다.
    ps_short = ps_daily.loc["2021-01-01":].copy()
    ps_payload = build_chat_payload(ps_monthly, ps_cfg, daily_nav=ps_short)
    assert ps_payload["risk_frequency"] == "monthly_fallback"
    assert ps_payload["series"]["전략"]["metrics"]["MDD_source"] == "monthly_fallback"

    # 설정값 오류는 계산 중 난해한 예외/복소수 대신 생성 시점에 즉시 차단한다.
    for bad_kwargs in (
        {"periods_per_year": 0},
        {"risk_free_rate": -1.5},
        {"initial_capital": -1.0},
    ):
        try:
            BacktestConfig(**bad_kwargs)
            raise AssertionError(f"잘못된 설정값을 감지하지 못했습니다: {bad_kwargs}")
        except ValueError:
            pass

    # 2.0 기준 wealth index도 명백한 임의 스케일이므로 차단한다.
    scale2 = monthly * 2.0
    try:
        run_four_periods(scale2, cfg, daily * 2.0)
        raise AssertionError("2.0 기준 wealth index 오입력을 감지하지 못했습니다.")
    except ValueError as e:
        assert "1.0 기준" in str(e)

    # 한 달에 거래일이 여러 개 빠진 불완전 일별 자료를 daily MDD로 인정하면 안 된다.
    sparse_idx = pd.bdate_range("2021-01-01", "2021-03-31")
    feb = sparse_idx[sparse_idx.month == 2]
    sparse_idx = sparse_idx.difference(feb[5:10])  # 5거래일 의도적 누락
    sparse = pd.DataFrame({"전략": np.cumprod(np.full(len(sparse_idx), 1.0002))}, index=sparse_idx)
    assert not _daily_full_coverage(sparse, pd.Timestamp("2021-01-01"), pd.Timestamp("2021-03-31"))

    # 60/40형 회귀 테스트: 두 자산을 60/40으로 보유하고 매년 첫 거래일 전에
    # 목표비중으로 재조정한 결정론적 NAV를 넣었을 때 일별 MDD가 독립 계산과 일치해야 한다.
    reg_idx = pd.bdate_range("1999-12-30", "2026-08-31")
    n = len(reg_idx)
    ra = np.where(np.arange(n) % 17 == 0, -0.012, 0.00035)
    rb = np.where(np.arange(n) % 29 == 0, -0.006, 0.00018)
    value = 1.0
    weights = np.array([0.6, 0.4], dtype=float)
    reg_nav = []
    for i, dt in enumerate(reg_idx):
        if i > 0 and dt.year != reg_idx[i - 1].year:
            weights = np.array([0.6, 0.4], dtype=float)
        gross = np.array([1.0 + ra[i], 1.0 + rb[i]])
        pg = float((weights * gross).sum())
        value *= pg
        weights = weights * gross / pg
        reg_nav.append(value)
    reg_daily = pd.DataFrame({"60/40": reg_nav}, index=reg_idx)
    reg_monthly = reg_daily.groupby(reg_daily.index.to_period("M")).tail(1).copy()
    reg_monthly.index = reg_monthly.index.to_period("M").to_timestamp("M")
    reg_cfg = BacktestConfig(title="60/40-regression", book_start="2000-01-01", book_end="2021-12-31")
    reg_out = run_four_periods(reg_monthly, reg_cfg, reg_daily)
    reg_s = reg_daily.loc["2000-01-01":"2026-08-31", "60/40"]
    reg_base = reg_daily.loc[:"1999-12-31", "60/40"].iloc[-1]
    reg_s = reg_s / reg_base
    independent_mdd = float((reg_s / reg_s.cummax() - 1.0).min())
    template_mdd = float(reg_out["from_2000"]["metrics"].loc["60/40", "MDD"])
    assert abs(template_mdd - independent_mdd) < 1e-12



    # 한국 장기 연휴는 정상 거래소 휴장이다. 평일 휴리스틱 때문에 daily MDD를
    # 월별 fallback으로 오판하지 않도록 XKRX 실제 세션과 대조한다.
    try:
        import exchange_calendars as _xcals  # type: ignore
        _xkrx = _xcals.get_calendar("XKRX")
        _sess = pd.DatetimeIndex(_xkrx.sessions_in_range("2017-09-01", "2017-10-31"))
        if _sess.tz is not None:
            _sess = _sess.tz_localize(None)
        _holiday_nav = pd.DataFrame({"전략": np.linspace(1.0, 1.1, len(_sess))}, index=_sess)
        assert _daily_full_coverage(
            _holiday_nav, pd.Timestamp("2017-09-01"), pd.Timestamp("2017-10-31"),
            market_calendar="XKRX",
        )
        _missing_one = _holiday_nav.drop(index=_holiday_nav.index[len(_holiday_nav)//2])
        assert not _daily_full_coverage(
            _missing_one, pd.Timestamp("2017-09-01"), pd.Timestamp("2017-10-31"),
            market_calendar="XKRX",
        )
    except ImportError:
        pass

    # 누적수익률은 최종배수-1로 직접 제공되어야 한다.
    cm = calculate_metrics(monthly, cfg)
    assert abs(float(cm.loc["전략", "누적수익률"]) - (float(monthly.iloc[-1, 0]) - 1.0)) < 1e-12

    # 거래비용 독립 회귀 테스트: gross return 0%, 매수/매도 각 50%,
    # 양쪽 공통 10bp + 매도세 20bp -> 총 비용 20bp = 0.2%.
    ci = pd.to_datetime(["2026-01-31"])
    gross_r = pd.Series([0.0], index=ci)
    buy_to = pd.Series([0.5], index=ci)
    sell_to = pd.Series([0.5], index=ci)
    cost_assump = TradingCostAssumptions(commission_bps=10.0, sell_tax_bps=20.0)
    cost_out = apply_trading_costs_to_returns(gross_r, buy_to, sell_to, cost_assump)
    assert abs(float(cost_out.iloc[0]["cost_fraction"]) - 0.002) < 1e-12
    assert abs(float(cost_out.iloc[0]["net_return"]) + 0.002) < 1e-12

    # PIT 표준팩터는 동일 종목/동일 이용가능일 중복을 허용하지 않는다.
    obs_test = pd.DataFrame({"Date": pd.to_datetime(["2026-04-01"]), "Code": ["005930"]})
    dup_fac = pd.DataFrame({
        "available_date": pd.to_datetime(["2026-03-31", "2026-03-31"]),
        "Code": ["005930", "005930"],
        "factor": [1.0, 2.0],
    })
    try:
        pit_asof_join(obs_test, dup_fac)
        raise AssertionError("PIT 팩터 중복을 감지하지 못했습니다.")
    except AssertionError as e:
        assert "동일 종목/이용가능일 중복" in str(e)

    # ETF 공통 로더 회귀 테스트: 실제 저장소와 같은 CSV/registry 스키마를 임시로 구성한다.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / KRX_EQUITY_YEARLY_DIR).mkdir(parents=True, exist_ok=True)
        (root / ETF_US_DIR).mkdir(parents=True, exist_ok=True)
        (root / ETF_KR_DIR).mkdir(parents=True, exist_ok=True)
        (root / "config").mkdir(parents=True, exist_ok=True)
        pd.DataFrame({
            "ticker": ["SPY"], "asset_class": ["US Equity"], "description": ["S&P 500"]
        }).to_csv(root / ETF_US_REGISTRY, index=False)
        pd.DataFrame({
            "yahoo_ticker": ["069500.KS"], "code": ["069500"], "name": ["KODEX200"],
            "role": ["KR_EQUITY"], "proxy_quality": ["EXACT"], "notes": [""]
        }).to_csv(root / ETF_KR_REGISTRY, index=False)
        ed = pd.DataFrame({
            "Date": pd.to_datetime(["2026-01-02", "2026-01-05"]),
            "Open": [100.0, 101.0], "High": [101.0, 102.0], "Low": [99.0, 100.0],
            "Close": [100.5, 101.5], "Adj Close": [100.0, 101.0], "Volume": [1000, 1100],
        })
        ed.to_csv(root / ETF_US_DIR / "SPY.csv", index=False)
        ed.to_csv(root / ETF_KR_DIR / "069500_KODEX200.csv", index=False)
        us_bundle = load_etf_backtest_data(["SPY"], market="US", repo_root=root)
        kr_bundle = load_etf_backtest_data(["KODEX200"], market="KR", repo_root=root)
        assert us_bundle["symbols"] == ["SPY"]
        assert kr_bundle["symbols"] == ["069500"]
        assert list(us_bundle["fields"]["Adj Close"].columns) == ["SPY"]
        assert list(kr_bundle["fields"]["Adj Close"].columns) == ["069500"]

    # v2-16/CURRENT interactive-dashboard + project-data-contract regression test.
    p_long = out["longest"]["chat_payload"]
    p_2000 = out["from_2000"]["chat_payload"]
    p_2021 = out["from_2021"]["chat_payload"]
    combined = combine_period_payloads(p_long, p_2000, p_2021)
    assert combined["schema_version"] == 8
    assert combined["render_target"] == "chatgpt_interactive_backtest_dashboard"
    assert combined["presentation_versions"]["version_2"]["inline_chart_count"] == 3
    assert combined["presentation_versions"]["version_1"]["inline_chart_count"] == 9
    assert combined["controls"]["period_buttons"]["default_period"] == "from_2000"
    assert combined["controls"]["period_buttons"]["style"] == "buttons"
    assert combined["controls"]["period_buttons"]["apply_to_each_chart"] is True
    assert combined["controls"]["series_toggles"]["enabled"] is True
    assert len(combined["charts"]) == 3
    assert [c["chart_key"] for c in combined["charts"]] == ["cumulative_wealth", "log2_wealth", "drawdown"]
    assert combined["chat_render_policy"]["preferred_version"] == "version_1"
    assert combined["chat_render_policy"]["fallback_version"] == "version_2"
    assert combined["chat_render_policy"]["version_2"]["inline_chart_count"] == 3
    assert combined["chat_render_policy"]["version_2"]["same_period_buttons_on_each_chart"] is True
    assert combined["chat_render_policy"]["version_1"]["inline_chart_count"] == 9
    assert combined["chat_render_policy"]["version_1"]["render_all_periods"] is True
    assert combined["chat_render_policy"]["series_toggles_required_when_supported"] is True
    assert combined["chat_render_policy"]["static_matplotlib_disallowed"] is True
    assert combined["chat_render_policy"]["require_korean_labels"] is True
    assert PROJECT_GITHUB_REPO == "Horororong/quant-marcap-runner"
    assert PROJECT_DATA_PRIORITY[0] == "data/krx_equities/yearly/"
    assert PROJECT_COLLECTION_WORKFLOWS["krx_equities"] == ".github/workflows/update-quant-data.yml"
    assert KRX_EQUITY_YEARLY_DIR == "data/krx_equities/yearly"
    assert "상장폐지" in KRX_BACKTEST_DATA_CONTRACT
    assert callable(load_krx_equity_panel)
    assert callable(load_korean_equity_backtest_data)
    assert callable(load_etf_backtest_data)
    assert callable(load_dart_financial_rows)
    assert callable(apply_trading_costs_to_returns)
    assert callable(pit_asof_join)
    assert PROJECT_COLLECTION_REGISTRIES["us_etf"] == "config/etf_universe.csv"
    assert PROJECT_COLLECTION_REGISTRIES["kr_etf"] == "config/kr_etf_universe.csv"
    assert PROJECT_COLLECTION_REGISTRIES["strategy_long_or_missing"] == "config/strategy_data_collection.csv"
    assert "GitHub" in BACKTEST_EXECUTION_CONTRACT
    assert "버전 1" in BACKTEST_EXECUTION_CONTRACT


    # v2-16: t 신호는 t+1 종가 체결. t+1 수익은 기존 포지션(초기 cash)이 받는다.
    _px_idx = pd.bdate_range("2026-01-02", periods=6)
    _px = pd.DataFrame({
        "A": [100.0, 110.0, 121.0, 133.1, 146.41, 161.051],
        "B": [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
    }, index=_px_idx)
    _tw = pd.DataFrame({"A": [1.0], "B": [0.0]}, index=[_px_idx[0]])
    _exec = simulate_target_weight_portfolio(
        _px, _tw, TradingCostAssumptions(), ExecutionAssumptions(execution_lag_sessions=1)
    )
    assert _exec["execution_schedule"].iloc[0]["execution_date"] == _px_idx[1]
    # 첫날~체결일 종가까지는 현금이므로 NAV=1, 그 다음 날부터 A 수익이 반영된다.
    assert abs(float(_exec["daily_nav"].loc[_px_idx[1], "Gross"]) - 1.0) < 1e-12
    assert abs(float(_exec["daily_nav"].loc[_px_idx[2], "Gross"]) - 1.1) < 1e-12
    assert abs(float(_exec["trades"].loc[_px_idx[1], "buy_turnover"]) - 1.0) < 1e-12

    # 거래불가 자산을 조용히 매수하면 안 된다.
    _mask = pd.DataFrame(True, index=_px_idx, columns=["A", "B"])
    _mask.loc[_px_idx[1], "A"] = False
    try:
        simulate_target_weight_portfolio(_px, _tw, tradable_mask=_mask)
        raise AssertionError("거래불가 체결을 감지하지 못했습니다.")
    except RuntimeError as e:
        assert "거래불가" in str(e)

    # walk-forward는 embargo 이후에 OOS가 시작되어야 한다.
    _wf = generate_expanding_walk_forward_windows(_px_idx, 3, 1, embargo_observations=1)
    assert (_wf["test_start"] > _wf["train_end"]).all()
    assert len(_wf) >= 1

    # 최근 미완결월은 정식 성과에서 제외하고 최신 NAV는 별도 보존한다.
    _didx = pd.bdate_range("2026-07-01", "2026-09-23")
    _dnav = pd.DataFrame({"X": np.cumprod(np.full(len(_didx), 1.001))}, index=_didx)
    _formal_d, _formal_m, _latest = complete_monthly_nav_from_daily(_dnav, "2026-09-23")
    assert _formal_m.index[-1] == pd.Timestamp("2026-08-31")
    assert _latest["latest_daily_date"] == pd.Timestamp("2026-09-23")
    assert _latest["partial_current_month_excluded_from_formal_metrics"] is True

    # 벤치마크 통계는 기본 키를 반환한다.
    _bm = calculate_benchmark_statistics(monthly[["전략"]].assign(벤치=monthly["전략"]), "전략", "벤치", cfg)
    assert set(["tracking_error", "information_ratio", "beta", "alpha_annualized_arithmetic", "downside_capture"]).issubset(_bm)

    # v2-16: 전체 일별 위험계산은 유지하면서 채팅 Drawdown payload만 제한한다.
    # CHAT_PAYLOAD_MAX_DRAWDOWN_POINTS regression
    _long_dd = drawdown_series(daily["전략"])
    _compact_dd = _compress_drawdown_for_chat(_long_dd)
    assert len(_compact_dd) <= CHAT_PAYLOAD_MAX_DRAWDOWN_POINTS
    assert _compact_dd.index[0] == _long_dd.index[0]
    assert _compact_dd.index[-1] == _long_dd.index[-1]
    assert float(_long_dd.min()) == float(_compact_dd.min())
    assert TEMPLATE_VERSION == "v2-16"


if __name__ == "__main__":
    _self_test()
    print("SELF TEST: PASS")
    print(CHATGPT_RENDERING_RULES)