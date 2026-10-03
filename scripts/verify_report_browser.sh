#!/usr/bin/env bash
set -euo pipefail
report_html=${1:?report HTML required}
evidence_dir=${2:?evidence directory required}
mkdir -p "$evidence_dir"
timeout -k 5s 150s node scripts/test_report_dashboard.cjs "$report_html" "$evidence_dir/report-preview.png" > "$evidence_dir/browser-verification.json" 2> "$evidence_dir/browser-verification.log"
timeout 15s python - "$evidence_dir" <<'CHECK'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
r = json.loads((p / 'browser-verification.json').read_text())
assert r['status'] == 'passed', r
assert r['ready_periods_checked'] >= 2, r
assert (p / 'report-preview.png').read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'
print('Browser evidence: passed JSON and actual PNG verified')
CHECK
