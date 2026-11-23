# Options and Volatility Strategies for a Small Retail Account (~150 USD)

Research date: 2026-11-23. Labels used: [LIVE] = actual traded/realized results; [INDEX-BACKTEST] = rules-based index, partly back-filled; [ACADEMIC-EMPIRICAL] = academic study of actual historical prices/trades (paper trades at historical quotes, not a live fund).

## 1. Volatility risk premium (selling options): evidence, returns, drawdowns, blowups

### Takeaway
Selling S&P 500 options has earned a real but modest premium: the Cboe PutWrite index made about 7.1%/yr since 2007 with a -32.7% max drawdown, *below* the S&P 500's 11.0%. Leveraged or naked short-vol products have been wiped out in single days (XIV -96% on 5 Feb 2018, LJM funds -80%+ in two days). Done safely (fully cash-secured), the strategy cannot turn 150 USD into a large sum quickly. Done with leverage, it carries real ruin risk.

### Cited Findings
- **Mechanism:** the VRP is the compensation investors earn for providing protection against market losses, i.e. underwriting insurance through options. AQR attributes it to investors' risk aversion and their tendency to overestimate the probability of significant losses (Ang, Israelov, Sullivan, Tummala, May 2018). — [AQR, Understanding the Volatility Risk Premium](https://www.aqr.com/Insights/Research/White-Papers/Understanding-the-Volatility-Risk-Premium)
- AQR's example: adding a rolled one-month 5% OTM put hedge to the S&P 500 (1996–2016) cut average annual return from 5.1% to 1.8%. Put buyers paid the premium, so sellers earned it. — [CAIA summary of the AQR paper](https://caia.org/node/5509)
- Israelov, Nielsen and Villalon ("Embracing Downside Risk", J. Alternative Investments 2017) report short volatility earning 1.8%/yr with 2.9% annualized volatility. That is small in absolute terms (de-levered, delta-hedged). — [AQR JoAI PDF](https://www.aqr.com/-/media/AQR/Documents/Journal-Articles/JoAI-Embracing-Downside-Risk.pdf?sc_lang=en)
- Israelov & Nielsen, "Still Not Cheap" (JPM 2015): put protection is still expensive relative to subsequent realized volatility even when implied volatility is historically low. The VRP was positive in every implied-vol decile. — [CFA Institute digest](https://rpc.cfainstitute.org/research/cfa-digest/2015/12/still-not-cheap-portfolio-protection-in-calm-markets-digest-summary); [Alpha Architect](https://alphaarchitect.com/2016/11/in-calm-markets-should-we-buy-cheap-put-protection/)
- Israelov & Nielsen, "Covered Calls Uncovered" (FAJ 2015): covered calls collect the equity and volatility premia but embed an uncompensated short-reversal (equity timing) exposure. — [CFA Institute](https://rpc.cfainstitute.org/research/financial-analysts-journal/2015/covered-calls-uncovered)
- **[INDEX-BACKTEST] Cboe PUT index (ATM SPX puts sold monthly, fully collateralized by T-bills), factsheet as of 31 Oct 2026, from 3 Jan 2007:** annualized return 7.1% vs 11.0% for S&P 500 TR; volatility 10.7% vs 15.4%; max drawdown -32.7% vs -50.9%; Sharpe 0.52 vs 0.61. Annualized 1y/3y/5y/10y: 13.2% / 14.0% / 8.9% / 8.5%. — [Cboe PUT factsheet](https://cdn.cboe.com/resources/indices/factsheet/CboeGlobalIndices_PUT-Index.pdf)
- **Post-2020 calendar years, PUT vs S&P 500 TR:**

  | Year | PUT | S&P 500 TR |
  |---|---|---|
  | 2018 | -5.9% | -4.4% |
  | 2020 | 2.1% | 18.4% |
  | 2021 | 21.8% | 28.7% |
  | 2022 | -7.7% | -18.1% |
  | 2023 | 14.3% | 26.3% |
  | 2024 | 17.8% | 25.0% |
  | 2025 | 9.2% | 17.9% |

  The 2020 gap shows how the March 2020 crash hurt put sellers, who then lagged the V-shaped rebound. — [Cboe PUT factsheet](https://cdn.cboe.com/resources/indices/factsheet/CboeGlobalIndices_PUT-Index.pdf)
- **Longer history:** from July 1986 to August 2023, PUT returned 9.40%/yr vs 9.91% for the S&P 500, with a -32.66% vs -50.96% drawdown and 10.26% vs 15.38% standard deviation. — [Cboe, cash-secured put writing](https://www.cboe.com/insights/posts/generating-income-and-managing-risk-cash-secured-put-writing-in-a-low-equity-return-environment)
- **Other periods and indexes:**
  - From December 1990 to March 2017, PUT returned 9.9% vs 10.1% for the S&P 500, with 9.7% vs 14.2% volatility. — [Neuberger Berman](https://www.nb.com/documents/public/en-us/uncovering_the_equity_index_putwrite_strategy.pdf)
  - A Wilshire study (1986–2016, Cboe-commissioned) found options-based indexes had max drawdowns about 24% lower on average than the S&P 500. — [Cboe IR 2016](https://ir.cboe.com/news/news-details/2016/New-Wilshire-Analytics-Study-Finds-Options-Indexes-Offered-Noteworthy-Returns-Over-30-Years-09-21-2016/default.aspx)
  - From 2006 to 2018, the max drawdown was -24.2% for WPUT (weekly) and -32.7% for PUT vs -50.9% for the S&P 500 (Bondarenko, Cboe white paper). — [Cboe insights](https://www.cboe.com/insights/posts/benchmark-indices-series-hedging-downside-exposure-with-pput-cll-and-cllz-indices)
  - Cboe's 2021 benchmark piece says BXM, PUT and two other Cboe benchmark indexes returned less than the S&P 500 over the long run. — [Cboe benchmark series](https://www.cboe.com/insights/posts/benchmark-indices-series-income-generation-and-smoother-returns-with-cboes-bxm-bxmd-put-and-cmbo-indices)
  - Note: Cboe is the product sponsor, so these are vendor-published.
- **[LIVE] Volmageddon, 5 Feb 2018:**
  - XIV (inverse VIX ETN) had $1.9bn in assets the prior Friday and lost 96.3% of its value on Monday 5 Feb 2018.
  - Credit Suisse triggered an acceleration event because the indicative value fell to 20% or less of the prior day's value. The last trading day was 20 Feb 2018.
  - The VIX jumped a record 20 points that day.
  - Sources: [ETF.com](https://www.etf.com/sections/news/inverse-vix-etn-shuts-down); [Bloomberg, "The Day the VIX Doubled"](https://www.bloomberg.com/news/articles/2019-02-06/the-day-the-vix-doubled-tales-of-volmageddon)
- **[LIVE] LJM Preservation and Growth (sold S&P 500 futures options, net short vol):**
  - NAV fell from $9.67 to $4.27 on 5 Feb 2018, then to $1.94 the next day.
  - The SEC complaint says losses exceeded 80% of the value of LJM-managed funds over two trading days. The fund shut down.
  - The SEC charged the managers in 2021 for misleading investors about "remote but extreme" risks.
  - Sources: [SEC press release 2021-89](https://www.sec.gov/news/press-release/2021-89); [SLCG analysis](https://www.slcg.com/files/research-papers/Investors%20Strangled%20by%20LJM%20Preservation%20and%20Growth%20Fund%20(LJMIX).pdf); [MFDF](https://www.mfdf.org/news-resources/news/2018/02/21/Trustees-Adviser-Named-in-Suit-after-Fund-Collapses-Amid-Market-Volatility-2795)
- **Retail sellers:** retail traders who *sell* short-dated options made significant profits even after transaction costs (Nov 2019–Jun 2021 sample). This is consistent with the VRP. — [Bryzgalova, Pavlova, Sikorskaya, JF 2023](https://lbsresearch.london.edu/id/eprint/2827)

### Inferences
- With fully collateralized put writing, returns scale with the cash posted. A single SPX put needs hundreds of thousands of USD in collateral. Even one cash-secured put on a $20 stock ties up about $2,000, so a 150 USD account can only sell cash-secured puts on stocks under about $1.50. Those are penny stocks with very wide spreads.
- At PUT-like returns of about 7–14%/yr, 150 USD earns about 10–20 USD/yr. The VRP is a slow premium, not a route to 5x in a month.
- Leveraged short vol (naked puts, short VIX products) is what produced the blowups. In a small margin account, one gap day can exceed 100% of equity. This is the classic ruin profile: small steady gains, rare total loss.

### Gaps
- I could not open the full AQR 2018 PDF tables: its Sharpe, worst month and drawdown figures were not retrieved.
- I found no primary source on optionsellers.com (Nov 2018) or on specific 2020 short-vol fund blowups (e.g., Malachite). I also have no fetched source for the March 2020 VIX peak level.
- I did not retrieve BXM calendar-year returns after 2020.

## 2. Buying OTM and short-dated options (0DTE, weeklies): retail results and lottery payoffs

### Takeaway
Large-sample evidence shows retail option *buyers* lose money on average, both before and after costs. The losses concentrate in exactly the cheap, short-dated, OTM contracts a 150 USD account can afford. Bid-ask spreads of 12–29% are the main cost. 0DTE retail traders also lost in aggregate after 2022.

### Cited Findings
- **[ACADEMIC-EMPIRICAL] Bryzgalova, Pavlova & Sikorskaya, "Retail Trading in Options and the Rise of the Big Three Wholesalers" (Journal of Finance 2023, DOI 10.1111/jofi.13285).** Sample Nov 2019–Jun 2021. All facts below are from the published paper text. — [LBS repository / JF PDF](https://lbsresearch.london.edu/id/eprint/2827)
  - **Retail share and size:**
    - Retail recently exceeded 60% of total options market volume.
    - Options PFOF in 2021 was $2.4bn, vs $1.3bn for equities.
    - Citadel, Susquehanna and Wolverine take most of the PFOF.
  - **What retail trades:**
    - 50% of retail trades are in options with less than a week to expiry, with an average quoted spread of 12.6% (effective spread about 6.6%).
    - Slightly-OTM trades (23% of trades) have an average quoted spread of 29%.
    - 42% of retail trades are "micro" (up to $250), with a 23.5% average quoted spread.
    - Embedded leverage in weekly options often exceeds 50.
    - 69% of volume is in calls; 72% of trades are ATM.
  - **Results:**
    - Assuming a 10-day holding period, retail lost $2.1bn in aggregate (Nov 2019–Jun 2021).
    - Indirect trading costs (distance from trade price to midquote) totaled $6.4bn, vs about $0.9bn in direct commissions.
    - Before costs, the buy-minus-sell portfolio was positive ($10.4–12.9m/day). After costs it was -$1.6m to -$5.0m/day.
    - The **buy portfolio loses even gross of costs**. The sell portfolio is positive net of costs, but mostly not statistically significant.
    - Unleveraged, retail loses 28–40 cents per $100 traded.
    - Contracts with less than a week to expiry incur significant losses at all holding periods.
    - Worst months were Jan 2021 (GME), Feb 2021 and Dec 2020, with losses of $672m, $358m and $321m.
- **[ACADEMIC-EMPIRICAL] Beckmeyer, Branger & Gayda, "Retail Traders Love 0DTE Options... But Should They?" (2023, SSRN).**
  - Data: Cboe SPX trades with trader-type codes, Jan 2021–Feb 2023.
  - Retail lost about $70m in aggregate on 0DTE SPX options. The average daily loss rose from about $184k to about $358k after daily expirations began on 16 May 2022.
  - 0DTE made up more than 75% of retail SPX volume.
  - The authors attribute the losses largely to transaction costs and to retail ignoring how expensive the options are. They read the motive as gambling and entertainment.
  - Sources: [CXO Advisory](https://www.cxoadvisory.com/individual-investing/retail-0dte-option-trader-performance); [Bloomberg 2023-04-21](https://www.bloomberg.com/news/articles/2023-04-21/day-traders-lose-358-000-per-day-gambling-on-zero-day-options); [WealthManagement](https://www.wealthmanagement.com/equities/retail-investors-are-in-love-with-same-day-options). Secondary summaries; the PDF could not be fetched.
- **Counter-view from Cboe (exchange, conflicted):** retail is about 50–60% of SPX 0DTE trading, over 95% of 0DTE trades use limited-risk formats, and market-maker gamma hedging is de minimis. Cboe does not claim retail profits. — [Cboe, "0DTEs Decoded"](https://www.cboe.com/insights/posts/0-dt-es-decoded-positioning-trends-and-market-impact)
- **Boyer & Vorkink, "Stock Options as Lotteries" (JF 2014):** option portfolios sorted on ex-ante skewness show average-return differences of 10–50% *per week*. High-skewness (lottery-like, i.e. OTM and short-dated) options earn the lowest returns. In an early version, the low-minus-high skewness spread for 7-day calls was +1.4% vs -35.4% per week. — [IDEAS/RePEc](https://ideas.repec.org/a/bla/jfinan/v69y2014i4p1485-1527.html); [CXO summary](https://www.cxoadvisory.com/equity-options/sell-lottery-tickets-for-their-fun-and-your-profit)
- **Call returns and strike:** call returns on stocks and indexes decrease in the strike price and are significantly negative for contracts that start out-of-the-money. This line of work follows Coval & Shumway (JF 2001). — [Coval & Shumway, RePEc](https://econpapers.repec.org/RePEc:bla:jfinan:v:56:y:2001:i:3:p:983-1009); search-result summaries of follow-up work. I did not verify a specific number.
- **[ACADEMIC-EMPIRICAL] Boulatov, Eisdorfer, Goyal & Zhdanov, "Cheap Options Are Expensive" (2021 WP; US equity options 1996–2017).**
  - Delta-hedged calls on the lowest-priced stocks return -0.68%/week, vs -0.14% for the highest-priced. For puts the figures are -0.46% vs -0.12%.
  - Low-priced underlyings underperform by 0.54%/week for calls and 0.34% for puts. Options become 13% (calls) and 9% (puts) relatively more expensive after stock splits.
  - Retail-style "cheap" options are systematically overpriced.
  - Source: [ASU conference PDF](https://finance-conference.wpcarey.asu.edu/sites/default/files/imported/21-11-20-04-07-04_Cheap_Options_Are_Expensive%20(1).pdf)

### Inferences
- **Chance of 5x or more in one month.** I found no study that reports the frequency of 5x+ outcomes directly, so this is an inference. Buying short-dated OTM options is the only listed route where a 5x month is mechanically possible. The papers show these are the most overpriced contracts, with average returns well below zero. That means any 5x outcome is a low-probability tail draw paid for by frequent total losses (option to zero). The expected value of repeating the bet is negative.
- **Spreads alone at 150 USD.** With 12–29% quoted spreads, a round trip on a micro-size option can cost 6–15% or more of the premium before any price move.
- **Ruin risk.** For a buyer, the maximum loss per trade is the premium. Concentrating 150 USD in one or two contracts means a high probability of losing most of the account within weeks.

### Gaps
- No verified statistic gives the empirical share of OTM options (calls or 0DTE) that return 5x or more by expiry. Building one would need OptionMetrics or Cboe data, or an own backtest.
- I could not access the Beckmeyer et al. full text for per-trade returns or the cost share. One secondary summary claims about 60% of losses come from costs; this is unverified.
- I did not locate post-2023 academic 0DTE retail P&L studies (e.g., a 2016–2024 Frankfurt School study mentioned in a blog), so their authorship and figures are unverified.

## 3. Earnings straddles: implied vs realized move

### Takeaway
Academic evidence suggests buying ATM straddles shortly before earnings has *historically* earned positive average returns, i.e. announcement uncertainty was underpriced on average. The edge concentrates in small, high-volatility firms, which are also the names with the widest spreads. I found no post-2020, net-of-cost live evidence.

### Cited Findings
- "Anticipating Uncertainty: Straddles around Earnings Announcements" (JFQA 2018, cited elsewhere as Gao et al. 2018): ATM straddles bought before announcements earn positive returns. One version reports 3.34% for holding from 3 days before the announcement to the announcement date. Returns are stronger for smaller and higher-volatility firms. — [Cambridge / JFQA](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/anticipating-uncertainty-straddles-around-earnings-announcements/7B34877AD5E06304BA3C55FBA3219FDD). I could not confirm the authors (search label "Gao, Xing, Zhang") from the page.
- A JRFM (MDPI 2023) study: straddle returns are significantly higher (lower) when the historical earnings move is high (low) relative to the option-implied earnings move. — [MDPI JRFM 16(5):270](https://mdpi.com/1911-8074/16/5/270)
- A related paper: "Earnings Announcements and Option Returns" (Penn State). — [PSU](https://pure.psu.edu/en/publications/earnings-announcements-and-option-returns/)

### Inferences
- A mean of about 3% per event is not 5x. Because straddles lose when the realized move is smaller than the implied move, the per-event outcome is volatile.
- A straddle costs two premiums, so on liquid names it typically costs well over 150 USD. Spreads on small-cap names may erase the documented edge.

### Gaps
- I found no net-of-bid-ask figures, sample period details, or post-2020 replication for the earnings-straddle premium.
- I found no data on the 0DTE/weekly "implied move" accuracy for single stocks after 2020.

## 4. Options-implied signals for picking stocks (skew, IV spread)

### Takeaway
Option-implied signals (call-put IV spread, volatility skew) have predicted next-month stock returns in academic samples, but the predictability has decayed over time. I found no evidence they survive realistic costs for a tiny account. The signal could be used to trade *stocks*, not options, which avoids option spreads.

### Cited Findings
- Cremers & Weinbaum (2010, JFQA): the call-put implied volatility spread is strongly positively related to future stock returns over the following month. The authors note the predictability decreased over their sample, and their sample excludes thinly traded option names. — [Search-result summaries; e.g. NBER w19590](https://www.nber.org/papers/w19590.pdf); [Lancaster eprint](https://eprints.lancs.ac.uk/id/document/45308)
- Xing, Zhang & Zhao (2010, JFQA): implied volatility skew has strong predictive power for cross-sectional stock returns (steep-smirk stocks underperform). — [Search-result summary, Essex JPM paper](https://repository.essex.ac.uk/11215/1/JPM_LIU.PDF)
- Cost robustness, from an adjacent study ("Cheap Options Are Expensive"):
  - The long-short is still profitable when effective spreads are up to 50% (calls) or 40% (puts) of quoted spreads.
  - At 50% of quoted, the put leg drops to an insignificant 0.06%/week, and the calls to 0.17%/week.
  - Muravyev & Pearson (2020) estimate effective spreads at about 30% of quoted for traders who time executions well.
  - The pattern: many option anomalies are fragile to costs.
  - Source: [ASU PDF](https://finance-conference.wpcarey.asu.edu/sites/default/files/imported/21-11-20-04-07-04_Cheap_Options_Are_Expensive%20(1).pdf)

### Inferences
- These are long-short, many-stock, monthly-rebalanced portfolio effects of roughly a few percent a year or less. A 150 USD account cannot diversify across dozens of names, and the edge is far too small for 5x outcomes.

### Gaps
- I found no study testing IV-spread or skew signals net of costs after 2015 or after 2020.

## 5. Minimum capital: can 150 USD trade options meaningfully? (contracts, spreads, broker rules, Thailand access)

### Takeaway
150 USD can buy a handful of cheap single-leg options, and nothing else. Selling options, spreads and diversification all need far more capital and margin approval. The affordable contracts carry the worst spreads and the most negative expected returns. Thai residents can reportedly open accounts at Interactive Brokers, but options permission rules for small accounts are unverified.

### Cited Findings
- Interactive Brokers lists an account minimum of USD 0. — [IBKR Required Minimums](https://www.interactivebrokers.com.hk/en/accounts/required-minimums.php)
- Aggregator sites report that IBKR accepts Thai residents with a Thai ID, at about $0.65 per contract (minimum $1). — [QuantWheel](https://quantwheel.com/marketplace/brokers/in/thailand); [BrokerChooser](https://brokerchooser.com/best-brokers/best-options-platforms-and-brokers-in-thailand). These are marketing aggregators and unverified.
- 42% of US retail option trades are micro (up to $250), with a 23.5% average quoted spread. Small tickets are normal but expensive. — [BPS JF 2023](https://lbsresearch.london.edu/id/eprint/2827)
- Collateral for a single SPX ATM put is index-level times 100 (the PUT index is fully T-bill collateralized). — [Cboe PUT factsheet](https://cdn.cboe.com/resources/indices/factsheet/CboeGlobalIndices_PUT-Index.pdf)

### Inferences
- **Contract size.** A standard US equity option covers 100 shares (a standard convention; I did not fetch a source). A premium quoted at $1.50 therefore costs $150, so the whole account buys one contract priced at $1.50 or less.
- **Fixed costs.** A $1 minimum commission each way on a $30–150 position adds about 1–7% per round trip, on top of spreads.
- **Selling and spreads.** Short premium needs either cash-secure (strike times 100) or margin approval. US brokers usually require a margin account, often with higher minimums, for spreads or naked writing. I did not verify a specific number such as $2,000 (the US FINRA margin minimum is commonly cited) for IBKR's non-US clients.
- **Account size and ruin.** One position equals 50–100% of the account, so a single expiring-worthless option is a near-total loss.

### Gaps
- I did not verify Thai SEC rules on Thai residents using foreign brokers, the Bank of Thailand FX rules for outward investment, or US withholding/tax treatment for Thai holders.
- I did not verify IBKR's options-permission levels and minimum equity for spreads or short options for non-US individual accounts.
- I did not check Thailand-local options: SET50 Index Options on TFEX, their multiplier and the minimum margin at Thai brokers. This could be a more accessible alternative and needs separate research.
