# คอนเทสต์บัญชีเล็ก, prop-firm challenge และ "small account challenge" 2015–2026

ขอบเขต: บัญชี 100–10,000 USD, ระยะ 1 เดือนขึ้นไป, เฉพาะข้อมูลสาธารณะ; แยก "ตรวจสอบได้ (broker/exchange-verified)" ออกจาก "self-reported" และ "demo"
อัปเดตข้อมูล: 24 พ.ย. 2026

---

## 1) คอนเทสต์ที่ตรวจสอบได้: ใครรายงานอะไร ใครชนะด้วยบัญชีเล็ก และหลังจากนั้นเกิดอะไร

### Takeaway
คอนเทสต์จริงจังที่เปิดให้บัญชีเล็กมีน้อยมาก และ **ไม่มีเจ้าภาพรายใดเปิดครบทั้ง 4 ตัวเลข (ขนาดบัญชี, ผลตอบแทน, drawdown, จำนวนผู้เข้า)** — Robbins Cup เปิดแค่ % ผลตอบแทนกับ top-5, WSOT เปิดจำนวนผู้เข้า + % + max drawdown แต่ไม่เปิดขนาดบัญชี, prop firm เปิด pass/payout แต่ไม่เปิดผลตอบแทนผู้ชนะ คนที่ทำผลได้ระดับ "หลายเท่าต่อเดือน" ในคอนเทสต์คือ outlier ของสนามที่ *ไม่จำกัด drawdown* และแทบไม่มีใครทำซ้ำได้ในปีถัดๆ ไปในระดับเดิม

### Cited Findings

**A. Robbins / World Cup Trading Championships (WCTC) — real money, broker-verified, แต่เปิดเผยจำกัดมาก**

- กติกา: เงินขั้นต่ำ futures annual **10,000 USD/entry**, forex **5,000 USD**, ควอเตอร์เตอร์ราย **2,500 USD**, รายเดือน/ไมโคร **500 USD**; ต้องมีอย่างน้อย **10 round-turn** ต่อบัญชีจึงมีสิทธิ์ได้ถ้วย — [worldcupchampionships.com](https://www.worldcupchampionships.com/) (หน้าแรก, เข้าถึง 24 พ.ย. 2026)
- กติกา liquidation: ถ้า equity ระหว่างวันลด **50% จาก equity ต้นวัน** โบรกอาจ liquidate และหยุดเทรด; ถ้า liquidating value **≤ 2,500 USD** โบรกอาจปิดทั้งหมด; ค่าคอม **5 USD/contract/side (1.50 USD สำหรับ micro)** — [2025 Futures World Cup Entry Agreement (PDF)](https://www.worldcupchampionships.com/wp-content/uploads/2025FuturesWorldCupEntryAgreement.pdf), §5, §7, §8
- ผลตอบแทนคิดเป็น **% เพิ่มขึ้นจาก Total Funds Deposited** และ "entrant may open more than one account… **Only the best performing account will be used for ranking**" — same PDF §1, §9 ⇒ มี selection bias ในตัวกติกาเอง
- เจ้าภาพเตือนเองว่า "WCC competitors may control accounts that produce results substantially different than the results achieved in their WCC accounts" — [worldcupchampionships.com](https://www.worldcupchampionships.com/)
- Margin วันที่ใช้จริงในคอนเทสต์: **Micro E-mini S&P 50 USD, Micro Nasdaq 200 USD, E-mini S&P 990 USD, E-mini Nasdaq 1,250 USD** — [worldcupchampionships.com](https://www.worldcupchampionships.com/) (ตาราง day-trading margins) ⇒ บัญชี 500 USD เทรด MES ได้ 1–10 สัญญา micro
- ผลรายไตรมาส (Futures Day Trading, 3 เดือน/รอบ) — [historical standings](https://www.worldcupchampionships.com/world-cup-trading-championship-historical-standings):
  - 2026 Q2: **1) David Trullas Vila +2,222.6%**, 2) +258.1%, 3) +101.5%, 4) +9.9%
  - 2026 Q1: 1) Trullas +585.4%, 2) +148.1%, 3) +141.3%
  - 2025 Q4: 1) Trullas **+930.7%**, 2) +80.4%, 3) +79.8%
  - 2025 Q3: 1) Trullas **+800.6%**, 2) +109.4%
  - 2025 Q2: 1) Trullas **+712.1%**, 2) +56.6%
- แปลงเป็นต่อเดือน (คำนวณจากตัวเลขข้างบน, ทบต้นเชิงเส้น 30/91 วัน): 585.4%→**~1.90x/เดือน**, 712.1%→**2.01x**, 800.6%→**2.08x**, 930.7%→**2.18x**, 2,222.6%→**2.85x/เดือน**
- ผู้ชนะรายปี (12 เดือน) ระดับสูงสุดในยุคหลัง: 2025 Forex 1) Pau Perdices Bellet **+600.9%**; 2024 Futures 1) Brent Carlile **+532.3%**; 2016 Futures 1) Artur Teregulov **+914.8%**; ตำนานคือ Larry Williams **+11,376% (1987)** — [historical standings](https://www.worldcupchampionships.com/world-cup-trading-championship-historical-standings)
- ผู้ชนะซ้ำมีจริงแต่หายาก: Andrea Unger ชนะ World Cup 2008 (671.9%), 2009 (115.4%), 2010 (239.6%); Chuck Hughes ชนะหลายครั้งช่วง 1995–2015; Michael Cook ชนะ 2004/2007 — same source
- **ไม่มี**จำนวนผู้เข้าที่เปิดเผย: หน้า standings/historical มีแค่ top-5 ต่อรุ่น ไม่มี field size, ไม่มี drawdown, ไม่มีขนาดบัญชีผู้ชนะ — same source (ตรวจแล้วทั้ง 2 หน้า)
- ข้อมูลในหน้า historical มีความไม่สอดคล้อง: 2025 Q1 Futures ระบุ "1st 31.75%" แต่ "3rd 169.70%" — same source ⇒ ตัวเลขบางแถวอาจสลับ/ผิดพลาด ต้องอ้างอย่างระวัง
- ข้อสังเกตภายนอก (secondary): คอนเทสต์รายไตรมาสมี cap "1 mini หรือ 10 micro ต่อ position" และเปิด leverage สูงถึง 200:1 ในบางรุ่น — [trading-tournaments.com/wctc](https://trading-tournaments.com/tournaments/championships/wctc) (ระบุ ณ 2026; หน้าเว็บตอบ 429 ตอนดึงข้อมูล 24 พ.ย. 2026 จึงอ้างได้แค่ snippet) ⇒ **ยังไม่ยืนยัน cap นี้จากเอกสารเจ้าภาพ**

**B. Bybit WSOT — real money, exchange-verified, เปิด denominator ใหญ่ที่สุด**

- WSOT 2025: **520,451 ผู้เข้า** จากทั่วโลก, 1,474 squads, Guinness record 71,765 คนสมัครใน 24 ชม. — [PR Newswire ประกาศ WSOT 2026](https://www.prnewswire.com/news-releases/wsot-2026-is-live-registration-opens-for-bybits-world-series-of-trading-with-a-prize-pool-of-up-to-10-million-usdt-across-crypto-stocks-and-ai-302923861.html); WSOT 2022 มี **69,000+ ผู้เข้า จาก 182 ประเทศ** — [Bybit learn](https://www.bybit.com/en/learn/read-to-earn/bybit-wsot-2026)
- แชมป์ WSOT 2025: **Silvan Abicht +37.13% ใน 3 เดือน, max drawdown 3.25%** (Net Profit / Max Drawdown / Calmar 1.62 เผยแพร่บนหน้า fame) — [wsot.com/fame](https://www.wsot.com/fame)
- 2026 (ระหว่างแข่ง, ต.ค.–พ.ย. 2026) ผู้นำอยู่ที่ **+63.10%** เท่านั้น (อันดับ 2 +17.91%, 3 +12.17%, 4 +4.75%) — [wsot.com/fame](https://www.wsot.com/fame)
- ข้อควรระวัง: WSOT จัดอันดับด้วยคะแนนที่ถ่วงความเสี่ยง (มี "Risk Control Bracelet", Calmar) ⇒ ตัวเลข +37.13% อาจไม่ใช่ ROI ดิบสูงสุดในสนาม แต่เป็นของผู้ที่ชนะตามกติกา — [wsot.com/fame](https://www.wsot.com/fame); [wsot.com](https://www.wsot.com/)

**C. คอนเทสต์อื่นที่มีLeaderboard สาธารณะ (ผลตอบแทนระยะสั้นระดับ 100–500%)**

- รวมผลคอนเทสต์หลายเจ้าภาพ (broker/exchange) เดือน ต.ค. 2026: ผู้ชนะรายเดือน +130.6% ถึง +228.14%; มีบัญชีเล็ก $160 → +181%, $450 → +116%, $140 → +123% — [trading-tournaments.com/results](https://trading-tournaments.com/results) (aggregator, ไม่ใช่ primary; ตัวเลขมาจากหน้าผลของแต่ละเจ้าภาพ)
- Bloomberg Global Trading Challenge (มหาวิทยาลัย, พอร์ตจำลอง ~1M USD): ผล absolute ของทีมอันดับต้นๆ ระดับ +$70k (+7%) — [Bloomberg for Education leaderboard](https://portal.bloombergforeducation.com/trading_challenges/8/leaderboard) ⇒ คอนเทสต์สายการศึกษาให้ผลระดับ single-digit % ไม่ใช่หลายเท่า

**D. ตารางเทียบความโปร่งใส (สรุปจากแหล่งข้างบน)**

| เจ้าภาพ | real money? | ขนาดบัญชีผู้ชนะ | ผลตอบแทน | Max DD | Leverage | จำนวนผู้เข้า |
|---|---|---|---|---|---|---|
| Robbins WCTC | ใช่ (broker-verified) | ไม่เปิด | เปิด (top-5) | ไม่เปิด | ตามกติกาโบรก (micro margin $50) | ไม่เปิด |
| Bybit WSOT | ใช่ (exchange) | ไม่เปิด | เปิด | เปิด (ผู้ชนะ 3.25%) | ตาม產品 | เปิด (520,451) |
| FTMO | ไม่ (simulated, จ่ายจริง) | ไม่เปิด | ไม่เปิด | กติกา 10%/5% | ~1:100 FX | ไม่เปิด (4.5M customers) |
| Topstep | ไม่ (combine→live) | ไม่เปิด | ไม่เปิด | กติกา | futures margin | เปิดเชิงอัตรา (16.8%) |

### Inferences
- ตัวเลข "+2,222% ใน 3 เดือน" ของ Robbins คือ **ปลายสุดของ tail** ในสนามที่แทบไม่จำกัด drawdown, ให้ผลซ้ำได้ในระดับ ~2x/เดือนติดกัน 5 ไตรมาส โดยคนๆ เดียว — นี่คือหลักฐานว่า "วิธีการเดิม" ทำได้จริงในเชิงกลไก แต่ยังไม่ใช่หลักฐานว่าคนทั่วไปทำได้ เพราะไม่มี field size และไม่มี drawdown
- ถ้าคนๆ เดียวทำ 2x/เดือนได้ 5 ควอเตอร์ติด แปลว่ากลไกไม่ใช่ "โชคครั้งเดียว" แต่เป็น **การรับความเสี่ยงระดับ ruin อย่างเป็นระบบ** ซึ่งผลลัพธ์ที่เห็นถูก filter ด้วยการที่เจ้าภาพ publich แค่ top-5 (คนที่ blew up ไม่ปรากฏ)
- WSOT คือ counter-example ที่สำคัญ: สนามใหญ่ที่สุด (5.2 แสนคน) ผู้ชนะได้ 37% ใน 3 เดือน เพราะกติกาบังคับ risk-adjusted score ⇒ เมื่อใส่ risk control เข้าไป ผลตอบแทน "หลายเท่า" หายทันที
- การที่ Robbins อนุญาตหลายบัญชีและนับเฉพาะบัญชีที่ดีที่สุด = multiple comparisons ต่อคน ⇒ อัตรา "ผู้ชนะ" พองเกินจริงเมื่อเทียบกับจำนวนคน

### Gaps
- ไม่พบจำนวนผู้เข้า Robbins Cup ต่อรุ่นจากแหล่งปฐมภูมิ (หน้าเว็บมีแค่ top-5) — ต้องใช้เป็นข้อจำกัดของงานเขียน ห้ามเดา denominator
- ไม่พบ drawdown/ขนาดบัญชีจริงของผู้ชนะ Robbins แม้แต่รายเดียว
- ไม่ยืนยันได้ว่า cap "1 mini/10 micro" ของรุ่น Day Trading เป็นกฎปัจจุบัน (เจอแค่ snippet + หน้าเว็บ 429)
- ไม่พบผลการแข่งขัน forex รายเดือนของโบรกไทย/เอเชียที่มีการเปิด statement ต่อสาธารณะ

---

## 2) Prop-firm challenge: pass rate, payout, สาเหตุที่ fail, ความเสี่ยงของคนที่ผ่าน, กี่คนทำซ้ำ

### Takeaway
ข้อมูลอุตสาหกรรมชี้ตรงกันว่า **ผ่าน challenge ~14% และได้ payout จริง ~7% ของคนซื้อ** (บางบริษัทแย่ถึง 1–3.7%) โดยคนที่ผ่านใช้ความเสี่ยงต่อไม้พอๆ กับกติกา (0.5–1%) ไม่ใช่ all-in และคนที่ได้ payout ซ้ำๆ เป็นชนกลุ่มน้อยมาก (top trader ของ FTMO มี 138 payouts จากลูกค้า 4.5 ล้านคน)

### Cited Findings
- **FPFX Tech / Finance Magnates (18 ก.ย. 2024)**: 300,000+ บัญชี, 100,000 เทรดเดอร์, 10 บริษัท — **14% ผ่าน challenge → ได้ funded**, ในกลุ่มนั้น **~45% ได้ payout อย่างน้อย 1 ครั้ง = 7% ของทั้งหมด**, payout เฉลี่ย **4% ของขนาด plan**, ต้นทุนเฉลี่ย **800 USD ต่อบัญชีตลอดวงจร (ประมาณ 3 challenges)**, เฉลี่ยใช้ **2.2 บริษัท** — [Finance Magnates](https://www.financemagnates.com/forex/analysis/exclusive-only-7-of-300000-prop-trading-accounts-achieved-payouts/)
- **Topstep (ข้อมูลบริษัทเอง, ปี 2025)**: **16.8%** ของ Trading Combine ที่เริ่มถูกผ่าน; **51.8%** ของคนที่ลองอย่างน้อย 1 ครั้ง ไปถึง Funded อย่างน้อย 1 ครั้ง; **33.3%** ของคนที่อยู่ระดับ Funded ได้ payout; **0.71%** ของ Express Funded ถูกเรียกขึ้น Live — [topstep.com/our-program](https://www.topstep.com/our-program)
- Topstep เวอร์ชัน 2024 (Business Insider): **12.4% funded, 28.3% ของ funded ได้รับ payout** — อ้างใน [The Prop Firm Guide](https://thepropfirmguide.com/prop-firm-statistics/)
- **The Funded Trader**: ผ่าน challenge แรก ~5%, ได้ payout ~20% ของคนที่ funded ⇒ **~1% ของลูกค้าทั้งหมด** — [Finance Magnates](https://www.financemagnates.com/forex/only-1-in-20-traders-pass-prop-firm-challenges-reports-the-funded-trader/)
- **Goat Funded Trader (ต.ค. 2026)**: ผู้ซื้อ 594,997 ราย → funded 28,859 (≈4.8%) → ได้รับเงิน 22,279 ราย (**≈3.7% ของผู้ซื้อ**) — [The Prop Firm Guide](https://thepropfirmguide.com/prop-firm-statistics/) อ้าง Finance Magnates
- **Futures evaluations (ตัวเลขบริษัทเอง)**: Earn2Trade **8.89%** (2025), Take Profit Trader **16.86%** (2024, ลดจาก 2023 ราว 3.5 จุด), TradeDay **28.2%** — [Fortunly statistics](https://fortunly.com/statistics/prop-firm-challenge-pass-rate-statistics/) (secondary aggregation)
- **FTMO**: **4.5M+ customers, >$650M จ่ายออก** สะสม; ไม่เปิด pass rate — [ftmo.com](https://ftmo.com/en/blog/we-pay-millions-in-payouts-to-our-ftmo-traders/) และ footer หน้าเดียวกัน; ตัวเลข payout: 2020 เฉลี่ย **851,044 USD/เดือน**, 2023 **5.78M USD/เดือน**, ม.ค. 2024 **9.64M USD**, ทั้งปี 2023 **75.17M USD**; เฉลี่ยต่อครั้ง **4,685 USD (2021)**; **2,753 payouts ใน ม.ค. 2024**; เทรดเดอร์ที่สม่ำเสมอที่สุดทำ **138 payouts**
- **การทำซ้ำ**: ข้อมูล ~10,000 เทรดเดอร์พบอัตรา funded **20.3% (one-step) vs 11.8% (two-step)**, ซื้อเฉลี่ย **1.6 challenges/คน** และคนที่สำเร็จซื้อซ้ำมากถึง **18 ครั้ง** — [Finance Magnates](https://www.financemagnates.com/forex/analysis/80-still-fail-in-prop-trading-globally-however-south-american-traders-aim-to-reverse-the-trend/) (อ้างผ่าน [Atmos Funded](https://atmosfunded.com/prop-firm-statistics/))
- **สาเหตุ fail ที่เปิดเผยได้**: กติกามาตรฐานคือ daily loss 3–5% และ total drawdown 6–10% (สองค่าที่ทำให้คนส่วนใหญ่ตาย) — [Atmos Funded](https://atmosfunded.com/prop-firm-statistics/); FTMO 2-step: target 10%, daily 5%, max 10% static — [traderssecondbrain](https://traderssecondbrain.com/guides/prop-firm-pass-rate)
- **แบบจำลองความเสี่ยงของคนที่ผ่าน** (simulation, ไม่ใช่ข้อมูลบริษัท): โปรไฟล์ "developing" (win 45%, 1.4R, 4 ไม้/วัน, risk 1%/ไม้) ผ่าน **45.8%** ต่อ attempt แต่ **93.3%** ของ funded account จะ breach กติกาใน 90 วัน; โปรไฟล์ "consistent" (48%, 1.6R, 0.75%/ไม้) ผ่าน **94.9%** — [LuxAlgo FTMO pass-rate model](https://www.luxalgo.com/prop-firms/ftmo/pass-rate/) (ระบุชัดว่าเป็น simulation + stated assumptions)
- **ความน่าเชื่อถือของอุตสาหกรรม**: 80–100 prop firms ปิดตัวในปี 2024; The Funded Trader ค้างจ่าย 900 คน; "none are independently audited" — [Finance Magnates](https://www.financemagnates.com/forex/exclusive-80-100-prop-firms-wiped-out-in-2024s-industry-collapse/), [The Prop Firm Guide](https://thepropfirmguide.com/prop-firm-statistics/)

### Inferences
- ตัวเลข "7%" และ "14%" มาจาก vendor เดียว (FPFX) และถูก cite วนซ้ำทั้งอุตสาหกรรม ⇒ ควรเขียนว่า "ตัวเลขที่ถูกอ้างมากที่สุด" ไม่ใช่ "ข้อเท็จจริงที่ตรวจสอบแล้ว"
- ส่วนต่าง 5% (TFT) กับ 28.2% (TradeDay) มาจาก **โครงสร้างกติกา** ไม่ใช่คุณภาพคน ⇒ การเอา pass rate ข้ามบริษัทมาเทียบกันตรงๆ ไม่ valid
- ถ้า payout เฉลี่ย = 4% ของ plan size และค่าสมัคร ≈ 100 USD ต่อ 10k plan ⇒ ผู้ได้ payout เฉลี่ย "กำไร" ไม่มากเมื่อหักค่าสมัครซ้ำ (800 USD/วงจร) ⇒ แม้แต่คนกลุ่ม 7% ก็ยังไม่แน่ว่ามี EV บวก
- "risk 0.5–1% ต่อไม้" เป็นเงื่อนไขเชิงคณิตศาสตร์ของการผ่านกติกา 10%/5% ไม่ใช่คำแนะนำเชิงกลยุทธ์: ถ้า risk 5%/ไม้ หาย 2 ไม้ติด = fail ทันที
- อัตราการทำซ้ำต่ำมาก (138 payouts จาก 4.5M customers ≈ 0.003%) ⇒ การได้ payout ครั้งเดียวไม่ใช่หลักฐานของ edge

### Gaps
- ไม่พบบริษัทใดเปิด **ผลตอบแทนจริงและ drawdown ของผู้ที่ได้ payout** (เปิดแค่ยอดเงิน)
- ไม่พบสถิติ "กี่ % ของคนที่ได้ payout แล้วได้ซ้ำภายใน 6–12 เดือน" จากบริษัทใด (มีแค่ anecdote 138 payouts)
- ตัวเลข leverage ที่ผู้ชนะใช้จริงไม่มีการเปิดเผยที่ใด — ต้องอนุมานจากกติกาเท่านั้น
- ข้อมูล Earnings/Apex/Topstep บางส่วนเป็น secondary (Fortunly, Prop Firm Guide) ไม่ใช่หน้าเว็บบริษัท

---

## 3) "Small account challenge": อะไรตรวจสอบได้จริง, วิธีที่ใช้, เกิดอะไรหลังจากนั้น

### Takeaway
เคสที่ตรวจสอบได้จริงและมีหลักฐานเชิงสถาบันมีเพียงไม่กี่เคส และ **เคสที่โด่งดังที่สุด ($583 → $1M) จบด้วย FTC ฟ้องและปรับ 3 ล้าน USD ฐานทำให้ "ลูกค้าส่วนใหญ่ขาดทุน"** — เคสที่รอดจริง (Grittani, Cameron ระดับหนึ่ง) ใช้เวลา **หลายปี** ไม่ใช่ 1 เดือน และเกือบทั้งหมดเป็น momentum/small-cap ไม่ใช่ 0DTE หรือ leverage สูง

### Cited Findings
- **Ross Cameron / Warrior Trading "$583 Challenge"**: อ้างว่า $583 → **$1M ใน ~2 ปี** และมี "Verified Earnings Statements" จาก accountant อิสระ — [warriortrading.com verified earnings 2026](https://www.warriortrading.com/verified-earnings-2026/), [warriortrading.com $1M challenge complete](https://www.warriortrading.com/1-million-dollar-challenge-complete-ross-trade-recap/)
- **FTC v. Warrior Trading (เม.ย. 2022)**: โฆษณาใช้เคส "$583 → $1M" และเคลม "profits … scalable"; FTC ระบุ "**the vast majority of customer accounts actually lost money**"; คำสั่งศาล: จ่าย **3 ล้าน USD** คืนผู้บริโภค และห้ามเคลมผลตอบแทนที่ไม่มีหลักฐาน; บริษัททำรายได้ "tens of millions" ช่วง 2018–2021 — [FTC press release 19 เม.ย. 2022](https://www.ftc.gov/news-events/news/press-releases/2022/04/federal-trade-commission-cracks-down-warrior-trading-misleading-consumers-false-investment-promises); [FTC case page](https://www.ftc.gov/legal-library/browse/cases-proceedings/2023198-warrior-trading-inc-ftc-v); คืนเงินผู้เสียหาย >$2.9M — [FTC refunds](https://www.ftc.gov/news-events/news/press-releases/2023/01/ftc-returns-more-29-million-consumers-harmed-warrior-trading)
- **Tim Grittani**: $1,500 → "over $13.5M" ภายใน ~10 ปี (self-reported ผ่าน Timothy Sykes; ไม่มี independent audit เผยแพร่) — [timothysykes.com case study](https://www.timothysykes.com/blog/case-study-tim-grittani/); วิธี = penny-stock momentum ไม่ใช่ leverage/options
- **James Wynn (crypto perps, on-chain ยืนยันได้)**: ~$7,000 ใน PEPE → **>$25M**; ต่อมาถูก liquidate หลายครั้ง รวม ~$100M และบัญชีเหลือ **~$900**; การวิเคราะห์ระบุ position $1.27B BTC long ขาดทุน ~$85M — [Yahoo Finance](https://finance.yahoo.com/markets/crypto/articles/james-wynn-account-drops-900-101235555.html), [Presto Research](https://www.prestolabs.io/research/how-to-lose-85mm-james-wynns-1-27b-btc-long), [TheStreet](https://www.thestreet.com/crypto/markets/james-wynn-suffers-five-liquidations-in-market-drop)
- **เคส "guru ใช้ demo"**: กระทู้ forensic ใน r/Daytrading (2026) ระบุ guru คนหนึ่งสตรีม demo แล้วอ้างว่า live; เมื่อถูกตรวจสอบก็ "failed several attempts at the small account challenge" — [Reddit r/Daytrading](https://www.reddit.com/r/Daytrading/comments/1vmfb7o/exposing_a_fake_guru_pretending_to_trade_real/)
- **เคส guru ที่ challenge จบในแดง**: นักเทรดที่เขียนบล็อกเล่าว่า guru ซึ่งหาเงินจาก membership ได้มาก "wasn't able to grow his small account challenge. It finished in the red" — [davidpnowak.com](https://davidpnowak.com/b/nearly-5-years-day-trading-brutally-honest-truth/)
- **0DTE / options**: งานวิจัยพบ **0DTE trades ขาดทุนมากกว่าทุก option trade ประมาณ 4.7% ต่อไม้** (univariate) และยัง -2.95% เมื่อคุมตัวแปร; retail ซื้อ option ขาดทุนเฉลี่ย 3.95%/ไม้ — ["An Anatomy of Retail Option Trading" (LSU/pdf)](https://www.lsu.edu/business/files/event-files/2025-finance-mardi-gras/retail_option_trading_v2.pdf); งาน Beckmeyer et al. ประเมิน retail ขาดทุน 0DTE รวม ~**$350k/วัน** หลัง daily expiry เริ่ม — [SSRN 4404704](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4404704), [FoFI pdf](https://wp.lancs.ac.uk/fofi2024/files/2024/04/FoFI-2024-146-Leander-Gayda.pdf)
- **CFD base rate (เทียบเคส forex leverage สูง)**: ESMA ระบุ **74–89% ของบัญชี retail ขาดทุน**, ขาดทุนเฉลี่ย €1,600–29,000 — [ESMA 2018](https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors); FCA: **~80% ขาดทุน** — [FCA](https://www.fca.org.uk/news/press-releases/fca-highlights-continuing-concerns-about-problem-firms-cfd-sector)

### Inferences
- ความต่างระหว่าง Cameron (รอดและขยายบัญชีได้จริง) กับ Wynn (รอดแล้วพัง) คือ **position sizing ไม่ใช่วิธีหา entry**: Cameron ใช้ momentum + share size เล็กเทียบพอร์ต, Wynn ใช้ leverage ระดับ 40x และ position ใหญ่กว่าทุนหลายเท่า
- เคสที่ "ตรวจสอบได้" มักเป็น (ก) broker/accountant-verified แต่ถูกใช้เชิงการตลาด (Cameron) หรือ (ข) on-chain verified แต่จบด้วยการล้างพอร์ต (Wynn) ⇒ การตรวจสอบหลักฐานไม่ได้แก้ปัญหา survivorship
- สกรีนช็อต statement ที่ไม่มีทั้ง account number, broker letter, และ period ต่อเนื่อง ≥12 เดือน **ไม่ควรถูกนับเป็นหลักฐาน** — เกณฑ์นี้ทำให้เคสส่วนใหญ่ใน YouTube/TikTok หลุดออกจากการวิเคราะห์
- 0DTE เป็นเครื่องมือที่ "ดูเหมือน" ตอบโจทย์บัญชี 100–500 USD (ซื้อ 1 สัญญาได้) แต่หลักฐานวิชาการบอกว่าขาดทุนเชิงระบบจาก spread + theta ⇒ วิธีนี้คือสิ่งที่คนทำ challenge เลือกเพราะ *ราคาต่อสัญญาต่ำ* ไม่ใช่เพราะมี edge

### Gaps
- ไม่พบเคส "small account challenge" ที่มี **independent audit ต่อเนื่อง 12+ เดือน** และเปิด statement ครบ (นอกจาก Cameron ซึ่งจบด้วย FTC)
- ไม่พบหลักฐานยืนยันว่า Grittani's $13.5M ผ่านการ audit อิสระ (เป็น self-reported ผ่าน Sykes)
- ไม่พบเคส 0DTE/0DTE-challenge ที่มี broker statement ตรวจสอบได้และทำกำไรต่อเนื่อง >6 เดือน
- ข้อมูล Twitter/X ส่วนใหญ่ถูกลบ/private — ไม่สามารถ archive ยืนยันได้ในรอบนี้

---

## 4) การกระจายของผลตอบแทนรายเดือน: กี่คนถึง 3x, median/worst, survivorship

### Takeaway
ไม่มีการเปิดเผย distribution เต็มรูปแบบจากคอนเทสต์ใดเลย แต่หลักฐานทางอ้อมชี้ว่า **3x/เดือนอยู่เหนือผู้ชนะ WSOT (5.2 แสนคน) ประมาณ 8 เท่า** และอยู่ใกล้/เกินสถิติสูงสุดของ Robbins Cup (2.85x/เดือน) — ของจริงคือ **median ของนักเทรดรายวันคือขาดทุน** (97% ของคนที่อดทน >300 วัน) และ worst case คือ -100%

### Cited Findings
- **Robbins 2026 Q2 top-5**: 2,222.6% / 258.1% / 101.5% / 9.9% ⇒ อันดับ 4 ห่างจากอันดับ 1 ถึง **224 เท่า** แสดง heavy tail สุดขั้ว — [historical standings](https://www.worldcupchampionships.com/world-cup-trading-championship-historical-standings)
- **WSOT 2025**: ผู้ชนะ +37.13% ทั้งสนาม 520,451 คน; 2026 ระหว่างแข่งผู้นำ +63.1% — [wsot.com/fame](https://www.wsot.com/fame), [PR Newswire](https://www.prnewswire.com/news-releases/wsot-2026-is-live-registration-opens-for-bybits-world-series-of-trading-with-a-prize-pool-of-up-to-10-million-usdt-across-crypto-stocks-and-ai-302923861.html)
- **Chague, De-Losso & Giovannetti (2020), ข้อมูล CVM บราซิล**: คนเริ่มเทรด mini-Ibovespa 2013–2015 = **19,646 คน**; ผู้ที่เทรดต่อเนื่อง **>300 วัน = 1,551 คน**; **97% ขาดทุน** (net of fees); **1.1% (17 คน)** ชนะเกินค่าแรงขั้นต่ำ; **0.5%** ชนะเกินเงินเดือน teller; ไม่พบหลักฐาน "learning by doing" — [SSRN 3423101](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101), [pdf](https://ebicapital.nl/wp-content/uploads/2022/05/day-trading.pdf)
- **Prop firm funnel**: 100% ซื้อ → 25–35% ผ่าน Phase 1 → 5–14% funded → ~7% ได้ payout → **1–3% เป็น funded trader ระยะยาว** — [Track360](https://track360.io/blog/prop-trading-industry-statistics-2026) (aggregator; ตัวเลขหลักมาจาก FPFX/Topstep)
- **ผลตอบแทนของคนที่ "ชนะ" ใน prop model**: simulation ของ LuxAlgo ชี้ว่าแม้ผ่านแล้ว **93.3% ของ funded account จะ breach กติกาภายใน 90 วัน** (โปรไฟล์ developing) — [LuxAlgo](https://www.luxalgo.com/prop-firms/ftmo/pass-rate/)
- **Retail CFD**: 74–89% ขาดทุน, ขาดทุนเฉลี่ย €1,600–29,000 — [ESMA](https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors)
- **Publication bias ในตัวคอนเทสต์**: Robbins ประกาศแค่ top-5, อนุญาตหลายบัญชี, นับเฉพาะบัญชีที่ดีที่สุด — [entry agreement §1](https://www.worldcupchampionships.com/wp-content/uploads/2025FuturesWorldCupEntryAgreement.pdf)
- **ค่าธรรมเนียมเป็นตัวกำหนดผลลัพธ์บัญชีเล็ก**: ค่าคอม Robbins 5 USD/side (1.50 micro) — same PDF §5e; เฉลี่ยคนซื้อ challenge จ่าย 800 USD ตลอดวงจร — [Finance Magnates](https://www.financemagnates.com/forex/analysis/exclusive-only-7-of-300000-prop-trading-accounts-achieved-payouts/)

### Inferences
- **แปลง 3x/เดือนเป็นความน่าจะเป็น**: ถ้าเทรดแบบ all-in ด้วย bet ที่ win 50% และได้ 1:1 ต้องชนะติดกัน 2 ครั้ง = สำเร็จ 25% แต่ ruin 75% ต่อ attempt; ถ้าทำซ้ำทุกวัน 20 วัน โอกาสรอดทั้งเดือน = 2^-20 ≈ **1 ในล้าน** ⇒ "3x/เดือน" ไม่ใช่เป้าหมายการเทรด แต่คือผลข้างเคียงของการรับ risk ที่ทำให้ ruin เป็นผลลัพธ์ปกติ
- ถ้า 520,451 คนใน WSOT ใช้ bet 50/50 all-in คนที่ชนะ 19 ครั้งติดจะได้ ~500,000x ⇒ **การมีผู้ชนะระดับหลายร้อยเท่าในสนามใหญ่เป็นเรื่องที่คาดหมายได้ทางสถิติ** โดยไม่ต้องมี skill
- Median ของประชากรนักเทรดรายวัน = ติดลบ; "median ของคนที่โพสต์ออนไลน์" = บวก เพราะคนขาดทุนไม่โพสต์ ⇒ ตัวเลขที่เราเห็นเป็น **conditional on survival + conditional on posting**
- ในสนามที่จำกัด drawdown (prop/WSOT) ผลตอบแทนสูงสุดถูกบีบลงมาที่ ~40–60% ต่อไตรมาส ⇒ "3x/เดือน" กับ "อยู่ในกติกา" เป็นสองสิ่งที่ไม่เกิดร่วมกัน
- ถ้าคนๆ เดียวทำ ~2x/เดือนได้ 5 ไตรมาส (Robbins) นั่นคือหลักฐานว่า tail ไม่ได้เกิดจากคนสุ่มล้วนๆ แต่ก็ยังสรุปไม่ได้ว่าเป็น edge ที่ถ่ายทอดได้ เพราะไม่มี drawdown และไม่มีขนาดบัญชี

### Gaps
- **ไม่มีแหล่งใดเปิด distribution รายเดือนของผู้เข้าแข่งขัน** (percentile, median, worst) — ทั้ง Robbins และ WSOT เปิดแค่ผู้ชนะ
- ไม่พบจำนวนคนที่ "ทำได้ 3x ใน 1 เดือน" จากแหล่งปฐมภูมิใดๆ
- ไม่พบสถิติ survival rate ของบัญชีเล็ก (<1,000 USD) แยกต่างหาก
- ตัวเลข 1.1%/0.5% ของ Chague เป็นตลาด futures บราซิล ไม่ใช่ forex/crypto ⇒ ใช้เป็น base rate เชิงเปรียบเทียบเท่านั้น

---

## 5) บัญชี 147 USD ต้องมีกติกาอะไรจึงจะอยู่รอดพอทดสอบ edge ได้ และความเสี่ยงแบบคอนเทสต์แบบไหนที่ irrational

### Takeaway
ที่ 147 USD ต้นทุนต่อไม้ (spread/commission) กิน risk budget 1% ทั้งก้อนในเกือบทุก instrument ที่มี leverage ⇒ บัญชีนี้ **ทดสอบ edge ไม่ได้ทางคณิตศาสตร์** ไม่ว่าจะเลือกวิธีไหน สิ่งที่ทำได้คือ (ก) ใช้เป็น live-fire ขนาดจิ๋วเพื่อฝึกวินัย, (ข) เติมเงินถึง ~1,000–2,000 USD ก่อนคาดหวังสัญญาณทางสถิติ, หรือ (ค) paper trade — ส่วนการไล่ 3x/เดือนด้วยบัญชีนี้คือการเดิมพันที่ EV ติดลบและ ruin probability ≈ 1

### Cited Findings
- ขนาดขั้นต่ำของ instrument ที่เกี่ยวข้อง: **Micro E-mini S&P day margin 50 USD** (1 สัญญา = 34% ของบัญชี 147 USD) — [worldcupchampionships.com margin table](https://www.worldcupchampionships.com/); MES multiplier **$5/point, tick 0.25 = $1.25** — [CME Micro E-mini S&P 500 spec](https://www.cmegroup.com/markets/equities/sp/micro-e-mini-s-and-p-500.html)
- ค่าคอมในคอนเทสต์ futures: **1.50 USD/side สำหรับ micro** (เช่น MES) ⇒ 3 USD round-turn = **2.0% ของบัญชี 147 USD** — [entry agreement §5e](https://www.worldcupchampionships.com/wp-content/uploads/2025FuturesWorldCupEntryAgreement.pdf)
- Micro lot forex (0.01 lot EURUSD) = **$0.10/pip** ⇒ 1% risk ($1.47) = stop 14.7 pips — คำนวณจาก contract spec มาตรฐาน (10,000 units)
- กติกา PDT สหรัฐ: บัญชี margin <25,000 USD เทรด day trade ได้ไม่เกิน 3 ครั้งใน 5 วันทำการ — [FINRA Rule 4210](https://www.finra.org/rules-guidance/rulebooks/finra-rules/4210)
- ค่า spread/ค่าธรรมเนียมเป็นสาเหตุหลักที่ retail ขาดทุน: 0DTE retail ขาดทุน ~$350k/วัน ส่วนใหญ่จาก bid-ask — [Beckmeyer et al.](https://wp.lancs.ac.uk/fofi2024/files/2024/04/FoFI-2024-146-Leander-Gayda.pdf)
- ข้อจำกัดสินเชื่อ/ค่าธรรมเนียมของ prop firm บังคับ risk ต่อไม้ให้ ≤1% โดยพฤตินัย (daily 5%, max 10%) — [FTMO objectives](https://ftmo.com/en/trading-objectives/)

### Inferences (คำนวณ)
สมมติ risk 1% = **1.47 USD/ไม้**:

| Instrument | ขนาดไม้เล็กสุด | risk 1% แปลว่า | ต้นทุน round-trip | ต้นทุน/risk |
|---|---|---|---|---|
| MES futures | 1 สัญญา | stop 0.29 point (~1 tick) | $1.25 spread + $3.00 คอม | **289%** |
| EURUSD micro | 0.01 lot | stop 14.7 pips | ~$0.10–0.20 spread | 7–14% |
| Crypto perp | notional ~$70 (2% stop) | stop 2% | ~0.05–0.1% notional | 2–5% |
| SPY 0DTE | 1 สัญญา (เบี้ย ~$20–40) | 1 สัญญา = 14–27% ของบัญชี | spread + theta | **>1000%** |

- MES ใช้ไม่ได้ที่ 147 USD: 1 tick ของ spread = 0.85% ของบัญชี และ stop ที่แคบกว่า 1 tick เป็นไปไม่ได้ ⇒ ต้อง risk 8–10%/ไม้ขั้นต่ำ (stop 10 ticks = $12.50 = 8.5%) ⇒ **หาย 2 ไม้ติด = -17%, 6 ไม้ = -50%**
- 0DTE ใช้ไม่ได้: 1 สัญญาราคา 20–40 USD = 14–27% ของบัญชี ⇒ ต้องถูก 4 ครั้งติดแค่จะไม่ขาดทุน และ 3 พลาด = -60% ขึ้นไป
- ทางเดียวที่ risk 1% ยังมีความหมายคือ **micro FX หรือ crypto notional เล็ก** แต่ edge ต่อไม้จะอยู่ระดับ 0.1–0.2R = 0.15–0.30 USD/ไม้ ⇒ ต้องเทรด **~200–900 ไม้** จึงจะแยก edge ออกจาก noise ที่ 95% (N ≈ (1.96·σ/edge)², σ≈1.5R: edge 0.2R → ~216 ไม้, edge 0.1R → ~864 ไม้)
- ที่ 5 ไม้/วัน, 216 ไม้ = ~6 สัปดาห์ แต่บัญชี 147 USD ที่ risk 1% จะโตได้เพียง ~30–40% ในช่วงนั้น (0.2R × 1% × 216 ≈ 43% ของทุน) ⇒ **ยังไม่พอเป็นหลักฐานและยังไม่พอเป็นรายได้**
- กติกาที่ทำให้ "อยู่รอดพอทดสอบได้" (ข้อเสนอเชิงปฏิบัติ):
  1. risk ตายตัว ≤1% ($1.47) และ **บังคับว่า spread+คอม ≤10% ของ risk** ⇒ ตัด MES และ 0DTE ออกโดยอัตโนมัติ
  2. daily stop -3% ($4.41), weekly -6%, max DD -10% ⇒ หยุดทันทีเมื่อถึง
  3. ห้ามเติมเงินระหว่างทดสอบ (ไม่งั้น R-multiple เพี้ยน) — บันทึกเป็น R ไม่ใช่ USD
  4. เป้าไม่ใช่กำไร แต่คือ **จำนวนไม้ที่มากพอเชิงสถิติ** (≥200) และการรอดถึง 200 ไม้
  5. ถ้าต้องการทดสอบ edge จริง ให้ paper/backtest 200–500 ไม้ก่อน แล้วใช้ 147 USD เป็น "ค่าธรรมเนียมการเรียน" ≤0.25%/ไม้
- ความเสี่ยงแบบคอนเทสต์ที่ **irrational** สำหรับ 147 USD:
  - all-in ต่อไม้เพื่อหวัง 3x/เดือน (ruin 75% ต่อ attempt; รอด 20 วัน ≈ 1e-6)
  - martingale/เพิ่มขนาดหลังขาดทุน (บัญชี 147 รองรับการเพิ่มได้ 1–2 ขั้นเท่านั้น)
  - 0DTE เพราะ "ซื้อได้ 1 สัญญา" (ต้นทุนต่อไม้ 20–30% ของบัญชี)
  - perps leverage >10x ( liquidation ที่ -10% ของ notional = -100% ของ risk unit)
  - เทรดเพื่อ "ให้ทัน" คอนเทสต์/ความคาดหวังรายเดือน — เป็นการเปลี่ยน risk จาก edge-driven เป็น target-driven ซึ่งเพิ่ม ruin probability โดยไม่เพิ่ม expectancy

### Gaps
- ไม่พบเอกสารราชการ/วิชาการที่กำหนด "ขั้นต่ำของทุนเพื่อทดสอบ edge ได้" — ตัวเลข 1,000–2,000 USD เป็นการคำนวณจากต้นทุนต่อไม้ ไม่ใช่มาตรฐานที่อ้างอิงได้
- ราคา spread จริงแยกตามโบรก/เวลา (EURUSD, crypto perp) ไม่ได้รวบรวมในรอบนี้ — ตัวเลขในตารางเป็นค่าประมาณช่วงกว้าง
- ยังไม่มีข้อมูลค่า funding rate ของ perps ในช่วงทดสอบ ซึ่งอาจเปลี่ยนต้นทุนต่อไม้อย่างมีนัยสำคัญ

---

### หมายเหตุระเบียบวิธี (สำหรับผู้อ่านที่ต้องการตรวจสอบ)
- ใช้เฉพาะแหล่งที่เปิดสาธารณะ; วันที่ของตัวเลขคือวันที่หน้าเว็บแสดง ไม่ใช่วันที่เหตุการณ์
- ตัวเลขที่ผมคำนวณเอง (monthly compounding, N-trade, ตารางต้นทุน) ระบุว่า "คำนวณ" หรือ "Inferences" ทุกจุด — ห้ามนำไปอ้างเป็นตัวเลขจากแหล่ง
- ตัวเลขที่ aggregator (Track360, Fortunly, Prop Firm Guide, trading-tournaments) รวบรวม ถูกทำเครื่องหมายว่า secondary เพราะต้นทางคือบริษัท/สื่อที่ไม่เปิด dataset
- ไม่มีแหล่งใดในรอบนี้ให้ **distribution เต็ม** ของผู้เข้าแข่งขัน ⇒ ข้อสรุปเรื่อง "กี่คนถึง 3x" ต้องเขียนเป็นช่วง/เชิงเปรียบเทียบ ไม่ใช่ตัวเลขเดี่ยว
