# Crypto Market-Structure Edges: Can a ~150 USD Retail Trader Capture Them?

Research date: 2026-11-23. Source-type tags: [ACADEMIC] = peer-reviewed or arXiv/NBER/BIS working paper; [DATA-FIRM] = research desk at a data vendor, market maker or exchange (Kaiko, Talos, Keyrock, The Tie, Coinbase, Glassnode, Sygnum); [VENDOR-BLOG] = vendor marketing or self-interested research; [PRESS] = news coverage, often secondhand.

## Funding-rate and basis carry (spot long + perp/futures short), 2020-2026

### Takeaway
Carry was large during booms. A BIS paper puts the average above 10%/yr with peaks up to 60%, and BTC funding/basis ran 20-40% annualized in early 2024. It then compressed to roughly 3-5% in 2026, at or below T-bill yields, with a 67-day run of negative 30-day-average funding into May 2026. Ethena's sUSDe, the packaged version, paid about 5% in Oct 2026. At 150 USD the dollar yield is tiny: 5-10% is about 7.5-15 USD/yr before fees. The return is also small compared with exchange-failure, depeg and liquidation risk on the short leg.

### Cited Findings
- [ACADEMIC] Schmeling, Schrimpf & Todorov, "Crypto carry," BIS Working Paper 1087 (4 Apr 2023). BTC/ETH futures carry averages above 10%/yr and can reach up to 60%/yr. It is driven by a "convenience yield" from trend-chasing small investors seeking leveraged upside and by scarce arbitrage capital, not by interest-rate differentials. High carry predicts future price crashes, and arbitrage is risky because margin spikes and liquidations occur during drawdowns. — [BIS WP 1087](https://www.bis.org/publ/work1087.htm)
- [DATA-FIRM] Talos (page "last reviewed" 26 Oct 2026, cites Nov 2026 data). BTC perp funding and 30-day futures basis peaked at 20-40% annualized in early 2024, compressed through 2025-26, and settled around 3-5% in 2026, briefly negative in Q2 2026. The top-10 crypto perps paid about 3% annualized in 2026 vs about 11% for the top-10 equity perps, so basis capital is rotating into stock perps. Talos gives no explicit figure for 2025 and no ETH figures. — [Talos](https://www.talos.com/insights/following-the-funding-the-shift-towards-the-equity-basis-trade)
- [DATA-FIRM via PRESS] Sygnum (Nov 2026): the 30-day average BTC funding rate stayed negative for 67 consecutive days until May 2026, and the CME BTC annualized basis fell to about 3% in Aug 2026, below the 3.8% 2-yr Treasury yield. Coinbase (2 Nov 2026 report): BTC funding rose from about 4% annualized in early Oct 2026 to an 8.9% average in the last week of October. Sygnum forecasts carry beating T-bills in 2027 (a forecast, not a measurement). — [The Block, 19 Nov 2026](https://www.theblock.co/news/markets/2026-11-19-sygnum-bitcoin-carry-trades-beating-treasury-bills-2027-443547); [TradingView/Cointelegraph](https://www.tradingview.com/news/cointelegraph:a7f65d753094b:0-bitcoin-carry-trades-could-beat-treasury-bills-in-2027-sygnum-predicts/)
- [PRESS] Feb 2024: Binance BTC perp annualized funding topped 100% for the first time in at least a year (Velo Data / CoinGlass). — [FXStreet, 27 Feb 2024](https://www.fxstreet.com/cryptocurrencies/news/bitcoin-funding-rates-jump-to-100-sparking-opportunity-for-savvy-traders-202402270607)
- [DATA-FIRM] BitMEX's 9-year XBTUSD analysis (2025 Q2 derivatives report) gives a mean funding rate of 0.0173% per period. If that is per 8h, it annualizes to about 19% (my calculation: ×3×365). Seen only in a search snippet; the report page redirected and could not be read. — [BitMEX report (search snippet)](https://blog.bitmex.com/2025q2-derivatives-report)
- [DATA-FIRM] Glassnode publishes a free chart comparing 3-month-futures cash-and-carry yield with annualized perp funding (8h rate ×3×365). The chart was introduced in The Week On-chain, Week 12 of 2022. — [Glassnode Studio](https://studio.glassnode.com/workbench/btc-futures-annualized-yield)
- [DATA-FIRM / protocol] Ethena sUSDe: daily APY averaged about 4.99% in Oct 2026 (5.06% on 31 Oct 2026). USDe supply was $4.87B on 1 Oct 2026 and $4.51B on 31 Oct 2026. — [Ethena governance update, Oct 2026](https://gov.ethenafoundation.com/t/ethena-s-october-2026-governance-update/879)
- [VENDOR-BLOG] USDe supply peaked at about $14.82B on 4 Oct 2025 (DefiLlama) and was about $4.95B on 28 Sep 2026. A 30-day average sUSDe APY of 4.79% was reported in late Sep 2026. — [Stablecoin Insider review 2026](https://stablecoininsider.org/ethenas-staked-usde-stablecoin/)
- [DATA-FIRM] On 10 Oct 2025, USDe traded as low as about $0.65 on Binance's spot book amid liquidations and auto-deleveraging. Coin Metrics calls it a sharp, short-lived depeg. Ethena and 21Shares say it was confined to Binance's internal order book and oracle, and that on-chain prices held. — [Coin Metrics](https://coinmetrics.substack.com/p/state-of-the-network-issue-335); [21Shares](https://www.21shares.com/en-eu/insights/why-did-ethenas-stablecoin-remain-stable-onchain-but-depegged-on-binance); [BeInCrypto](https://beincrypto.com/binance-usde-ethena-depeg/)
- [Protocol docs] Ethena says its insurance fund covers periods when the combined LST yield and funding are negative, and that it does not pass on "negative yield" to sUSDe holders. The docs cite the longest historical negative-funding streak as 13 days. Note the Sygnum figure above (67 days of negative 30-day-average funding into May 2026) measures something different but shows longer negative regimes can occur. — [Ethena funding-risk docs](https://docs.ethena.fi/protocol-overview/risks/funding-risk)
- [PRESS] April 2024: funding turned sharply negative during Middle East geopolitical stress, and USDe briefly reached $0.995. — [Cointelegraph Magazine](https://cointelegraph.com/magazine/real-risks-ethena-stablecoin-model-not-ones-you-think/)

### Inferences
- Yield by year, roughly, from the sources above: 2021 and early 2024 were boom peaks (20-40%+ annualized, and above 100% on some days in Feb 2024). The 2022 bear market had low or negative funding; no figure was retrieved. 2025 was moderate, but no clean figure was found. 2026 was about 3-5%, with a negative stretch in Q2 and a rebound to about 9% in late October. Carry is pro-cyclical: it pays most when crash risk is highest (BIS).
- For 150 USD: a delta-neutral split is about 75 USD spot and 75 USD short perp at 1x, or 150 USD spot with a 1-2x perp short. At 5-10% that is about 7.5-15 USD/yr. Round-trip taker fees (about 0.1-0.2% total) and any spot/perp spread consume part of it. The short leg can still be liquidated in a spike if margin is thin, even though the position is hedged. Buying sUSDe gives the same exposure without operational work, but adds smart-contract, custodian/exchange and depeg risk.
- Counterparty risk: in the FTX case (Nov 2022), funds held on the exchange were frozen, so a perfectly hedged position still lost the collateral. With a small balance, a full exchange failure is a 100% loss of whatever sits there.

### Gaps
- No clean yearly average funding/basis series for 2020, 2021, 2022, 2023 or 2025 was retrieved. Glassnode, CoinGlass and Velo charts hold it but were not exported.
- No FTX-specific source was fetched in this session (e.g., bankruptcy figures, customer recovery rates). The FTX point above is general knowledge and needs a citation.
- The 13-day "longest negative streak" in Ethena's docs is undated and may predate 2026.

## Cross-exchange and triangular arbitrage

### Takeaway
Makarov & Schoar (JFE 2020) documented large, recurring cross-exchange gaps that lasted weeks in 2017-18. These came mostly from cross-border capital controls, not from inefficiency between exchanges in the same jurisdiction. The surviving gaps today, such as the Korean premium (about 10% in Mar 2024), persist because they cannot be arbitraged: capital controls, no shorting on the expensive venue, and transfer delay. Same-jurisdiction spreads on liquid pairs are arbitraged by co-located market makers. Retail with 150 USD cannot capture either type after fees and withdrawal costs.

### Cited Findings
- [ACADEMIC] Makarov & Schoar, "Trading and arbitrage in cryptocurrency markets," Journal of Financial Economics 135(2), 2020, pp. 293-319. Tick data cover BTC, ETH and XRP on 34 exchanges in 19 countries. They find large, recurrent arbitrage opportunities that often persist for weeks. Gaps are much larger between countries than within them and smaller between coins, pointing to capital controls. Gaps widen when BTC rallies. A common order-flow component explains up to 80% of BTC returns (published version; the 2018 working paper said 85%). — [LSE Research Online](https://researchonline.lse.ac.uk/id/eprint/118909); [Harvard Law forum summary](https://corpgov.law.harvard.edu/2019/09/21/trading-and-arbitrage-in-cryptocurrency-markets); [Working paper PDF](https://personal.lse.ac.uk/makarov1/index_files/CryptocurrencyMarkets.pdf)
- [PRESS / DATA-FIRM] Kimchi premium: about 10% in Mar 2024 (CoinDesk), and CryptoQuant's Korea Premium Index hit 10.88% on 16 Mar 2024, the highest since May 2021. — [CoinDesk video, 7 Mar 2024](https://www.coindesk.com/video/kimchi-premium-reaches-two-year-high/); [NBC/CNBC](https://www.nbclosangeles.com/news/business/money-report/in-the-wake-of-bitcoins-new-highs-south-koreas-kimchi-premium-is-in-the-spotlight-again/3378619)
- [PRESS] The kimchi premium was about 4% at one point in 2025. CryptoSlate's own (non-academic) backtest treats it as a directional signal, not an arbitrage. — [CryptoSlate](https://cryptoslate.com/does-thes-kimchi-premium-still-front-run-btc/?rand=6792)
- [ACADEMIC] Limits to arbitrage: BTC usually cannot be shorted on the premium venue, and the premium can shrink or vanish during transfer time. Exchange default risk and liquidity also affect cross-exchange arbitrage. — [Borri & Shakhnov, LUISS](https://iris.luiss.it/bitstream/11385/232119/1/borri-shakhnov-cryptomarket_discounts.pdf); [Cardiff/FRL paper](https://orca.cardiff.ac.uk/173664/1/1-s2.0-S154461232401393X-main.pdf)
- [DATA-FIRM via PRESS] Kaiko (Mar 2024): BTC's all-time-high price differed by venue. This is only evidence of divergence; no spread size is given. — [Axios, 7 Mar 2024](https://www.axios.com/2024/03/07/bitcoin-all-time-high-btc-complicated)
- [PRESS] Blockworks covers the decline of retail crypto arbitrage. Content not fetched. — [Blockworks](https://blockworks.co/news/what-happened-to-arbitrage-trading-in-crypto)

### Inferences
- Within the same jurisdiction, BTC/ETH spreads on top exchanges are now typically below combined taker fees (about 0.1% per side) for anyone without VIP fee tiers and co-location. Triangular arbitrage on one exchange is competed away by bots with fee rebates. Treat this as a reasoned conclusion, not a measured figure from this session.
- A fixed withdrawal fee (often a few USD, or a BTC network fee) on a 150 USD round trip alone exceeds 1-3%, which wipes out most observable spreads.

### Gaps
- No 2024-2026 Kaiko or academic measurement of typical intra-jurisdiction cross-exchange spreads or half-lives was found.
- No study of triangular-arbitrage profitability after 2022 was found.

## MEV (sandwich, arbitrage) on Ethereum and Solana

### Takeaway
MEV is a highly concentrated, infrastructure-heavy industry. On Ethereum, 2-3 builders produce over 80-90% of blocks (Titan about half), the top 3 CEX-DEX searchers capture about three quarters of that volume and value, and searchers bid most of their profit away to builders. On Solana, Jito tips are about 42-66% of chain "REV", and sandwiching is done by a few dozen bots. A 150 USD retail trader has no realistic path: capital for inventory, low-latency infrastructure and exclusive order flow are the barriers, and sandwiching harms users.

### Cited Findings
- [ACADEMIC] Canidio & Pahari (arXiv 2509.16052, 2025): Titan builds about half of Ethereum blocks and the top 3 builders over 90%. Concentration is driven by exclusive order flow, with a feedback loop where winning builders attract more of it. Flashbots ran its own builder until mid-2025, then BuilderNet (Flashbots + Beaverbuild) took over. — [arXiv 2509.16052](https://arxiv.org/html/2509.16052v3)
- [ACADEMIC] Oct 2023-Mar 2024: three builders produced about 80% of blocks. — [arXiv 2407.13931](https://arxiv.org/html/2407.13931v1)
- [ACADEMIC, preprint] By Sep 2024, Titan and Beaverbuild held a combined 87.7%. Concentration remained entrenched through 2025 even after BuilderNet absorbed Beaverbuild. — [arXiv 2605.04471](https://arxiv.org/pdf/2605.04471.pdf)
- [ACADEMIC] CEX-DEX arbitrage (AFT 2025 / arXiv 2507.13023): the top 3 searchers capture about 75% of CEX-DEX arbitrage volume and extracted value. Searchers tied exclusively to a builder pass most revenue to that builder and sometimes run at negative net profit. — [Dagstuhl AFT 2025](https://drops.dagstuhl.de/storage/00lipics/lipics-vol354-aft2025/html/LIPIcs.AFT.2025.26/LIPIcs.AFT.2025.26.html); [arXiv](https://arxiv.org/html/2507.13023v3)
- [DATA-FIRM via PRESS] In a 30-day Bitquery sample of Ethereum arbitrage surplus, about 49.3% went to builders, 9.4% was burned and 41.3% went to trading operators. — [CryptoSlate](https://cryptoslate.com/ethereum-arbitrage-study-reveals-builders-receive-5-for-every-1-burned-by-the-network/)
- [VENDOR-BLOG, conflicted] Titan takes about 80-85% of total builder surplus while building about half of blocks (Dune data). The author discloses an investment in Titan's parent, Gattaca. — [Greenfield Capital](https://greenfieldcapital.com/?p=4614)
- [DATA-FIRM] Solana: Jito tips were 41.6-66% of Solana REV in H1 2025. — [Helius H1 2025 report](https://www.helius.dev/blog/solana-ecosystem-report-h1-2025)
- [ACADEMIC] IMC '25 measurement found 521,903 sandwich attacks via Jito with over $7.7M in victim losses. — [Weintraub et al. PDF](https://ben-weintraub.com/files/solanamev.pdf)
- [VENDOR-BLOG] In one Solana sandwich sample, 40 attackers extracted 5,321 SOL (about $708k), 78.4% of which went to searchers as profit. Only about 40% of attacks went through Jito. — [elovianoo Substack](https://elovianoo.substack.com/p/toxic-mev-on-solana)
- [VENDOR-BLOG] Solana MEV totals conflict: $720M for 2025 vs "over $400M". Searchers reportedly tip 35-60% of expected profit. — [Business Model Analyst](https://businessmodelanalyst.com/the-400-million-mev-problem-how-solanas-block-production-became-a-competitive-sport/); [Dysnix](https://dysnix.com/blog/solana-mev-infrastructure)

### Inferences
- The competitive auction transfers most MEV to builders and validators. The residual margin goes to a handful of professional teams with custom infrastructure, private order flow and inventory on both CEX and DEX. Retail is far more likely to be a victim (being sandwiched) than an earner. For small traders the practical "edge" is defensive: use MEV-protected RPCs or intent-based DEXs and set tight slippage.

### Gaps
- No retrieved data from mevboost.pics, relayscan.io or EigenPhi on searcher profit distribution for 2025-26. These dashboards are free and should be checked directly.
- No study measures the profitability of new or small searchers.

## Liquidation hunting and open-interest signals

### Takeaway
Liquidation cascades are real and huge: over $19B was liquidated on about 10 Oct 2025. No peer-reviewed or backtested study was found showing that trading toward or around liquidation-heatmap clusters is profitable. Heatmap claims come from vendors.

### Cited Findings
- [DATA-FIRM / consultancy] More than $19B of crypto leverage was liquidated in roughly one day around 10 Oct 2025. — [FTI Consulting](https://www.fticonsulting.com/insights/articles/crypto-crash-october-2025-leverage-met-liquidity)
- [PRESS] Hyperliquid open interest fell by $7.4B (over 30%), yet volume rose 17% in the following week, and traders "kept getting liquidated". — [The Block, 21 Oct 2025](https://www.theblock.co/news/markets/2025-10-21-hyperliquid-traders-double-down-after-historic-wipeout-keep-getting-liquidated-375347)
- [ACADEMIC, reported] Most forced selling in the worst minute went to Hyperliquid's backstop, not its public book ($576M moved off-book). — [CryptoSlate](https://cryptoslate.com/shifting-576-million-of-forced-sales-off-public-order-books-saved-hyperliquid-from-a-systemic-crash-during-peak-panic/)
- [ACADEMIC] Lim (2026, Journal of FinTech and Digital Assets) studies Hyperliquid order-book liquidity recovery after the cascade. It is a microstructure paper, not a signal test. — [JFDA](https://journals.lincoln.ac.nz/index.php/JFDA/article/view/1395)
- [VENDOR-BLOG] Glassnode: as price approaches liquidation clusters, "market stress intensifies". This is a descriptive claim, not a backtest. — [Glassnode](https://insights.glassnode.com/liquidation-heatmaps/)
- [ACADEMIC] The BIS crypto-carry paper links high carry (crowded leveraged longs) to subsequent crashes. This is the closest peer-reviewed-style evidence that leverage or positioning indicators predict drawdowns. — [BIS WP 1087](https://www.bis.org/publ/work1087.htm)

### Inferences
- Extreme positive funding or basis and high OI-to-market-cap may work as a crash-risk warning (consistent with BIS). Using them for precise entries is unproven. Small accounts trading these setups with leverage are exposed to the same cascades. Note also that heatmaps are model estimates, since exchanges do not publish leverage by position.

### Gaps
- No academic backtest of liquidation-cluster or OI-based strategies net of costs was found.

## On-chain whale tracking and smart-money following (Nansen, Arkham)

### Takeaway
The only quantitative support comes from the vendor selling the labels (Nansen, data to Mar 2022). Independent evidence points to execution gaps: Bitquery says 74% of Pump.fun gains cannot be replicated by copiers. Other problems are survivorship bias and mislabeled wallets, including MEV bots and market makers. No measured evidence shows that followers profit.

### Cited Findings
- [VENDOR-BLOG] Nansen's own test of copy strategies using its Smart Money labels, on Ethereum data up to Mar 2022, claims "significant returns" potential. — [Nansen research](https://www.nansen.ai/research/trading-crypto-with-nansen-smart-money)
- [DATA-FIRM via PRESS] Bitquery Pump.fun study ($752M of gains): 74% of gains cannot be replicated by copy traders because of early-entry and latency gaps. — [CryptoSlate](https://cryptoslate.com/pump-funs-biggest-winners-may-be-impossible-to-copy-as-752-million-study-exposes-hidden-trading-gap/); [KuCoin news](https://www.kucoin.com/news/flash/bitquery-study-reveals-74-of-pump-fun-gains-cannot-be-replicated-by-copy-traders)
- [ACADEMIC] A Jan 2026 arXiv paper finds that meme-coin trader profitability is predictable. It does not test follower returns. — [arXiv 2601.08641](https://arxiv.org/html/2601.08641)
- [VENDOR-BLOG] Pitfalls include copying MEV bots or market makers by mistake and wallet networks that fake profitability. — [Bitsgap](https://bitsgap.com/blog/why-copying-on-chain-whale-trades-usually-backfires); [KuCoin blog](https://www.kucoin.com/blog/tr-is-crypto-copytrading-profitable-in-2026)

### Inferences
- Free on-chain explorers (Arkham free tier, Etherscan, Dune, Solscan) make tracking possible at zero cost. The edge, if any, decays with latency, and gas or priority fees take a large share of a small copied trade.

### Gaps
- No independent, peer-reviewed study of the net returns of following labeled smart-money wallets was found.

## Token unlock events

### Takeaway
Keyrock's study of over 16,000 unlocks (40 tokens, published around Dec 2024) found about 90% exert negative price pressure. Declines start about 30 days before the unlock, team unlocks are worst (about −25%), and prices stabilise about 14 days after. This is a market-maker study, not peer-reviewed. The "short before the unlock" trade is widely known and partly priced in.

### Cited Findings
- [DATA-FIRM] Keyrock, "From Locked to Liquidity: What 16,000+ Token Unlocks Teach Us": over 16,000 events across 40 tokens, with prices tracked ±30 days and normalised to ETH. 90% of unlocks show negative price pressure. Team unlocks are the worst (−25%; method not shown). Investor and community unlocks have moderate effects (investor unlocks: 106 events, slow minimal declines). Ecosystem-development unlocks average +1.18%. Pre-unlock declines start about 30 days ahead and accelerate in the final week; volume peaks 28 or 14 days before. Prices stabilise within about 14 days after. Size does not scale neatly: "Huge" (>10% of supply) unlocks did as well as or better than "Large" ones, although the key takeaways say bigger unlocks cause 2.4x sharper drops. More than $600M unlocks weekly. — [Keyrock](https://keyrock.com/from-locked-to-liquidity-what-16000-token-unlocks-teach-us/)
- [PRESS] Coverage of the same study. — [CryptoSlate](https://cryptoslate.com/90-of-token-unlocks-drive-prices-down-declines-begin-a-month-ahead/); [BeInCrypto](https://beincrypto.com/keyrock-research-token-unlocks/)

### Inferences
- The tradable version is to short or underweight 30 days before large team or investor unlocks. That needs perps on mid-cap tokens, which carry funding costs and squeeze risk, and Keyrock's ETH-relative returns are not directly a USD P&L. Free calendars include Tokenomist (ex-Token Unlocks), CryptoRank and DefiLlama unlocks. Keyrock's sample has survivorship and a 2.4x vs "size doesn't matter" inconsistency, which lowers confidence.

### Gaps
- The Tie unlock study was not retrieved. No peer-reviewed unlock-event study was found.

## Exchange listing announcements (Binance, Coinbase effect)

### Takeaway
Announcement-day returns are large on average: 32.8% on Coinbase and 22.7% on Binance in an AFT 2025 paper. They mostly accrue before or at the announcement, and post-listing returns revert to flat or negative within one to a few weeks (The Tie, 1,844 listings, 2023-Jun 2026). Retail cannot reliably get in before the announcement and is typically the exit liquidity afterwards.

### Cited Findings
- [ACADEMIC] AFT 2025 (LIPIcs vol. 354, paper 11): significantly positive short-term listing returns on both exchanges, higher on the more-regulated Coinbase than on Binance. A related working paper reports average first-day announcement returns of 32.8% (Coinbase) and 22.7% (Binance). The result extends to 80 exchanges: more regulated venues give higher initial returns. — [Dagstuhl AFT 2025](https://drops.dagstuhl.de/storage/00lipics/lipics-vol354-aft2025/html/LIPIcs.AFT.2025.11/LIPIcs.AFT.2025.11.html); [Loyola conference slides](https://loyola.edu/_media/sellinger-business/documents/academics/departments/finance/wealth-management-conference/speakers/J_Li.pdf)
- [DATA-FIRM] The Tie (2026): 1,844 listings on Binance, Coinbase, OKX, Bybit, Kraken, Upbit and Bithumb, Jan 2023-Jun 2026, BTC-adjusted. Prices rise before day 0, and more tokens run up pre-listing than gain after. Post-listing returns go flat or negative within about 1-2 weeks. Small caps show the biggest pop and the steepest later decline. First-ever listings decline the most. The 2023 cohort was the high-water mark, with 2024-26 reactions smaller and fading faster. Volume stays above 1.5x baseline while price reverts. Limitations: CCData only, no wash-trade filter, and day 0 is the first trade, not the announcement. — [The Tie](https://www.thetie.io/insights/what-does-an-exchange-listing-actually-deliver-in-2026)
- [PRESS / DATA-FIRM] The "Binance effect" fades: fewer than 20% of tokens were profitable six months after listing (May 2024). — [FXStreet](https://fxstreet.com/cryptocurrencies/news/binance-effect-fades-less-than-20-tokens-are-profitable-six-months-after-listing-202405201006)
- [VENDOR-BLOG] Average −11.3% over the first 7 days after listing for 20 Binance tokens (small sample). Messari (2021): a 91% jump in the first 5 days after Coinbase listings, a pre-2022 figure. — [Blockworks](https://blockworks.co/news/major-exchange-listings-coinbase-binance); [RockawayX](https://rockawayx.com/insights/bullish-or-bearish-what-really-happens-when-tokens-list-on-a-cex)

### Inferences
- The capturable part for retail is at most the seconds to minutes after a public announcement, which is a latency race against bots that parse exchange APIs. The documented post-listing drift is negative, so the evidence-consistent retail stance is to avoid buying newly listed tokens after listing. Front-running evidence (pre-announcement run-ups) suggests information leakage that retail cannot access.

### Gaps
- No 2023-26 peer-reviewed measurement of pre-announcement front-running was found. The Tie's numeric charts were not in the page text.

## DeFi yield farming and liquidity providing

### Takeaway
Measured studies show passive LPs in volatile pairs usually underperform holding. In May-Sep 2021, $260.1M of impermanent loss exceeded $199.3M in fees, and 49.5% of LPs had negative returns. In Jan 2022-Dec 2023, fees covered only about 80% of arbitrage losses (LVR) in the largest Uniswap v3 ETH pool. Fees did cover losses in some Uniswap v2 and less-liquid pools. On top of that come gas costs, which are proportionally large for 150 USD on L1, plus smart-contract risk.

### Cited Findings
- [ACADEMIC] Loesch et al., "Impermanent Loss in Uniswap v3" (arXiv 2111.09192, Nov 2021). Covering uncorrelated pairs with TVL above $10M (about 43% of v3 TVL), May-Sep 2021: $260.1M IL vs $199.3M fees, and 49.5% of LPs had negative returns. The average LP would have done better holding. — [arXiv 2111.09192](https://arxiv.org/pdf/2111.09192)
- [ACADEMIC] Milionis, Moallemi & Roughgarden, LVR framework (arXiv 2208.06046): ignoring fees, AMM LPs always do worse than a rebalancing strategy, and the model matches observed Uniswap v2 WETH-USDC losses. — [arXiv 2208.06046](https://arxiv.org/pdf/2208.06046v4)
- [ACADEMIC] Fritsch & Canidio, "Measuring Arbitrage Losses and Profitability of AMM Liquidity" (arXiv 2404.05803, Apr 2024), covering Jan 2022-Dec 2023:
  - In the largest Uniswap v3 ETH/BTC pools, fees fall short of LVR. WETH-USDC 5bp fees were about 80% of losses. WETH-USDT 5bp and WBTC-USDC 30bp roughly broke even.
  - Less-liquid v3 pairs (MATIC-ETH, LINK-ETH) had fees up to about 50% above losses.
  - On Uniswap v2, fees were consistently about 3x losses in the second year, and v2 beat v3 for the same pair and fee tier.
  - Faster blocks cut arbitrage losses by 20-70%.
  — [arXiv 2404.05803](https://arxiv.org/html/2404.05803v2)

### Inferences
- Post-2022 "real yield" for retail LPs is weakly positive at best in volatile pairs and depends on the pool. Stablecoin-stablecoin pools avoid most IL but yield little and carry depeg risk. At 150 USD, Ethereum L1 gas for entry, exit and rebalancing can wipe out a year of fees, so only L2s or Solana are viable cost-wise. Smart-contract exploits are an additional loss source not modelled in these studies.

### Gaps
- No 2024-26 study of aggregate LP P&L across chains or L2s was retrieved. No measured study of "real yield" (protocol revenue-based) farming returns after 2022 was found.

## Crypto momentum and trend factors

### Takeaway
Academic evidence for 2014-2018 samples is strong. Liu & Tsyvinski (RFS 2021) find strong time-series momentum and predictive investor attention. Liu, Tsyvinski & Wu (JF 2022) find a three-factor model (market, size, momentum). Post-2021 evidence is mixed: Coinbase found TSMOM underperformed buy-and-hold in 5 of 7 quarters from 2021 to Q3 2022, momentum crashes are severe, and the strong 2022-24 out-of-sample claims come from non-peer-reviewed preprints. Time-series trend following is the most accessible approach for 150 USD, since it needs no infrastructure and only spot trades, but the expected edge is uncertain.

### Cited Findings
- [ACADEMIC] Liu & Tsyvinski, "Risks and Returns of Cryptocurrency," Review of Financial Studies 34(6), 2021, pp. 2689-2727 (NBER w24877, 2018). There is strong time-series momentum. Attention proxies (Google, Twitter) forecast returns: a 1 SD rise in weekly BTC Google searches is associated with about +1.84% the next week. There is no exposure to stock, macro, currency or commodity factors, and momentum is weaker for ETH. — [NBER w24877](https://nber.org/papers/w24877); [RePEc](https://econpapers.repec.org/RePEc:oup:rfinst:v:34:y:2021:i:6:p:2689-2727.)
- [ACADEMIC] Liu, Tsyvinski & Wu, "Common Risk Factors in Cryptocurrency," Journal of Finance 77(2), 2022, pp. 1133-1177. Three factors (crypto market, size, momentum) capture the cross-section of expected crypto returns. Of 25 tested characteristics, 9 form significant long-short strategies, all explained by the 3-factor model. — [RePEc JF](https://econpapers.repec.org/RePEc:bla:jfinan:v:77:y:2022:i:2:p:1133-1177); [NBER w25882](https://www.nber.org/papers/w25882)
- [DATA-FIRM] Coinbase Institutional (Sep 2022): TSMOM underperformed buy-and-hold in all but 2 of 7 quarters since the start of 2021, with high variability. — [Coinbase research](https://www.coinbase.com/institutional/research-insights/research/monthly-outlook/trend-following-in-uncertain-times-september-2022)
- [ACADEMIC] Han, Kang & Ryu: under realistic assumptions, time-series momentum evidence is strong and cross-sectional momentum evidence weak. TSMOM is concentrated in bull markets. — [JFQA/Cambridge](https://www.cambridge.org/core/services/aop-cambridge-core/content/view/S0022109024000747)
- [ACADEMIC] Crypto momentum suffers severe crashes, e.g., −255.23% in one Dec 2020 event (long-short). — [Springer FMPM](https://link.springer.com/article/10.1007/s11408-025-00474-9)
- [ACADEMIC, low credibility preprint] Talyxion "AdaptiveTrend" (arXiv 2602.11708) claims a Sharpe of 2.41 and max drawdown of −12.7% over 2022-2024. It is not peer-reviewed, from a small firm, and the numbers look implausibly strong. — [arXiv 2602.11708](https://arxiv.org/html/2602.11708v1)

### Inferences
- The cross-sectional size and momentum factors require shorting many small coins, which is not feasible at 150 USD. A long-or-cash BTC/ETH trend filter is feasible, and the Han et al. result (TSMOM concentrated in bull markets) is consistent with it acting mainly as drawdown avoidance. Fees and whipsaw in sideways regimes (as in 2021-22, per Coinbase) are the main drag.

### Gaps
- No peer-reviewed out-of-sample test of crypto TSMOM on 2023-2026 data was found.

## Free data sources (cross-cutting)
- Funding, basis and OI: CoinGlass (free tier), Velo Data, Glassnode Studio (some free charts, e.g. the [futures annualized yield chart](https://studio.glassnode.com/workbench/btc-futures-annualized-yield)), and exchange public APIs (Binance, Bybit, OKX, Hyperliquid funding history endpoints).
- Ethena: app.ethena.fi, DefiLlama, and the [Ethena governance monthly updates](https://gov.ethenafoundation.com/t/ethena-s-october-2026-governance-update/879).
- MEV: mevboost.pics, relayscan.io (cited by [Canidio & Pahari](https://arxiv.org/html/2509.16052v3)), EigenPhi, Dune dashboards, and Jito explorer for Solana.
- Unlocks: Tokenomist, CryptoRank and DefiLlama unlock calendars. Listings: exchange announcement RSS/API feeds.
- On-chain: Arkham (free tier), Etherscan, Solscan, Dune, Nansen (mostly paid).
- LP analytics: Revert Finance and Dune Uniswap dashboards (not verified in this session).
