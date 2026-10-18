"""Fresh real-data E2E of opt-in shared contracts, never source collection."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import pandas as pd

HOME = Path(__file__).resolve().parent
ROOT = HOME.parents[2]
sys.path[:0] = [str(ROOT / 'scripts'), str(HOME), str(HOME.parent / 'stage15-research-environment-20261017')]
from verify_long_ledger import verify as long_ledger
from verify_research_nav import verify as original_ledger
from test_research_workbench import REQUEST


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(out, check):
    out.mkdir(parents=True, exist_ok=False)
    commands = []

    def command(name, args):
        started = time.monotonic()
        with (out / (name + '.log')).open('xb') as f:
            r = subprocess.run([sys.executable, '-I', *args], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        commands.append(dict(name=name, args=args, exit_code=r.returncode, elapsed_seconds=round(time.monotonic() - started, 3),
                             log_sha256=sha(out / (name + '.log'))))
        (out / 'commands.json').write_text(json.dumps(commands, ensure_ascii=False, indent=2) + '\n')
        print(name, r.returncode, flush=True)
        assert r.returncode == 0, (name, r.returncode, 'See preserved exact command log; no retry/skip')

    for name in ['test_execution_scheduling.py', 'test_annual_selected_preparation.py', 'test_calendar_cache.py']:
        command(name, ['-c', "import sys,runpy;sys.path.insert(0,'scripts');runpy.run_path('scripts/" + name + "',run_name='__main__')"])
    command('contracts', ['-c', "import sys,runpy;sys.path.insert(0,'scripts');sys.argv=['scripts/export_strategy_dsl_contract.py','--check'];runpy.run_path(sys.argv[0],run_name='__main__')"])
    manifest = json.loads((HOME / 'source_manifest.json').read_bytes())
    assert manifest['requests'] == 4 and manifest['retries'] == 0 and not manifest['errors']
    for pin in manifest['responses']:
        path = HOME / 'evidence' / pin['file']
        assert path.stat().st_size == pin['bytes'] and sha(path) == pin['sha256']
    preserved = json.loads((HOME / 'stage16_frozen_manifest.json').read_bytes())
    for path, pin in preserved['files'].items():
        actual=dict(bytes=(ROOT/path).stat().st_size,sha256=sha(ROOT/path))
        if actual!=pin:
            revision=json.loads((ROOT/'docs/research/long-multi-backfill-20261018/executable_revision.json').read_bytes())
            migration=revision['authorized'].get(path)
            assert migration and migration['before']==pin and migration['after']==actual, path
            assert path=='docs/research/stage16-continuous-research-20261018/validate_continuous.py', 'No numeric/source migration allowed'
    prefix = preserved['prior_registry_prefix']
    assert hashlib.sha256((ROOT / prefix['path']).read_bytes()[:prefix['bytes']]).hexdigest() == prefix['sha256'], 'Stage16 action rows must remain byte-identical prefix'
    command('financial_original_preservation', ['docs/research/stage16-continuous-research-20261018/preserve.py', '--output', str(out / 'financial-preservation')])

    source = ROOT / 'config/strategies/research_size_top1_2001_2025_deferred_v1.json'
    report = 'config/reports/research_continuous_2025.json'
    for label in ['long2001_2025', 'korean2001_2025']:
        run = out / label
        args = ['scripts/research_workbench.py', 'run', '--report-periods', report, '--output-dir', str(run)]
        if label.startswith('long'):
            args += ['--strategy', str(source)]
        else:
            request = REQUEST.replace('2019-01-01', '2001-01-01').replace('2020-12-31', '2025-12-31').replace('시가총액 낮은', '시가총액 높은').replace('10분위', '상위1개')
            args += ['--request', request, '--research-model-from', str(source), '--execution-contract-from', str(source)]
        command(label, args)
        status = json.loads((run / 'run_status.json').read_bytes())
        assert status['status'] == 'ok' and status['nav_ready'] and status['report_ready']
        preparation = json.loads((run / 'artifacts/data_preparation.json').read_bytes())
        assert preparation['sessions'] == 6168 and preparation['selected_codes'] == ['000660', '005930']
        assert len(preparation['annual']) == 25
    independent = long_ledger(out / 'long2001_2025', out / 'long_independent')
    left_spec = json.loads((out / 'long2001_2025/strategy_normalized.json').read_bytes())
    right_spec = json.loads((out / 'korean2001_2025/strategy_normalized.json').read_bytes())
    for field in ['universe', 'portfolio', 'rebalance', 'execution', 'cost_scenarios', 'period', 'benchmark', 'initial_capital', 'research']:
        assert left_spec[field] == right_spec[field], ('Korean contract differs', field)
    assert [{k: v for k, v in f.items() if k != 'name'} for f in left_spec['factors']] == [{k: v for k, v in f.items() if k != 'name'} for f in right_spec['factors']]
    pins = {}
    for name in ['artifacts/daily_nav.csv', 'artifacts/target_weights.csv', 'artifacts/selections.csv',
                 'report/metrics_CURRENT.csv', 'report/daily_nav_canonical.csv']:
        left = out / 'long2001_2025' / name
        if name != 'artifacts/selections.csv':
            assert left.read_bytes() == (out / 'korean2001_2025' / name).read_bytes(), ('Korean differs', name)
        pins[name] = dict(bytes=left.stat().st_size, sha256=sha(left))
    a = pd.read_csv(out / 'long2001_2025/artifacts/selections.csv', dtype={'Code': str})
    b = pd.read_csv(out / 'korean2001_2025/artifacts/selections.csv', dtype={'Code': str})
    pd.testing.assert_frame_equal(a, b.rename(columns={'factor_rank__Marcap': 'factor_rank__size'}), check_exact=True)
    (out / 'numeric_manifest.json').write_text(json.dumps(pins, indent=2) + '\n')
    if check:
        assert pins == json.loads((HOME / 'numeric_manifest.json').read_bytes()), 'Pinned long experiment changed; never regenerate expected to pass'

    # Actual original ten portfolios through the same opt-in projection, with
    # untouched legacy execution and research assumptions. All old numeric pins
    # come from the PRE-CHANGE original experiment, not this implementation.
    projected = json.loads((ROOT / 'config/strategies/research_size_deciles_2019_2020_v1.json').read_bytes())
    projected['execution']['data_loading'] = 'annual_selected_projection'
    projected_path = out / 'projection_original_input.json'
    projected_path.write_text(json.dumps(projected, ensure_ascii=False, indent=2) + '\n')
    run = out / 'projected_original'
    command('projected_original', ['scripts/research_workbench.py', 'run', '--strategy', str(projected_path),
                                  '--report-periods', 'config/reports/research_2019_2020.json', '--output-dir', str(run)])
    original_pins = json.loads((HOME.parent / 'stage15-research-environment-20261017/numeric_manifest.json').read_bytes())
    for path in ['artifacts/daily_nav.csv', 'report/metrics_CURRENT.csv', 'report/daily_nav_canonical.csv']:
        pin = original_pins['original/' + path]
        assert (run / path).stat().st_size == pin['bytes'] and sha(run / path) == pin['sha256'], ('Original decile numerical regression', path)
    frozen = json.loads((HOME.parent / 'stage16-continuous-research-20261018/regression_baseline.json').read_bytes())['files']
    for path in ['artifacts/target_weights.csv', 'artifacts/decile_membership.csv', 'artifacts/execution_schedule.csv', 'artifacts/execution_trades.csv']:
        pin = frozen['original/' + path]
        assert (run / path).stat().st_size == pin['bytes'] and sha(run / path) == pin['sha256'], ('Projection changed original selection/order bytes', path)
    projected_accounting = original_ledger(run, out / 'projected_original_independent')
    summary = dict(status='PASS_EXPLICIT_LONG_RESEARCH_CONTRACT', github_sha=os.getenv('GITHUB_SHA'), ci_run_id=os.getenv('GITHUB_RUN_ID'),
                   python=sys.executable, investment_approved=False, long_accounting=independent, original_deciles_projection=projected_accounting,
                   frozen_stage16_files=len(preserved['files']), new_primary_responses=4, source_requests_this_validation=0,
                   language_nav_targets_metrics_bytes_identical=True, selection_values_exact_after_factor_label_mapping=True,
                   original_fixed_lag_blockers_unchanged=True, numeric_identity_checked=check, commands=commands,
                   scope='Separate predeclared deferred-close largest-cap experiment, not original fixed-lag long strategy, total cash distribution return or investment PIT certification')
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'commands'}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--check', action='store_true')
    a = p.parse_args()
    main(a.output, a.check)
