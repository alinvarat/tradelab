# Prediction markets, sports betting edges, retail FX/futures: what works for a ~150 USD account

Research date: 2026-11-23. Figures marked **[unverified]** come from secondary or press summaries that I did not check against the primary document. Most numbers here come from search-result summaries, not full-text reads, unless noted.

## 1. Polymarket and Kalshi: calibration, biases, documented edges, share of profitable wallets, bot dominance

### Takeaway
Prediction markets are reasonably well calibrated overall, but they show a favourite-longshot bias: longshots are overpriced, and takers lose more than makers. Roughly 70-84% of Polymarket wallets lose money, and a tiny fraction of wallets, likely automated, take most of the profit. Arbitrage edges exist (about $40M extracted on Polymarket from Apr 2024 to Apr 2025), but they are captured by a few high-volume wallets at 1-5% per trade. For Thailand, Polymarket is "close-only" and Thai police have flagged it as illegal gambling.

### Cited Findings
**Calibration / accuracy**
- Princeton thesis (2026): 188,509 resolved binary Polymarket markets and 1,875,570 daily price observations, Nov 2022 to Dec 2025. Brier Skill Score 0.398 overall. By domain it ranges from 0.264 in Sports (worst) to 0.565 in Politics (best). — [Princeton thesis](https://theses-dissertations.princeton.edu/entities/publication/d5708372-5ea3-4252-b669-7f9cee07387c)
- Clinton & Huang (Vanderbilt) studied Polymarket, Kalshi and PredictIt over the final 5 weeks of the 2024 US election. Polymarket was the least accurate of the three by their measure, and inefficiency increased in the final two weeks. Kalshi disputed the methodology, saying it is "almost perfectly" calibrated. **[paper figures unverified; press account]** — [DL News](https://dlnews.com/articles/markets/polymarket-kalshi-prediction-markets-not-so-reliable-says-study/)
- Le (2026, arXiv 2602.19520) used 292 million trades on Kalshi and Polymarket. Political markets are persistently underconfident, with prices compressed toward 50%. — [arXiv](https://arxiv.org/html/2602.19520v1)
- Ng, Peng, Tao & Zhou (2025, SSRN) studied common 2024-election contracts on Polymarket, Kalshi, PredictIt and Robinhood. Polymarket leads Kalshi in price discovery, especially when liquidity is high, which implies economically meaningful arbitrage opportunities. — [SSRN 5331995](https://papers.ssrn.com/abstract=5331995)

**Favourite-longshot bias**
- Snowberg & Wolfers, "Explaining the Favorite-Longshot Bias: Is it Risk-Love or Misperceptions?", *Journal of Political Economy* 118(4), Aug 2010, pp. 723-746. Data: 5.6M+ US horse-race starts, 1992-2001. The bias is better explained by misperception of probabilities (prospect-theory style) than by risk-love. — [NBER w15923](https://www.nber.org/papers/w15923); [RePEc](https://econpapers.repec.org/RePEc:ucp:jpolec:v:118:y:2010:i:4:p:723-746)
- Bürgi, Deng & Whelan, "Makers and Takers: The Economics of the Kalshi Prediction Market" (UCD WP25/19, July 2025; 2026 revision as GWU 2026-001 / CEPR DP 20631):
  - Sample of 300,000+ Kalshi contracts with a systematic favourite-longshot bias: a 10-cent contract wins less than 10% of the time.
  - Average return across all contracts is about -22% after fees in the 2025 version, and about -20% (described as before fees) in the 2026 version. **[versions conflict]**
  - Takers lose far more on longshots than makers do.
  - There is some evidence the bias is shrinking over time.
  - The bias was not generally found in older prediction-market studies.
  - Sources: [UCD WP2025_19](https://www.ucd.ie/economics/t4media/WP2025_19.pdf); [CESifo](https://www.ifo.de/en/cesifo/publications/2026/working-paper/makers-and-takers-economics-kalshi-prediction-market); [GWU PDF](https://www2.gwu.edu/~forcpgm/2026-001.pdf)

**"Buy 95-99 cent" strategy**
- I found no rigorous peer-reviewed test. A blog analysis of ~1,800 resolved Polymarket sports markets found that markets priced around 95-97% resolved for the favourite only 93.6% of the time, which suggests slight overconfidence and argues against this strategy in sports. **[blog, unverified]** — [dev.to/edgelab](https://dev.to/edgelab/the-polymarket-paradox-what-2490-sports-prediction-markets-reveal-about-bookmaker-edge-akc)
- A Bitquery audit of US primaries (via CryptoSlate) found the favourite won 238/273 races, but $1 on each favourite lost 4 cents overall. Favourites at 90c+ won 177/182. **[secondary, unverified]** — [CryptoSlate](https://cryptoslate.com/?p=570285)
- Break-even arithmetic: with a 2% round-trip fee, a 95c entry needs about a 96.9% hit rate and a 97c entry about 98.9% (the author's fee assumption). — [teletype.in analysis](https://teletype.in/@russianpolymarket/sniper_35)

**Arbitrage**
- Saguillo, Ghafouri, Kiffer & Suarez-Tangil, "Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets" (arXiv Aug 2025; AFT 2025 / LIPIcs vol. 354):
  - On-chain Polymarket data from Apr 2024 to Apr 2025, about 86M bets, with an estimated ~$40M realised arbitrage profit.
  - Two types: market-rebalancing arbitrage within one market, and combinatorial arbitrage across related markets.
  - Per DL News, the top 3 wallets made about $4.2M, and most individual arbitrage trades earned about 1-5%.
  - Sources: [arXiv 2508.03474](https://arxiv.org/abs/2508.03474); [Dagstuhl AFT 2025](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.AFT.2025.27); [DL News](https://dlnews.com/articles/markets/polymarket-users-lost-millions-of-dollars-to-bot-like-bettors-over-the-past-year/); [Decrypt](https://decrypt.co/339958/40-million-free-money-glitch-crypto-prediction-markets)
- Cross-platform (Polymarket vs Kalshi) gaps persist because of structural limits to enforceability (different resolution rules, settlement, access), not informational disagreement. — [arXiv 2601.01706](https://arxiv.org/html/2601.01706v1)
- Practitioner guides report 5-10% discrepancies on overlapping 2024 markets **[anecdotal]**. They note that bots now close gaps faster, that capital must be pre-funded on both venues, and that Kalshi's fees are variable. — [tech-insider guide](https://tech-insider.org/prediction-markets/prediction-market-arbitrage/); [dev.to/polytrage](https://dev.to/polytrage/why-the-same-market-trades-at-different-prices-on-polymarket-and-kalshi-4l84)

**Share of profitable wallets / concentration / bots**
- Bloomberg News analysis (reported 29 Apr 2026) covered every Polymarket wallet active since the start of 2025:
  - 100,000+ wallets lost at least $1,000, nearly double the number that gained $1,000+.
  - Profits went mainly to a small group of high-volume traders "likely running automated strategies".
  - Excluding the top winners, the remaining users had a combined net loss of $131M.
  - The article gives no exact bot share and no total wallet count.
  - Source: [Finance Magnates summary of Bloomberg](https://www.financemagnates.com/fintech/100000-polymarket-wallets-lost-at-least-1000-bloomberg-analysis-shows/); [BeInCrypto](https://beincrypto.com/prediction-market-retail-traders-losses-bloomberg/)
- DeFi Oasis analysed ~1.7M addresses: about 70% had realised losses, and fewer than 0.04% of addresses captured more than 70% of total profits ($3.7B). **[secondary]** — [Yahoo Finance](https://finance.yahoo.com/news/70-polymarket-traders-lost-money-192327162.html)
- Sergeenkov analysed ~2.5M wallets with data as of 1 Apr 2026: 84.1% unprofitable, and only 840 wallets (0.033%) had more than $100k profit. **[secondary]** — [KuCoin news](https://www.kucoin.com/news/flash/84-of-polymarket-traders-are-losing-money-0-033-capture-majority-profits); [TechFlow](https://www.techflowpost.com/en-US/article/31018)
- An academic study through Mar 2026 found 68.8% of Polymarket users lost money, and 1% of traders accounted for 76.5% of profits. A Motley Fool analysis (2025, ~313k wallets) found about 17% profitable. **[both via search summary; not opened]** — [WFTV/"Do stocks beat prediction markets"](https://www.wftv.com/news/do-stocks-beat/7ZTJXTK3GUYWDNEOPW6647EITY/); [WSJ via Yahoo](https://finance.yahoo.com/markets/options/articles/prediction-markets-hit-milestones-most-042140220.html)

**Thailand availability**
- Polymarket's official geoblock docs list Thailand as **close-only**: users can close existing positions but cannot open new ones. — [Polymarket docs](https://docs.polymarket.com/api-reference/geoblock.md); [Polymarket help](https://help.polymarket.com/en/articles/13364163-geographic-restrictions)
- Thai police flagged Polymarket in Jan 2025 as showing signs of illegal online gambling, and a ban was proposed. — [The Block](https://www.theblock.co/post/334678/thailand-proposes-banning-polymarket-amid-online-gambling-crackdown)

### Inferences
- With a 150 USD account, the documented edges are inaccessible or unprofitable in practice:
  - Arbitrage is captured by a few automated wallets at 1-5% per trade. 1-5% of $150 is $1.5-7.5 per opportunity, before gas, bridging and fees.
  - The structural edge (favourite-longshot bias) favours makers and favourites. Its practical form is "provide liquidity, avoid buying longshots as a taker", which is a small, slow edge.
- The favourite-longshot bias implies buying longshots is the worst retail habit. Buying 95-99c favourites is not a proven edge: the evidence is mixed and the payoff is asymmetric (a single loss wipes out about 19-99 wins).
- A Thai resident cannot legally or technically open new Polymarket positions. Kalshi is a US CFTC-regulated exchange and its availability to Thai residents was not verified (see Gaps).

### Gaps
- Kalshi's eligibility for non-US/Thai residents was not checked.
- I did not read the full Kalshi paper's tables by price bucket (the VoxEU page returned 403).
- I found no rigorous study isolating the returns of a 95-99c strategy after current Polymarket fees.
- The exact Polymarket fee schedule post-2025 was not verified (one source says fees "began" after 2025).
- The "Bloomberg analysis of 2 million addresses" as worded in the brief: the Bloomberg piece I found counts wallets since Jan 2025 but gives no total. The 1.7M and 2.5M counts come from other analysts.

## 2. Sports betting: arbitrage/value betting, CLV, limiting of winners, pro ROI, exchange commission

### Takeaway
Value betting against soft bookmakers, using sharp (Pinnacle) prices as "true" odds, is documented to be profitable: Kaunitz et al. made about 5.5-8.5% ROI. Bookmakers then restrict winning accounts, which caps scalability. Exchanges don't limit winners but take about 2-5% of net winnings. In Thailand, gambling (including online) is illegal outside authorised channels.

### Cited Findings
- Kaunitz, Zhong & Kreiner, "Beating the bookies with their own numbers - and how the online sports betting market is rigged" (arXiv 1710.02824, Oct 2017):
  - Method: use the bookmakers' consensus/closing-implied probabilities to spot mispriced odds at individual bookies (football).
  - Paper trading: 407 bets of $50 returned $1,128.50 (5.5%).
  - Real money: 256 bets of $50 over 5 months returned $957.50 (8.5%).
  - Bookmakers limited stakes, required "manual inspection", or cut maximum stakes to as little as $1.25.
  - Sources: [arXiv](https://pdf.arxiv.org/pdf/1710.02824); [MIT Technology Review, 19 Oct 2017](https://www.technologyreview.com/2017/10/19/67760/the-secret-betting-strategy-that-beats-online-bookmakers/); [code](https://github.com/Lisandro79/BeatTheBookie)
- Joseph Buchdahl treats Pinnacle's closing odds as the most accurate benchmark ("Wisdom of the Pinnacle crowd"), and argues that Pinnacle's pre-closing prices can locate value at other books. **[mirror site of Buchdahl's writing]** — [Buchdahl on CLV (mirror)](https://pod-d614f9k2t-pod-team.vercel.app/blog/closing-line-value--clv-demystified-by-expert-joseph-buchdahl)
- A backtest on football-data.co.uk data (22 European leagues) using Pinnacle pre-closing odds as "ground truth" would have been profitable. **[Substack analysis]** — [networked.substack](https://networked.substack.com/p/a-view-from-the-pinnacle)
- Attributed to Buchdahl: proving profit from results alone can take several thousand bets, whereas a consistent ~5% edge over the close might show significance in about 50 bets. **[unverified against original]** — [same mirror](https://pod-d614f9k2t-pod-team.vercel.app/blog/closing-line-value--clv-demystified-by-expert-joseph-buchdahl)
- Karlwhelan.com also has a critical piece, "The Truth about Closing Line Value" (not read). — [Karl Whelan](https://www.karlwhelan.com/?p=2595)
- Betfair Exchange's Market Base Rate is 5% of net winnings on most sport markets (NRL 10%). Some accounts were raised to 6.5% (undated forum letter). Smarkets and Matchbook charge a flat 2% in the UK. — [Betfair Data Scientists](https://betfair-datascientists.github.io/wagering/commission); [Oddschecker](https://www.oddschecker.com/best-betting-exchanges); [SBC News, 7 Aug 2019 (Matchbook 2%)](https://sbcnews.co.uk/europe/2019/08/07/matchbook-sticks-at-2-commission-on-all-sports/)
- Thailand law:
  - Gambling is illegal or restricted under the Gambling Act B.E. 2478 (1935). — [Chambers 2023 Thailand guide](https://chambers.com/downloads/gpg/750/037_thailand.pdf)
  - A proposed amendment would make online gambling unlawful unless authorised, with 1-3 years' prison for participants. — [Tilleke & Gibbins](https://www.tilleke.com/insights/thailand-seeks-comments-on-draft-amendment-to-permit-online-gambling/)
  - A later draft Gambling Act would reach offshore operators targeting Thais, with player fines up to THB 20,000 and public comments due 9 Dec 2026. **[draft; enactment status unverified; the two Tilleke drafts conflict]** — [Tilleke & Gibbins](https://www.tilleke.com/insights/thailands-draft-gambling-act-sets-strict-rules-for-online-gambling)

### Inferences
- Of all the approaches reviewed, value betting is the clearest documented retail edge (about 5-8% ROI on turnover). But ROI on turnover is not return on capital, and it decays with account limiting.
- On $150 with $5-10 stakes:
  - Expected profit is a few dollars per hundred bets.
  - Variance dominates, since thousands of bets are needed to confirm an edge from results alone.
  - Soft books may limit the account once it wins.
- Pure arbitrage has the same limiting problem, plus multi-account capital fragmentation, and $150 split across books makes this nearly impossible.
- A 2-5% exchange commission on net winnings consumes a large share of a 2-5% edge.
- For a Thai resident, offshore sportsbooks and exchanges are illegal gambling under Thai law (participants are also liable), so legal access is effectively nil.

### Gaps
- I found no academic study quantifying how fast bookmakers limit winners (the share of accounts limited, time-to-limit).
- I found no reliable data on the "typical ROI of professional bettors". Industry folklore says about 2-5% on turnover, but I found no source, so it is not cited.
- I found no independent replication of Kaunitz et al. after 2020.
- I found no peer-reviewed proof that CLV predicts profit. Mostly vendor or secondary material.

## 3. Retail forex: share of profitable accounts, ESMA CFD loss rates, carry and momentum evidence, post-2020

### Takeaway
Regulated disclosures consistently show most retail FX/CFD accounts lose money:
- US: roughly 30-35% profitable at FOREX.com, and about 46-54% at Interactive Brokers.
- EU: 74-89% of CFD accounts lose.

Academic FX factor premia (carry, momentum) exist historically but are risk compensation that crashes in volatility spikes, and G10 carry has been weak for about 15 years. In Thailand, retail forex with unlicensed brokers is illegal, and the BOT has never licensed it.

### Cited Findings
- FOREX.com (US, NFA-required disclosure, non-discretionary accounts) — [FOREX.com disclosures](https://www.forex.com/en-us/terms-and-policies/disclosures-and-risk-warning):

  | Quarter | Profitable |
  |---|---|
  | Q3 2025 (40,232 active accounts) | 34.25% |
  | Q4 2025 | 31.72% |
  | Q1 2026 | 30.91% |
  | Q2 2026 | 32.56% |

- Interactive Brokers retail forex (NFA disclosure; profitability includes commissions) — [IBKR disclosure](https://www.interactivebrokers.com/en/general/about/performanceCustomerForex.php):

  | Quarter | Profitable |
  |---|---|
  | Q1 2025 | 47.16% |
  | Q2 2025 | 47.09% |
  | Q3 2025 | 45.92% |
  | Q4 2025 | 53.91% |

  **[IBKR's clientele is skewed toward professionals and hedgers]**
- US retail forex deposits stalled near $462-470M (2025-26), a small and shrinking market. — [Finance Magnates](https://www.financemagnates.com/forex/analysis/us-retail-forex-deposits-fall-to-462-million-the-lowest-since-at-least-2023/)
- ESMA (decision agreed 23 Mar 2018, MiFIR Art. 40) — [ESMA press release](https://www.esma.europa.eu/node/84933); [ESMA notice](https://www.esma.europa.eu/sites/default/files/library/esma35-43-1135_notice_of_pi_decisions_on_cfds_and_binary_options.pdf):
  - National regulators found 74-89% of retail CFD accounts lose money, with average losses of €1,600-29,000 per investor.
  - Measures: leverage caps of 30:1 on major FX pairs and 20:1 on non-majors, gold and major indices; negative balance protection; a mandatory firm-specific "% of accounts lose money" warning.
- Central Bank of Ireland (2015): 75% of retail CFD clients lost money in 2013-14. — [Irish Times](https://www.irishtimes.com/business/personal-finance/europe-restricts-leverage-on-cfds-to-protect-retail-investors-1.3441764)
- Menkhoff, Sarno, Schmeling & Schrimpf, "Carry Trades and Global Foreign Exchange Volatility", *Journal of Finance* 67(2), 2012, pp. 681-718. High-yield currencies do badly when global FX volatility spikes. A global FX volatility factor explains over 90% of the cross-sectional excess returns of 5 carry portfolios, so carry is compensation for crash/volatility risk. — [City Research Online](https://openaccess.city.ac.uk/id/eprint/3391/); [VoxEU](https://voxeu.org/article/risk-carry-trades)
- GMO ("Let's Not Get Carried Away", ~2023-24) — [GMO](https://www.gmo.com/americas/research-library/lets-not-get-carried-away_insights/):
  - Carry as a strategy has performed "somewhat poorly over the last 15 years".
  - The G10 yield pickup recovered to pre-pandemic levels but remains far below the era when carry was reliable.
  - High-yielders are now the expensive currencies (a valuation headwind).
  - This is an asset manager's view.
- G10 carry index had its "biggest returns since 2016" in 2021, in a low-volatility environment. **[Bloomberg headline; details truncated]** — [BloombergQuint](https://www.bloombergquint.com/amp/onweb/carry-trade-comes-surging-back-with-biggest-returns-since-2016)
- Academic evidence notes a substantial decline in G10 currency strategy returns, while emerging-market carry stayed strong and G10 momentum levelled off from the early 2000s. **[paper date unclear]** — [Chernov et al. paper (EPFL)](https://memento.epfl.ch/public/upload/files/Chernovpaper.pdf)
- Thailand (sources: [Thairath, Jun 2026](https://en.thairath.co.th/news/governmentpolicy/2941760); [Nation Thailand](https://www.nationthailand.com/business/banking-finance/40067830); [Kaohoon](https://www.kaohooninternational.com/markets/516552); [Nation 2022 (SEC)](https://nationthailand.com/thailand/economy/40020204)):
  - The Bank of Thailand says it has never licensed retail forex trading businesses.
  - Unauthorised forex is illegal under the Exchange Control Act B.E. 2485.
  - In 2026 the BOT warned payment gateways not to facilitate unlicensed forex platforms.
  - The SEC (2022) said no FX rights are granted to non-banks or non-finance companies.
  - Forex-3D scheme: 9,824+ victims and losses above THB 2.49B.

### Inferences
- About 2/3 of retail FX accounts at a mainstream US retail broker lose each quarter, even after US leverage limits. Small accounts are likely to do worse, since per-trade costs and spreads are a larger share and position sizing is coarse. This is an inference; disclosures are not broken out by account size.
- Carry and momentum are institutional, diversified, low-Sharpe premia with crash risk. On $150 at a retail broker:
  - Spreads, swap markups and minimum lot sizes (0.01 lot is about $1,000 notional) make a diversified carry or momentum portfolio impractical.
  - A single-pair carry trade is concentrated crash exposure.
- For a Thai resident, retail FX via offshore brokers is not legal under BOT rules. The only legal route is bank FX, which isn't a leveraged trading venue.

### Gaps
- OANDA's 2025-26 quarterly profitability figures were not found.
- I did not find the CFTC/NFA aggregate across all US FCMs/RFEDs.
- I did not verify the currency momentum paper (Menkhoff et al., JFE 2012) or its return figures, nor current FX momentum performance after 2020.
- I found no clean 2020-2026 return series for a G10 carry index.
- I found no data splitting profitability by account size.

## 4. Futures for small accounts: micro futures, CTA/trend-following 2010-2026, is 150 USD enough?

### Takeaway
No. A single Micro E-mini S&P 500 (MES) contract needs roughly $2,300-2,500 in exchange margin to hold overnight. Brokers' $50-125 intraday margins mean $150 can be wiped out by a roughly 20-30 point S&P move. Trend-following CTAs had a bad 2025 (SG CTA Index down more than 8% YTD by late May 2025, and one of their worst stretches on record), ending roughly flat to slightly positive with wide dispersion.

### Cited Findings
- MES contract and margins:
  - The contract has a $5 multiplier, about $25k notional at S&P 5,000. — [NinjaTrader ES vs MES](https://www.ninjatrader.com/futures/blogs/es-vs-mes-futures/)
  - Exchange initial margin is about $2,300-2,500 per CME article (2026). — [CME Group 2026](https://www.cmegroup.com/articles/2026/the-goldilocks-of-equity-futures-why-contract-size-matters-in-todays-markets.html)
  - Broker day-trade margins: StoneX $125 per MES contract; NinjaTrader advertises $50 intraday micro margins. — [StoneX](https://futures.stonex.com/day-trading-margins); [NinjaTrader](https://ninjatrader.com/margin-details/?symbol=MES)
  - Webull lists a $100 minimum equity requirement (a broker rule, not exchange margin). — [Webull](https://www.webull.com/blog/334-Micro-E-Mini-Futures-A-Complete-Guide-to-Contract-Specs-Margins-and-Trading)
- CTA / trend performance:
  - The SG CTA Index was down more than 8% YTD by late May 2025. Large trend-followers ended a four-month losing streak in June 2025, one of their worst periods on record. — [Alternatives Watch, 2 Jun 2025](https://www.alternativeswatch.com/2025/06/02/trend-following-hedge-funds-endure-more-pain-societe-generale-indices/); [Alternatives Watch, 2 Sep 2025](https://www.alternativeswatch.com/2025/09/02/ctas-trend-following-hedge-funds-rebound-h1-rout-societe-generale-indices/)
  - SG Trend Index: +1.37% in Nov 2025 (10 largest trend CTAs, equal-weighted, inception 1 Jan 2000). — [The Full FX](https://thefullfx.com/ctas-end-2025-on-a-positive-note/); [Transtrend index description](https://transtrend.com/en/strategies/dtp/description-indices/)
  - Barclay CTA Index: provisional +3.16% for 2025. — [The Full FX](https://thefullfx.com/ctas-end-2025-on-a-positive-note/)
  - 2025 CTA performance "splintered", ranging from double-digit gains to double-digit losses. — [Institutional Investor, Jan 2026](https://www.institutionalinvestor.com/article/premium/cta-performance-splinters-late-surge-lifts-some-not-all)
  - Deep dives on trend-following dispersion and the long-run record are available. — [Man Group](https://www.man.com/insights/deep-dive-trend-following); [AIMA](https://www.aima.org/journal/aima-journal---edition-144/article/a-trend-following-deep-dive-the-dynamics-of-dispersion.html)

### Inferences
- With $150, futures trading is limited to intraday micro positions:
  - One MES point is $5, so a 30-point move (about 0.5% of the index) is $150.
  - This is not a diversified trend-following program, which needs many markets and the ability to hold through drawdowns. Professional CTAs run multi-asset portfolios with millions in capital.
- Retail access to trend-following at $150 would only be via a managed-futures ETF or fund, and those may not be available to Thai residents. Not verified.
- Trend-following has delivered long-run diversification but a weak 2010s and a volatile 2025. It is not a reliable small-account profit engine.

### Gaps
- I did not obtain full-year SG Trend Index returns for 2010-2024 (notable years such as 2014 and 2022 were strong, but this is unsourced here).
- No 2025 CME official MES maintenance margin figure was found; the CME 2026 figure is from an article.
- Thai residents' access to US futures brokers and its legal status (Thai SEC/TFEX rules) was not verified. TFEX (the Thai futures exchange) micro contracts were not researched.
