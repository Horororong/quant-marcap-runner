"""
quant_backtest_template_CURRENT.py

표준 퀀트 백테스트 템플릿 v2-17 / CURRENT (2026-10 canonical performance)

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
   - 2001~2026(가용 최신일)
   - 2021~2026(가용 최신일)
   - 가능한 최장기간~2026(가용 최신일)
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
from functools import lru_cache
from typing import Optional, Dict, Any, Tuple
import json
import math

import numpy as np
import pandas as pd

from execution_contract import PERFORMANCE_TEMPLATE_VERSION

TEMPLATE_VERSION = PERFORMANCE_TEMPLATE_VERSION
CHAT_PAYLOAD_MAX_DRAWDOWN_POINTS = 480


# =========================================================
# 0. 프로젝트 데이터 소스 계약 (v2-15)
# =========================================================

PROJECT_GITHUB_REPO = "Horororong/quant-marcap-runner"
PROJECT_DATA_PRIORITY = [
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
    "us_etf": ".github/workflows/update-etf-data.yml",
    "market_and_proxy": ".github/workflows/update-market-data.yml",
}

BACKTEST_EXECUTION_CONTRACT = """
사용자가 '백테스트해줘', '백테스트', '전략 검증' 등 백테스트 실행을 요청하면 다음 순서를 기본 강제한다.

1) 항상 이 CURRENT v2-17 템플릿의 계산/검증/출력 규칙을 사용한다.
2) 필요한 가격, 지수, 환율, 거시, 재무, 프록시 데이터가 이미 사용자 GitHub 저장소
   Horororong/quant-marcap-runner 에 존재하는지 먼저 탐색한다.
3) GitHub에 존재하는 데이터가 충분하면 외부 데이터 제공업체를 우선 사용하지 않는다.
4) 필요한 데이터가 GitHub에 없거나 요구기간이 부족하면 데이터를 임의 생성하지 않는다.
5) 누락 데이터가 반복수집 가능한 자산/시계열이면 자동수집 레지스트리에 추가한다.
   - 미국 ETF: config/etf_universe.csv
   - 한국 ETF: config/kr_etf_universe.csv
   - 장기 프록시/전략별 미수집 데이터: config/strategy_data_collection.csv
6) 레지스트리 추가만으로 기존 수집기가 처리 가능한 경우, 해당 주간 GitHub Actions가 이후 자동 갱신하도록 한다.
7) 기존 수집기가 해당 데이터 유형을 처리하지 못하면, 적절한 수집 스크립트와 workflow를 추가/수정하여
   자동 갱신 경로를 함께 만든다. 단, API 키/유료 권한/법적 접근이 필요한 경우에는 임의로 대체하지 않고 한계를 명시한다.
8) 수집기 추가/수정 후에는 데이터 저장 경로, 시작일, 빈도, 수정주가/총수익 여부, 결측치, 기업행위 반영 여부를 기록한다.
9) 데이터가 아직 확보되지 않은 상태에서 백테스트 수치를 만들지 않는다. 확보 가능한 구간만 조용히 축약하지 않고
   표준기간 충족 실패를 명시하거나, 검증 가능한 대체 프록시를 별도 '탐색적' 결과로 구분한다.
10) 모든 백테스트 산출물은 비용 전/후를 구분하고, 4개 표준기간을 유지한다.
11) 차트 출력은 버전 1을 기본으로 한다.
    - 2001~현재: 누적자산 / Log2 누적자산 / Drawdown
    - 2021~현재: 누적자산 / Log2 누적자산 / Drawdown
    - 최장~현재: 누적자산 / Log2 누적자산 / Drawdown
    총 9개 인라인 차트.
12) 버전 1을 현재 채팅 UI에서 안정적으로 렌더링할 수 없을 때만 버전 2로 fallback한다.
    - 누적자산 / Log2 / Drawdown 3개 차트
    - 각 차트에 2001 / 2021 / 최장 기간 선택 UI
13) 책 검증기간은 성과표 및 책 수치 비교에 포함하지만 기본 차트에서는 제외한다.
"""


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

    # 표준 분석의 마지막 연도. 실제 종료일은 데이터 최신일로 제한된다.
    standard_end_year: int = field(default_factory=lambda: pd.Timestamp.today().year)
    # 데이터 가용성 기준일. None이면 실행일을 사용한다.
    as_of_date: Optional[str] = None

    market_calendar: Optional[str] = None
    # CURRENT uses 2001; PROJECT compatibility callers can explicitly retain 2000.
    standard_start_year: int = 2001

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
            raise ValueError("market_calendar must be a nonempty calendar name")
        if self.standard_start_year not in (2000, 2001):
            raise ValueError("standard_start_year must be 2000 (legacy PROJECT) or 2001 (CURRENT)")


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
    df = nav.copy()
    df.index = pd.to_datetime(df.index).normalize()
    df = df.sort_index()
    _basic_nav_checks(df, "daily_nav")
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
    2. from_2001       : 2001~가용 최신일(최대 2026년)
    3. from_2021       : 2021~가용 최신일(최대 2026년)
    4. longest         : 가능한 최장기간~가용 최신일(최대 2026년)
    """
    m = validate_monthly_nav(monthly_nav, config)
    return standard_period_windows_from_dates(m.index, config)


def standard_period_windows_from_dates(
    monthly_dates: pd.DatetimeIndex,
    config: BacktestConfig,
) -> Dict[str, Tuple[pd.Timestamp, pd.Timestamp, str]]:
    """The same canonical period policy, usable before any NAV is computed."""
    dates = pd.DatetimeIndex(monthly_dates).normalize()
    if dates.empty or dates.hasnans or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("canonical monthly dates must be nonempty, unique and ordered")
    months = dates.to_period("M")
    if not dates.equals(months.to_timestamp("M")) or not months.equals(pd.period_range(months[0], months[-1], freq="M")):
        raise ValueError("canonical monthly dates must be consecutive month ends")
    data_start = dates[0]
    data_end = min(dates[-1], pd.Timestamp(f"{config.standard_end_year}-12-31"))

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
        f"from_{config.standard_start_year}": pd.Timestamp(f"{config.standard_start_year}-01-01"),
        "from_2021": pd.Timestamp("2021-01-01"),
        "longest": data_start,
    }

    # 고정 기간은 데이터가 부족하다고 조용히 뒤로 당기지 않는다.
    # 필요한 과거 자료가 없으면 프록시/백필을 먼저 준비하도록 명시적으로 실패한다.
    if data_start.to_period("M") > pd.Period(f"{config.standard_start_year}-01", freq="M"):
        raise ValueError(
            f"{config.standard_start_year}~기간 고정 조건을 충족할 수 없습니다. 데이터 시작월={data_start:%Y-%m}. "
            f"{config.standard_start_year}-01부터의 프록시/백필 데이터를 준비하십시오."
        )
    if data_start.to_period("M") > pd.Period("2021-01", freq="M"):
        raise ValueError(
            f"2021~기간 고정 조건을 충족할 수 없습니다. 데이터 시작월={data_start:%Y-%m}. "
            "2021-01부터의 데이터를 준비하십시오."
        )

    return {
        "book_validation": (book_start, book_end, f"책 검증 {book_start:%Y-%m}~{book_end:%Y-%m}"),
        f"from_{config.standard_start_year}": (starts[f"from_{config.standard_start_year}"], data_end, f"{config.standard_start_year}~{data_end:%Y-%m}"),
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

@lru_cache(maxsize=16)
def _market_calendar(market_calendar: str, start_year: int, end_year: int):
    import exchange_calendars as xcals
    return xcals.get_calendar(market_calendar, start=f"{start_year-1}-01-01", end=f"{end_year+1}-12-31")


def expected_market_sessions(start: pd.Timestamp, end: pd.Timestamp, market_calendar: str) -> pd.DatetimeIndex:
    """Exact named-exchange sessions; explicit bounds also support historical reports."""
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    cal = _market_calendar(str(market_calendar), start.year, end.year)
    dates = pd.DatetimeIndex(cal.sessions_in_range(start, end))
    return dates.tz_localize(None) if dates.tz is not None else dates

def assert_daily_session_coverage(daily: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, market_calendar: str) -> None:
    expected = expected_market_sessions(start, end, market_calendar)
    actual = pd.DatetimeIndex(daily.loc[start:end].index).normalize()
    missing, extra = expected.difference(actual), actual.difference(expected)
    if len(missing) or len(extra):
        raise ValueError(f"daily NAV session mismatch ({market_calendar}): "
                         f"missing={len(missing)} {missing[:5].strftime('%Y-%m-%d').tolist()}, "
                         f"extra={len(extra)} {extra[:5].strftime('%Y-%m-%d').tolist()}")

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
        expected = expected_market_sessions(effective_start, effective_end, str(calendar_name))
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
    *, requested_period: bool = False,
) -> pd.DataFrame:
    """
    CAGR/Sharpe/변동성 = 월별 NAV
    MDD/회복기간 = 일별 NAV 우선, 없으면 월별 fallback
    """
    if requested_period:
        if daily_nav is None or not config.market_calendar:
            raise ValueError("requested-period metrics require daily NAV and an explicit exchange calendar")
        dnav = validate_daily_nav(daily_nav)
        assert_daily_session_coverage(dnav, dnav.index[0], dnav.index[-1], config.market_calendar)
        if dnav.index[-1] > pd.Timestamp(config.as_of_date).normalize():
            raise ValueError("requested NAV extends beyond as_of_date")
        baseline = dnav.attrs.get("baseline_date")
        if baseline is None or pd.Timestamp(baseline) > dnav.index[0]:
            raise ValueError("requested metrics require an explicit observed/inception baseline")
        mnav = dnav
    else:
        mnav = validate_monthly_nav(monthly_nav, config, enforce_expected=False)
        dnav = validate_daily_nav(daily_nav) if daily_nav is not None else None

    if dnav is not None and not requested_period:
        missing = [c for c in mnav.columns if c not in dnav.columns]
        if missing:
            raise AssertionError(f"daily_nav에 전략 열이 없습니다: {missing}")

        # 공개 함수 calculate_metrics()를 직접 호출하더라도 월/일 NAV를
        # 서로 다른 전략에서 섞어 쓰지 못하게 한다.
        if dnav.attrs.get("coverage_verified", False) and config.market_calendar is None:
            _check_daily_monthly_consistency(mnav, dnav)
        elif not _daily_full_coverage(
            dnav, dnav.index[0] if dnav.attrs.get("allow_partial_first_month", False) else mnav.index[0], mnav.index[-1], market_calendar=config.market_calendar,
            allow_partial_first_month=bool(dnav.attrs.get("allow_partial_first_month", False))
        ):
            dnav = None
        else:
            _check_daily_monthly_consistency(mnav, dnav)

    rows = []
    for name in mnav.columns:
        s_month = mnav[name].astype(float)
        r = requested_complete_month_returns(s_month, config) if requested_period else monthly_returns_from_nav(s_month)
        # 일반적인 완전월 자료는 월수/12가 정확하고 재현성이 높다.
        # 다만 데이터 inception이 월 중간인 최장기간처럼 실제 기준일을 알고 있는 경우에는
        # 짧은 첫 달을 1개월로 과대계상하지 않도록 실제 경과일수로 CAGR을 연환산한다.
        # 완전월 구간은 월수/periods_per_year로 연환산한다. 실제 일수 연환산은
        # 월중 inception처럼 명시적으로 performance_baseline_date를 복원한 경우에만 사용한다.
        performance_baseline = mnav.attrs.get("baseline_date") if requested_period else mnav.attrs.get("performance_baseline_date")
        if performance_baseline is not None:
            elapsed_days = (s_month.index[-1] - pd.Timestamp(performance_baseline)).days
            if elapsed_days <= 0 and not requested_period:
                raise AssertionError("CAGR 기준일이 종료일보다 늦거나 같습니다.")
            years = elapsed_days / 365.2425
        else:
            years = len(r) / config.periods_per_year
        final_multiple = float(s_month.iloc[-1])
        cagr = final_multiple ** (1.0 / years) - 1.0 if years > 0 else np.nan
        if requested_period and elapsed_days < 365:
            cagr = np.nan

        # inception이 월중이면 첫 월 수익은 완전한 한 달 수익이 아니다.
        # CAGR에는 실제 경과일수로 반영하되 Sharpe/변동성의 월별 표본에서는 제외한다.
        stats_r = r
        if performance_baseline is not None and len(r) > 0 and not requested_period:
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
        if requested_period and len(risk_s) < 2:
            mdd_value = np.nan
            recovery = {"days": np.nan, "months": np.nan}
        calmar = cagr / abs(mdd_value) if mdd_value < 0 else np.nan
        monthly_win_rate = float((stats_r > 0).mean()) if len(stats_r) else np.nan

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


REQUESTED_REPORT_CONTRACT_VERSION = "1"


def validate_report_periods(raw: Any) -> list[dict]:
    """Strict report specification, separate from strategy semantics/fingerprint."""
    import re
    if not isinstance(raw, list) or not 1 <= len(raw) <= 32:
        raise ValueError("report periods must be a list of 1..32 objects")
    out, ids = [], set()
    for item in raw:
        if not isinstance(item, dict) or set(item) - {"id", "label", "start", "end"}:
            raise ValueError("report period has unknown fields")
        if not {"id", "start", "end"} <= set(item):
            raise ValueError("report period requires id/start/end")
        key = item["id"]
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", key) or key in ids:
            raise ValueError("report period id must be unique and safe")
        ids.add(key)
        for field, token in (("start", "longest"), ("end", "latest")):
            value = item[field]
            if value == token:
                continue
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("report dates require YYYY-MM-DD or explicit longest/latest")
            if pd.Timestamp(value).date().isoformat() != value:
                raise ValueError("invalid report date")
        if item["start"] != "longest" and item["end"] != "latest" and item["start"] > item["end"]:
            raise ValueError("report period start must not exceed end")
        label = item.get("label", key)
        if not isinstance(label, str) or not label.strip() or len(label) > 160:
            raise ValueError("report label must be a nonempty string up to 160 characters")
        out.append({**item, "label": label})
    return out


def requested_period_readiness(dates: pd.DatetimeIndex, periods: list[dict], config: BacktestConfig) -> dict:
    periods = validate_report_periods(periods)
    dates = pd.DatetimeIndex(dates).normalize()
    if dates.empty or dates.hasnans or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("requested report source dates must be nonempty, unique and ordered")
    if not config.market_calendar or config.as_of_date is None:
        raise ValueError("requested reports require an explicit calendar and as_of_date")
    as_of = pd.Timestamp(config.as_of_date).normalize()
    available = dates[dates <= as_of]
    rows = {}
    for item in periods:
        row = {**item, "status": "data_gap", "reason": "데이터 부족", "ready": False}
        rows[item["id"]] = row
        if available.empty:
            row["reason"] = "기준일까지 검증된 NAV가 없습니다."
            continue
        start = available[0] if item["start"] == "longest" else pd.Timestamp(item["start"])
        end = available[-1] if item["end"] == "latest" else pd.Timestamp(item["end"])
        row.update(requested_start=start.date().isoformat(), requested_end=end.date().isoformat())
        expected = expected_market_sessions(start, end, config.market_calendar) if start <= end else pd.DatetimeIndex([])
        if end > as_of:
            row["reason"] = "요청 종료일이 자료 기준일보다 늦습니다."
        elif expected.empty:
            row["reason"] = "요청 기간에 거래일이 없습니다."
        elif len(expected.difference(available)):
            missing = expected.difference(available)
            row["reason"] = f"요청 기간의 거래일 NAV {len(missing)}개 부족 (첫 누락 {missing[0]:%Y-%m-%d}). 시작일을 이동하지 않습니다."
        else:
            row.update(status="ready", ready=True, reason=None, actual_start=expected[0].date().isoformat(),
                       actual_end=expected[-1].date().isoformat(), observations=len(expected))
    return {"contract_version": REQUESTED_REPORT_CONTRACT_VERSION, "mode": "requested_period_report",
            "ready": any(p["ready"] for p in rows.values()), "complete": all(p["ready"] for p in rows.values()),
            "as_of_date": as_of.date().isoformat(), "periods": rows}


def requested_complete_month_returns(nav: pd.Series, config: BacktestConfig) -> pd.Series:
    """Only full exchange months; partial boundary months never enter monthly ratios."""
    baseline_date = pd.Timestamp(nav.attrs["baseline_date"])
    extended = nav.copy()
    if baseline_date < nav.index[0]:
        extended = pd.concat([pd.Series([1.0], index=[baseline_date]), extended])
    values = {}
    for month in nav.index.to_period("M").unique():
        sessions = expected_market_sessions(month.start_time, month.end_time.normalize(), config.market_calendar)
        prior = expected_market_sessions(sessions[0] - pd.Timedelta(days=31), sessions[0], config.market_calendar)
        prior_date = prior[prior < sessions[0]][-1]
        if len(sessions.difference(nav.index)) == 0 and prior_date in extended.index:
            values[month.to_timestamp("M")] = float(extended.loc[sessions[-1]] / extended.loc[prior_date] - 1)
    return pd.Series(values, dtype=float)


def _finite_metric(value):
    return float(value) if pd.notna(value) and np.isfinite(value) else None


def dashboard_period_data(daily: pd.DataFrame, metrics: pd.DataFrame, label: str, *, baseline_date=None,
                          requested_start=None, requested_end=None, calendar=None, monthly_samples=None) -> dict:
    """One standard owner for monetary normalization, multiples, DD and log ticks."""
    rows = {}
    for name in daily.columns:
        s = daily[name]
        dd = drawdown_series(s)
        compact = _compress_drawdown_for_chat(dd)
        # Preserve extrema, boundaries and exactly the same dates in all three charts.
        chosen = compact.index.union(pd.DatetimeIndex([s.index[0], s.index[-1]])).sort_values()
        anchor = pd.Timestamp(baseline_date) if baseline_date is not None else None
        points = []
        if anchor is not None and anchor < s.index[0]:
            points.append({"date": anchor.date().isoformat(), "multiple": 1.0, "asset": 10000.0,
                           "log2": 0.0, "drawdown_pct": 0.0, "baseline": True})
        points += [{"date": dt.date().isoformat(), "multiple": float(s.loc[dt]), "asset": float(s.loc[dt] * 10000),
                    "log2": float(np.log2(s.loc[dt])), "drawdown_pct": float(dd.loc[dt] * 100), "baseline": False}
                   for dt in chosen]
        m = metrics.loc[name]
        row = {key: _finite_metric(m[col]) for key, col in {
            "cagr": "CAGR", "cumulative_return": "누적수익률", "mdd": "MDD", "annual_volatility": "연환산_표준편차",
            "sharpe": "Sharpe", "recovery_days": "최대회복기간_일", "final_multiple": "최종배수"}.items()}
        row["final_asset"] = float(m["최종배수"] * 10000)
        if row["final_asset"] != points[-1]["asset"]:
            if not np.isclose(row["final_asset"], points[-1]["asset"], rtol=1e-12, atol=1e-8):
                raise AssertionError("dashboard ending wealth differs from canonical metrics")
        row["mdd_source"] = str(m["MDD_source"])
        row["unavailable"] = {key: ("샤프 분모 0 또는 완결 월 표본 부족" if key == "sharpe" else
                                    "표본 부족: CAGR는 365일 이상, 월별 통계는 완결 월 2개 이상 필요" if key in ("cagr", "annual_volatility") else "계산 불가/표본 부족")
                              for key, value in row.items() if value is None}
        rows[name] = {"metrics": row, "points": points}
    logs = [p["log2"] for value in rows.values() for p in value["points"]]
    ticks = list(range(min(0, math.floor(min(logs))), max(1, math.ceil(max(logs))) + 1))
    return {"status": "ready", "ready": True, "label": label,
            "actual_start": daily.index[0].date().isoformat(), "actual_end": daily.index[-1].date().isoformat(),
            "requested_start": requested_start, "requested_end": requested_end,
            "baseline_date": pd.Timestamp(baseline_date).date().isoformat() if baseline_date is not None else None,
            "ending_asset_label": "해당 기간 종료자산", "ending_asset_date": daily.index[-1].date().isoformat(),
            "initial_capital": 10000, "currency": "USD standardized", "fx_applied": False, "additional_contributions": 0,
            "risk_observations_full": len(daily), "monthly_statistical_samples": monthly_samples,
            "series": rows, "log_ticks": {"values": [2.0 ** k for k in ticks], "labels": [f"{2.0 ** k:g}배" for k in ticks]},
            "calendar": calendar, "risk_frequency": "daily" if all(m["metrics"]["mdd_source"] == "daily" for m in rows.values()) else "monthly_fallback"}


def run_requested_periods(daily_nav: pd.DataFrame, config: BacktestConfig, periods: list[dict]) -> dict:
    dnav = validate_daily_nav(daily_nav)
    if not np.allclose(dnav.iloc[0].to_numpy(float), 1.0, atol=1e-12, rtol=0):
        raise ValueError("requested report NAV must start at observed initial capital (1.0); no silent rescaling")
    assert_daily_session_coverage(dnav, dnav.index[0], dnav.index[-1], config.market_calendar)
    readiness = requested_period_readiness(dnav.index, periods, config)
    results = {}
    for key, row in readiness["periods"].items():
        if not row["ready"]:
            results[key] = dict(row)
            continue
        selected = _slice_and_rebase(dnav, pd.Timestamp(row["actual_start"]), pd.Timestamp(row["actual_end"]))
        if selected.attrs["baseline_date"] is None:
            selected.attrs["baseline_date"] = selected.index[0]  # observed cash/inception anchor
        metrics = calculate_metrics(selected, config, selected, requested_period=True)
        samples = len(requested_complete_month_returns(selected.iloc[:, 0], config))
        data = dashboard_period_data(selected, metrics, row["label"], baseline_date=selected.attrs["baseline_date"],
                                     requested_start=row["requested_start"], requested_end=row["requested_end"],
                                     calendar=config.market_calendar, monthly_samples=samples)
        data["limitations"] = (["짧은 표본의 실행·보고 검증입니다. 장기 투자 검증 결과가 아닙니다."] if samples < 12 else [])
        data["metrics_frame"] = metrics
        data["daily_nav_frame"] = selected
        results[key] = data
    return {"contract_version": REQUESTED_REPORT_CONTRACT_VERSION, "readiness": readiness, "periods": results}




# =========================================================
# 5. 표준 4기간 실행
# =========================================================

def calculate_benchmark_statistics(
    monthly_nav: pd.DataFrame,
    strategy_col: str,
    benchmark_col: str,
    config: BacktestConfig,
    *, requested_period: bool = False,
) -> Dict[str, float]:
    """월별 NAV 기준 tracking error / IR / alpha / beta / downside capture를 계산한다."""
    m = (validate_daily_nav(monthly_nav[[strategy_col, benchmark_col]]) if requested_period else
         validate_monthly_nav(monthly_nav[[strategy_col, benchmark_col]], config, enforce_expected=False))
    if strategy_col == benchmark_col:
        raise ValueError("strategy and benchmark columns must differ")
    rs = requested_complete_month_returns(m[strategy_col], config) if requested_period else monthly_returns_from_nav(m[strategy_col])
    rb = requested_complete_month_returns(m[benchmark_col], config) if requested_period else monthly_returns_from_nav(m[benchmark_col])
    x = pd.concat([rs.rename("s"), rb.rename("b")], axis=1).dropna()
    baseline = m.attrs.get("performance_baseline_date")
    if baseline is not None and pd.Timestamp(baseline).to_period("M") == m.index[0].to_period("M") and not requested_period:
        x = x.iloc[1:]
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
                d_slice.attrs["allow_partial_first_month"] = allow_partial_first
                _check_daily_monthly_consistency(m_slice, d_slice)
                # 월별 시계열에 직전 기준월이 없는 inception 구간은 일별 첫 관측일로
                # 실제 성과 시작 직전 기준일을 복원해 partial-month CAGR 왜곡을 막는다.
                if m_slice.attrs.get("baseline_date") is None:
                    if config.market_calendar:
                        prior = expected_market_sessions(d_slice.index[0] - pd.Timedelta(days=31), d_slice.index[0], config.market_calendar)
                        m_slice.attrs["performance_baseline_date"] = prior[prior < d_slice.index[0]][-1]
                    else:
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

def _compress_drawdown_for_chat(dd: pd.Series, max_points: int = CHAT_PAYLOAD_MAX_DRAWDOWN_POINTS) -> pd.Series:
    """채팅 렌더링 전용 축약.

    계산/MDD 산출에는 원본 일별 시계열을 그대로 사용하고, 화면 표시용 Drawdown만 축약한다.
    각 구간의 최저점과 구간 끝점을 보존해 단순 등간격 샘플링보다 MDD/회복 형태 손실을 줄인다.
    """
    s = dd.dropna().astype(float).sort_index()
    if len(s) <= max_points:
        return s
    if max_points < 8:
        raise ValueError("max_points는 8 이상이어야 합니다.")

    interior = s.iloc[1:-1]
    bucket_count = max(1, (max_points - 2) // 2)
    edges = np.linspace(0, len(interior), bucket_count + 1, dtype=int)
    keep = {s.index[0], s.index[-1]}

    for i in range(bucket_count):
        chunk = interior.iloc[edges[i]:edges[i + 1]]
        if chunk.empty:
            continue
        keep.add(chunk.idxmin())
        keep.add(chunk.index[-1])

    out = s.loc[sorted(keep)]
    if len(out) > max_points:
        # 부동소수점/경계 중복 상황에서도 상한을 확실히 지킨다.
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
        if dnav.attrs.get("coverage_verified", False) and config.market_calendar is None:
            _check_daily_monthly_consistency(mnav, dnav)
        elif not _daily_full_coverage(
            dnav, dnav.index[0] if dnav.attrs.get("allow_partial_first_month", False) else mnav.index[0], mnav.index[-1], market_calendar=config.market_calendar,
            allow_partial_first_month=bool(dnav.attrs.get("allow_partial_first_month", False))):
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
        # 성과/위험 계산은 전체 일별 데이터를 사용하되, 채팅 시각화 payload만 축약한다.
        dd_chat = _compress_drawdown_for_chat(dd)
        drawdown_rows = [{
            "date": dt.strftime("%Y-%m-%d"),
            "drawdown_pct": round(float(v * 100.0), 6),
        } for dt, v in dd_chat.items()]

        m = metrics.loc[name]
        series_payload[name] = {
            "metrics": {
                "CAGR_pct": round(float(m["CAGR"] * 100.0), 4),
                "MDD_pct": round(float(m["MDD"] * 100.0), 4),
                "MDD_source": str(m["MDD_source"]),
                "Sharpe": None if pd.isna(m["Sharpe"]) else round(float(m["Sharpe"]), 4),
                "Sortino": None if pd.isna(m["Sortino"]) else round(float(m["Sortino"]), 4),
                "Calmar": None if pd.isna(m["Calmar"]) else round(float(m["Calmar"]), 4),
                "monthly_win_rate_pct": None if pd.isna(m["월간승률"]) else round(float(m["월간승률"] * 100), 4),
                "cumulative_return_pct": round(float(m["누적수익률"] * 100), 4),
                "annual_std_pct": None if pd.isna(m["연환산_표준편차"]) else round(float(m["연환산_표준편차"] * 100.0), 4),
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
    - 기간 버튼: 2001~현재 / 2021~현재 / 최장~현재
    - 기본 선택: 2001~현재
    - 버전 1(우선): 기간 선택 UI를 안정적으로 구현할 수 없으면 3기간 x 3차트 = 총 9개 인라인 차트를 모두 렌더링한다.
    - 버전 1 차트 순서: 기간별로 누적자산 -> Log2 -> Drawdown, 기간 순서는 2001 -> 2021 -> 최장.
    - 전략/벤치마크 시리즈는 가능한 경우 체크박스/토글로 켜고 끌 수 있게 한다.
    - 책 검증기간은 성과표에는 포함하지만 차트 기간 버튼/9개 fallback에서는 제외한다.
    """
    if not payloads:
        raise ValueError("최소 1개의 payload가 필요합니다.")

    periods = {p["period_key"]: p for p in payloads}
    historical_key = "from_2001" if "from_2001" in periods else "from_2000"
    selector_labels = {
        "from_2000": "2000~현재",
        "from_2001": "2001~현재",
        "from_2021": "2021~현재",
        "longest": "최장~현재",
    }
    selector_order = [k for k in (historical_key, "from_2021", "longest") if k in periods]
    if not selector_order:
        raise ValueError("기간 선택용 payload(longest/from_2001/from_2021)가 최소 1개 필요합니다.")

    default_period = selector_order[0]
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
                "period_order": [historical_key, "from_2021", "longest"],
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
                "period_order": [k for k in (historical_key, "from_2021", "longest") if k in periods],
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
    if dnav is not None and _daily_full_coverage(dnav, mnav.index[0], mnav.index[-1]):
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
   B. 2001~현재
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
     · 2001~현재 / 2021~현재 / 최장~현재
     · 기본 선택은 2001~현재
     · 총 인라인 차트 수는 3개다.
   - 버전 1(우선): 버전 2의 네이티브 기간 선택 UI를 사용할 수 없거나 안정적 렌더링이 불가능하면
     2001~현재 / 2021~현재 / 최장~현재의 3기간 각각에 누적자산 / Log2 / Drawdown을 모두 표시한다.
     · 총 인라인 차트 수는 9개다.
     · 순서: 2001 3개 -> 2021 3개 -> 최장 3개.
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
21. 새 대화에서도 사용자가 단순히 '백테스트해줘'라고 요청하면 별도 지시 없이 이 CURRENT v2-17 템플릿의 계산 및 출력 규칙을 적용한다.
22. 백테스트에 필요한 데이터는 사용자 GitHub 저장소 Horororong/quant-marcap-runner 를 최우선으로 탐색한다.
23. GitHub에 필요한 데이터가 없거나 기간이 부족하면 임의 데이터로 대체하지 않는다.
24. 반복 수집 가능한 누락 데이터는 config/etf_universe.csv, config/kr_etf_universe.csv 또는 config/strategy_data_collection.csv 중 적절한 자동수집 레지스트리에 추가한다.
25. 기존 수집기가 처리하지 못하는 데이터 유형이면 수집 스크립트/workflow도 함께 보완하여 이후 자동 업데이트 경로를 만든다.
26. 외부 데이터는 GitHub 데이터가 없거나 품질/기간상 불충분하고, 출처·정의·시점 정합성을 검증할 수 있을 때만 보조적으로 사용한다.
27. 자동수집 레지스트리나 workflow를 변경했다면 무엇을 왜 추가했는지 최종 보고에 명시한다.
28. 전략별 스크립트가 CAGR/MDD/Sharpe/차트 규칙을 재구현하지 않는다. 전략 스크립트는 일별 NAV 산출까지만 담당하고, 성과표/위험지표/채팅 차트 payload는 CURRENT 템플릿 또는 quant_backtest_postprocess.py가 단일 계산원(single source of truth)으로 생성한다.
29. 계산 정확도와 채팅 표시량을 분리한다. MDD와 회복기간은 전체 일별 NAV로 계산하되 Drawdown 차트 표시점은 CURRENT의 보존형 축약 로직을 사용한다.
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
    assert list(out.keys()) == ["book_validation", "from_2001", "from_2021", "longest"]
    assert out["from_2001"]["metrics"].loc["전략", "MDD_source"] == "daily"

    out_fallback = run_standard_backtest(monthly, cfg)
    assert out_fallback["metrics"].loc["전략", "MDD_source"] == "monthly_fallback"

    # 일별 데이터가 기간 중간부터만 있으면 장기구간은 월별 fallback이어야 한다.
    partial_daily = daily.loc["2021-01-01":].copy()
    out_partial = run_four_periods(monthly, cfg, partial_daily)
    assert out_partial["book_validation"]["metrics"].loc["전략", "MDD_source"] == "monthly_fallback"
    assert out_partial["from_2001"]["metrics"].loc["전략", "MDD_source"] == "monthly_fallback"
    assert out_partial["from_2021"]["metrics"].loc["전략", "MDD_source"] == "monthly_fallback"
    assert out_partial["longest"]["metrics"].loc["전략", "MDD_source"] == "monthly_fallback"

    # 2000 이후에 시작하는 월별 데이터로 2000~ 기간을 조용히 축약하면 안 된다.
    late_monthly = monthly.loc["2005-01-31":].copy()
    late_cfg = BacktestConfig(title="late", book_start="2005-01-01", book_end="2021-12-31")
    try:
        run_four_periods(late_monthly, late_cfg)
        raise AssertionError("2000 고정기간 데이터 부족을 감지하지 못했습니다.")
    except ValueError as e:
        assert "2001~기간 고정 조건" in str(e)

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
    assert inc_out["from_2001"]["metrics"].loc["전략", "MDD_source"] == "daily"

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
        {"periods_per_year": 0},        {"risk_free_rate": -1.5},
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
    reg_s = reg_daily.loc["2001-01-01":"2026-08-31", "60/40"]
    reg_base = reg_daily.loc[:"2000-12-31", "60/40"].iloc[-1]
    reg_s = reg_s / reg_base
    independent_mdd = float((reg_s / reg_s.cummax() - 1.0).min())
    template_mdd = float(reg_out["from_2001"]["metrics"].loc["60/40", "MDD"])
    assert abs(template_mdd - independent_mdd) < 1e-12

    # v2-15/CURRENT interactive-dashboard + project-data-contract regression test.
    p_long = out["longest"]["chat_payload"]
    p_2001 = out["from_2001"]["chat_payload"]
    p_2021 = out["from_2021"]["chat_payload"]
    combined = combine_period_payloads(p_long, p_2001, p_2021)
    assert combined["schema_version"] == 8
    assert combined["render_target"] == "chatgpt_interactive_backtest_dashboard"
    assert combined["presentation_versions"]["version_2"]["inline_chart_count"] == 3
    assert combined["presentation_versions"]["version_1"]["inline_chart_count"] == 9
    assert combined["controls"]["period_buttons"]["default_period"] == "from_2001"
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
    assert PROJECT_COLLECTION_REGISTRIES["us_etf"] == "config/etf_universe.csv"
    assert PROJECT_COLLECTION_REGISTRIES["kr_etf"] == "config/kr_etf_universe.csv"
    assert PROJECT_COLLECTION_REGISTRIES["strategy_long_or_missing"] == "config/strategy_data_collection.csv"
    assert "GitHub" in BACKTEST_EXECUTION_CONTRACT
    assert "버전 1" in BACKTEST_EXECUTION_CONTRACT


if __name__ == "__main__":
    _self_test()
    print("SELF TEST: PASS")
    print(CHATGPT_RENDERING_RULES)
