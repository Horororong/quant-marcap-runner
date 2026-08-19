# KRX marcap PIT analysis

- Sample: 1998-10-20 to 2026-08-18
- Rows: 14,311,281
- Unique codes: 4,795
- Trading dates: 6,867

## Holding-period up probability

|   horizon_trading_days | label   |   strict_n |   strict_up_n |   strict_nonup_n |   strict_up_probability |   pit_proxy_n |   pit_proxy_up_n |   pit_proxy_nonup_n |   pit_proxy_up_probability |   proxy_last_exit_n |   missing_even_after_proxy_n |
|-----------------------:|:--------|-----------:|--------------:|-----------------:|------------------------:|--------------:|-----------------:|--------------------:|---------------------------:|--------------------:|-----------------------------:|
|                      1 | 1일      |   14294145 |       6118462 |          8175683 |                0.42804  |      14296041 |          6118462 |             8177579 |                   0.427983 |                1896 |                           16 |
|                      5 | 1주      |   14275032 |       6414625 |          7860407 |                0.44936  |      14284496 |          6415715 |             7868781 |                   0.449138 |                9464 |                           76 |
|                     21 | 1개월     |   14198671 |       6398832 |          7799839 |                0.450664 |      14238302 |          6405395 |             7832907 |                   0.449871 |               39631 |                          316 |
|                     63 | 3개월     |   13999234 |       6273912 |          7725322 |                0.448161 |      14116914 |          6303228 |             7813686 |                   0.446502 |              117680 |                          938 |
|                    126 | 6개월     |   13704288 |       6107174 |          7597114 |                0.44564  |      13934587 |          6170109 |             7764478 |                   0.442791 |              230299 |                         1801 |
|                    252 | 1년      |   13133482 |       5867628 |          7265854 |                0.446769 |      13569653 |          5987658 |             7581995 |                   0.441254 |              436171 |                         3256 |

Definition: return > 0 is up; return == 0 is non-up. Strict requires a close on the exact target market trading date. PIT proxy uses the last observed close when a security disappears before the target date; this avoids dropping delisted/disappeared names but is not an exact delisting-return series.
