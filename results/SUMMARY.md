# KRX marcap PIT analysis

- Sample: 1998-10-20 to 2026-08-18
- Rows: 14,308,409
- Unique codes: 4,794
- Trading dates: 6,866

## Holding-period up probability

|   horizon_trading_days | label   |   strict_n |   strict_up_n |   strict_nonup_n |   strict_up_probability |   pit_proxy_n |   pit_proxy_up_n |   pit_proxy_nonup_n |   pit_proxy_up_probability |   proxy_last_exit_n |   missing_even_after_proxy_n |
|-----------------------:|:--------|-----------:|--------------:|-----------------:|------------------------:|--------------:|-----------------:|--------------------:|---------------------------:|--------------------:|-----------------------------:|
|                      1 | 1일      |   14291274 |       6117861 |          8173413 |                0.428084 |      14293169 |          6117861 |             8175308 |                   0.428027 |                1895 |                           16 |
|                      5 | 1주      |   14272163 |       6413461 |          7858702 |                0.449369 |      14281625 |          6414551 |             7867074 |                   0.449147 |                9462 |                           76 |
|                     21 | 1개월     |   14195806 |       6396961 |          7798845 |                0.450623 |      14235430 |          6403524 |             7831906 |                   0.44983  |               39624 |                          316 |
|                     63 | 3개월     |   13996381 |       6273393 |          7722988 |                0.448215 |      14114035 |          6302703 |             7811332 |                   0.446556 |              117654 |                          938 |
|                    126 | 6개월     |   13701454 |       6106433 |          7595021 |                0.445678 |      13931703 |          6169355 |             7762348 |                   0.442828 |              230249 |                         1801 |
|                    252 | 1년      |   13130710 |       5866538 |          7264172 |                0.44678  |      13566777 |          5986528 |             7580249 |                   0.441264 |              436067 |                         3256 |

Definition: return > 0 is up; return == 0 is non-up. Strict requires a close on the exact target market trading date. PIT proxy uses the last observed close when a security disappears before the target date; this avoids dropping delisted/disappeared names but is not an exact delisting-return series.
