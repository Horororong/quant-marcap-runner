"""Replay recorded readiness diagnostics, without NAV or strategy optimisation."""
import argparse
import json
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--python', required=True)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    cases = json.loads(Path(__file__).with_name('preflight_cases.json').read_text())
    expected = {x['id']: x for x in json.loads(Path(__file__).with_name('preflight_matrix.json').read_text())}
    results = []
    failed = False
    for case in cases:
        command = [args.python, 'scripts/strategy_dsl_preflight.py', case['path'], '--repo-root', str(args.repo)]
        start = time.monotonic()
        try:
            result = subprocess.run(command, cwd=args.repo, timeout=60, capture_output=True, text=True)
            evidence = json.loads(result.stdout)
            status = evidence.get('status')
            actual = {'id': case['id'], 'command': command, 'seconds': round(time.monotonic()-start, 2),
                      'returncode': result.returncode, 'status': status, 'evidence': evidence, 'stderr': result.stderr}
            actual['matches_recorded'] = result.returncode == expected[case['id']]['returncode'] and status == expected[case['id']]['status']
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            actual = {'id': case['id'], 'command': command, 'matches_recorded': False, 'error': str(exc)}
        failed |= not actual['matches_recorded']
        results.append(actual)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n')
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
