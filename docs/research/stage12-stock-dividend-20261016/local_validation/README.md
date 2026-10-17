# Validation phases are separate

`results.json` and `test_*.py.log` are the INITIAL local run of15 test files plus
the generated-contract check, all exit0. They precede the later CI/native incident
and are not the final full-suite verdict.

The later focused software evidence is:
- `test_stock_dividend.precision-final.log`:23 tests PASS.
- `test_stock_dividend_collection.ci-gate-final.log`:10 tests PASS.
- `test_stock_dividend_krx.log`:4 tests PASS.

`ci39003674278-engine-exits.log` preserves a later CI DART E2E timeout/exit124.
`dart-e2e-diagnostic.log` is a partial asynchronous stack diagnostic that exited139,
not a successful replay. See ../native_runtime_incident.json. Final CI must keep
that requirement UNVERIFIED/exit2 while independently running remaining tests,
price comparisons and preservation. A successful initial run is not final CI.

Preservation JSONs certify byte/control preservation at their recorded phase,
not new financial extraction accuracy. The final live CI/artifacts are associated
with the actual published HEAD and must be inspected through GitHub Actions.
