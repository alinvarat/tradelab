# กลยุทธ์ Crypto Spot/Perpetuals/Futures ที่มีหลักฐาน Edge หลังหักต้นทุน (ทุนจำลอง ~147 USD, ณ ปี 2026)

ขอบเขต: crypto spot, perp, dated futures, commodity/FX futures · เน้น 2020–2026 · แยก "backtest" กับ "หลักฐานจริง" ทุกตัวเลขมี URL · ตัวเลขที่คำนวณเองระบุว่า "คำนวณเอง"

---

## Q1. Perpetual funding / basis carry, cross-exchange funding, cash-and-carry, spot-perp basis — ผลตอบแทนหลังหักค่าธรรมเนียมและ funding เป็นเท่าไร และต้องใช้ทุน/สภาพคล่องแค่ไหน (ตัวเลข 2020–2026)

### Takeaway
Carry แบบ delta-neutral (long spot / short perp) คือ edge ที่มีหลักฐานแน่นที่สุดใน crypto แต่ *กำลังตาย*: Sharpe 6.45 ในช่วง ส.ค. 2020–พ.ค. 2025 ลดเหลือ 4.06 ตั้งแต่ 2024 และติดลบใน 2025; ผลตอบแทนสุทธิจริง (ไม่ใช่ Sharpe) อยู่ราว +5.6%/ปี และติดลบใน 2026 เพราะ basis เหลือ ~3–5%/ปี ต่ำกว่าดอกเบี้ย T-bill — และมันต้องการทุนสองขา (จึงใช้ทุนเป็น 2 เท่า) ซึ่งทำให้ไม่เหมาะกับพอร์ต 147 USD

### Cited Findings
- Perpetual futures คิดเป็น >98% ของปริมาณซื้อขาย Bitcoin futures ใน sample ของ Schmeling et al.; กลยุทธ์ crypto carry = short perp + long spot — [arXiv 2510.14435, Fact 9](https://arxiv.org/html/2510.14435v1) (16 ต.ค. 2025)
- Annualized Sharpe ของ crypto carry = **6.45** ตลอด sample ส.ค. 2020–พ.ค. 2025; ตั้งแต่ 2024 ลดเหลือ **4.06**; **ติดลบใน 2025**; กำไรมาจาก funding เป็นหลัก โดย "mean return ประมาณ 8% และ volatility 0.8%" — [arXiv 2510.14435](https://arxiv.org/html/2510.14435v1)
- BTC perp funding + 30-day futures basis เคยขึ้นถึง **20–40% annualized ช่วงต้นปี 2024** และลงมาเหลือ **~3–5% ในปี 2026**; funding ติดลบชั่วคราวใน Q2 2026 — [Talos / State of the Network, ต.ค. 2026](https://www.talos.com/insights/following-the-funding-the-shift-towards-the-equity-basis-trade)
- ค่าเฉลี่ย funding ของ top-10 crypto perps ในปี 2026 = **~3%/ปี** เทียบกับ top-10 equity perps = **~11%/ปี**; cross-venue funding spread เฉลี่ยของ crypto perps = **12%** (equity perps 23%) — [Talos](https://www.talos.com/insights/following-the-funding-the-shift-towards-the-equity-basis-trade)
- ขนาดตลาดของ carry: Ethena USDe peak >**$14B** (ก.ย. 2025) แล้วลดเหลือ **$4.5B** หลังเหตุ liquidation 10 ต.ค. 2025 — [arXiv 2510.14435](https://arxiv.org/html/2510.14435v1); [Talos](https://www.talos.com/insights/following-the-funding-the-shift-towards-the-equity-basis-trade)
- Panel 30 Binance USD-M perps, **112,853 funding observations, 2023-01→2026-05**: median annualized funding **+7.3% (2023) → +13.4% (2024) → +2.8% (2025) → +0.6% (2026)** — [Bryan Vine, "Crypto Carry: The Funding-Rate Cross-Section, Net of Costs", 16 มิ.ย. 2026](https://bryanvine.github.io/alpha-research/paper2.html)
- Cash-and-carry แบบ level harvest: Sharpe headline **8.5 คือ artifact** ของ funding ที่ vol เกือบศูนย์; ตัวเลขที่ซื่อสัตย์คือ net return **+5.6%/ปี** ทั้ง sample และ **ติดลบใน 2026** (ต่ำกว่า risk-free ~5%) — [Bryan Vine](https://bryanvine.github.io/alpha-research/paper2.html)
- Cross-sectional funding factor (long low-funding / short high-funding perp, dollar-neutral, gross 1.0, cost 6 bp/side): net Sharpe **IS 0.71**, **purged walk-forward OOS 0.39**, max DD **−35%**, PBO **0.81**, ผ่านทุก 36 configs (0.58–1.5) — [Bryan Vine](https://bryanvine.github.io/alpha-research/paper2.html)
- Extreme funding แทบไม่พยากรณ์ราคา: rank-IC ระหว่าง trailing funding กับ forward 7-day return = **−0.005 (t = −0.89, n = 1,240 วัน)** — [Bryan Vine](https://bryanvine.github.io/alpha-research/paper2.html)
- ตัวอย่าง carry ฝั่ง equity perp บน Binance (bStock + perp, หัก 20 bp round-trip): CRCL, SNDK, MU, NVDA ให้ **7–10%/ปี**; SK Hynix ติดลบเมื่อ funding พลิก — [Talos](https://www.talos.com/insights/following-the-funding-the-shift-towards-the-equity-basis-trade)
- ความเสี่ยงที่โมเดล funding-only มองไม่เห็น: 10 ต.ค. 2025 หนังสือ "delta-neutral" ถูกบังคับปิดทั้งอุตสาหกรรม — [Bryan Vine](https://bryanvine.github.io/alpha-research/paper2.html); รายละเอียดเหตุการณ์อยู่ Q4

### Inferences
- อัตราผลตอบแทนที่ควรคาดหวังจาก carry ปี 2026 = **3–6%/ปีก่อนหักต้นทุนการทำสองขา** (ค่า fee สองขาไป-กลับ ≈ 0.1–0.2% ของ notional ต่อรอบ, บวก slippage) → สุทธิใกล้ 0 ถึง 4%/ปี
- ถ้าต้องกันความเสี่ยงด้วยการถือ spot จริงและ short perp บนอีก venue ต้องวาง margin ทั้งสองที่ → **capital efficiency ~50%** และเพิ่ม counterparty exposure เป็น 2 เท่า; ที่ทุน 147 USD ต้องแยกอย่างน้อย 2×~74 USD ซึ่งต่ำกว่า min notional ที่ใช้งานได้จริงในหลาย prodotti
- Sharpe 6+ ที่คนอ้างถึงคือ Sharpe ของ *funding stream* ไม่ใช่ของ *กลยุทธ์*; ใช้ Sharpe เป็นเกณฑ์คัดเลือกจะหลอกตัวเอง (ดู Q5 เรื่อง ruin)

### Gaps
- ไม่พบตัวเลข median funding รายปีที่แยกตาม exchange (Bybit/OKX/Deribit) แบบ public ฟรี; ตัวเลข 2020–2022 ใน literature ส่วนใหญ่มาจาก Binance เท่านั้น
- ไม่พบงานที่วัด **net return ของ cross-exchange funding arb หลังหักค่าโอน (withdrawal/gas) และต้นทุน hedging FX/USDT de-peg** — ตัวเลขส่วนใหญ่เป็น gross spread
- งานของ Schmeling et al. (Management Science 2026) เป็น paywall; ตัวเลขที่อ้างอิงมาจาก survey arXiv เท่านั้น ไม่ได้ตรวจสอบตารางต้นฉบับ

---

## Q2. Time-series / cross-sectional momentum, volatility targeting, trend following, breakout, mean reversion — effect size, drawdown, decay, transaction costs

### Takeaway
Momentum crypto มีจริงเฉพาะ **horizon สั้นมาก (2 สัปดาห์)** และเป็น horizon ที่ต้นทุนกินมากที่สุด: gross +0.573%/สัปดาห์ เหลือ **+0.173%/สัปดาห์หลังหัก 0.40pp round-trip** และไม่ผ่าน significance test ใด ๆ; trend following (MA/breakout + vol targeting) ลด drawdown ได้จริงแต่ให้ผลตอบแทนไม่ชนะ buy-and-hold หลังหักต้นทุน

### Cited Findings
- Cross-sectional momentum (2-week formation, value-weighted quintiles, 16,468 coins, ธ.ค. 2013–ก.ย. 2025): long-short **+2.6%/สัปดาห์ (t = 3.89)** ทั้ง sample และ **+2.1%/สัปดาห์ (t = 3.70)** หลัง 2020 — [arXiv 2510.14435, Table 2](https://arxiv.org/html/2510.14435v1)
- Momentum 12 สัปดาห์ และ 24 สัปดาห์ **ไม่มีนัยสำคัญ** (+0.3%, −0.9% ต่อสัปดาห์; t = 0.47, −1.50) ทั้ง sample; หลัง 2020 ก็ยังไม่ significant — [arXiv 2510.14435, Table 3](https://arxiv.org/html/2510.14435v1)
- Replication บน universe ที่เทรดได้จริง: **832 Binance USDⓈ-M perps, ม.ค. 2020–ก.ค. 2026, 338 สัปดาห์อิสระ** → gross spread **+0.573%/สัปดาห์** (สัปดาห์บวก 52.7%), ผ่าน significance แค่ 1 จาก 3 tests — [Karaptic Research, 12 ก.ย. 2026](https://karaptic.com/blog/cross-sectional-momentum-net-of-costs)
- ต้นทุน 0.05% taker/side + 0.05% slippage/side = **0.40pp round-trip = ~70% ของ gross spread** → เหลือ **+0.173%/สัปดาห์**, สัปดาห์บวก **50.0%**, ไม่ผ่าน test ใดเลย — [Karaptic](https://karaptic.com/blog/cross-sectional-momentum-net-of-costs)
- Specification instability: 2-week holding แบบ non-overlapping ให้ **+0.429%/สัปดาห์** ใน headline phase แต่ **−0.076%/สัปดาห์** ใน diagnostic phase — ต่างกันแค่วันเริ่มนับสัปดาห์ — [Karaptic](https://karaptic.com/blog/cross-sectional-momentum-net-of-costs)
- ตัวเลขจาก asset manager จริง (Starkiller Capital): **125 basis points round-trip cost ทำให้ edge ตาย** — [Karaptic อ้างถึง SSRN 4322637](https://karaptic.com/blog/cross-sectional-momentum-net-of-costs)
- Trend following บน 20 เหรียญ liquid สุด: net-of-fees **Sharpe > 1.5**, alpha **10.8%/ปี** เทียบ BTC (backtest, 2026) — [Concretum, "Catching Crypto Trends", ก.พ. 2026](https://concretumgroup.com/wp-content/uploads/2026/02/Catching-Crypto-Trends.pdf)
- BTC trend signal (สลับ BTC/cash) 2012–2023: **126%/ปี, Sharpe 1.9** — [Grayscale Research](https://research.grayscale.com/reports/the-trend-is-your-friend-managing-bitcoins-volatility-with-momentum-signals) (in-sample backtest, period ที่ BTC ขึ้น 100×)
- Backtest อิสระที่มี transaction cost: MA crossover ให้ **27.1%/ปี เทียบค่า buy-and-hold 29.3%/ปี**; ลด worst loss จาก **−81% เหลือ −56%**; เพิ่ม vol targeting ลดเหลือ **−43% ถึง −51%** — [pooriag/crypto-strategy-backtest](https://github.com/pooriag/crypto-strategy-backtest)
- Vol targeting อย่างเดียวลด deepest loss จาก **84% เหลือ 15%** ใน test ปี 2017–2025 — [Summitward](https://summitward.com/learn/crypto-trend-following) (practitioner, ไม่ใช่ peer-reviewed)
- ทุกกลยุทธ์ microstructure/HF ที่ turnover สูงล้มเหลวหลังต้นทุน: ตาราง net Sharpe ของ spot = **−31.29** สำหรับ AR(1), turnover 124×/วัน — [Frontiers in Blockchain, 2026](https://frontiersin.org/journals/blockchain/articles/10.3389/fbloc.2026.1811716/full)

### Inferences
- Edge ของ momentum อยู่ใน 2-week horizon ซึ่ง turnover ~50–100%/สัปดาห์ → ต้นทุน 0.4pp/สัปดาห์ กิน 70% ของ gross; ที่ทุน 147 USD ค่า fee คิดเป็นสัดส่วนเท่ากัน (ไม่ขึ้นกับขนาด) ดังนั้น "edge หาย" เป็นเรื่องของ *ความถี่* ไม่ใช่ขนาดทุน
- งานที่รายงาน Sharpe >1.5 ส่วนใหญ่เป็น backtest ใน-sample และไม่ได้หัก slippage จริง; งานที่หักต้นทุนจริง (Karaptic, pooriag) ให้ผล "เสมอตัวหรือแย่กว่า buy-and-hold"
- Trend following มีคุณค่าในฐานะ *risk overlay* (ลด DD 30–60%) มากกว่า *return engine*; ถ้าเป้าหมายคือ high return ด้วยทุนเล็ก มันไม่ตอบโจทย์

### Gaps
- ไม่พบ out-of-sample study ของ breakout (Donchian 20/55) ใน crypto ที่หักต้นทุนและรายงาน DD — มีแต่ backtest เชิงพาณิชย์
- ไม่พบตัวเลข decay ของ momentum รายปี (2020→2026) แบบต่อเนื่อง นอกจาก median funding; Karaptic ให้ภาพรวม 338 สัปดาห์ แต่ไม่มีตัวเลข net รายปี
- Vol targeting: ไม่พบงานที่วัดผลของ *transaction cost ของการ rebalance รายวัน* ต่อ Sharpe ใน crypto (ต้นทุนมักถูกสมมติเป็น 0)

---

## Q3. Event-driven crypto: listings/delistings, token unlocks, airdrops, ETF flows, halving, regulatory news — event ไหนมี drift และราคาสะท้อนเร็วแค่ไหน

### Takeaway
สอง event ที่มี drift วัดได้ชัดคือ **exchange listing (บวก 5–10% รอบวัน) และ token unlock (ลบ ไม่ใช่บวก)**; ทั้งคู่ถูก front-run ล่วงหน้า (listing: ซื้อข่าวลือ, unlock: drift เริ่ม 30 วันก่อน) และหลักฐานขัดกันเรื่องขนาด — listing effect จางลงมากหลัง 2021 เพราะตลาด anticipate

### Cited Findings
- 327 exchange listings ของ 180 coins บน 22 exchanges: **average abnormal return +5.7% ในวัน listing** (statistically significant) — [Blockchain Research Lab, 10 ก.ย. 2019](https://blockchainresearchlab.org/en/blog/2019/09/10/market-reaction-to-exchange-listings-of-cryptocurrencies)
- Cross-listing ของ ICO tokens: **+6.51% วัน listing, +9.97% ใน 7-day window** — [Springer, Decisions in Economics and Finance, 2021](https://link.springer.com/article/10.1007/s10203-021-00323-0)
- Coinbase listings เพิ่ม volume 30 วัน **68–94%**; Binance listings เพิ่ม **22–160%**; effect เล็กลงหลัง 30 วัน — [Li et al., Loyola / SAET 2023](https://saet.uiowa.edu/wp-content/uploads/sites/18/gravity_forms/11-4d2b366dcba748062160497d6fc362c1/2023/06/cryptoexchanges.pdf)
- พฤติกรรมราคา listing บน Binance: pump หลายวันหลัง listing แล้วค่อย ๆ ขายลงมา จน **ROI 30 วัน ≈ 0** — [RockawayX](https://rockawayx.com/insights/bullish-or-bearish-what-really-happens-when-tokens-list-on-a-cex)
- Token unlocks: Keyrock วิเคราะห์ **16,000+ unlock events** → **90% ให้ผลตอบแทน 30 วันติดลบ**, price impact เริ่ม **~30 วันก่อน unlock**, unlock ขนาดใหญ่ทำให้ราคาตกแรงขึ้น **2.4×** — [Keyrock, "From Locked to Liquidity"](https://keyrock.com/from-locked-to-liquidity-what-16000-token-unlocks-teach-us/)
- 52 unlock events บน Binance ม.ค. 2023–ธ.ค. 2025: **46/52 (88.5%) ติดลบใน 72 ชั่วโมง** (binomial p = 2.2×10⁻⁹) — [SSRN 6632838, Kim 2026](https://doi.org/10.2139/ssrn.6632838)
- **ขัดแย้ง**: งานอีกชิ้นบน SSRN อ้างว่าเมื่อหัก token-specific drift แล้ว ราคาแทบไม่ตอบสนองใน 3 วัน (market-model abnormal return ไม่มีนัยสำคัญ) — [SSRN 7567460, "Does Modigliani-Miller Fail in Crypto?"](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7567460)
- ETF/basis: การเปิด spot Bitcoin ETF ม.ค. 2024 มาพร้อม basis ที่ 20–40% annualized ซึ่งเป็นช่วงที่ carry ทำเงินได้มากที่สุด — [Talos](https://www.talos.com/insights/following-the-funding-the-shift-towards-the-equity-basis-trade)
- Regulatory event: event study ของ 6 การแทรกแซงกำกับดูแล DeFi ปี 2023–2025 พบ abnormal returns มีนัยสำคัญ (ไม่ได้ระบุขนาดใน abstract) — [MDPI JRFM 19(1):54, 2026](https://mdpi.com/1911-8074/19/1/54)

### Inferences
- Listing effect เป็น "buy the rumor" มากกว่า "buy the listing": abnormal return กระจุกในวันประกาศ/วันแรก และกลับเป็นศูนย์ใน 30 วัน → กลยุทธ์ที่ทดสอบได้คือ **front-run announcement** ไม่ใช่ซื้อวัน listing (ซึ่งต้นทุน slippage ระหว่าง pump สูงมาก)
- Unlock เป็น event ที่ *คาดเดาได้ล่วงหน้า* (ตาราง unlock public) → ถ้า drift เริ่ม 30 วันก่อน แปลว่าตลาด price ไปแล้วบางส่วน; ส่วนที่เหลือคือ "sell the event" ซึ่งเสี่ยง squeeze
- หลักฐาน unlock ขัดกันชัดเจน (90% ติดลบ vs ไม่มีนัยสำคัญ) — ความต่างอยู่ที่ universe, การวัด abnormal return และการคุม token-specific trend; ต้อง replicate เองก่อนเชื่อ

### Gaps
- ไม่พบตัวเลขผลของ **delisting announcement** (ผลลบกี่ %) จากแหล่งที่ตรวจสอบได้
- ไม่พบงาน quantified ของ **halving** 2020/2024 ว่า drift มีจริงหลังหัก trend ตลาด — มีแต่บทความอุตสาหกรรม
- ไม่พบตัวเลขผลของ **airdrop** ต่อราคา token หลัง TGE ที่หักต้นทุนการ short
- ไม่พบตัวเลขขนาด abnormal return ของ FOMC/CPI ต่อ BTC ที่เป็น peer-reviewed (มีแต่ thesis)

---

## Q4. Market microstructure: liquidation cascades, order-book imbalance, funding spikes, weekend effects — retail API จับอะไรได้จริง

### Takeaway
Liquidation cascade เป็น event ที่ retail *เห็น* ได้ (ผ่าน API สาธารณะ) แต่ *เทรด* ได้แย่ เพราะ slippage/spread ระเบิดในวินาทีนั้น; order-book imbalance และ latency edge เป็นสนามของ HFT ที่ต้อง colocation — retail API (50–200 ms) แพ้เชิงโครงสร้าง

### Cited Findings
- 10 ต.ค. 2025: liquidation **~$19B ใน 24 ชม.**, ผู้เทรดถูกบังคับปิด **~1.6 ล้านราย**, BTC ร่วง **>14%**, open interest โลกลด **27.5%** — [CoinDesk Research](https://coindesk.com/research/market-spotlight-the-19-billion-liquidation-that-shook-crypto); [CCN, 2026](https://www.ccn.com/education/crypto/crypto-october-10-crash-anniversary-2026-liquidation-risk/)
- ตัวเลข $19B เป็น *notional* ไม่ใช่ขาดทุนจริง — ขาดทุนจริงน้อยกว่านั้นมาก — [Yahoo Finance/CoinGlass](https://finance.yahoo.com/news/19b-crypto-liquidations-didn-t-135537432.html)
- การศึกษา 7 เหตุการณ์ cascade ใหญ่ปี 2022–2025 พบโครงสร้างแบบ **subcritical branching process** (แพร่กระจายแล้วดับเอง ไม่ลุกลามแบบไม่สิ้นสุด) — [arXiv 2608.03616, 4 ส.ค. 2026](https://arxiv.org/abs/2608.03616)
- เสนอกรอบ **Slippage-at-Risk (SaR)** วัดความเสี่ยงในการปิดสถานะจากสภาวะ order book ที่observable ได้ — [arXiv 2603.09164](https://arxiv.org/html/2603.09164)
- Order-book imbalance พยากรณ์ return ระยะสั้นได้จริง แต่ต้องข้อมูลระดับ **100 ms, 20 ระดับ depth** และแบบจำลองซับซ้อน — [Charles University thesis, 2025](https://dspace.cuni.cz/bitstream/handle/20.500.11956/213492/130479105.pdf?isAllowed=y&sequence=3); [arXiv 2506.05764](https://arxiv.org/pdf/2506.05764)
- LOB-based กลยุทธ์ที่ turnover สูงให้ **net Sharpe ติดลบหนัก** หลังหักต้นทุน (spot −31.29) — [Frontiers in Blockchain 2026](https://frontiersin.org/journals/blockchain/articles/10.3389/fbloc.2026.1811716/full)
- Weekend effect: weekend returns สูงกว่า weekday อย่างมีนัยสำคัญ (p < 0.05); BTC mean daily return เปลี่ยนจาก 0.0012 ในวันธรรมดา — [ACR Journal, "The Weekend Effect in Crypto Momentum"](https://acr-journal.com/article/the-weekend-effect-in-crypto-momentum-does-momentum-change-when-markets-never-sleep--1514/)
- **ขัดแย้ง**: งาน day-of-week อื่นพบว่า *วันจันทร์* ให้ผลตอบแทนสูงสุด (2013–2018) และงาน ANN พบ *วันพฤหัส* ต่ำสุด — ทิศทางไม่คงที่ — [Finance Research Letters 2018](https://sciencedirect.com/science/article/abs/pii/S1544612317307894); [Financial Innovation 2023](https://link.springer.com/article/10.1186/s40854-023-00499-x)

### Inferences
- สิ่งที่ retail ทำได้จริงจาก microstructure: (1) **ไม่เทรด**ในช่วง cascade (protection ไม่ใช่ alpha), (2) ใช้ liquidation heatmap เป็น *ตัวกรองความเสี่ยง* ก่อนเข้าเทรด, (3) เล่น mean reversion *หลัง* cascade สงบ (ชั่วโมง–วัน) ไม่ใช่ระหว่าง
- Weekend effect มีหลักฐานอ่อนและทิศทางไม่คงที่ — ไม่ควรใช้เป็น standalone signal; ใช้ได้แค่เป็น context ในการเลือกเวลา rebalance
- Funding spike: ข้อมูลจาก Q1 ชี้ว่า extreme funding แทบไม่พยากรณ์ return (IC −0.005) → funding spike ใช้เป็นสัญญาณ *ต้นทุน* ไม่ใช่สัญญาณ *ทิศทาง*

### Gaps
- ไม่พบตัวเลข "average slippage ของ retail market order ขนาด $100–$1,000 บน Binance/Bybit ระหว่าง cascade" — ต้องวัดเองจาก order book snapshot (ไม่มี public dataset ฟรี)
- ไม่พบงานที่วัด **funding spike (|funding| > 0.1%/8h) → forward 24h return** โดยตรง
- ไม่พบข้อมูล weekend effect ในช่วง 2024–2026 โดยเฉพาะ (งานส่วนใหญ่อ้าง sample เก่า)

---

## Q5. ข้อจำกัดของทุนเล็ก: min order size, fees, slippage, leverage limits, counterparty risk — เพดานผลตอบแทนจริงและ ruin probability ที่ 10x/20x

### Takeaway
ที่ 147 USD เพดานผลตอบแทนที่สมเหตุสมผลคือ **8–12%/ปี (ราว $12–18)** จากกลยุทธ์ net Sharpe ~0.4–0.6 ที่ vol target 20% — ไม่ใช่ 100%+; การใช้ 10x/20x ทำให้ **ruin probability ภายใน 1 ปี = 84%/92%** (จำลอง) และค่า funding เพียงอย่างเดียวที่ 10x กิน **~60–110% ของทุนต่อปี**

### Cited Findings
- Binance USDⓈ-M futures VIP 0: **maker 0.0200% / taker 0.0500%**; จ่ายด้วย BNB ลด 10% เหลือ **0.0180%/0.0450%**; spot standard **0.10%** — [Binance Fee Schedule](https://www.binance.com/en/fee/futureFee); [Binance Square, 2026](https://www.binance.com/en/square/post/388643211570560)
- Bybit BTCUSDT (ตรวจ 2026-10-17): **min order qty 0.001 BTC, min notional 5 USDT** — [Kevin Wu, Bybit Futures Guide 2026](https://kevin-wu.org/en/bybit-futures-guide-en)
- Binance ปฏิเสธ order ที่ notional ต่ำกว่า **5 USDT** (error −4164) — [Hafizebot](https://hafizebot.com/post/binance-error-4164-order-notional-too-small)
- Micro futures margin (Ironbeam, 21 เม.ย. 2026): MES day **$50** / overnight **$2,307**; MGC day **$100** / overnight **$2,640**; MCL day **$200** / overnight **$416**; MNQ overnight **$3,542** — [Ironbeam](https://ironbeam.com/how-much-money-to-start-trading-futures)
- ค่าคอมมิชชัน micro futures: **$0.75/side + $0.30 clearing + exchange/NFA** ต่อสัญญา; MES tick = **$1.25**, MGC tick = **$1.00** — [tastytrade](https://tastytrade.com/commissions-and-fees); [Schwab Micro Futures](https://schwab.com/futures/micro-futures)
- FTX: ผู้ใช้กู้คืนได้ **118–119% ของมูลค่าบัญชี ณ วันยื่นล้มละลาย (พ.ย. 2022)** แต่เป็น USD ไม่ใช่ crypto; ตอนล้มละลาย FTX ถือ BTC จริงเพียง **0.1%** ของที่ลูกค้าคิดว่ามี — [Reuters, 7 ต.ค. 2024](https://www.reuters.com/legal/crypto-exchange-ftxs-liquidation-plan-receives-court-approval-2024-10-07/)

**ตัวเลขคำนวณเอง (สมมติฐานระบุชัด):**
- สูตร liquidation แบบ isolated: ราคาที่ถูกบังคับปิดเมื่อขาดทุน ≈ `1/leverage − maintenance_margin` → 10x ≈ **−9.5%**, 20x ≈ **−4.5%** (mm 0.5%)
- Reflection principle (driftless, σ_daily = 3%): P(แตะ −9.5% ภายใน 30 วัน) = **56.3%**; ภายใน 7 วัน = **23.1%**; ที่ 20x (barrier −4.5%) = **78.4% (30 วัน)**, 57.1% (7 วัน). ถ้า σ_daily = 4%: 10x → **66.5%**, 20x → **83.7%**
- Monte Carlo (20,000 paths, fixed notional, µ = 30%/ปี, σ = 60%/ปี, funding 10.95%/ปี = 0.01%/8h, taker 0.05% ขาเข้า, liquidate เมื่อ equity ≤ 0.5% ของ notional, ไม่มี stop-loss):

| Leverage | Ruin ภายใน 1 ปี | P(กำไร) | Median equity | Median เวลาถึง ruin |
|---|---|---|---|---|
| 1x | 0.0% | 51.7% | 1.03 | — |
| 3x | 50.8% | 41.7% | 0.00 | 128 วัน |
| 5x | 70.2% | 28.1% | 0.00 | 64 วัน |
| 10x | **84.2%** | 15.5% | 0.00 | **22 วัน** |
| 20x | **91.7%** | 8.3% | 0.00 | **8 วัน** |

- ต้นทุน funding ที่ leverage L: `funding_annual × L` ของ equity → ที่ funding 6%/ปี และ 10x = **60% ของทุน/ปี**; ที่ 11%/ปี และ 10x = **110% ของทุน/ปี**
- ค่า fee ต่อ round-trip ที่ 10x = 0.10% × 10 = **1.0% ของ equity ต่อการเทรด 1 รอบ** → เทรด 3 รอบ/วัน = −3%/วัน ก่อน market move ใด ๆ

### Inferences
- เพดานผลตอบแทนจริง: กลยุทธ์ที่ดีที่สุดที่มีหลักฐาน net OOS (cross-sectional funding, Sharpe 0.39) ที่ vol 20% ให้ ~**8%/ปี**; ที่ 147 USD = **~$12/ปี** — ต่ำกว่าค่า fee ของการเทรด active มาก
- Commodity/FX futures ด้วย 147 USD: ทำได้เฉพาะ **day-trade MES/MGC/MCL** (margin $50–$200) แต่ overnight margin $416–$2,640 ทำให้ถือข้ามคืนไม่ได้; ค่า commission ~$2.1–2.5 round-trip = **1.4–1.7% ของทุนต่อสัญญา** → ต้องชนะ 2 ticks ก่อน break-even
- Counterparty risk เป็นความเสี่ยง *เชิงทวีคูณ* สำหรับ carry: FTX คืน 119% ของมูลค่า ณ พ.ย. 2022 แต่ BTC ขึ้นจาก ~$16k เป็น >$100k ในช่วงนั้น → ผู้ถือ crypto จริงขาด upside มหาศาล; การถือ spot บน exchange จึงมี opportunity cost ที่ไม่ปรากฏในตัวเลข "recovery rate"
- ข้อสรุปเชิงกลยุทธ์: ที่ทุนระดับนี้ **leverage >3x ทำให้ ruin probability >50%/ปี** — ไม่ใช่ "เพิ่มผลตอบแทน" แต่คือ "ลดอายุพอร์ต"

### Gaps
- ไม่พบตัวเลข official ของ Binance/Bybit เรื่อง **liquidation penalty fee** และ maintenance margin tier สำหรับ notional <$10k (เอกสารระบุเป็น tier แต่ไม่เผยแพร่ตัวเลขละเอียดในหน้าเดียว)
- ไม่พบข้อมูล **slippage จริงของ order $100–$500** ในคู่ BTCUSDT/ETHUSDT จากแหล่ง public ที่วัดเป็น bps
- ไม่มีข้อมูล **ภาษี/ค่าธรรมเนียมถอน (withdrawal fee) ของแต่ละเชน** ซึ่งกินต้นทุนจริงของ carry ข้าม venue (มัก 1–5 USD ต่อการย้าย)

---

## Q6. 2–3 สมมติฐานที่ทดสอบได้ พร้อมกฎที่แน่นอน แหล่งข้อมูล และการควบคุม

> หลักการ: ทุกข้อใช้ public data + simulated money, แยก backtest (in-sample) / walk-forward (OOS) / live paper ชัดเจน, หัก 5 bp taker + 5 bp slippage ต่อขา (และ stress ที่ 15 bp), รายงาน max DD และ ruin ก่อนสรุป

### H1 — Cross-sectional funding carry (หลักฐาน OOS แข็งที่สุด)
**สมมติฐาน:** perp ที่ funding สูงกว่า (crowded long) จะ underperform perp ที่ funding ต่ำกว่า ในระดับ dollar-neutral หลังหักต้นทุน

**กฎexact**
- Universe: 30 perp USDⓈ-M บน Binance ที่มี volume 30 วันสูงสุด, คัดเลือก ณ วัน rebalance (point-in-time, ไม่ใช้รายชื่อปัจจุบันย้อนหลัง)
- Signal: ค่าเฉลี่ย funding 7 วัน ย้อนหลัง (shift 1 วัน) → จัดอันดับ
- Position: long tercile ล่าง (funding ต่ำ) / short tercile บน (funding สูง), equal-weight, dollar-neutral, gross = 1.0×equity
- Rebalance: ทุกวันจันทร์ 00:00 UTC; turnover cap 50%/ครั้ง
- Cost: 6 bp/side (taker 5 + slippage 1) เป็น base case; stress 15 bp
- Vol target: 20%/ปี (scale gross ตาม realized vol 30 วัน, cap 2×)
- Stop: ปิดทั้งพอร์ตถ้า DD > 25%; ห้ามเทรดถ้า funding spread ของ tercile < 2%/ปี (edge ไม่คุ้ม cost)
- Leverage สูงสุด: **1.0×** (ไม่ใช้ leverage)

**ข้อมูล**
- `https://data.binance.vision/data/futures/um/daily/fundingRate/` (funding รายวัน, ฟรี)
- `https://fapi.binance.com/fapi/v1/fundingRate` (ย้อนหลัง 1,000 จุด/ครั้ง)
- klines รายวันจาก data.binance.vision สำหรับ price leg

**การควบคุม**
- Purged walk-forward (train 12 เดือน / test 3 เดือน, embargo 7 วัน), deflated Sharpe, PBO
- เทียบกับ baseline: holding BTC, และ cash (T-bill ~5%)
- ต้องรอด: (a) drop ทีละเหรียญ, (b) เปลี่ยน lookback 3/7/14 วัน, (c) ตัดช่วง 10 ต.ค. 2025 ออก
- เกณฑ์ผ่าน: net OOS Sharpe ≥ 0.3 และ max DD ≤ 20% ที่ vol target 20%

**ความคาดหวังตามหลักฐาน:** net Sharpe ~0.4, max DD −35% (ก่อน vol target) → ที่ 147 USD คาด +$5–9/ปี; ผ่านเกณฑ์ = "ทดสอบได้" ไม่ใช่ "รวยได้"

### H2 — Post-liquidation mean reversion (event-driven, จำนวน event น้อย)
**สมมติฐาน:** หลัง liquidation cascade ใหญ่ BTC/ETH มี rebound 3–7 วัน มากกว่าวันปกติ (forced selling จบแล้ว)

**กฎexact**
- Trigger: liquidation 24 ชม. รวม > **$1B** และ BTC drawdown 24 ชม. > **−7%** (ใช้ Coinglass/Coinalyze aggregate)
- Entry: market buy ที่ close ของแท่ง 4h แรกที่ trigger ครบ; ถ้า trigger เกิดซ้ำภายใน 24 ชม. ไม่เพิ่มสถานะ
- Exit: ชนะเมื่อ +6% หรือครบ 7 วัน (whichever first); ขาดทุนตัดที่ −4%; time stop 7 วัน
- Size: risk 1% ของ equity ต่อ event (หยุดที่ −4% → notional ≈ 25% ของ equity)
- Leverage: 1× (spot) หรือ perp 2× เท่านั้น

**ข้อมูล**
- Coinglass API (liquidation history; free tier จำกัด), Coinalyze, หรือ Binance forceOrders (จำกัด)
- ราคา: Binance klines 1h/4h

**การควบคุม**
- นับ event ทั้งหมดตั้งแต่ 2021 (คาด ~10–20 ครั้ง) → **underpowered**; ต้องรายงาน confidence interval และไม่สรุปจาก n น้อย
- เปรียบเทียบกับ unconditional 7-day return (bootstrap), และกับ random entry วันเดียวกันของปีก่อน
- ตรวจ survivorship: รวมเหตุการณ์ที่ rebound ไม่เกิด (২০২২ LUNA, FTX)

**ความคาดหวัง:** หลักฐานที่มี (subcritical branching) บอกว่า cascade *ดับเอง* แต่ไม่ได้บอกว่า rebound ทำเงินได้หลังหัก spread ที่กว้างขึ้น — ถ้า n < 20 ให้ถือเป็น "ยังสรุปไม่ได้"

### H3 — Token unlock short (ขัดแย้งใน literature → ต้อง replicate)
**สมมติฐาน:** token ที่มี unlock > 2% ของ circulating supply มีผลตอบแทนติดลบในช่วง 30 วันก่อนถึงวัน unlock

**กฎexact**
- Universe: token ที่มี perp บน Binance/Bybit และมีตาราง unlock public
- Signal: unlock value ≥ $5M และ ≥ 2% ของ circulating supply, ภายใน 30 วันข้างหน้า
- Position: short perp ขนาด 0.5× equity ต่อชื่อ, สูงสุด 3 ชื่อพร้อมกัน (gross cap 1.5×)
- Entry: 30 วันก่อน unlock (หรือทันทีที่ประกาศถ้าน้อยกว่า 30 วัน); Exit: วัน unlock + 1 วัน
- Cost: 10 bp/side + funding ที่จ่ายจริงตลอด holding (ถ้า funding ติดลบแรง ให้ปิดก่อน)
- Stop: +15% adverse (squeeze protection)

**ข้อมูล**
- ตาราง unlock: Tokenomist (fka Token Unlocks), Keyrock public reports
- ราคา/funding: Binance/Bybit API

**การควบคุม**
- ต้อง replicate ทั้งสองฝั่งของข้อขัดแย้ง: วัดทั้ง *raw return* และ *abnormal return หัก market/token drift* — ถ้าใช้ raw return จะได้ผล "90% ติดลบ" แต่ถ้าหัก drift อาจไม่เหลืออะไร
- ตรวจว่า drift เกิดก่อน 30 วันหรือไม่ (ถ้าใช่ กลยุทธ์นี้สายเกินไป)
- ระวัง: short squeeze, borrow/funding cost, และการที่ exchange เปลี่ยน funding interval

**ความคาดหวัง:** ถ้า drift ถูก price ไปแล้ว 30 วันก่อน event → edge ที่เหลือ ~0 หลังต้นทุน; นี่คือ hypothesis ที่มีโอกาส "FAIL" สูง และควรทดสอบเพื่อ *ตัดทิ้ง* มากกว่าหวังผล

---

## สรุปเชิงตัวเลขสำหรับผู้เขียนรายงาน

| ประเด็น | ตัวเลข | แหล่ง |
|---|---|---|
| Carry Sharpe 2020–2025 | 6.45 → 4.06 (2024) → ติดลบ (2025) | arXiv 2510.14435 |
| Carry net return | +5.6%/ปี, ติดลบ 2026 | Bryan Vine 2026 |
| Median funding รายปี | 7.3% → 13.4% → 2.8% → 0.6% | Bryan Vine 2026 |
| BTC basis 2024 vs 2026 | 20–40% → 3–5% | Talos 2026 |
| Momentum gross/net ต่อสัปดาห์ | +0.573% → +0.173% | Karaptic 2026 |
| ต้นทุนที่ทำให้ momentum ตาย | 125 bp round-trip | Starkiller via Karaptic |
| Listing abnormal return | +5.7% (วันแรก), +9.97% (7 วัน) | BRL 2019; Springer 2021 |
| Unlock events ติดลบ 30 วัน | 90% (16,000 events) | Keyrock |
| Liquidation 10 ต.ค. 2025 | $19B notional, 1.6M traders, OI −27.5% | CoinDesk; CCN |
| Fee VIP0 | 0.02/0.05% (perp), 0.10% (spot) | Binance |
| Min notional | 5 USDT | Bybit; Binance −4164 |
| MES overnight margin | $2,307 (day $50) | Ironbeam 2026 |
| Ruin 1 ปี @10x / 20x | 84% / 92% | คำนวณเอง (MC) |
| เพดานผลตอบแทนจริง @147 USD | ~8–12%/ปี = $12–18 | คำนวณเองจาก Sharpe 0.4–0.6 |
