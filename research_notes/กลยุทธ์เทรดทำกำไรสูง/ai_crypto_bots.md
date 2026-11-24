# AI/automated crypto trading bots และ agent: อะไรมีหลักฐานจริง อะไรคือ backtest overfitting และ token hype (2019–2026)

ขอบเขต: bot framework โอเพนซอร์ส (Freqtrade, Hummingbot, Jesse, OctoBot), bot SaaS (3Commas, Cryptohopper, HaasOnline, Gunbot, Pionex), copy-trading ของ exchange, Hyperliquid vault, และ "AI crypto agent" (Virtuals, ai16z/Eliza, Alpha Arena) · เน้น 2019–2026
กติกา: แยก **live / on-chain** ออกจาก **backtest / paper** ทุกครั้ง; แยก **PnL ของ treasury/strategy** ออกจาก **ราคา token**; ตัวเลขที่คำนวณเองระบุ "คำนวณเอง"; ทุกตัวเลขมี URL

---

## Q1. Bot/framework ไหนมีผลลัพธ์ live ที่ตรวจสอบได้จริง — strategy, ช่วงเวลา, ค่าธรรมเนียม, drawdown และวิธี verify

### Takeaway
ในกลุ่มนี้มีเพียง **Hyperliquid vault (HLP)** ที่มี PnL on-chain ตรวจสอบได้แบบครบflows และแม้แต่มันก็ไม่ได้แปลว่ามี edge แบบทำซ้ำได้ (41% ของกำไรทั้งชีวิตมาจาก 2 event) — ส่วน Freqtrade/Hummingbot/Jesse/OctoBot เป็น **เครื่องมือ** ที่ไม่มีระบบพิสูจน์ผลลัพธ์กลาง และ bot SaaS (3Commas/Cryptohopper/HaasOnline/Gunbot/Pionex) ไม่มี track record ที่ผ่าน third-party audit เลย มีแต่ backtest/paper + รีวิวที่มี affiliate

### Cited Findings

**กลุ่ม A: ตรวจสอบได้จริง (on-chain, flow-adjusted)**

- **HLP (Hyperliquid protocol vault, 0xdfc24b07…df303)**: 2023-05 → 2026-06 (91 biweekly obs) ให้ **CAGR 58.8%, vol 24.2%, Sharpe 1.72 (rf=5%), max DD −5.8%, PF 9.96** เทียบ BTC buy-and-hold 31.3%/42.9%/−48.7%; ตัด 8 ช่วง NAV เล็กออกแล้ว CAGR ยัง 59.8% — [Validated Strategies, 21 มิ.ย. 2026](https://validatedstrategies.com/strategy/hlp-vault)
- **HLP 30 วัน (20 พ.ย. 2026)**: +1.50%, max DD 0.31%; ค่ามัธยฐานของ 62 user vault = **−3.7% ใน 30 วัน, DD 10.4%**; top decile +14.1% — [Cipher Intelligence, 20 ก.ย. 2026 (อัปเดต 20 พ.ย. 2026)](https://cipher-intelligence.io/blog/hyperliquid-vaults/)
- **HLP APR เปลี่ยนตาม regime**: 2 พ.ย. 2026 หน้า vault แสดง APR **−0.11%** และ past-month ~0%; TVL $155.0M; vault ทั้งระบบ $246.9M — [Totalis, 3 พ.ย. 2026](https://www.totalis.trade/blogs/hyperliquid/hyperliquid-vaults-hlp)
- **กำไร HLP กระจุกตัว**: ~41% ของกำไร lifetime มาจาก 2 event เท่านั้น (10 ต.ค. 2025 crash และ liquidation วาฬ 31 ม.ค. 2026) รวมกันไม่ถึง 2 สัปดาห์; Q2 2026 fee share $1.5M; performance fee 0% — [datawallet, 26 ส.ค. 2026](http://www.datawallet.com/crypto/hyperliquid-hlp-explained)
- **HLP ในเหตุ 10 ต.ค. 2025**: ประเมินว่าทำได้ **$40–41.5M ค่าธรรมเนียมในสุดสัปดาห์นั้น = ~10% ของ depositor capital ใน <48 ชม.** — [CoinGecko Learn, 2 ก.ค. 2026](https://www.coingecko.com/learn/hyperliquid-hlp-vault-analysis)
- **HLP drawdown ที่วัดผิด**: ระหว่าง 29 ต.ค.–26 พ.ย. 2025 account value ลดจาก $583.8M → $448.1M (−23%) แต่ cumulative PnL แค่ $122.4M → $117.9M; PnL drawdown ที่แย่สุดทั้งประวัติ = **$4.66M ≈ 0.8%** ของ peak — ส่วนที่เหลือคือ **การถอนเงิน ไม่ใช่การขาดทุน** — [Hyperfolio, 24 ต.ค. 2026](https://www.hyperfolio.fun/en/blog/hyperliquid-drawdown-equity-curve-guide)
- **ผู้สร้าง user vault จ่าย 10,000 USDC creation fee + ต้องถือ ≥5% ของ vault; leader รับ 10% ของกำไร; lock-up 4 วัน (HLP) / 1 วัน (user vault)** — [Cipher](https://cipher-intelligence.io/blog/hyperliquid-vaults/); [Totalis](https://www.totalis.trade/blogs/hyperliquid/hyperliquid-vaults-hlp)

**กลุ่ม B: โอเพนซอร์ส — ไม่มีผลลัพธ์กลาง แต่มีร่องรอย live ที่ยืนยันว่า backtest กับ live ต่างกันมาก**

- Freqtrade ประกาศชัดว่าเป็น "educational purposes only… authors assume no responsibility for your trading results" และแนะนำให้รัน dry-run ก่อน — [Freqtrade docs](https://www.freqtrade.io/en/stable/)
- **เคส live จริงที่รายงานเองใน issue #8518** (ม.ค.–เม.ย. 2023, ทุน ~1,000 USDT): live ขาดทุน 3 เดือนติด **−3.70%, −13.42%, −10.95%** (ม.ค. +9.60%) ขณะที่ชุดเดียวกันใน backtest ให้ Sharpe/Sortino ติดลบแต่ curve ต่างกันชัด; max DD ของ backtest 26.33% — [GitHub freqtrade#8518, 17 เม.ย. 2023](https://github.com/freqtrade/freqtrade/issues/8518)
- **สาเหตุเชิงกลไกที่ dry-run ดีกว่า live**: dry-run ถือว่า order เติมทันที, backtest เติมที่ราคา candle open โดยไม่มี slippage, live มี spread/queue/rate-limit (เช่น Binance error −4192 cooling-off, −4411 ต้องเซ็น agreement) — [Bot Academy, 12 ก.พ. 2026](https://botacademy.ddns.net/2026/02/12/difference-between-dry-and-live-run); [Freqtrade issue #3685](https://github.com/freqtrade/freqtrade/issues/3685)
- **Freqtrade ระบุ slippage ในการ backtest ถูกซ่อนไว้และจำลองได้ด้วยการเพิ่ม fee** (เช่น --fee 0.0015 แทน 0.001 = slippage 0.05%) — [freqtrade#2792](https://github.com/freqtrade/freqtrade/issues/2792)
- **การทดสอบ 41 strategy ชุมชนบน data/เงื่อนไขเดียวกัน** (Binance spot 10 เหรียญ, 1 มิ.ย. 2023–30 พ.ค. 2025, wallet $1,000, $200/trade, fee 0.1% ทุกขา): **เพียง 15/41 ทำกำไรได้**; ที่ดีสุด ReinforcedAverageStrategy +126.5% (DD 9.7%, PF 1.93, 328 trades) แต่ **buy-and-hold BTC ให้ +288.1%** และ equal-weight 10 เหรียญ +194.8% — [freqtradestrategy.com, 10 พ.ย. 2026](https://freqtradestrategy.com/guides/best-freqtrade-strategies)
- **สัญญาณ overfitting ในผลทดสอบเดียวกัน**: อันดับ 5 `CustomStoplossWithPSAR` +83.6% 但有แค่ **11 trades** ถือเฉลี่ย ~200 วัน (คือซื้อแล้วถือผ่านตลาดกระทิง) และ `UniversalMACD` exit signal "ยิงไม่ได้เลย" พึ่ง take-profit table อย่างเดียว — [freqtradestrategy.com](https://freqtradestrategy.com/guides/best-freqtrade-strategies)

**กลุ่ม C: repo ที่อ้างผลมหาศาลจนต้องสงสัย (ตัวอย่าง survivorship/overfitting ที่ควรระวัง)**

- `helloword8888889/freqtrade-strategies-showcase` อ้าง B536FT **+5,568.9% ใน 6.7 ปี, max DD −2.4%, ชนะ 82/82 เดือน, 30,385 trades, leverage 10x, 50 คู่** — แต่ **ไม่เปิด source code** และตัวเลข DD ต่ำกว่า 3% กับ leverage 10x พร้อม trade 3 หมื่นครั้งเป็นไปไม่ได้ในเชิงกลไก — [GitHub repo, 9 ต.ค. 2026](https://github.com/helloword8888889/freqtrade-strategies-showcase)
- ตรงข้าม: repo ที่เปิดผลลัพธ์ละเอียดกลับขาดทุนเกือบทั้งหมด — LightGBM/FreqAI 15m หลายช่วง 2025-10→2026-09 ให้ **−5% ถึง −45%, DD 6–46%, PF 0.61–0.86** — [MiltiadesLefk/freqtrade-bot backtest_summary](https://github.com/MiltiadesLefk/freqtrade-bot/blob/main/results/backtest_summary.md)

**กลุ่ม D: Hummingbot (market making / arbitrage)**

- Hummingbot ประกาศตรง ๆ ว่า "**Market making is not a risk-free, always profitable trading operation**" และความเสี่ยงหลักคือ inventory risk + execution risk — [Hummingbot blog](https://hummingbot.org/blog/what-is-market-making/); [inventory risk](https://hummingbot.org/blog/what-is-inventory-risk)
- XEMM (cross-exchange MM) "แทบจะ risk-free" เฉพาะ inventory เท่านั้น; ความเสี่ยงที่เหลือคือ **execution risk** เพราะราคาเคลื่อนระหว่าง quote กับ hedge — [Hummingbot XEMM docs, 11 พ.ย. 2026](https://hummingbot.org/strategies/v1-strategies/cross-exchange-market-making)
- โมเดล liquidity mining ปี 2019 อ้าง simulation ว่า MM ได้ผลตอบแทนสูงกว่า HODL/lending/staking แต่แลกกับงานและความเสี่ยงมากขึ้น — เป็น **simulation ไม่ใช่ live** — [Hummingbot, 1 พ.ย. 2019](https://hummingbot.org/blog/introducing-liquidity-mining-a-marketplace-for-market-makers)

**กลุ่ม E: Bot SaaS — ไม่มี third-party verified PnL, validation ตื้น, รีวิวมี affiliate**

- ข้อจำกัดร่วมของ Cryptohopper/3Commas/Bitsgap/Pionex: validation จบที่ **backtest + paper** ไม่มี Monte Carlo, walk-forward หรือ drift detection ในตัว; closed-source, host บน server ผู้ขาย (API key อยู่ที่นั่น) — [Noon Barbari, 23 พ.ค. 2026](https://noonbarbari.xyz/en/blog/crypto-backtesting-software-2026)
- 3Commas: backtest ได้เฉพาะ DCA/Grid, "uses past data… cannot guarantee future results"; demo account $10,000 virtual, **เทรดเฉพาะ perpetual** — [3Commas Help Center](https://help.3commas.io/en/articles/4430555-all-about-3commas-features-tools-history-and-benefits); [Ethy AI, 17 พ.ย. 2026](https://www.ethyai.app/blog/3commas-vs-cryptohopper)
- ราคา: 3Commas Free/Starter $20/Pro $50/Expert $140 ต่อเดือน; Cryptohopper Explorer $24.16/Adventurer $57.50/Hero $107.50 (annual) — [Riven Trust, ส.ค. 2026](https://riven-trust.com/compare/3commas-vs-cryptohopper/)
- **ประสบการณ์ 5 ปีบน Cryptohopper Hero (เจ้าของทุนเอง)**: strategy ทำงานถูกต้อง แต่ "net return after subscription fees, tax software, and taxes was consistently worse than holding Bitcoin" และที่พอร์ต $10k–50k ค่า Hero ($129/เดือน) **เกิน edge จริงของ strategy** — [unCoded, 1 พ.ค. 2026](https://uncoded.ch/blogs/3commas-vs-cryptohopper-vs-bitsgap-vs-wundertrading-an)
- Cryptohopper marketplace: strategy ขาย $5–20/เดือน, **ไม่มี standardized quality vetting**, performance เป็น historical ไม่ใช่ predictive — [Insigtrade, 14 ก.ย. 2026](https://insigtrade.com/blog/cryptohopper-vs-3commas-which-crypto-trading-bot-wins-2026) (หน้านี้ประกาศ affiliate ตัวเอง); [pickmytrade, 24 ส.ค. 2026](https://blog.pickmytrade.io/cryptohopper-vs-3commas-vs-diy-bots-honest-2026-guide)
- Pionex: bot อยู่ใน exchange เอง (ไม่ต้อง API key) — ข้อดีด้าน security แต่ผลลัพธ์คือ "grid profit" ที่ **"can only be positive and never decreases"** จึงไม่ใช่ตัววัดกำไร — [Pionex blog](https://www.pionex.com/blog/how-would-the-profit-on-grid-went-into-negative-what-contribute-to-that); [AlgoGrade, 27 ก.ค. 2026](https://algograde.com/strategies/pionex-neutral-grid-bot-loss)

**กลุ่ม F: Copy-trading ของ exchange — "verify" ได้แค่ตัวเลขที่แพลตฟอร์มเลือก show**

- งานวิชาการบนแพลตฟอร์ม copy-trading crypto (CHI 2024): copier **follow ranking บน leaderboard แทบทั้งหมด** และ "positions collapse shortly after they appear on the leaderboard and start being extensively copied"; leader ปิดพอร์ตที่ขาดทุนแล้วเปิดใหม่ได้ → สร้าง history สวยได้; **TraderWagon median portfolio life = 2.9 วัน**; Bybit จำกัด 1 พอร์ตต่อ leader และ **<20% ของพอร์ตยัง active** เทียบกับ >50% บน TraderWagon — [Kawai et al., ACM CHI 2024](https://dl.acm.org/doi/fullHtml/10.1145/3613904.3642715)
- ESMA ออก supervisory briefing ให้ copy trading เข้าเกณฑ์ MiFID II (ผลตอบแทน/ค่าธรรมเนียม, suitability, conflict of interest จากโครงสร้างค่าตอบแทน) — [ESMA, 30 มี.ค. 2023](https://www.esma.europa.eu/press-news/esma-news/esma-provides-guidance-supervision-copy-trading-services); FCA ถือว่า copy trading = portfolio/investment management ต้องมี authorization — [FCA](https://www.fca.org.uk/firms/copy-trading)
- การทดลองใน Management Science: การเห็นผลของคนอื่นเพิ่ม risk taking และการมีตัวเลือก copy เพิ่มขึ้นอีก → "copy trading leads to excessive risk taking" — [Apesteguia et al., Mgmt Sci, 14 ก.ค. 2020](https://pubsonline.informs.org/doi/10.1287/mnsc.2019.3508)
- survivorship เชิงตัวเลขของผู้เขียนที่ลอง copy เอง: copy 10+ strategy ที่ ROI ranking สูง **ทุกตัวขาดทุน 95–100% ภายใน 6 เดือน**; ตัวอย่าง provider บน cTrader Copy ลงทุนเอง $947 แต่ follower ลง $87,971 — [BrokerListings, 23 ต.ค. 2026](https://brokerlistings.com/research-hub/copy-trading-blow-ups)

### Inferences
- **ลำดับความน่าเชื่อถือ**: on-chain vault ที่มี flow-adjusted PnL (HLP) > live account ที่ expose read-only ต่อ third party > live ที่เจ้าของโพสต์เอง > dry-run > backtest > screenshot/affiliate review. ในกลุ่มที่สำรวจ มีแค่ HLP ที่อยู่ชั้นบนสุด และมันยังเป็น "satellite allocation" ไม่ใช่เครื่องทำกำไรระยะสั้น
- Freqtrade/Hummingbot ไม่ได้ "ล้มเหลว" — พวกมันแค่ไม่มีระบบพิสูจน์ผลลัพธ์ เพราะเป็น library; คนที่อ้างว่า framework ทำเงินได้จึงกำลังอ้างผลของ *strategy ที่เขาเขียนเอง* ซึ่งเลือกมาจาก backtest ที่ดีที่สุด (selection bias)
- ตัวเลข "+5,568%" หรือ "DD −2.4%" ที่ leverage 10x คือสัญญาณตรงของ overfitting/compounding artifact ไม่ใช่ความสามารถ; ถ้า source code ปิดและไม่มี trade log ที่ตรวจได้ ก็ควรจัดเป็นโฆษณา
- ค่า subscription ของ SaaS ($20–140/เดือน) เป็น **ค่าคงที่ต่อเดือน** ไม่ขึ้นกับขนาดทุน → ที่ทุน 147 USD มันคือ 14–95% ของทุนต่อเดือน ซึ่งทำให้ edge ใด ๆ หายก่อนเริ่ม

### Gaps
- **ไม่พบ track record live ที่ตรวจสอบได้ของ Jesse, OctoBot, HaasOnline, Gunbot** ในแหล่งอิสระ (has-verified/third-party) — ค้นแล้วเจอแต่หน้า product และรีวิว affiliate จึงไม่สรุปว่า "มี" หรือ "ไม่มี" ผลลัพธ์
- ไม่พบ leaderboard อย่างเป็นทางการของ Freqtrade/Hummingbot ที่ผูก read-only exchange account (เช่นเดียวกับ Myfxbook) — การยืนยันผลจึงต้องพึ่ง repo ส่วนตัว/ชุมชน ซึ่งคัดเลือกตัวเอง
- ตัวเลข HLP จากหลายแหล่งไม่ตรงกัน (APR 18.53% vs −0.11% vs +17.4% ในเดือนเดียวกัน) เพราะแต่ละเจ้าใช้ window/วิธี annualize ต่างกัน — ไม่มีแหล่งไหนอธิบายสูตร APR ของ Hyperliquid ได้
- ไม่พบการศึกษาที่วัด **net-of-fee ผลของ bot SaaS แบบสุ่มตัวอย่าง** (ไม่ใช่เคสเดียว) — หลักฐานส่วนใหญ่เป็น anecdote

---

## Q2. "AI crypto agent" (Virtuals, ai16z/Eliza, autonomous trading agents, LLM vault) — PnL จริง vs token hype

### Takeaway
งานวิจัย on-chain ที่กว้างที่สุด (Pantera/Stanford/IC3, ครอบ 1,900 โครงการ AI) สรุปว่า agent treasury **กำไร paper $34.3M** แต่ **holder ขาดทุนสุทธิ $191.7M จาก 925,323 wallet** และ token ร่วงเฉลี่ย **−93%** — คือ "AI agent" แทบทั้งหมดคือ **สินค้าที่มี narrative ไม่ใช่ strategy ที่มี edge**; ในกลุ่มที่เทรดจริง มีเพียง Alpha Arena ที่ยืนยันได้ว่า LLM ส่วนใหญ่ขาดทุนเมื่อเทรดเงินจริง

### Cited Findings

**โครงสร้างตลาด**
- สำรวจ 1,900 โครงการที่ติด tag AI (CoinGecko + Messari, ต.ค. 2024–พ.ย. 2025) → คัดเหลือ **1,035 โครงการที่เป็น DeFi investment agent**; สุ่มเชิง purposive 10 โครงการ; **มีเพียง 3 โครงการที่เทรดด้วย pooled fund จริง** (Axelrod, Eliza, Alpha Arena), 2 เป็น passive vault, 5 เป็น advice/simulation — [Yu, Zhao, Sui, arXiv 2605.29174, 27 พ.ค. 2026](https://arxiv.org/html/2605.29174)
- developer interview กับทีม ElizaOS และ Virtuals: "**LLMs cannot trade well**" และ "most agents implement basic API integrations rather than autonomous execution" — [arXiv 2605.29174](https://arxiv.org/html/2605.29174)
- **แม้แต่โครงการที่ observability สูง (มี wallet สาธารณะ) ผู้วิจัยก็แยกไม่ออกว่า execution เป็น autonomous หรือมนุษย์เซ็น** — on-chain บอกได้ว่า *ทำอะไร* ไม่ได้บอกว่า *ใครสั่ง* — [arXiv 2605.29174](https://arxiv.org/html/2605.29174)

**PnL ของ treasury vs ของ holder (ตัวเลขหลักของงานนี้)**
- Aggregate **treasury PnL +$34.3M** แต่ **aggregate user PnL −$191.7M** จาก **925,323 wallet** (ณ snapshot ปลาย ก.พ. 2026); ยอด paper gain ของ user เคยพุ่งถึง **>$2.4B** (ai16z เดี่ยว $2.45B) ก่อนหายทั้งหมด — [arXiv 2605.29174](https://arxiv.org/html/2605.29174)
- **top 1% ของ wallet ที่กำไร (2,590 จาก 259,016) กิน 81.4% ของกำไรทั้งหมด = $1.81B; 62.2% (575,246 wallet) ขาดทุน; median return ติดลบหรือใกล้ศูนย์ทุกแพลตฟอร์ม** — [arXiv 2605.29174 §5.4; สรุปใน note.com/x402inc, 25 ก.ย. 2026](https://note.com/x402inc/n/nfa81d65846cf?hl=en)
- **token ร่วงเฉลี่ย −93% จาก ATH (range 88–99%)** เทียบ SOL −54% ในช่วงเดียวกัน — [arXiv 2605.29174](https://arxiv.org/html/2605.29174)
- **MC/AUM**: 8 จาก 10 agent มี peak MC/AUM > 10×; **Vader AI และ Axelrod > 10,000×** เทียบ DeFi protocol ใหญ่ (Maker, Aave, Curve, Uniswap) < 1× และ digital asset treasury 1–3× NAV — [arXiv 2605.29174](https://arxiv.org/html/2605.29174)
- **peak AUM มาหลัง token ATH** หลายวันถึงหลายสัปดาห์ในเกือบทุก agent → เงินไหลเข้า treasury หลัง narrative พีคแล้ว (reflexive, ไม่ใช่ fundamental) — [arXiv 2605.29174](https://arxiv.org/html/2605.29174)
- ai16z/Eliza: peak mcap **$2,716,989,656 (9 ม.ค. 2025)** แต่ peak AUM เพียง **$22,963,939** — ratio ~118×; ถือ degenai/fxn/ai16z เป็นหลัก — [arXiv 2605.29174 Table 2](https://arxiv.org/html/2605.29174)
- มีเพียง 2 แพลตฟอร์มที่ user PnL รวมยังเป็นบวก: **Truth Terminal +$24.1M และ Zerebro +$8.4M**; ที่เหลือขาดทุนสุทธิ — [arXiv 2605.29174](https://arxiv.org/html/2605.29174)

**ai16z → ELIZAOS: token ตายแยกจาก software**
- ATH $2.47 (2 ม.ค. 2025) → ปัจจุบัน **$0.0002** (market cap ~$226k) — [CoinGecko](https://www.coingecko.com/en/coins/ai16z)
- ผู้ก่อตั้ง Shaw Walters ประกาศ **"The token is dead. Completely."** (4–5 ส.ค. 2026), foundation ปิด, ไม่มี buyback; ELIZAOS −97% จาก high, mcap ~$2.3M; มี class action กล่าวหาว่าโครงการ "misleading investors about being an autonomous, AI-run venture fund" และ dilute holder ตอน migration — [CoinDesk, 5 ส.ค. 2026](https://www.coindesk.com/markets/2026/08/05/ai-agent-token-once-worth-usd2-4-billion-ends-with-founder-calling-it-dead)
- migration พ.ย. 2025: total supply 6.6B → 11B (+66.7% คำนวณเองจากตัวเลข 6.6→11) โดย 40% ของ supply ใหม่จัดสรรให้ foundation/"Generative Treasury"; holder swap 1 AI16Z → 6 ELIZAOS (ไม่ใช่ 10) — [elizaOS "The Breakdown", อ้างใน ICHIZEN, 16 ก.ค. 2026](https://ichizenholdings.co.jp/media/column/crypto/what-is-ai16z/)

**Alpha Arena: การทดสอบ LLM ด้วยเงินจริง (หลักฐานที่ดีที่สุดว่า LLM ไม่มี edge)**
- Season 1: 6 model, **$10,000 จริง/คน**, Hyperliquid perps, 18 ต.ค.–3 พ.ย. 2025; จบที่ Qwen3 Max **+22.31% ($12,231)**, DeepSeek V3.1 +4.89%, Claude Sonnet 4.5 −42.01%, Gemini 2.5 Pro −45.55%, Grok 4 −57.92%, GPT-5 −58.74% — [TradeRank (อ่าน nof1.ai archive 6 ส.ค. 2026)](https://www.traderank.ai/alpha-arena-leaderboard); [SCMP, 4 พ.ย. 2025](https://www.scmp.com/tech/tech-trends/article/3331425/alibabas-ai-model-outperforms-us-rivals-crypto-trading-showdown)
- **recompute จาก Hyperliquid public data ทั้ง 38 account: 31/38 ขาดทุน; จ่าย fee รวม $43k บน stake $380k** (≈11.3% ของทุนเป็นค่าธรรมเนียม — คำนวณเอง); Season 1 winner +20.3% (ไม่ใช่ +22.3%) — [TradingAgentStack, 29 ต.ค. 2026](https://tradingagentstack.com/alpha-arena-results)
- Season 1.5 (US-stock perps, 19 พ.ย.–3 ธ.ค. 2025): **6/32 account ทำกำไร**; แย่สุด −96.15%, ดีสุด +34.59%; **Sharpe ของแถวบนสุด = 0.019, 0.009, 0.000** — คือ noise ล้วน — [ai-crypto.exchange, 21 ต.ค. 2026](https://ai-crypto.exchange/ai-crypto-trading-agents/alpha-arena-results); [tradepartner g6 notes](https://github.com/josejuarez96/tradepartner/blob/main/docs/research/2026-09-26-g6-alpha-arena.md)
- **ผลลัพธ์พลิกกลางเกม**: วันที่ 27 ต.ค. 2025 DeepSeek ขึ้นไป $22,900 (+126%) และ Qwen $20,850 (+108%) แล้วจบที่ $10,489 และ $12,231 → ranking ณ สัปดาห์ไหนก็ได้คนละเรื่อง — [upscale.trade, 5 ต.ค. 2026](https://upscale.trade/blog/ai-trading-alpha-arena)
- nof1 เองเรียก LLM ว่า "**shockingly bad**" ที่ตลาด และผล 2–3 สัปดาห์พิสูจน์ skill แทบไม่ได้ — [ai-crypto.exchange](https://ai-crypto.exchange/ai-crypto-trading-agents/alpha-arena-results)

**วรรณกรรม LLM trading (บริบท)**
- Chen et al.: LLM agent ส่วนใหญ่ **ไม่ชนะ buy-and-hold** บนหุ้น DJIA ใน 4 เดือน; Fan et al.: general intelligence **ไม่แปลงเป็น trading capability** ทั้งหุ้น US, A-share และ crypto; Qian et al.: system design (multi-agent, tool use, memory) สำคัญกว่า choice of LLM — สรุปใน [arXiv 2605.29174 §2](https://arxiv.org/html/2605.29174)

### Inferences
- **"Agent ทำกำไร" กับ "holder ทำกำไร" เป็นคนละตัวแปรโดยโครงสร้าง**: treasury ถือ basket ของ token เล็กที่มันเองออก/ถือตั้งแต่ถูก ส่วน holder ถือ native token ที่ priced ด้วย narrative → ตัวเลข +$34.3M vs −$191.7M คือคำตอบของคำถามนี้ในบรรทัดเดียว
- MC/AUM >10,000× ไม่ใช่ "premium for AI" แต่คือราคาของ **option บน narrative**; เมื่อ narrative หมด (ม.ค. 2025) อะไรที่ priced ด้วยมันก็ลง 88–99% พร้อมกัน
- Alpha Arena เป็นหลักฐานเชิงลบที่แข็งแรงกว่าเชิงบวก: มี 2/6 ชนะใน S1 แต่พอเปลี่ยน market/rule set ผู้ชนะก็เปลี่ยน และ Sharpe ของผู้ชนะ ≈ 0 → **ผลลัพธ์ 2 สัปดาห์ไม่สามารถแยก skill จาก luck ได้**
- ai16z เป็นกรณีศึกษาว่า software (ElizaOS framework) กับ token คนละชีวิต: framework ยัง develop ต่อได้แม้ token −99.9% → การประเมิน "AI agent project" จากราคา token จึงผิดระบบ

### Gaps
- ไม่มีตัวเลข **net trading PnL ของ agent treasury แยกจากกำไรจากการถือ token ของตัวเอง** (mark-to-market ของ token ที่ agent ถืออยู่คือราคาที่มันช่วยสร้าง) — งาน arXiv เองยอมรับว่าเป็น daily snapshots ไม่ใช่ trade events
- ไม่พบ PnL ที่ตรวจสอบได้ของ **Virtuals agent รายตัว** (งาน arXiv ตัด Base/Virtuals ออกเพราะ VIRTUAL เป็น routing currency) — จึงตอบไม่ได้ว่า agent บน Virtuals ตัวไหนทำเงินจริง
- ไม่พบหลักฐานว่า agent ใดในกลุ่มนี้เทรด **ด้วยกลยุทธ์ที่ระบุได้และทำซ้ำได้** เป็นเวลานานกว่า 12 เดือน
- ไม่มีข้อมูลค่าใช้จ่ายจริง (inference cost ต่อวัน) ของ agent เหล่านี้ → คำนวณ net edge ไม่ได้

---

## Q3. กลยุทธ์ไหน dominate และอะไรอยู่รอดหลังหักค่าธรรมเนียม/เปลี่ยน regime

### Takeaway
กลยุทธ์ที่ "ขายดี" (grid, DCA, martingale) คือกลุ่มที่ **คณิตศาสตร์ของค่าธรรมเนียมฆ่าได้ง่ายที่สุด** และ display ของมันถูกออกแบบให้ดูดีขณะขาดทุน; กลยุทธ์ที่อยู่รอดจริงคือ (ก) market making/backstop ที่มีต้นทุนโครงสร้างต่ำและมีผู้เล่นรายใหญ่ถือ inventory (HLP) และ (ข) trend/breakout ที่ยอมขาดทุนบ่อยแลกกับ drawdown ที่ต่ำกว่า — แต่ **ไม่มีตัวไหนชนะ buy-and-hold ในตลาดขาขึ้น** ตามการทดสอบ 41 strategy

### Cited Findings

**Grid — fee กินเกือบครึ่งของ spread**
- ตัวอย่างจริง: grid 90 ช่อง ช่วง 71,382–87,244.6 → ระยะ ~176 USDT/ช่อง ≈ **0.22% ต่อ step**; Pionex คิด **0.05% ต่อ fill** → round trip 0.10% = **~45% ของ gross spread ไปที่ fee** (คำนวณเองจากตัวเลขในบทความ) — [AlgoGrade, 27 ก.ค. 2026](https://algograde.com/strategies/pionex-neutral-grid-bot-loss)
- บัญชีเดียวกัน 72 วัน: **grid profit +8.39% แต่ trend PnL −70.28% → account −61.88%** (75.10 → 28.62 USDT); dashboard โชว์ "grid annualized 42.53%" คู่กับ "total annualized −99.25%" พร้อมกัน — [AlgoGrade](https://algograde.com/strategies/pionex-neutral-grid-bot-loss)
- Pionex เองยอมรับเชิงเอกสารว่า grid profit "**can only be positive and never decreases**" และ total profit ติดลบได้แม้ grid profit บวก — [Pionex blog](https://www.pionex.com/blog/how-would-the-profit-on-grid-went-into-negative-what-contribute-to-that)
- เมื่อราคาหลุดกรอบ: spot grid "hold more base asset" ขาดทุน unrealized ต่อ; futures grid ยังมี liquidation risk ต่อเนื่อง — [Pionex grid risks, 9 มิ.ย. 2026](https://www.pionex.com/blog/grid-trading-risks)

**DCA / martingale — ความเสี่ยงอยู่ที่ safety orders และ liquidation**
- 3Commas DCA รองรับ **safety orders สูงสุด 20 ไม้** พร้อม deviation/volume scaling; ใน "live test 30 วัน" (ส.ค. 2026) ปิด 14/16 deal กำไร — เป็น **ตัวเลขจากรีวิวที่มี affiliate** และไม่มี drawdown/ขนาดทุน — [Insigtrade, 14 ก.ย. 2026](https://insigtrade.com/blog/cryptohopper-vs-3commas-which-crypto-trading-bot-wins-2026)
- futures grid "neutral" ไม่ได้ neutral: เริ่ม flat แต่พอราคาลงก็ะสม long; ที่ 10x การเคลื่อน 19% = ~190% ของ margin — [AlgoGrade](https://algograde.com/strategies/pionex-neutral-grid-bot-loss)
- เคสผู้ใช้ Pionex (มิ.ย. 2026): SPCX/USDT short futures grid 25x, entry 172.93, mark 173.89 (**+0.55% against**) แต่ถูกปิด **−1,513 USDT / −100%** ระหว่าง maintenance/price adjustment โดย **0 grid transaction** — ผู้ใช้โต้แย้งว่าเป็นการ liquidation ที่อธิบายไม่ได้; Pionex ตอบว่าทำงานตาม design — [r/Pionex, 10 มิ.ย. 2026](https://www.reddit.com/r/Pionex/comments/1u285vk) (เป็นข้อกล่าวหาของผู้ใช้ ไม่ใช่ข้อเท็จจริงที่ตรวจสอบแล้ว)

**Trend / breakout — รอดแต่ไม่ชนะ buy-and-hold**
- 41 strategy บนข้อมูลเดียวกัน: ผู้ชนะคือ 4h trend/averaging (ReinforcedAverage +126.5%, DD 9.7%; MultiMa +97.8%, DD 11.1%, PF 2.43) แต่ BTC +288.1% — [freqtradestrategy.com](https://freqtradestrategy.com/guides/best-freqtrade-strategies)
- ranking ตาม return/DD (risk-adjusted) ให้ภาพต่างจาก return ดิบ: ReinforcedAverage 13.0, UniversalMACD 10.3, AverageStrategy 9.4 — [freqtradestrategy.com](https://freqtradestrategy.com/guides/best-freqtrade-strategies)

**Market making / backstop (HLP) — โครงสร้างได้เปรียบจริงแต่กระจุกตัว**
- HLP ทำ 3 อย่างพร้อมกัน: quote spread, **backstop liquidation**, และปล่อย USDC ให้ยืม; ไม่มี performance fee — [dificalc, 18 ก.ย. 2026](https://dificalc.com/blog/hyperliquid-hlp-vault)
- ผลตอบแทนผันผวนรายเดือนสุดขั้ว: ม.ค. 2026 **+6.40%**, ก.พ. 2026 **+0.07%**; 1 ก.พ. 2026 วันเดียว **+$15M ≈ +5.8%** จาก cascade $700M — [dificalc](https://dificalc.com/blog/hyperliquid-hlp-vault)
- ความเสี่ยงเชิงโครงสร้าง: HLP เป็น **เป้าที่คาดเดาได้** ของการโจมตี (JELLYJELLY มี.ค. 2025, POPCAT พ.ย. 2025, Fartcoin เม.ย. 2026) — [CoinGecko, 2 ก.ค. 2026](https://www.coingecko.com/learn/hyperliquid-hlp-vault-analysis)
- มี.ค. 2025 HLP ขาดทุน ~**$4M ใน 24 ชม.** — [Totalis, 3 พ.ย. 2026](https://www.totalis.trade/blogs/hyperliquid/hyperliquid-vaults-hlp)

**Funding / basis (อ้างจากบันทึก sibling ที่ตรวจแล้ว)**
- median annualized funding ของ 30 Binance USD-M perps (112,853 obs, 2023-01→2026-05): **+7.3% (2023) → +13.4% (2024) → +2.8% (2025) → +0.6% (2026)**; cash-and-carry net **+5.6%/ปี** ทั้ง sample และติดลบใน 2026 — [Bryan Vine, 16 มิ.ย. 2026](https://bryanvine.github.io/alpha-research/paper2.html) (รายละเอียดเต็มอยู่ใน `crypto_futures.md` ของโปรเจกต์นี้)
- funding เฉลี่ย top-10 crypto perps ปี 2026 ≈ **3%/ปี** และ basis เหลือ 3–5%/ปี — [Talos, ต.ค. 2026](https://www.talos.com/insights/following-the-funding-the-shift-towards-the-equity-basis-trade)

**Arbitrage / sniping**
- ไม่พบตัวเลข net-of-fee ที่ตรวจสอบได้ของ retail triangular arb หรือ DEX sniping bot ในแหล่งอิสระ — เจอแต่คำอธิบายกลไก (ดู Gaps)
- Hummingbot ระบุชัดว่า arbitrage/XEMM "risk-free" เฉพาะ inventory; ที่เหลือคือ execution risk และต้อง **rebalance ระหว่าง exchange** ซึ่งมีค่าโอน — [Hummingbot XEMM](https://hummingbot.org/strategies/v1-strategies/cross-exchange-market-making)

### Inferences
- **ค่าธรรมเนียมเป็นฟังก์ชันของความถี่ ไม่ใช่ขนาดทุน** → กลยุทธ์ที่ "ทำเงินทีละนิดแต่ทำบ่อย" (grid, scalping, MM บน spread แคบ) จะมี break-even ที่สูงขึ้นเรื่อย ๆ เมื่อ volatility ต่ำลง; นี่คือเหตุที่ grid ให้ผลดีใน sideways และหายทันทีเมื่อ trend มา
- **martingale/DCA ไม่ใช่กลยุทธ์ but การจัดการ position**: มันเปลี่ยน distribution ของผลลัพธ์ให้ "ชนะบ่อย ขาดทุนครั้งเดียวใหญ่" → win rate 80–90% ที่รายงานจึงไม่บอกอะไรเกี่ยวกับ expectancy; ถ้าดูเฉพาะ deal ที่ปิด (ไม่รวม deal ที่ค้าง) จะได้ survivorship ภายในพอร์ตตัวเอง
- HLP ชนะเพราะ **เป็น counterparty ของ forced flow** (liquidation) ไม่ใช่เพราะ predictive skill — edge ชนิดนี้วัดด้วย Sharpe รายเดือนได้ดี แต่ **ไม่ scale**: เมื่อ TVL โต กำไรเดียวกันถูกหารด้วย capital มากขึ้น (peak TVL $603.9M ก.ย. 2025 → ~$155M พ.ย. 2026) — [datawallet](http://www.datawallet.com/crypto/hyperliquid-hlp-explained)
- กลยุทธ์ที่ "อยู่รอด regime change" ในข้อมูลที่มีคือ trend-following ที่มี stop และ market making ที่มี inventory cap — ไม่ใช่ grid/martingale ที่ตั้ง range แล้วปล่อย

### Gaps
- ไม่มีตัวเลข **net-of-fee ของ DCA/martingale แบบหลายรอบ (multi-cycle)** จากแหล่งอิสระ (ที่มีทั้ง fee, funding, และ deal ที่ค้าง) — ตัวเลข 14/16 มาจากรีวิว affiliate
- ไม่พบตารางเทียบค่าธรรมเนียม effective ของ grid bot กับผลตอบแทนจริงข้ามหลาย regime (bull/bear/sideways) จากแหล่งที่ไม่ขายสินค้า
- sniping/MEV: ไม่พบสถิติ success rate หรือ PnL distribution ของ bot ประเภทนี้จากแหล่งที่ตรวจสอบได้ — ส่วนใหญ่เป็น Telegram ขาย bot ซึ่งมี incentive ให้โกหก
- ไม่มีข้อมูลว่า HLP จะให้ผลอย่างไรถ้า TVL กลับไป $600M+ (ตัวเลข 58.8% CAGR มาจากช่วงที่ NAV โตจากเล็กไปใหญ่)

---

## Q4. อัตราความล้มเหลวและ blow-up ที่ยืนยันได้ (grid/martingale ใน trend, exchange outage, API key theft, delisting)

### Takeaway
ความสูญเสียใหญ่สุดไม่ได้มาจาก "strategy แพ้" แต่มาจาก **leverage + liquidity + โครงสร้างตลาด**: 10 ต.ค. 2025 มี **$19.13B liquidated ใน 24 ชม. จาก 1.62M trader** และ API key ที่ถูกขโมยจาก 3Commas ทำให้ผู้ใช้เสีย **$14.8M–$22M**; ส่วน delisting ทำให้ bot ถูกบังคับปิด position โดยไม่มีการเตือนล่วงหน้าที่ใช้งานได้

### Cited Findings

**10 ตุลาคม 2025 — largest liquidation in history**
- **$19.13B liquidated ใน 24 ชม., 1,618,240 trader**, ~$16–16.8B เป็น long (≈85–88%); BTC ลงไป $104,000–106,560, alt หลายตัว −75% ในไม่กี่นาที — [CoinGlass via CoinDesk, 10–11 ต.ค. 2025](https://www.coindesk.com/markets/2025/10/10/usd16b-in-longs-liquidated-as-wall-street-sell-off-extends-btc-eth-broader-crypto-market-meltdown); [CoinDesk, 15 ต.ค. 2025](https://www.coindesk.com/coindesk-indices/2025/10/15/crypto-s-black-friday)
- **Open interest ลด 43%: $217B (10 ต.ค.) → $123B (11 ต.ค.)**; Hyperliquid OI −57% ($14B → $6B) — [CoinDesk Research, 17 ต.ค. 2025](https://www.coindesk.com/research/market-spotlight-the-19-billion-liquidation-that-shook-crypto)
- Hyperliquid: **6,300 wallet แดง, 1,000+ ถูก liquidate ทั้งหมด, 205 ขาดทุน >$1M**, capital หาย $1.23B บนแพลตฟอร์มเดียว; top-100 trader กำไร $1.69B (short) vs top-100 ขาดทุน $743.5M — [CoinDesk, 11 ต.ค. 2025](https://www.coindesk.com/markets/2025/10/11/largest-ever-crypto-liquidation-event-wipes-out-6-300-wallets-on-hyperliquid)
- **order book depth หาย >80% ในไม่กี่นาที**; ATOM บน Binance แสดง bid ใกล้ $0.001 — [CoinShares, 20 ต.ค. 2025](https://coinshares.com/us/insights/knowledge/billions-in-liquidations-what-happened)
- USDe depeg ถึง **$0.65 บน Binance** เพราะ pricing ใช้ internal spot market ไม่ใช่ external oracle → จุดชนวน liquidation ระลอกสอง — [CoinShares](https://coinshares.com/us/insights/knowledge/billions-in-liquidations-what-happened)
- ประเมินว่ายอดจริงอาจ >$50B (CoinShares) หรือ "$20B+" (Blockworks) — ตัวเลขทางการต่ำเกินจริงเพราะ Binance รายงานได้แค่ 1 liquidation order/วินาที — [Cointelegraph, 14 ต.ค. 2025](https://cointelegraph.com/news/19b-crypto-market-crash-controlled-deleveraging-cascade)

**API key theft — 3Commas (กรณีศึกษาที่ตรงที่สุดของ "bot platform ถือ key")**
- 19–20 ต.ค. 2022: การโจมตี phishing ปลอมหน้าเว็บ 3Commas → **~20,000 trades** ถูกสั่งผ่าน API, เทขายเหรียญแล้วซื้อ DMG (8,500 trades), MTA (1,000), MATH (9,000); 3Commas อ้างผู้ใช้ 10 รายยืนยันความเสียหายรวม ~**$6M** และ "<0.025% ของ 100,000 active traders" — [3Commas post-mortem](https://3commas.io/blog/october-19-phishing-attack-post-mortem)
- 28 ธ.ค. 2022: leaker เผย **~100,000 API key** (10,000 ชุดแรกก่อน); CEO ยืนยันว่า "ข้อมูลในไฟล์เป็นความจริง" และขอให้ Binance/KuCoin/Coinbase revoke key ทั้งหมด — [CoinDesk, 28 ธ.ค. 2022](https://www.coindesk.com/tech/2022/12/28/anonymous-twitter-user-leaks-alleged-3commas-api-database)
- ZachXBT ยืนยัน **44 เหยื่อ รวม $14.8M** (เฉพาะที่พิสูจน์ identity ได้); ผู้ใช้กลุ่มหนึ่งอ้างว่ายอดจริง ~**$22M** — [Blockworks, 29 ธ.ค. 2022](https://blockworks.com/news/crypto-trading-bot-platform-3commas-rocked-by-critical-api-leak)
- 3Commas เคยปฏิเสธว่าไม่ใช่ความผิดตัวเอง (พ.ย. 2022) ก่อนยอมรับว่า API data รั่วจากฐานข้อมูลตัวเอง (29 ธ.ค. 2022) — [3Commas legal statement, 22 พ.ย. 2022](https://3commas.io/blog/3commas-legal-statement-in-regard-of-violated-api-keys); [3Commas notice, 29 ธ.ค. 2022](https://3commas.io/blog/notice-on-api-data-disclosure-incident)
- บทเรียนที่ยังใช้ได้ปี 2026: ใช้ key แบบ **trade-only, ปิด withdrawal, ผูก IP whitelist** — [Cryptohopper comparison](https://www.cryptohopper.com/blog/cryptohopper-vs-3commas-an-honest-comparison-of-trading-bots-13307)

**Delisting — bot ถูกบังคับปิดและ position ถูก force-sell**
- Binance delist 14 token พร้อมกัน 16 เม.ย. 2025 (BADGER, BAL, BETA, CREAM, CTXC, ELF, FIRO, HARD, NULS, PROS, SNT, TROY, UFT, VIDT) หลัง "Vote to Delist" แรก — [Binance announcement, 8 เม.ย. 2025](https://www.binance.com/en/support/announcement/detail/fac9c3e401da4cc8b604566fd261d70c)
- ประกาศ delisting ระบุชัดว่า **"Binance will terminate Trading Bots services… Users are strongly advised to update or cancel their Trading Bots prior to the cessation"** และ Spot Copy Trading จะ **force-sell at market price** — [Binance, 3 ก.ย. 2025 (BAKE/HIFI/SLF)](https://www.binance.com/en/support/announcement/detail/b601f1d986ad403b8c667dd0ca17e2e7)
- รอบอื่น: 2 พ.ค. 2025 (ALPACA/PDA/VIB/WING), 4 ก.ค. 2025 (ALPHA/BSW/KMD/LEVER/LTO), 12 พ.ย. 2025 (FLM/KDA/PERP) — อย่างน้อย **26 token ในปี 2025** จาก 5 ประกาศที่พบ (นับเอง; ไม่ใช่ตัวเลขทั้งปี เพราะ Binance delist หลายรอบกว่าในตัวอย่างนี้) — [Binance 12 พ.ย. 2025](https://www.binance.com/en/support/announcement/detail/a6c810fc36424548917e146dbe21469a)

**อัตราความล้มเหลวของ "AI/bot" ในตัวอย่างที่มีการวัด**
- Alpha Arena: **31/38 account ขาดทุน** (81.6%) — [TradingAgentStack, 29 ต.ค. 2026](https://tradingagentstack.com/alpha-arena-results)
- Freqtrade 41 strategy บนข้อมูลเดียวกัน: **26/41 ไม่ทำกำไร** (63.4%) — [freqtradestrategy.com](https://freqtradestrategy.com/guides/best-freqtrade-strategies)
- AI agent token holders: **62.2% ของ 925,323 wallet ขาดทุน**, median return ติดลบ — [arXiv 2605.29174](https://arxiv.org/html/2605.29174)
- Copy trading: ผู้เขียนที่ทดลอง 10+ strategy ขาดทุน **95–100% ภายใน 6 เดือนทุกตัว** — [BrokerListings, 23 ต.ค. 2026](https://brokerlistings.com/research-hub/copy-trading-blow-ups)

### Inferences
- **Blow-up ของ bot ไม่ได้เกิดตอน market ลง แต่เกิดตอน market ลงเร็ว + liquidity หาย + leverage สูงพร้อมกัน** — 10 ต.ค. 2025 แสดงว่าการ stop-loss ปกติใช้ไม่ได้เมื่อ depth หาย 80% และ mark price วิ่งผ่าน liquidation โดยไม่มี fill
- **API key คือ attack surface ที่ใหญ่กว่า strategy risk สำหรับ bot SaaS**: 3Commas ไม่ได้เทรดผิด — มันเทรด *ถูก* ตามคำสั่งของ attacker; ผู้ใช้ที่ปิด withdrawal permission ยังเสียเงินเพราะ attacker เทรดขาดทุนให้ (ขายของถูกให้ตัวเอง)
- **Delisting คือความเสี่ยงที่ bot grid/DCA มองไม่เห็นเลย**: range ที่ตั้งไว้บนเหรียญที่จะถูก delist จะกลายเป็น position ที่ถูก force-sell ที่ราคาตลาด ไม่ว่า grid จะ "กำไร" แค่ไหน
- ตัวเลข "อัตราล้มเหลว" ที่ต่างกัน (63%, 81%, 95%) สะท้อน **นิยามที่ต่างกัน** (strategy ไม่กำไร / account ขาดทุน / ผู้ใช้หมดตัว) ไม่ใช่ความขัดแย้ง — แต่ทุกนิยามชี้ทางเดียวกัน: ฐานความน่าจะเป็นไม่เอื้อผู้ใช้รายย่อย

### Gaps
- ไม่มีตัวเลข **จำนวน bot account ที่ล้มเหลวทั้งหมด** จาก exchange (Binance/Bybit ไม่เปิด) → คำนวณ base rate จริงไม่ได้
- ไม่พบ postmortem อย่างเป็นทางการของ **Pionex/Gunbot/HaasOnline** กรณี outage หรือ liquidation ผิดปกติ (เคส SPCX เป็นเพียงโพสต์ผู้ใช้)
- ไม่มีข้อมูลผลกระทบของ **exchange outage** (เช่น Binance maintenance) ต่อ bot ที่ค้าง position เป็นตัวเลข — มีแต่คำเตือนเชิงคุณภาพ
- จำนวน delisting ทั้งปี 2025 ของ Binance/Bybit/OKX ไม่มีแหล่งสรุปที่ตรวจสอบได้ในเวลาที่ค้น — ตัวเลข 26 เป็นการนับจากประกาศที่พบเท่านั้น

---

## Q5. บัญชี 147 USD ทำอะไรได้จริง และอะไรเป็นไปไม่ได้ (exchange minimum, fee, API limit, cloud cost)

### Takeaway
ที่ 147 USD สิ่งที่ "เป็นไปได้" มีแค่ **spot/perp ไม่กี่ position ความถี่ต่ำ บนเหรียญที่ min notional 5 USDT** — เพราะค่า VPS อย่างเดียว (~$6/เดือน) กิน **~4.7% ของทุนต่อเดือน (≈56%/ปี)** และค่า subscription bot ($20–140/เดือน) กิน 14–95% ของทุนต่อเดือน; grid หลายชั้น, cross-exchange arb, market making และ funding carry ต้องมีทุนสองขา/หลายพันดอลลาร์จึงจะคุ้มต้นทุนขั้นต่ำ

### Cited Findings

**Minimum order size (ตรวจจริง 7 พ.ย. 2026)**
- Binance USDⓈ-M: **BTCUSDT 50 USDT, ETHUSDT/LINKUSDT/LTCUSDT 20 USDT, อื่น ๆ เช่น SOL/BNB/XRP/ADA = 5 USDT**; ขั้นต่ำเดิม $1 (ม.ค. 2021) → เปลี่ยนได้โดยไม่ต้องแจ้ง — [HafizeBot, 14 พ.ย. 2026](https://www.hafizebot.com/post/binance-error-4164-order-notional-too-small)
- **margin ขั้นต่ำ = min notional ÷ leverage**: เหรียญ 20 USDT ต้องใช้ 20/10/4/2 USDT margin ที่ 1x/2x/5x/10x; เหรียญ 50 USDT ต้อง 50/25/10/5 — [HafizeBot](https://www.hafizebot.com/post/binance-error-4164-order-notional-too-small)
- Binance Spot min notional = **5 USDT** (ค่า default; ต้องอ่าน `exchangeInfo` จริงเพราะแต่ละคู่ไม่เหมือนกัน) — [Binance Academy](https://www.binance.com/en/academy/articles/binance-spot-trading-rules-a-comprehensive-guide); [fincodelabs, 24 ต.ค. 2026](https://fincodelabs.com/en/blog/binance-api-python-trading-bot)

**ค่าธรรมเนียม**
- Spot: **0.1% maker/taker** (0.075% ถ้าจ่ายด้วย BNB) → round trip 0.2%
- USDⓈ-M futures: **0.02% maker / 0.05% taker** (0.018%/0.045% ด้วย BNB); คิดบน **notional ไม่ใช่ margin** → $10,000 notional taker ไป-กลับ = $10 — [Binance fee page](https://www.binance.com/en/fee/futureFee); [FeeFlux, 11 พ.ย. 2026](https://feeflux.com/en/articles/binance-fees-guide/)
- Hyperliquid: **0.015% maker / 0.045% taker** — [datawallet, 4 ต.ค. 2026](https://www.datawallet.com/crypto/binance-futures-review)
- Pionex: **0.05% ต่อ fill** สำหรับ grid → 0.10% ต่อรอบ — [AlgoGrade](https://algograde.com/strategies/pionex-neutral-grid-bot-loss)
- ค่าธรรมเนียมเป็น % ของ notional ไม่ขึ้นกับขนาดทุน → ที่ทุน 147 USD อัตราเดียวกันกับทุน $1M แต่ **ผลกระทบต่อการอยู่รอดของบัญชีต่างกันมาก** (147 × 0.2% = $0.294/รอบ; 10 รอบ/วัน = $2.94/วัน = 2% ของทุน/วัน — คำนวณเอง)

**API limits (ตรวจ 4 พ.ย. 2026)**
- Spot: **6,000 request weight/นาที ต่อ IP**, **100 orders/10 วินาที**, 200,000 orders/วัน, RAW_REQUESTS 300,000/5 นาที
- USDⓈ-M futures: **2,400 weight/นาที**, **300 orders/10 วินาที**, 1,200 orders/นาที
- ban 429 → 418 มีโทษ 2 นาที ถึง 3 วัน; weight นับ per IP ไม่ใช่ per key → bot หลายตัวบน VPS เดียวแชร์โควตา — [fincodelabs, 5 พ.ย. 2026](https://fincodelabs.com/en/blog/binance-api-rate-limit); [Binance Developer Docs](https://developers.binance.com/en/docs/products/common/sapi/general-info)
- ข้อจำกัดที่กระทบ grid: Pionex futures grid **ต้องลงทุน ≥100U สำหรับ 20+ orders, ≥200U สำหรับ 30+, ≥300U สำหรับ 50+**; BTC/ETH/ETHBTC จำกัด 20 orders, เหรียญเล็ก 5 orders — [Pionex blog](https://www.pionex.com/blog/pionex_long_futures_grid)

**Cloud cost**
- Hetzner CX23 (2 vCPU/4 GB/40 GB, รวม IPv4): **€5.99/เดือน** (€5.49 + €0.50) ณ 18 พ.ย. 2026; ขึ้นจาก €3.99 หลังปรับราคา 1 เม.ย. + 15 มิ.ย. 2026 — [VPNSmith, 18 พ.ย. 2026](https://www.vpnsmith.com/en/blog/vps-prices-after-2026-price-increases); [cloudhim, 4 พ.ย. 2026](https://www.cloudhim.com/pricing-costs/hetzner-cx22-pricing-2026)
- ถูกกว่า: OVH VPS-1 (2/4 GB) from **€3.81/เดือน** — [VPNSmith](https://www.vpnsmith.com/en/blog/vps-prices-after-2026-price-increases)
- Hetzner CX/CAX **sold out / restricted** สำหรับลูกค้าใหม่ตั้งแต่ 26 มิ.ย. 2026 — [cloudhim](https://www.cloudhim.com/pricing-costs/hetzner-cx22-pricing-2026)

**ค่า subscription bot (เทียบทุน 147 USD)**
- 3Commas Starter **$20/เดือน** = **13.6% ของทุน/เดือน** (คำนวณเอง)
- Cryptohopper Explorer **$24.16/เดือน** = **16.4%/เดือน** (คำนวณเอง)
- 3Commas Expert $140/เดือน = **95%/เดือน** → เป็นไปไม่ได้ในทางปฏิบัติ — [Riven Trust](https://riven-trust.com/compare/3commas-vs-cryptohopper/)

**ข้อจำกัดเชิงโครงสร้างของ carry/arb**
- carry แบบ delta-neutral ต้องวาง margin สองขา (spot + perp) → capital efficiency ~50% และต้อง split 147 เป็น ~74+74 ซึ่งต่ำกว่า min notional ที่ใช้งานได้จริงหลายที่ — (อนุมานจากกลไก; ตัวเลข funding อยู่ใน Q3)
- cross-exchange MM ต้องถือ inventory ทั้งสอง exchange และ rebalance เป็นรอบ ๆ ซึ่งมีค่าโอน + ต้องมี reserve — [Hummingbot XEMM](https://hummingbot.org/strategies/v1-strategies/cross-exchange-market-making)

### Inferences
- **ต้นทุนคงที่คือศัตรูตัวจริงที่ทุน 147 USD**: VPS $6/เดือน + ไม่มี subscription = 4.1%/เดือน; ถ้าใส่ 3Commas Starter ด้วย = 17.7%/เดือน → ต้องทำ ~18% ต่อเดือนเพียงเพื่อเสมอตัว ซึ่งมากกว่าผลตอบแทนของ strategy ที่ดีที่สุดใน 41 ตัว (126.5% ใน 2 ปี ≈ 4.2%/เดือน) — คำนวณเอง
- **สิ่งที่ทำได้จริง**: 1–3 position พร้อมกัน บนเหรียญที่ min 5 USDT, timeframe ≥1h, ใช้ limit order (maker) เพื่อลด fee, หลีกเลี่ยงการถือข้าม funding ถ้าไม่จำเป็น, รันบนเครื่องตัวเองหรือ VPS ราคาถูกที่สุด
- **สิ่งที่ทำไม่ได้**: grid 20+ ชั้น (ต้อง 100U+ ต่อ bot และเหลือ margin น้อยมาก), market making สองฝั่ง (ต้อง inventory + reserve), funding carry (ต้องสองขา), copy trading บน leaderboard (ค่าธรรมเนียม + slippage หักผลตอบแทน), และ bot SaaS ระดับ $50–140/เดือน
- leverage ไม่ได้แก้ปัญหา min notional อย่างที่คิด: 5 USDT notional ที่ 10x ใช้ margin 0.5 USDT ก็จริง แต่ liquidation distance แคบลง ~10 เท่า → ความน่าจะเป็นที่จะถูกบังคับปิดก่อน strategy ทำงานจบสูงขึ้นมาก

### Gaps
- ไม่มีข้อมูล **ค่าธรรมเนียม withdrawal/network ขั้นต่ำ** ที่กระทบการ rebalance ทุนเล็ก (ขึ้นกับ chain และเวลา)
- ไม่มีตัวเลข **slippage จริงต่อ order size 5–50 USD** บนคู่เล็ก ๆ (งานส่วนใหญ่ศึกษา order $10,000)
- ไม่พบการเปรียบเทียบ **net return ของ strategy เดียวกันที่ทุน 147 vs 10,000 USD** — จึงประมาณได้แค่ว่าผลกระทบหลักมาจากค่าคงที่ ไม่ใช่ market impact
- ไม่มีข้อมูลค่า electricity/เครื่องตัวเอง (self-host) ที่วัดได้ → ตัวเลข 4.1%/เดือนเป็นขอบล่างของต้นทุนโครงสร้าง

---

## Q6. หลักฐานแบบไหนที่จะพิสูจน์ว่า AI agent มี edge จริง ไม่ใช่โชค

### Takeaway
เกณฑ์ที่แยกได้จริงคือ **"record ที่ครบ ไม่ใช่ record ที่เลือก"**: ต้องมี read-only track record ≥12–24 เดือนที่รวม **ทุกบัญชี** (รวมที่ปิดไป), PnL ที่ปรับ flows แล้ว, หัก fee+funding จริง, และผ่าน out-of-sample/walk-forward พร้อม deflated Sharpe/PBO — เพราะงานวิจัยแสดงว่าการคัดเลือก (selection) อย่างเดียวสร้าง +700 bp, survivorship สร้าง +442 bp, และแค่ 1,000 คนไม่มี skill ก็มี ~125 คนที่ชนะตลาด 3 ปีติด

### Cited Findings

**ขนาดของ bias ที่ต้องหักออกก่อน**
- **Backfill**: กองทุนที่รายงานผลย้อนหลังให้ผลสูงกว่า contemporaneous report เฉลี่ย **>700 bp** (วิเคราะห์ TASS database, Saha 2006) — [Centaur, 28 ต.ค. 2026](https://www.centaur.io/blog/how-to-evaluate-a-traders-public-track-record)
- **Survivorship**: ช่องว่าง **442 bp** — กองทุนที่รอดให้ 13.74% เทียบ 9.32% ของทั้งหมด (1996–2003); กองทุนที่หยุดรายงาน **underperform ก่อนหยุด** — [Centaur](https://www.centaur.io/blog/how-to-evaluate-a-traders-public-track-record)
- **Luck vs skill**: 1,000 trader ที่ไม่มี skill เลย → **~125 คนชนะตลาด 3 ปีติด** (0.5³) — [FinLitSimplified, 21 พ.ย. 2026](https://www.finlitsimplified.org/scams-and-fraud/finfluencers)
- **Backfilled history ใน crypto signal**: 58 จาก 100 record ที่เก่าที่สุดบน SignalStart และ 19 จาก 28 signal MQL5 ที่อายุยาว/DD ต่ำ **มี history ก่อนถูก list เกิน 1 ปี**; 1 record โชว์ 508 สัปดาห์แต่เพิ่งเริ่มบน MQL5 ได้เดือนเดียว — [Quantex Research R2, 6 พ.ย. 2026](https://quantex.com.sg/research/copy-trading-survivors/)

**หลักฐานเชิงลบจากสิ่งที่วัดได้แล้ว**
- Alpha Arena S1.5: **Sharpe ของแถวที่ดีที่สุด = 0.019** (grok-4.20, 158 trades, +34.59%) และอีก 5 แถวถัดมา 0.009/0.000/0.016/0.004/−0.010 → ผลตอบแทน 2 สัปดาห์คือ noise — [tradepartner g6 notes, 26 ก.ย. 2026](https://github.com/josejuarez96/tradepartner/blob/main/docs/research/2026-09-26-g6-alpha-arena.md)
- **ผู้ชนะ S1 (Qwen3 Max) แพ้ทุก 4 การแข่งใน S1.5** (−29%) ขณะที่ Grok 4.20 ชนะ → ข้าม market/rule set แล้วผู้ชนะเปลี่ยน — [abit.ee, 4 ธ.ค. 2025](https://abit.ee/en/artificial-intelligence/ai-models-failed-again-on-the-stock-market-alpha-arena-season-1-5-results)
- **QLiveTradeBench: คะแนน benchmark ทั่วไปของ model แทบไม่สัมพันธ์กับผลตอบแทนหุ้น** — [thortradecopier, 13 พ.ย. 2026](https://thortradecopier.com/blog/can-chatgpt-trade-for-you)
- **Freqtrade backtest กับ live ต่างกันแม้ config เดียวกัน**: dry-run เติมทันที, live มี order ที่ไม่ fill, spread, rate-limit — [freqtrade#5489](https://github.com/freqtrade/freqtrade/issues/5489); [freqtrade#8518](https://github.com/freqtrade/freqtrade/issues/8518)
- **นักวิจัย on-chain ยืนยันไม่ได้ว่า execution เป็น autonomous**: wallet บอกได้แค่ว่าทำอะไร ไม่ได้บอกว่าใครสั่ง — [arXiv 2605.29174](https://arxiv.org/html/2605.29174)

**สิ่งที่ใช้ verify ได้จริงในทางปฏิบัติ**
- Hyperliquid: แยก **`pnlHistory` (ปรับ flows) จาก `accountValueHistory`**; drawdown ที่วัดบน account value จะนับการถอนเงินเป็นขาดทุน (เคส HLP: −23% account value แต่ PnL แทบไม่เปลี่ยน) — [Hyperfolio, 24 ต.ค. 2026](https://www.hyperfolio.fun/en/blog/hyperliquid-drawdown-equity-curve-guide)
- Hyperliquid vault: เช็ค **max drawdown เทียบ total return, leader's share (ขั้นต่ำ 5%), leverage/concentration, อายุ depositor** — [Totalis, 3 พ.ย. 2026](https://www.totalis.trade/blogs/hyperliquid/hyperliquid-vaults-hlp)
- Copy-trading filter ที่ใช้ได้: **≥3 ปี, max DD ≤40%, มี trade ใน 30 วันล่าสุด, และ history ก่อน listing ≤12 เดือน** → จาก 8 แพลตฟอร์ม เหลือเพียง **29 record** ที่ผ่าน (SignalStart 11, MQL5 9, Neotech 9) — [Quantex R2](https://quantex.com.sg/research/copy-trading-survivors/)
- ตัวชี้วัดที่ควรถามแทน ROI: **equity drawdown (ไม่ใช่ balance drawdown), win rate คู่กับขนาด loss, leverage/broker entity, provider มีเงินตัวเองในStrategy เท่าไร** — [BrokerListings](https://brokerlistings.com/research-hub/copy-trading-blow-ups)

### Inferences
- **เกณฑ์ขั้นต่ำที่เพียงพอจะ "ไม่ถูกหลอก" (แต่ยังไม่พอจะสรุปว่ามี edge)**: (1) read-only API ที่ third party เห็นทุก fill, (2) ≥12 เดือน และ ≥100 trades, (3) PnL รวม fee+funding+สลิปเปอร์, (4) flow-adjusted, (5) ระบุจำนวนบัญชีที่ล้มเหลว/ถูกปิดไปด้วย
- **เกณฑ์ที่จะสรุปว่ามี edge**: (6) out-of-sample/walk-forward ที่กำหนดก่อนเห็นข้อมูล, (7) ผลไม่เปลี่ยนเมื่อขยับ parameter ±20%, (8) ผ่านเกณฑ์เดิมใน regime ที่ต่างกัน (bull/bear/sideways), (9) capacity/ผลตอบแทนไม่พังเมื่อ size โต, (10) ต้นทุนรวม (VPS+fee+funding) ต่ำกว่าผลตอบแทนสุทธิ, (11) Sharpe/PF ที่ผ่าน hurdle เทียบ benchmark แบบเดียวกัน
- **ถ้า agent อ้าง "AI" แต่ให้แค่ราคา token หรือ APR จาก vault**: นั่นคือ fundamental ของ token ไม่ใช่ trading PnL — ต้องถามว่า treasury มี realized PnL เท่าไร แยกจาก mark-to-market ของ token ที่ตัวเองถือ
- หลักฐานที่ "ดีที่สุดในตลาดตอนนี้" (HLP) ยังไม่ผ่านเกณฑ์ข้อ 7–9 เต็ม: Sharpe 1.72 ใน 3 ปี, แต่ผลตอบแทนกระจุกใน 2 event และ APR ติดลบในบางเดือน → ควรจัดเป็น **beta ต่อ volatility/liquidation flow** ไม่ใช่ alpha

### Gaps
- ไม่พบเครื่องมือ third-party ที่รับรอง live PnL ของ crypto bot แบบ Myfxbook ที่เป็นที่ยอมรับทั่วไป (Myfxbook เน้น FX/MT4-5) → การ verify ยังต้อง DIY จาก on-chain/API
- ไม่มีงานที่คำนวณ **deflated Sharpe ratio หรือ PBO** ของ strategy ตลาด crypto จากแหล่ง public ที่เปิดให้ตรวจ (มีแต่งาน carry ที่อ้าง PBO 0.81 ในบันทึก sibling)
- ไม่มีเกณฑ์อุตสาหกรรม (IOSCO/ESMA/FCA) สำหรับ **การโฆษณาผลตอบแทนของ AI agent** โดยเฉพาะ — มีแต่กรอบ copy trading ทั่วไป
- ไม่พบหลักฐานว่า agent ใดผ่านเกณฑ์ 10 ข้อข้างต้นครบ — จึงสรุปได้เพียงว่า "ยังไม่มีตัวอย่างที่พิสูจน์ edge ได้" ไม่ใช่ "พิสูจน์แล้วว่าไม่มี"

---

## ภาคผนวก: ตารางสรุประดับการตรวจสอบ (ใช้ตัดสินใจเร็ว)

| ระดับ | ตัวอย่าง | อะไรที่ตรวจได้ | ข้อจำกัด |
|---|---|---|---|
| 1. On-chain + flow-adjusted | HLP, Hyperliquid user vault | ทุก fill, funding, PnL แยกจาก deposit/withdraw | PnL กระจุกตัว, APR ไม่มีสูตรชัด, ต้องเชื่อ smart contract |
| 2. Live account + read-only API | Freqtrade/Hummingbot ที่เจ้าของเปิด API | trade log จริง, fee จริง | เจ้าของเลือกช่วงเวลา/บัญชีที่จะโชว์ได้ |
| 3. Live ที่เจ้าของโพสต์เอง | 3Commas/Cryptohopper user, Pionex screenshot | ตัวเลขบน dashboard | ไม่มี trade log, เลือกเดือนที่ดี, affiliate incentive |
| 4. Dry-run / paper | 3Commas demo, Cryptohopper paper | signal ทำงาน | order เติมทันที, ไม่มี slippage/queue |
| 5. Backtest | 41 strategy test, repo ต่าง ๆ | จำลองซ้ำได้ถ้าเปิด data | ไม่มี slippage, เลือก parameter, survival bias |
| 6. โฆษณา/รีวิว affiliate | "grid annualized 42%", "+5,568%" | — | มักขัดกับ total PnL หรือไม่เปิด source |

**หมายเหตุเรื่อง affiliate:** หลายแหล่งที่ใช้ในบันทึกนี้ประกาศตัวเองว่ามี affiliate link (FillBench, AlgoGrade, Insigtrade, pickmytrade, uncoded, Ethy AI, Noon Barbari) — ใช้เฉพาะข้อเท็จจริงที่อ้างอิงเอกสารผู้ขายได้ และระบุไว้เมื่อตัวเลขมาจากรีวิวลักษณะนั้น ตัวเลขที่ใช้ตัดสินหลัก (arXiv, Hyperliquid API, Binance docs, CHI/ESMA) ไม่มี incentive เชิงพาณิชย์กับ bot รายใด
