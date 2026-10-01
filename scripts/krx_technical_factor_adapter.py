from __future__ import annotations

"""PIT-safe KRX price-derived technical factor adapter.

The adapter compounds the exchange-reported daily ChangesRatio field instead of
raw close-to-close ratios. KRX reference prices are adjusted for events such as
stock splits, so ChangesRatio is a safer primitive for price momentum than
naively dividing unadjusted Close values.

No missing daily observation inside a requested window is silently filled.
A code with an incomplete window receives NaN for that factor.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

KRX_EQUITY_YEARLY_DIR = "data/krx_equities/yearly"


@dataclass(frozen=True)
class TechnicalFactorSpec:
    field: str
    lookback_sessions: int
    skip_sessions: int
    description: str
    calculation: str = "compound_return"

    def __post_init__(self) -> None:
        if self.lookback_sessions < 1:
            raise ValueError("lookback_sessions must be >= 1")
        if self.skip_sessions < 0 or self.skip_sessions >= self.lookback_sessions:
            raise ValueError("skip_sessions must satisfy 0 <= skip < lookback")
        if self.calculation not in {"compound_return", "annualized_volatility"}:
            raise ValueError(f"unsupported technical calculation: {self.calculation}")


TECHNICAL_FACTOR_SPECS: dict[str, TechnicalFactorSpec] = {
    "momentum_3_1": TechnicalFactorSpec(
        "momentum_3_1", 63, 21,
        "compound KRX daily ChangesRatio over roughly 3 months, skipping the latest 1 month",
    ),
    "momentum_6_1": TechnicalFactorSpec(
        "momentum_6_1", 126, 21,
        "compound KRX daily ChangesRatio over roughly 6 months, skipping the latest 1 month",
    ),
    "momentum_12_1": TechnicalFactorSpec(
        "momentum_12_1", 252, 21,
        "compound KRX daily ChangesRatio over roughly 12 months, skipping the latest 1 month",
    ),
    "momentum_12_0": TechnicalFactorSpec(
        "momentum_12_0", 252, 0,
        "compound KRX daily ChangesRatio over roughly 12 months through the signal date",
    ),
    "volatility_3m": TechnicalFactorSpec(
        "volatility_3m", 63, 0,
        "annualized sample standard deviation of KRX daily ChangesRatio over 63 sessions",
        calculation="annualized_volatility",
    ),
    "volatility_6m": TechnicalFactorSpec(
        "volatility_6m", 126, 0,
        "annualized sample standard deviation of KRX daily ChangesRatio over 126 sessions",
        calculation="annualized_volatility",
    ),
    "volatility_12m": TechnicalFactorSpec(
        "volatility_12m", 252, 0,
        "annualized sample standard deviation of KRX daily ChangesRatio over 252 sessions",
        calculation="annualized_volatility",
    ),
}


def technical_factor_catalog() -> list[dict]:
    return [
        {
            "field": spec.field,
            "lookback_sessions": spec.lookback_sessions,
            "skip_sessions": spec.skip_sessions,
            "calculation": spec.calculation,
            "description": spec.description,
        }
        for _, spec in sorted(TECHNICAL_FACTOR_SPECS.items())
    ]


class KrxTechnicalFactorAdapter:
    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root)
        self._year_cache: dict[int, pd.DataFrame | None] = {}

    def _year_path(self, year: int) -> Path:
        return self.repo_root / KRX_EQUITY_YEARLY_DIR / f"marcap-{int(year)}.parquet"

    def _load_year(self, year: int) -> pd.DataFrame | None:
        year = int(year)
        if year in self._year_cache:
            cached = self._year_cache[year]
            return None if cached is None else cached.copy()

        path = self._year_path(year)
        if not path.exists():
            self._year_cache[year] = None
            return None

        try:
            x = pd.read_parquet(path, columns=["Date", "Code", "ChangesRatio"])
        except Exception as exc:
            raise RuntimeError(f"{path}: failed to read technical factor inputs") from exc

        missing = {"Date", "Code", "ChangesRatio"} - set(x.columns)
        if missing:
            raise KeyError(f"{path}: missing technical factor columns {sorted(missing)}")

        x = x.copy()
        x["Date"] = pd.to_datetime(x["Date"], errors="coerce").dt.normalize()
        x["Code"] = x["Code"].astype(str).str.replace(".0", "", regex=False).str.zfill(6)
        x["ChangesRatio"] = pd.to_numeric(x["ChangesRatio"], errors="coerce")
        x = x[x["Date"].notna()].sort_values(["Date", "Code"]).reset_index(drop=True)
        if x.duplicated(["Date", "Code"]).any():
            raise AssertionError(f"{path}: duplicate Date+Code rows")
        self._year_cache[year] = x
        return x.copy()

    def _history(self, signal: pd.Timestamp) -> pd.DataFrame:
        signal = pd.Timestamp(signal).normalize()
        chunks: list[pd.DataFrame] = []
        # Three calendar years safely cover a 252-session lookback even for
        # signals near the start of a calendar year.
        for year in range(signal.year - 2, signal.year + 1):
            x = self._load_year(year)
            if x is not None and not x.empty:
                chunks.append(x)
        if not chunks:
            raise FileNotFoundError(
                f"no KRX yearly parquet files available for technical factors before {signal.date()}"
            )
        h = pd.concat(chunks, ignore_index=True)
        h = h[h["Date"] <= signal].copy()
        if h.empty:
            raise RuntimeError(f"no KRX technical history on/before {signal.date()}")
        return h.sort_values(["Date", "Code"]).reset_index(drop=True)

    @staticmethod
    def _validate_fields(fields: Sequence[str]) -> list[TechnicalFactorSpec]:
        requested = sorted(set(str(x) for x in fields))
        invalid = [x for x in requested if x not in TECHNICAL_FACTOR_SPECS]
        if invalid:
            raise ValueError(f"unsupported KRX technical fields: {invalid}")
        return [TECHNICAL_FACTOR_SPECS[x] for x in requested]

    def coverage_report(self, signal: pd.Timestamp, fields: Sequence[str]) -> list[dict]:
        signal = pd.Timestamp(signal).normalize()
        specs = self._validate_fields(fields)
        history = self._history(signal)
        dates = pd.DatetimeIndex(history["Date"].dropna().unique()).sort_values()
        rows: list[dict] = []
        for spec in specs:
            available = int(min(len(dates), spec.lookback_sessions))
            ratio = min(1.0, available / float(spec.lookback_sessions))
            raw_ok = len(dates) >= spec.lookback_sessions
            rows.append({
                "signal_date": signal,
                "field": spec.field,
                "required_sessions": int(spec.lookback_sessions),
                "available_sessions": available,
                "ratio": float(ratio),
                "raw_ok": bool(raw_ok),
            })
        return rows

    def factor_frame(
        self,
        signal: pd.Timestamp,
        cross_section: pd.DataFrame,
        fields: Sequence[str],
    ) -> pd.DataFrame:
        signal = pd.Timestamp(signal).normalize()
        specs = self._validate_fields(fields)
        codes = cross_section["Code"].astype(str).str.replace(".0", "", regex=False).str.zfill(6)
        code_list = sorted(set(codes))
        out = pd.DataFrame({"Code": code_list})
        if not specs:
            return out

        history = self._history(signal)
        dates = pd.DatetimeIndex(history["Date"].dropna().unique()).sort_values()
        history = history[history["Code"].isin(code_list)].copy()
        wide = history.pivot(index="Date", columns="Code", values="ChangesRatio").reindex(index=dates)

        for spec in specs:
            values = pd.Series(np.nan, index=code_list, dtype=float)
            if len(dates) >= spec.lookback_sessions:
                if spec.skip_sessions:
                    window_dates = dates[-spec.lookback_sessions:-spec.skip_sessions]
                else:
                    window_dates = dates[-spec.lookback_sessions:]
                required_count = spec.lookback_sessions - spec.skip_sessions
                window = wide.reindex(index=window_dates, columns=code_list)
                daily = window / 100.0
                complete = daily.notna().sum(axis=0).eq(required_count)
                if spec.calculation == "compound_return":
                    gross = 1.0 + daily
                    complete &= (gross > 0).all(axis=0)
                    calculated = gross.prod(axis=0, min_count=required_count) - 1.0
                elif spec.calculation == "annualized_volatility":
                    calculated = daily.std(axis=0, ddof=1) * np.sqrt(252.0)
                else:
                    raise AssertionError(spec.calculation)
                values.loc[complete.index[complete]] = calculated.loc[complete]
            out[spec.field] = values.reindex(code_list).to_numpy(float)

        return out


__all__ = [
    "KrxTechnicalFactorAdapter",
    "TECHNICAL_FACTOR_SPECS",
    "TechnicalFactorSpec",
    "technical_factor_catalog",
]
