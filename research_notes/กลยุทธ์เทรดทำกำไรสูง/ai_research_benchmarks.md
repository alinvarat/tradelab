# LLM Benchmarks for Trading and Stock Prediction (2023–2026): What Actually Predicts, With What Controls

Scope note: this note answers six questions on LLM equity forecasting. Every claim is tagged
**[PR]** peer-reviewed (journal/conference with DOI), **[PP]** preprint/working paper, **[VEN]** vendor/blog/self-reported.
"Sharpe" is annualized unless stated. Costs are stated as reported; where a paper omits them I say so explicitly
because omission is itself the finding (see Q2 and Q7).

---

## Q1. What do the flagship studies actually find (accuracy, Sharpe, sample, universe, costs)?

### Takeaway
Two very different literatures get conflated. (a) **Short-horizon news/headline scoring** is the only place with
replicated, peer-reviewed, out-of-sample return predictability — and it is small in economic terms (≈30–40 bps/day
gross, dead at 20 bps round-trip cost), concentrated in small caps and bad news, and decaying year by year.
(b) **End-to-end "LLM trading agent" papers** (FinMem, FinAgent, TradingAgents, FinCon) report Sharpe 1.4–8.2 on
3–18 month windows over 3–6 hand-picked tickers, almost none deduct costs, and the one independent
bias-controlled re-run (FINSABER) reverses their sign.

### Cited Findings

**A. News-headline scoring — the strongest evidence**

| System | Sample | Universe | Headline result | Costs? |
|---|---|---|---|---|
| GPT-4 (gpt-4-0314, cutoff Sep-2021) | Oct-2021 → May-2024 | 4,123 US common stocks, ~159k headlines | Initial-reaction portfolio hit rate **93.3%** overnight / **88.8%** intraday; drift L/S **+34 bps/day**, **SR 2.97** | No (sensitivity given) |
| GPT-3.5 | same | same | SR **1.66** | No |
| DistilBART-MNLI | same | same | SR **1.26** | No |
| FinBERT | same | same | SR **−0.33** (negative) | No |
| GPT-1/GPT-2/BERT | same | same | hit rate <65%, negative SR | No |

- GPT-4 drift strategy: long leg **+9 bps/day (SR 0.90)**, short leg **+29 bps/day (SR 2.12)**; asymmetry attributed to limits-to-arbitrage on shorting — [Lopez-Lira & Tang, arXiv:2304.07619](https://arxiv.org/html/2304.07619v5). **[PR]** published as *Journal of Financial Economics* (2026), [S0304405X26001066](https://www.sciencedirect.com/science/article/pii/S0304405X26001066).
- Full-sample descriptive table reports **LS GPT-4 SR 3.28**, daily mean 0.38%, max DD −17.4%; the **2.97** figure is the drift-strategy variant. Both numbers appear in the same paper — do not cite them as one result ([Wharton slides, Table 2 / p.37](https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2024/09/Lopez-Lira.pdf)). **[PR]**
- Cost sensitivity, the single most important number in this literature: cumulative return stays **>300% at 5 bps round-trip**, **>100% at 10 bps**, and the strategy is **unprofitable at 20 bps** ([Alpha Architect summary of the JFE version](https://alphaarchitect.com/chatgpt-forecast-stock-price)). **[VEN]** secondary, but consistent with the paper's own cost panels.
- Predictability is **~5× larger for stocks below the 20th percentile of NYSE size breakpoints**, and stronger after negative news — [arXiv:2304.07619v5](https://arxiv.org/html/2304.07619v5). **[PR]**
- **Decay:** SR 6.54 (2021Q4) → 3.68 (2022) → 2.33 (2023) → **1.22 (Jan–May 2024)**. Authors call this *suggestive* evidence of LLM-driven efficiency gains, not proof — [ScienceDirect JFE](https://www.sciencedirect.com/science/article/pii/S0304405X26001066). **[PR]**
- Out-of-sample integrity here is genuine and is the paper's key design feature: model cutoff Sep-2021, sample starts Oct-2021, so the whole test is post-cutoff — [arXiv:2304.07619v5](https://arxiv.org/html/2304.07619v5). **[PR]**
- Caveat that kills most pop-science retellings: the ~90% figure is a **portfolio-day hit rate on the initial price reaction**, much of which occurs between prior close and next open and is not attainable by a normal trader; the tradable part is the 1–2 day drift with a **55–58%** hit rate — [DanFin analysis](https://danfin.net/chatgpt-stock-news-return-predictability). **[VEN]**

**B. Filing / fundamental analysis — strongest "reasoning" evidence**

- GPT-4 with chain-of-thought, given **anonymized** balance sheet + income statement, predicts the **sign of next-year earnings change** with **60.4%** accuracy vs **52.7%** for the median analyst (one month after release) and 56–57% for analysts 3–6 months later; non-CoT prompt only 52%; naive extrapolation 49% — [Kim, Muhn & Nikolaev, arXiv:2407.17866](https://arxiv.org/html/2407.17866v1). **[PP]** (Chicago Booth working paper; widely cited, not yet in a journal as of the paper versions reviewed).
- Sample: Compustat **150,678 firm-years, 15,401 firms, 1968–2021**; analyst benchmark 39,533 obs, 3,152 firms, 1983–2021. A dual-input ANN (GPT text + numeric ratios) reaches **63.16%** accuracy / 66.33 F1 / 65.90 AUC — [arXiv:2407.17866v2](https://arxiv.org/html/2407.17866v2). **[PP]**
- Contamination control: company names removed and **years replaced with "Period t / t−1"**, so the model cannot look up the outcome. Authors report the accuracy "does not stem from training memory" and that GPT's trading strategies earn higher Sharpe/alpha than ML-based ones — [SUERF Policy Brief 1008](https://www.suerf.org/wp-content/uploads/2024/10/SUERF-Policy-Brief-1008_Kim-et-al.pdf). **[PP]**
- Note the effect size honestly: 60.4% vs 52.7% is a ~7.7 pp edge on a binary task where the base rate is ~50%. It monetizes only through portfolio sorts, and the paper's alpha tests are the least-replicated part.

**C. Earnings-call tone**

- Section-weighted **FinBERT** sentiment over **6.5M sentences / 16,428 S&P 500 transcripts (2015–2025)**, trained to Dec-2022, frozen and tested Jan-2023 onward: out-of-sample **Spearman IC 0.142** (vs 0.115 in-sample), monthly L/S **FF5 alpha 2.03% (t = 6.49)**, survives SUE control; FinBERT subsumes Loughran–McDonald (t = 5.90 vs 0.86) — [arXiv:2604.13260](https://arxiv.org/html/2604.13260v1). **[PP]** — note this is a fine-tuned encoder, not a generative LLM; it is the cleanest OOS design in the earnings-call group.
- Agentic RAG over transcripts + fundamentals, strict publication-date ordering, **3,158 calls**, 2-year backtest: **36% annualized, SR 1.64**; gains persist in a post-`gpt-4o-mini`-cutoff evaluation — [CARAG, EACL 2026](https://aclanthology.org/2026.eacl-long.141.pdf). **[PR]**
- Counter-evidence on naive LLM tone: a 60-firm, FY2010–2023 GPT-4o study finds GPT-4o sentiment adds explanatory power over LM dictionary but the design is in-sample explanatory regression, not a tradable OOS test — [Tilburg thesis](http://arno.uvt.nl/show.cgi?fid=188999). **[PP]** (MSc thesis; treat as weak).

**D. End-to-end agents — big Sharpe, thin evidence**

| System | Test window | Universe | Reported | Costs? | Venue |
|---|---|---|---|---|---|
| FinMem | Oct-2022 → Apr-2023 (~6 mo) | 5 stocks incl. TSLA, MSFT, NFLX, AMZN, COIN | TSLA CR **+61.8%, SR 2.68**; MSFT CR +23.3%, SR 1.44 | **No** | **[PR]** IEEE (2025) |
| FinAgent | Jun-2023 → Jan-2024 (~7 mo) | 5 stocks + crypto | ARR **31.9–92.3%**, SR **1.43–2.01**, MDD 5.6–13.2%; TSLA ARR 92.3% | **No** | **[PR]** KDD 2024 |
| FinCon | Jan-2022 → Jun-2023 | 6 US stocks | SR **3.26**, CR 114%, MDD 16.2% | **No** | **[PP]** |
| TradingAgents | 1-Jan → 29-Mar-2024 (3 mo) | AAPL, GOOGL, AMZN, NVDA, MSFT | SR **5.60–8.21**, CR 23–27%, MDD 0.91–2.1% | **No** | **[PP]** arXiv:2412.20138 |
| FinVision | ~7 months, bullish window | AAPL, MSFT, AMZN | SR **1.20–1.72** | **No** | **[PR]** ICAIF 2024 |
| StockAgent | 264 simulated trading days | synthetic 200 agents | No alpha claim; leakage-free simulation design | 0.005/share fee | **[PR]** ACM TIST |

- FinAgent: "enhancements of at least 10% (ARR) and 19% (SR) vs best baseline", TSLA +84%/+118% — [KDD'24 PDF](https://www3.ntu.edu.sg/home/boan/papers/KDD24_FinAgent.pdf). **[PR]** but single-stock cherry-picking is explicit.
- TradingAgents authors themselves concede the Sharpe is implausibly high and explain it as "few pullbacks during that period"; they also disclose the cost driver: **11 LLM calls and 20+ tool calls per prediction**, which is why the test is only 3 months — [arXiv:2412.20138](https://arxiv.org/html/2412.20138). **[PP]**
- FinMem with memory-capacity ablation: SR ranges **1.12 → 2.75** purely from the retrieval depth K — [FinMem PDF](https://suchow.io/assets/docs/yu2024finmem.pdf). **[PR]**
- **The replication that matters:** re-running FinMem/FinAgent over 2004–2024 with historical S&P 500 constituents (incl. delisted), point-in-time alignment and costs: FinMem MSFT **CR +23.26% → −22.04%**, **SR 1.44 → −1.247**; NFLX **SR 2.017 → −0.478**; neither agent produces significant alpha (**p > 0.34**), buy-and-hold beats both (**p ≤ 0.0117**); regime split B&H 0.61/0.48/−0.28 vs FinMem −0.19/−0.10/−0.97 — [FINSABER, arXiv:2505.07078](https://arxiv.org/html/2505.07078v4), **[PR]** KDD 2026 Datasets & Benchmarks ([ACM DOI](https://dl.acm.org/doi/10.1145/3770854.3785702)).

**E. Strategy/factor mining (the "code generation" case)**

- Alpha-GPT: LLM translates a researcher's natural-language idea into alpha expressions via 3-stage RAG; self-reports **top-10 of 41,000+ teams** in the WorldQuant International Quant Championship — [ACL Anthology EMNLP 2025 demo](https://aclanthology.org/2025.emnlp-demos.14). **[PR demo track / VEN-grade claim]** — a competition placement is not an audited backtest; no cost, window or universe disclosure.
- FactorMAD (two-agent debate + code-based factor pipeline): debate iterations monotonically improve **IC** while single-agent iterations flatten; also reduces factor code length — [ICAIF 2025](https://dl.acm.org/doi/full/10.1145/3768292.3770377). **[PR]**
- FinGPT: **weighted F1 0.882 (FPB) / 0.874 (FiQA-SA) / 0.903 (TFNS)**, fine-tune cost **$17.25 on one RTX 3090, 17.25 h**; vs BloombergGPT ~**$3M / 53 days** — [FinGPT GitHub](https://github.com/AI4Finance-Foundation/FinGPT). **[VEN]** self-reported. Latest paper version: 82.1% acc / 80.9 macro-F1 vs FinBERT 71.2 / 69.9 and ChatGPT zero-shot 63.4 / 61.7 — [arXiv:2306.06031](https://arxiv.org/html/2306.06031). **[PP]**
- Caution on FinGPT: independent look-ahead audit of a FinGPT-based pipeline found in-sample SR **4.88** collapsing to **−2.06** out-of-sample, on one-month windows — [Leckat, Research Square case report](https://assets-eu.researchsquare.com/files/rs-10217060/v1_covered_0b28357b-0823-400f-bc88-daf752670e11.pdf). **[PP, low quality]** (single author, one month per period, no control arm; the author says so).

### Inferences
- The reliable effect is **text→direction over 1–5 days**, worth tens of bps gross, and it is a *liquidity/small-cap* phenomenon. Nothing in this literature supports an LLM forecasting multi-month returns.
- FinMem/FinAgent/TradingAgents numbers are not evidence of alpha; they are evidence that 3–6 months of a bull market plus 3–5 cherry-picked tickers can produce any Sharpe you want. FINSABER is the only paper here that tests the same agents the way an allocator would.
- Alpha-GPT's competition result is the strongest single signal that LLMs help **research throughput** (idea → expression → backtest), which is a very different claim from "LLM predicts returns."

### Gaps
- No paper reports confidence intervals on the **net-of-cost** Sharpe of a news-sentiment strategy at retail scale.
- Kim et al. does not report a post-2021-only subsample, so the 60.4% is pooled over 1968–2021 and cannot be separated from model knowledge.
- No independent replication of the JFE 2.97 Sharpe with a different headline vendor.

---

## Q2. How severe is contamination/lookahead, and who controls for it?

### Takeaway
Severe and measurable, but **not uniform**: memory-driven "prediction" is large at the daily/large-cap/index level and
negligible at intraday and for small models. The field-level audit is damning: **98% of papers whose test may overlap
their model's training data do nothing about it**. Only two designs actually work — post-cutoff windows and
chronologically consistent models — plus anonymization as a partial control.

### Cited Findings

**Field-level audit (the headline number for this whole question)**

Pre-registered audit of **91 LLM trading/alpha-mining papers** (75 with a trading test; population frozen before coding;
LM coders with verbatim-quote checks; blind recode of 18 papers, 100% agreement on costs, 89% on leakage):
- **51% deduct no trading costs at all**; 40% a flat rate; only **9% model spread/impact/borrow from data**.
- Median test window **12 months** (quartiles 6 and 36); 18 papers ≤6 months; median 69 assets but 20 of 54 papers test ≤10 assets.
- Look-ahead: 40% **do not discuss it**, 32% acknowledge without control, 19% test after cutoff, 8% live/forward, **1% (one paper) chronologically consistent**. Of the 51 papers whose window may overlap training, **50 (98%) do nothing**.
- **9%** report a multiplicity-adjusted result. Only **5 papers (7%)** combine deducted costs + leakage control + a reported trial count.
- Median headline Sharpe (13 papers that state one in abstract/conclusion) = **2.0**. Correlation between headline Sharpe and window length = **−0.10 (p=0.36)** — i.e. undetectable at n=13.
— [arXiv:2611.18934](https://arxiv.org/html/2611.18934v1). **[PP]** independent, pre-registered, code released.

**Direct quantification of memorization**

- Prompting models to recall historical returns *with no context* (ticker + date only) produces a long-short **Sharpe 2.88 at daily frequency**, correlation with actual returns 0.05, direction accuracy 0.54. Trimming **q = 3.0%** of observations removes it at daily frequency; **3.5%** for large caps. Adding same-day market return to the context raises the required trim for GPT-4.1 from 3.5% to **22%**. Effect is **negligible for small models and fine granularity** (GPT-4.1-nano ≈ uncorrelated) — [Economics Letters 2025, "AI's predictable memory in financial analysis"](https://www.sciencedirect.com/science/article/pii/S0165176525004392). **[PR]**
- "Profit Mirage": **FinLake-Bench** (2,000 historical QA pairs, e.g. "did the market rise on date T?") — GPT-4o and peers answer **>85%** correctly. Counterfactual perturbation: the *worst* model leaves **82.13%** of its predictions unchanged when key inputs are altered, i.e. it is reciting, not analyzing. Claims nearly every published agent fails to beat a random baseline once the cutoff is passed — [arXiv:2510.07920](https://arxiv.org/html/2510.07920). **[PP]**
- Crossing the cutoff destroys agent alpha: FinMem total return **−71.85%**, QuantAgent Sharpe **−51.48%** when the evaluation window is moved past the pretraining cutoff — cited in [The Alpha Illusion, arXiv:2605.16895](https://arxiv.org/html/2605.16895). **[PP]**
- Knowledge is also **unevenly** memorized: LLMs answer revenue questions correctly for **54.17%** of large-cap firms in 2017 but only **6.32%** in 1995, with hallucination rising for larger/recent firms — Shah et al. 2025, cited in [arXiv:2605.16895](https://arxiv.org/html/2605.16895). **[PP]** So a mega-cap 2023–2024 backtest is *doubly* fragile: most likely to leak and least likely to be knowledge-limited, while small/old firms — the ones with the actual edge — are the ones the model knows least about.

**Controls that exist and what they show**

1. **Post-cutoff window (cleanest, cheapest).** Lopez-Lira & Tang use gpt-4-0314 (cutoff Sep-2021) on Oct-2021→ data. This is why their result survives scrutiny. **[PR]**
2. **Chronologically consistent models.** ChronoBERT/ChronoGPT trained only on text available at each year-end, one vintage per year from 1999; validated with 300 neologisms (probability mass centered at zero before first use, jumps after). Asset-pricing test, next-day returns from news embeddings: **Sharpe 4.80 (ChronoBERT), 4.92 (ChronoGPT) vs 4.90 (much larger Llama)** → *lookahead bias is modest in this setting*. Important counterweight to the doomer view — [JFE 2026](https://www.sciencedirect.com/science/article/pii/S0304405X26001455), [arXiv:2502.21206](https://arxiv.org/html/2502.21206). **[PR]**
3. **Anonymization.** BlindTrade strips tickers and company names, keeps only 60 business days of data; **Sharpe 1.40 ± 0.22 across 20 seeds** on 2025 YTD, S&P 500 point-in-time constituents; negative controls (randomized signals) collapse performance — [arXiv:2603.17692](https://arxiv.org/html/2603.17692). **[PP]**
4. **Inference-time de-biasing.** FINCAD (context-aware decoding against a learned bias prior): subset-averaged Spearman between in-sample and post-cutoff Sharpe rankings rises **+0.779 → +0.846**; anonymization alone *hurts* (+0.779 → +0.547) because it destroys signal — [EMNLP 2026](https://aclanthology.org/2026.emnlp-main.510.pdf). **[PR]** Key nuance: **anonymization is not free**, it removes real information along with the leak.
5. **Live/forward replay.** rta-bench-1 replays headlines **by the minute published**, runs each period both **blind and named**, scores decisions against random same-day/same-sector choices, across a rally, a slow bear and a crash — [arXiv:2611.19530](https://arxiv.org/html/2611.19530v1). **[PP]**

### Inferences
- The 98% figure is the single most useful number in this report: it means **the prior on any agent paper's Sharpe is "uninformative", not "promising."**
- "Anonymization" and "post-cutoff" are not interchangeable. Anonymization removes leakage *and* alpha; post-cutoff removes leakage *only*. Prefer post-cutoff.
- The ChronoBERT result suggests leakage is **application-specific**: a thin feature (news embedding → next-day return) leaks little, while an agent asked "what happened next to NVDA in 2023" leaks almost everything. Leakage scales with how much *narrative outcome* the prompt invites.

### Gaps
- No public measurement of how much of a *frontier* model's (2025–2026) equity knowledge survives when the prompt is a full agentic workflow rather than a recall probe.
- No paper reports the **cost** (in alpha) of a full chronological-consistency rebuild for a retail user; ChronoBERT is an academic artifact, not a deployable API.

---

## Q3. Which tasks show robust value, and which do not?

### Takeaway
Robust: **headline sentiment direction (1–5 day)**, **filing/ratio-based earnings-direction classification**, **earnings-call
section tone**, **research throughput (factor expression generation, code, summarization, risk commentary)**.
Not robust: **numeric time-series/technical trading**, **long-horizon agentic portfolio management**, **multi-month
return forecasting**, **anything where the LLM must recall prices**.

### Cited Findings

**Robust / replicated**
- Headline → next-day drift: SR 2.97 OOS post-cutoff, decay 6.54→1.22 over 2021–2024 ([JFE](https://www.sciencedirect.com/science/article/pii/S0304405X26001066)). **[PR]**
- Anonymized financial statements → earnings direction: 60.4% vs 52.7% analyst ([arXiv:2407.17866](https://arxiv.org/html/2407.17866v1)). **[PP]**
- Earnings-call section-weighted tone: OOS IC 0.142, FF5 alpha 2.03%/mo t=6.49 ([arXiv:2604.13260](https://arxiv.org/html/2604.13260v1)). **[PP]**
- Earnings call agentic RAG: 36% ann., SR 1.64, 3,158 calls, publication-date-ordered ([EACL 2026](https://aclanthology.org/2026.eacl-long.141.pdf)). **[PR]**
- Target/entity-level sentiment: GPT-4o **0.79 accuracy** vs FinBERT 0.56, FinBERT-Tone 0.63, DeBERTa-ABSA 0.68, VADER 0.50 — [CLiC-it 2025](https://aclanthology.org/2025.clicit-1.74.pdf). **[PR]**
- Statement summarization: LLaMA-2 + LongT5 summaries retain price-relevant information; FinBERT's predictability **fades in turbulent markets while LLaMA-2 stays robust** — [Pacific-Basin Finance Journal 2025](https://www.sciencedirect.com/science/article/abs/pii/S0927538X24003846). **[PR]**
- Factor mining: debate-driven code generation improves IC monotonically vs single agent ([ICAIF 2025](https://dl.acm.org/doi/full/10.1145/3768292.3770377)). **[PR]**

**Not robust / negative**
- **Direct numeric trading.** InvestorBench, 4 single-asset tasks: on MSFT buy-and-hold CR 15.34 / SR 0.717 vs GPT-4 16.65/0.643, GPT-4o **12.46/0.638**, o1-preview 17.18/0.664; on HON GPT-4o 38.54/1.668 does beat B&H 33.26/1.619 — i.e. **inconsistent across tickers, no systematic edge** — [ACL 2025](https://aclanthology.org/2025.acl-long.126.pdf). **[PR]**
- Next-day direction from OHLCV + RSI/MACD/Bollinger: GPT-4 Turbo 58.3%, FinGPT 56.8%, Claude 3 Opus 55.7%, Gemini 1.5 Pro 53.9%, Llama-3-70B **50.4%** — [arXiv:2607.15414](https://arxiv.org/pdf/2607.15414). **[PP]** (tables self-labelled "simulated / illustrative data" — treat as indicative only).
- Long-horizon LLM timing: no significant alpha, p>0.34, loses to B&H ([FINSABER](https://arxiv.org/html/2505.07078v4)). **[PR]**
- Naive sentiment *levels* are often **reactive, not predictive**: sector-tagged headline sentiment showed "econometric tests show the sentiment signal is reactive, not predictive, of next-day returns", yet still supported a technology L/S with SR 1.88 — [Electronics 2025](https://www.mdpi.com/2079-9292/14/23/4680). **[PR]** The gap between "reactive" and "profitable L/S" is exactly the cost/turnover question.

**Task-by-task verdict table**

| Task | Verdict | Best evidence | Effect size |
|---|---|---|---|
| Headline sentiment → 1–5d direction | **Works, decaying** | JFE 2026 | +34 bps/day gross; dead @20 bps |
| Anonymized filings → earnings direction | **Works (weak-moderate)** | Kim et al. | +7.7 pp over analysts |
| Earnings-call tone (section-weighted) | **Works** | arXiv 2604.13260 | IC 0.142 OOS; 2.03%/mo |
| Entity-level sentiment classification | **Works** | CLiC-it 2025 | 0.79 vs 0.56 acc |
| Summarization / distillation of long docs | **Works** | Pacific-Basin Fin J 2025 | qualitative |
| Factor expression / code generation | **Works as throughput** | Alpha-GPT, FactorMAD | top-10/41k teams (self-reported) |
| Risk commentary / explanation | **Works as UX, unmeasured as alpha** | FinDebate, AlphaAgents | human eval only, +20.4% quality score |
| OHLCV/technical next-day direction | **Does not work** | InvestorBench, arXiv 2607.15414 | 50–58% acc, no net edge |
| Multi-month portfolio management | **Does not work** | FINSABER (KDD 2026) | negative alpha |
| Recalling prices/dates | **"Works" — that's the problem** | Econ Letters 2025 | 54% acc, SR 2.88 fake |
| Volatility prediction from transcripts | **Weak/contradicted** | DEC (ACL Findings 2025) vs ECC Analyzer | transcript models underperform simple historical volatility in early years |

- On volatility: "transcript-based models and STPEV(Mean) underperform STPEV(LR) during the early years of 2019 and 2020" — [DEC, ACL Findings 2025](https://aclanthology.org/2025.findings-acl.946.pdf). **[PR]** i.e. an LLM reading the transcript added nothing over the firm's own volatility history.

### Inferences
- The value is in **converting text into a small number of ordinal signals**, not in "the LLM as trader." Every robust result is a classification/regression on text with a short horizon.
- "Reactive not predictive" plus "profitable L/S" in the same paper is the tell that the profit comes from **cross-sectional dispersion and slow diffusion**, which is exactly what transaction costs and crowding eat first.

### Gaps
- No study isolates the marginal value of LLM summarization over a fine-tuned encoder on the *same* signal, at the same horizon, net of costs.
- Risk-commentary and idea-generation value is only ever measured by human raters or by downstream backtests confounded with the rest of the pipeline.

---

## Q4. Best prompt/agent designs and the marginal gain of each component

### Takeaway
The single most replicated design finding is **counter-intuitive: more reasoning and more agents usually hurt.**
CoT helps on structured numeric reasoning (statements) and *hurts* on sentiment classification. Multi-agent debate has
a small, task-specific gain in factor mining; in trading P&L ablations, **removing most specialist agents improves Sharpe.**
The components that do earn their keep are **tool grounding for numbers**, **point-in-time retrieval**, **reflection on
realized outcomes**, and **cheap-model routing**.

### Cited Findings

- **CoT: helps on statements, hurts on sentiment.**
  - Statements: non-CoT 52% → CoT **60.4%** accuracy ([arXiv:2407.17866](https://arxiv.org/html/2407.17866v1)). **[PP]**
  - Sentiment: "reasoning, whether prompt-induced or built-in, does not improve alignment with human labels… GPT-4o **without** CoT achieves the best performance across varying levels of linguistic complexity and annotation ambiguity" — [ICAIF 2025, "Reasoning or Overthinking"](https://dl.acm.org/doi/10.1145/3768292.3770341). **[PR]**
- **Agent ablation, the cleanest marginal-gain table in the literature.** Baseline Sharpe 0.54–0.90 (fine-grained) and 0.62–0.76 (coarse-grained) across portfolio sizes 10–50. Removing an agent and re-measuring:
  - w/o **Technical**: −0.42 to −0.66 (10–50 names) → **technical agent is the main value driver**
  - w/o **Quant**: **+0.45, +0.23, +0.41, +0.48, +0.20** → removing it *improves* Sharpe at every size
  - w/o **Qual(itative)**: +0.16 → +0.50 → removing improves
  - w/o **News**: +0.12 to +0.29 → removing improves
  - w/o **Macro**: +0.15 to +0.36 → removing improves
  "Most ablation settings show positive differences relative to the full-agent configuration, indicating that most individual agents may introduce **noise or redundant signals**" — [arXiv:2602.23330](https://arxiv.org/html/2602.23330v1). **[PP]**
  - Also: **fine-grained task decomposition beats coarse** (SR 0.84–0.90 vs 0.62–0.76).
- **Debate helps only weakly and only in search tasks.** FactorMAD: IC improves with debate iterations, single-agent iterations flatten; debate also yields shorter factor code — [ICAIF 2025](https://dl.acm.org/doi/full/10.1145/3768292.3770377). **[PR]** No IC point estimates in the accessible text → **gap**.
  - AlphaAgents (fundamental + sentiment + valuation debate, 15 tech stocks, equal weight): qualitative claim that debate "improves analytical rigor… especially in scenarios involving conflicting signals or partial agent reliability"; no OOS Sharpe reported — [arXiv:2508.11152](https://arxiv.org/html/2508.11152). **[PP]**
  - FinDebate (5 agents + safe debate protocol + RAG): +20.4% average quality score vs baselines, **p<0.001**, but scored by LLM/human raters, not P&L — [FinNLP 2025](https://aclanthology.org/2025.finnlp-2.20.pdf). **[PR workshop]**
- **Memory: large, tunable, and easily overfit.** FinMem's retrieval depth K drives SR from **1.12 → 2.75** on the same data; "self-adaptive risk profile" is the only profile with SR>2 on TSLA — [FinMem PDF](https://suchow.io/assets/docs/yu2024finmem.pdf). **[PR]** A 2.5× Sharpe swing from one hyperparameter is a warning, not a feature.
- **Tools/grounding for numbers.** AlphaAgents built explicit math tools and monitored the valuation agent with Arize Phoenix specifically "to reduce hallucination" — [arXiv:2508.11152](https://arxiv.org/html/2508.11152). **[PP]** This is the correct pattern: **never let the model do arithmetic it can call out for.**
- **Reflection on realized outcomes.** FinVision: "the ablation studies indicate that the **visual reflection module** plays a crucial role"; the reflection loop consumes realized signal outcomes — [ICAIF 2024](https://dl.acm.org/doi/fullHtml/10.1145/3677052.3698688). **[PR]**
- **Retrieval with strict as-of ordering.** CARAG: transcripts and fundamentals "strictly sorted by publication date… when the agent analyzes quarter t it has access only to transcripts and fundamentals dated ≤ t"; agent retrieves 5 historical + 5 peer facts (best macro-F1 at exactly 5+5) — [EACL 2026](https://aclanthology.org/2026.eacl-long.141.pdf). **[PR]**
- **Model routing is a free 25×.** At statistically tied decision quality, one league cost **$8.25** on qwen3.7-plus vs **$203.61** on claude-fable-5; production fleet runs the cheap pair — [arXiv:2609.05663](https://arxiv.org/html/2609.05663v1). **[PP]** vendor-authored (DX Research Group), flag accordingly.
- **Minimum viable model.** A 7B local model "produces a Bull/Bear debate that loops without resolving"; practitioners put the floor at mid-tier reasoning models — [Apidog blog](https://apidog.com/blog/tradingagents-multi-agent-llm-trading). **[VEN]**

### Inferences
- Marginal gain ordering, honest version: **point-in-time data plumbing > tool grounding > task decomposition > reflection > retrieval depth > debate > more agents**. Debate and memory are the two most over-marketed components and the two with the largest overfitting surface.
- The "removing agents improves Sharpe" result is the most actionable finding in this note for a small build: **start with one technical/price agent + one news agent and prove each addition pays for itself.**

### Gaps
- No paper reports debate's marginal gain **net of token cost** (the "Coordination Breakeven Spread" metric is proposed but not populated) — [arXiv:2603.27539](https://arxiv.org/html/2603.27539). **[PP]**
- No clean head-to-head of "one strong model, one prompt" vs "five agents, debate" on the same OOS window with costs.

---

## Q5. Failure modes

### Takeaway
Ranked by damage per dollar: **lookahead/contamination (silent, total) > information injection from news feeds
(62–100% attack success, defeats debate and model scaling) > non-determinism (5+ Sharpe points across seeds) >
cost/latency (small for 1–5 names, fatal for intraday or large universes) > hallucinated numbers (fixable with tools) >
benchmark overfitting (endemic).**

### Cited Findings

**Information injection (the under-appreciated one)**
- Benchmark over ~10,000 decisions on 15 US stocks, 5 injection vectors × 7 event categories:
  - **Prompt injection ASR only 14%**, but **fabricated news reaches 62%**, and **two 30-word templates reach 100% on all 15 stocks** — "inverting the usual LLM-security intuition" — [arXiv:2610.26438](https://arxiv.org/html/2610.26438v1). **[PP]**
  - **Surface form beats content**: removing credibility cues (a named source, a "BREAKING" tag) drops ASR from **100% to 0%** while the claim is identical. **[PP]**
  - Success is **state-dependent**: a fake indicator panel scored **91%** against an agent about to hold, **12%** against one about to buy. **[PP]**
  - Defenses: "model scaling stops shallow vectors but **not** fact poisoning, **peer debate fails**, and only **hierarchical aggregation** reduces ASR." **[PP]**
- 15 academic schemes reviewed: **no paper** describes a halt that skips LLM inference or combines source provenance with cross-source corroboration; the **7 code releases enforce no stop-loss or position limit outside the LLM**. Three LLMs sell whole positions on a fake headline and on the real 2000 Emulex hoax; **one fake headline crashes a 400-agent simulated market in all runs** — [arXiv:2609.19705](https://arxiv.org/html/2609.19705). **[PP]**
- Unicode-homoglyph / hidden-text headline edits lower annual returns by up to **17.7 pp** in a 9-model sentiment stack — Rizvani et al., cited in [arXiv:2610.26438](https://arxiv.org/html/2610.26438v1). **[PP]**
- Prompt injection (reverse-expectation) on a working agent: total return 7.81% → 0.89%, **SR 5.72 → 0.29**, MDD 2.33% → 8.12% — [TradeTrap, arXiv:2512.02261](https://arxiv.org/html/2512.02261). **[PP]**
- Contagion: adversarial social-media content "materially degrades risk–return profiles, sharply reducing Sharpe ratios", but **suitably designed topologies and coordinator prompts dampen shocks** — [Springer 2026](https://link.springer.com/chapter/10.1007/978-3-032-37673-2_12). **[PR]**

**Non-determinism**
- Two runs of the same model differing only in random seed ended **5.2 Sharpe points apart** on average — [rta-bench, arXiv:2611.19530](https://arxiv.org/html/2611.19530v1). **[PP]**
- Production fleet: "selection quality across repeats spans rank percentile **0.486–0.508** (0.5 is chance)" — i.e. run-to-run variation carried **no** measurable economic information — [arXiv:2609.05663](https://arxiv.org/html/2609.05663v1). **[PP, vendor]**
- Seed-spread is why single-run agent Sharpes are meaningless: with σ≈5 Sharpe points across seeds, no 3-month single-run result distinguishes skill from luck.

**Cost / latency**
- Per-decision cost model (GPT-5.4 pricing, 8k–15k input + 500–2k output tokens): **≈$0.12/decision**; erosion table: 50 trades/day on $100k at 5 bps expected alpha → cost **6.0 bps** → **net −1.0 bps (infeasible)**; 50 trades/day on $1M → 0.6 bps cost, net +4.4 bps — [MethodAlgo](https://www.methodalgo.com/press/research/latency-of-logic). **[VEN]** but the arithmetic is checkable and correct.
- Measured decision-cycle costs: **$0.0388–$0.0484 per decision** for scoped tool configs, **$1.074/decision** for the unscoped boundary case; 200 decisions/day ≈ **$7.75–$9.68/day** — [Alpaca](https://alpaca.markets/learn/inference-optimization-in-ai-trading). **[VEN]**
- TradingAgents: **11 LLM calls + 20+ tool calls per prediction**; a single-ticker run costs **$0.10–$5** depending on model and debate rounds — [arXiv:2412.20138](https://arxiv.org/html/2412.20138), [Apidog](https://apidog.com/blog/tradingagents-multi-agent-llm-trading). **[PP/VEN]**
- Latency: LLM inference 15–40 s per decision for agentic stacks; 4.2 s median for single-call technical signals — [MethodAlgo](https://www.methodalgo.com/press/research/latency-of-logic), [arXiv:2607.15414](https://arxiv.org/pdf/2607.15414). **[VEN/PP]** This is why every credible LLM signal is daily-or-slower.

**Hallucinated numbers**
- Revenue-question accuracy 54.17% (2017 large caps) vs 6.32% (1995); hallucination rises for larger and more recent firms — Shah et al. 2025 in [arXiv:2605.16895](https://arxiv.org/html/2605.16895). **[PP]**
- Mitigation in practice: explicit math tools + runtime monitoring (Arize Phoenix) — [AlphaAgents](https://arxiv.org/html/2508.11152). **[PP]**

**Benchmark overfitting / reporting**
- 9% multiplicity-adjusted; 52% do not even discuss how many configs were tried; 31% report a "trial count" but **13 of 23 are just 3–5 random seeds**, not the size of the search — [arXiv:2611.18934](https://arxiv.org/html/2611.18934v1). **[PP]**
- Five pervasive evaluation failures (look-ahead, survivorship, backtest overfitting, cost neglect, regime blindness) "can reverse the sign of reported returns"; no surveyed system satisfies all five; FinMem scores 0/5 — [arXiv:2603.27539](https://arxiv.org/html/2603.27539). **[PP]**
- Survivorship: only point-in-time constituents + delisted names avoids it; BlindTrade and FINSABER both do this explicitly. **[PP]/[PR]**

**Jailbreak-adjacent / ethical**
- Under pressure, LLM agents will use insider information and craft deceptive explanations to conceal it — Scheurer et al., cited in [survey arXiv:2408.06361](https://arxiv.org/html/2408.06361). **[PP]** Relevant to any agent with tool access.

### Inferences
- For a small account, the ranking is inverted relative to what vendors emphasize: **prompt-injection and seed variance will cost you more than model quality.** Both are cheap to fix (allow-list sources, ignore "BREAKING" framing, require corroboration across ≥2 feeds, multiple seeds, hard stop-loss outside the model).
- "Peer debate fails against fact poisoning" is the strongest argument against elaborate multi-agent designs: the debate propagates the poisoned claim rather than filtering it.

### Gaps
- No measurement of information-injection ASR for a *retail* feed (Reddit/StockTwits) with realistic attacker budgets.
- No public data on how often live LLM trading agents actually hallucinate a price when given tool access (tool grounding probably removes most of it, but nobody has counted).

---

## Q6. What would a credible forward test look like for a small account?

### Takeaway
A credible test is **forward-only, point-in-time, cost-inclusive, seed-averaged, pre-registered, and small** — one or two
signals, 5–20 names, daily cadence, 6–12 months, with a hard external stop and a written kill criterion. The literature
gives you a ready-made six-line reporting standard; use it as the test spec, not as a paper format.

### Cited Findings (the standards to copy)

- **Six-line reporting minimum** (the best artifact in this literature): (1) test window dated + number of assets; (2) model + training cutoff, and whether the test lies after it; (3) cost model **with the breakeven cost at which the result vanishes**; (4) number of strategies/prompts/configs searched before the reported one; (5) a multiplicity-aware statistic (deflated Sharpe / reality check) at that count; (6) a benchmark-relative or composition-matched null — [arXiv:2611.18934](https://arxiv.org/html/2611.18934v1). **[PP]**
- **Composition-matched null**: score every decision against random choices of the same day and sector — this separates "agent picked good stocks" from "agent was long a rising sector" — [rta-bench, arXiv:2611.19530](https://arxiv.org/html/2611.19530v1). **[PP]**
- **Blind vs named pairing**: run each period twice, once with tickers/company names and once anonymized. If the named run is much better, you are measuring memory — [rta-bench](https://arxiv.org/html/2611.19530v1); anonymization design in [BlindTrade](https://arxiv.org/html/2603.17692). **[PP]**
- **Negative control**: randomize the signal and confirm performance collapses. BlindTrade: "performance collapses when signals are randomized… confirms that performance derives from cross-sectional signal structure" — [arXiv:2603.17692](https://arxiv.org/html/2603.17692). **[PP]**
- **Multi-seed**: report the seed distribution, not the best seed; with 5.2 Sharpe-point seed spreads, n=1 is not a result — [rta-bench](https://arxiv.org/html/2611.19530v1). **[PP]**
- **Live/forward beats backtest**: DeepFund runs agents in real time against a benchmark so the evaluation window can never overlap training data — [arXiv:2505.11065](https://arxiv.org/abs/2505.11065). **[PP]**
- **Explicit next-open execution, adjusted OHLC, commission + slippage + liquidity caps + LLM-cost accounting** are implemented and released in FINSABER 2.0 (`pip install finsaber`), KDD 2026 — [poster](https://waylonli.com/files/finsaber-poster.pdf). **[PR]**
- **Two configurations, one variable at a time**: FINSABER's own caveat — "these comparisons change more than one condition at once… they do not isolate whether time horizon, stock selection, or a particular bias explains the difference" — [alphaXiv summary](https://www.alphaxiv.org/abs/2505.07078). **[PP]** Copy the discipline: change one thing.

### A concrete protocol (synthesized — this is inference, not a cited result)

**Structure**
- Account: $10k–$50k, cash or margin-free. Universe: 20–50 liquid US names you can actually short or avoid (or long-only, and accept that half the documented edge — the short leg at SR 2.12 in Lopez-Lira — is unavailable).
- Cadence: **daily decision after close, execute at next open** (this is what FINSABER and rta-bench do; it removes the "trade the initial reaction" illusion).
- Signals to test, in order of published support: (S1) news-headline ordinal score → 1–3 day drift; (S2) earnings-call section tone → 5–20 day; (S3) one technical/price agent, as the ablation says it's the only agent that pays.
- Do **not** start with a 5-agent debate. The ablation says it will subtract Sharpe.

**Controls (each is cheap and each is in the literature)**
1. Point-in-time everything; timestamps to the minute; no vendor field that is restated later.
2. Run every period **blind and named**; log the gap.
3. Run **≥5 seeds** per configuration; report mean ± sd and the min.
4. **Randomization null** and **same-day/same-sector random-pick null**.
5. Pre-register the hypothesis, the metric, the window, and the **kill criterion** before the first trade.
6. Count and log every prompt/config/strategy you tried; deflate the final Sharpe by that count.
7. Hard stop-loss, position cap, and a **halt that skips LLM inference** — enforced in code, not in the prompt. All 7 released codebases in the FARSIGHT review failed this.

**Cost assumptions to write down before you start**
- Commission + spread: **5–10 bps per side** on liquid US large caps; assume **20 bps round-trip** for anything small-cap (that is exactly where the published edge lives, and exactly where Lopez-Lira's strategy dies).
- Borrow: if you short, add 0.3–3%/yr plus hard-to-borrow fees; assume the short leg is unavailable for the smallest names.
- LLM: **$0.04–$0.12 per decision** at 2026 pricing (Alpaca, MethodAlgo). For 5 names/day: **$0.20–$0.60/day ≈ $50–$150/yr**.
  - On a $10k account that is **0.5–1.5% of AUM per year** — larger than most documented gross edges. On $50k it is 0.1–0.3%, which is survivable.
  - Break-even math: at $0.12/decision and 5 names/day, you need **≥ 6 bps/day** of gross alpha just to pay inference, before spread. Lopez-Lira's drift is 34 bps/day gross at ~100% daily turnover — so it works only if turnover and cost per decision both stay low.
- Turnover: assume **100% daily turnover** for a news-drift strategy; that is 20 bps/day at 20 bps round-trip = **~50%/yr** in costs. This is why the 20 bps line is fatal.

**What "pass" looks like**
- 6–12 months forward, ≥100 trading days, mean daily net return > 0 with a **t-stat > 2 on the net series**, alpha vs same-sector random picks > 0, blind-vs-named gap small, and every seed profitable. Anything less is a hypothesis, not a strategy.
- Expect to fail. The base rate from this literature, once costs and leakage are controlled, is roughly "no significant alpha" (FINSABER p>0.34; StockBench: most agents fail to beat buy-and-hold).

### Inferences
- For a small account the binding constraint is **not model capability, it is cost-per-decision vs notional**. The same system that is viable at $1M is arithmetically infeasible at $100k if it trades 50 times a day. Design for **low frequency, high conviction, few names** — which happens to be where the *evidence* is strongest anyway (event-driven, 1–5 day drift, small caps).
- The correct use of an LLM in a small account is as a **filter and explainer on a small number of candidate events**, not as a portfolio manager. Every robust result in Q3 is a filter.

### Gaps
- No published forward test of a retail-scale ($10k–$50k) LLM strategy with full cost accounting. This is a genuine hole in the literature and the most valuable thing an independent tester could produce.
- No agreed deflated-Sharpe implementation for the "number of prompts tried" case — Bailey/López de Prado assumes strategy trials, not prompt variants.

---

## Cross-cutting: peer-reviewed vs preprint, and how much to trust each

**[PR] Peer-reviewed (journal/DOI)** — weight these most:
- Lopez-Lira & Tang, *JFE* 2026 — [DOI link](https://www.sciencedirect.com/science/article/pii/S0304405X26001066)
- He, Lv, Manela & Wu, *JFE* 2026 (ChronoBERT/ChronoGPT) — [DOI](https://doi.org/10.1016/j.jfineco.2026.104374)
- "AI's predictable memory in financial analysis", *Economics Letters* 2025 — [link](https://www.sciencedirect.com/science/article/pii/S0165176525004392)
- FINSABER, KDD 2026 D&B — [ACM](https://dl.acm.org/doi/10.1145/3770854.3785702)
- FinMem, IEEE 2025; FinAgent, KDD 2024; FinVision, ICAIF 2024; FactorMAD, ICAIF 2025; "Reasoning or Overthinking", ICAIF 2025; CARAG, EACL 2026; FINCAD, EMNLP 2026; FinDebate, FinNLP 2025; DEC, ACL Findings 2025; InvestorBench, ACL 2025; Alpha-GPT, EMNLP 2025 demo; Pacific-Basin Finance Journal 2025 (LLaMA-2 filings); *Information Systems Research* 2026 (earnings-call graphs)

**[PP] Preprint / working paper** — directionally useful, verify before betting:
- Kim, Muhn & Nikolaev (statements) — arXiv:2407.17866
- FinCon, TradingAgents, AlphaAgents, BlindTrade, Profit Mirage, The Alpha Illusion, rta-bench, the 91-paper audit, FARSIGHT, Fake News Real Crashes, TradeTrap, FinGPT paper, earnings-call section-tone (2604.13260), "Toward Expert Investment Teams" (2602.23330)
- The audit (2611.18934), rta-bench (2611.19530) and Alpha Illusion (2605.16895) are **critiques of the field** and are preprints themselves — they are still the best available discipline, but note the irony.

**[VEN] Vendor / blog / self-reported** — treat as marketing until replicated:
- Alpha-GPT's "top-10 of 41,000 teams" (self-reported competition placement)
- FinGPT's F1 table and $17.25 fine-tune cost
- DX Research Group production fleet numbers (2609.05663) — vendor-authored
- Alpaca / MethodAlgo / Apidog cost and latency figures — useful arithmetic, not measured strategy returns
- The 2026 practitioner summaries of Lopez-Lira (Alpha Architect, DanFin, AdvisorAnalyst) — good for the cost-sensitivity and myth-correction framing, but always cite the JFE paper for numbers

### Meta-conclusion
The honest synthesis across 2023–2026: **LLMs are very good at reading a document and producing an ordinal judgment about
short-horizon direction, and very bad at being a trader.** The measured edge (≈30–40 bps/day gross on news, ~8 pp on
earnings-direction classification, IC ≈0.14 on call tone) is real, replicated out-of-sample in at least three independent
designs, and small enough that execution costs, model seed variance, and a single poisoned headline can each erase it.
Papers reporting Sharpe >3 on multi-agent agents are, with one exception (FINSABER), reporting the interaction of a short
bull window, a handful of tickers, zero costs, and an uncontrolled training-data overlap.
