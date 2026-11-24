# Real Crypto Traders and On-Chain Wallets with Documented High Returns, 2019-2026

Scope note for the report writer: this file covers **named/pseudonymous traders and public wallets**, what they actually did, and how good the evidence is. It deliberately separates four different things that get conflated in retail media: (a) trading skill on a public order book, (b) airdrop/points windfalls that merely *look* like trading PnL on a leaderboard, (c) one-token lottery tickets, and (d) survivorship-filtered leaderboards. The USD 147 constraint is treated as binding in the last section.

Evidence grades used throughout:

| Grade | Meaning |
|---|---|
| **A** | Per-fill on-chain history, rebuildable and replayable by a third party (Hyperliquid fills, DEX swaps on Solana/EVM) |
| **B** | Account-level on-chain PnL from the venue's own API/leaderboard (aggregate, not per-fill; includes spot price changes and deposits-adjusted PnL) |
| **C** | Press/analyst reporting of on-chain data (Lookonchain, Arkham, OnChainLens, Hypurrscan screenshots) - numbers are usually right, the *selection* is not |
| **D** | Self-reported, interview-based, or exchange marketing |

---

## Q1. Which public on-chain wallets or exchange-leaderboard traders turned a small balance into a large one? Addresses, start/end values, period, assets, leverage, drawdowns, completeness

### Takeaway
The genuinely verifiable "small to large" cases split cleanly into three buckets, and only one of them is trading. Hyperliquid's *all-time PnL leaderboard* is topped by accounts that never traded - they are spot HYPE airdrop recipients whose token appreciation is counted as PnL ($373M-$445M on **$16K lifetime volume**). The largest *actual* trading profits belong to professional firms and market makers with eight-figure balance sheets. The only repeatable small-capital trading case with hard numbers is a maker-rebate bot that turned $6,800 into ~$1.5M - and it required co-located infrastructure. Everything else in the "small to millions" genre is memecoin convexity, i.e. lottery outcomes, or unverifiable self-reporting.

### Cited Findings

**Hyperliquid: full on-chain account history (grade A/B), but the leaderboard is contaminated by spot holders**

| Wallet | Period / window | PnL | Account value | Volume | Read |
|---|---|---|---|---|---|
| `0x4ec8fe22...649a80` | all-time, snapshots 2 Nov & 18-23 Nov 2026 | **+$373.0M to +$445.0M**; daily PnL **+$2** | $153M-$225M | **$16.0K lifetime** | Not a trader. Spot HYPE holder; the "profit" is token price change, which Hyperliquid counts as PnL - [LabelYX](https://labelyx.com/leaderboard), [Hyperkeel](https://hyperkeel.com/leaderboards/), [In-Crypto](https://in-crypto.app/exchange/hyperliquid/accounts), [Totalis](https://www.totalis.trade/blogs/hyperliquid/hyperliquid-top-traders) |
| `0x393d...2109` | all-time, Nov 2026 | +$260.0M | $620.9M | **$0** | Same pattern - [Hyperkeel](https://hyperkeel.com/leaderboards/) |
| `0xdfc2...f303` | all-time, Nov 2026 | +$141.0M | $153.9M | **$0** | Same pattern - [Hyperkeel](https://hyperkeel.com/leaderboards/) |
| `0x9794...333b` | all-time, Nov 2026 | +$144.1M | **$52.55** | $26.4M | ROI +758.7%; account was drained - illustrates that "all-time PnL" is cumulative, not current equity - [Hyperkeel](https://hyperkeel.com/leaderboards/) |

- Hyperliquid's own footnote: "Excludes accounts with less than 100k USDC account value and less than 10M USDC trading volume"; ROI = PnL / max(100, starting account value + maximum net deposits) - [Totalis snapshot of the official page, 2 Nov 2026](https://www.totalis.trade/blogs/hyperliquid/hyperliquid-top-traders).
- Totalis explicitly flags the artefact: "Several top PnL accounts showed no trading volume in the same window, and a tiny starting balance can inflate ROI into the millions of percent" - [Totalis](https://www.totalis.trade/blogs/hyperliquid/hyperliquid-top-traders).
- Blockmetric states it filters rows where "PnL of that window [is] at most 20x its volume (a larger PnL does not come from trading in that window but from held tokens or airdrops)" - [Blockmetric methodology](https://blockmetric.io/traders).
- Only **14.5% of 46,802 listed accounts were up over 30 days** (snapshot 23 Nov 2026); the leaderboard lists only *active* accounts, so this is not a population win rate - [Underhyper](https://underhyper.com/data/leaderboard/). HyperScan reports 2,679 of 6,741 accounts with $100K+ in profit over 30 days (40%) - [HyperScan](https://hyperscan.online/leaderboard).

**The actual top trading accounts (still on-chain, still pseudonymous)**

| Wallet / label | Window | PnL | Account value | Volume | Win rate | Max DD | Avg hold | Notes |
|---|---|---|---|---|---|---|---|---|
| `0x5b5d51203a0f9079f8aeb098a6523a13f298c060` ("Abraxas Capital", owner-set, unverified) | 30d Nov 2026 | +$121.3M | $6.38M | $835M | 93% | −16% | 12d 23h | All-time +$311M; Sharpe 5.2; ROI 30d +74% - [Blockmetric](https://blockmetric.io/traders), [Thrive](https://thrive.fi/leaderboards/hyperliquid) |
| `0xb83de012dba672c76a7dbbbf3e459cb59d7d6e36` | 30d Nov 2026 | +$100.5M | $7.14M | $835.6M | 88% | −13% | 12d 8h | All-time +$241M; ROI +65% - [Blockmetric](https://blockmetric.io/traders) |
| `0x7fdafde5cfb5465924316eced2d3715494c517d1` ("BobbyBigSize") | 30d Nov 2026 | +$35.5M | $26.4M | $2.15B | 71% | −13% | 3d 20h | All-time +$176-181M; Sharpe 10.2; style tagged "position, high leverage" - [Blockmetric](https://blockmetric.io/traders), [HyperScan](https://hyperscan.online/leaderboard) |
| `0x87f9cd15f5050a9283b8896300f7c8cf69ece2cf` | 30d Nov 2026 | +$40.1M | $115M | $24.9B | - | - | - | High-turnover; all-time PnL +$98M to +$101M per other trackers - [Underhyper](https://underhyper.com/data/leaderboard/), [HyperScan](https://hyperscan.online/leaderboard) |

- Note the structural tell: the top PnL accounts hold $6-7M while having made $240-311M. Hyperliquid's PnL is deposit/withdrawal-adjusted, so this means continuous profit withdrawal, not compounding - the opposite of the "small account compounded" narrative - [Blockmetric](https://blockmetric.io/traders).

**The one small-capital trading case with a clean, repeatable mechanism**

- Hyperliquid wallet `0x6f90...336a`: two deposits in **early February 2024**, **$6,800** total, grew to **>$1.5M realised**. Generated **$20.6B** in volume, >3% of *all* maker volume on the exchange, at times $1.4B in 14 days. *Timeline caveat: the source mixes an "early February 2024" start with a "14 days / $1.4B" burst, so the $1.5M may be a 14-day figure rather than the full-life total; the $20.6B lifetime volume is unambiguous.* Net exposure kept **below $100,000**; max drawdown **6.48%**. Strategy: one-sided passive quoting (bids *or* asks, never both), bot cancels/switches sides, delta-neutral, income = maker rebate (−0.003% at tier 3) plus spread - [BeInCrypto, 27 Jun 2025](https://beincrypto.com/hyperliquid-trader-earns-millions-from-maker-strategy/), [Bitget/Foresight translation](https://www.bitget.com/news/detail/12560604969577).
- Arithmetic check published with the story: $1.4B × 0.003% ≈ **$420K** of rebate in two weeks; the remaining ~$1.1M came from spread/position PnL and reinvestment - [Bitget/Foresight](https://www.bitget.com/news/detail/12560604969577).
- Hyperliquid rebate tiers are a *share of exchange maker volume*, not own volume: >0.5% → −0.001%, >1.5% → −0.002%, >3.0% → −0.003%. With ~$77B of exchange volume per 14 days, 0.5% ≈ **$385M of maker volume per fortnight** - [Hyperliquid docs, Fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees), [Hyperliquid Guide](https://hyperliquidguide.com/guides/trading/hyperliquid-market-making-guide).

**Aggressive directional small/mid-capital cases (grade C, press-reported from chain data)**

| Trader | Start | Peak | Realised end | Leverage | Period | Source |
|---|---|---|---|---|---|---|
| `0x15b3` | $125,000 (May 2025) | **$43M equity / $303M notional** (344x paper) | **$6.86M** (55x), then re-entered 25x and lost **$6.22M in 2 days** → $771K | 20-30x estimated | May-Aug 2025 | [TradingView/Cointelegraph](https://www.tradingview.com/news/cointelegraph:88c0232ea094b:0-how-one-trader-turned-125k-into-43m-on-ether-and-what-you-can-learn-from-it/), [DeepNewz](https://deepnewz.com/markets/trader-0x15b3-turns-125k-into-29-6m-66749-eth-long-on-hyperliquid-later-losing-6-ec5fb9f0) |
| Unnamed wallet | ~$3M deposited 7-9 Apr 2025 | +$27.5M in 52 days, $22M unrealised | $6M withdrawn, ~$10M available | ">40% of available margin used", 100% long | Apr-May 2025 | [Cointelegraph](https://cointelegraph.com/news/hyperliquid-trader-3m-to-27m-crypto-rally) |
| GCR ("Gigantic-Cassocked-Rebirth") | ~$1,000 (2020) | est. $400M-$1B net worth | n/a | n/a | 2020-2022 | Grade **D/B** - see below |
| `0xRay518` (Taiwanese, 19 in 2025) | $3,000 (2020, shipping stocks) → wiped → Arbitrum airdrop | ~RMB 100M+ claimed | n/a | 1x on TRUMP, then Hyperliquid | 2020-2025 | Grade **D** - [BlockTempo](https://www.blocktempo.com/19-year-old-taiwanese-high-school-student-makes-over-100-million-rmb-trading-crypto/) |

- GCR: repeatedly top of the **FTX** PnL leaderboard 2021-22; the $1k→$1B figure is explicitly anecdotal in the better sources ("this $1B figure is anecdotal", "estimated net worth... while impressive, is unauditable"). Verifiable fragments: `ezekielx.eth`, a ~$2M Sad Doge NFT sale, 300+ Milady NFTs bought on Blur in Q1 2023, and a **$4M USDT→USDC swap during the March 2023 USDC depeg** (~12-13% if it re-pegged) - [CryptoZ](https://www.cryptoz.ink/posts/gcr-trader-billionaire), [Phemex Academy](https://phemex.com/academy/who-is-gcr-crypto-anonymous-trader-journey), [Directions Mag](https://www.directionsmag.com/crypto/gcr-crypto-trader). His LUNA short: $10M bet with Do Kwon escrowed by Cobie plus $10M of FTX perps; "final realized profit... was never presented as a clean, audited number" - [Directions Mag](https://www.directionsmag.com/crypto/gcr-crypto-trader).
- 0xRay518's own account of the sequence, given to OKX: $3,000 → ~$300K on 2020 shipping stocks → near-zero on leverage → NFT/airdrops → **Arbitrum airdrop as first real capital** ("a few thousand dollars of cost for tens of thousands") → $1M TRUMP position at $6-7, exited at 3-4x → one year of Hyperliquid points/volume farming, then concentrated into HYPE at launch. OKX **pulled the article within 24h** after backlash over survivorship bias - [BlockTempo](https://www.blocktempo.com/19-year-old-taiwanese-high-school-student-makes-over-100-million-rmb-trading-crypto/).

**Passive/protocol case that is fully auditable: HLP**

- HLP (Hyperliquidity Provider), vault `0xdfc24b077bc1425ad1dea75bcb6f8158e10df303`: **+$140.9M-$141.1M all-time PnL since May 2023**; TVL peaked at $603.9M (3 Sep 2025), $149-152M in Nov 2026; **max drawdown 5.8%** on a return index - [NuWealth](https://nuwealth.ai/blog/hlp-vault-returns), [LabelYX HLP page](https://labelyx.com/hlp), [PerpVault](https://perpvault.com/hyperliquid-vaults).
- Return is extremely lumpy: **$60.3M of the $140.9M (43%) came from two 14-day stretches** (1-15 Oct 2025: +$41.4M; 21 Jan-4 Feb 2026: +$18.8M), both containing liquidation cascades. The other 28 stretches since Oct 2025 added ~$0.3M combined - [NuWealth](https://nuwealth.ai/blog/hlp-vault-returns).
- APR figures conflict across trackers: 17.3% (LabelYX, 22 Nov 2026), 19.8% on Hyperliquid's own vault list (16 Nov 2026, a 30-day figure), and 54.8%/yr flow-adjusted over 3.5y (PerpVault). The 2025 calendar-year gain was ~19%, 2026 to mid-Nov ~9.5% - [LabelYX](https://labelyx.com/hlp), [NuWealth](https://nuwealth.ai/blog/hlp-vault-returns), [PerpVault](https://perpvault.com/hyperliquid-vaults).

**Memecoin convexity cases (grade A on-chain but pure lottery; realised vs unrealised matters)**

| Case | Cost | Value | Period | Realised vs paper | Source |
|---|---|---|---|---|---|
| CHILLGUY wallet `9zW...` | **$233.89** first buy, ~$1,101 total | >$1.1M claimed | 30 hours to first 38,800%, then days | **$411,500 sold + ~$700,000 still held** at time of writing - i.e. mostly unrealised | [TechFlow/Decrypt](https://techflowpost.com/en-US/article/21753) |
| "114514" wallet `8BGiMZ` | **$321** | $2.18M (6,800x) | 11 days, Jan 2026 | "no large outbound transfers" - **entirely unrealised** | [CryptoNews](https://cryptonews.com/news/trader-turns-321-into-2-18m-in-just-11-days-with-this-solana-memecoin/) |
| URO + RIF trader | $768 + $300 = ~$1,068 | $1.62M | 20 days, Nov 2024 | $94,335 USDC realised on RIF; rest paper | [Finbold/Lookonchain](https://finbold.com/cryptocurrency-trader-turns-1-1k-into-1-62-million-in-20-days/) |
| LIBRA top sniper | n/a | **+$6.5M** | 43 minutes, 14 Feb 2025 | not disclosed; wallet funded by a Bybit wallet and a bot wallet | [The Block/Nansen](https://www.theblock.co/news/business/2025-02-19-traders-of-solana-based-libra-memecoin-lost-251-million-nansen-342266) |
| BNB "diamond hand" `0x850...` | $1,000 (2017, ~$1/BNB) | >$1M | 8 years | still holding at $1,005 ATH, Sep 2025 | [Cointelegraph/Lookonchain/Nansen](https://cointelegraph.com/news/bnb-investor-turns-1k-into-1m) |

**Prediction markets (fully on-chain, different mechanism)**

- Polymarket wallet "RN1": **$1,000 → >$2M in 2025**, >13,000 sports trades, single best trade +$129,000, described as AMM price-discrepancy arbitrage/HFT rather than outcome forecasting - [Phemex News](https://phemex.com/news/article/smart-money-rn1-nets-2m-on-polymarket-from-1k-investment-49297). **Single secondary source citing an influencer; treat as unverified.**
- Population baseline: only **15.9% of ~2.5M Polymarket traders are in profit**; 2% made >$1,000 lifetime; 0.033% made >$100,000 - [Sergeenkov, Dune-based](https://sergeenkov.com/polymarket-profitability/). Galaxy: 69.2% of 2.9M retail accounts below break-even, aggregate −$338.9M - [Galaxy Research](https://www.galaxy.com/insights/research/polymarket-trader-behavior-onchain-analysis-retail-profit-loss-specialization).

### Inferences
- A Hyperliquid all-time PnL screenshot is **not evidence of trading skill** without the volume column. Any account with PnL/volume > ~5 should be assumed to be holding spot tokens (usually HYPE) rather than trading.
- "Small to large" trading outcomes that survive scrutiny share one feature: the trader had an *infrastructure or information edge* (co-located maker bot, market-maker status, exchange relationships), not a chart pattern. The $6,800 → $1.5M case is the cleanest proof and it is un-copyable at retail latency.
- The famous directional runs ($125K → $43M, $3M → $27M) are leverage-and-trend outcomes inside a 4-month window; both are reported with explicit warnings that a single adverse move erases them, and in the 0x15b3 case that is exactly what happened 2 days later.

### Gaps
- No source gives a **complete per-fill, all-time dataset** for any of the large directional traders; Hyperliquid's public API gives aggregates, and third-party rebuilds (Ironflow, Trade Replayer) cover windows, not full history.
- The identity attributions ("Abraxas Capital", "BobbyBigSize") are owner-set display names and explicitly unverified.
- No documented case of a **sub-$1,000 account** compounding to $1M+ through *sustained trading* (as opposed to one token or one airdrop) was found in any source.
- FTX-era leaderboard records (GCR, Alameda-adjacent accounts) are **gone**; no archive with full PnL tables was located.

---

## Q2. What methods did they use? Exact rules where known

### Takeaway
Six mechanisms account for essentially all documented high returns: (1) perp directional leverage with compounding, (2) maker-rebate market making, (3) liquidation/oracle manipulation ("self-liquidation"), (4) funding/basis carry, (5) airdrop/points farming, (6) new-token sniping and first-leg memecoin rotation. Only (4) and (6) have published, mechanical rule sets that a small account could implement; (2) and (3) are capital- and infrastructure-gated; (5) has been largely closed by sybil filtering.

### Cited Findings

**Perp momentum / leveraged directional (grade A-C, rule set is trivial and that is the problem)**
- James Wynn: 40x long BTC, scaled from $830M notional (7,764 BTC @ $105,033, 21 May 2025) to **$1.25B (11,588 BTC @ $108,243, 24 May)**; liquidation prices within 2-3% of entry; re-opened after each partial liquidation at worse break-even - [The Block](https://www.theblock.co/news/ecosystems/2025-05-30-hyperliquid-trader-james-wynn-hit-with-over-100-million-loss-as-leveraged-bitcoin-trade-unravels-356341), [CoinDesk](https://www.coindesk.com/markets/2025/06/02/how-james-wynn-s-usd100m-implosion-is-a-leverage-tale-as-old-as-time).
- Machi: 21.5x-40x, "100% long exposure", 15x-25x ETH longs, repeated re-entry after each liquidation; 335 separate liquidation events by Mar 2026 - [BeInCrypto](https://beincrypto.com/machi-big-brother-liquidations-hyperliquid-loss/), [CoinTelegraph](https://cointelegraph.com/news/machi-big-brother-44m-profit-10m-loss).
- AguilaTrades: fixed-size 4,000 BTC longs (>$400M notional), no take-profit at +$5.6M/+$10M/+$3.2M unrealised, then liquidated; win rate **37.5% over 64 trades**, best trade +$22.8M, worst −$19.9M; **without the 5 best trades the record is −$70.5M** - [Trade Replayer (per-fill rebuild)](https://trade-replayer.com/traders/aguila-trades/), [CryptoPotato](https://cryptopotato.com/heres-how-bitcoin-volatility-cost-a-veteran-swing-trader-35m/).

**Maker-rebate market making (grade A, exact rules)**
- Rules as reported for `0x6f90...336a`: (i) quote **one side only** at a time; (ii) cancel/re-quote within milliseconds; (iii) hard cap net position at **$100K**; (iv) on approaching the cap, stop quoting that side and flip; (v) reinvest rebates immediately; (vi) run from a server physically close to Hyperliquid's; (vii) stay in perps only (single venue, no spot leg) - [BeInCrypto](https://beincrypto.com/hyperliquid-trader-earns-millions-from-maker-strategy/), [Bitget/Foresight](https://www.bitget.com/news/detail/12560604969577).
- Economics: base tier maker fee 0.015%, taker 0.045%; maker fee reaches **0% at $500M/14d volume** and only turns into a rebate above **0.5% of exchange maker volume** - [Hyperliquid docs](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees). Adverse selection ("being arbitraged") is the named failure mode - [Bitget/Foresight](https://www.bitget.com/news/detail/12560604969577).

**Liquidation hunting / self-liquidation (grade A, court-documented in one case)**
- Mango Markets, 11 Oct 2022: deposit ~**$5M USDC into two wallets**; sell MNGO perps in one, buy in the other (holding both sides); buy MNGO spot on the **three venues feeding the oracle** (FTX, AscendEX, Serum); oracle price +700% in 14 minutes (Bloomberg: +1,300% in 20 minutes); borrow against the inflated long; dump MNGO spot to collapse the oracle; borrow against the inflated short; withdraw **>$100M** - [SDNY Opinion & Order, 23-cr-10](https://www.nysd.uscourts.gov/sites/default/files/2025-05/23cr10%20Opinion%20and%20Order.pdf), [DOJ](https://www.justice.gov/archives/opa/pr/man-convicted-110m-cryptocurrency-scheme).
- JELLY, 26 Mar 2025: three accounts deposited **$7.17M in minutes**; $4.1M short + $2.15M and $1.9M longs; margin removed from the short to push it into HLP; JELLY spot pumped on thin DEX liquidity (to ~$0.50); HLP unrealised loss **−$13.5M**; Hyperliquid validators delisted and force-settled at **$0.0095**; attackers left with a small loss (~$6.26M withdrawn of $7.17M deposited) - [Arkham](https://arkm.com/research/jellyjelly-exploit-on-hyperliquid), [CoinDesk](https://www.coindesk.com/markets/2025/03/26/hyperliquid-delists-jellyjelly-after-vault-squeezed-in-usd13m-tussle), [Blockworks](https://blockworks.com/news/hyperliquid-decentralization-validator-put).

**Funding / basis carry (grade A backtests, exact rules)**
- Binance BTC/ETH/SOL, $100K spot + $100K coin-margined perp short, no extra leverage, Aug 2020-13 Nov 2026, fees included: **BTC +$59,279 (7.7%/yr income-as-cash, 9.9% reinvested), ETH +$58,610 (7.7-9.8%), SOL −$13,877 (−2.8%/yr), SOL max drawdown −44.5%** - [InvestWealth six-year backtest](https://www.investwealth.com/learn/guides/crypto-basis-trade).
- Cost math: 4 taker legs ≈ **0.38% round trip** (10bp spot + 5bp perp + 2bp slippage, ×2); at 0.01%/8h funding that is **12.7 days to break even** - [BlofinX](https://www.blofinx.com/learn/is-funding-rate-carry-still-profitable).
- Edge compression: gross BTC funding 30.61%/yr (2021) → 11.92% (2024) → **5.13% (2025) → 2.43% (2026 to 24 Aug)**; share of 8h periods clearing a 0.01% entry bar fell from 86.0% (2021) to **5.5% (2026)**; measured net strategy return **+4.7%/yr** - [BlofinX](https://www.blofinx.com/learn/is-funding-rate-carry-still-profitable).
- Binance monthly annualised funding in 2026: Feb −0.83% (BTC), Mar −1.09%, Apr −2.16% — i.e. the short-paid side flipped for three months - [Upshift](https://www.upshift.finance/blog/funding-rate-arbitrage).
- Cross-venue funding spreads: 17% of observations show ≥20bp spreads, but **only 40% of top opportunities are profitable after costs**, and **12 of 20** simulated delta-neutral portfolios were forced out at a loss; average net PnL across 20 portfolios **$22** on $10K/side - [MDPI, 26 exchanges, 749 symbols](https://www.mdpi.com/2227-7390/14/2/346).

**Airdrop / points farming (grade B-D, rules known, outcomes now diluted)**
- Hyperliquid: two points seasons (Nov 2023-May 2024 ~1M pts/week; May-Sep 2024 ~700k/week), weighted to perp volume, maker activity, referrals, spot volume, HLP deposits; Season 1 points worth more per dollar of volume than Season 2; **>27,000 addresses across ~100 entities** had points cut to 2% or 20% for sybil behaviour - [Odaily/Bitget](https://www.bitget.com/en-CA/news/detail/12560604390337), [AirdropStat case study](https://airdropstat.com/articles/hyperliquid-hype-airdrop-case-study.html).
- Distribution: 310M HYPE allocated (31% of supply), **274.15M actually claimed by 94,028 wallets**; mean 2,915.66, **median 64.53**; 56.6% received ≤100 HYPE; top 147 wallets got 262K-1M HYPE - [PANews/ASXN](https://www.panews.io/articles/1m37x8gd), [Odaily](https://www.bitget.com/en-CA/news/detail/12560604390337).
- The "multi-product" rule, from a farmer's own three wallets: $12K capital across spot+perp+HLP+vaults for 8+ months → ~24,500 HYPE; $4K spot+perp only → ~4,800 HYPE; **$800 perp-only, opened 6 weeks before snapshot → ~820 HYPE, "after gas and the bridge cost, this was a slight loss"** - [AlphaGain diary](https://alphagaindaily.com/en/blog/hyperliquid-season-2-airdrop-farming-guide) (grade D, self-reported).
- Sybil filtering intensity elsewhere: Linea removed **516,960 of 1,297,203** otherwise-eligible addresses (~40%; another source says 654,443 = 50.45%); LayerZero: **1.28M of 6M users eligible (~21%)**, >800,000 flagged; Arbitrum scored addresses and docked points for ≥8 transactions in 48h or dust balances - [Does It Pay? airdrop research](https://doesitpay.org/airdrop-farming/research/), [Dificalc](https://dificalc.com/blog/defi-airdrop-farming-2026).

**New-token sniping and memecoin rotation (grade A data, negative-expectancy rules)**
- Execution stack: private Jito bundles (all-or-nothing, up to 5 tx), tips by percentile — **median 0.0001-0.0003 SOL, 75th 0.001-0.003, 95th 0.005-0.015, 99th 0.05-0.25 SOL**; priority fee 0.0005-0.002 SOL normal; base fee 5,000 lamports/signature; **failed transactions are still charged**; token-account rent 0.00203928 SOL - [TierZero Jito cost breakdown](https://tierzero.dev/blog/jito-bundle-tips-cost-breakdown-solana-mev), [SnipeMint](https://www.snipemint.com/solana-sniper-bot-cost).
- Who actually wins: in FOMO-app coins with ≥1,000 buyers, **the first 10 buyers made +71% on spend; from the 1,001st buyer onward, buyers lost 11%**; median hold time for a Solana memecoin in 2026 was **58 seconds** (down from ~1 day in 2024) - [Bitquery](https://bitquery.io/investigations/fomo-app-traders-lose-money).
- Ray's stated rule (grade D): only trade the **first leg** of a narrative ("I never touch the second leg"), exit into 3-4x, never hold for the full move - [BlockTempo](https://www.blocktempo.com/19-year-old-taiwanese-high-school-student-makes-over-100-million-rmb-trading-crypto/).
- Bot economics: most tools charge **~1% per snipe** (Axiom 0.95%, Banana Gun 1%), pump.fun curve fee **1.25%** per trade, and a competitive setup needs a co-located RPC at **$800-2,500/month** (full team $4,800-13,500/month) - [Memecoin Guru](https://memecoin.guru/best/sniper-bots), [TierZero build cost](https://tierzero.dev/blog/cost-to-build-solana-sniper-bot-from-scratch), [TrenchBay](https://trenchbay.com/blog/what-is-a-pump-fun-bundler/).

**Copy trading as a "method" (grade A statistical studies, negative result)**
- Audit of the OKX and Binance lead-trader boards (top 100 by profit each, fetched 15 Oct 2026): **0 of 180 lead traders clear the statistical bar for being picked off the board**; ~1 in 10 passes a single t-test; OKX #1 by PnL ($2.2M) has t = 0.03 over 365 days - [Evidence Deflator audit 007](https://evidencedeflator.com/audits/007-cex-copy-trading.html).
- CHI '24 peer-reviewed study of Bybit + TraderWagon (Oct 2022-Aug 2023): leaderboard position is driven by UI defaults, not future returns; **the majority of "Gold" portfolios collapse in the rankings within about a week of promotion** (some as early as two days); the bottom 25% of Gold portfolios produced **losses >$15,000 within 10 days** for copiers; leaders can hedge across sub-accounts and copy themselves to inflate follower PnL - [Kawai et al., CHI 2024](https://dl.acm.org/doi/full/10.1145/3613904.3642715).

### Inferences
- The methods with published exact rules (basis carry, first-leg sniping) are the ones with the *worst* current economics: carry is at 2.4%/yr gross in 2026 and sniping is a 1%-per-side fee race against co-located bots.
- The methods with the best documented returns (rebate MM, oracle/liquidation games) are gated by either **$385M/fortnight of maker volume** or **$5-8M of capital plus a thin oracle**.
- Directional perp trading "works" in these case studies only as a convexity bet during a trending window; the same rule set produces the blowups in Q4.

### Gaps
- No public source documents a *profitable* retail rule set for liquidation hunting after Hyperliquid's JELLY fix (the "validator put") and Mango's collapse.
- Airdrop farming ROI after costs is not measured by any dataset found; "Does It Pay?" explicitly says "We found no dataset showing what share of farmers end up ahead after fees and time" - [Does It Pay?](https://doesitpay.org/airdrop-farming/research/).
- No verified source on the internal rules of the top Hyperliquid market makers (spread width, inventory skew, cancel thresholds).

---

## Q3. How much of the PnL is airdrops, incentives, wash trading, insider allocations or one lucky token? Separating skill from luck/survivorship

### Takeaway
For the *headline* numbers, most of it is not trading. The largest "trader" PnLs on Hyperliquid are spot airdrop appreciation; the largest memecoin fortunes are single-token convexity with insider/sniper advantage; and the population base rates are brutal (≈6% of memecoin traders profitable, ≈15% on Polymarket, ≈14.5% of active Hyperliquid accounts up over 30 days). Copy-trading boards are statistically indistinguishable from luck. The honest decomposition of any viral PnL screenshot is: airdrop or one token (most), leverage in a trend (some), infrastructure edge (rare), skill (unproven at the individual level).

### Cited Findings

**Airdrop share of "trading" PnL**
- HYPE genesis: 310M allocated / 274.15M claimed, 94,028 wallets, worth **~$1.18-1.2B at launch**; the average 2,882-HYPE bag raised **~$18K** if sold on day one and was worth **~$187K on 20 Nov 2026** (~$280K at the September 2026 peak) - [The Block](https://www.theblock.co/news/markets/2024-11-29-hyperliquid-airdrops-over-1-2-billion-worth-of-tokens-to-users-as-hype-crosses-4-billion-fdv-328769), [DropsTab](https://news.dropstab.com/latest/hyperliquid-hype-airdrop-value-nov-2024).
- No VC allocation, no team allocation in genesis, 1-year cliff on the 23.8% contributor bucket - [Hyper Foundation medium](https://hyperfnd.medium.com/hype-genesis-1830a4dc2e3f).
- Referral effect: a single public closed-alpha code ("ALPHA") referred 2,749 accounts; **1,490 of them received 28.56M HYPE = 9.2% of the entire airdrop**, worth $111M at launch and ~$2.31B at $80.93 - [HyperliquidNews](https://hyperliquidnews.xyz/alpha-code-hyperliquid-team-referred-new-whales).
- A concrete case where non-trading activity dominated: `0x5cc7...aa34` traded only **$598K** but received **691,292 HYPE**, because it deposited $500K into HLP in Oct 2023 and another $315K in Jan 2024 - [HyperliquidNews](https://hyperliquidnews.xyz/alpha-code-hyperliquid-team-referred-new-whales).

**One-token / insider share of memecoin PnL**
- LIBRA (14 Feb 2025): 15,431 wallets traded; **86% realised losses totalling $251M**; 2,101 profitable wallets made **$180M**; two wallets that bought at 22:01 UTC and sold by 22:44 made **>$5.4M**; one sniper made **$6.5M**, funded by a Bybit wallet plus a bot wallet; 1,001 wallets still held with ~$11M unrealised losses - [Nansen via The Block](https://www.theblock.co/news/business/2025-02-19-traders-of-solana-based-libra-memecoin-lost-251-million-nansen-342266), [CoinDesk](https://www.coindesk.com/markets/2025/02/20/libra-memecoin-fiasco-destroyed-usd251m-in-investor-wealth-research-shows). Nansen's own framing: "net-negative wealth-generating" - [Decrypt](https://decrypt.co/307025/some-wallets-still-trading-libra-despite-251-million-losses-nansen).
- TRUMP token: **988,905 wallets lost money (~two thirds of all buyers), totalling $3.81B** (Nansen, July 2026, as summarised by a secondary source) - [Orca Crypto summary](https://orcacrypto.io/learn/memecoins/). *Secondary aggregation; primary Nansen post not located.*
- Memecoin population base rate: 90 days to Aug 2026, **19,003 of 304,161 Solana memecoin traders profitable = 6.25%**; **88% of the profitable made under $100**; median trader lost $120; only **25 wallets made >$10,000** - [Cryptopolitan/Dune](https://www.cryptopolitan.com/6-solana-meme-traders-profit-in-90-days/). Base, Feb-Jun 2024, independent: **6.6% of addresses profitable** (GoPlus) - [Orca Crypto](https://orcacrypto.io/learn/memecoins/).
- Fee drag alone flips outcomes: FOMO app, 13 Jan-7 Oct 2026, 829,539 wallets: **15% were ahead before fees, 10% after**; 94% of all winnings went to the best 1% of wallets; median wallet lost $25 on $130 deployed - [Bitquery](https://bitquery.io/investigations/fomo-app-traders-lose-money).

**Wash trading and incentive farming**
- NBER working paper 30783 ("Wash Trading in Crypto Markets"): wash trades average **>70% of reported volume on unregulated exchanges** (~61% after controls; **53.4% Tier-1, 81.7% Tier-2**), i.e. trillions of dollars/year - [NBER w30783](https://www.nber.org/system/files/working_papers/w30783/w30783.pdf).
- Hyperliquid's own sybil action: **>27,000 addresses across ~100 entities** detected trying to farm points at scale, points multiplied by 2% or 20% - [Odaily](https://www.bitget.com/en-CA/news/detail/12560604390337).
- Coingecko's Pump.fun study explicitly warns that "bot and wash trading activity has not been filtered out, which may inflate wallet counts and trading volumes", and counts only realised PnL (excluding bagholders) - [CoinGecko](https://www.coingecko.com/research/publications/pump-fun-traders-are-making-a-comeback).

**Survivorship: the leaderboard is the sample, not the population**
- Hyperliquid: 46,802 listed accounts, **14.5% up over 30 days**; "the leaderboard only lists active accounts, so this is not a win rate for everyone who trades" - [Underhyper](https://underhyper.com/data/leaderboard/).
- LabelYX states the problem directly: "Traders who took the same risks and were wrong do not appear at the bottom of this list - they are not on it at all" - [LabelYX](https://labelyx.com/leaderboard).
- Copy-trading: 0/180 top-100 lead traders clear the "best of N" significance bar; "the boards are not full of bad traders, they are full of records that cannot be told apart from luck" - [Evidence Deflator](https://evidencedeflator.com/audits/007-cex-copy-trading.html).
- Polymarket: top 1% of profitable users capture **76.5%** of profits (588M trades, $67B volume); "monthly performance is modestly persistent, however this may represent sample selection rather than skill" - [CEPR DP21615](https://cepr.org/publications/dp21615). Another reconstruction: top 1% of wallets = 89.2% of positive returns, 68.66% of 1.54M wallets negative - [arXiv 2610.34754](https://arxiv.org/abs/2610.34754).
- Even the exchange's own marketing case is filtered: the OKX interview with the 19-year-old was **removed within 24 hours** after community criticism of "survivorship bias" - [BlockTempo](https://www.blocktempo.com/19-year-old-taiwanese-high-school-student-makes-over-100-million-rmb-trading-crypto/).

### Inferences
- A defensible rule of thumb from the data: if a claimed PnL exceeds ~5x the account's traded volume, assume airdrop/spot-hold; if a memecoin PnL comes from one token bought in the first minutes, assume sniper/insider positioning; if a perp PnL comes from one quarter, assume trend + leverage, not process.
- The cleanest genuine-skill datapoint in the whole corpus is the maker-rebate wallet: 3% of exchange maker volume, 6.48% max DD, 220x. It is skill, and it is also a full-time engineering business.
- Reported "average airdrop $20K" is a mean corrupted by 147 wallets holding 262K-1M HYPE; the median participant got ~$400. Any plan built on "airdrop = $20K" is built on the tail.

### Gaps
- No source decomposes a single named trader's PnL into trading vs airdrop vs incentive components; even Hyperliquid's API does not tag PnL by source ("The leaderboard does not break PnL down by source") - [Totalis](https://www.totalis.trade/blogs/hyperliquid/hyperliquid-top-traders).
- The Nansen TRUMP number ($3.81B lost by 988,905 wallets) could only be verified through a secondary summary.
- Nobody has published a survivorship-corrected return distribution for Hyperliquid perp traders (only the 14.5%/30-day snapshot).

---

## Q4. Which cases blew up or lost most of the gains? Exchange failures, hacks, delistings, funding flips

### Takeaway
Every high-leverage case in this sample eventually gave back more than it made, and the give-back happened in days, not years. The recurring pattern is not "bad market" but **position size relative to venue depth plus re-entry after partial liquidation**. Two structural risks also destroyed capital without any trading error: exchange failure (FTX, $8B hole) and protocol-level intervention (Hyperliquid's JELLY delisting and forced settlement at an arbitrary price).

### Cited Findings

**Trader blowups (all grade C, chain-analyst reported)**

| Trader | Peak | Final | Mechanism | Time to lose it |
|---|---|---|---|---|
| James Wynn (`0x507...`) | ~$100M unrealised (some reports $85M-$87M) | **−$17.5M net; $23 left in account** | 40x BTC long $1.25B; 949-1,044 BTC liquidated at $104,150-$104,950 while BTC moved ~2% | ~1 week (24-30 May 2025) - [CoinDesk](https://www.coindesk.com/markets/2025/05/31/cryptos-most-watched-whale-gets-fully-liquidated-after-placing-billions-in-risky-bets), [DL News](https://www.dlnews.com/articles/defi/hyperliquid-whale-loses-100m-on-leveraged-bitcoin-bet/) |
| Machi (`0x020c...`) | **+$44.84M** unrealised (Sept 2025) | **−$75.19M realised** by Mar 2026; $30,268 left; 335 liquidations | 21.5-40x ETH longs, 100% long, re-lever after each liquidation | 6 months - [BeInCrypto](https://beincrypto.com/machi-big-brother-liquidations-hyperliquid-loss/), [Arkham](https://dailycoin.com/crypto-trader-machi-big-brother-hyperliquid-losses/) |
| AguilaTrades | +$3M after clawing back from −$35M | **−$32M to −$40M** | 720 BTC ($83.3M) long liquidated 25 Jul 2025; 4 consecutive liquidations | 2 months - [BeInCrypto](https://beincrypto.com/aguilatrades-crypto-liquidation-40-million/) |
| `0x15b3` | $43M equity / 344x paper | **$6.86M realised → then −$6.22M in 2 days → $771K** | re-entered at 25x immediately after closing | 2 days - [DeepNewz](https://deepnewz.com/markets/trader-0x15b3-turns-125k-into-29-6m-66749-eth-long-on-hyperliquid-later-losing-6-ec5fb9f0) |
| qwatio | +$6.8M | **−$10M** | perp reversal | weeks - [TradingView/Cointelegraph](https://www.tradingview.com/news/cointelegraph:88c0232ea094b:0-how-one-trader-turned-125k-into-43m-on-ether-and-what-you-can-learn-from-it/) |
| "14-win-streak" trader | +$33M | **−$30.2M** | leverage | - [Cryptopolitan](https://www.cryptopolitan.com/high-leverage-trading-cost-7-traders-fortune/) |
| Unnamed biggest loser | - | **−$45.3M realised** | leverage | - [Cryptopolitan](https://www.cryptopolitan.com/high-leverage-trading-cost-7-traders-fortune/) |

- Machi's numbers conflict across sources: Arkham/BeInCrypto report **−$75.19M** realised over the six months to Mar 2026; Lookonchain/ETtoday report **~−$37.11M cumulative since May 2025** as of 30 Oct 2026, and a separate **−$13.33M** Hyperliquid-account figure as of 3 Nov 2025. Most likely differences are gross deposits vs net PnL and account scope. **Treat the magnitude as "tens of millions", not an exact figure.**
- On 30 Oct 2026 Machi was liquidated **8 times in 6 hours**, ending with **$1.50** in the account, after depositing another $250K mid-sequence - [ETtoday](https://finance.ettoday.net/news/3263694).
- Counter-trading the whale was itself a documented strategy: one trader shorted BTC/ETH whenever Wynn went long (and vice versa) and made **~$17M in a week** - [DL News](https://www.dlnews.com/articles/defi/hyperliquid-whale-loses-100m-on-leveraged-bitcoin-bet/), [CoinDesk](https://www.coindesk.com/markets/2025/06/02/how-james-wynn-s-usd100m-implosion-is-a-leverage-tale-as-old-as-time).

**Protocol / venue events**
- JELLY (26 Mar 2025): HLP unrealised **−$13.5M** at peak; HYPE −20%; TVL fell from $510M to ~$150M; validators **delisted the market and force-settled every position at $0.0095** (the attacker's short entry) instead of the ~$0.50 oracle price; HLP ended **+$700K**; attackers deposited $7.17M and withdrew ~$6.26M - [CoinDesk](https://www.coindesk.com/markets/2025/03/26/hyperliquid-delists-jellyjelly-after-vault-squeezed-in-usd13m-tussle), [Arkham](https://arkm.com/research/jellyjelly-exploit-on-hyperliquid), [Blockworks](https://blockworks.com/news/hyperliquid-decentralization-validator-put).
- The precedent matters more than the loss: Blockworks calls it a **"validator put"** - an implicit backstop where the protocol overrides the market when HLP's losses grow too large. >50% of stake is held by five Hyper Foundation validators - [Blockworks](https://blockworks.com/news/hyperliquid-decentralization-validator-put).
- HLP has since absorbed repeated "let it be liquidated" attacks: **−$4.7M** (POPCAT, 29 Oct-12 Nov 2025), **−$4.0M** (ETH long, 5-12 Mar 2025), **−$2.3M** (FARTCOIN, 1-15 Apr 2026) - [NuWealth](https://nuwealth.ai/blog/hlp-vault-returns).

**Exchange failure**
- FTX: **$8B shortfall** in customer deposits; withdrawals stopped **8 Nov 2022**; ~$6B withdrawn in 72 hours before the halt; Chapter 11 on 11 Nov 2022; ~1M creditors; a further **$477M** suspected theft within hours of the filing - [FT (paywalled)](https://www.ft.com/content/913ff750-d1f4-486a-9801-e05be20041c1), [Reuters](https://www.reuters.com/technology/ftx-needs-emergency-funding-amid-withdrawal-requests-wsj-2022-11-09/), [CNBC](https://www.cnbc.com/2022/11/12/ftx-says-its-removing-trading-and-withdrawals-moving-digital-assets-to-a-cold-wallet-after-a-477-million-suspected-hack.html).
- Consequence for this research: FTX's leaderboard - the main evidence base for the 2021-22 "top trader" narrative - no longer exists, and balance on FTX was itself the single largest risk factor for any trader in that period.

**Funding flips**
- The Nov 2022 SOL basis trade: funding fell to **−2.5% per 8 hours**; the delta-neutral position lost **~$37,000 of $100,000 in one month** and drew down **−44.5%** - [InvestWealth](https://www.investwealth.com/learn/guides/crypto-basis-trade).
- 2026: BTC/ETH funding went negative for three consecutive months (Feb-Apr 2026), with 45-58 of ~90 intervals negative per month - [Upshift](https://www.upshift.finance/blog/funding-rate-arbitrage).

**Legal/regulatory**
- Mango attacker Avraham Eisenberg: convicted on all three counts (Apr 2024, $110M), then **convictions vacated and acquitted on all counts in May 2025** because venue was improperly laid (the court nonetheless held there was "ample evidence" of manipulation) - [Reuters](https://www.reuters.com/legal/trader-convicted-mango-markets-fraud-first-us-crypto-manipulation-case-2024-04-18/), [SDNY Opinion](https://www.nysd.uscourts.gov/sites/default/files/2025-05/23cr10%20Opinion%20and%20Order.pdf), [CoinDesk](https://www.coindesk.com/business/2025/05/24/judge-overturns-convictions-in-mango-markets-exploiters-crypto-fraud-case). DOJ has signalled it will retry; treat legal outcome as unsettled.

### Inferences
- The failure mode is mechanical and predictable: at 40x, a **2.5%** adverse move is total loss, and BTC's daily range exceeds that routinely. All the deaths above are consistent with a single 2-5% move plus forced re-entry.
- Delisting/forced-settlement risk means a "winning" perp position on a small-cap market is not a claim on the oracle price; it is a claim on validator discretion. This caps the realistic upside of any thin-market manipulation strategy.
- Exchange custody risk dominated strategy risk in 2022 (FTX). The same exposure now sits with Hyperliquid's HLP/validator set.

### Gaps
- No post-mortem was found that reconciles Machi's conflicting cumulative loss figures.
- No data on Hyperliquid account-level **funding costs** for the big directional traders; Trade Replayer explicitly excludes funding.
- No source quantifies how much of the FTX-era "top trader" PnL was actually withdrawn before the freeze.

---

## Q5. What can a USD 147 account realistically copy, and what is impossible due to gas, minimum size, whitelists, speed or KYC?

### Takeaway
At $147 the executable set is narrow but not empty: small Hyperliquid perps (min $10 notional, gas-free trading, $1 withdrawal), small Polymarket positions, and manual spot on cheap chains. Everything that produced the headline numbers is mechanically out of reach: rebate market making needs hundreds of millions of fortnightly maker volume, liquidation hunting needs $5-8M of simultaneous capital, bundled sniping needs co-located infrastructure and per-attempt tips that can exceed the entire account, airdrop farming needs $500-1,500 of working capital across months plus multi-product history, and CEX copy trading needs KYC plus ~$1,000 before order-minimum truncation stops distorting the copy.

### Cited Findings

**Hyperliquid (the only leveraged venue that is accessible at this size)**
- **Minimum order: $10 notional. Withdrawal fee: $1, ~5 minutes. Trading is gas-free** (gas is paid only on the source chain when depositing) - [Senpi fee guide](https://senpi.ai/resources/learn/hyperliquid-fees), [PerpDEX Guide](https://perpdexguide.com/hyperliquid/fees/).
- Tier 0 fees: **taker 0.045%, maker 0.015%**; tier 1 starts above **$5M of 14-day volume**, so a $147 account is permanently at tier 0 - [Hyperliquid docs](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees).
- Worked cost: a $10,000 round trip is $9.00 taker / $3.00 maker; scaled to $147 of notional that is **$0.13 taker / $0.04 maker per round trip** - [Cipher Intelligence](https://cipher-intelligence.io/blog/hyperliquid-fees/), [LearnHyper](https://learnhyper.com/access/fees/).
- Maker rebates require **>0.5% of exchange maker volume ≈ $385M per 14 days** - unreachable by six orders of magnitude - [Hyperliquid Guide](https://hyperliquidguide.com/guides/trading/hyperliquid-market-making-guide).
- Liquidation distance by leverage, mechanically: 40x ≈ 2.5%, 20x ≈ 5%, 10x ≈ 10%, 3x ≈ 33% (before maintenance margin). At $147, a $10 position is 6.8% of the account, so a **$441 notional at 3x** is the largest sane size and still only tolerates a ~33% move.

**Binance / CEX**
- Minimum order notional **5 USDT** for most alts, but **BTCUSDT 50 USDT, ETHUSDT 20 USDT** - one minimum BTC clip is a third of a $147 balance in notional terms at 1x, so proportional mirroring of any multi-asset book is impossible - [Binance contract specs](https://www.binance.com/en/support/faq/usd%E2%93%A2-margined-futures-contract-specifications-360033161972), [Binance trading parameters](https://www.binance.com/en/futures/trading-parameters).
- Copy trading minimum is **10 USDT fixed-amount / 100 USDT fixed-ratio**, and lead traders need **500 USDT**; but at a $100 copy account **68% of a tested strategy's orders fall below the exchange minimum** (42% of new positions), versus 7% at $1,000 and 1% at $2,500 - [MyCryptoStart](https://mycryptostart.com/binance/copy-trading/), [RealPnL order-minimum study](https://realpnl.live/research/small-accounts-minimum-orders/).
- KYC is mandatory before trading or withdrawing; copy trading is unavailable in the US, Canada, Netherlands and other jurisdictions, and not available to sub-accounts - [MyCryptoStart](https://mycryptostart.com/binance/copy-trading/), [Coin Bureau](https://coinbureau.com/analysis/top-crypto-copy-trading-platforms).

**Solana sniping (the most capital-hostile of all)**
- Per-snipe tool fee **~1%** (Axiom 0.95%); pump.fun curve fee **1.25%** per trade; token-account rent **0.00203928 SOL**; base fee 5,000 lamports/signature - [Memecoin Guru](https://memecoin.guru/best/sniper-bots), [SnipeMint](https://www.snipemint.com/solana-sniper-bot-cost), [TrenchBay](https://trenchbay.com/blog/what-is-a-pump-fun-bundler/).
- Tips in a contested launch reach **0.05-0.25 SOL per attempt** (99th percentile), i.e. several percent to tens of percent of a $147 account **per attempt**, and failed transactions are still charged - [TierZero](https://tierzero.dev/blog/jito-bundle-tips-cost-breakdown-solana-mev).
- A competitive setup needs private RPC/co-location at **$800-2,500/month**, and a full team operation at **$4,800-13,500/month** - [TierZero](https://tierzero.dev/blog/cost-to-build-solana-sniper-bot-from-scratch).
- Base rates for the activity itself: **6.25%** of 304,161 Solana memecoin traders profitable over 90 days; **88% of winners made <$100**; **25 wallets** made >$10,000 - [Cryptopolitan/Dune](https://www.cryptopolitan.com/6-solana-meme-traders-profit-in-90-days/).

**Airdrop farming**
- Realistic working capital **$500-1,500**, 6 months, gas **$60-150** on L2s, plus bridging/slippage ~1% - [Dificalc](https://dificalc.com/blog/defi-airdrop-farming-2026). Conservative profile: **$400 capital at risk, $150-200 costs, expected return $0-500**, often negative after sybil risk - [Altcoin Investor](https://altcoininvestor.com/how-much-does-airdrop-farming-cost/).
- Median outcomes per campaign: Hyperliquid **~$400** (median 64.53 HYPE), Arbitrum **~$1,650** (median 1,250 ARB @ $1.32), zkSync **~$195** floor, Monad **~$230** average (only 41% claimed) - [Does It Pay?](https://doesitpay.org/airdrop-farming/research/).
- The explicit lesson from Hyperliquid: a **$800 perp-only wallet opened 6 weeks before the snapshot received ~820 HYPE and was a net loss after gas and bridging**, while a $12K multi-product wallet for 8+ months received ~24,500 HYPE - [AlphaGain](https://alphagaindaily.com/en/blog/hyperliquid-season-2-airdrop-farming-guide).
- Industrial farming is a different business: a 5,000-wallet operation costs **$30,000-80,000** to run and breaks even at 7-15 successful claims - [Tokenomics.net](https://www.tokenomics.net/glossary/airdrop-farming/) (practitioner estimate, not measured).

**Basis/funding carry**
- Round trip 0.38%; 12.7 days to break even at 0.01%/8h; 2026 gross 2.43%/yr with only 5.5% of periods clearing the entry bar; measured net **+4.7%/yr** - [BlofinX](https://www.blofinx.com/learn/is-funding-rate-carry-still-profitable).
- On $147 that is roughly **$7-14/year before tax**, against a $1 withdrawal fee, two-leg execution risk, and venue custody risk (the FTX lesson) - arithmetic from [InvestWealth](https://www.investwealth.com/learn/guides/crypto-basis-trade) + [BlofinX](https://www.blofinx.com/learn/is-funding-rate-carry-still-profitable).

**Prediction markets**
- Polymarket has effectively no minimum stake and only introduced taker fees in early 2026, but **69.2% of 2.9M retail accounts are below break-even** and the population is down $338.9M; the median account is down ~$3 - [Galaxy](https://www.galaxy.com/insights/research/polymarket-trader-behavior-onchain-analysis-retail-profit-loss-specialization).
- Only **2% of 2.5M traders made >$1,000 lifetime**; **0.033%** made >$100,000 - [Sergeenkov](https://sergeenkov.com/polymarket-profitability/).
- Copying "smart money" wallets is studied and does not transfer: 68.66% of wallets negative, top 1% take 89.2% of profits, and the authors "highlight the challenges of translating observed trading performance into replicable economic returns" - [arXiv 2610.34754](https://arxiv.org/abs/2610.34754).

**What the venue itself will let you do at $147 (mechanical summary)**

| Activity | Minimum viable capital | Binding constraint | Verdict at $147 |
|---|---|---|---|
| Hyperliquid perp, 1-2 positions | ~$50 | $10 min notional, $1 withdrawal, tier-0 fees | **Feasible** |
| Polymarket directional | ~$5 | none, but 69% lose | Feasible, negative expectancy |
| Spot on Solana/Base | ~$20 | gas <$0.05, 1% DEX fee | Feasible |
| CEX copy trading | $1,000+ | order-minimum truncation (68% skipped at $100) + KYC | Marginally feasible, statistically unselectable |
| Basis carry | $5,000+ to matter | 0.38% round trip, 2 legs, custody risk | Pointless at $147 |
| Airdrop farming | $500-1,500 | multi-product history, 6 months, sybil filters | Not feasible |
| Maker-rebate MM | ~$200K + co-location + >$385M/14d maker volume | exchange-wide volume share | **Impossible** |
| Liquidation hunting | $5-8M simultaneous | venue depth, oracle access | **Impossible** |
| Bundled sniping | $2-5K + RPC | 0.05-0.25 SOL tips per contested attempt, failed tx charged | **Impossible** |
| Insider/team allocations | n/a | whitelists, private rounds | **Impossible** |

### Inferences
- The realistic transferable content of this corpus for a $147 account is **risk sizing and rule discipline**, not any of the return profiles: at tier-0 fees a $147 account pays 0.045% taker, so the cost structure is fine; the killer is that the only strategies with published positive expectancy at this size (small perp trends, cheap-chain spot) have win rates in the single digits to low teens when measured on populations.
- Copying a *person* is empirically unsupported (0/180 boards clear significance; 68.66% of Polymarket wallets negative). Copying a *rule* is the only defensible move - and the rules that survive are the low-return ones (carry at ~5%/yr, first-leg discipline with strict exits).
- Any plan that requires a rebate, a whitelist, a co-located node, or a >$1K minimum is structurally closed, not merely hard.

### Gaps
- No source gives a **minimum viable size for Hyperliquid vaults** or for HIP-3 markets (some HIP-3 deployers set their own minimums); the $10 figure is for validator-operated perps.
- No measured data on **retail outcomes for Hyperliquid specifically** by account-size band; the 14.5%/30-day figure is account-level and size-filtered.
- Bybit/OKX copy-trading minimums were not verified from primary documentation in this pass (only secondary summaries and regional restrictions).
- No source quantifies the tax/withdrawal friction for a $147 account rotating across venues (bridge fees, spread on-ramps), which for small accounts can exceed the strategy edge.
