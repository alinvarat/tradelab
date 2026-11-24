# Cross-Asset, Carry, Pairs and Statistical Arbitrage for a ~USD 147 Retail Account (research as of Nov 2026)

Scope note for the report writer: all findings below are about *documented* evidence with numbers. Where a source is a blog / practitioner post rather than peer-reviewed, it is labelled. The account constraint (USD 147, cash account in practice) is treated as binding throughout: no margin, no shorting, no futures. That single fact disqualifies most of the literature's Sharpe ratios, and the notes say so explicitly.

---

## Cross-asset momentum (time-series momentum, TSMOM) and carry: evidence, returns, drawdowns, costs, 2020-2026 behaviour

### Takeaway
Time-series momentum is the best-documented cross-asset edge (Sharpe ~1.0 gross on futures, ~0.76 net of costs and 2/20 fees over 1880-2016), but almost all of that evidence is *long/short futures with leverage*. The retail ETF replication over 2004-2026 nets a Sharpe of 0.53 versus 0.65 for simply buying the same ETFs, i.e. no edge after costs on five ETFs. Carry is stronger in the literature (global Sharpe 1.2) and equally dependent on shorting the low-carry leg.

### Cited Findings

**Foundational momentum**
- Moskowitz, Ooi & Pedersen, "Time Series Momentum", *Journal of Financial Economics* 104(2), 2012, pp. 228-250: 58 liquid futures (24 commodities, 12 currency pairs, 9 equity indices, 13 bond futures), Jan 1965-Dec 2009; signal = sign of past 12-month excess return, 1-month hold, each position scaled to 40% ex-ante vol; diversified portfolio Sharpe "greater than one", ~2.5x the equity market's Sharpe; monthly alpha 1.58% vs MSCI World + SMB/HML/UMD; positive in **all 58** contracts, 52 of 58 significant at 5% — [JFE paper PDF](https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf).
- Same paper: TSMOM returns are largest in the biggest up *and* down market months (positive coefficient on squared market return, "option straddle" payoff); the strategy lost money in Q3 2008 and again in Mar-May 2009 when the crisis trend reversed — [JFE paper PDF](https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf).
- Independent replication (R, 1986-2009): annualized 11.93% total / 8.93% excess, vol 19.5%, Sharpe 0.46, max drawdown -53.8%, beta to S&P -0.10 — materially worse than the paper's headline and closer to what a levered retail version would see — [replication PDF](https://unknownamit.com/docs/TimeSeries_Momentum_Replication.pdf).

**Long-horizon out-of-sample**
- Hurst, Ooi & Pedersen, "A Century of Evidence on Trend-Following Investing", *Journal of Portfolio Management* 44(1), Fall 2017: 67 markets (29 commodities, 11 equity indices, 15 bond, 12 FX), 1880-2016, equal-weight 1/3/12-month signals, 10% vol target: **18.0%/yr gross, 11.0% after costs, 7.3% after costs and 2/20 fees, Sharpe 0.76 net**, correlation -0.01 to US stocks, positive in 8 of the 10 worst 60/40 drawdowns — [AQR PDF](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/AQR-JPM-Fall-2017.pdf); decade-by-decade table and cost assumptions (one-way: stocks 6bp, bonds 1bp, commodities 10bp, FX 3bp for 2003-2016) reproduced at [Finetiq summary](https://ideas.finetiqsystems.com/en/papers/century-of-trend-following/).
- Note the decay inside that same table: 1970s after-fee 15.1%/yr, 1990s 8.3%, 2000-2009 6.3%, 2010-2016 3.3% — [Finetiq summary](https://ideas.finetiqsystems.com/en/papers/century-of-trend-following/).

**2020-2026 realised performance (industry indices, net of manager fees)**
- SG Trend Index: 2022 **+27.35%**, 2023 **-4.17%**, 2024 **+2.66%**, 2025 **+2.39%**; SG CTA Index 2022 +20.13%, 2023 -3.49%, 2024 +2.36%, 2025 -0.11%; DBMF (ETF wrapper) 2022 +23.07%, 2023 -8.72%, 2024 +7.18%, 2025 +13.85% — [MoneyScience, Sep 2026](https://moneyscience.org/articles/managed-futures.php).
- Jan 2023-Sep 2025 the SG Trend Index declined **-3.8%** cumulative, "one of the most challenging periods for the industry as an aggregate in the past 25 years" — [Quantica Quarterly, 2025Q4](https://quantica-capital.com/publications/pdf/2025Q4_QuanticaQuarterlyInsights.pdf).
- Crisis behaviour by quarter (SG Trend): Q1 2020 S&P 500 futures -22.5% vs TF CTA **+2.3%**; Q2 2022 S&P -18.0% vs **+9.2%**; Q4 2018 S&P -15.4% vs **-5.2%** (trend's worst crisis quarter); positive in 12 of the 16 worst equity quarters since 2000, average +6.1% vs -14.4% — [Quantica Quarterly 2024Q2, Table 2](https://quantica-capital.com/publications/pdf/2024Q2_QuanticaQuarterlyInsights.pdf).

**Retail ETF implementation, the closest thing to our constraint**
- Audit of MOP's rule on 5 ETFs only (SPY, EFA, EEM, IEF, TLT), 12-month lookback, 40% vol target, monthly, **5bp one-way cost**, 2004-05-03 to 2026-09-24: net CAGR **11.0%** vs buy-and-hold **7.5%**; Sharpe **0.53 vs 0.65**; max drawdown **-47.6% vs -33.6%**; excess Sharpe over benchmark 0.218 with standard error 0.212 (95% CI includes 0); holdout split at 2018-01-02 shows deflated excess Sharpe 0.31 in-sample → **0.06 out-of-sample**; fragility grade F — [Holdout Labs audit, Sep 2026](https://holdoutlabs.io/audits/batch-3/reports/tsmom-5) (practitioner, not peer-reviewed, but the method disclosure is unusually complete).

**Carry**
- Koijen, Moskowitz, Pedersen & Vrugt, "Carry", *Journal of Financial Economics* 127(2), 2018 (online Nov 2017): carry defined as the futures return if price does not change; nine asset classes (global equities, global bonds, currencies, commodities, US Treasuries, credit, equity index options). Long-short carry Sharpe **0.78 average** across asset classes (range 0.37 calls to 1.80 puts); diversified global carry factor Sharpe **1.20**; passive equal-weight benchmark only 0.40; carry1-12 (12-month averaged signal) Sharpe **1.12** with ~**50% lower turnover**; net returns still positive and significant after Bollerslev-et-al transaction-cost estimates for equities, fixed income, Treasuries, commodities, currencies — [JFE version](https://doi.org/10.1016/j.jfineco.2017.11.002); [NBER WP 19325 PDF](https://www.nber.org/system/files/working_papers/w19325/w19325.pdf).
- Conflict to flag: the July-2012 working-paper draft of the same paper reports a global carry Sharpe of **1.49** and a carry1-12 Sharpe of 0.95, with per-class Sharpes 0.62-0.93 — [2012 draft](https://w4.stern.nyu.edu/facdir/lpederse/papers/Carry.pdf). Use the published 1.20/1.12 numbers; the dispersion across vintages is itself evidence of specification sensitivity.

### Inferences
- The published Sharpe ~1.0 for TSMOM is not attainable with long-only ETFs. The gap is structural: (a) no short leg in falling markets (2022's +27% for CTAs came from short bonds/equities), (b) no leverage to hit the 10-40% vol targets, (c) ETF expense ratios and spreads replace 1-10bp futures costs.
- Crypto carry has now decayed to the point of being dominated by T-bills (see the carry-decay findings in the pairs/seasonality-adjacent section below): BTC perp funding annualized 30.61% in 2021 → **2.92% in 2026**, with 26.2% of 2026 settlements negative — [Delta Tech Systems, Oct 2026](https://www.delta-tech-systems.com/research/funding-carry-compressed). A funding-only "Sharpe 8.5" is a volatility artefact; honest net return is +5.6%/yr full sample and negative by 2026 — [Alpha Research, Jun 2026](https://bryanvine.github.io/alpha-research/paper2.html).
- Therefore the realistic retail question is not "does TSMOM work" but "does long-flat ETF TSMOM beat 60/40 net of spread with ≤12 trades a year".

### Gaps
- No source found that reports a *long-only, unlevered, ETF-based* cross-asset momentum Sharpe out-of-sample for 2020-2026 with explicit costs, other than the 5-ETF audit above. A 8-12 asset version with commodities (GLD, DBC) and FX (UUP) is untested in the literature I found.
- No public source quantifies the borrow/locate cost impact on the *short* leg of a retail multi-asset momentum account, because retail cannot short most of these instruments at all.
- Capacity: no paper estimates capacity for a USD 147 account. My own arithmetic (below) suggests commissions, not market impact, are the binding constraint.

---

## Pairs trading / statistical arbitrage: cointegration, ETF pairs, share-class pairs, index arbitrage, lead-lag — what survives costs and borrow

### Takeaway
Classic distance/cointegration pairs trading on US equities is real gross (85-91bp/month), thin net (~30-38bp/month, Sharpe ~0.35), and has been **largely unprofitable since 2002** once commissions, impact and short fees are charged. The only pair class where the economics are clean enough to measure is same-claim dual-class shares, and there a 2026 study finds the gross edge is almost exactly equal to the round-trip spread (correlation +0.95): you supply liquidity or you lose. Index arbitrage and lead-lag are latency businesses with negative net P&L for anyone crossing the spread.

### Cited Findings
- Gatev, Goetzmann & Rouwenhorst, *Review of Financial Studies* 19(3), 2006: daily data 1962-2002, minimum-distance matching on normalized prices, top-20 pairs ~**11%/yr excess** (12% in the NBER WP version); estimate 83bp round-trip cost per pair, 2.4 round trips per 6-month interval = 200bp, leaving **88-168bp net per 6 months** — [NBER WP 7032 PDF](https://www.nber.org/system/files/working_papers/w7032/w7032.pdf); [RFS abstract](https://academic.oup.com/rfs/article-abstract/19/3/797/1646694).
- Do & Faff, *Journal of Financial Research*, 2012 (1963-2009, commissions + impact + short fees): risk-adjusted **~30bp/month** for well-matched industry pairs; "both these types of contrarian investing are **largely unprofitable after 2002**" — [Wiley abstract](https://onlinelibrary.wiley.com/doi/10.1111/j.1475-6803.2012.01317.x).
- Rad, Low & Faff, *Quantitative Finance*, 2016 (1962-2014, time-varying costs): monthly excess return before/after costs — distance **91bp / 38bp**, cointegration **85bp / 33bp**, copula **43bp / 5bp**; after-cost Sharpe ~0.35; "from 2009, the frequency of trading opportunities via the distance and cointegration methods is reduced considerably" — [PDF](https://randlow.github.io/2016_QF_PairsTrading.pdf).
- Replication over the last 20 years (Yale, 2024): distance method still yields **6.2%/yr excess and Sharpe 1.35** — [Zhu, Yale](https://economics.yale.edu/sites/default/files/2024-05/Zhu_Pairs_Trading.pdf). This is an outlier versus Do-Faff; treat as replications-in-conflict and check the cost assumptions before believing it.
- "Gold Standard Pairs Trading Rules: Are They Valid?" (arXiv 2010.01157, Oct 2020), US equities 1990-2020 incl. Covid: base distance and cointegration strategies **fail to beat the market** (total 0.11%/mo and 0.18%/mo vs market 0.47%/mo; Sharpe -0.86 and -0.27), but deliver ~**2%/month in bear markets** and lag ~1%/month in bull markets; they explicitly note that selecting bear markets ex post is foresight — [arXiv](https://arxiv.org/pdf/2010.01157.pdf).
- Dual-class (same-claim) pairs, 2026 practitioner study, SIP daily bars 3 Jan 2022-3 Sep 2026 (1,172 sessions/symbol), dividends verified leg by leg: GOOGL/GOOG deviation sd **28bp**; decile sort D1-D10 = **+49.1bp over 10 sessions** (t 9.03 raw, ~2.86 after overlap haircut); but round-trip costs are GOOGL/GOOG **1.3bp**, NWSA/NWS 7.8bp, FOXA/FOX 26.1bp, ZG/Z 24.1bp, UAA/UA 39.4bp, HEI/HEI.A **124bp**; only 2 of 6 pairs survive as a taker; gross edge vs round-trip cost correlation **+0.95** (Spearman +0.94); lookalike-but-not-same-claim pairs (FOXA/NWSA, GOOGL/MSFT, HEI/TDG) show **zero** reversion; multi-day version out-of-sample 2025-2026 at |z|1.5 = +23.7bp (t 2.32, n=132) but pooled +10.0bp and insignificant at |z|2.0; **borrow assumed free and available** — [Vortex Capital Group, Sep 2026](https://www.vortexcapitalgroup.com/insights/one-claim-two-prices-dual-class-arbitrage-us-equities) (practitioner).
- Academic dual-listed-company arbitrage, 12 DLCs 1980-2002: abnormal returns up to **~10%/yr** after costs and margin requirements, but with "substantial idiosyncratic return volatility and a high incidence of large negative returns" — [Review of Finance, 2009](https://doi.org/10.1093/rof/rfn031).
- OU-process treatment of GOOGL/GOOG reports expected return 8.71%→8.36% as one-way cost rises 0.1%→0.7% and Sharpe 5.64→5.36 — [Yang & Chen, SAJBM, Sep 2025](https://sajbm.org/index.php/sajbm/article/view/4850/3419). Treat the Sharpe as an artefact of annualizing a near-zero-variance spread; the return sensitivity to cost is the usable part.
- Lead-lag: international size/coverage portfolios, weekly or monthly, produce significant pre-cost alpha that "quickly deteriorate as transaction costs increase and become insignificant for one-way costs above 10bp" (weekly) and above ~40bp (monthly) with 43-55% weekly turnover — [IJFR 2018](https://www.sciedu.ca/journal/index.php/ijfr/article/download/12633/7802).
- Lead-lag at tick frequency: 60.3-63.6% directional accuracy forecasting the next midquote move, +0.4 to +0.54bp per trade at mid, but **-2.73 to -3.44bp per trade once the bid-ask spread is paid** — [Huth & Abergel, arXiv 1111.7103](https://arxiv.org/pdf/1111.7103). Profitable lead-lag arbitrage requires LOB data, latency and exchange fees that a retail API cannot reach — [Poutré, Dionne & Yergeau, *IJF* 40(3), 2024](https://ideas.repec.org/a/eee/intfor/v40y2024i3p1002-1021.html).

### Inferences
- Frequency requirement is the killer: the pairs edge is 30-50bp per trade, so you need (i) spreads ≤5bp, (ii) borrow at general-collateral rates, (iii) many independent pairs. A USD 147 cash account has none of the three. Pairs/stat arb is a *post-USD 2,000* project, and even then only with a margin account.
- The dual-class result is the most useful single design lesson in this whole note: the correct control is a **lookalike pair without a shared claim**. Any pairs backtest that cannot reproduce "no reversion for FOXA/NWSA" is measuring beta, not arbitrage.
- ETF pairs (SPY/IVV/VOO, or ETF vs its index) are not a pairs trade for retail: the spread is 1-2bp and the arbitrage is done by authorised participants with creation/redemption. I found no credible public study showing after-cost retail profit in ETF-vs-NAV or ETF-vs-futures basis at daily frequency.

### Gaps
- No public, after-cost estimate of *ETF-pair* (e.g. IVV/SPY) or *share-class* returns for a sub-USD 2,000 account; all studies assume institutional borrow.
- Borrow cost for the specific thin legs (HEI.A, FOX, NWS, LEN.B) is unverified in every source I found; the 2026 dual-class study says outright that it "could not verify locate availability or rate".
- No source quantifies how much of the post-2002 pairs decline is competition versus decimalization versus Reg NMS; the literature (Do-Faff) attributes it to reduced arbitrage opportunities but does not decompose it.

---

## Seasonality and calendar effects: turn-of-month, month-end, commodity seasonality, FX fix — size and post-publication decay

### Takeaway
Every calendar effect I could source has either decayed to statistical zero or only survives in a form (intraday FX fix, slow-moving commodity seasonality) that a USD 147 cash account cannot trade. Turn-of-month went from ~12.7bp/day before 1987 to 2.7bp/day after 2001 and is now indistinguishable from zero; commodity seasonal strategies fail to beat an equal-weight long benchmark out-of-sample; the FX 4pm-fix effect is 14bp per 10% equity move, measured in a one-hour window, and its methodology was changed in 2015.

### Cited Findings
- Han, Han & Tian, "The disappearing turn-of-month effect", *Finance Research Letters* 71, Feb 2025: the TOM effect "disappears entirely after 2001"; the liquidity explanation (Ogden 1990) no longer holds; authors attribute it to the post-2001 fall in transaction costs — [RePEc record](https://ideas.repec.org/a/eee/finlet/v71y2025ics1544612324014909.html).
- Independent replication with two data sources and HAC standard errors: TOM premium 12.74bp/day (S&P 500, pre-1987) and 12.58bp/day (French US market), 11.66/14.43bp in the 1987-2001 window, then **2.72bp/day (p=0.53)** and **2.97bp/day (p=0.50)** after 2001, and 2.22/1.84bp/day under T+2; modern 10-year rolling 95% intervals include zero — [Herrera, Aug 2026](https://www.luiguiherrera.com/en/research/the-ghost-of-an-anomaly) (practitioner replication).
- Counter-evidence: Marquering, Nisser & Valla, *Applied Financial Economics* 16(4), 2006 find the weekend, holiday, time-of-month and January effects disappeared after publication but "the turn-of-the-month effect seems still present" — [RePEc](https://ideas.repec.org/a/taf/apfiec/v16y2006i4p291-302.html). Shaneyev & Ghimire (*European Journal of Finance* 27(3), 2021) find post-publication decay insignificant for TOM (t -1.22, -1.55) — [PDF](https://rgu-repository.worktribe.com/OutputFile/2439425). Read together: TOM decayed via microstructure, not via publication.
- Commodity seasonality, 26 commodities 1970-2023: only a few commodities in the early years show half-monthly/monthly seasonality; the same-month strategy of Keloharju et al. (2016) beats the other-month strategy mostly in **1990-1999**; seasonal effects "have weakened in recent years" — Li, Liu, Miao & Tse, *International Review of Economics & Finance* 93, 2024 — [RePEc](https://ideas.repec.org/a/eee/reveco/v93y2024ipbp448-462.html).
- Out-of-sample test with costs, 15 liquid commodity futures, rolling 10-year estimation, evaluated 2016-2024: equal-weight long benchmark CumRet **16.81%**, Sharpe **0.191**, maxDD **-41.4%**; best model (dummy-variable regression, long) Sharpe 0.245; **none of 18 paired bootstrap Sharpe tests rejects** after Holm adjustment; SSA variants have negative median cumulative returns — [arXiv 2609.12227, Sep 2026](https://arxiv.org/abs/2609.12227).
- Global futures seasonality (bonds, commodities, equities), walk-forward out-of-sample: fast patterns (day-of-week, day-of-month) show strong gross but "negative performance net of transaction costs"; slow patterns (day-of-quarter, day-of-half-year, day-of-year) are positive net except day-of-quarter; ensemble OOS Sharpe competitive with established time-series factors and adds ~**30%** to a global factor portfolio's Sharpe — [arXiv 2611.15657, Nov 2026](https://arxiv.org/html/2611.15657).
- FX fix (WM/Reuters 4pm London), 10 developed currencies, 2004-2012, 5-minute TWAP data: panel regression of the 15:00-16:00 currency return on the month-to-date equity return gives **-0.0142** (t significant, R²=0.03), i.e. a **10% equity appreciation → 14bp of currency depreciation in the hour before the month-end fix**; **72% of that move reverses before noon the next day**; month-end NBFI order flow is **1.39x (NZD) to 2.36x (EUR)** normal volume — [Melvin & Prins, ECB workshop PDF](https://www.ecb.europa.eu/events/pdf/conferences/131216/Third_FX_Workshop_MELVIN_PRINS_Equity%20hedging%20and%20exchange%20rates%20Nov%202013.pdf).
- That fix methodology was replaced after the 2013 manipulation scandal; the WM/R fix now uses a widened window, and a 2024 pre-registered study re-tests its representativeness — [Journal of International Financial Markets, Institutions & Money, 2024](https://iris.unitn.it/retrieve/64d95366-a7a7-4bc5-9aa2-a7b889ab01cd/1-s2.0-0927538X24000623-main.pdf). Any pre-2015 fix anomaly number should be treated as regime-specific.

### Inferences
- Seasonality is now a *factor-diversification* story (slow, low-turnover, cross-market), not a calendar-timing story. The one configuration with positive net OOS results is exactly the one retail cannot run: multi-market futures, long/short, day-of-year rebalancing.
- TOM is the ideal **negative control** for a backtesting harness: a rule that was worth 12.7bp/day in 1960-1986 and ~0 today must show ~0 out-of-sample. If a harness finds OOS TOM alpha, the harness is broken (look-ahead in the T-4/T+3 definition, or dividend/split misalignment).
- The FX fix trade needs (a) spot FX execution inside a 60-minute window, (b) 24/7 or London-hours monitoring, (c) a size large enough that 14bp covers the spread. At USD 147 the gross P&L per event is cents.

### Gaps
- No source gives an after-cost, retail-feasible estimate for month-end equity-index timing in 2020-2026 specifically; the 2025/2026 papers stop at statistical significance.
- I found no reliable public study of *commodity ETF* (DBC, DBA, UNG) seasonality net of ETF roll costs, which is the only version a USD 147 account could trade.
- No post-2015 published measurement of the residual 4pm-fix effect after the WM/R methodology change with numbers.

---

## ETF flows, index rebalances, fund holdings changes, options-expiration pinning: measurable price effects and retail feasibility

### Takeaway
All four effects are real and measurable, and all four have shrunk to the point where the tradable residual is smaller than the cost of the trade. S&P 500 addition excess return went from 8.32% (1995-99) to -0.04% (2011-21) between announcement and effective date; ETF flow price pressure is 34bp temporary + 55bp permanent per 1-sigma ($3bn) shock, i.e. a few bp for the ETFs a retail account can buy; expiration pinning is 16.5bp average and requires knowing dealer gamma, which public open interest does not reveal.

### Cited Findings
- S&P Dow Jones Indices, "What Happened to Index Effect?" (1995-Jun 2021): median excess return announcement→effective for additions **8.32% (1995-99) → 3.64% (2000-10) → -0.04% (2011-21)**; deletions **-9.58% → -6.99% → +0.06%**; USD 13.5trn indexed/benchmarked to the S&P 500 at end-2020 — [S&P DJI PDF](https://www.spglobal.com/spdji/en/documents/research/research-what-happened-to-the-index-effect.pdf).
- Greenwood & Sammon, NBER WP 30748, Dec 2022: addition abnormal return **3.4% (1980s), 7.6% (1990s), 0.8% (last decade)**; deletion -0.6% between 2010 and 2020 — [NBER](https://www.nber.org/papers/w30748).
- Kappou (post-crisis sample 2008-2013): day-after-announcement +3.01% (significant), but effective-date abnormal return **-0.10% and insignificant** post-2008 vs ~+1% pre-2008; "buying the added stock the morning after announcement and selling at the event close does not generate any significant returns any longer" — [Reading repository PDF](https://centaur.reading.ac.uk/76714/1/Diminished%20effect%20of%20index%20rebalances_kkappou.pdf).
- Petajisto, *Financial Analysts Journal*, 2023: additions outperform by 41.5% in the 12 months *before* announcement and deletions underperform by -29.1% — i.e. the pre-announcement drift is a momentum signal, not a rebalance trade; post-trade-date reversal for deletions is +20.4% over the next year (t 3.40) — [Taylor & Francis](https://www.tandfonline.com/doi/full/10.1080/0015198X.2023.2173506).
- ETF flows: a 1-sigma aggregate flow shock (1.11% ≈ **USD 3bn**) is associated with **34bp temporary + 55bp permanent** market return, with **38% of the shock reversed within five days** (2007-2010 VAR) — [Staer, *International Journal of Business* 22(4), 2017](https://ijb.cyut.edu.tw/var/file/10/1010/img/863/V224-1.pdf).
- Decomposed flows: the *unexpected* component of daily ETF creation/redemption predicts next-day ETF returns by **8.8-9.8bp per 1% of unexpected flow**, with no reversal out to 40 days (information, not pressure), implying 19.16% open-to-close or 22.42% close-to-close annualized for informed participants — [Xu, Yin & Zhao, *Financial Management*, 2022](https://onlinelibrary.wiley.com/doi/10.1111/fima.12396). Undecomposed flows do reverse on days 3-5.
- Spot bitcoin ETFs, Jan 2024-Apr 2025 (313 days): **USD 100m net flow → 53bp same-day return** (74bp IV), 21% of daily return variance, cumulative impact 96bp at 10 days; individual shocks reverse but flow autocorrelation creates the drift — [SSRN 6592830, Apr 2026](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6592830).
- Expiration pinning: closing prices of optionable stocks cluster at strikes; average return alteration **≥16.5bp per expiration**, ~**USD 9bn** aggregate market cap shift; attributed to market-maker delta-hedge rebalancing plus proprietary-trader manipulation — Ni, Pearson & Poteshman, *JFE* 78(1), 2005, pp. 49-87 — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=519044).
- The mechanism requires dealers to be **net long gamma** at a large strike; public open interest cannot tell you which side dealers are on, so max-pain is not a forecast. Avellaneda & Lipkin's model gives pinning probabilities of ~10-30% conditional on large open interest — [Avellaneda slides](https://math.nyu.edu/inmemoriam/avellaneda/PinningSlides.pdf); a summary of the follow-on literature (Golez & Jackwerth 2012: S&P futures pulled to strikes at serial expiry, pushed *away* before quarterly index expiry; weekly expiries weaker than monthly) is at [Tradoki, Sep 2026](https://blog.tradoki.com/posts/options-expiration-pinning-explained) (practitioner).

### Inferences
- The index-rebalance trade is a *liquidity-provision* business (sell to the closing auction imbalance, buy the reversal), which requires being the counterparty at the close, not a marketable order. Retail marketable orders pay the effect rather than earn it.
- ETF flow signals need intraday or next-day NAV/creation data and the ability to trade the *basket*; the residual for a single ETF is a few bp, below spread.
- Pinning is a market-making/hedging P&L, not a directional signal; the only retail-accessible version is selling options into expiry, which needs options approval and capital.

### Gaps
- No source measures the post-2021 index effect with 2022-2026 data; the S&P DJI study ends June 2021 and the NBER paper covers "last decade" ending ~2020.
- No source gives an after-cost estimate for retail trading the ETF-flow reversal; all studies use institutional baskets.
- Weekly-options pinning (post-2022, 0DTE era) is documented only in working papers with small samples (93 stocks, 2010-2012 in the summary above); nothing reliable for 2024-2026 index products.

---

## Shorting: cost of borrow, margin, locate, and which brokers/APIs permit it at USD 147; long-only alternatives

### Takeaway
Shorting is unavailable at USD 147 at every broker I checked: both IBKR and Alpaca require **USD 2,000 equity** for margin or any short sale, and Alpaca additionally requires round-lot (100-share) locates for hard-to-borrow names. So every strategy in this note must be recast long-only or long/flat before it can be tested on this account. The long-only recasts lose the market-neutral property that produced most of the literature's Sharpe.

### Cited Findings
- IBKR: "For accounts trading on margin and/or executing short sales, the minimum equity requirement is **USD 2,000**"; the FINRA rule change removed the USD 25,000 pattern-day-trader minimum and replaced it with intraday margin standards, with broker transition ending **October 2027** — [IBKR FAQ](https://www.interactivebrokers.com/support/faq/content/if-25-000-minimum-equity-1460021712); [IBKR margin page](https://ndcdyn.interactivebrokers.com/en/trading/margin-stocks.php?ex=us&hm=us&pm=1).
- IBKR short mechanics: short initial margin 31.5% of market value (or USD 5.00/share below USD 15.87, 100% below USD 5.00); borrow charged as a daily fee, with "special fees expressed in terms of daily interest" for hard-to-borrow stock; short proceeds interest is proportionally lower for accounts under USD 100k NAV — [IBKR short sale cost](https://www.interactivebrokers.com/en/pricing/short-sale-cost.php); [fees overview](https://www.interactivebrokers.com/support/faq/content/overview-fees-1112363676).
- IBKR margin loan benchmark: USD margin rate **5.38%** at the USD 25k tier as of 13 Nov 2026 (Fed funds + 1.5% up to USD 100k) — [IBKR margin](https://www.interactivebrokers.com/en/trading/margin.php).
- IBKR commissions: USD 0.005/share with a **USD 1.00 minimum per trade** (IBKR Pro); IBKR Lite is commission-free on US stocks/ETFs, minimum balance USD 0 — [fees overview](https://www.interactivebrokers.com/support/faq/content/overview-fees-1112363676).
- Alpaca: "In order to trade on margin or sell short, you must have **$2,000 or more account equity**. Accounts with less than $2,000 will not have access to these features and will be restricted to 1x buying power"; 5,000+ easy-to-borrow symbols with **$0 locate and borrow fees**; hard-to-borrow requires an approved locate, **round lots of 100 shares**, single-use and non-refundable — [Alpaca docs](https://docs.alpaca.markets/us/docs/margin-and-short-selling); [Alpaca support](https://alpaca.markets/support/determine-margin-account).
- Retail commission arithmetic for our constraint: a monthly 8-leg rebalance on USD 147 at IBKR Pro's USD 1.00 minimum = USD 8/month = **~65% annualized drag**; at 5bp one-way spread on 8 legs × 12 rebalances the drag is ~48bp/yr. Zero-commission execution is therefore not an optimization, it is a precondition.

### Inferences
- Long-only recasts, ranked by how much of the original edge survives:
  1. **Long/flat TSMOM** (hold asset if trend positive, else T-bills): keeps the crisis-avoidance half of trend following, loses the short-bond/short-equity profits that made 2022 exceptional. Expect roughly half the gross Sharpe.
  2. **Long the cheap leg of a dual-class pair**: keeps ~50% of the spread reversion but adds full equity beta; the 28bp spread sd is swamped by a 1.5%/day stock move, so this is only viable with a beta hedge (SPY short or put), which needs margin.
  3. **Long-only carry proxies** (short-duration high-yield/T-bill spread, covered-call ETFs): these are beta/vol-selling exposures, not carry in the Koijen sense; no source supports them as an edge at retail size.
  4. **Inverse ETFs / puts as a short substitute**: inverse ETFs reset daily and bleed in choppy markets (2x/3x worse); puts have defined risk but the premium is a direct cost that a 30-50bp/month edge cannot cover.
- For a USD 147 account the honest conclusion is: **only long/flat, monthly-rebalanced, zero-commission ETF strategies are testable**. Everything else must be paper-traded or deferred until equity ≥ USD 2,000.

### Gaps
- No broker I checked publishes a *hard-to-borrow rate* for a sub-USD 2,000 account, because such accounts cannot short at all. Borrow-cost sensitivity must therefore be assumed, not measured.
- No source compares the after-cost performance of long/flat TSMOM versus long/short TSMOM on the same ETF universe; that gap is exactly what hypothesis H1 below is designed to fill.
- Fractional-share availability differs by broker and is not documented for shorting (fractional shares cannot be shorted at Alpaca or IBKR), which rules out dual-class pairs at USD 147 even if the spread were 10x wider.

---

## Concrete testable hypotheses (2-3) with exact rules, data sources, in/out-of-sample split and controls

### Takeaway
Three hypotheses are worth running, in this order: (H1) long/flat 8-asset ETF time-series momentum versus buy-and-hold, with a random-signal null; (H2) dual-class spread reversion with a *lookalike-pair* placebo as the control, paper-only until equity ≥ USD 2,000; (H3) a pre-registered *negative* control (turn-of-month) whose expected result is zero, used to validate the harness. Each has a measurable rule, an explicit cost model, a capacity ceiling and a control that can fail.

### Cited Findings (the numbers each hypothesis must beat)
- H1 benchmark: 5-ETF TSMOM net Sharpe **0.53** vs buy-and-hold **0.65**, net CAGR 11.0% vs 7.5%, maxDD -47.6% vs -33.6%, 5bp one-way, 2004-2026 — [Holdout Labs audit](https://holdoutlabs.io/audits/batch-3/reports/tsmom-5).
- H1 long-horizon prior: net-of-cost net-of-fee Sharpe **0.76** on 67 futures markets; after-cost return 11.0%/yr — [AQR Century PDF](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/AQR-JPM-Fall-2017.pdf).
- H2 gross edge and cost, per pair: GOOGL/GOOG +4.6bp gross vs 1.3bp round trip; NWSA/NWS +15.3 vs 7.8; FOXA/FOX +25.8 vs 26.1; ZG/Z +16.5 vs 24.1; UAA/UA +17.4 vs 39.4; HEI/HEI.A +49.7 vs 124.0; pooled gross +17.5bp (t 5.66, n=211) — [Vortex Capital Group](https://www.vortexcapitalgroup.com/insights/one-claim-two-prices-dual-class-arbitrage-us-equities).
- H2 placebo: FOXA/NWSA, GOOGL/MSFT and HEI/TDG show 10-session reversion slopes of -0.00, -0.01 and -0.07 with spread sds of 799bp, 4,149bp and 591bp vs 28bp for GOOGL/GOOG — same source.
- H3 prior: TOM premium 12.74bp/day pre-1987, **2.72bp/day after 2001 (p=0.53)** — [Herrera](https://www.luiguiherrera.com/en/research/the-ghost-of-an-anomaly); "disappears entirely after 2001" — [Han, Han & Tian, FRL 71, 2025](https://ideas.repec.org/a/eee/finlet/v71y2025ics1544612324014909.html).

### Inferences — the three specifications

**H1. Long/flat cross-asset time-series momentum, 8 liquid ETFs (the only strategy that fits USD 147) — incremental to the project's existing dual-momentum baseline, not a rerun**

- Do **not** re-test the project's existing monthly dual momentum over 9 ETFs + BTC (already closed: ~10-15%/yr expected, losing years 20-30% — `research/LESSONS.md`, "Conclusions so far"). That result is the benchmark this hypothesis must beat, and its data must be treated as used.
- Universe (all US-listed, zero-commission at IBKR Lite/Alpaca): SPY, EFA, EEM, IWM, IEF, TLT, GLD, DBC. (DBC starts 2006-02; GLD 2004-11. Two sub-samples: 5-asset 2004-2026 and 8-asset 2007-2026.)
- Data: adjusted close (total return) from Yahoo Finance or Stooq; cross-check 10% of dates against issuer NAV history; risk-free = FRED `DTB3` (secondary market 3-month T-bill, daily) or `TB3MS` monthly.
- Signal at each month-end t: `excess12_i = P_i(t)/P_i(t-12m) - 1 - rf12_i`. Long asset i if `excess12_i > 0`, otherwise hold the asset's cash proxy (BIL/SGOV, or literal cash at 0% for conservatism).
- Sizing: `w_i ∝ 1/σ_i` with `σ_i` = EWMA(λ=0.94) of daily returns over the last 60 sessions, annualized. Scale the vector so ex-ante portfolio vol = 10%/yr, **cap gross at 1.0** (no leverage, no margin). If the vol target implies gross > 1, scale all weights down proportionally.
- Execution: trade at the **next day's open** after the month-end signal (never the signal-day close). One rebalance per month; no intra-month stops.
- Costs: base case **5bp one-way** per leg traded (spread + slippage, zero commission), sensitivity at 2/10/20bp; charge cost on `|Δw|` only. Add 0.03-0.10%/yr ETF expense ratio as a constant drag.
- Split: **IS 2004-01 to 2015-12; OOS 2016-01 to 2026-09** (OOS contains Covid-2020, the 2022 bond/equity drawdown, and the 2023-2025 trend drought).
- Controls, all four required:
  1. Equal-weight buy-and-hold of the same universe, same rebalance dates, same costs.
  2. 60/40 SPY/IEF monthly rebalanced.
  3. **Random-signal null**: replace `sign(excess12)` with Bernoulli draws calibrated so the long-rate matches the strategy's realized long-rate; run 1,000 paths, hold turnover and costs identical. Report the strategy's Sharpe percentile in that null distribution.
  4. Anti-signal (short the trend, long-only version = hold asset when trend is *negative*); this should have a lower net Sharpe. If it does not, the result is noise.
- Success criterion (pre-register): OOS net Sharpe exceeds the better of controls 1-2 by **≥0.20** with a block-bootstrap 95% CI excluding zero, *and* max drawdown is at least 5pp smaller, *and* the strategy is positive in both 2020 and 2022, *and* it beats the project's existing 9-ETF + BTC dual-momentum baseline over the same OOS window on the same cost schedule (otherwise there is no reason to change the running bot). Anything less = no edge, report as such.
- Capacity: at USD 147 with 8 legs, minimum trade size ≈ USD 18; spread cost 5bp = USD 0.009 per leg — irrelevant; commission at USD 1/trade = 5.4% per leg — fatal. **Zero-commission broker required.** Capacity ceiling for the strategy itself is in the hundreds of millions (all components are top-10 ETFs), so capacity is not the constraint; account size is.
- Prior expectation from the evidence: gross Sharpe ~0.4-0.6, net 0.3-0.5, likely **below** buy-and-hold on Sharpe but with a much smaller 2022 drawdown. The hypothesis is a *risk-adjusted* claim, and it may well fail on Sharpe while succeeding on drawdown — pre-register which metric decides.

**H2. Dual-class / twin-share spread reversion (paper-trade now; live only at equity ≥ USD 2,000 with margin)**

- Pairs (same claim, verified dividend parity leg-by-leg): GOOGL/GOOG, NWSA/NWS, FOXA/FOX, ZG/Z, UAA/UA, HEI/HEI.A, BF.A/BF.B, LEN/LEN.B.
- Data: **raw, unadjusted** daily closes (Alpaca SIP or Yahoo raw); 1-minute SIP bars only if testing the intraday version; dividend records per leg to confirm parity; class terms from issuer filings, not ticker convention.
- Rule: `R_t = log(P_A/P_B)`; `d_t = R_t - mean(R_{t-60..t-1})` in bp; `z_t = d_t / sd_60`. Enter when `|z| ≥ 1.5` (long cheap, short rich), exit when `z` crosses 0, hard time stop 10 sessions (daily version) or 12 weeks (slow version), no overlapping positions per pair.
- Costs: use the **measured** per-pair round trip from the NBBO study above (1.3bp to 124bp), not a flat assumption; that measurement alone eliminates 4 of 6 pairs.
- Borrow: assume GC 0.3%/yr base case, HTB 5%/yr stress, and **flag any pair whose edge < 2× assumed borrow** as untradeable.
- Split: IS 2022-01 to 2024-12; OOS 2025-01 to 2026-09 (matches the only study with this split; do not extend IS backwards without re-verifying dividend parity).
- Controls: (i) the three lookalike-but-different-claim pairs (FOXA/NWSA, GOOGL/MSFT, HEI/TDG) as placebos — they must show ~zero reversion; (ii) a random-pair placebo drawn from same-sector, similar-market-cap names; (iii) a beta-matched SPY-hedged version to separate spread P&L from market beta.
- Success criterion: pooled OOS net return > 0 with t > 2 after the overlap haircut (divide t by √k for overlapping windows), and the placebo slope must be indistinguishable from zero. Publication of a *negative* result (edge ≈ cost) is an acceptable and likely outcome.
- Capacity: ~USD 10-50k per pair before the spread widens; at USD 147 and no shorting, **not executable** — fractional shares cannot be shorted, and one GOOGL share alone exceeds the account.

**H3. Turn-of-month long-only timing — a pre-registered negative control**

- Rule: long SPY from the close of the 4th-to-last trading day of the month (T-4) to the close of the 3rd trading day of the next month (T+3); otherwise T-bills. Two switches per month, 1bp per switch.
- Split: IS 1963-2001 (Kenneth French daily market factor, `Mkt-RF` + `RF`), **OOS 2002-01 to 2026-09**. Costs 1bp and 5bp.
- Controls: (i) all other trading days as the comparison bucket, with a HAC t-test; (ii) a random 7-day window per month with matched turnover; (iii) the same rule applied to a placebo index (e.g. a non-US index) where no liquidity story exists.
- Expected result: ~0 alpha post-2001 (2.7bp/day, p≈0.53). Success criterion is therefore **failure**: if this rule shows significant OOS alpha at 5bp costs, the harness has a look-ahead or survivorship bug and H1/H2 results are not trustworthy.
- Capacity: unlimited; irrelevant. Its only purpose is harness validation.

**Screened out (documented, with the number that kills each)**
- Crypto funding carry: 2.92% gross annualized in 2026 vs ~5% T-bills; worst 90-day window -0.39% but liquidation/de-peg tail not in the funding series — [Delta Tech Systems](https://www.delta-tech-systems.com/research/funding-carry-compressed); [Alpha Research](https://bryanvine.github.io/alpha-research/paper2.html). Also needs two legs and margin → not a USD 147 trade.
- S&P 500 index addition: 0.8% last decade, -0.04% median AD→ED 2011-2021, so no residual after the announcement gap — [NBER 30748](https://www.nber.org/papers/w30748); [S&P DJI](https://www.spglobal.com/spdji/en/documents/research/research-what-happened-to-the-index-effect.pdf).
- Options-expiration pinning: 16.5bp average, requires dealer gamma sign that public OI does not reveal — [Ni/Pearson/Poteshman](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=519044).
- Lead-lag / index arbitrage: negative net P&L once the spread is paid (-2.73 to -3.44bp per trade) — [Huth & Abergel](https://arxiv.org/pdf/1111.7103).
- Equity pairs trading: ~30bp/month after costs and "largely unprofitable after 2002" — [Do & Faff](https://onlinelibrary.wiley.com/doi/10.1111/j.1475-6803.2012.01317.x).
- FX 4pm fix: 14bp per 10% equity move in a one-hour window; requires spot FX execution and post-2015 methodology is different — [Melvin & Prins](https://www.ecb.europa.eu/events/pdf/conferences/131216/Third_FX_Workshop_MELVIN_PRINS_Equity%20hedging%20and%20exchange%20rates%20Nov%202013.pdf).

**Alignment with the TradeLab repo rules (AGENTS.md / LESSONS.md)**
- Nothing here is to be run on the owner's machine: H1-H3 go into a branch + PR, unit tests run in GitHub Actions (`python -m unittest discover -s tests -t .`), and behaviour is observed read-only on https://tradelab.dgnr.us. No local server, no LLM calls, no timers.
- One account, one cash path: the project's account is USD 147 (~THB 5,000). Every hypothesis must be simulated as a single continuous account with cash, not as a stack of per-trade returns (LESSONS research trap #3). H1's vol-target must be capped at gross 1.0 precisely because margin is unavailable at this equity.
- Report format required by rule 6: ending equity, worst drawdown, number of months reaching the target, the same numbers at the higher cost/haircut, and the random control under identical costs. "Not found" is an acceptable and published outcome.
- Overlap check against closed experiments: Bybit pre-delisting rebound, DVOL two-leg strangle, cross-sectional multi-horizon momentum and the option-timing lines are closed and none of H1-H3 repeats them. Crypto funding carry appears here only as a screened-out candidate with its decay numbers, not as a new test.
- LESSONS trap #5 ("edges decay") is the reason H1's OOS window starts 2016 and H3's starts 2002: both must include the post-publication period, and neither may stop before 2026.

**Cross-cutting measurement rules for all three**
- Use deflated Sharpe (Bailey & López de Prado) and report the number of configurations tried; the H1 grid alone (lookbacks 3/6/9/12 × vol targets 5/10/15 × 5bp/10bp) is 24 trials.
- Report turnover as annualized one-way notional / average equity, and cost drag in %/yr, not just net Sharpe.
- Block-bootstrap (stationary bootstrap, mean block 20 days) confidence intervals for all Sharpe comparisons; overlapping-window t-stats divided by √k.
- Never report a strategy without the buy-and-hold and random-signal controls on the same cost schedule.

### Gaps
- No public dataset gives point-in-time ETF *holdings* changes at daily frequency for free (issuers publish daily holdings files but without revision history), so the "fund holdings changes" channel of KQ4 cannot be backtested without a paid vendor.
- I found no after-cost study of long/flat TSMOM on an 8-ETF universe including commodities and FX; H1 is genuinely untested, which is both its interest and its risk.
- No source quantifies the *tax* drag of monthly rebalancing in a USD 147 taxable account, which for a small account may exceed the spread cost.
