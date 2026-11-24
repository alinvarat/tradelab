# Options strategies a US$147 (≈฿5,000) simulated retail account can actually execute — as of Nov 2026

Scope note: all figures are public data; no orders were placed. Account size US$147 is treated as ~5,000 THB at ~34 THB/USD. Reference prices used throughout: **SPX 7,520.93, XSP ≈752.09, SPY $749.92 (close 10 Nov 2026)**, **BTC ≈US$61,100 (23 Nov 2026, intraday $55,081 low on 21 Nov)**. Option premium levels where I could not obtain a live chain are explicitly labelled *(estimate — needs live chain verification)*.

---

## 1. US equity/index options: what US$147 can buy or sell

### Takeaway
At US$147 a US retail account is **structurally limited to buying single-leg long options paid in full**. It cannot sell any option and cannot leg into any spread, because (a) a cash account is barred from spreads and uncovered writing by broker rule, and (b) a margin account requires US$2,000 minimum equity to use margin. Every credit spread, iron condor and naked structure in the US market is therefore **mathematically impossible**, not merely tight.

### Cited Findings
- 1 US equity/ETF/index option = 100 units of the underlying. A $1.50 premium costs $150; SPY at $749.92 means one at-the-money SPY contract controls ~$74,992 notional — [Cboe, Nanos explainer, 2022-12-20](https://www.cboe.com/insights/posts/what-to-know-before-you-trade-nano-index-options/); [Alpaca, SPX vs SPY, 2026-11-19](https://alpaca.markets/learn/spx-vs-spy-options)
- Long calls/puts with ≤9 months to expiry must be **paid in full**; no loan value, no margin — [Cboe, Strategy-Based Margin](https://www.cboe.com/us/options/strategy_based_margin); [Cboe Margin Manual (PDF)](https://cdn.cboe.com/resources/membership/Margin_Manual.pdf)
- **Cash accounts may buy calls/puts, write covered calls and cash-secured puts only.** "Short selling, uncovered option writing, option spreads, and pattern day-trading strategies all require extension of credit under the terms of a margin account and such transactions are not permitted in a cash account." — [Fidelity, Trading Restrictions FAQ (accessed Nov 2026)](https://www.fidelity.com/trading/faqs-trading-restrictions). Same rule restated by [TradingBlock, 2026-10-13](https://www.tradingblock.com/blog/margin-account) and [OptionsPilot, 2026-10-27](https://optionspilot.app/blog/cash-account-vs-margin-account-options-trading)
- **US$2,000 minimum equity** is required to use margin / sell uncovered / post spread margin (FINRA Rule 4210(b)(4)) — [FINRA Regulatory Notice 21-24](https://www.finra.org/rules-guidance/notices/21-24); [IBKR FAQ](https://www.interactivebrokers.com/support/faq/content/minimum-balance-required-trading-options-76143010); [FINRA, Intraday Margin, 2026-04-20](https://www.finra.org/investors/insights/intraday-margin-requirements)
- Exception that does *not* help: "Full cash payment for any option purchased will satisfy [the $2,000] requirement … even if the resulting equity is less than $2,000" — i.e. buying is exempt, selling/spreading is not — [FINRA 21-24](https://www.finra.org/rules-guidance/notices/21-24)
- Uncovered equity option margin = max(100% premium + 20% underlying − OTM amount, premium + 10% underlying); broad-based index uses 15% instead of 20% — [TradingBlock, 2026-10-13](https://www.tradingblock.com/blog/margin-account); [Cboe Strategy-Based Margin](https://www.cboe.com/us/options/strategy_based_margin)
- Naked-option approval floors published by brokers: Fidelity **$20,000 equity for naked equity options, $50,000 for naked index options** — [OptionsDrill, Jun 2026](https://optionsdrill.app/start)
- **PDT rule abolished 4 Jun 2026**: no more $25,000 day-trading minimum, no 4-trades-in-5-days count. The $2,000 margin minimum remains; 0DTE held to expiry counts as a day trade for intraday-margin purposes; firms may phase in through 20 Oct 2027 — [FINRA, 2026-04-20](https://www.finra.org/investors/insights/intraday-margin-requirements); [E*TRADE, 2026-06-05](https://us.etrade.com/knowledge/library/margin/pattern-day-trading-rule-change)
- Smallest listed US index contract, **Cboe Nanos (NANOS)**: $1 multiplier, $0.50 strikes, European, cash-settled, tick $0.01 — one contract ≈$752 notional at SPX 7,520 — [Cboe NANOS spec](https://www.cboe.com/tradable_products/sp_500/nanos_index_options/specifications)
- **Nanos liquidity is effectively nil**: Cboe reported volume **31 contracts and open interest 598** as of 20 Nov 2026 — [Cboe Nanos product page](https://www.cboe.com/tradable-products/sp-500/nanos-index-options/). IBKR charges $0.065/contract for NANOS, Cboe charges $0.01 — [IBKR commissions](https://www.interactivebrokers.com/en/pricing/commissions-options.php); [Cboe Fee Schedule, 2026-11-20](https://cdn.cboe.com/resources/membership/Cboe_FeeSchedule.pdf)
- **XSP (Mini-SPX)**: $100 multiplier, 1/10 of SPX, European, PM cash-settled; ~198,600 contracts/day and ~746,500 OI as of Apr 2026 — [Cboe XSP spec](https://www.cboe.com/tradable_products/sp_500/mini_spx_options/specifications); [LegalClarity, 2026-07-09](https://legalclarity.org/mini-options-contracts-xsp-micro-e-mini-and-more/)
- XSP strike intervals: "generally $1 or greater where the strike price is $200 or less and **$5.00 or greater where the strike price is greater than $200**"; "for XSP weekly contracts, the lowest strike price interval Cboe may list is $0.50" — [Cboe XSP spec](https://www.cboe.com/tradable_products/sp_500/mini_spx_options/specifications). Note: several 2026 blogs show 1-point XSP spreads (e.g. 760/759) with no caveat — [Tradebrary, 2026-10-16](https://tradebrary.com/spx-vs-xsp.html) — which conflicts with the $5 interval above $200; treat 1-point XSP spreads at XSP≈752 as **not reliably available**.
- Worked XSP margin example (XSP 752.09, sell 715 put at $3.00): requirement **$7,872** vs cash-secured $71,200 — 53× and 485× the $147 account — [OptionsPilot, 2026-11-11](https://optionspilot.app/blog/xsp-mini-spx-options-explained)
- US per-contract costs, round trip, 1 contract: IBKR $0.65/side ($1.30) + OCC clearing $0.025/side + Cboe ORF $0.01248/side (on-exchange model since 1 Jul 2026) + exchange transaction fee $0.18 Cboe customer + SEC fee on sells ($0.0000206 × proceeds) ≈ **$1.7–1.8 per contract round trip**, i.e. ~3.5% of a $50 premium — [IBKR commissions](https://www.interactivebrokers.com/en/pricing/commissions-options.php); [OCC fee schedule, Oct 2026](https://www.theocc.com/company-information/schedule-of-fees); [Cboe ORF notice, 2026](https://www.cboe.com/notices/content/?id=60003); [IBKR ORF table, 2026-11-01](https://www.interactivebrokers.com/support/faq/content/options-regulatory-fee-orf-1112364993)

**Arithmetic at $147 (my calculations, using anchors above):**

| Candidate trade | Cash needed | % of $147 | Verdict |
|---|---|---|---|
| 1 SPY ATM weekly (≈$5–8/sh) | $500–800 | 340–545% | impossible |
| 1 XSP ATM 0DTE (≈$3.00) | ~$300 | 204% | impossible |
| 1 XSP 1–2% OTM weekly (≈$1.00–2.50) | $100–250 | 68–170% | only the cheapest strikes |
| 1 SPY 0DTE ~0.5% OTM (≈$0.30–0.60) | $30–60 | 20–41% | feasible |
| 1 SPY 1–2% OTM weekly (≈$0.80–1.20) | $80–120 | 54–82% | feasible but >50% risk |
| 1 XSP 5-wide credit spread @ $1.25 credit | $375 max loss | 255% | impossible |
| 1 SPY 1-wide credit spread @ $0.30 credit | $70 max loss | 48% | **arithmetically fine, legally blocked** (needs margin account, $2,000) |
| 1 SPY 1-wide iron condor @ $0.40 net credit | $60 max loss | 41% | **legally blocked** (needs margin account) |
| 1 cash-secured put on a $1 stock | $100 | 68% | no such liquid US option exists |
| NANOS 1-lot | $1–20 | <14% | size OK, **no liquidity (31 contracts/day)** |

*(premium estimates above are marked as estimates; the point holds for any premium — see formula below.)*

### Inferences
- The binding constraint is not the 100× multiplier, it is **account type**. Below $2,000 you cannot open/maintain margin, so the entire defined-risk *credit* family (verticals, condors, butterflies, strangles) is unavailable regardless of how small the max loss is. A $70-max-loss SPY 1-wide condor is small enough in dollars but cannot be entered.
- Therefore, at $147 the only US-legal structures are: single long calls/puts (cash), long-only multi-leg combinations paid in full (e.g. long straddle/strangle, long butterfly if the broker accepts the 4-leg order without margin), and covered/cash-secured positions that need far more cash than $147.
- A long-only US structure has max loss = premium, so "max loss ≤ 50% of account" means **premium ≤ $73**, which at SPY $749 buys only ~1.5–2.5% OTM, short-dated contracts. Any thesis needing ATM exposure is out of reach by a factor of 4–10.
- XSP looks like the natural vehicle ($100 multiplier, 1/10 SPX, cash-settled, European) but at XSP≈752 the $5 strike interval means the narrowest vertical risks ~$400–500, i.e. 270–340% of the account. XSP only becomes usable at account sizes ≥$1,000 even for a 1-lot vertical.
- Nanos is the only product whose size truly fits ($1 multiplier) and it is unusable: 31 contracts/day means no realistic fill, and a market order would move the strike grid. This is the clearest case of "mathematically possible, operationally impossible".

### Gaps
- No live option chain was pulled, so exact premiums/deltas at the 24 Nov 2026 close are unverified. Brokers' quoted minimum premiums for 0DTE SPY/XSP were not obtained.
- Whether any US broker permits **long debit spreads in a cash account** at $147 is unresolved. Fidelity explicitly forbids "option spreads" in cash accounts; Schwab/Robinhood require margin for multi-leg. IRA "limited margin" arrangements at some brokers may allow defined-risk spreads, but that is an account-type feature not available to a small taxable account, and I found no broker-published confirmation for sub-$2,000 accounts.
- No primary source found on whether brokers will accept a 2-leg *long-only* order (long straddle) in a cash account when both legs are paid in full; likely yes but unverified.

---

## 2. Crypto options (Deribit): minimum sizes, inverse vs linear, and what 0.1 BTC actually risks

### Takeaway
The "0.1 BTC minimum" is a **~US$400–700 maximum loss floor per spread**, i.e. 3–5× the whole account — so inverse BTC options are out. But Deribit's **USDC-settled linear** BTC options have a 0.01-contract minimum, which puts the same 8.5%/15% wing spread at **US$40–60 max loss (27–41% of the account)**. This is the only venue where a genuine defined-risk short-vol structure fits $147.

### Cited Findings
- Inverse BTC options: contract = **1 BTC**, multiplier 1, premium quoted in BTC, European, cash-settled in BTC, daily 08:00 UTC expiry; **minimum order size 0.1 contract** for BTC (1 ETH for ETH) — [Deribit, Inverse Options spec (updated 2026-01-21)](https://support.deribit.com/hc/en-us/articles/31424939096093-Inverse-Options); [Paradigm venue spec](https://paradigm.network/help/products/derivatives/venues/deribit)
- Linear USDC options: contract = 1 BTC, multiplier 1, "fractional contracts are possible", **minimum order size 0.01 contract**, tick 5 USDC for prices ≤1,000 USDC — [Deribit, Linear USDC Options spec (updated 2026-11-19)](https://support.deribit.com/hc/en-us/articles/31424932728093-Linear-USDC-Options)
- Linear USDC options launched 19 Aug 2025 with 0.01 BTC / 0.1 ETH minimums explicitly "to improve accessibility" — [Deribit Insights, 2025-08-15](https://insights.deribit.com/education/usdc-settled-btc-eth-options-launch/); [PR Newswire, 2025-08-15](https://www.prnewswire.com/news-releases/deribit-introduces-linear-options-for-btc-and-eth-302531054.html)
- Since early Apr 2026 ITM linear options first settle into a futures contract at the strike, which then cash-settles in USDC; net result identical to cash settlement — [Deribit Linear USDC spec](https://support.deribit.com/hc/en-us/articles/31424932728093-Linear-USDC-Options)
- Block-trade minimums are irrelevant to retail: 25 BTC / 25 ETH notional — [Deribit Block Trading (2026-11-11)](https://support.deribit.com/hc/en-us/articles/25944688627229-Block-Trading)
- **Standard-margin initial margin, short option** (inverse): Short Call = MAX(0.15 − MAX((Strike−Index)/Index,0), 0.1) + mark price; Short Put = MAX(MAX(0.15 − MAX(Index−Strike,0)/Index, 0.1) + mark, maintenance). Long options are paid in full, no further margin — [Deribit Inverse Options spec](https://support.deribit.com/hc/en-us/articles/31424939096093-Inverse-Options)
- Standard margin does **not** net a long option against a short option; offsetting requires Portfolio Margin, which stress-tests ±16% price with vol up/same/down and uses the worst scenario + delta shock + roll shock; maintenance = 0.80 × initial — [Deribit Portfolio Margin (2026-10-21)](https://support.deribit.com/hc/en-us/articles/25944756247837-Portfolio-Margin); [Deribit Margin types](https://support.deribit.com/hc/en-us/articles/25944811317149-Margin-types-and-usage)
- Fees: options ~**0.03% of index notional per side** (maker = taker per third-party comparison), delivery fee 0.015% capped at 12.5% of option value — [Spark exchange comparison, mid-2026](https://www.spark.money/tools/bitcoin-options-exchange-comparison); liquidation fee **0.19% of index price** — [Deribit Linear USDC spec](https://support.deribit.com/hc/en-us/articles/31424932728093-Linear-USDC-Options)
- Deribit is **not available to US residents** — [Spark, mid-2026](https://www.spark.money/tools/bitcoin-options-exchange-comparison)

**Max-loss arithmetic (my calculations; BTC = $61,100, R = 0.03% fee rate, inverse payoff = max(0,(S−K)/S) BTC for a call, max 1 BTC):**

Inverse BTC option, **0.1 contract**, short put spread, short strike 8.5% OTM / long strike 15% OTM:
- K_short = 55,900; K_long = 51,900; width = 4,000.
- Max loss per 1.0 BTC contract = (K_short − K_long)/K_short = 4,000/55,900 = **0.0716 BTC**
- × 0.1 contract = **0.00716 BTC ≈ US$437** (linear shortcut 0.1 × 4,000 = $400 — close, so the simple version is fine for sizing)
- = **297% of the $147 account** → impossible.
- If "wings" instead means short at 15% OTM / long at 24.7% OTM (K 51,900 / 46,000, width 5,900): 5,900/51,900 = 0.1137 BTC → ×0.1 = **0.01137 BTC ≈ US$695** = **473%** → impossible.

Inverse BTC option, **0.1 contract, naked short 15% OTM put**, standard margin: 0.15 − 0.15 = 0 → floor 0.10 → 10% of notional = 0.1 × $6,110 = **US$611 initial margin** (417% of account) before premium. Impossible.

Linear USDC BTC option, **0.01 contract**, identical strikes:
- Max loss = 0.01 × 4,000 = **US$40.00** = **27% of $147** ✅
- 15%/24.7% version: 0.01 × 5,900 = **US$59.00** = **40%** ✅
- Standard-margin IM for the short leg ≈ 10% × 0.01 × 61,100 = **US$61.10**; the long leg is paid in full (~$2–8). Portfolio margin would net it to roughly the width.
- Fees per leg per side = 0.03% × 0.01 × 61,100 = **US$0.18**; a 2-leg spread opened and closed = ~**$0.73**, i.e. **1.8% of a $40 max loss** and, at an $8 credit, **9% of the credit**. At 0.01 size the fee floor is a first-order cost, not a rounding error.

Long-only crypto (both venues are cheap at minimum size): a 0.01-lot linear option priced at, say, 250 USDC per BTC costs **$2.50**; a 0.1-lot inverse option priced at 0.0015 BTC costs **0.00015 BTC ≈ $9.17**. Long straddles/strangles therefore fit easily — but see §5 on why that is not an edge.

### Inferences
- The 0.1 BTC minimum implicitly targets an account of roughly $2,000+: a 0.1-lot 8.5%/15% spread carries a $437 max loss, which is 20% of ~$2,185. At $147 it is a hard blocker for anything that *sells* volatility in inverse BTC, because the minimum loss unit is 2.7–4.7× the account.
- Linear (USDC) options change the feasibility verdict entirely and are the single most important 2025–2026 structural change for a sub-$500 crypto options account. Max loss becomes exactly (width × 0.01), so the account can express a defined-risk short-vol view with 27–40% risk.
- Inverse and linear are **not interchangeable for risk reporting**: inverse max loss is fixed in BTC, so its USD value moves *with* the BTC price and is not the $437 you sized at. The same 0.00716 BTC is $501 at BTC $70,000 and $358 at $50,000. Practical consequences: (i) sizing off today's price overstates the USD loss in a crash and understates it in a rally; (ii) the BTC-denominated collateral requirement does not shrink with price, so a falling market raises the *coin* cost of the same USD risk. This is routinely ignored in retail sizing tables.
- Standard margin (no netting) means a 0.01-lot short strangle needs ~$122 IM, which is 83% of the account — still possible but leaves no buffer; PM is required for capital efficiency and PM has its own access thresholds (not published as a dollar figure).

### Gaps
- Deribit's minimum account balance / minimum deposit for Portfolio Margin access is not published in the docs I reached; whether a $147 account can enable PM is unverified.
- No live Deribit chain was pulled; the 8.5%/15% strike premiums (and hence credits) are illustrative, not quoted. DVOL level on 23 Nov 2026 not retrieved.
- Actual realised wider-spread cost on 0.01-lot BTC_USDC options is unknown; with a 5-USDC tick and a $610 notional, the tick alone is 0.8% of notional.

---

## 3. Evidence on the volatility risk premium, earnings vol crush, short strangle/condor returns, long straddle/strangle returns and 0DTE retail performance (after costs, with tails)

### Takeaway
There **is** a documented variance risk premium and documented earnings IV crush, but the two most credible 2024–2026 sources say the harvestable part has decayed: standard S&P 500 option strategies show **no statistically significant alpha after 2012**, and 0DTE retail trading loses money *after costs* in every published dataset, with transaction costs responsible for roughly 60% of the loss. No source supports a positive after-cost edge reachable at $147.

### Cited Findings
**Variance risk premium / short volatility**
- Short one-month ATM SPX straddle, 1996–2022 out-of-sample: excess return 9.2%, Sharpe **0.51**, skew **−4.07**, kurtosis 28.6, **max drawdown −39%**; timing overlay lifts Sharpe to 0.62 — [Yang, "Volatility-Managed Volatility Trading", Jun 2024, Table 12](https://english.phbs.pku.edu.cn/uploadfile/2024/0530/20240530092144610.pdf)
- **Structural break**: studying SPX options 1987–2025, "after 2012 … standard options strategies no longer have statistically significant alphas or information ratios"; the decay coincides with a change in dealer option portfolios — [Dew-Becker & Giglio, "The decline of the S&P 500 variance risk premium", 2 Jun 2026](https://www.dew-becker.org/documents/option_decline.pdf)
- Harvesting study 1996–2020 with CBOE margin rules and realistic spreads (baseline = 25% of quoted spread): transaction costs hit multi-leg structures hardest — moving from 50% to 0% effective spread improves 25-year terminal wealth by **30% for condor strangle, 24% for butterfly, 18% for variance-swap replication, ~13% for delta-hedged call/put/straddle** — [FernUniversität Hagen, "How to Harvest Variance Risk Premiums"](https://www.fernuni-hagen.de/bwlbuf/docs/how_to_harvest_variance_risk_premiums_for_the_long-term_investor_.pdf)
- Even a favourable stock-level VRP study reports that with full quoted spreads the long-short straddle portfolio falls from **13.5%/month to 8.1%/month**, Sharpe 0.334, and certainty-equivalent turns **negative** for risk aversion 3 and 7 — [UCP thesis, Investment strategies based on the VRP](https://repositorio.ucp.pt/server/api/core/bitstreams/407ed597-e58f-45d9-8061-62c5c0f648cd/content)

**Earnings volatility crush**
- 1,546 earnings events, 40 underlyings, 10 years, 648,861 simulated trades: **IV contracted in 1,395 of ~1,500 events (~90%)**, average −7.50 vol points (~20%), IV rank −25 points (~53%) — [Option Alpha, 2020-03-31](https://optionalpha.com/podcast/we-stopped-trading-earnings-after-we-saw-new-research)
- Same study: the best gross performer (50-delta long straddle, 20 days before, 20 DTE) earned $95,000 total but **4 of the top 10 trades each made >$10,000**; removing the top 10 of 1,205 trades made it unprofitable. Defined-risk *buying* was profitable on average with a **32% win rate**; defined-risk *selling* and undefined-risk selling had **negative average P&L despite 57% win rates** — same source
- 1,097 earnings releases, 434 liquid US stocks, 2016–2022: earnings IV crushed to **60% on average**; long calendar straddle averaged **~13%** return, profitable **53%** of the time — [Quantcha research PDF](https://quantcha.blob.core.windows.net/public/Research/2204-Quantcha-AnAnalysisOfTradingEarningsReleasesUsingOptions.pdf)
- S&P 500 constituents 2010–Aug 2025: mean IV−RV spread **−16.5pp**, average P&L **+$31 per $10,000 notional**, positive in **69%** of events, quarterly Sharpe 2.05 **before costs**; "ATM straddles on short-dated earnings contracts typically carry bid-ask spreads of 5 to 15 percent of the premium … a realistic net Sharpe after costs, for names outside the top 100 by liquidity, would likely be close to zero or negative" — [The Intrinsic Investor, Sep 2026](https://theintrinsicinvestor.com/research/earnings-vol-cycle/)
- Around earnings, ATM straddle returns are *positive* for the long (one day before to announcement: **+2.3%**, t>15), i.e. the crush does **not** reliably pay the seller at the index/single-name level once the move is counted — [Gao/Xing/Rice, "Straddle returns around earnings", 2013](https://www.ruf.rice.edu/~yxing/straddle_201305_03.pdf)

**0DTE retail performance**
- Cboe trade-level data, Feb 2021–Sep 2023: retail lost **$241,000 per average day**; **$350,000/day** after the May 2022 daily-expiry calendar; cumulative **net −$125m** vs gross ≈ −$30m; "roughly **60% of daily losses are the result of transaction costs**"; >75% of retail SPX option trades are now 0DTE — [Beckmeyer, Branger & Gayda, "Retail Traders Love 0DTE Options", Dec 2023](https://wp.lancs.ac.uk/fofi2024/files/2024/04/FoFI-2024-146-Leander-Gayda.pdf)
- Same paper, per-strategy net P&L and margin-adjusted return: single put mean **−$16.3** (−5.6% of margin), single call mean **−$20.7** (−9.4%); put spread mean −$20.2 but **median +$85** (+3.0%); **iron condor mean −$15.6, median +$135, margin-adjusted mean −1.1%, median +5.5%, 5th percentile −100%**; straddle mean −$59.5, 5th pct −$4,709; strangle mean −$40.0, 5th pct −$3,847 — same source, Tables 3–4
- 889,967 retail parent option trades: average return **−0.93%** (t = −3.57); naked option sales **+20%**, option purchases **−3.95%**; 0DTE trades underperform other trades by **−4.71%** univariate (−2.95% with controls); index/ETF option trades **−3%** vs +0.15% single-stock — [de Silva, Smith & So, "An Anatomy of Retail Option Trading"](https://www.brettonwoodsskiconference.com/uploads/b/f9bfc8b0-0251-11ed-a646-3dea17112d2f/An%20Anatomy%20of%20Retail%20Option%20Trading.pdf)
- Same paper: average 0DTE trade size only **$1,077** with dollar loss per trade **−$44.8** — i.e. the modal retail 0DTE ticket is already ~7× a $147 account
- Retail share of 0DTE is contested: Cboe's proprietary method implies **50–60%** of SPX 0DTE volume; independent reconstruction implies **30–35%** — [OptionMetrics, 2026-09-28](https://optionmetrics.com/blog/how-much-of-0-dte-is-really-retail-evidence-from-spx-and-spy-options/)
- Limit-order behaviour in 0DTE is studied by the SEC: customer non-marketable limit orders and quote improvement — [SEC DERA working paper, 16 Mar 2025](https://www.sec.gov/files/dera-hope-reasonable-prc-2503.pdf)

**Tail losses (concrete)**
- 2 Aug 2024 → 5 Aug 2024: SPX 5,338 → 5,186. A 6 Sep 4850/5610 short strangle sold for **$5,050 credit lost $4,540** — **90% of the credit collected in one session**; the author's model attributes **~$3,100 of the $4,540 to the IV spike**, not the 160-point move. The matching 30-point-wide iron condor collected **$870** and its bull put spread lost **$435 (−9% of capital at risk)** — [Options Trading IQ, 2024-09-25](https://optionstradingiq.com/selling-option-premium/)
- VIX 23.38 → 38.56 close-to-close, with a pre-market print near **66**; deep OTM put IV went **36% → 90%** — [ORATS, 2024-08-13](https://orats.com/blog/0dte-and-the-august-fifth-correction); [BIS Bulletin 95, 2024-10-29](https://www.bis.org/publications/bulletin-95-anatomy-vix-spike-august-2024.pdf)
- BIS: on 5 Aug 2024 the VIX rose **180%** pre-market, the largest one-day spike on record; bid-ask spreads on some deep OTM puts reached **>80% of mid** vs ~25% on normal days, and spreads in the VIX strip widened up to **10×** — [BIS Bulletin 95](https://www.bis.org/publications/bulletin-95-anatomy-vix-spike-august-2024.pdf)
- SEC DERA: a specific 3500-strike SPX put's quoted spread went from **$0.20 to >$15** pre-market on 5 Aug 2024, mid from ~$0.7 to >$10 (peak $50.25) — [SEC DERA, Apr 2025](https://www.sec.gov/files/dera-vix-working-paper-2504.pdf)
- 0DTE liquidity withdraws exactly when needed: 0DTE share of SPX volume fell to **26%** on 5 Aug 2024 from its ~50% norm — [Reuters, 2024-08-07](https://www.reuters.com/markets/us/traders-spurn-zero-day-options-this-weeks-market-tumble-2024-08-07/)
- Practitioner postmortem: a 150-spread 0DTE book at 10-delta was "underwater by late morning" on 5 Aug 2024; a VIX-25-sized convexity hedge did not offset a VIX-65 event — [Math and Markets, 2026-05-22](https://mathandmarkets.com/p/i-added-one-rule-to-my-0dte-spx-strategy)

### Inferences
- The direction of the evidence is consistent: **selling** volatility has positive gross expectancy and catastrophic left tail; **buying** has negative expectancy with positive skew. The only category that survives costs in retail data is option *sales* (+20% in the 890k-trade sample) — and that is exactly the category a $147 US account cannot access.
- The 0DTE numbers are the most damning for a small account because the loss is *proportional*: −60% of the loss is spread/fees, and smaller tickets pay proportionally more spread. A $30 0DTE ticket pays ~6% round-trip in US fees and typically 5–15% in spread — a structural 11–21% headwind per trade before any view.
- "Median positive, mean negative" for iron condors and credit spreads is the classic small-sample trap: median +5.5% of margin with 5th percentile −100%. On a $147 account, one 5th-percentile event erases 15–20 median winners.
- The earnings-crush edge is real but thin and liquidity-conditional (5–15% of premium in spread, Sharpe→0 outside top-100 names). No US structure that monetises it (short straddle, calendar) is executable at $147.
- Dew-Becker & Giglio's 2012 structural break is the single most important counterweight to any "sell premium for income" pitch written before 2024. Any backtest ending in 2012 or using pre-2013 data overstates the edge.

### Gaps
- No source found that measures the VRP or earnings crush specifically on **accounts under $500** or on **sub-1-lot crypto** positions; all after-cost results are for institutional/large retail size, so small-account costs are, if anything, understated.
- No published study isolates 0DTE performance **after the June 2026 PDT abolition**; the intraday-margin regime is too new for peer-reviewed evidence.
- The 2026 academic literature on whether the 2024–2026 0DTE boom further compressed the VRP was not located.

---

## 4. Option-chain data: brokers/APIs, cost and limitations

### Takeaway
Free real-time option chains essentially do not exist for automation. The practical stacks are: **Deribit public API (free, real-time, crypto only)**, **Alpaca free indicative feed** (15-min delayed trades, modified quotes, paid OPRA upgrade), **Massive/Polygon Basic** (end-of-day only, 5 calls/min) and **Tradier** (real-time only with a funded brokerage account). Every free US tier is unusable for measuring spread cost on 0DTE, which is the one number that matters at this account size.

### Cited Findings
- Alpaca options: free Basic = **indicative feed**, "trades are delayed and quotes are modified"; OPRA real-time requires **Algo Trader Plus $99/month**; historical data limited to latest 15 minutes on Basic; 200 API calls/min; 200 websocket quote subs — [Alpaca market data docs](https://docs.alpaca.markets/us/docs/about-market-data-api); [Option chain endpoint](https://docs.alpaca.markets/us/reference/optionchain)
- Alpaca chain snapshots carry greeks/IV but **no open interest** in the stream; NBBO is not attached to streamed trades (must be fetched per print) — [whale-options feeds doc](https://github.com/LuxAlgo/whale-options/blob/main/docs/feeds.md)
- Tradier: API included with a brokerage account at no extra charge; production = real-time consolidated feed, **Level 1 top-of-book only, no depth**; **sandbox = 15-minute delayed**; **historical data unavailable for expired options** (kills any backtest of 0DTE) — [Tradier API docs](https://docs.tradier.com/brokerage-api)
- Massive (ex-Polygon, rebranded 2025-10-30): Basic **$0, end-of-day, 5 calls/min, 2 years history, no greeks**; Starter **$29/mo, 15-min delayed + greeks**; Developer $79/mo (trades, 4y); Advanced **$199/mo real-time** — [Massive/optionsstack comparison, checked 2026-11-03..09](https://optionsstack.com/compare/options-data-apis/); [AI Fin Hub vendor prices](https://aifinhub.io/vendor-prices/)
- Cboe's own delayed quote pages **prohibit automated extraction**, so scraping is not a compliant data path — [QVeris, 2026-05-04](https://qveris.ai/guides/free-options-data-api)
- Deribit exposes public, unauthenticated market data (`public/get_instruments`, `public/get_order_book`, `public/ticker`) including greeks/IV per instrument — [Deribit API docs](https://docs.deribit.com/)
- Deribit's own Position Builder exposes the PM risk matrix / margin requirements for a simulated portfolio, which is the only free way to measure true spread margin pre-trade — [Deribit Portfolio Margin doc](https://support.deribit.com/hc/en-us/articles/25944756247837-Portfolio-Margin)

### Inferences
- For this project, the correct data choice is Deribit public API (free, real-time, order-book depth, greeks) plus **one** US paid tier only if a US structure is being measured. Free Alpaca/Massive tiers cannot answer "what does the spread cost on a 30-cent option" because the quotes are modified or end-of-day — the exact quantity that decides whether a $30 ticket is viable.
- Tradier's lack of expired-option history is disqualifying for any 0DTE backtest; you would need OPRA-derived historical quotes (paid) or Cboe trade data (research licence).
- Point-in-time contract metadata is the hidden cost: a naive backtest that uses today's strike grid overstates liquidity for delisted weeklies.

### Gaps
- Exact current pricing of Cboe DataShop / OPRA historical quotes, and whether a research licence is available to an individual, was not priced.
- Deribit rate limits and whether greeks are returned for the full chain in one call were not verified from the spec.
- No source found on latency/quality of the "indicative" Alpaca feed specifically for 0DTE SPY at the open, which is where a small account would actually trade.

---

## 5. Structures that fit US$147 with max loss ≤ 25–50% of the account, with exact rules

### Takeaway
Only **three** structures are both legal and small enough: (A) a US single-leg long option with premium ≤$70, (B) a Deribit **BTC_USDC 0.01-lot** defined-risk put credit spread with max loss $40 (27%), and (C) a Deribit **BTC_USDC 0.01-lot long straddle** with debit ≤$30 (20%). All three are *testable*; none has a documented after-cost edge at this size.

### Cited Findings
- Legal basis for A: cash accounts may buy options; $2,000 margin minimum does not apply to a fully paid option purchase — [Fidelity](https://www.fidelity.com/trading/faqs-trading-restrictions); [FINRA 21-24](https://www.finra.org/rules-guidance/notices/21-24)
- Size basis for B/C: 0.01-contract minimum on linear BTC options, fractional contracts permitted — [Deribit Linear USDC spec](https://support.deribit.com/hc/en-us/articles/31424932728093-Linear-USDC-Options)
- Cost basis for B/C: 0.03%/side of index notional; ~$0.18 per 0.01-lot leg per side — [Spark](https://www.spark.money/tools/bitcoin-options-exchange-comparison); [Deribit spec](https://support.deribit.com/hc/en-us/articles/31424932728093-Linear-USDC-Options)
- Optionality caveat for B: PM netting requires Portfolio Margin; standard margin charges 10% of notional on the short leg (~$61 per 0.01 lot) without netting — [Deribit Inverse spec](https://support.deribit.com/hc/en-us/articles/31424939096093-Inverse-Options); [Deribit PM](https://support.deribit.com/hc/en-us/articles/25944756247837-Portfolio-Margin)
- Evidence basis for "test, don't assume": median-positive / mean-negative credit-spread profile with 5th percentile −100% — [Beckmeyer et al., Table 4](https://wp.lancs.ac.uk/fofi2024/files/2024/04/FoFI-2024-146-Leander-Gayda.pdf); post-2012 alpha decay — [Dew-Becker & Giglio, 2026](https://www.dew-becker.org/documents/option_decline.pdf)

**A. US long single-leg option (cash account), premium ≤ $70 (≤48% of account)**
- Instrument: SPY (or XSP if premium ≤$70), 0–7 DTE, delta magnitude 15–30.
- Entry: limit order only, at mid or one tick better; reject if premium > $0.70/share ($70) or if quoted spread > 8% of mid. Never market order.
- Exit: take profit at +100% of debit; hard stop at −50% of debit or at 15:45 ET on expiry day; never hold a 0DTE long into the close hoping for settlement.
- Controls: 1 contract maximum; one open position at a time; no averaging down; log realised spread cost per trade (entry mid vs fill).
- Expected outcome given §3: negative after-cost expectancy (−0.9% to −4.7% per trade in the retail datasets). Purpose is measurement, not income.

**B. Deribit BTC_USDC 0.01-lot put credit spread, short ~8.5% OTM / long ~15% OTM, 7–14 DTE**
- Max loss: 0.01 × (K_short − K_long) = **≈$40** (27% of $147). IM under standard margin ≈$61 on the short leg; the long leg is paid in full.
- Entry gate: only if DVOL / 30-day IV percentile ≥ 50th; only if the credit is ≥ 20% of width (i.e. ≥$8 on a $40 width) — below that the $0.73 round-trip fee consumes >9% of the credit.
- Exit: buy back at 50% of credit, or at 3 DTE, whichever first; hard stop if the spread's mark reaches 2× the credit received. No rolling, no widening.
- Expiry: European, cash-settled, no early assignment; ITM settles via futures into USDC. Settlement is 08:00 UTC — do not leave a position through expiry unintentionally.
- Controls: one spread at a time; cap at 2 concurrent only if equity > $300; record credit, fee, mark at exit, and max adverse excursion.

**C. Deribit BTC_USDC 0.01-lot long straddle (or 25-delta strangle), 7–30 DTE**
- Cost target ≤ **$30** (20% of account): a 7-DTE ATM straddle at ~$1,500/BTC → 0.01 × $1,500 = $15; a 30-DTE straddle at ~$3,500/BTC = $35, so cap tenor at ~14 days to stay under $30 *(premium figures are estimates)*.
- Entry: before a known event (FOMC/CPI) only if IV percentile < 40th; otherwise skip.
- Exit: +100% / −50% of debit; time stop at 50% of tenor elapsed; no re-striking.
- Max loss = debit, by construction. This is the only structure here whose risk is truly capped without collateral.

**Explicitly ruled out (mathematically or legally impossible at $147):**
- Any US short option, credit spread, iron condor, iron butterfly, short strangle, naked put — blocked by the $2,000 margin minimum and cash-account spread prohibition (see §1).
- Cash-secured put on any US stock — needs strike × 100; cheapest liquid names still cost 10× the account.
- Inverse BTC 0.1-lot spreads ($437–695 max loss = 297–473% of account).
- XSP 1-lot verticals at XSP≈752 with $5 strike intervals (~$375–500 max loss = 255–340%).
- Nanos — sized correctly ($1–20) but 31 contracts/day makes entry/exit unmeasurable.

### Inferences
- The three survivors all sit at 20–48% of the account, which means **one loss consumes the entire monthly risk budget**. This is not a diversification problem that sizing can fix; it is a floor imposed by contract granularity.
- B is the only structure that can plausibly harvest the documented VRP, and it does so at a size where fees are 9% of credit and where the underlying edge is statistically insignificant post-2012. The honest prior is: B is a *cost-and-discipline exercise*, not an income strategy.
- C monetises the one documented anomaly that survives (earnings/event vol underpricing is thin, but long straddles around events are the only category where the literature reports positive returns: +2.3% around earnings announcements), yet it too pays 5–15% of premium in spread.
- Recommended experiment design: run A, B, C in parallel on paper with **≥100 trades each**, logging fill vs mid, and compare to the null of zero. At this account size, 100 trades of B at $8 credit = $800 gross max — enough to distinguish a real 5% edge only if costs are logged precisely, which is why §4's data choice matters more than the strategy choice.

### Gaps
- No source establishes minimum viable sample size or a power calculation for detecting a 5–10% edge on $8 credits; the 100-trade figure above is my judgement, not a cited standard.
- Deribit's actual quoted credit for a 0.01-lot 8.5%/15% spread on 23 Nov 2026 was not retrieved, so the "≥20% of width" gate is unverified against live pricing.
- Whether a Thai resident can open and fund a Deribit account at $147 (KYC tier, minimum deposit, on/off-ramp cost) was not researched; on/off-ramp fees could exceed the entire expected edge.
