from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence
import os

import pandas as pd

PROJECT_GITHUB_REPO = "Horororong/quant-marcap-runner"
KRX_EQUITY_YEARLY_DIR = "data/krx_equities/yearly"
KRX_EQUITY_STATUS_FILE = "data/status/krx_equities_status.csv"
DART_FULL_HISTORY_DIR = "data/financials/full_history"

KRX_EQUITY_CANONICAL_COLUMNS = [
    "Date", "Code", "Name", "Market", "Dept", "MarketId", "Rank",
    "Open", "High", "Low", "Close", "Volume", "Amount",
    "Changes", "ChangeCode", "ChangesRatio", "Marcap", "Stocks",
    "Change", "UpDown", "Comp",
]

KRX_BACKTEST_DATA_CONTRACT = """
1. Korean individual-stock backtests use data/krx_equities/yearly/marcap-YYYY.parquet first.
2. Never rebuild historical membership from today's listing universe.
3. Do not silently remove preferred shares, SPACs, REITs, financials, IPOs or managed issues.
   Strategy-level exclusions must be stated explicitly.
4. A signal computed with close-t information cannot execute at the same close by default.
5. Financial factors become usable only on/after their actual filing_date.
6. Delisted/suspended/illiquid securities cannot be silently dropped.
7. Missing year files, duplicate Date+Code keys and insufficient requested history are hard errors.
"""


def resolve_project_root(repo_root: Optional[str | Path] = None) -> Path:
    candidates: list[Path] = []
    if repo_root is not None:
        candidates.append(Path(repo_root).expanduser())
    env_root = os.getenv("QUANT_REPO_ROOT", "").strip()
    if env_root:
        candidates.append(Path(env_root).expanduser())
    candidates.append(Path.cwd())
    try:
        candidates.append(Path(__file__).resolve().parents[1])
    except NameError:
        pass

    seen: set[Path] = set()
    for base in candidates:
        base = base.resolve()
        for root in [base, *base.parents]:
            if root in seen:
                continue
            seen.add(root)
            if (root / KRX_EQUITY_YEARLY_DIR).exists():
                return root
    raise FileNotFoundError(
        "quant-marcap-runner data root not found. "
        "Run inside the repository or pass repo_root / QUANT_REPO_ROOT."
    )


def _normalize_codes(codes: Optional[Iterable[str]]) -> Optional[set[str]]:
    if codes is None:
        return None
    x = {str(v).strip().zfill(6) for v in codes if str(v).strip()}
    return x or None


def available_years(repo_root: Optional[str | Path] = None) -> list[int]:
    root = resolve_project_root(repo_root)
    years: list[int] = []
    for p in sorted((root / KRX_EQUITY_YEARLY_DIR).glob("marcap-*.parquet")):
        try:
            years.append(int(p.stem.split("-")[-1]))
        except ValueError:
            pass
    if not years:
        raise FileNotFoundError("No KRX yearly parquet files found.")
    return sorted(set(years))


def read_status(repo_root: Optional[str | Path] = None) -> Dict[str, Any]:
    root = resolve_project_root(repo_root)
    path = root / KRX_EQUITY_STATUS_FILE
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    return {} if df.empty else df.iloc[-1].to_dict()


def load_krx_equity_panel(
    start: Optional[str | pd.Timestamp] = None,
    end: Optional[str | pd.Timestamp] = None,
    codes: Optional[Iterable[str]] = None,
    markets: Sequence[str] = ("KOSPI", "KOSDAQ"),
    columns: Optional[Sequence[str]] = None,
    repo_root: Optional[str | Path] = None,
    require_all_year_files: bool = True,
) -> pd.DataFrame:
    root = resolve_project_root(repo_root)
    yearly_dir = root / KRX_EQUITY_YEARLY_DIR
    years = available_years(root)

    start_ts = pd.Timestamp(start).normalize() if start is not None else None
    end_ts = pd.Timestamp(end).normalize() if end is not None else None
    if start_ts is not None and end_ts is not None and start_ts > end_ts:
        raise ValueError("start is later than end.")

    first_year = start_ts.year if start_ts is not None else min(years)
    last_year = end_ts.year if end_ts is not None else max(years)
    requested = list(range(first_year, last_year + 1))
    missing = [y for y in requested if y not in years]
    if require_all_year_files and missing:
        raise FileNotFoundError(
            f"Missing KRX yearly files: {missing}. Requested history is not silently shortened."
        )

    wanted = list(columns) if columns is not None else list(KRX_EQUITY_CANONICAL_COLUMNS)
    mandatory = ["Date", "Code", "Market"]
    for c in reversed(mandatory):
        if c not in wanted:
            wanted.insert(0, c)

    code_set = _normalize_codes(codes)
    market_set = {str(x).upper().strip() for x in markets}
    chunks: list[pd.DataFrame] = []

    for year in requested:
        path = yearly_dir / f"marcap-{year}.parquet"
        if not path.exists():
            continue
        try:
            import pyarrow.parquet as pq
            schema = set(pq.ParquetFile(path).schema.names)
            read_cols = [c for c in wanted if c in schema]
            df = pd.read_parquet(path, columns=read_cols)
        except ImportError:
            df = pd.read_parquet(path)
            df = df[[c for c in wanted if c in df.columns]].copy()

        for c in mandatory:
            if c not in df.columns:
                raise AssertionError(f"{path.name}: missing required column {c}")

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
        raise ValueError("No KRX observations match the requested conditions.")

    out = pd.concat(chunks, ignore_index=True, sort=False)
    out = out.sort_values(["Date", "Code"]).reset_index(drop=True)
    if out.duplicated(["Date", "Code"]).any():
        example = out.loc[
            out.duplicated(["Date", "Code"], keep=False), ["Date", "Code"]
        ].head(10)
        raise AssertionError(
            "Duplicate KRX Date+Code keys found:\n" + example.to_string(index=False)
        )

    if columns is not None:
        absent = [c for c in columns if c not in out.columns]
        if absent:
            raise KeyError(f"Requested columns do not exist in the panel: {absent}")

    out.attrs["source"] = "FinanceData/marcap via Horororong/quant-marcap-runner"
    out.attrs["point_in_time_universe"] = True
    out.attrs["survivorship_filter_applied"] = False
    out.attrs["loaded_years"] = [y for y in requested if y in years]
    out.attrs["status"] = read_status(root)
    return out


def field_matrix(panel: pd.DataFrame, field: str = "Close") -> pd.DataFrame:
    required = {"Date", "Code", field}
    missing = required.difference(panel.columns)
    if missing:
        raise KeyError(f"Missing columns for field matrix: {sorted(missing)}")
    x = panel[["Date", "Code", field]].copy()
    x[field] = pd.to_numeric(x[field], errors="coerce")
    return x.pivot(index="Date", columns="Code", values=field).sort_index()


def month_end_cross_sections(panel: pd.DataFrame) -> pd.DataFrame:
    if not {"Date", "Code"}.issubset(panel.columns):
        raise KeyError("panel must contain Date and Code.")
    x = panel.copy()
    x["Date"] = pd.to_datetime(x["Date"]).dt.normalize()
    x["Month"] = x["Date"].dt.to_period("M")
    month_end = x.groupby("Month", observed=True)["Date"].max().rename("MarketMonthEnd")
    x = x.join(month_end, on="Month")
    out = x[x["Date"] == x["MarketMonthEnd"]].copy()
    return out.drop(columns=["MarketMonthEnd"]).sort_values(["Date", "Code"]).reset_index(drop=True)


def load_backtest_bundle(
    start: Optional[str | pd.Timestamp] = None,
    end: Optional[str | pd.Timestamp] = None,
    codes: Optional[Iterable[str]] = None,
    markets: Sequence[str] = ("KOSPI", "KOSDAQ"),
    matrix_fields: Sequence[str] = ("Close",),
    repo_root: Optional[str | Path] = None,
) -> Dict[str, Any]:
    needed = [
        "Date", "Code", "Name", "Market", "Open", "High", "Low", "Close",
        "Volume", "Amount", "Marcap", "Stocks", "Changes", "ChangeCode",
        "ChangesRatio", "Change", "UpDown", "Comp",
    ]
    for field in matrix_fields:
        if field not in needed:
            needed.append(field)

    panel = load_krx_equity_panel(
        start=start,
        end=end,
        codes=codes,
        markets=markets,
        columns=needed,
        repo_root=repo_root,
    )
    matrices = {f: field_matrix(panel, f) for f in matrix_fields}
    return {
        "panel": panel,
        "matrices": matrices,
        "month_end_cross_sections": month_end_cross_sections(panel),
        "status": panel.attrs.get("status", {}),
        "data_contract": KRX_BACKTEST_DATA_CONTRACT,
    }


def load_dart_financial_rows(
    years: Sequence[int],
    periods: Sequence[str] = ("FY",),
    fs_div: str = "CFS",
    stock_codes: Optional[Iterable[str]] = None,
    repo_root: Optional[str | Path] = None,
) -> pd.DataFrame:
    root = resolve_project_root(repo_root)
    base = root / DART_FULL_HISTORY_DIR
    if not base.exists():
        raise FileNotFoundError(f"DART full_history path not found: {base}")

    periods_u = [str(x).upper().strip() for x in periods]
    fs = str(fs_div).upper().strip()
    files: list[Path] = []
    for year in sorted(set(int(y) for y in years)):
        for period in periods_u:
            files.extend(sorted(base.glob(f"dart_full_{year}_{period}_{fs}_*.csv.gz")))
    if not files:
        raise FileNotFoundError(
            f"No DART files for years={list(years)}, periods={periods_u}, fs_div={fs}"
        )

    code_set = _normalize_codes(stock_codes)
    chunks: list[pd.DataFrame] = []
    for path in files:
        df = pd.read_csv(path, low_memory=False)
        if "stock_code" not in df.columns:
            raise AssertionError(f"{path.name}: stock_code is missing.")
        df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
        if code_set is not None:
            df = df[df["stock_code"].isin(code_set)]
        if "filing_date" not in df.columns and "rcept_no" in df.columns:
            df["filing_date"] = df["rcept_no"].astype(str).str.slice(0, 8)
        if "filing_date" in df.columns:
            df["filing_date"] = pd.to_datetime(
                df["filing_date"], format="%Y%m%d", errors="coerce"
            )
        if len(df):
            chunks.append(df)
    if not chunks:
        raise ValueError("No DART rows match the requested conditions.")
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
    for c in (observation_date, code_col):
        if c not in observations.columns:
            raise KeyError(f"observations missing {c}")
    for c in (factor_available_date, factor_code_col):
        if c not in factors.columns:
            raise KeyError(f"factors missing {c}")

    left = observations.copy()
    right = factors.copy()
    left[observation_date] = pd.to_datetime(left[observation_date], errors="coerce")
    right[factor_available_date] = pd.to_datetime(
        right[factor_available_date], errors="coerce"
    )
    left[code_col] = left[code_col].astype(str).str.zfill(6)
    right[factor_code_col] = right[factor_code_col].astype(str).str.zfill(6)
    if factor_code_col != code_col:
        right = right.rename(columns={factor_code_col: code_col})

    left = left.sort_values([observation_date, code_col])
    right = right.sort_values([factor_available_date, code_col])
    out = pd.merge_asof(
        left,
        right,
        left_on=observation_date,
        right_on=factor_available_date,
        by=code_col,
        direction="backward",
        allow_exact_matches=True,
    )
    future = (
        out[factor_available_date].notna()
        & (out[factor_available_date] > out[observation_date])
    )
    if future.any():
        raise AssertionError("Future financial information leaked through PIT join.")
    return out


def _smoke_test() -> None:
    status = read_status()
    latest = pd.Timestamp(status.get("latest_date")).normalize()
    start = latest - pd.Timedelta(days=10)
    panel = load_krx_equity_panel(
        start=start,
        end=latest,
        columns=["Date", "Code", "Market", "Open", "Close", "Amount", "Marcap"],
    )
    close = field_matrix(panel, "Close")
    if panel.empty or close.empty:
        raise AssertionError("KRX smoke test returned empty data.")
    if panel.duplicated(["Date", "Code"]).any():
        raise AssertionError("KRX smoke test found duplicate Date+Code.")
    print(
        "KRX DATA SMOKE TEST: PASS",
        f"latest={latest.date()}",
        f"rows={len(panel)}",
        f"codes={panel['Code'].nunique()}",
        f"days={close.shape[0]}",
        sep=" | ",
    )


if __name__ == "__main__":
    _smoke_test()
