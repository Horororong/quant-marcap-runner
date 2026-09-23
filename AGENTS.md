# Repository instructions

For every backtest task, read and follow `BACKTEST_START_HERE.md` first.

Do not implement performance metrics or chat charts inside strategy-specific scripts.
Strategy-specific code should produce daily NAV; canonical metrics and chart payloads come from:
- `scripts/quant_backtest_template_CURRENT.py`
- `scripts/quant_backtest_postprocess.py`
