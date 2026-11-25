# 8-K drift pilot: results (2026-11-24)

Rules: `protocol.md`, which was locked before the first run. Raw rows: `results_20261124_40.json` (40 large caps, 9,630 rows) and `results_20261124_0348.json` (first 20 of them). Full reports: `report_40.json` and `report_0348.json`, produced with `python research/news_backtest/run.py --from-file <results.json>`, offline and without re-fetching data.

**Verdict: no edge shown for "buy any 8-K at the next open".** This is a pilot and descriptive. It rejects this rule only, not item-filtered 8-Ks or Form 4 (see `protocol_next.md`).

40 symbols, 8-K since 2018, long-only, net after a 0.18% round trip. diff = event minus a random same-class stock bought at the same open. p values are one-sided; "block" resamples symbol-month clusters (about 2,095 clusters for 3,200 events).

| Horizon | n | gross | net | net 2× | diff | p_diff iid | p_diff block |
|---|---|---|---|---|---|---|---|
| 1 | 3216 | −0.052% | −0.232% | −0.412% | −0.037% | 0.80 | 0.78 |
| 3 | 3209 | +0.173% | −0.007% | −0.187% | +0.061% | 0.24 | 0.22 |
| 5 | 3205 | +0.336% | +0.156% | −0.025% | +0.014% | 0.46 | 0.44 |
| 5, test 2025+ | 879 | +0.342% | +0.161% | −0.019% | −0.276% | 0.90 | 0.86 |

- The positive net at H5 comes from the market drift that the control also earns: the paired diff is about 0 and it turns negative in test. The net is also negative at 2× cost.
- The 20-symbol subset looked better pooled (H5 diff +0.19%, p 0.09). Its test slice was negative (−0.04%), and adding 20 more symbols removed the effect, which is consistent with noise.
- Contributors change from one horizon to the next (H5 best: AVGO, TXN, AMD; H3 best: AVGO, IBM, TXN; INTC is worst at H1 and H3), so no single firm or sector carries a stable effect.
- The block bootstrap was added after the pilot as a stricter statistic. It does not change any rule, and it does not change the verdict: the p values move by 0.02 or less, because most clusters contain one 8-K.
- Limits: as listed in `protocol.md` (routine 8-Ks dilute the signal, survivorship bias, the control is not matched on sector or volatility).

## N1 news_v3 on Claude Haiku 5.5 (2026-11-25, run 45556256839)

Held-out 2.02 filings 2026-10-20..11-05: 2390 found, 1746 tradeable. Verdict **v3 no edge shown**: H5 n = 84, hit 39%, net -1.39% (p 0.88); v3 minus v1 paired H5 -0.99% (p 1.00). Details in `research/studies/protocol_news_v3.md`.
