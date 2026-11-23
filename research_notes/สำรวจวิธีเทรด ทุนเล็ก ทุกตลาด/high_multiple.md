# High-multiple (5x+ in one month) routes: measured success vs. ruin rates

Research date: 2026-11-23. Notes compiled from web search snippets plus a small number of fetched pages. Most crypto figures come from crypto media reporting on Dune, Hyperdash or on-chain analyst data, not from peer-reviewed work. Treat them as snapshots tied to a specific time window. Items marked **[UNVERIFIED]** or **[SECONDARY]** were not checked against the primary document.

## 1. Memecoins and launchpads (pump.fun, Raydium, snipers)

### Takeaway
Fewer than about 2% of pump.fun tokens ever "graduate" to a DEX. Solidus Labs flagged about 98.6-98.7% of pump.fun tokens as rug pulls or pump-and-dumps. On Dune-based wallet studies, roughly half to 60% of pump.fun wallets lose money, about 96% lose money or make less than $500, and only about 0.4% realize more than $10k. The consistent winners are creators and same-block sniper bots, not retail buyers.

### Cited Findings
- **Solidus Labs "2025 Rug Pull Report"** (published about May 2025). It analyzed more than 7 million pump.fun tokens from January 2024 to March 2025. Fewer than 100,000 kept liquidity above $1,000. The report flags about **98.7%** of pump.fun tokens (its own page and X post; most press, including CoinDesk, says **98.6%**) and **about 93% of 388,000 Raydium pools (about 361,000)** as showing rug-pull or pump-and-dump ("soft rug") patterns. The rugs were mostly small: the 25th percentile was under $732, the median about $2,832, and the largest $1.9M — [Solidus Labs report page](https://www.soliduslabs.com/reports/solana-rug-pulls-pump-dumps-crypto-compliance); [CoinDesk coverage](https://hotfix.coindesk.com/business/2025/05/07/98-of-tokens-on-pump-fun-have-been-rug-pulls-or-an-act-of-fraud-new-report-says); [BeInCrypto](https://beincrypto.com/pump-fun-tokens-scams-solidus-labs-report/)
  - Verification: the "98.6%" figure is real but press rounding. Solidus's own page says 98.7%. **Pump.fun publicly disputed the report** (CoinDesk headline: "Pump.fun Hits Back..."). I did not retrieve the substance of its rebuttal. "Rug/pump-and-dump" is a behavioral classification, and it largely captures tokens that simply died with a small amount of creator extraction.
- **Graduation rate (share of tokens that complete the bonding curve and migrate to a DEX):**
  - Published estimates range from 0.63% to 3.09% across three studies — [BloFin Academy](https://blofin.com/academy/education/pumpfun/pump-fun-graduation-rate-reality) [SECONDARY]
  - About 5-8% in early 2024 and about 0.7-0.8% in July-August 2025 — [Cointelegraph](https://cointelegraph.com/news/how-pump-fun-captured-80-of-solana-memecoins-and-can-it-last) [SECONDARY, snippet]
  - On-chain data shows that fewer than 2% of launched coins graduate (June 2026), with about 0.26% at a mid-June 2026 low (Dune via DEXTools) — [The Block](https://theblock.co/news/defi/2026-07-29-pump-fun-token-graduation-rate-jumps-boost-changes-launch-incentives-409815); [DEXTools](https://www.dextools.io/news/pump-fun-graduation-collapse-solana-fees-2026)
  - A temporary spike to 6.7% in late July 2026 followed the "BOOST" mechanism. The Block notes that BOOST acts after bonding, so the spike does not mean more tokens are reaching the threshold — [The Block](https://theblock.co/news/defi/2026-07-29-pump-fun-token-graduation-rate-jumps-boost-changes-launch-incentives-409815)
  - Bots buy into about 1 in 4 new tokens at launch, and almost none of those tokens graduate (June 2026) — [DEXTools](https://www.dextools.io/news/pumpfun-new-token-bot-activity-data-june-2026)
- **Wallet P&L (Dune, realized P&L only):**
  - Six months before the PUMP token launch (mid-2025), more than 60% of pump.fun addresses had losses. Another reading of the same period gives about 56% with losses of at least $1,000 — [BeInCrypto](https://beincrypto.com/pump-fun-trading-data-majority-lose-money/); [crypto.news](https://crypto.news/over-60-pump-fun-traders-saw-losses-less-than-0-01-made-over-1m/)
  - About 27.2% of roughly 4.2M tracked wallets were profitable — [Cointelegraph (Dune)](https://cointelegraph.com/news/pump-fun-crypto-traders-majority-do-not-realize-profits-dune-data)
  - Only 55,012 of more than 13.4M wallets (about **0.4%**) realized at least $10k. About **0.048%** realized more than $100k and about **0.00217%** realized more than $1M — [CoinMarketCap Academy](https://coinmarketcap.com/academy/nl/article/996percent-of-pumpfun-traders-have-not-realized-over-dollar10000-in-profits-data-shows); [crypto.news](https://crypto.news/over-60-pump-fun-traders-saw-losses-less-than-0-01-made-over-1m/)
  - March 2026 snapshot of about 1.4M wallets: 49-50.6% lost money, and **about 96% either lost money or earned less than $500** — [crypto.news](https://crypto.news/pump-fun-data-shows-49-of-march-traders-in-the-red-as-platform-locks-fees/)
  - Caveat: one person can run many wallets, and realized P&L ignores bags still held, which are mostly worthless. The true loss share is probably higher than the realized-loss share. Wallet counts also overstate the number of distinct people.
- **Chainalysis (2025 Crypto Crime Report / January 2025 blog):** more than 2M tokens were launched in 2024 (the blog says more than 3M) and about 42% were listed on a DEX. **Only about 1.7% were actively traded in the last 30 days (as of the report).** About **3.59%** of all 2024 launches showed pump-and-dump traits (the blog version says about 4.5%). **Nearly 90% of suspected pump-and-dump DEX pools were rugged by the address that created the pool** — [Tekedia](https://www.tekedia.com/3-59-of-tokens-launched-in-2024-showed-signs-of-pump-and-dump-schemes-chainalysis-report-reveals/); [crypto.news](https://crypto.news/chainalysis-over-4-5-of-all-tokens-launched-in-2024-have-pump-and-dump-traits/) [SECONDARY. The 3.59% vs 4.5% gap comes from different token counts and methods.]
  - Note: Chainalysis's 3.6-4.5% "pump-and-dump" share is far below Solidus's 98.6%, because the definitions differ. Chainalysis requires a specific price-spike-then-dump pattern. Solidus counts almost any liquidity pull or abandonment. Both agree that about 98% of new tokens are effectively dead within weeks. Chainalysis also found that only about 1.7% of 2024 tokens were actively traded in the last 30 days.
- **Sniper bots:**
  - Pine Analytics found that deployer-funded same-block snipers took more than **15,000 SOL in realized net profit in one month across 15,000+ launches**. They had an **87% success rate** and typically made 1-100 SOL per wallet. 85% of positions were exited within 5 minutes — [Pine Analytics "Exit Liquidity Machines"](https://pineanalytics.substack.com/p/exit-liquidity-machines); [BeInCrypto](https://beincrypto.com/pump-fun-meme-coin-snipers-systematic-problem)
  - Lookonchain reported a single bot that made about 27,000 SOL in 30 days from pump.fun sniping — [BeInCrypto](https://beincrypto.com/?p=689736) [SECONDARY, single case]
  - An academic study of 6,000 pump.fun projects defines snipers as buyers in the first 5 blocks and finds that sniper presence cuts creator profit by about $54 per project — [SBFC 2025 paper](https://sbfc.sydney.edu.au/2025/papers/SBFC2025_4G3_P154.pdf)

### Inferences
- A retail buyer of a random new memecoin faces a roughly 98% chance that the token dies or is rugged within weeks. A 5x+ outcome is real but concentrated in less than 1-2% of tokens, and the profits from those tokens go disproportionately to creators and block-0 snipers who sell to later buyers.
- The realistic odds that a retail wallet turns a small stake into a large sum: about 0.4% of wallets ever realized $10k or more, and about 0.05% realized $100k or more. Even this upper tail mixes skill, insider status, bots and survivorship.
- Sniping is the one memecoin route with a high measured "success rate" (87%). Most of that profit comes from deployer-linked or insider wallets with infrastructure, and retail snipers using off-the-shelf Telegram bots compete with them for the same blocks.

### Gaps
- I did not obtain the Solidus PDF's methodology or Pump.fun's detailed rebuttal.
- I found no peer-reviewed estimate of the share of pump.fun *buyers* (as opposed to wallets) who achieve 5x+ in a month.
- I found no data on retail Telegram-bot sniper P&L (for example Trojan or BonkBot users) as a population.

## 2. Airdrop farming

### Takeaway
Major airdrops paid ordinary eligible wallets in the low hundreds of dollars on average, and the median was lower. Sybil filtering removed a large share of farming wallets. Most airdropped tokens fell in price within 90 days. Airdrop farming is a time- and gas-intensive lottery with mostly small payoffs, not a dependable 5x-in-a-month route.

### Cited Findings
- **Jupiter (JUP), round 1, January 2024:** 1B JUP went to about 955,000 wallets. Every user got at least 200 JUP. The average claim was **489 JUP**, skewed by whales and power users — [Decrypt](https://decrypt.co/208324/jupiter-reveals-airdrop-allocations-solana-defi-users); [SolanaFloor](https://solanafloor.com/news/25-of-jup-claimants-stake-allocations-and-recommit-for-further-rewards)
- **Jupiter "Jupuary" January 2025:** 700M JUP worth about **$550-616M** went to about 2M eligible wallets. That implies roughly **$275-308 per wallet on average** (my arithmetic). The median was lower because allocations are skewed — [The Defiant](https://thedefiant.io/news/defi/jupiter-launches-usd550-million-jupuary-airdrop); [CoinMarketCap](https://coinmarketcap.com/academy/article/jupiters-jupuary-airdrop-dollar616-million-in-tokens-to-be-distributed-today)
- **LayerZero (ZRO), June 2024:** 1.28M of about 6M interacting wallets were eligible. About 1M wallets were identified as sybils. Self-reported sybils got 15% of their allocation. The drop was worth about $290M at $3.46/ZRO, an **average of about $229 per recipient** with a top recipient of about $36k — [CoinMarketCap](https://coinmarketcap.com/academy/article/layerzero-announces-airdrop-eligibility-for-128-million-wallets); [TechFlow](https://techflowpost.com/en-US/article/18588); [The Block](https://www.theblock.co/post/301626/layerzeros-zro-token-faces-mixed-reactions-as-sybil-crackdown-continues)
  - One source says 803,273 wallets (59%) were removed before distribution. This conflicts with other counts — [Crypto News Navigator](https://www.cryptonewsnavigator.com/academy/article/layerzero-airdrop-retrospective-shows-what-worked-and-what-didnt)
- **Arbitrum (ARB), March 2023:** allocations of **625 to 10,250 ARB per wallet** — [Spark glossary](https://www.spark.money/glossary/airdrop-farming) [SECONDARY]. An academic study found that up to about **95% of airdrop proceeds were sold on exchanges shortly after the drop**, and that per-address activity fell after the airdrop — [arXiv 2312.02752](https://arxiv.org/html/2312.02752v4)
- **Post-airdrop price performance:** Keyrock's study of **62 airdrops in 2024** found that **about 88.7% were below their listing price after 90 days**. Only 8 had positive 90-day returns, and most of the move happened within about 15 days. Keyrock notes the weak overall market as a confounder — [Keyrock](https://keyrock.com/airdrops-in-the-barren-desert/); [DappRadar "88% lose value within 3 months"](https://dappradar.com/blog/88-of-airdropped-tokens-lose-value-within-3-month)
- One post-2024 compilation found that 6 of 8 tracked airdrop projects lost 92-99% of their value, and only Hyperliquid (HYPE) delivered about 36x — [KuCoin news flash](https://www.kucoin.com/news/flash/crypto-airdrop-data-shows-6-of-8-projects-lose-92-99-value-only-hyperliquid-delivers-36x-return) [SECONDARY, exchange content]
- Trend: commentators describe most 2024 airdrops as disappointing because of industrial sybil farming and whale participation — [The Defiant](https://thedefiant.io/education/premium-tutorials/is-airdrop-farming-back); [Blockworks](https://www.blockworks.com/news/airdrop-branding-layerzero-zro-token-launch)

### Inferences
- Measured against capital, a $100-300 average airdrop on a wallet that spent $50-200 in fees and bridging over months can be a high *percentage* return. But it arrives on a 6-18 month timeline, not one month, and payoffs per wallet are capped at small dollar amounts unless the farmer runs many wallets, which is exactly what sybil filters target.
- Outliers like Hyperliquid (about 36x) exist, but they are found only after the fact, which is survivorship.

### Gaps
- I found no reliable median (as opposed to average) per-wallet value for Arbitrum, Jupiter or LayerZero.
- I found no systematic study of farmer ROI (cost, time, gas, sybil-exclusion rate) across many campaigns.

## 3. Leveraged perpetual futures (crypto)

### Takeaway
Leveraged crypto perps are a heavy net-loss activity for retail. Third-party Hyperliquid samples show only about 14-25% of accounts profitable. Retail-facing consumer-app wallets lost $280M with about 14% three-month survival. Single events liquidate more than 1.6M traders in a day. Academic work on BitMEX finds that liquidated traders used about 60x average leverage and that smaller traders are disproportionately liquidated.

### Cited Findings
- **Cheng, Deng, Wang & Yu (2021), arXiv 2102.04591 (BitMEX perpetuals):** daily forced liquidations equal **3.51% of outstanding longs and 1.89% of shorts**. Liquidated investors used an average leverage of about **60x** — [arXiv](https://arxiv.org/abs/2102.04591)
- **Binance 2020 data**, cited in an NYU Stern working paper: about **79% of customers traded with more than 20x leverage**, and high leverage was most popular among retail — [Duró-Carielo, NYU Stern](https://www.stern.nyu.edu/sites/default/files/assets/documents/Duron-Carielo_Is%20There%20A%20Future%20In%20Perpetual%20Futures.pdf) [exchange-sourced figure]
- **Carnegie Mellon (Soska et al.) BitMEX study:** small and inexperienced traders are disproportionately liquidated and outperformed by more sophisticated traders — [CryptoNews](https://cryptonews.com/news/obsessed-amateur-crypto-traders-are-disproportionately-liqui-9979.htm) [SECONDARY]
- **Jia, Moallemi, Wang & Zeng (AFT 2026), Hyperliquid:** "front-end" (predominantly retail) traders lost about **$1.11B**, through forced liquidations, execution costs and fees. Liquidations exit "at prices far worse than any voluntary trade" — [LIPIcs AFT 2026](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.AFT.2026.36)
- **Hyperliquid wallet samples:** a June 2025 Hyperdash sample of 1,000 traders showed 135-166 profitable (**about 14-16.6%**), with an average daily P&L of -$5,600. A May 2026 address-level analysis found **about 75% of addresses losing**. About 400,000 wallets trading via six consumer apps lost **$280M**, with **three-month survival near 14%** — [The Coin Republic](https://www.thecoinrepublic.com/2025/06/16/hyperliquid-crypto-only-166-of-1000-traders-profitable-whats-going-on/); [HTX news](https://www.htx.com/news/data-75-of-traders-on-hyperliquid-are-losing-money-what-are-R2h1lIXH/); [KuCoin blog](https://www.kucoin.com/blog/th-hyperliquid-retail-traders-280-million-losses) [SECONDARY, third-party analytics]
- **Liquidation events (CoinGlass):** on October 10-11, 2025, **$19.13B** was liquidated across **1,618,240 traders** in 24 hours, the largest event on record and about 9x any prior day. CoinGlass calls this an undercount because Binance reports only one liquidation per second — [Decrypt](https://decrypt.co/343941/bitcoin-ethereum-dogecoin-down-record-19-billion-crypto-liquidations); [CoinGecko](https://www.coingecko.com/learn/october-10-crypto-crash-explained); [FTI Consulting](https://www.fticonsulting.com/insights/articles/crypto-crash-october-2025-leverage-met-liquidity)

### Inferences
- With 20-100x leverage, a 1-5% adverse move wipes out the position. The same leverage is what makes 5x in a month mechanically possible: at 50x, a +10% underlying move is +500%. The probability of catching the move before a -2% liquidation is the binding constraint (see the ruin math in section 7).
- Hyperliquid's on-chain transparency gives about 14-25% profitable. By inference this is broadly consistent with the ESMA CFD figures (74-89% losing implies about 11-26% not losing).

### Gaps
- No centralized exchange (Binance, Bybit, OKX) publishes a retail profitability share comparable to ESMA's CFD disclosures.
- I found no peer-reviewed study giving the share of crypto perp accounts that achieved 5x+ in a month.

## 4. Retail CFD/forex leverage (ESMA disclosures)

### Takeaway
Regulators found that **74-89% of retail CFD accounts lose money**, with average losses of €1,600-29,000 per client. This prompted ESMA to cap retail leverage at 30:1 to 2:1 from August 2018 and to require brokers to publish their own loss percentages.

### Cited Findings
- ESMA press release, 27 March 2018 (Board decision 23 March 2018): national regulators' analyses show **74-89% of retail accounts typically lose money**, with **average losses per client of €1,600 to €29,000**. Measures: leverage caps of **30:1** (major FX pairs), **20:1** (non-major FX, gold, major indices), 10:1 (commodities and minor indices), 5:1 (single equities) and **2:1 (crypto)**, plus a 50% margin close-out, negative balance protection, a bonus ban and a standardized risk warning. The measures took effect 1 August 2018 and were renewed from 1 November 2018 — [ESMA](https://www.esma.europa.eu/node/84933); [ESMA renewal](https://www.esma.europa.eu/node/86076); [EUR-Lex Decision 2018/796](https://eur-lex.europa.eu/eli/dec/2018/796/oj/eng)
  - Verified on the ESMA page: the full ladder is 30:1 for major FX; 20:1 for non-major FX, gold and major indices; 10:1 for commodities other than gold and for non-major indices; 5:1 for individual equities; 2:1 for crypto.

### Inferences
- The 74-89% figure was measured *before* the leverage caps, when retail could use 100:1-500:1. Higher leverage raises the variance of outcomes, which also raises the probability of hitting a margin close-out before any edge can play out.

### Gaps
- I did not retrieve post-2018 aggregate ESMA or FCA data showing whether loss rates fell after the leverage caps.
- I found no CFTC disclosure for US retail forex in this session.
- Brokers must now display a firm-specific percentage ("X% of retail investor accounts lose money..."). I did not collect current per-broker figures in this session.

## 5. Day trading studies (academic)

### Takeaway
Large administrative-data studies consistently find that **fewer than 1-3% of day traders are reliably profitable**. Most lose money after costs, and there is little evidence that they learn.

### Cited Findings
- **Barber, Lee, Liu & Odean, "The Cross-Section of Speculator Skill: Evidence from Day Trading," Journal of Financial Markets 18 (2014): 1-24.** The study covers Taiwan, 1992-2006, with complete trade records. **Fewer than 1% of day traders are able to predictably profit** net of fees. Top-ranked traders keep earning the next year, while the bottom-ranked group loses — [RePEc](https://econpapers.repec.org/RePEc:eee:finmar:v:18:y:2014:i:c:p:1-24); [eScholarship PDF](https://www.escholarship.org/content/qt7k75v0qx/qt7k75v0qx.pdf?t=ohrd1z)
  - In the related working paper "Learning, Fast or Slow," **97% of day traders can expect to lose money**, and the profitable, experienced group is under 3%. Unprofitable traders keep trading at about the same rate as profitable ones — [PUC-Rio PDF](https://www.econ.puc-rio.br/uploads/adm/seminarios/Learning_fast_or_slow_180606.pdf); [Berkeley working paper](https://faculty.haas.berkeley.edu/odean/papers/day%20traders/day%20trading%20and%20learning%20110217.pdf)
- **Chague, De-Losso & Giovannetti, "Day Trading for a Living?" (SSRN 3423101, 2019):** the study follows 19,646 individuals in Brazil who began day trading mini-Ibovespa futures in 2013-2015. Among those who **persisted for more than 300 days, 97% lost money**. **Only 0.4% earned more than a bank teller (US$54/day)**, and the top individual made about US$310/day. There was no evidence of learning — [IDEAS/RePEc](https://ideas.repec.org/p/fgv/eesptd/525.html); [Quantpedia summary](https://quantpedia.com/retail-day-trading-is-an-uphill-battle/)
  - Note: the 97% figure applies to *persistent* traders (more than 300 days), not all day traders. Viral restatements often drop this qualifier.
  - The abstract (verified) gives the 0.4% against the bank-teller benchmark, not the minimum wage.
- **Jordan & Diltz (2003), "The Profitability of Day Traders," Financial Analysts Journal 59(6): 85-94.** The data cover seven branches of a day-trading brokerage, February 1998 to October 1999. **About twice as many day traders lost money as made money. Only about 20% were "more than marginally profitable"** (RePEc says this means at least $5,000 in day-trading profit). Profitability tracked the Nasdaq Composite. The industry had claimed 60% were profitable after a learning period — [CFA Institute abstract](https://rpc.cfainstitute.org/research/financial-analysts-journal/2003/the-profitability-of-day-traders); [IDEAS/RePEc](https://ideas.repec.org/a/taf/ufajxx/v59y2003i6p85-94.html)

### Inferences
- If fewer than 1% of day traders are *predictably* profitable on an annual basis, the share able to compound at 5x per month is effectively nil. Any 5x month in these populations comes from variance (luck), not edge.

### Gaps
- I did not fetch Jordan & Diltz in this session.

## 6. Trading competitions and documented 5x+ results (survivorship)

### Takeaway
The most famous record, Larry Williams' **11,376% in the 1987 Robbins World Cup**, took **12 months**, not one. The median annual return of a *contest champion* is about 252%. Only three contest years (1985, 1987, 1997) had a winning return above 1,000%. Champions are the maximum of a field of high-variance accounts, so their returns are survivorship outliers, not achievable targets.

### Cited Findings
- **Larry Williams, 1987 Robbins World Cup Championship of Futures Trading:** **+11,376% over 12 months**, about $10,000 → $1.1M. Reported end balances vary ($1,137,600 is the most commonly cited, $1,147,607 per TraderPlanet). It is still the all-time contest record — [Wikiwand: Larry R. Williams](https://www.wikiwand.com/en/articles/Larry_R._Williams); [Complete Traders Edge](https://completetradersedge.com/larry-williams-11376-percent-trading-record/) [promotional-style source]
- **Michelle Williams (his daughter), 1997:** about **1,000%** (1,001%) — [Wikiwand](https://www.wikiwand.com/en/articles/Larry_R._Williams); [TraderPlanet](https://www.traderplanet.com/?p=16791)
- The next-best winning year was **1,283% (1985)**. Only 1985, 1987 and 1997 had returns above 1,000%. The **median champion return is 251.8%/year**, and "a 250% return would have won half of all years" — [CTE Research Sheet, World Cup Trading Championships 2026-11 (PDF)](https://completetradersedge.com/wp-content/uploads/2026/11/CTE-Research-Sheet-World-Cup-Trading-Championships-2026-11.pdf)
- Other named champions include Chuck Hughes, Kurt Sakaeda, Serghey Magala, Patrick Nill and Ivan Scherman. The contest was founded in Chicago in 1983 — [same CTE PDF](https://completetradersedge.com/wp-content/uploads/2026/11/CTE-Research-Sheet-World-Cup-Trading-Championships-2026-11.pdf)

### Inferences
- Even the *best* real-money trader in the field each year typically makes about 2.5x in **12 months**. A 5x+ month for a small account sits well beyond the median champion's *annual* outcome.
- Contests reward variance. Entrants who blow up are not publicized, and winners are selected after the fact, which is classic survivorship.

### Gaps
- I could not verify the size of Williams' intra-year drawdown in 1987 (an unsourced figure of about $2.1M → $700k circulates).
- **I could not find the fraction of Robbins entrants who finish profitable or achieve 5x+.** Robbins does not publish full entrant distributions, and the CTE PDF's charts were not machine-readable.
- I found no reliable statistics for crypto exchange trading competitions (Binance/Bybit "WSOT" leaderboards) on the share of entrants achieving 5x.

## 7. Kelly criterion and ruin math: probability of reaching 6x in a month

### Takeaway
With **no edge** (a fair game), the maximum probability of turning 1 unit into 6 before going broke is about **1/6 (16.7%)**, whatever the strategy (optional-stopping theorem). With realistic costs or a negative edge it is lower, about 10-13% in simulation, with **about 75-93% ending near zero**. Only an implausibly large, sustained edge (a 55% win rate at 1:1 payoff over hundreds of trades in a month) makes 6x more likely than ruin.

### Cited Findings
- **Gambler's-ruin bound (math, no source needed):** for a fair martingale bankroll, P(reach target T before 0) ≤ initial/T. So P(6x) ≤ 1/6 ≈ 16.7%, and **at least about 83% fail to reach 6x**. Ending near zero dominates only when a trader sizes positions large enough to force the target (it is about 73-93% in the over-betting rows below). With small bets, most paths end somewhere between ruin and the target (the 52%/Kelly row has 0.1% ruin but only 5.5% reaching 6x). A negative expected value per bet (fees, spread, funding, house edge) pushes this strictly lower. The "bold play" result (Dubins & Savage) says that in an unfavorable game, betting maximally is optimal for hitting a target, yet the probability is still below 1/6.
- **Kelly:** the optimal fraction for an even-money bet with win probability p is f* = 2p − 1. The expected log-growth per bet is about edge²/2. Reaching 6x needs ln 6 ≈ 1.79 log units. At p = 0.52 (f* = 4%), growth is about 0.0008/bet, so reaching 6x **on median** would take about 2,200 Kelly-sized bets. At p = 0.55 (f* = 10%), growth is about 0.005/bet, about 360 bets (my calculation).
- **Monte Carlo** (my simulation, 200k paths, even-money bets; "ruin" = equity ≤ 10% of start; script at `/tmp/claude-1000/-home-alinvarat/ffbf355d-1f17-4bd1-badf-53bba62610e3/scratchpad/ruin.py`):

| Win prob p | Fraction risked f | Trades in month | Cost/trade | P(≥6x) | P(≤10%, "ruin") | Median end equity |
|---|---|---|---|---|---|---|
| 0.50 | 100% (all-in, 3 doublings) | 3 | 0 | 12.6% (=1/8 for 8x) | 87.4% | 0 |
| 0.50 | 50% | 100 | 0 | 12.7% | 87.3% | 0.08x |
| 0.50 | 20% | 400 | 2% of stake | 10.1% | 89.8% | 0.09x |
| 0.48 (negative edge) | 20% | 400 | 0 | 7.0% | 93.0% | 0.09x |
| 0.52 | 4% (full Kelly) | 400 | 0 | 5.5% | 0.1% | 1.38x |
| 0.52 | 20% (5x Kelly) | 400 | 0 | 26.6% | 72.6% | 0.09x |
| 0.55 | 10% (full Kelly) | 100 | 0 | 15.2% | 0.6% | 1.65x |
| 0.55 | 25% | 100 | 0 | 36.2% | 41.5% | 0.51x |
| 0.55 | 50% | 100 | 0 | 24.9% | 75.1% | 0.08x |
| 0.55 | 10% (full Kelly) | 400 | 0 | 70.7% | 5.6% | 6.14x |

### Inferences
- **The key trade-off:** with a modest real edge (52%), betting Kelly almost never ruins you but reaches 6x in a month only about 5% of the time. Over-betting to "force" 6x raises P(6x) to about 27% but ruins about 73%. Without an edge, no bet sizing beats about 1/6, and costs reduce it to about 10-12%.
- The only scenario where 6x/month is likely (the last row: 55% win rate at even money, 400 independent trades in a month, zero cost) implies an edge far above anything documented for retail in sections 3-5. Fewer than 1% of day traders are predictably profitable *at all*.
- Real markets are worse than this model because of fat tails, gap risk through liquidation prices, funding, and slippage on small-cap tokens.

### Gaps
- The simulation assumes i.i.d. even-money bets. It does not model fat tails, path-dependent liquidation or the convex payoff of memecoins (which resemble lottery tickets: a tiny P(100x), a large P(0)).

### Cross-route summary: realistic upper bound for small retail accounts (synthesis of sections 1-7)

| Route | Measured "success" proxy | Measured near-zero/loss proxy | Source quality |
|---|---|---|---|
| Random pump.fun token | <2% graduate (0.26-8% by period); 1.7% of 2024 tokens actively traded in the last 30 days | 98.6-98.7% flagged rug/P&D (Solidus) | Medium (disputed by pump.fun) |
| pump.fun wallets | ~27% realized profit; 0.4% ≥$10k; 0.05% ≥$100k | 50-60% realized loss; ~96% lose or make <$500 | Medium (Dune, wallet ≠ person) |
| Same-block snipers (insider/deployer-linked) | 87% of trades profitable | — | Low-medium (single analytics firm) |
| Airdrops | avg ~$229 (ZRO), ~$275-308 (JUP 2025) per wallet | 88.7% of 2024 airdrop tokens below listing price at 90 days | Medium |
| Crypto perps (Hyperliquid) | ~14-25% accounts profitable | ~75-86% losing; 14% 3-month survival on consumer apps | Medium (third-party on-chain) |
| EU retail CFDs | ~11-26% not losing (implied) | 74-89% lose (pre-2018 caps) | High (regulator) |
| Day trading | <1% predictably profitable (Taiwan); 3% of persistent traders profitable (Brazil); ~20% more than marginally profitable (US 1998-99) | 97% of persistent traders lose | High (peer-reviewed/admin data) |
| Trading contests | Median champion +252%/yr; record +11,376%/yr | Not disclosed | Medium (survivorship) |
| Ruin math (fair game) | ≤16.7% reach 6x | ≥83% fail to reach 6x; ~73-93% near zero when over-betting to force it (simulation) | Exact math + simulation |

**Bottom line for a small retail account:** no population-level dataset shows a repeatable route to 5x+ in one month. Every documented 5x+ outcome is a right-tail draw from a distribution where most outcomes end in losses. With no edge, at least about 83% fail to reach 6x. Sizing up to force the target turns most of that failure into near-zero outcomes: about 73-93% in the simulation. For any strategy without a real, large edge, the best achievable odds of 6x in a month are about 1-in-6 to 1-in-10.
