# Outsourced, AI and social approaches for retail traders: measured outcomes (2020-2026)

Research date: 2026-11-23. Evidence-quality labels: **A** = peer-reviewed / court record / regulator; **B** = preprint or reputable trade-press investigation with stated data; **C** = vendor/aggregator/blog, unverified.

## Copy trading (eToro CopyTrader / Popular Investors, Binance/Bybit copy leaderboards, academic studies)

### Takeaway
No independent, account-level evidence shows that the typical copier profits. The academic evidence (lab experiment, peer-reviewed in Management Science) shows copy trading raises risk-taking and lowers ex-ante welfare. Crypto copy leaderboards have heavy survivorship bias: most portfolios close within months and drop off the board. eToro publishes figures only for the traders being copied (leaders), not aggregate copier P&L.

### Cited Findings
- Apesteguia, Oechssler and Weidenholzer, "Copy Trading" (Management Science, DOI 10.1287/mnsc.2019.3508, published 2020; BSE Working Paper 1048, summarized Nov 26, 2018). Lab experiment with BASELINE / INFO / COPY treatments. Just showing others' strategies and success increased risk-taking. About one third of subjects chose to copy, mostly copying the traders who had taken the riskiest assets, which raised risk-taking further. The authors conclude copy trading reduces ex-ante welfare. Evidence quality A, but it is a lab study, not platform data, and the summary page does not give the sample size. — [BSE Focus](https://focus.bse.eu/copy-trading-risk-taking/); [Management Science](https://pubsonline.informs.org/doi/pdf/10.1287/mnsc.2019.3508)
- Pelster and Hofmann (2018), eToro data: losses tend to be larger on copied trades when returns are negative (secondary summary, quality B/C). — [Wikipedia: Copy trading](https://en.wikipedia.com/wiki/Copy_trading)
- Pelster and Romero Gonzalez used eToro's copy feature to study social interaction and behavioural biases (risk-taking after gains and losses). The excerpt does not report copier profit rates. — [VoxEU PDF](https://voxeu.org/system/files/2023-02/Social%20media%20interactions%20and%20biases%20in%20investment%20decisions.pdf)
- I found no Pelster and Breitmayer paper that reports the share of eToro copiers who profit. Breitmayer, Massari and Pelster (2019), "Swarm intelligence? Stock opinions of the crowd and stock returns," is about crowd stock opinions, not copiers. — [search results; see Gaps]
- eToro's own figures (vendor, quality C): in 2020 eToro said 95% of its Popular Investors were profitable and 77% beat the S&P 500. A pre-2015 sample of 134 million copied trades was about 80% profitable. Both are about leaders or individual trades, not copier accounts, and the leader statistics are subject to selection, since the Popular Investor status is earned by performance. — [eToro 2020 blog](https://www.etoro.com/news-and-analysis/copytrader/goodbye-2020-meet-our-most-consistently-profitable-investors-who-have-finished-over-3-years-in-profit); [Which?](https://www.which.co.uk/news/article/will-copying-someone-elses-investments-make-you-better-off-advNh8r7dYMT)
- Which? (UK consumer body): Popular Investors are not professionals and are as liable as other retail investors to make common mistakes. — [Which?](https://www.which.co.uk/news/article/will-copying-someone-elses-investments-make-you-better-off-advNh8r7dYMT)
- An MIT-linked study by Yaniv Altshuler reportedly found guided copiers did 6-10% better than manual traders on eToro. This is an older figure from a secondary source and may be eToro-affiliated (quality C). — [Wikipedia: Copy trading](https://en.wikipedia.com/wiki/Copy_trading)
- Binance copy-trading survivorship: an independent author who scraped Binance copy portfolios found about 75% closed within four months. Closed portfolios disappear from the leaderboard, so the visible board overstates performance (quality B/C, one author, earlier period). — [Habr](https://habr.com/en/articles/808639)
- A 90-day study across Binance, Bybit and MEXC is widely cited: 97% of lead traders were profitable on their own positions, but only about 43.6% produced positive returns for copiers. I could not locate the original study. It appears only in vendor blogs, including a competing exchange (KuCoin) and Arkham (quality C). — [KuCoin blog](https://www.kucoin.com/blog/is-crypto-copytrading-profitable-in-2026); [Arkham](https://info.arkm.com/research/crypto-copy-trading-what-is-it-and-how-to-do-it)
- Leaders can earn through profit share, subscriptions and volume fees while followers lose, so incentives favour risky, high-variance leaders. This is commentary, quality C. — [BrokerListings](https://brokerlistings.com/research-hub/copy-trading-blow-ups)
- Binance's leaderboard filters (ROI, max drawdown, Sharpe, AUM) are computed only on portfolios that are still live. — [Binance blog](https://www.binance.com/blog/futures/copy-trading-essential-criteria-for-selecting-lead-traders-5061215295703009149)

### Inferences
- The only rigorous causal evidence (the Management Science lab study) points to more risk-taking, not better outcomes. Platform statistics describe survivors and leaders, not followers.
- Can a 150 USD account use it? Technically often yes. Crypto exchanges and eToro allow small copy allocations, but the minimum amounts were not verified here. Small accounts suffer more from proportional-sizing problems: a leader's small positions get rounded or skipped, and fixed fees weigh more. Copying leveraged crypto futures leaders on 150 USD carries a real chance of liquidation.

### Gaps
- No independent, account-level dataset of eToro copier profitability for 2020-2026 was found. eToro's regulatory "X% of retail CFD accounts lose money" warning was not retrieved in this session.
- No primary source was found for the "43.6% of leaders profitable for followers" study.
- Pelster and Breitmayer on eToro: no specific copier-profit statistic was found under that author pair.
- Exact minimum copy amounts (eToro, Binance, Bybit) were not verified.

## Paid signal groups / Telegram signals and pump-and-dump groups

### Takeaway
Academic studies of Telegram and Discord pump groups (2018-2019 data) show systematic, recurring manipulation. Organizers and early insiders profit, while late joiners, typically the paying or "VIP-tier-below" members and outside buyers, absorb losses. I found no rigorous study showing that paid Telegram trading-signal channels beat the market net of costs.

### Cited Findings
- Xu and Livshits, "The Anatomy of a Cryptocurrency Pump-and-Dump Scheme" (USENIX Security 2019; arXiv 1811.10109). Identified 412 pump events across 358 Telegram channels over about 8 months (2018-2019). The authors built a model to predict target coins. Their simulated strategy reported returns as high as 80% over three weeks, and a citing paper notes about 60% "even with caution." These are returns from front-running pumps with a prediction model, not returns to group members (quality A, though the strategy returns are backtests). — [arXiv 1811.10109](https://arxiv.org/pdf/1811.10109v1); [EPFL copy](https://memento.epfl.ch/public/upload/files/Xupaper.pdf)
- Hamrick et al. (2018 data): 952 pumps on Discord and 2,469 on Telegram over six months. Returns for "transparent" pumps did not decline over time, while returns for "obscured" pump groups declined significantly. Obscured groups often pumped the same coins repeatedly. Quality A/B. The attribution comes from search snippets, so check the URL before quoting. — [UCL / SSRN PDF](https://discovery.ucl.ac.uk/10133232/1/SSRN-id3303365%20%281%29.pdf); [NSF PAR](https://par.nsf.gov/servlets/purl/10251729)
- Press coverage of a study of more than 500 pump schemes: in 229 pumps where groups announced a target, the average target return was 212%. These are organizer targets, not realized returns. — [The Block](https://www.theblock.co/post/2209/researchers-study-over-500-cryptocurrency-pump-and-dump-schemes)
- "The Doge of Wall Street" (La Morgia et al., arXiv 2105.00733) analyses and detects pump-and-dump events organized in Telegram groups (details not extracted in this session). — [arXiv](https://arxiv.org/html/2105.00733v2)
- CFTC customer advisory (Jan 25, 2024): fraudsters tout "trade signal strategies" and AI bots promising unreasonably high or guaranteed returns. It advises against trusting social-media influencers and strangers online. Quality A. — [CFTC advisory](https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/aitradingbots.html)

### Inferences
- In pump groups, the structure itself guarantees that most participants lose: insiders buy first, and members are the exit liquidity. With 150 USD, a member arrives after the price has already moved.
- Paid signal channels have unaudited track records that are typically survivor-selected (deleted losing calls, multiple channels). Treat them as vendor claims.

### Gaps
- I found no peer-reviewed 2020-2026 study measuring accuracy or net returns of paid forex or crypto Telegram signal channels. Newer post-2021 pump-group data was not reviewed in this session.

## Prop firms (challenge pass rates, payouts, collapses)

### Takeaway
The best-quality dataset (FPFX Technology, about 300,000 accounts from about 100,000 traders at 10 firms, reported by Finance Magnates) shows about 14% pass the evaluation and about 7% of all traders ever receive a payout. The average payout was about 4% of the plan size. FTMO does not publish an official pass rate. The industry is fee-driven, and in 2024 many firms closed after the MetaQuotes license crackdown. The MyForexFunds case ended with the CFTC's suit dismissed and the CFTC sanctioned (May 2025).

### Cited Findings
- FPFX Tech data (Finance Magnates exclusive, 2024): more than 300,000 accounts and about 100,000 traders across 10 prop firms. About 14% passed evaluations. About 45% of funded traders got a payout, which is about 7% of all traders. The average payout was about 4% of the plan size. Across two releases the figures ranged from 12-14% passing and 7-8% reaching a payout. Caveats: it is unclear whether the 14% is per trader or per account, and whether fee refunds are included. Quality B. — [Finance Magnates](https://www.financemagnates.com/forex/exclusive-only-7-of-300000-prop-trading-accounts-achieved-payouts/); [TradeInformer](https://tradeinformer.com/prop-weekly/what-ftmo-tells-us-about-prop-firm-finances)
- FTMO: no first-party pass-rate disclosure was found. Third-party estimates put the combined two-phase pass rate at roughly 10-12% (quality C). FTMO's parent OMHC reportedly had about 329 million USD of 2024 revenue, up 53% year on year (trade press, B). — [TradeInformer: How FTMO makes money](https://tradeinformer.com/prop-weekly/how-does-ftmo-make-money); [Traders Second Brain](https://traderssecondbrain.com/guides/prop-firm-pass-rate)
- Aggregator (2025 "industry disclosures"): about 45% of funded traders receive at least one payout, and about 7% of all challenge buyers are ever paid. This is consistent with FPFX (quality C). — [Track360](https://track360.io/blog/prop-trading-industry-statistics-2026)
- MyForexFunds (Traders Global Group): On May 13, 2025, Judge Edward S. Kiel (D.N.J.) dismissed the case with prejudice and sanctioned the CFTC, awarding attorney's fees, after a special master found misleading statements by the CFTC. The CFTC put four lawyers and one investigator on leave. Assets were ordered returned. As of Nov 2025, MFF was analysing data before any relaunch or payouts. Quality A/B. — [Finance Magnates](https://www.financemagnates.com/forex/my-forex-funds-parent-defeats-cftc-in-court-as-judge-imposes-sanctions/); [Willkie](https://complianceconcourse.willkie.com/articles/new-jersey-federal-judge-dismisses-forex-case-with-prejudice-and-awards-attorney-fees/); [Newswire](https://www.newswire.ca/news-releases/myforexfunds-reconnecting-with-users-after-u-s-ruling-and-ontario-court-action-867909786.html)
- True Forex Funds: MetaQuotes cut its MT4/MT5 licenses in Feb 2024. It attempted a relaunch on cTrader and Match-Trade, then declared insolvency and closed in May 2024. The number of unpaid traders is unverified: one blog estimates about 300 traders owed 1.2 million USD (quality C). — [FX News Group](https://fxnewsgroup.com/forex-news/retail-forex/exclusive-prop-trading-firm-true-forex-funds-shut-down-by-metaquotes-move/); [Finance Magnates](https://www.financemagnates.com/forex/after-the-my-forex-funds-fiasco-true-forex-funds-stalls-operations/); [FundedTrading blog](https://fundedtrading.com/true-forex-funds-shutdown/)
- Other 2024 closures include SurgeTrader, Funded Engineer, Propel Capital and the futures firm FundedSeat. A reported 80-100 prop firms closed in 2024 (count not verified). — [Finance Magnates: FundedSeat](https://www.financemagnates.com/forex/brokers/futures-prop-firm-fundedseat-closes-due-to-limitations-from-big-trading-platforms/); [FundedTrading](https://fundedtrading.com/true-forex-funds-shutdown/)

### Inferences
- Expected value per challenge fee is negative for most buyers. Only about 7% ever get paid, and the average payout is about 4% of the notional, so a 10k account averages about 400 USD among those who are paid. Counterparty risk (firm closure, payout denial) is material.
- A 150 USD budget can buy roughly one or two small challenges (for example 5k-10k accounts; fee levels not verified here). It is a lottery-like spend, not capital growth. Counterparty risk also matters: payouts depend on firm solvency, as the 2024 closures showed.

### Gaps
- No audited, firm-published pass or payout statistics from FTMO or others. Challenge fee levels for small accounts were not verified in this session.

## LLM and AI trading agents (Alpha Arena, StockBench, academic LLM studies, live funds, scams)

### Takeaway
Live, real-money LLM contests (Alpha Arena S1, Oct-Nov 2025, about 10,000 USD per model) produced mostly losses: four of six models finished in the red, there was heavy overtrading, and results were dominated by a few lucky directional bets over only about 17 days. Academic benchmarks (StockBench, 2025-2026) find most LLM agents do not beat buy-and-hold. The best evidence of LLM signal value, Lopez-Lira and Tang's news-headline study, shows predictability concentrated in small stocks and declining as LLM adoption rises. Regulators warn that "AI bot" marketing is a common fraud vector.

### Cited Findings
- Alpha Arena Season 1 (Nof1): about Oct 17/18 to Nov 3, 2025, crypto perpetuals on Hyperliquid, about 10,000 USD real capital per model, six models. Qwen 3 Max won with about +22%. DeepSeek was second or near the top. Four of six models lost money. GPT-5 and Gemini 2.5 Pro had drawdowns of more than 28% (some reports cite larger losses). There was heavy overtrading (one report: Qwen made 1,418 trades in a round). Quality B (press reporting of a public live leaderboard). Sample is n=6 models over about 2.5 weeks, which is statistically meaningless as evidence of skill. — [Forklog](https://forklog.com/en/four-out-of-six-ai-models-suffer-losses-in-trading-tournament/); [GN Crypto](https://www.gncrypto.news/news/qwen-wins-alpha-arena-season-1-with-22-percent-returns/); [Decrypt](https://decrypt.co/345006/ai-crypto-trading-showdown-deepseek-grok-winning-gemini-implodes)
- Alpha Arena Season 1.5 (US stocks: TSLA, NDX, NVDA, MSFT, AMZN, GOOGL; ended Dec 3, 2025): a "mystery model," later revealed as an xAI Grok 4.20 beta, won with a 12.11% aggregate return across four competition variants. GPT-5.1 was second and Gemini 3 third. Another report gives 22.38%, a discrepancy that is unexplained. Per-model losses were not verified. — [GN Crypto](https://www.gncrypto.news/news/mystery-model-alpha-arena-season-1-5-winner/); [Forklog](https://forklog.com/en/ai-model-grok-4-2-triumphs-in-trading-tournament/); [Aihola](https://aihola.com/article/grok-wins-alpha-arena-trading)
- StockBench (Chen et al., Tsinghua/BUPT, arXiv 2510.02209, Oct 2025, revised Mar 2026): daily buy/sell/hold decisions on DJIA stocks over a multi-month, contamination-free window. Models tested include GPT-5, Claude-4, Qwen3, Kimi-K2 and GLM-4.5. Most LLM agents fail to beat equal-weight buy-and-hold, though a few show higher returns or better risk control. Static finance-QA skill does not transfer to trading. Quality B (preprint). — [arXiv](https://arxiv.org/abs/2510.02209v1); [Project page](https://stockbench.github.io)
- Lopez-Lira and Tang, "Can ChatGPT Forecast Stock Price Movements?" (arXiv 2304.07619; v5 Sep 11, 2024; v6 Oct 28, 2025). Sample: 4,123 US common stocks, Oct 2021-May 2024, using headlines after the model's training cutoff. GPT-4 scores capture the initial reaction (about 90% portfolio-day hit rate, which is not tradable) and predict subsequent drift, mainly in small stocks and after negative news. v6 reports that strategy returns decline as LLM adoption rises, consistent with increased price efficiency. Magnitudes of the decline were not retrieved. Quality B (widely cited working paper). — [arXiv v6](https://arxiv.org/abs/2304.07619v6); [arXiv v5 PDF](https://arxiv.org/pdf/2304.07619v5.pdf)
- CFTC Customer Advisory "AI Won't Turn Trading Bots into Money Machines" (Jan 25, 2024): warns of AI bot and signal schemes promising guaranteed returns. It cites the Cornelius Steynberg case, which promised at least 10% a month from a "bot" for as little as 100 USD in bitcoin. Quality A. — [CFTC advisory](https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/aitradingbots.html)
- The SEC, NASAA and FINRA issued parallel investor alerts on AI investment fraud in Jan 2024. — [Orrick InfoBytes](https://infobytes.orrick.com/2024-02-02/securities-regulators-issue-guidance-and-rfc-ai-trading-scams/)

### Inferences
- There is no measured evidence that an off-the-shelf LLM agent produces a durable edge for retail traders. Contest winners over weeks are indistinguishable from luck, and benchmarks show underperformance versus buy-and-hold.
- A 150 USD account can run an LLM-driven bot (API costs are small), but fees and minimum order sizes, plus overtrading tendencies, would dominate. Any product selling "AI trading bot" returns to small retail accounts matches the regulator fraud profile.

### Gaps
- AI-Trader and FinRL contest results were not retrieved in this session (FinRL contests are mostly backtest or paper-trading). No audited live retail fund run purely by an LLM was found. Alpha Arena Season 2 or later results were not checked. Lopez-Lira v6 decay magnitudes were not retrieved.

## Social sentiment (WallStreetBets, Twitter/StockTwits, Google Trends)

### Takeaway
WallStreetBets due-diligence posts had measurable predictive value before the Jan 2021 GameStop squeeze: about 1.1% two-day announcement returns, gross of costs (RFS 2024). That value weakened after 2021. The famous Bollen (2011) "Twitter mood predicts the Dow" result failed replication, and the fund built on it closed.

### Cited Findings
- Bradley, Hanousek, Jame and Xiao, "Place Your Bets? The Value of Investment Research on Reddit's WallStreetBets" (Review of Financial Studies, 2024; working paper 2021). Before the GME squeeze, WSB due-diligence recommendations predicted returns and cash-flow news. Average buy recommendations earned about 1.1% two-day announcement returns. Returns are gross, and bid-ask spreads on WSB-recommended stocks can be high. The informativeness declined after the GME episode. Quality A. — [Kentucky Scholars](https://scholars.uky.edu/en/publications/place-your-bets-the-value-of-investment-research-on-reddits-walls/); [IDEAS](https://ideas.repec.org/p/men/wpaper/76_2021.html); [CXO Advisory](https://www.cxoadvisory.com/investing-expertise/wallstreetbets-contributors-and-users-skilled)
- A separate study of 5,050 WSB DD reports (2018-2021) found influence on stock prices, with predictive value declining since 2021 (quality B, secondary report). — [SuchScience](https://suchscience.net/?p=33659); [arXiv 2308.09485](https://ar5iv.labs.arxiv.org/html/2308.09485)
- Bollen, Mao and Zeng (2011, J. Computational Science; preprint 2010) claimed 87.6% accuracy in predicting the daily direction of the DJIA from Twitter mood. Lachanski and Pav (Econ Journal Watch, Sept 2017) could not reproduce it: the effect held in the original subsample but not in an extended sample, which is consistent with data snooping, and there was no out-of-sample predictive power. Derwent Capital Markets, a hedge fund set up to trade the strategy, closed in early 2012. Quality A. — [Econ Journal Watch](https://econjwatch.org/articles/shy-of-the-character-limit-twitter-mood-predicts-the-stock-market-revisited); [Bollen arXiv](https://arxiv.org/pdf/1010.3003)

### Inferences
- The social-sentiment edge is small (about 1% over days), gross of costs, decays once popular, and concentrates in high-spread names. For a 150 USD account, spreads and commissions on small-cap or meme stocks likely consume it. Following WSB "hype" (rather than DD quality) has no measured positive edge.

### Gaps
- StockTwits sentiment and Google Trends predictive-power studies for 2020-2026 were not retrieved in this session. The classic Preis, Moat and Stanley (2013) Google Trends result also has replication critiques, but these were not verified here.

## Robo / automated bot platforms (3Commas, Pionex grid bots)

### Takeaway
No independent, peer-reviewed measurement of retail grid-bot outcomes on Pionex or 3Commas was found. Theory and one preprint suggest a plain grid has roughly zero expected return before fees: it profits in ranges but accumulates losing inventory in trends. Evidence is mostly vendor or anecdotal.

### Cited Findings
- arXiv 2506.11921 (2025 preprint): under simple assumptions, a traditional grid strategy's expected return is essentially zero. A proposed dynamic grid, backtested on BTC and ETH minute data from Jan 2021 to Jul 2024, reportedly beat both the static grid and buy-and-hold. This is a backtest and not peer-reviewed. Quality B. — [arXiv](https://arxiv.org/abs/2506.11921v1)
- Stevens Institute FE800 student project (Bybit/Binance data): ML-tuned grids did not outperform traditional grids, while a hedged variant did better (quality C). — [Stevens FSC](https://fsc.stevens.edu/cryptocurrency-market-making-improving-grid-trading-strategies-in-bitcoin/)
- Practitioner examples (quality C): in a sideways period where BTC rose 0.66%, grids earned 0.84-1.71% depending on spacing. A six-month Gate.io BTC grid log concluded it was "not passive and not risk-free." — [Medium](https://medium.com/coinmonks/tuning-the-grid-increment-in-bitcoin-grid-trading-bot-to-significantly-increase-its-profitability-c077bca27b7a); [DEV](https://dev.to/joe_hans_6c082d6c1caf189f/i-ran-a-gateio-btc-grid-bot-for-6-months-real-returns-and-3-fatal-mistakes-2i1p)
- Pionex states its grid bots carry no extra fee beyond spot trading fees. Its claims of improved profitability for "AI" grids are vendor statements. — [Pionex FAQ](https://intercom.help/pionex/en/articles/15500905-grid-trading-bot-faq)
- 3Commas: in Dec 2022, leaked API keys led to unauthorized trades on users' exchange accounts. This is from memory and not verified in this session; see Gaps.

### Inferences
- Grid bots are a short-volatility, range-bound bet. With 150 USD split across many grid levels, each order is near exchange minimums, and fees take a large share of each small grid profit. Futures grids add liquidation risk. Usable, but there is no measured positive expectancy.

### Gaps
- No independent dataset of Pionex or 3Commas user outcomes. The 3Commas 2022 API-key leak was not verified with a source in this session. Exchange minimum order sizes per grid level were not verified.
