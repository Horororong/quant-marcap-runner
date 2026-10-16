"""Independent read-only checks of Stage10 census; never execute NAV."""
from pathlib import Path
from decimal import Decimal, getcontext
import json
import sys
import hashlib
import subprocess
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from corporate_action_preflight import trace_planned_exposures
from strategy_dsl import load_strategy_spec
from strategy_dsl_runner import load_project_engine, engine_inputs
from krx_history_audit import expected_krx_sessions

getcontext().prec = 40
r = HERE / 'results'
raw = pd.concat([pd.read_parquet(ROOT / f'data/krx_equities/yearly/marcap-{y}.parquet') for y in (2019, 2020)])
raw['Date'] = pd.to_datetime(raw.Date)
raw['Code'] = raw.Code.astype(str).str.zfill(6)
raw = raw[raw.Market.isin(['KOSPI','KOSDAQ'])]
sessions = expected_krx_sessions('2019-01-01', '2020-12-31')
members = pd.read_csv(r / 'membership.csv', dtype={'Code':str}, parse_dates=['signal_date'])
held = pd.read_csv(r / 'planned_holding_observations.csv.gz', dtype={'Code':str}, parse_dates=['Date','previous_date'])
bad = pd.read_csv(r / 'planned_holding_mismatches.csv', dtype={'Code':str}, parse_dates=['Date'])
schedule = pd.read_csv(r / 'schedule.csv', parse_dates=['signal_date','execution_date'])
expected_keys = set()
cohorts = []
for signal, start, end, size in [
    ('2019-04-30','2019-05-02','2020-05-04',33),
    ('2020-04-29','2020-05-04','2020-12-30',26),
]:
    signal, start, end = map(pd.Timestamp, (signal,start,end))
    cs = raw[raw.Date.eq(signal) & raw.Marcap.ge(10**13) & raw.Close.gt(0) & raw.Volume.gt(0)]
    cs = cs.sort_values(['Marcap','Code'])
    m = members[members.signal_date.eq(signal)]
    assert len(cs) == size and cs.Code.tolist() == m.Code.tolist()
    # Independent balanced-bucket check against raw market-cap order.
    groups = [list(x) for x in __import__('numpy').array_split(cs.Code.to_numpy(), 10)]
    for i, codes in enumerate(groups, 1):
        assert codes == m[m.decile.eq(f'D{i:02d}')].Code.tolist()
    assert sessions[sessions > signal][0] == start
    ds = sessions[(sessions > start) & (sessions <= end)]
    for day in ds:
        expected_keys.update((day, code) for code in cs.Code)
    cohorts.append({'signal':str(signal.date()),'codes':size,'return_exposure_sessions':len(ds),
                    'expected_code_days':size*len(ds)})
assert expected_keys == set(zip(held.Date, held.Code))
lookup = raw.set_index(['Date','Code'])
decimal_bad = set()
maximum_float_error = 0.0
for row in held.itertuples():
    current = lookup.loc[(row.Date, row.Code)]
    previous_day = sessions[sessions < row.Date][-1]
    previous = lookup.loc[(previous_day, row.Code)]
    assert previous_day == row.previous_date
    assert current.Close == row.Close and previous.Close == row.previous_close
    assert current.ChangesRatio == row.ChangesRatio
    delta = ((Decimal(str(current.Close))/Decimal(str(previous.Close))-1)
             -Decimal(str(current.ChangesRatio))/100)*10000
    maximum_float_error = max(maximum_float_error, abs(float(delta)-row.difference_bps))
    if abs(delta) > 1:
        decimal_bad.add((row.Date, row.Code))
assert maximum_float_error < 1e-9
assert decimal_bad == set(zip(bad.Date, bad.Code))
spec = load_strategy_spec(ROOT / 'docs/research/stage8-2019-2020-20261015/deciles_research_only.json')
engine = load_project_engine(ROOT)
_, _, execution = engine_inputs(spec, engine)
targets = {}
for bucket, b in members.groupby('decile'):
    targets[bucket] = b.pivot(index='signal_date', columns='Code', values='target_weight').fillna(0)
traced = []
for event_date, cases in bad.groupby('Date'):
    gaps = pd.DataFrame([dict(predecessor_code=x.Code,event_date=x.Date,reason='DIAGNOSTIC probe only; not production gap') for x in cases.itertuples()])
    # Production gaps persist after event date. Cap each probe at its own day
    # so a subsequent first buy in another bucket is not mistaken for that day's holding.
    bounded_targets = {label:w[w.index < event_date] for label,w in targets.items()}
    found, _ = trace_planned_exposures(bounded_targets, sessions[sessions <= event_date], gaps, pd.DataFrame(), engine, execution)
    traced.extend(found)
assert {(pd.Timestamp(x['check_date']), x['Code'], x['portfolio']) for x in traced} == set(zip(bad.Date,bad.Code,bad.decile))
assert all(x['phase'] == 'prior_holding_before_close' for x in traced)
assert len(schedule) == 20
for f in [r / 'panel_mismatches.csv', r / 'panel_numeric_mismatches.csv']:
    table = pd.read_csv(f)
    assert not table.duplicated(['Date','Code']).any()
changes = subprocess.check_output(['git','diff','--name-only','6dfa430128b37cd49990232acf43f2882fcf20dc','--','.'],cwd=ROOT,text=True).splitlines()
old_changes = [path for path in changes if not path.startswith('docs/research/stage10-return-diagnostic-20261016/')]
assert not old_changes, old_changes
paths = json.loads((ROOT / 'docs/research/stage9-followup-20261015/preservation.json').read_text())['baseline_identical_files']
preservation = {}
for path, entry in paths.items():
    value = hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    assert value == entry['sha256'], path
    preservation[path] = value
summary = {'status':'PASS','scope':'Diagnostic arithmetic/selection/timing/byte preservation; not new financial or investment certification',
    'independent_raw_selection_rows':len(members), 'cohorts':cohorts, 'expected_held_keys':len(expected_keys),
    'decimal_recomputed_observations':len(held),'decimal_mismatches':len(decimal_bad),
    'maximum_float_decimal_difference_bps':maximum_float_error,
    'shared_preflight_trace_case_matches':len(traced),'completed_nav_runs':0,
    'existing_tracked_changes':old_changes,'prior_preservation_sha256':preservation,
    'original60_scope':'Existing source/ZIP/member SHA controls retained; original60 archive bytes not re-downloaded or re-audited in Stage10',
    'investment_PIT_approved':0,'stage6_samples':6}
(HERE/'verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
