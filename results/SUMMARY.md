# KRX marcap PIT analysis

- Sample: 1998-10-20 to 2025-09-05
- Rows: 13,651,493
- Unique codes: 4,706
- Trading dates: 6,638

## Holding-period up probability

|   horizon_trading_days | label   |   strict_n |   strict_up_n |   strict_nonup_n |   strict_up_probability |   pit_proxy_n |   pit_proxy_up_n |   pit_proxy_nonup_n |   pit_proxy_up_probability |   proxy_last_exit_n |   missing_even_after_proxy_n |
|-----------------------:|:--------|-----------:|--------------:|-----------------:|------------------------:|--------------:|-----------------:|--------------------:|---------------------------:|--------------------:|-----------------------------:|
|                      1 | 1일      |   13634446 |       5839527 |          7794919 |                0.428292 |      13636244 |          5839527 |             7796717 |                   0.428236 |                1798 |                           16 |
|                      5 | 1주      |   13615682 |       6128344 |          7487338 |                0.450095 |      13624660 |          6129344 |             7495316 |                   0.449871 |                8978 |                           76 |
|                     21 | 1개월     |   13540751 |       6126253 |          7414498 |                0.452431 |      13578346 |          6132354 |             7445992 |                   0.451627 |               37595 |                          316 |
|                     63 | 3개월     |   13345327 |       6013307 |          7332020 |                0.450593 |      13456928 |          6040569 |             7416359 |                   0.448882 |              111601 |                          938 |
|                    126 | 6개월     |   13056603 |       5802896 |          7253707 |                0.444441 |      13274752 |          5860741 |             7414011 |                   0.441495 |              218149 |                         1801 |
|                    252 | 1년      |   12499982 |       5540778 |          6959204 |                0.443263 |      12913936 |          5650775 |             7263161 |                   0.437572 |              413954 |                         3256 |

Definition: return > 0 is up; return == 0 is non-up. Strict requires a close on the exact target market trading date. PIT proxy uses the last observed close when a security disappears before the target date; this avoids dropping delisted/disappeared names but is not an exact delisting-return series.
