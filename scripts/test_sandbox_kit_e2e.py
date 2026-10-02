"""Real KRX/DART replay from a clean offline venv, with blocked IP sockets.

Requires build-time wheel cache and a supported Python executable. No synthetic
NAV replaces real source/engine comparison. Linux libc socket guard is inherited
by bootstrap, pip and engine/CURRENT subprocesses, including isolated Python.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from build_sandbox_kit import ROOT, STARTER, build_kit
from sandbox_bootstrap import hash_file

GUARD = r'''
#include <errno.h>
#include <sys/socket.h>
#include <netdb.h>
#include <dlfcn.h>
int connect(int fd, const struct sockaddr *addr, socklen_t len) {
    if (addr && (addr->sa_family == AF_INET || addr->sa_family == AF_INET6)) {
        errno = EPERM; return -1;
    }
    int (*original)(int,const struct sockaddr*,socklen_t) = dlsym(RTLD_NEXT,"connect");
    return original(fd,addr,len);
}
int getaddrinfo(const char *node, const char *service, const struct addrinfo *hints, struct addrinfo **result) {
    return EAI_FAIL;
}
'''


def call(command, env=None, expected=0):
    started = time.monotonic()
    print('Running: ' + ' '.join(str(x) for x in command), flush=True)
    process = subprocess.run([str(x) for x in command], capture_output=True, text=True, env=env, timeout=900)
    assert process.returncode == expected, (command, process.returncode, process.stdout[-5000:], process.stderr[-5000:])
    print(f'Completed in {time.monotonic() - started:.1f}s', flush=True)
    return process


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheels-dir', type=Path, required=True)
    parser.add_argument('--python', type=Path, default=Path(sys.executable))
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--strategy', action='append', help='Repository DSL path; repeat for a custom kit profile')
    parser.add_argument('--runtime-target', action='append', choices=('cp311', 'cp312'))
    parser.add_argument('--part-size-mib', type=int, default=32)
    args = parser.parse_args()
    minor = call([args.python, '-c', 'import sys;print(f"cp{sys.version_info.major}{sys.version_info.minor}")']).stdout.strip()
    if args.work_dir:
        args.work_dir.mkdir(parents=True, exist_ok=False)
        run_test(args.work_dir, args, minor)
    else:
        with tempfile.TemporaryDirectory(prefix='quant-sandbox-e2e-') as temporary:
            run_test(Path(temporary), args, minor)


def run_test(work, args, abi):
    kit = work / 'parts'
    strategies = args.strategy or [f'config/strategies/{name}.json' for name in STARTER]
    built = build_kit(ROOT, kit, args.wheels_dir, targets=args.runtime_target or (abi,),
                      strategies=strategies, part_bytes=args.part_size_mib * 1024**2)
    cfile, guard = work / 'offline.c', work / 'offline.so'
    cfile.write_text(GUARD)
    call(['cc', '-shared', '-fPIC', '-o', guard, cfile, '-ldl'])
    env = os.environ.copy()
    env['LD_PRELOAD'] = str(guard)
    env['PYTHONNOUSERSITE'] = '1'
    # Prove that the isolated Python used by bootstrap cannot open an IP socket.
    probe = 'import socket; s=socket.socket(); s.connect(("1.1.1.1",443))'
    denied = call([args.python, '-I', '-c', probe], env, expected=1)
    assert 'PermissionError' in denied.stderr, denied.stderr
    installed = work / 'installed'
    bootstrap = call([args.python, '-I', kit / 'bootstrap_quant.py', '--parts-dir', kit, '--destination', installed], env)
    ready = json.loads(bootstrap.stdout)
    assert ready['kit_id'] == built['kit_id']
    python, runner = Path(ready['python']), installed / 'scripts/sandbox_runtime.py'
    call([python, '-I', runner, 'verify'], env)
    results = []
    for strategy in strategies:
        name = Path(strategy).stem
        original, replay = ROOT / strategy, installed / strategy
        # Baseline uses the existing checked entry point and the caller's
        # development packages. The isolated replay uses its pinned wheels.
        baseline, output = work / f'{name}-baseline', work / f'{name}-replay'
        call([sys.executable, ROOT / 'scripts/strategy_dsl_runner.py', original,
              '--execution-only', '--output-dir', baseline], env)
        proc = call([python, '-I', runner, 'run', replay, '--execution-only', '--output-dir', output], env)
        result = json.loads(proc.stdout)
        assert result['status'] == 'ok' and result['nav_ready'] and not result['report_ready'], result
        base_status = json.loads((baseline / 'run_status.json').read_text())
        assert result['strategy_fingerprint'] == base_status['strategy_fingerprint']
        artifacts = []
        for path in sorted((baseline / 'artifacts').rglob('*')):
            if path.is_file():
                relative = path.relative_to(baseline / 'artifacts')
                assert path.read_bytes() == (output / 'artifacts' / relative).read_bytes(), (abi, name, relative)
                artifacts.append(str(relative))
        export = json.loads(call([python, '-I', runner, 'export', output, '--output', work / f'{name}.zip'], env).stdout)
        assert export['status'] == 'ok' and export['nav_ready'] and not export['report_ready']
        result_manifest = json.loads((output / 'sandbox_execution_manifest.json').read_text())
        assert result_manifest['data_integrity_verified'] and result_manifest['kit_id'] == built['kit_id']
        results.append({'strategy': name, 'fingerprint': result['strategy_fingerprint'],
                        'daily_nav_sha256': hash_file(output / 'artifacts/daily_nav.csv'), 'identical_artifacts': artifacts})
        print(f'{abi}: {name}: all {len(artifacts)} real artifacts byte-identical', flush=True)
    raw = json.loads((installed / 'config/strategies/kr_equity_split_research.json').read_text())
    request = work / 'request.json'
    # Valid DSL, missing year: data_gap, never truncate the user's dates.
    raw['period'] = {k: ('2019-04-01' if 'start' in k else '2019-04-30') for k in raw['period']}
    raw['rebalance']['months'] = [4]
    request.write_text(json.dumps(raw))
    missing = json.loads(call([python, '-I', runner, 'run', request, '--execution-only', '--output-dir', work / 'missing-year'], env, 3).stdout)
    assert missing['status'] == 'data_gap' and not missing['nav_ready']
    # Known unresolved payment/evidence event remains blocked in both modes.
    raw['period'] = {'start':'2024-09-02','end':'2024-10-24','book_start':'2024-09-02','book_end':'2024-10-24','as_of_date':'2024-10-24'}
    raw['universe']['filters'] = [{'field':'Close','op':'gte','value':12000},{'field':'Close','op':'lte','value':14000}]
    raw['factors'] = [{'name':'size','source':'krx','field':'Marcap','direction':'high'}]
    raw['rebalance']['months'] = [9]
    for mode in ('top_n', 'deciles'):
        raw['portfolio'] = {'selection':mode,'weighting':'equal'}
        if mode == 'top_n': raw['portfolio']['number_of_positions'] = 3
        request.write_text(json.dumps(raw))
        gap = json.loads(call([python, '-I', runner, 'run', request, '--execution-only', '--output-dir', work / f'known-{mode}'], env, 3).stdout)
        assert gap['status'] == 'data_gap' and gap['gap_phase'] == 'corporate_actions' and not gap['nav_ready'],gap
    # Formal report is never falsely claimed for starter research windows.
    formal = json.loads(call([python, '-I', runner, 'run', installed / 'config/strategies/kr_equity_split_research.json',
                              '--output-dir', work / 'formal-short'], env, 3).stdout)
    assert formal['status'] == 'data_gap' and not formal['nav_ready'] and not formal['report_ready']
    # Wrong package or missing source blocks before a result directory exists.
    mismatch = call([python, '-I', '-c', f"import sys;sys.path.insert(0,{str(installed / 'scripts')!r});import sandbox_bootstrap as b;from unittest.mock import patch;\nwith patch.object(b.metadata,'version',return_value='wrong'): b.check_environment({{'packages':{{'pandas':'3.0.6'}}}})"], env, 1)
    assert 'KitEnvironmentError' in mismatch.stderr
    source = installed / 'data/krx_equities/yearly/marcap-2020.parquet'
    renamed = source.with_suffix('.preserved')
    source.rename(renamed)
    try:
        corrupt = json.loads(call([python, '-I', runner, 'run', installed / 'config/strategies/super_value_dart_benchmark_dsl.json',
                                  '--execution-only','--output-dir',work / 'corrupt'], env, 4).stdout)
        assert corrupt['error']['type'] == 'KitIntegrityError' and not (work / 'corrupt').exists()
    finally:
        renamed.rename(source)
    (work / 'verification.json').write_text(json.dumps({'status':'passed','runtime':abi,'network':'IP sockets and DNS blocked in inherited libc guard',
                                                      'kit':built,'replays':results,'gap_checks':['missing_year','known_event_top_n','known_event_deciles','formal_readiness','wrong_package','missing_source']}, indent=2))
    print(f'{abi}: OFFLINE REAL-DATA REPLAY AND FAILURE BOUNDARIES PASS', flush=True)


if __name__ == '__main__':
    main()
