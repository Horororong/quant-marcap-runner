from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import extend_k_allweather_1990 as m

_original_fred = m.fred


def fred_patched(series_id: str) -> pd.Series:
    if series_id != "GOLDPMGBD228NLBM":
        return _original_fred(series_id)
    # The old LBMA FRED series was removed. Use the BLS nonmonetary-gold export
    # price index (IQ12260), available from 1984. Before 1994 observations are
    # sparse/quarterly, so interpolate the index level monthly in time.
    s = _original_fred("IQ12260")
    s = s.resample("ME").last().interpolate(method="time").ffill().bfill()
    s.name = "IQ12260_GOLD_PROXY"
    return s


m.fred = fred_patched
m.main()

readme = m.OUT / "README.txt"
if readme.exists():
    txt = readme.read_text(encoding="utf-8")
    txt = txt.replace(
        "- Gold: LBMA PM USD spot + USD/KRW.",
        "- Gold 1990-1999: BLS Export Price Index (End Use): Nonmonetary Gold [IQ12260] + USD/KRW. Sparse pre-1994 index levels are time-interpolated monthly. 2000 onward reuses the prior validated gold return panel unchanged."
    )
    readme.write_text(txt, encoding="utf-8")
