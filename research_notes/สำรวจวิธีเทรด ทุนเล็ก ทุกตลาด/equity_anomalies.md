# Stock-market anomalies and signal strategies: do they still pay after costs for a ~150 USD retail account? (notes compiled 2026-11-23)

Scope note: about 25 tool calls (searches, fetches, plus one computation on Ken French data). Where a number comes from my own calculation, it is marked **[own calc]** and the method is given. Where I could not verify a number in this session, it is listed under Gaps rather than stated as fact.

**[own calc] method:** I downloaded the Kenneth French Data Library monthly files on 2026-11-23 (5 factors 2x3, Momentum, ST Reversal; data run to 2026-09) from https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html. For each long-short factor I computed the compound annual return, the maximum drawdown of the cumulative long-short series and the annualized Sharpe ratio. These are paper returns: gross of costs, no shorting fees, and the factors are value-weighted long-short portfolios built on 2x3 sorts. A retail trader cannot hold them directly.

| Factor (US, long-short) | 1963-07 to 2019-12: ann. / maxDD / Sharpe | 2020-01 to 2026-09: ann. / maxDD / Sharpe |
|---|---|---|
| Market minus T-bill | 5.49% / -55.8% / 0.43 | 11.88% / -25.3% / 0.73 |
| SMB (size) | 2.18% / -56.4% / 0.26 | -2.83% / -32.7% / -0.20 |
| HML (value) | 3.29% / -39.8% / 0.39 | 0.72% / -33.7% / 0.12 |
| RMW (profitability/quality) | 2.80% / -41.8% / 0.40 | 1.69% / -25.9% / 0.21 |
| CMA (investment) | 3.03% / -19.6% / 0.47 | 0.09% / -27.6% / 0.06 |
| Mom (12-2 momentum) | 6.79% / -57.8% / 0.53 | 2.52% / -25.4% / 0.24 |
| ST_Rev (1-month reversal) | 5.52% / -33.8% / 0.56 | -5.90% / -40.4% / -0.39 |

Calendar-year returns [own calc], in percent: 2020 HML -30.7, Mom -0.9, ST_Rev -7.4. 2021 HML +22.2, RMW +24.5, Mom -2.9. 2022 HML +31.7, CMA +29.1, Mom +20.2, Mkt-RF -21.0. 2023 HML -11.1, Mom -20.5. 2024 Mom +18.5, SMB -10.5, ST_Rev -8.3. 2025 HML +6.6, RMW -10.2, ST_Rev -18.0. 2026 YTD to September: Mom +11.0, RMW -12.6.

### Summary evidence table (for report writer; [own calc] = Ken French data, see method above)

| Strategy | Mechanism | Best evidence of profitability (gross → net) | Typical annual return / drawdown | Works after 2020? | Data needed / free? | Feasible at USD 150? |
|---|---|---|---|---|---|---|
| Value (HML) | Risk premium or mispricing on cheap stocks | Survives costs (low turnover; [Novy-Marx & Velikov](https://www.nber.org/papers/w20721)) | 1963-2019 +3.3%/yr L-S, maxDD -40%; 2020-26 +0.7%/yr, -31% in 2020 [own calc] | Mixed: big 2021-22 rebound, flat overall | Fundamentals; free via ETFs / French library | Yes, via ETF (beta tilt) |
| Momentum (12-2) | Underreaction / herding | Survives costs with buffers ([N-M&V](https://www.nber.org/papers/w20721)); crash risk ([Daniel-Moskowitz](https://www.nber.org/system/files/working_papers/w20439/w20439.pdf)) | 1963-2019 +6.8%, maxDD -58%; 2020-26 +2.5%/yr, 2023 -20.5% [own calc] | Weak positive | Prices only; free | Yes, ETF or monthly basket |
| Quality / profitability (RMW) | Market underprices profitable firms | Survives costs; high capacity ([N-M&V](https://www.nber.org/papers/w20721)) | 1963-2019 +2.8%; 2020-26 +1.7%/yr, 2025 -10.2% [own calc] | Weak | Fundamentals; partly free | Yes, ETF |
| Low volatility | Leverage constraints / lottery preference | Low turnover; no net-of-cost source found | Lagged in 2025 ([Russell, vendor](https://russellinvestments.com/content/dam/ri/files/us/en/institutions/articles/Equity-Factor-Investing-Report_2025-Q3.pdf)) | Weak 2023-25 | Prices; free | Yes, ETF |
| Size (SMB) | Small-firm premium | Mostly microcap-driven ([HXZ](https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2019-2133..html)) | 2020-26 -2.8%/yr [own calc] | No | Free | n/a |
| Short-term reversal | Liquidity provision | Fails after costs (turnover ~100%/month; [N-M&V](https://www.nber.org/papers/w20721)) | 2020-26 -5.9%/yr, maxDD -40% [own calc] | No | Prices; free | No |
| PEAD | Underreaction to earnings news | Gone in non-microcaps since ~2006 ([Martineau](https://nowpublishers.com/article/Details/CFR-0122)); t = 2.18 → 1.43 without microcaps ([Subrahmanyam via UCLA](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again)) | ~0 in liquid stocks | No (liquid stocks) | Consensus estimates; mostly paid | No |
| Insider buying (opportunistic / cluster) | Insiders' private information | 82 bp/month VW 1986-2007 ([CMP 2012](https://www.nber.org/papers/w16454)); 2018-24 microcaps: reaction lasts 2-3 days, no alpha after day 1 ([Zhao preprint](https://arxiv.org/abs/2602.06198)) | Older evidence 6%+/yr; recent edge mostly on day 1 | Weak; fast decay | Form 4; free (EDGAR, openinsider) | Possible but marginal |
| Analyst revisions | Underreaction to revisions | Drift smaller since 2002; possibly explained by costs ([JBFA 2020](https://ideas.repec.org/a/bla/jbfnac/v47y2020i9-10p1151-1181.html)) | n/a | Unverified, likely weak | I/B/E/S; paid | No |
| Short interest / days-to-cover | Informed short sellers | 1.2%/month L-S, weaker VW / ex-microcaps ([NBER w21166](https://nber.org/papers/w21166)) | n/a | Unverified | FINRA biweekly; free, lagged | Long leg only, weak |
| Option IV spread / skew | Informed option traders | ~50 bp/week ([C-W 2010](https://repository.hku.hk/bitstream/10722/284759/1/content.pdf)); 6-month predictability for skew ([XZZ via Yae](https://acfr.aut.ac.nz/__data/assets/pdf_file/0007/29797/J-Yae_A-Comprehensive-Look-at-the-Option-Implied-Predictors-of-Stock-Returns.pdf)) | n/a | Unverified | Option IV history; paid | Not practical |
| Pairs trading | Mean reversion of co-moving stocks | 0.86 → 0.24%/month across 1962-2009 ([Do & Faff 2010](https://ideas.repec.org/a/taf/ufajxx/v66y2010i4p83-95.html)); ~30 bp/month net ([Do & Faff 2012](https://strathprints.strath.ac.uk/41722/)) | Low | Likely ~0 | Prices; free | No (needs shorting) |
| Turn of month / seasonals | Flow timing | Persists weakly, equal-weighted ([Choi-Hong-Lou 2022](https://aeaweb.org/conference/2022/preliminary/paper/iQikdBKZ)) | Fraction of 1%/yr | Weak | Prices; free | Yes, but trivial edge |
| Trend following (time-series momentum) | Slow diffusion / risk-off | SG CTA +20% in 2022 ([Hedgeweek](https://www.hedgeweek.com/flat-december-sees-ctas-complete-record-year-2022/)); about flat 2024-25 ([AlternativesWatch](https://www.alternativeswatch.com/2025/07/01/trend-following-hedge-funds-loss-h1-societe-generale-index/)) | Low single digits, deep drawdowns in reversals | 2022 yes, otherwise flat | Prices; free | Yes, simple MA filter on an ETF |
| ML cross-section (GKX) | Nonlinear combination of characteristics | Sharpe > 2 gross ([GKX](https://www.nber.org/papers/w25398.pdf)); profits from microcaps, eroded by turnover ([Avramov et al.](https://afajof.org/management/viewp.php?n=32368)); net Sharpe ~0.84 for best LSTM after decay and costs ([Azevedo-Hoegner-Velikov 2025](https://www.aeaweb.org/conference/2025/program/paper/TihddefB)) | n/a | Some net edge at institutional cost levels; retail unverified | Large characteristic panel; partly free (Chen-Zimmermann, JKP) | No (turnover, data) |
| LLM headline sentiment | Slow reaction to news | 38 bp/day gross; ~50% cumulative at 25 bp/trade; decaying with LLM adoption ([Lopez-Lira & Tang](https://arxiv.org/abs/2304.07619)) | n/a | Decaying | News feed (paid for real-time) + LLM API | No |

---

## 1. What the large replication studies say

### Takeaway
Most published anomalies are weaker than first reported. After publication, average long-short returns fall by about half (McLean-Pontiff: 58% lower). Two thirds of 452 anomalies fail once microcaps are given value weights (Hou-Xue-Zhang). Jensen-Kelly-Pedersen read the same evidence more kindly: about 82% replicate in a Bayesian sense, though at smaller sizes. Studies agree on the direction. Where they disagree, the split comes from how microcaps and multiple testing are handled.

### Cited Findings
- **McLean and Pontiff (J. Finance 2016, 97 predictors):** "Portfolio returns are 26% lower out-of-sample and 58% lower post-publication… We estimate a 32% (58%–26%) lower return from publication-informed trading. Post-publication declines are greater for predictors with higher in-sample returns, and returns are higher for portfolios concentrated in stocks with high idiosyncratic risk and low liquidity." The figures are quoted from the abstract, which I extracted from the PDF. — [McLean & Pontiff 2016 PDF](https://Www.Gwern.net/doc/economics/2016-mclean.pdf); [RePEc](https://econpapers.repec.org/RePEc:bla:jfinan:v:71:y:2016:i:1:p:5-32)
- **Hou, Xue and Zhang, "Replicating Anomalies" (RFS 2020):** With NYSE breakpoints and value-weighted returns, 65% of 452 anomalies fail |t| ≥ 1.96. The failure rate is 96% for the trading-frictions category and 82% at the multiple-testing hurdle of t = 2.78. Microcaps are about 60% of stocks by number but about 3% of market value. Even the anomalies that replicate are "much smaller than originally reported". — [IDEAS/RFS](https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2019-2133..html); [NBER w23394](https://www.nber.org/papers/23394); [Alpha Architect summary](https://alphaarchitect.com/replicating-anomalies/)
- With NYSE-Amex-NASDAQ breakpoints and equal weights, which let microcaps dominate, the HXZ failure rate falls to about 43%. This figure comes from Chen-Zimmermann's discussion as summarized by search, so it is secondary. — [Fed FEDS 2021-037](https://www.federalreserve.gov/econres/feds/files/2021-037pap.pdf)
- **Harvey, Liu and Zhu (RFS 2016):** The paper catalogs 316 factors from 313 papers and argues that a new factor needs t > 3.0, not 2.0. It concludes that "most claimed research findings in financial economics are likely false." — [NBER w20592](https://nber.org/papers/w20592); [RePEc RFS](https://econpapers.repec.org/RePEc:oup:rfinst:v:29:y:2016:i:1:p:5-68.)
- **Jensen, Kelly and Pedersen, "Is There a Replication Crisis in Finance?" (J. Finance 2023, 153 factors, 93 countries):** Taking HXZ's 35% success rate as the starting point, the rate rises to about 64% once factors that were insignificant in their original papers are dropped. Their Bayesian model, which adjusts for publication bias and multiple testing, puts it at about 82%. Replicated factors fall into 13 themes and hold up out of sample and across countries. Data are free at jkpfactors.com. — [NBER w28432](https://www.nber.org/papers/w28432); [CBS publisher version](https://research-api.cbs.dk/ws/portalfiles/portal/95651880/theis_ingerslev_jensen_et_al_is_there_a_replication_crisis_in_finance_publishersversion.pdf)
- **Chen and Zimmermann, Open Source Cross-Sectional Asset Pricing (Critical Finance Review 2022):** Their open code and data reproduce nearly all published predictors and post monthly long-short returns for more than 200 of them, free at openassetpricing.com. Their 2018 paper estimates publication bias at only about 12% of in-sample returns, too small to explain the post-publication decay, which points to mispricing being arbitraged away. — [SSRN 3604626](https://papers.ssrn.com/abstract=3604626); [Fed FEDS 2018-033](https://www.federalreserve.gov/econres/feds/files/2018033pap.pdf)
- **Chen and Lopez-Lira (2024 version):** After the original sample ends, published predictors keep about 53% of their in-sample mean returns, and data-mined predictors keep about 51%. Search summary only. — [arXiv 2212.10317](https://arxiv.org/html/2212.10317v5)
- **Novy-Marx and Velikov (RFS 2016):** Anomalies with one-sided monthly turnover under 50% mostly keep significant net spreads when designed to reduce costs. "Few of the strategies with higher turnover do." The most effective way to cut costs is a buy/hold spread, which sets a stricter rule for entering a position than for keeping it. Few net spreads clear t > 3. Size, value and profitability have the most capacity. — [NBER w20721](https://www.nber.org/papers/w20721)

### Inferences
- A rough prior for any published anomaly is that about half of the paper's gross return is left today. Fast anomalies (high turnover, microcap-based) lose most or all of it to costs.
- Factors that survive both the replication critics and the cost studies are slow-moving: value, profitability/quality, investment, and momentum with buffers. My own French-data calculation shows that even these earned close to zero after 2020 on a long-short basis, with momentum the exception at about +2.5% a year.

### Gaps
- I did not obtain a per-anomaly table of net-of-cost returns after 2020. The Chen-Zimmermann data could produce one but was not downloaded here.

---

## 2. Insider buying (SEC Form 4)

### Takeaway
Insider purchases, especially "opportunistic" (non-routine) and clustered ones in small firms, carried sizable abnormal returns in samples up to about 2007-2010. The most recent large-sample preprint (US microcaps, 2018-2024) finds the edge mostly sits in the first 2-3 trading sessions after the filing. A calendar-time portfolio that skips day 1 earns no significant alpha. For a retail trader who sees the filing late, little edge is left.

### Cited Findings
- **Cohen, Malloy and Pomorski, "Decoding Inside Information" (J. Finance 2012, data 1986-2007):** A portfolio of opportunistic insiders' trades earns value-weighted abnormal returns of about 82 bp per month. Routine insiders, who are more than half of all insider trades, earn about zero. The most informed are local, non-executive insiders at poorly governed firms. Opportunistic traders cut back trading after waves of SEC enforcement. — [NBER w16454](https://www.nber.org/papers/w16454); [NBER Digest](https://www.nber.org/digest/apr11/decoding-inside-information)
- **Jeng, Metrick and Zeckhauser (J. Business, sample period not verified here):** Insider purchases earn abnormal returns of more than 6% per year, and insider sales earn none that are significant. — [Harvard PDF](https://scholar.harvard.edu/sites/scholar.harvard.edu/files/rzeckhauser/files/insider_trading.pdf)
- **Lakonishok and Lee (RFS 2001):** The signal is strongest in small stocks and much weaker in large ones. This is via a secondary summary from Interactive Brokers Campus, **a broker blog**. — [IBKR Traders' Insight](https://www.interactivebrokers.com/campus/traders-insight/securities/stocks/what-corporate-insider-buying-can-tell-investors-evidence-from-academic-research/)
- **Clustering (Alldredge and Blank 2019):** Purchases made within two days of another insider's purchase were followed by about 2.1% abnormal return over the next month. This is via the same secondary summary. — [IBKR Traders' Insight](https://www.interactivebrokers.com/campus/traders-insight/securities/stocks/what-corporate-insider-buying-can-tell-investors-evidence-from-academic-research/)
- **Post-2018 evidence (Zhao, arXiv preprint 2602.06198, 2026, not peer-reviewed):** The sample is 13,534 Form 4 open-market purchases from 1,192 US issuers with market caps of USD 30-500M, 2018-2024.
  - First-day abnormal return is 4.13% for stocks farthest below their 52-week high and 0.86% for those nearest it. Random days average 0.14%.
  - Most of that gradient reflects volatility. With full controls the gap is 0.94 points (t = 2.11), which fails the paper's pre-specified bar.
  - "The reaction lasts about two to three sessions. The 29-day drift is imprecise (t = 1.70). A calendar-time portfolio that skips the first day earns no significant alpha."
  - A large-cap cluster-buy extension "fails every matched-comparison gate."
  - A gradient-boosting classifier reaches AUC 0.676, no better than logistic regression.
  — [arXiv 2602.06198](https://arxiv.org/abs/2602.06198)
- Purchases that follow acquisitions get about 23% less market reaction than the average insider purchase (CLS Blue Sky blog, 2026). — [CLS Blue Sky](https://clsbluesky.law.columbia.edu/2026/09/22/when-are-insider-purchases-credible-signals-of-private-information/)

### Inferences
- The classic 6%+ per year and 82 bp per month figures come from pre-2008 samples. The 2018-2024 microcap evidence says the reaction now happens within days of the filing. A retail trader buying at the next open after reading openinsider likely captures part of day 1 at best, and pays microcap spreads to do it.
- Insider buying in microcaps is still one of the more plausible signals for a small account, because size is no constraint and fractional or whole shares of USD 5-50 stocks work. Expect a modest edge with high variance, not 10%+ a year net.
- Data is free: SEC EDGAR Form 4 full-text and XBRL feeds, and openinsider.com screens including cluster buys. I did not verify openinsider's terms or reliability in this session.

### Gaps
- I found no peer-reviewed study that directly compares insider-purchase alpha before and after 2010 or 2020, or that reports net-of-cost retail implementation returns.
- I did not verify Lakonishok and Lee's exact magnitudes from the primary source.

---

## 3. Post-earnings announcement drift (PEAD)

### Takeaway
For non-microcap US stocks, PEAD has been essentially gone since about 2006 (Martineau 2022). Two 2025 papers claim it is alive. Subrahmanyam's 2025 replication shows that the claim depends on microcaps: t falls from 2.18 to 1.43 once they are excluded. Any remaining drift lives in illiquid microcaps where spreads would eat it.

### Cited Findings
- **Martineau, "Rest in Peace Post-Earnings Announcement Drift" (Critical Finance Review 2022):** Prices now absorb earnings surprises on the announcement day. In large stocks PEAD has been non-existent since 2006, and in microcaps it disappeared only recently. Drift in non-microcaps began disappearing in 2001 and was gone by 2006. The suggested causes are decimalization and the 2005 regulation (Reg NMS) that sped up high-frequency trading. — [CFR](https://nowpublishers.com/article/Details/CFR-0122); [UCLA Anderson Review](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again)
- **Counter-claims (2025):** Dickerson, Julliard and Mueller (JFE, in press) find that earnings drift "remains a major market factor". Hirshleifer, Peng and Wang (RFS 2025) find drift with t of about 14, weaker where social connectedness is higher. — [UCLA Anderson Review](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again)
- **Subrahmanyam (2025 working paper, Feb 2001-Dec 2024):** The earnings drift factor has t = 2.18 on all stocks and 1.43, not significant, once microcaps are excluded. Microcaps here are the bottom 20% by NYSE size and about 3% of market value. He argues the opposing papers did not filter microcaps. — [UCLA Anderson Review](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again)

### Inferences
- For a retail trader, PEAD in liquid stocks is not a viable edge after 2020. A microcap version might show gross drift, but the round-trip spread in microcaps is often several percent, and the gross drift found there is smaller than that.

### Gaps
- I have no net-of-cost microcap PEAD estimate after 2020. Earnings-surprise data (consensus estimates) is mostly paid, and free sources (for example Yahoo or Nasdaq calendars) were not verified for history or quality.

---

## 4. Analyst revisions, short interest, options-implied signals

### Takeaway
Short interest (days-to-cover) and option-implied signals (call-put implied-volatility spread, IV smirk) had strong original results. The evidence I found on decay after publication is thin. Option-implied signals need option-chain history, which is mostly paid. Short interest is free but published with a lag, twice a month.

### Cited Findings
- **Cremers and Weinbaum (JFQA 2010; sample period not verified here):** Stocks whose calls are relatively expensive compared with otherwise identical puts outperform those with expensive puts by about 50 bp per week. — [summary in HKU PDF/search](https://repository.hku.hk/bitstream/10722/284759/1/content.pdf)
- **Xing, Zhang and Zhao (JFQA 2010; sample period not verified here):** Stocks with the steepest implied-volatility smirk underperform, and the predictability lasts at least 6 months. — [NBER w19590 (cites XZZ)](https://www.nber.org/papers/w19590.pdf); [Yae, comprehensive look at option-implied predictors](https://acfr.aut.ac.nz/__data/assets/pdf_file/0007/29797/J-Yae_A-Comprehensive-Look-at-the-Option-Implied-Predictors-of-Stock-Returns.pdf)
- **Hong, Li, Ni, Scheinkman and Yan, "Days to Cover and Stock Returns" (NBER w21166):** A long-short days-to-cover strategy earns about 1.2% per month. Alpha Architect notes that value-weighted results are weaker, and DTC's edge over the plain short ratio loses significance without microcaps. — [NBER w21166](https://nber.org/papers/w21166); [Alpha Architect](https://alphaarchitect.com/betting-against-days-to-cover/)
- **Rapach, Ringgenberg and Zhou (JFE 2016):** Aggregate short interest predicts market returns, with an annual R² of about 13% out of sample. This is a market-timing signal, not a stock-picking one. — [RePEc JFE](https://econpapers.repec.org/RePEc:eee:jfinec:v:121:y:2016:i:1:p:46-65)
- Several cross-sectional anomalies on the replication lists are short-interest or option-based, so the general 50-58% decay applies to them. — [McLean & Pontiff 2016](https://Www.Gwern.net/doc/economics/2016-mclean.pdf)

- **Analyst forecast revisions:** Post-forecast-revision drift has shrunk since 2002, and one study argues the anomaly can be explained by random variation plus transaction costs (sample period not verified). Chen, Narayanamoorthy, Sougiannis and Zhou (2020) attribute it to investor underreaction. — [J. Business Finance & Accounting 2020 (IDEAS)](https://ideas.repec.org/a/bla/jbfnac/v47y2020i9-10p1151-1181.html); [search-result working paper](https://core.ac.uk/download/83969469.pdf)

### Inferences
- A tiny account cannot short, so only the long leg is usable: buy low short-interest stocks, or stocks with expensive calls. Long-only legs of these anomalies are usually much weaker than the long-short spreads reported.
- FINRA short interest is free, twice a month and lagged. Historical option IV surfaces (OptionMetrics) are institutional and expensive, so retail backtesting of option-implied signals is hard.

### Gaps
- I found no post-2020 test of analyst revisions. I/B/E/S is paid.
- I found no post-2015 out-of-sample test of the Cremers-Weinbaum or XZZ signals.

---

## 5. Momentum, value, quality, low volatility, trend following (performance after 2020 and crash risk)

### Takeaway
After 2020 the classic long-short US equity factors were roughly flat to slightly positive, with large year-to-year swings [own calc]. Value lost 31% in 2020 and gained 22% in 2021 and 32% in 2022. Momentum lost 20.5% in 2023 and gained 18.5% in 2024. Size, investment and short-term reversal were negative or about zero. Trend following (CTAs) had a record 2022 (about +20%), then sat roughly flat from 2023 to 2025. Momentum crash risk is extreme in rebounds after a bear market.

### Cited Findings
- 2020-01 to 2026-09 annualized, gross, long-short: Mom +2.5% (maxDD -25%), HML +0.7% (maxDD -34%), RMW +1.7%, CMA +0.1%, SMB -2.8%. By contrast 1963-2019 was Mom +6.8%, HML +3.3%, RMW +2.8%. — [own calc from Ken French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
- AQR (a factor-fund manager, vendor source): "From the GFC to about late 2020, value's performance was somewhere between subpar and terrible." — [AQR Perspectives](https://aqr.com/Research-Archive/Perspectives/We-Are-Not-Just-Value-Except-You-Know-When-We-Are)
- Low-volatility sub-factors kept underperforming in 2025 (Russell, Q3 2025 report). Quality is the factor that has been the most consistent since the GFC (LSEG). **Vendor sources:** Russell Investments and LSEG/FTSE Russell sell factor indices and products. — [Russell Investments Q3 2025](https://russellinvestments.com/content/dam/ri/files/us/en/institutions/articles/Equity-Factor-Investing-Report_2025-Q3.pdf); [LSEG/FTSE Russell Q4 2025](https://www.lseg.com/content/dam/ftse-russell/en_us/documents/market-insights/equity-factor/equity-factor-insights-q4-2025.pdf)
- Morningstar argues that factor investing is "very much alive" and that factor rankings rotate from year to year. This is commentary, not peer-reviewed. — [Morningstar](https://www.morningstar.com/financial-advisors/factor-investing-is-very-much-alive)
- **Momentum crashes (Daniel and Moskowitz, JFE 2016):** The worst two months of 1927-2013 were July-August 1932, when past losers rose about 232% and winners 32%. In March-May 2009 losers rose about 163% and winners 8%. A different source puts the 2009 momentum loss at more than 73% within three months. — [Daniel & Moskowitz NBER w20439](https://www.nber.org/system/files/working_papers/w20439/w20439.pdf); [Alpha Architect](https://alphaarchitect.com/avoiding-momentum-crashes/)
- **Trend following / CTAs:** The SG CTA Index returned a record +20.13% in 2022. The SG Trend Index gained about 2.6% in 2024 and then fell about 10.5% in the first half of 2025, ending 2025 at about +2.4%. — [Hedgeweek 2022](https://www.hedgeweek.com/flat-december-sees-ctas-complete-record-year-2022/); [AlternativesWatch Jul 2025](https://www.alternativeswatch.com/2025/07/01/trend-following-hedge-funds-loss-h1-societe-generale-index/); [Cambridge Associates on trend's struggle](https://publishedresearch.cambridgeassociates.com/?p=19140)

### Inferences
- A tiny account can capture these factors cheaply only through ETFs (value, quality, momentum and min-vol ETFs, with fees of roughly 0.15-0.30%). That is a beta tilt, not an alpha strategy. Building your own momentum portfolio from 10-30 stocks is possible with fractional shares, but tracking error is high and the long-only leg is weaker than the long-short.
- Time-series momentum on stocks or ETFs (for example a 10-month moving-average filter on an index ETF) needs only free price data and has low turnover. The historical benefit was mostly smaller drawdowns in long bear markets such as 2008 and 2022, not higher returns, and it whipsaws in V-shaped recoveries such as 2020.

### Gaps
- I computed no long-only factor returns or ETF returns net of fees after 2020.
- I have no SG Trend Index figure for 2022 or 2023.

---

## 6. Seasonality, pairs trading, short-term reversal

### Takeaway
Short-term reversal, the classic high-turnover anomaly, lost 5.9% a year gross from 2020 to 2026-09 [own calc]. It is dead for retail. Pairs-trading returns fell steadily from 0.86% a month in 1962-88 to 0.24% in 2003-09, before costs. Turn-of-the-month persists weakly, mainly in equal-weighted indices. These are low-value edges for a retail trader.

### Cited Findings
- ST_Rev (1-month reversal): +5.5% a year from 1963 to 2019, then -5.9% a year with maxDD -40% from 2020 to 2026-09, including -18.0% in 2025. These are gross figures, and the strategy turns over nearly 100% a month. — [own calc, Ken French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
- **Pairs trading (Do and Faff, FAJ 2010):** The top-20 pairs earned a mean excess return of 0.86% a month in 1962-88, 0.37% in 1989-2002 and 0.24% in 2003-09. They attribute up to 70% of the drop to worsening arbitrage risk. Do and Faff (2012, J. Financial Research) find that after commissions, market impact and short fees the strategy is still profitable "at much more modest levels", about 30 bp a month for well-matched pairs within refined industries. Gatev-Goetzmann-Rouwenhorst's original result is often cited as up to 11% a year excess, but that figure is secondary and was not verified. — [RePEc FAJ 2010](https://ideas.repec.org/a/taf/ufajxx/v66y2010i4p83-95.html); [Strathprints, robust to trading costs](https://strathprints.strath.ac.uk/41722/); [CFA Institute](https://rpc.cfainstitute.org/research/financial-analysts-journal/2010/does-simple-pairs-trading-still-work)
- **Turn of the month:** The effect "still exists, even in the recent period, but primarily on an equal-weighted basis" (Choi, Hong and Lou, 2022 working paper). It is not stronger in stocks with heavy 401(k) exposure. Other work finds the timing moving earlier, or the effect disappearing in many international markets. — [AEA 2022 paper](https://aeaweb.org/conference/2022/preliminary/paper/iQikdBKZ); [Atlanta Fed WP 2000-11](https://www.atlantafed.org/research/publications/wp/2000/11.aspx)

### Inferences
- Pairs trading needs short-selling. A USD 150 account cannot short in most retail setups, and borrow fees and margin minimums apply. Not feasible.
- Turn-of-the-month or pre-holiday timing on an index ETF is cheap to run with zero commission, but the expected edge is a fraction of a percent a year and the evidence is weak. It is more a curiosity than a strategy.

### Gaps
- I found no recent peer-reviewed source on the Halloween ("sell in May") or pre-holiday effects after 2020.

---

## 7. Machine learning prediction and LLM news sentiment

### Takeaway
ML cross-sectional models (Gu-Kelly-Xiu) show gross Sharpe ratios above 2. Most of that comes from microcaps and hard-to-arbitrage stocks, and high turnover erodes it after costs. The ChatGPT headline-sentiment signal earned 38 bp a day gross in its sample. The authors' own latest version says returns decline as LLM adoption rises and are capturable mainly by low-cost participants such as market makers.

### Cited Findings
- **Gu, Kelly and Xiu (RFS 2020; sample period not verified here):** Machine-learning forecast portfolios earn annualized Sharpe ratios "in excess of 2.0", gross of costs. — [NBER w25398](https://www.nber.org/papers/w25398.pdf)
- **Avramov et al. (2023), "Machine Learning vs. Economic Restrictions"** (search summary only, not read in full): ML strategies draw profits from microcaps, hard-to-arbitrage stocks and high limits-to-arbitrage periods, and high turnover shrinks them after costs. — [AFA/search summary](https://afajof.org/management/viewp.php?n=32368)
- **Azevedo, Hoegner and Velikov, "The Expected Returns on Machine-Learning Strategies" (AEA 2025 working paper):** Accounting together for transaction costs, post-publication decay and the post-decimalization period cuts performance by about 57% on average. The best strategy (a one-layer LSTM) still has an expected gross (net) Sharpe ratio of 0.94 (0.84). The authors say this contrasts with earlier work finding ML strategies unprofitable after economic constraints. The figures are quoted from the abstract, which I extracted from the PDF. — [AEA 2025](https://www.aeaweb.org/conference/2025/program/paper/TihddefB)
- **Jensen, Kelly, Malamud and Pedersen:** ML return forecasts that ignore trading costs rely on "fleeting small-scale characteristics, resulting in poor net returns". Building costs into the optimization fixes part of this. — [AEA 2024](https://aeaweb.org/conference/2024/program/paper/SYTF3aaz)
- **Lopez-Lira and Tang, "Can ChatGPT Forecast Stock Price Movements?" (arXiv 2304.07619, several versions 2023-2025):**
  - ChatGPT sentiment on headlines predicts next-day returns. GPT-1, GPT-2 and BERT do not.
  - Gross return is about 38 bp a day. At 10 bp per trade the cumulative return over the sample is about 350%. At 25 bp it is about 50%. These figures come from earlier drafts.
  - The latest version reports that returns decline as LLM adoption rises, and that exploitation is "only feasible for market participants whose transaction costs are sufficiently low, such as market makers".
  — [arXiv 2304.07619](https://arxiv.org/abs/2304.07619); [v6](https://arxiv.org/abs/2304.07619v6)

### Inferences
- A daily long-short signal on headlines with 25 bp round-trip costs loses most of its edge, and the signal is decaying. A USD 150 retail account with zero commission still pays the spread, typically several bp in large caps and much more in small caps where news effects are larger. The trader cannot short, and a cash account has settlement constraints. Net expectation is about zero.
- A retail-feasible version would be low-turnover: monthly rebalancing, large caps, long only. Avramov et al. and Jensen et al. show this is where most of the ML alpha disappears.

### Gaps
- I have no out-of-sample LLM-sentiment results for 2025-2026 or exact net numbers from the final version.
- A search snippet credited a figure of "up to 1.42% a month net" for ML strategies. I could not tie it to a specific paper, so it is not used.

---

## 8. Practical constraints for a ~150 USD account

### Takeaway
The US pattern-day-trader rule (USD 25k minimum for 4 or more day trades in 5 days) was abolished. The SEC approved FINRA's change on 2026-04-14, and new intraday margin standards replace it, with broker roll-out through 2026-27. Day trading on margin still needs a margin account, and the reported margin minimum is USD 2,000, which a USD 150 account does not meet. Fixed costs are no longer the issue with zero commission and fractional shares. Spreads, the inability to short, and the fact that a 1% edge is worth USD 1.50 a year are the issues.

### Cited Findings
- The SEC approved FINRA's Rule 4210 amendment on 2026-04-14. It eliminates the PDT designation, the USD 25,000 minimum and the trade-counting trigger. FINRA Regulatory Notice 26-10 adopts intraday margin standards in their place. — [FINRA Notice 26-10](https://www.finra.org/rules-guidance/notices/26-10); [Federal Register 2026-07485](https://www.federalregister.gov/documents/2026/04/17/2026-07485/self-regulatory-organizations-financial-industry-regulatory-authority-inc-notice-of-filing-of); [Schwab](https://www.schwab.com/learn/story/sec-approves-scrapping-25000-day-trader-minimum)
- E*TRADE states that the new minimum is USD 2,000, "same as any margin account". The effective date was reported as about 2026-06-04, with phased implementation through 2027, but I did not confirm this against a FINRA primary source. — [E*TRADE](https://us.etrade.com/knowledge/library/margin/pattern-day-trading-rule-change); [Firstrade blog](https://blog.firstrade.com/blog/2026/6/3/the-complete-guide-to-the-pdt-rule-elimination-everything-investors-need-to-know-on-day-one)

### Inferences
- **USD 150 arithmetic:** even a strategy earning 5% a year net makes USD 7.50 a year. Any fixed fee (data subscription, international wire, FX conversion fee, or a non-zero-commission broker charging USD 1 per trade) wipes out the edge. For a non-US (Thai) resident, the FX spread and the cost of funding a US broker probably matter more than the strategy.
- **Cash accounts:** without margin there is no day-trading cap, but settlement rules (T+1 in the US since May 2024, not verified here) limit how fast proceeds can be reused, and shorting is impossible.
- Only long-only, low-turnover, fractional-share-friendly strategies are realistic: factor ETFs, a monthly-rebalanced momentum or quality basket, and possibly insider-cluster buys in small caps.

### Gaps
- I did not verify any specific broker's fractional-share or commission terms, or fees for Thai residents.
