# Social-media practitioner evidence: retail trading strategies, small accounts and fast growth (2020-2026)

Evidence labels used throughout:
- **[VERIFIED]** = regulator data, court/regulator filing, peer-reviewed or working-paper study, or on-chain dataset analysis.
- **[ANALYSIS]** = independent backtest or journalist/data-firm analysis (method disclosed, not audited).
- **[ANECDOTE]** = self-reported social-media or forum claim, not independently verified.
- **[ALLEGATION]** = investigator claim (e.g. ZachXBT), disputed or not adjudicated.

Research date: 2026-11-23. Research limits: Reddit threads could not be fetched directly (only via mirror listings in search results). Myfxbook/FXBlue leaderboards, Telegram/Discord groups and YouTube transcripts were not retrieved first-hand. Everything below has a source link. Anything without one is listed under Gaps.

## Q1. Reddit communities: what practitioners report working or failing (algotrading, Daytrading, Forex, options/thetagang wheel, WSB, memecoins, sports betting, Polymarket)

### Takeaway
Reddit success claims are almost all self-reported and unbenchmarked. Where independent data exists (on-chain memecoin/Polymarket wallets, Brazilian day-trader records, wheel backtests, WSB DD studies), most participants lose or underperform a passive benchmark. Gains are concentrated in a very small tail, often bots, insiders or token deployers.

### Cited Findings
**r/algotrading / bots**
- [ANECDOTE] Mirror listings of r/algotrading show posts claiming extreme results, such as "12,000%+ Returns w/ <3% Drawdown". The posters ask others to "break" the backtest. No live, verified track record was attached. A 2025 r/algotrading post asked whether anyone had an EA that stayed profitable live for 1-2 years, and the poster said they had not found one. — [r/algotrading mirror (Mar 2025)](https://redlib.cypherpunktools.com/r/algotrading/hot); [r/algotrading thread "Has anyone actually found a long-term profitable…"](https://libreddit.winscloud.net/r/algotrading/comments/1ofontf/has_anyone_actually_found_a_longterm_profitable)
- [ANECDOTE] Practitioner advice from forums: go live on a small account and compare live fills with backtest results every day or two. Live and backtest must "reasonably match". — [Elite Trader "How to Become Profitable (algotrading for beginners)"](https://elitetrader.com/et/threads/how-to-become-profitable-algotrading-for-beginners.390775/)
- [ANECDOTE] A BabyPips user reported that one bot did worse than random trading. Overfitting comes up repeatedly as the failure cause. — [BabyPips "My automated trading experience"](https://forums.babypips.com/t/my-automated-trading-experience/290357?page=3)
- [ANECDOTE/vendor-adjacent] Expect 10-30% live degradation versus backtest from slippage and latency, and use ≥200 trades before drawing conclusions. The source has a commercial angle. — [dev.to "Crypto trading bot profitability: real numbers"](https://dev.to/trendrider/crypto-trading-bot-profitability-real-numbers-not-marketing-hype-1pf0)
- Other recurring "is anyone actually making money" threads (ProRealCode, QuantConnect) show the same pattern: a few claimed winners and many failed bots. — [ProRealCode "Live Trading Success – Is anyone actually making any money?"](https://www.prorealcode.com/topic/live-trading-success-is-any-one-actually-making-any-money/page/2/); [QuantConnect "has anyone made real money yet"](https://www.quantconnect.com/forum/discussion/1144/has-anyone-made-real-money-yet/)

**r/Daytrading: base rates behind the stories**
- [VERIFIED] Chague, De-Losso & Giovannetti, "Day Trading for a Living?" (SSRN 2019/FGV 2020). It covers everyone who began day trading Brazilian equity index futures in 2013-2015. Of those who persisted more than 300 days, 97% lost money. Only 0.4% earned more than a bank teller (~US$54/day), and the best earned ~US$310/day with high risk. The authors found no learning with experience. — [IDEAS/RePEc](https://ideas.repec.org/p/fgv/eesptd/525.html); [Bloomberg coverage](https://www.bloombergquint.com/onweb/day-traders-in-brazil-study-would-ve-done-better-with-9-to-5-job)
- [VERIFIED] A follow-up (Brazilian Review of Finance, 2025) covers the COVID-19 surge, when day trading reached ~100,000 active participants per day. — [RBFin](https://periodicos.fgv.br/rbfin/article/view/94291)
- [ANECDOTE] An r/Daytrading user (Nov 2024) coded their discretionary strategy into a bot and posted results. This is typical of the sub: personal P&L screenshots with no audit. — [r/Daytrading mirror](https://lr.eu.psf.lt/r/Daytrading/comments/1ghidl3/coded_my_trading_strategy_into_a_bot_and_these)

**r/Forex: base rate**
- [VERIFIED] Under ESMA's 2018 product intervention, national regulators found that 74-89% of retail CFD accounts lose money, with average losses of €1,600-€29,000 per investor. Brokers must publish their own loss percentage. — [ESMA press release, 27 Mar 2018](https://www.esma.europa.eu/node/84933); [ESMA warning-text notice](https://www.esma.europa.eu/sites/default/files/library/esma35-43-1135_notice_of_pi_decisions_on_cfds_and_binary_options.pdf)

**r/options / r/thetagang: wheel strategy**
- [ANECDOTE] An r/thetagang "updated stats" post (Oct 2024) reported a wheel portfolio up ~30% YTD after being down ~30% earlier. It gave no benchmark comparison. A commenter said the big posted wins mostly come from selling ATM puts in bull markets. — [r/thetagang mirror, 25 Oct 2024](https://libreddit.winscloud.net/r/thetagang/comments/1gc4acf/updated_stats)
- [ANALYSIS] Early Retirement Now (Options series part 12, 17 Sep 2024) titled its post "The Wheel Strategy Doesn't Work". It argues the wheel's mechanics underperform simple put-writing or buy-and-hold. — [Early Retirement Now](https://earlyretirementnow.com/2024/09/17/the-wheel-strategy-doesnt-work-options-series-part-12/)
- [ANALYSIS] A quant blog (May 2026) backtested SPY wheel variants starting in 2019 and 2020. Pure SPY beat every wheel variant on CAGR, and covered calls beat the wheel. The main drag was cash idle while waiting for assignment. — [haozhezhang6.github.io](https://haozhezhang6.github.io/quant/2026/05/07/wheel-strategy.html)
- [ANALYSIS, conflicting] A QuantConnect research piece reported that the automated wheel outperformed buy-and-hold SPY over its test window. The result depends on period and parameters. — [QuantConnect "Automating the Wheel Strategy"](https://www.quantconnect.com/research/17871/automating-the-wheel-strategy/)
- [ANALYSIS] A Patreon analysis says the wheel lags in bull markets, roughly matches in sideways markets and loses badly in bear markets unless hedged, and that taxes cost 1-3% CAGR. — [CompoundingLab](https://www.patreon.com/CompoundingLab/posts/why-you-should-148455582)

**r/wallstreetbets**
- [VERIFIED] Bradley, Hanousek, Jame & Xiao ("Place Your Bets? The Value of Investment Research on Reddit's WallStreetBets"). Before GameStop, an incremental DD buy recommendation was associated with ~5.17% higher one-month returns (gross). After GME, the predictive value and the retail response faded. — [EBSCO abstract](https://www.ebsco.com/articles/business-and-management/cf6a3620-b1a9-5907-94b9-b492bd0db320/place-your-bets-the-value-of-investment-research-on-reddit-s-wallstreetbets); [CXO Advisory summary](https://www.cxoadvisory.com/investing-expertise/wallstreetbets-contributors-and-users-skilled)
- [VERIFIED] An Oxford-hosted study found WSB provides little to no signal about future prices, except for meme stocks such as GME and AMC. — [ORA Oxford](https://ora.ox.ac.uk/objects/uuid:6f3c53d3-f0d6-4232-b3cf-bf1696b200f9/files/dsf268587w)
- [VERIFIED] Buz & de Melo compared WSB recommendations with investment-bank analysts. They found the community can be a source of advice "with varying success". — [arXiv 2301.00170](https://ar5iv.labs.arxiv.org/html/2301.00170)

**r/CryptoCurrency / r/solana: memecoins and Pump.fun**
- [VERIFIED-ish: on-chain dashboard analysis] Over a six-month window, more than 60% of Pump.fun trading addresses lost money, and ~1,700 wallets were down more than $100k. Only ~3% of buyers made more than $1,000 in one Dune analysis, and ~0.76% made $1,000+ in another. — [crypto.news](https://crypto.news/over-60-pump-fun-traders-saw-losses-less-than-0-01-made-over-1m/); [crypto.news 0.76%](https://crypto.news/only-0-76-of-pump-fun-wallets-made-1000-or-more-cn-research/); [cryptorank 3%](https://cryptorank.io/news/feed/19483-3-percent-traders-on-pump-fun-made-over-1000)
- [ANALYSIS] March 2026, ~1.4M wallets: 49-50.6% in loss, and ~96% made less than $500 that month. In the same month ~250 token deployers extracted ~$79M from traders. — [Protos](https://protos.com/over-50-of-pump-fun-token-traders-lost-money-this-month-report); [cryptorank/CoinEdition](https://cryptorank.io/news/feed/0501b-over-50-pump-fun-traders-lose-money-as-launchers-extract-79m); [crypto.news Mar 2026](https://crypto.news/pump-fun-data-shows-49-of-march-traders-in-the-red-as-platform-locks-fees/)
- Caveat: CoinGecko's Pump.fun study counts only realized PnL. Bagholders who never sold are excluded, so losses are understated. Counts are per wallet, and one trader can own many wallets. — [CoinGecko research](https://www.coingecko.com/research/publications/pump-fun-traders-are-making-a-comeback)

**r/sportsbook / r/sportsbetting: +EV / value betting**
- [VERIFIED: regulator testimony / journalism] US sportsbooks limit accounts whose bets predict line moves, i.e. consistent closing-line value (CLV), not a dollar threshold. A Fanatics executive told Massachusetts regulators that nearly half of limited customers were net losers when restricted, and that ~90% of winning customers are not limited. Another Fanatics risk executive admitted "too many accounts get limited… too harshly." — [ESPN](https://africa.espn.com/sports-betting/story/_/id/41231266/espn-sports-betting-news-sportsbooks-defend-practice-limiting-sharp-customers); [OddsShopper](https://www.oddsshopper.com/articles/betting-101/why-sportsbooks-limit-winning-bettors); [Covers, Feb 2025](https://www.covers.com/industry/true-state-of-sports-betting-part-iv-whither-the-winners-limiting-regulation-february-2025)
- [ANECDOTE, reported] Bettor Jack Andrews said DraftKings limited him to $27 on a Super Bowl coin toss. Limited accounts typically keep full stakes on main markets but are cut to "pocket change" on props and niche leagues. — [IBJ](https://www.ibj.com/articles/sportsbooks-say-you-can-win-big-then-they-try-to-limit-winners); [Deuces Cracked 2026](https://www.deucescracked.com/blog/sportsbook-account-limits-2026-why-winners-get-limited)
- Practitioner consensus: spread volume across books. Duplicate accounts break KYC/ToS and risk confiscation of the balance. — [OddsShopper arbitrage/limits](https://www.oddsshopper.com/articles/betting-101/arbitrage-betting-limits-getting-banned)

**r/Polymarket**
- [ANALYSIS] Motley Fool (2026) looked at ~313k wallets across 210 markets resolved in 2025. More than 82% lost net, and the top 1% of winning wallets took ~85% of profits. — [Motley Fool](https://www.fool.com/research/prediction-markets-vs-stock-market-returns/)
- [ANALYSIS] Other estimates range from ~70% to 87% of wallets unprofitable, depending on method. Reichenbach & Walther (2025) put it at ~70%. Sergeenkov put it at 84.1%, with only 2% of 2.5M traders making more than $1,000. Galaxy Research found 69.2% of 2.9M retail wallets below break-even, and Layerhub found 87.3%. Bloomberg (Apr 2026) found that more than 100k wallets lost at least $1,000 since 2025, about 2× the number that made $1,000, and that the winners "look like bots". — [casino.org](https://www.casino.org/news/84-of-polymarket-traders-arent-profitable/); [BeInCrypto/Galaxy](https://beincrypto.com/polymarket-retail-traders-losses-galaxy-study/); [Bloomberg 28 Apr 2026](https://bloomberg.com/news/articles/2026-04-28/most-prediction-market-traders-are-losing-money-while-bots-rack-up-gains); [Finance Magnates on Bloomberg](https://www.financemagnates.com/fintech/100000-polymarket-wallets-lost-at-least-1000-bloomberg-analysis-shows/)

### Inferences
- In every venue with an independent base rate (Brazil futures, EU CFDs, Pump.fun, Polymarket), losers are 50-97% of participants, and the profitable tail is tiny and concentrated. Reddit "gain porn" is a survivorship-biased sample of that tail.
- The most credible sustained "edge" practitioners report is structural: +EV sports betting via CLV, and bots/market-making on Polymarket. Even there the edge is capped by counterparties (sportsbooks limit winners) or captured by automated players.
- The wheel is best framed as an income/volatility-selling strategy that tends to lag SPY in bull markets. Reddit wheel success posts are rarely benchmarked.

### Gaps
- No yearly r/algotrading "show your live results" thread could be retrieved directly, because Reddit blocked fetching. The writer should not claim any specific consensus "what works" list from such threads.
- No sniper-specific (bot-sniping new Solana launches) loss rate was found. The Pump.fun figures cover all traders.
- No systematic r/thetagang self-reported return tally exists that I could find.

## Q2. YouTube: strategy channels, channels that backtest YouTube strategies, and small-account challenges

### Takeaway
"Tested 100 times" videos (e.g. Trading Rush) popularized quick manual backtests. Independent rebuilds of viral TradingView/YouTube strategies tend to land near coin-flip after costs. The best-known small-account-challenge promoter, Warrior Trading/Ross Cameron, settled FTC charges in 2022 that its customers mostly lost money.

### Cited Findings
- [ANALYSIS] A developer rebuilt "Manergy Cloud" from the YouTube channel Trading with DaviddTech. The claimed result was a 3,888% return on BTCUSDT 1h at 10x leverage, with 62.8% win rate, PF 2.1 and 237 trades. The original custom indicators are unpublished, so the claim could not be verified. A causal rebuild (next-bar fills, $0.85/side plus 1 tick slippage) on MES/MNQ/SPY/QQQ hourly gave win rates of 33-35% against a 33.3% breakeven at 1:2 R:R, and profit factor 0.81-1.01. MNQ's +$11k came with a ~-$111k max drawdown. The author notes that the reconstruction is approximate. — [dev.to, Jul 2026](https://dev.to/umam75/i-rebuilt-a-viral-3888-return-tradingview-strategy-it-landed-almost-exactly-at-coin-flip-odds-2hj7)
- [ANECDOTE/secondary] The Trading Rush channel tests indicator strategies "100 times" by hand, and a summary claims more than 10,000 trades across ~50 strategies. Community members have ported these tests into TradingView scripts and Forex Factory threads. — [SozAI transcript summary](https://sozai.app/transcript/analyzed-10000-trades-50-strategies/); [TradingView "Trading Rush Signals & Alerts" (unofficial)](https://in.tradingview.com/scripts/rush/); [Forex Factory post](https://www.forexfactory.com/thread/post/15248085)
- [ANECDOTE] A crowdsourced spreadsheet catalogs many "Tested 100 Times" YouTube strategies with their win rates and results. It is unaudited. — [Google Sheet](https://docs.google.com/spreadsheets/d/1LQ7lwnvcB5eacK4PxLXnV1mMEIzSxHzD8IZpP2N1oA8/edit)
- [ANALYSIS] A Medium/Coinmonks series ("Backtesting the Hype: Can YouTube Indicators Deliver?") backtests popular YouTube indicators. The content could not be fetched (HTTP 403). — [Medium](https://medium.com/coinmonks/backtesting-the-hype-can-youtube-indicators-deliver-part-1-7c97b5fe0ddb)
- [VERIFIED] FTC v. Warrior Trading & Ross Cameron (D. Mass., April 2022). The FTC alleged that the company used Cameron's results to market courses as profitable while "the vast majority of customers actually lost money trading… on top of the thousands they paid." The case settled for $3M in refunds plus a ban on unsubstantiated earnings claims, and FTC refund rounds followed. Warrior Trading said the settlement was about disclaimers and did not question Cameron's own results, so the two accounts conflict. — [FTC business blog, Apr 2022](https://www.ftc.gov/business-guidance/blog/2022/04/ftc-bids-good-night-deceptive-day-trading-earnings-claims); [FTC complaint PDF](https://www.ftc.gov/system/files/ftc_gov/pdf/2023198WarriorTradingComplaint_0.pdf); [FTC refunds](https://ftc.gov/enforcement/refunds/warrior-trading-refunds); [FTC consumer alert](https://consumer.ftc.gov/consumer-alerts/2022/04/day-trading-earnings-werent-payday-warrior-trading-promised)
- [ANECDOTE, secondary] The Warrior Trading YouTube series "My NEW Small Account Challenge" claimed $500 → ~$53k in 17 days. That was the presenter's own account and not evidence of student results. — [USA Herald](https://usaherald.com/warrior-trading-to-pay-3-million-for-making-false-earnings-claims-regarding-its-day-trading-strategies/)
- [ANALYSIS] TradingView's own community idea on overfitting warns that strategy-tester backtests "lie" because of overfitting. — [TradingView ideas: strategytester](https://www.tradingview.com/ideas/strategytester)

### Inferences
- Even when a presenter's own small-account run is real, it does not transfer to followers. That is the core of the FTC Warrior Trading case.
- Viral TradingView/YouTube strategies often depend on unpublished or repainting indicators, leverage and short cherry-picked windows. When rebuilt causally with costs, the edge disappears.

### Gaps
- I could not retrieve Trading Rush's own aggregate findings (which strategies held up) from a primary source.
- No independent verification was found for other famous "$100 → $10,000" challenges (e.g. broker statements). Treat them as unverified.

## Q3. X/Twitter and Telegram: crypto "alpha" callers, KOLs and documented dumping on followers

### Takeaway
On-chain investigators, mainly ZachXBT, have repeatedly documented, as allegations, influencers buying early, promoting, then selling into follower demand. The one academic study of finfluencer skill finds most have negative skill and that the worst attract the most followers.

### Cited Findings
- [VERIFIED: academic] Kakhbod, Kazempour, Livdan & Schürhoff, "Finfluencers" (SFI WP 23-30, April 2023; CEPR DP 20204, 2025; AEA 2025). Using StockTwits data, the 2023 version classifies ~28% of finfluencers as skilled, 16% unskilled and 56% antiskilled. The 2025 version gives ~29/16/55. Unskilled and antiskilled finfluencers have more followers and more influence on retail trading. Antiskilled ones chase returns, and a contrarian strategy against them earned ~1.2%/month out of sample. — [SFI WP 23-30](https://www.sfi.ch/en/publications/n-23-30-finfluencers); [CEPR DP 20204](https://ideas.repec.org/p/cpr/ceprdp/20204.html); [SFI news](https://www.sfi.ch/en/about-us/news/finfluencers-under-the-microscope-advice-vs.-entertainment)
- [ALLEGATION] ZachXBT (29 Sep 2022) alleged that Lark Davis made over $1M promoting low-cap tokens and selling on followers. Davis denied it. — [CryptoSlate](https://cryptoslate.com/zachxbt-alleges-crypto-influencer-lark-davis-made-over-1m-dumping-crypto-projects/)
- [ALLEGATION] Sep 2023: ZachXBT accused four popular crypto traders of pump-and-dump schemes. — [Binance Square/coverage](https://www.binance.com/en/square/post/2023-09-11-blockchain-investigator-accuses-four-crypto-traders-of-pump-and-dump-scheme-1126488); [CryptoPotato](https://cryptopotato.com/zachxbts-latest-expose-on-pump-and-dump-schemes-targets-4-popular-crypto-traders/)
- [ALLEGATION] ZachXBT alleged that Ansem promoted memecoin pump-and-dumps. — [CoinMarketCap Academy](https://coinmarketcap.com/academy/article/crypto-influencer-ansem-accused-of-promoting-memecoin-pump-and-dumps-by-zachxbt)
- [ALLEGATION] July 2025: 45 insider wallets linked to "Crypto Beast" sold more than $11M of ALT on 14 Jul 2025. Market cap fell from ~$190M to ~$3M within minutes. — [Cryptonews](https://cryptonews.com/news/zachxbt-exposes-crypto-beast-11m-alt-token-dump/)
- [ALLEGATION] ZachXBT has also targeted Logan Paul (CryptoZoo and other pump-and-dumps), KSI (~$1.2M of sales after shilling) and Arthur Hayes (bullish posts matched against sell transaction timestamps). — [CryptoSlate Logan Paul](https://cryptoslate.com/?p=237393); [KuCoin blog Arthur Hayes](https://www.kucoin.com/blog/ae-zachxbt-accuses-arthur-hayes-exit-liquidity); [BeInCrypto counter-trading](https://beincrypto.com/zachxbt-exposes-influencer-counter-trading)
- [ALLEGATION] ZachXBT flagged fake "war alert" accounts and a fake persona built to farm engagement and funnel followers into pumps. — [BeInCrypto](https://beincrypto.com/zachxbt-fake-war-alerts-crypto-pump-dump)
- [VERIFIED: on-chain] Pump.fun deployers extracted ~$79M in one month (Mar 2026). This is the structural counterpart of "callers": the person who launches or buys first wins. — [cryptorank](https://cryptorank.io/news/feed/0501b-over-50-pump-fun-traders-lose-money-as-launchers-extract-79m)

### Inferences
- Following caller/KOL signals is structurally adverse. The caller buys before posting, and followers provide exit liquidity. The Kakhbod result suggests the popularity of a caller is, if anything, a negative signal.

### Gaps
- Most ZachXBT cases have no court outcome, and subjects dispute them. The sources are mostly crypto media summaries rather than the original on-chain threads.
- No systematic dataset of Telegram/Discord "VIP signal" group performance was found.

## Q4. TradingView community scripts: does forward performance hold?

### Takeaway
No systematic study of out-of-sample performance of top TradingView community scripts was found. Available evidence is a single rebuild and community warnings about overfitting and repainting.

### Cited Findings
- [ANALYSIS] A viral 3,888% TradingView strategy rebuilt causally with costs landed near coin-flip, PF ~0.8-1.0 (see Q2). — [dev.to](https://dev.to/umam75/i-rebuilt-a-viral-3888-return-tradingview-strategy-it-landed-almost-exactly-at-coin-flip-odds-2hj7)
- [ANECDOTE] TradingView's community "strategytester" ideas include quant warnings that "your backtest lies" because of overfitting. — [TradingView](https://www.tradingview.com/ideas/strategytester)

### Inferences
- Popular-script results shown in the Strategy Tester are in-sample and often use default zero commissions/slippage. Forward holding should be presumed weak unless independently retested.

### Gaps
- No academic or large-scale forward-test of TradingView "Editors' Picks" or most-liked scripts was found.

## Q5. Facebook groups/pages, forex "account management" and signals: scam patterns and regulator warnings (SEC Thailand, FCA, CFTC, FBI)

### Takeaway
Regulators in Thailand, the UK and the US all identify social media as the main channel for trading scams. The recurring patterns are pig-butchering or relationship scams, fake regulator/exchange pages and unauthorised finfluencer promotion of forex/CFD schemes. Losses run to billions of USD per year.

### Cited Findings
- [VERIFIED] SEC Thailand's hotline received more than 1,500 suspected-scam calls in Sept 2025, double August's figure. Most scams were on social media. — [Nation Thailand, Nov 2025](https://www.nationthailand.com/business/investment/40057637)
- [VERIFIED] SEC Thailand: ~32,000 digital-asset mule accounts were suspended between Jan and 30 Sep 2025. — [Nation Thailand](https://www.nationthailand.com/business/banking-finance/40057252)
- [VERIFIED] SEC Thailand works with Facebook, Instagram, TikTok and LINE to block scam ads. It launched the "Cyber Check" LINE screening tool and a social-media whitelist (Dec 2025), plus a Meta × SEC "Protect Yourself from Investment Scams" campaign (Jul 2025) covering 4 scam types. Investment Scam Hotline: 1207 ext. 22. — [FastBull on Meta/SEC campaign](https://www.fastbull.com/brokersview/news/meta-and-thai-sec-launch-investment-scam-awareness-campaign-highlight-4-scams-to-watch-for-265796); [Bangkok Post](https://bangkokpost-xkgxtn.cdn.byteark.com/business/investment/2867468/securities-and-exchange-commission-sounds-alarm-on-fraud)
- [VERIFIED] IOSCO I-SCAN lists SEC Thailand warnings on specific Facebook pages, e.g. "ยีราฟพารวย", "Life is investment" (Jul 2025) and "โลกคริปโตไทย". — [I-SCAN 55784](https://www.iosco.org/i-scan/?id=55784); [I-SCAN 39102](https://www.iosco.org/i-scan/?id=39102); [I-SCAN 57998](https://www.iosco.org/i-scan/?id=57998)
- [VERIFIED] Thailand's Ministry of Digital Economy warned about a fake Facebook page impersonating the SET that promoted "gold stock"/SET50 investments with daily dividends. — [Pattaya Mail](https://www.pattayamail.com/?p=524836)
- [VERIFIED] FCA (UK): in 2024 it charged nine people, including reality-TV stars, over the Instagram account @holly_fxtrends promoting an unauthorised forex/CFD scheme (FSMA s.21, max 2 years). Influencers were later sentenced at Southwark Crown Court, including Aaron Chalmers. In June 2025 the FCA led an international finfluencer crackdown with nine regulators across six countries. — [FCA first court appearance](https://www.fca.org.uk/news/press-releases/first-court-appearance-three-finfluencers-charged-fca-led-global-crackdown-illegal-promotions); [FCA sentencing](https://www.fca.org.uk/news/press-releases/geordie-shore-star-illegal-finfluencer-sentenced-promoting-high-risk-investments-social-media); [FCA international crackdown](https://www.fca.org.uk/news/press-releases/fca-leads-international-crackdown-illegal-finfluencers)
- [VERIFIED] CFTC advisories (2022, 2024, 2025) on relationship investment ("pig butchering") scams. Contact starts on dating or social apps, or with a "wrong number" text. The scammer moves the chat to private messaging, claims wealth from forex/crypto "insider" trading and steers the victim to a fake trading site. The 2025 advisory cites FBI-reported losses of nearly $4B in 2023. — [CFTC Relationship Investment Scam alert](https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/RelationshipInvestmentScam.html); [CFTC six warning signs](https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/RomanceScam.html); [CFTC release 8492-22](https://www.cftc.gov/PressRoom/PressReleases/8492-22)
- [VERIFIED, via secondary coverage] FBI IC3 2024: total internet-crime losses were $16.6B. Crypto-related losses were $9.3B (+66% YoY), of which crypto investment fraud was ~$5.8B, with 149k+ crypto complaints. Victims aged 60+ lost more than $2.8B. Operation Level Up notified 4,323 victims. — [TRM Labs on IC3 2024](https://www.trmlabs.com/resources/blog/a-record-breaking-year-for-cybercrime-key-findings-from-the-fbis-2024-ic3-report-k1c94); [crypto.news](https://crypto.news/fbi-ties-over-9b-in-2024-fraud-losses-to-crypto-scams-led-by-pig-butchering-schemes/)

**Red flags compiled from the regulator sources above**
- Guaranteed or daily returns, and "account management" where you hand over credentials or deposit to a "manager" (Pattaya Mail SET page; CFTC "high returns with little or no risk").
- A move from Facebook/dating/TikTok to LINE/WhatsApp/Telegram private chat (CFTC).
- A trading platform that is new or unregistered. Check domain age with the ICANN lookup and check the regulator register / SEC Thailand Cyber Check (CFTC; SEC TH).
- Influencer lifestyle marketing of forex/CFD without authorisation (FCA cases).
- Impersonation of regulators, exchanges or famous people (DE/SET fake page; ZachXBT fake personas).

### Inferences
- In Thailand specifically, the dominant risk is not a "bad strategy" but outright fraud via Facebook/LINE/TikTok. Verifying the licence (SEC whitelist/Cyber Check) matters before any strategy evaluation.

### Gaps
- I did not open the FBI IC3 primary PDF. The figures come from consistent secondary coverage.
- No quantified data was found on Thai losses specifically from forex "account management" (MAM/PAMM) offers.

## Q6. Verified small-account growth: Myfxbook/FXBlue, prop firms and blow-up rates

### Takeaway
I found no formal study of the survival or blow-up rates of Myfxbook/FXBlue verified accounts. "Verified" on Myfxbook only confirms that the data matches the broker, not that the account is profitable or representative. The best large-sample proxy (prop-firm data) shows only ~7% of challenge buyers ever receive a payout.

### Cited Findings
- [ANALYSIS] Myfxbook's verified badge confirms that track-record data matches broker records. It does not mean profitable, and it says nothing about hidden sibling accounts. — [TakeProfit Myfxbook review 2026](https://takeprofitapp.com/en/learn/myfxbook-review-2026); [BabyPips guide to Myfxbook accounts](https://forums.babypips.com/t/a-guide-to-using-and-recognising-myfxbook-accounts/52656)
- [ANECDOTE/illustrative] The common survivorship trick: run ~10 aggressive accounts, quietly blow up 9 and market the survivor. — [dev.to "How to read a Myfxbook record"](https://dev.to/xauusdrobot/how-to-read-a-myfxbook-record-before-trusting-any-trading-ea-cc7)
- [ANECDOTE] Forex Peace Army documents fake Myfxbook pages, e.g. PDFs styled as Myfxbook exports, used in EA/signal sales. — [Forex Peace Army](https://www.forexpeacearmy.com/forex-books/205/fake-myfxbook-accounts-scam)
- [ANECDOTE, unsourced] Claims that "most popular AutoTrade strategies blow up within 6-18 months" circulate without data. Treat them as opinion. — [TakeProfit](https://takeprofitapp.com/en/learn/myfxbook-review-2026)
- [ANALYSIS] No regulator publishes a survival rate for copy-trading strategy providers, and copy-trading leaderboards reward risk-taking. — [BrokerListings research](https://brokerlistings.com/research-hub/copy-trading-blow-ups)
- [ANALYSIS] Finance Magnates analyzed 300,000+ prop-firm accounts (FPFX data, multiple firms). ~14% passed the challenge, and ~45% of those got a payout, so ~7% of all buyers were paid. A separate summary of the same data says 86% failed before funding. — [Finance Magnates exclusive](https://www.financemagnates.com/forex/exclusive-only-7-of-300000-prop-trading-accounts-achieved-payouts/); [Finance Magnates 80% fail](https://www.tradingview.com/news/financemagnates:b64d2ea39094b:0-80-fail-in-prop-trading-globally-south-american-traders-aim-to-reverse-the-trend/)
- [ANALYSIS] A 2026 "Velotrade" transparency report reached the same ~7% payout / 93% never-paid figure. — [CoinGape](https://coingape.com/blog/93-of-funded-prop-traders-never-see-a-payout-a-new-report-explains-why/)
- [VERIFIED: company-reported] FTMO reported paying traders 80% more in Jan-Jul 2024 than a year earlier, and more than $450M paid in total by its 10th anniversary. It does not disclose the share of traders paid. — [Finance Magnates FTMO $450M](https://www.financemagnates.com/forex/ftmo-announces-over-450-million-paid-out-as-prop-trading-firm-turns-10/); [TradeInformer on FTMO finances](https://tradeinformer.com/prop-weekly/what-ftmo-tells-us-about-prop-firm-finances)

### Inferences
- For "fast growth from a small account", the realistic verified benchmark is closer to "≈7% of prop challengers ever get paid" and "74-89% of CFD accounts lose" than to the top of a Myfxbook leaderboard. Leaderboard tops are a survivorship-selected sample.
- A credible verified record needs a long history (≥1-2 years), a published max drawdown, no gaps or deposits masking losses, and a disclosure of all accounts run by the same provider.

### Gaps
- Typical monthly returns and blow-up rates of top Myfxbook/FXBlue accounts were not obtainable. There is no published study, and I did not scrape the leaderboards. Building a dataset by tracking public accounts over time would be needed.
- No independently verified (broker-statement-audited) viral "$100 → $10,000" small-account story was found in 2020-2026 sources.
