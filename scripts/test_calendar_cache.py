"""Long-window calendar reuse; unchanged exact sessions, no metric proxy."""
import unittest
from unittest.mock import patch
import pandas as pd
import quant_backtest_template_CURRENT as current


class Cache(unittest.TestCase):
    def test_25_year_multi_series_does_not_thrash_calendar_construction(self):
        current._market_calendar.cache_clear()
        keys = [('XKRX', year, year) for year in range(2001, 2026)]
        keys += [('XKRX', year - 1, year) for year in range(2001, 2026)]
        with patch('exchange_calendars.get_calendar', side_effect=lambda *a, **kw: object()) as factory:
            first = [current._market_calendar(*key) for key in keys]
            for _ in range(4):
                self.assertEqual([current._market_calendar(*key) for key in keys], first)
            self.assertEqual(factory.call_count, 50)
            self.assertEqual(current._market_calendar.cache_info().hits, 200)
        current._market_calendar.cache_clear()

    def test_cached_exact_sessions_equal_original_factory(self):
        first, last = pd.Timestamp('2018-04-26'), pd.Timestamp('2018-05-09')
        original = current._market_calendar.__wrapped__('XKRX', first.year, last.year)
        raw = pd.DatetimeIndex(original.sessions_in_range(first, last))
        if raw.tz is not None:
            raw = raw.tz_localize(None)
        pd.testing.assert_index_equal(current.expected_market_sessions(first, last, 'XKRX'), raw)


if __name__ == '__main__':
    unittest.main(verbosity=2)
