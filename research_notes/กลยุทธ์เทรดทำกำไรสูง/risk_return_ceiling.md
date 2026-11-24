# เพดานผลตอบแทน ขนาดโพซิชัน และความเสี่ยงล้มละลาย ของบัญชีเทรดขนาดเล็ก ($147) — หลักฐานถึง พ.ย. 2026

บันทึกงานวิจัยสำหรับ report writer. ทุกตัวเลขที่มี URL คือข้อเท็จจริงจากแหล่ง; ตัวเลขที่กำกับว่า **[คำนวณเอง]** มาจากสคริปต์จำลองที่แสดงสมมติฐานไว้ในหัวข้อ Q5 (`/tmp/opencode/sim_risk.py`, `sim_lev2.py`) ไม่ใช่ข้อเท็จจริงจากงานตีพิมพ์ และต้องรายงานว่าเป็นการจำลอง

สมมติฐานร่วมของทั้งฉบับ: บัญชี $147, ไม่มีเงินเติม, นายหน้า/ตลาดที่ต้นทุนสมจริง (spread + ค่าธรรมเนียม + funding), 1 เดือน = 21 วันทำการ, ระยะเวลาเก็บข้อมูล 2020–2026 เป็นหลัก + ทฤษฎีรากฐาน. ไม่มีการเทรดจริง

---

## Q1. งานศึกษาเรื่องเทรดรายย่อย/forex/crypto/บัญชีเลเวอเรจสูง: สัดส่วนที่กำไรหลังหักต้นทุน (พร้อมขนาดตัวอย่างและช่วงเวลา)

### Takeaway
ทุกงานศึกษาที่ใช้ข้อมูลทั้งประชากร (ไม่ใช่กลุ่มตัวอย่างสมัครใจ) ให้ผลเดียวกัน: **ผู้ที่กำไรสุทธิหลังต้นทุนต่อเนื่องมีสัดส่วน 1–5% และยิ่งเทรดนานสัดส่วนยิ่งลดลง** ไม่มีงานศึกษาใดที่พบว่ากลุ่มรายย่อยส่วนใหญ่ทำกำไรได้ และตัวเลข "90% ขาดทุน" ที่ circulate กันนั้นจริง ๆ แล้ว *ต่ำกว่าความจริง* ในตลาด day trade แต่ *สูงเกินไป* สำหรับบัญชี CFD ทั้งหมด (ล่าสุดmedian ~72–74%)

### Cited Findings
- Taiwan Stock Exchange, day traders ทั้งหมด ปี 1992–2006, ~450,000 คน/ปี: **น้อยกว่า 1%** สามารถทำ abnormal return บวกสุทธิค่าธรรมเนียมได้อย่างคาดการณ์ได้ในปีถัดไป; top 500 คนได้ +37.9 bps/วัน (สมมติ commission 5 bps) หรือ +24.1 bps/วัน (14.25 bps) หลังหักต้นทุน; กลุ่มแย่สุดได้ −28.9 bps/วัน — [Barber, Lee, Liu & Odean, Journal of Financial Markets 18 (2014)](https://www.sciencedirect.com/science/article/pii/S1386418113000190)
- Taiwan 1992–2006, 3.7 พันล้านรายการซื้อขาย: day trader ขาดทุนเฉลี่ย **−7 bps/วันก่อนต้นทุน, −23.9 bps/วันหลังต้นทุน**; ผลรวมติดลบใน 14 จาก 15 ปี; **อัตราการอยู่รอด 44% (1 ปี), 24% (2 ปี), 15% (3 ปี)**; มีเพียง ~5% ของเทรดเดอร์ที่ active มี cumulative net return เป็นบวก ณ เวลาใดเวลาหนึ่ง; "97% of day traders are likely to lose money in future day trading" — [Barber, Lee, Liu, Odean & Zhang, Review of Asset Pricing Studies 10(1) (2020)](https://academic.oup.com/raps/article-abstract/10/1/61/5545095); ตัวเลข 23.9 bps/วัน และ survival rates: [สรุปงานวิจัย](https://www.tradicted.com/research/barber-learning-2020/)
- Taiwan 1995–1999, >130,000 นักลงทุนที่ day trade ≥ NT$1.5M ต่อ 6 เดือน: **มากกว่า 8 ใน 10 ขาดทุน** ในช่วง 6 เดือนทั่วไป; heavy day traders มีกำไรขั้นต้น NT$36.4M/วัน แต่ขาดทุนสุทธิ NT$68.9M/วัน; มีเพียง 19% ของกลุ่ม active ที่สุดที่กำไรสุทธิ — [Barber et al. 2004 (PDF, Odean)](https://faculty.haas.berkeley.edu/odean/papers/day%20traders/Day%20Trade%20040330.pdf)
- Brazil mini-Ibovespa futures: **19,646 คน** ที่เริ่ม day trade ปี 2013–2015, ติดตามทั้งประชากร; ในกลุ่มที่ยังเทรดต่อ **>300 วัน (1,551 คน) — 97% ขาดทุน**, มีเพียง **1.1%** ที่ได้มากกว่าค่าแรงขั้นต่ำ, **0.5%** ที่ได้มากกว่าเงินเดือนพนักงานธนาคาร (~US$54/วัน); คนที่เก่งที่สุดได้ **US$310/วัน โดยมี SD รายวัน US$2,560** (ผันผวนกว่า 8 เท่าของกำไร) — ไม่พบหลักฐานการเรียนรู้เมื่อเทรดนานขึ้น — [Chague, De-Losso & Giovannetti, "Day Trading for a Living?", FGV EESP TD 525 (ก.พ. 2020)](https://repositorio.fgv.br/server/api/core/bitstreams/0f00dd78-6909-4f91-84d5-aef8803e6436/content); [SSRN 3423101](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101)
- **สัดส่วนคนกำไรลดลงแบบ monotonic ตามจำนวนวันที่เทรด**: 1 วัน 29.8% → 2–50 วัน 15.5% → 51–100 วัน 8.9% → 101–200 วัน 6.8% → 201–300 วัน 5.4% → >300 วัน **3.0%** (เทียบกับรูเล็ตคาสิโน) — [Chague et al. 2020, ตารางในบทความ](https://repositorio.fgv.br/server/api/core/bitstreams/0f00dd78-6909-4f91-84d5-aef8803e6436/content)
- Brazil หุ้น (ไม่ใช่ futures): **98,378 คน** เริ่ม day trade หุ้น 2013–2016; เทรดทั้งหมด 2013–2018 พบเพียง **127 คน** ที่มีกำไรขั้นต้นเฉลี่ย/วัน > R$100 ติดต่อกัน >300 วัน (ตัวเลข *ก่อน* หักภาษี/แพลตฟอร์ม/คอร์ส) — [Chague & Giovannetti, Brazilian Review of Finance 18(3) (2020)](https://periodicos.fgv.br/rbfin/article/view/81949)
- EU/ESMA 2018: **74–89% ของบัญชี CFD รายย่อยขาดทุน**, ขาดทุนเฉลี่ยต่อลูกค้า **€1,600–€29,000** — [ESMA press release 27 มี.ค. 2018](https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors)
- ที่มาของช่วง 74–89%: CySEC วิเคราะห์ **~290,000 บัญชี ที่ 18 ผู้ให้บริการ CFD, 1 ม.ค.–31 ส.ค. 2017 → เฉลี่ย 76% ขาดทุน (24% กำไร)**; CNMV สเปน ~82% ขาดทุนในช่วง 21 เดือน (2015–2016); AMF ฝรั่งเศส **>89%** ใน 4 ปี (2009–2013) — [Central Bank of Ireland อ้างอิง ESMA, สรุปใน Trading Business Review ต.ค. 2026](https://tradingbusinessreview.com/market-intelligence/broker-loss-disclosures-compared)
- ข้อมูล disclosure รายไตรมาสล่าสุด (ต้องเปิดเผยตามกฎ EU/UK, คำนวณจาก 12 เดือนย้อนหลัง รวม unrealized P&L และต้นทุนทั้งหมด): ค่ามัธยฐาน **73.5% ของ 62 นิติบุคคล (ช่วง 54.4%–84%)** ณ 16 พ.ย. 2026 — [rulesbeforeresults](https://rulesbeforeresults.app/en/what-percentage-of-traders-lose-money); อีกทะเบียนหนึ่งค่ามัธยฐาน **72.0% (35 บริษัท, Q3 2026)** — [riskwarnings.com](https://riskwarnings.com/); 9 บริษัท UK/EU ที่อ่านเว็บเอง 7 ต.ค. 2026 อยู่ที่ **60%–77%** — [Trading Business Review](https://tradingbusinessreview.com/market-intelligence/broker-loss-disclosures-compared)
- โปแลนด์ (KNF) ปี 2025: **72.2% ของ 266,818 ลูกค้าที่ active ขาดทุน**, รวม **PLN 2.68 พันล้าน** — [rulesbeforeresults อ้าง KNF](https://rulesbeforeresults.app/en/what-percentage-of-traders-lose-money)
- ออสเตรเลีย ASIC Report 828 (20 ม.ค. 2026): ปีงบ 2023–24 มี **133,674 จาก 195,386 ลูกค้า CFD รายย่อย (68%) ขาดทุนสุทธิหลังค่าธรรมเนียม** รวม A$458 ล้าน (ในนั้น A$73 ล้านเป็นค่าธรรมเนียม); ผลิตภัณฑ์ CFDs over options ขาดทุน **85%** — [สรุปโดย Markitel อ้าง ASIC Report 828](https://markitel.com/blog/retail-loss-disclosures) *(หมายเหตุ: เป็นแหล่งทุติยภูมิที่อ้างรายงาน ASIC; ควรอ้างว่า "ASIC Report 828 ตามที่รายงานโดย…")*
- สหรัฐ forex (NFA/CFTC Reg. 5.5(e) — ต้องเปิดเผย % บัญชีกำไร/ขาดทุนทุกไตรมาส): FOREX.com ไตรมาส 2/2026 มี **34,791 บัญชี active, 32.56% กำไร / 67.44% ขาดทุน**; Q1/2026 30.91%; Q4/2025 31.72%; Q3/2025 34.25% — [FOREX.com risk disclosure](https://www.forex.com/en-us/terms-and-policies/risk-disclosure/); CFTC ระบุว่า disclosure ของ Schwab, FOREX.com, Tastyfx, IB, OANDA, Trading.com ใน 4 ไตรมาสล่าสุดอยู่ที่ **50.96%–74% ของบัญชี forex รายย่อยขาดทุน** — [CFTC Customer Advisory 9025-24, 18 ธ.ค. 2024](https://www.cftc.gov/PressRoom/PressReleases/9025-24)
- CFTC retail futures (ข้อมูล regulatory, 36,538 เทรดเดอร์, 50 ตลาด, ก.พ. 2021–พ.ย. 2022): เทรดเดอร์ทั่วไปมี **median 4 trading events, ถือ 4 วันต่อครั้ง**, กำไร/ขาดทุนระดับ "ไม่กี่ร้อยดอลลาร์ต่อ event"; ขาดทุนก้อนใหญ่ในเทรดแรกสัมพันธ์กับการออกจากตลาดถาวรอย่างมีนัยสำคัญ — [Ferko, Mixon & Onur, CFTC OCE Staff Paper 2023-002 (ก.พ. 2024)](https://www.cftc.gov/sites/default/files/2024-11/Retail_Traders_Futures_V2_new_ada.pdf)
- Crypto: ข้อมูลแพลตฟอร์มเทรดหลัก ส.ค. 2015–ธ.ค. 2022 → **ผู้ใช้ crypto app ส่วนใหญ่ในเกือบทุกประเทศขาดทุนจาก bitcoin holdings** หลัง Terra/Luna และ FTX (รายย่อยซื้อ ขณะที่รายใหญ่ขาย) — [BIS Bulletin 69, 20 ก.พ. 2023](https://www.bis.org/publ/bisbull69.htm)
- สวีเดน (FI Analysis 44, พ.ค. 2024), trading ใน cryptocertificates ทั้งหมด 1 ม.ค. 2018–31 มี.ค. 2024: **53% ของคนที่ขายถือครองทั้งหมดขาดทุน** แม้ราคา crypto เพิ่มขึ้นถึง 500% ในช่วงเดียวกัน — [Finansinspektionen](https://www.fi.se/contentassets/03e6af609fbe418c88d9a91f9d53e199/fi-analys-44-swedish-retail-trading-in-cryptocertificates.pdf)
- Hyperliquid (บัญชีครบทั้ง exchange, งาน ต.ค. 2026): **liquidation คิดเป็น 1.0% ของจำนวนเทรดที่ขาดทุน แต่ 27% ของเงินที่เสียทั้งหมด**; คนที่ถูกล้างพอร์ตมีโอกาสหยุดเทรด 1 เดือนสูงกว่า **19.7 percentage points**; คนที่กลับมาใช้เลเวอเรจเท่าเดิมและไม่ถูก liquidate บ่อยขึ้น — [Yuan & Li, "Who Realizes the Losses of Leveraged Traders?", SSRN 7404518 (ต.ค. 2026)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7404518)
- เลเวอเรจสูงทำนายผลขาดทุน: ก่อน CFTC cap 50:1 (ต.ค. 2010) **กลุ่ม quintile ที่ใช้เลเวอเรจสูงสุดขาดทุนเฉลี่ย 44% ต่อเดือน** และแย่กว่ากลุ่มเลเวอเรจต่ำสุด 30–40 pp ต่อเดือน; หลังจำกัดเลเวอเรจ ปริมาณเทรดลด 23% และผลตอบแทนกลุ่มนี้ดีขึ้น ~18 pp/เดือน (ขาดทุนลดลง ~40%) — [Heimer & Simsek, "Should retail investors' leverage be limited?", JFE (2019)](https://www.sciencedirect.com/science/article/pii/S0304405X18303076)

### Inferences
- ตัวเลข "กำไร" ที่สูงกว่า (เช่น 20–32% ของบัญชี forex กำไรในไตรมาสหนึ่ง) เป็น **snapshot รายไตรมาส ไม่ใช่ความอยู่รอดระยะยาว** — บัญชีเดียวกันสลับกำไร/ขาดทุนได้ และบัญชีที่กำไรไตรมาสเดียวไม่ใช่หลักฐานของ edge
- อัตราการกำไรลดลงตามจำนวนวันที่เทรด (29.8% → 3.0%) เป็นลายเซ็นของ **ค่า expectation ติดลบสะสม** ไม่ใช่ของ "ยังเรียนไม่เก่ง" — ถ้าเป็นเรื่องการเรียนรู้ สัดส่วนควรเพิ่มขึ้น
- กลุ่มที่รอดและกำไรมีจริง (~1–5%) มีลักษณะเฉพาะ: ขนาดโพซิชันใหญ่พอที่จะ cover ต้นทุน, ประสบการณ์ >40 วัน, และมีอยู่จริงในระดับหลักพันคนจากหลักแสน — **ไม่ใช่ผลของวินัยทั่วไป**
- งาน Hyperliquid ชี้ว่ากลไกตลาด (margin call) เป็นตัวตัดขาดทุนแทนเทรดเดอร์ เพราะเทรดเดอร์ไม่ตัดเอง → การมี stop ที่ผูกกับออเดอร์จึงเป็นเรื่องโครงสร้าง ไม่ใช่เรื่องวินัยส่วนบุคคล

### Gaps
- ไม่พบงานศึกษาเชิงวิชาการที่วัด **อัตราการรอดชีวิตของบัญชีขนาด <$500** โดยเฉพาะ (งานที่มีอยู่ตัดที่ NT$600k หรือ mini-contract margin) — ขนาดบัญชีเล็กกว่านั้นจึงต้องอนุมานจากต้นทุนต่อหน่วย (ดู Q7)
- ไม่พบสถิติ liquidation รายบุคคลจาก Binance/Bybit/OKX ที่เปิดเผยต่อสาธารณะ (มีแต่ยอดรวม notional ซึ่งไม่เท่ากับเงินที่เสียจริง) — งาน Hyperliquid เป็นเพียงแหล่งระดับบัญชีที่ตรวจสอบได้

---

## Q2. Kelly, fractional Kelly, volatility targeting และเลเวอเรจ: growth/drawdown ที่ edges 1%, 5%, 10% ต่อเทรด และเมื่อไหร่ 20x = ruin แน่นอน

### Takeaway
Kelly ให้ **เพดานการเติบโต** ไม่ใช่เป้า: f* = edge/σ² และ growth สูงสุด = edge²/(2σ²) ต่อเทรด — ที่ edge 1%/เทรด เพดานอยู่ราว **+0.3%/เดือน**; ที่ 5% ราว **+8%/เดือน**; ที่ 10% ราว **+37%/เดือน** (สมมติ σ = 1R) แต่ full Kelly แลกมาด้วยโอกาสถูก halve ~50% และ drawdown ระดับ 55–84% ส่วน **20x คือ ruin เชิงกลไก ไม่ใช่เชิงความน่าจะเป็น**: BTC ผันผวน 60%/ปี → ล้างพอร์ต 77% ภายใน 1 เดือน, EURUSD ที่ 30x พร้อมกฎ close-out 50% → โดนบังคับปิดที่การเคลื่อนไหวเพียง 1.67%

### Cited Findings
- สูตร: f* = p − (1−p)/b; ตัวอย่าง 55% win rate, payoff 1:1 → f* = 10% ของทุน/เทรด, expected log growth 0.50%/เทรด; ห้าแพ้ติดกันเหลือ 0.90⁵ = 0.59 (drawdown 41%); "การประเมิน edge สูงเกินจริงแพงกว่าประเมินต่ำเกินจริงมาก — เดาที่ 2 เท่าของ Kelly จริงให้ growth เท่าดอกเบี้ยเงินฝาก (ศูนย์)" — [EBC Financial Group, ต.ค. 2026](https://www.ebc.com/forex/kelly-criterion-position-sizing-formula-worked-example-risks)
- Thorp: ที่ full Kelly โอกาสที่จะเคยลงไปถึงสัดส่วน x ของทุนเริ่มต้น ≈ x (ดังนั้น P(halve) ≈ 50%); ที่ fraction k ของ Kelly → x^(2/k−1) (half Kelly → 12.5%); "Kelly-equivalent risk of ruin" ของคนที่ไม่ resize = e^(−2/k): k=1 → **13.53%**, k=0.5 → **1.83%**, k=0.25 → **0.03%**; ทีม blackjack มืออาชีพ一般在 k = 0.25–0.35 — [Chin, "Risk Formulæ for Proportional Betting" (2006)](https://condor.depaul.edu/wchin/riskpaper.pdf); [Thorp, "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market"](https://gwern.net/doc/statistics/decision/2006-thorp.pdf)
- Fractional Kelly: half Kelly ได้ **75% ของ growth สูงสุด** ด้วยความผันผวนครึ่งเดียว; 1.5× Kelly ได้ growth เท่ากันแต่ผันผวน 3 เท่าของ half Kelly — [BSIC, ต.ค. 2026](https://bsic.it/bet-sizing-from-the-kelly-criterion-to-drawdown-control)
- การจำลอง 4,000 paths × 20 ปี, Sharpe 0.5, vol 15%: Kelly leverage = 0.075/0.15² = **3.3x** → growth 12.5%/ปี แต่ **median max drawdown 84%** และแทบทุก path เคยขาดทุนเกินครึ่ง; half Kelly → 9.4%/ปี, median MaxDD **55%**, P(เคยเสียครึ่ง) 66%; 30% ของ Kelly → 6.4%/ปี, MaxDD 37%, P(เสียครึ่ง) 12% — [BSIC](https://bsic.it/bet-sizing-from-the-kelly-criterion-to-drawdown-control)
- Volatility targeting: ลดโอกาสเกิดผลตอบแทนสุดขั้วและลด left tail ใน **ทุก** asset class แต่ปรับ Sharpe ได้เฉพาะ equity/credit (เพราะ leverage effect) — ใน bonds/FX/commodities ผลต่อ Sharpe "negligible" — [Harvey, Hoyle, Korgaonkar, Rattray, Sargaison & Van Hemert, JPM 45(1) (2018)](https://jpm.pm-research.com/content/iijpormgmt/45/1/14); [สรุป Man Group](https://www.man.com/insights/the-impact-of-volatility-targeting)
- ข้อโต้แย้งสำคัญ: เมื่อทดสอบแบบ real-time กับ 103 กลยุทธ์ **vol-managed ชนะ 53 แพ้ 50** (มีนัยสำคัญเพียง 8) → "ไม่มีหลักฐานเชิงระบบว่า volatility-managed portfolios ดีกว่า unmanaged" — [Cederburg, O'Doherty, Wang & Yan, JFE 138(1) (2020)](https://www.sciencedirect.com/science/article/pii/S0304405X2030132X)
- Vol targeting แบบธรรมดาอาจ **เพิ่ม** max drawdown ในบางตลาด (UK, Canada, Australia, HK) และมี turnover >200%/ปี พร้อม leverage ที่แปรผันมาก — [Conditional Volatility Targeting, FAJ (2020)](https://www.tandfonline.com/doi/full/10.1080/0015198X.2020.1790853)
- กฎเลเวอเรจ EU/UK: 30:1 major FX, 20:1 non-major/gold, 10:1 อื่น ๆ, 5:1 หุ้น, 2:1 crypto **และบังคับ close-out ที่ 50% ของ margin ที่ต้องการ** — [ESMA/FCA COBS 22.5 สรุปโดย Forex Mechanics](https://forexmechanics.com/regulations/esma-retail-protection)
- ตัวอย่างจริงของ leverage ที่ฆ่าพอร์ต: VIX +115.6% ในวันเดียว (17→37) 5 ก.พ. 2018; XIV/SVXY ถือ short VIX futures รวม ~280,000 สัญญา (~$280M vega) มูลค่า **หาย >90% ในวันเดียว**, XIV ถูก liquidate, สินทรัพย์ short-vol ETP ลดจาก $3.7B → ~$525M — [Cboe, "Market Observations After the Volpocalypse"](https://cdn.cboe.com/resources/education/research_publications/after-the-volpocalypse-market-observation.pdf); [Financial Analysts Journal, "Volmageddon" (2021)](https://www.tandfonline.com/doi/full/10.1080/0015198X.2021.1913040)

**[คำนวณเอง] ตาราง growth เพดานที่ full Kelly (σ = 1R, 63 เทรด/เดือน)**
| edge/เทรด | f* (%ทุน/เทรด) | growth/เทรด | median เดือน | median เดือนถึง 3x |
|---|---|---|---|---|
| 1% | 1.0% | 0.005% | +0.32% | 349 เดือน |
| 2% | 2.0% | 0.020% | +1.27% | 87 เดือน |
| 4% | 4.0% | 0.080% | +5.17% | 21.8 เดือน |
| 5% | 5.0% | 0.125% | +8.19% | 14.0 เดือน |
| 10% | 10.0% | 0.500% | +37.0% | 3.5 เดือน |

**[คำนวณเอง] P(แตะ barrier) = 2·Φ(−a/(σ√T))** — leverage L, พอร์ตหมดที่การเคลื่อนไหว adverse a = 1/L (หรือ 0.5/L เมื่อมีกฎ close-out 50%)
| instrument / L | a | 1 วัน | 1 สัปดาห์ | 1 เดือน |
|---|---|---|---|---|
| BTC 60%/yr, 5x | 20% | 0.00% | 1.6% | 24.8% |
| BTC 60%/yr, 10x | 10% | 0.15% | 22.9% | 56.4% |
| BTC 60%/yr, **20x** | **5%** | **11.1%** | **54.7%** | **77.3%** |
| BTC 60%/yr, 20x + close-out 50% | 2.5% | 42.6% | 76.4% | 88.5% |
| BTC 60%/yr, 50x | 2% | 52.4% | 81.0% | 90.8% |
| EURUSD 8%/yr, 20x | 5% | 0.00% | 0.00% | 3.0% |
| EURUSD 8%/yr, **30x + close-out 50%** | **1.67%** | 0.01% | 13.3% | **47.1%** |
| EURUSD 8%/yr, 50x | 2% | 0.00% | 7.1% | 38.7% |

**[คำนวณเอง] Monte Carlo (200,000 paths, fixed-notional margin, BTC σ=60%/ปี, ไม่มี edge, ถือต่อเนื่อง 1 เดือน)**
| L | รอดชีวิต | จบ ≥3x | เคยแตะ 3x | median |
|---|---|---|---|---|
| 5x | 87.2% | 0.8% | 1.5% | 0.95 |
| 10x | 52.8% | 8.8% | 17.5% | 0.42 |
| **20x** | **27.9%** | **16.1%** | **33.2%** | **0.00** |
| 50x | 12.2% | 11.0% | 34.8% | 0.00 |

### Inferences
- **"20x guarantee ruin"** ต้องพูดให้ถูก: ไม่ใช่ทุกคนล้มในวันแรก แต่ที่ 20x การล้างพอร์ตเป็น **เหตุการณ์ปกติรายเดือน** (77%) และ **เกือบแน่นอนภายใน 1 ปี** (93%) เมื่อไม่มี edge; เมื่อมี edge ก็ยังถูกบังคับออกก่อน edge จะทำงาน เพราะ barrier อยู่ที่ 5% ของการเคลื่อนไหว adverse
- สำหรับ FX ที่ 30:1 กฎ close-out 50% ทำให้ barrier อยู่ที่ **1.67%** ซึ่งเป็น ~3.3σ ของ EURUSD รายวัน — หายากต่อวัน แต่ 47% ต่อเดือนถ้าถือเต็ม Notional ต่อเนื่อง; นี่คือเหตุผลที่ "ถือข้ามคืนที่ 30x" เป็นการเดิมพันกับ tail ไม่ใช่กับทิศทาง
- Vol targeting ลด tail ได้จริง แต่**ไม่เพิ่ม Sharpe** ในสินทรัพย์ส่วนใหญ่และไม่แก้ปัญหา edge เป็นลบ — มันเปลี่ยน "ล้มเร็ว" เป็น "ล้มช้า" เท่านั้น
- ตัวเลข BSIC (MaxDD 84% ที่ full Kelly) อธิบายว่าทำไมแม้แต่ hedge fund ก็ไม่รัน full Kelly: ไม่ใช่เพราะ growth ไม่ดี แต่เพราะ **ไม่มีใครอยู่รอด drawdown 84%** ได้ทั้งทางการเงินและทางจิตวิทยา

### Gaps
- ไม่พบงานที่วัด "effective leverage ของบัญชี $147 จริง" (ต้องมีข้อมูล margin ระดับบัญชีจาก broker) — ข้อจำกัดเรื่อง **minimum lot/notional** ถูกประมาณใน Q6 ด้วยค่ากลางของตลาด (0.01 lot, $5 min notional) ไม่ใช่จากแหล่งเดียว
- Kelly หลายตัวแปร (หลายสินทรัพย์ correlated) ไม่ได้ครอบคลุมในบันทึกนี้; งาน Busseti-Boyd risk-constrained Kelly มีอยู่แต่ไม่ได้ดึงตัวเลขมา

---

## Q3. การกระจายผลตอบแทนรายเดือนที่บันทึกไว้ ของ trend following, volatility selling, momentum, market making, event strategies (median, เดือนแย่สุด, max DD)

### Takeaway
กลยุทธ์ "มี edge จริง" ที่ดีที่สุดในโลกให้ **CAGR 5–13%** โดยมี Sharpe 0.3–1.0, เดือนแย่สุด −9% ถึง −13%, max DD 20–31% (trend) และ **−45% ถึง −74% ในเดือนเดียว** (momentum crash) ส่วน vol selling ให้ผลตอบแทนดีต่อเนื่องหลายปีแล้วคืนทั้งหมดในวันเดียว **ไม่มีกลยุทธ์ใดในหลักฐานสาธารณะที่ให้ median 200%/เดือน** — ตัวเลขระดับ 3x/เดือนไม่มีอยู่ใน distribution ของกลยุทธ์ที่ตรวจสอบได้เลย

### Cited Findings
**Trend following (SG Trend Index, 10 CTA ใหญ่สุด, net of fees)**
- ม.ค. 2000–ส.ค. 2026 (USD): CAGR **5.59%**, SD **13.26%**, Sharpe **0.36**; เดือนบวก **177/319 (55%)**; เดือนดีสุด +14.4% (ธ.ค. 2000), เดือนแย่สุด **−13.6% (พ.ย. 2001)**, รองลงมา −9.1% (มี.ค. 2003), −9.0% (ก.พ. 2018); **max DD −20.7% ยาว 6 ปี 1 เดือน (มี.ค. 2015–เม.ย. 2021)**; ปีดีสุด 2022 +27.4%, ปีแย่สุด 2018 −8.2% — [curvo.eu backtest SG Trend](https://curvo.eu/backtest/en/market-index/sg-trend?currency=usd)
- 2022 SG Trend **+27.3%** (ปีดีที่สุดเป็นประวัติการณ์) แต่ 2023 **−4.1%** ("ปีที่แย่ที่สุดเป็นอันดับ 6 นับจาก 2000, และแย่ที่สุดถ้าไม่นับ cash") — [Hedgeweek, 27 ม.ค. 2023](https://www.hedgeweek.com/trend-followers-turn-leaders-as-ctas-deliver-record-returns-2022/); [Quantica Quarterly Insights 2024Q1](https://quantica-capital.com/publications//pdf/2024Q1_QuanticaQuarterlyInsights.pdf)
- "Lost decade" 2009–2018: SG Trend annualized **0.4%** พร้อม max DD **21.8%** (MAR 0.02) — [Price Action Lab, ก.พ. 2023](https://www.priceactionlab.com/Blog/2023/02/trend-ctas-momentum/)
- drawdown ที่แย่กว่า −10%: 9 ครั้งใน 24 ปี, ความลึกเฉลี่ย −15%, ใช้เวลา recover เฉลี่ย 9 เดือน (เทียบ S&P: 5 ครั้ง ลึกเฉลี่ย −29%, recover 22 เดือน) — [Dunn Capital/IMDDA, ม.ค. 2024](https://imdda-members.s3.amazonaws.com/DUNN-Managed-Futures-Trendfollowing-December-2023.pdf)

**Momentum (WML, US equities 1927–2013)**
- Sharpe 0.68 (static), 1.19 (dynamic/risk-managed); monthly skew **−6.3**; เดือนแย่สุด: **−74.4% (ส.ค. 1932), −61.0% (ก.ค. 1932), −49.2% (ม.ค. 2001), −45.5% (เม.ย. 2009), −42.3% (มี.ค. 2009)** — [Daniel & Moskowitz, "Momentum Crashes", JFE 122 (2016), ตาราง 2](https://www.kentdaniel.net/papers/published/jfe_16.pdf)
- momentum crash 2009: **−52.91% ทั้งปี ขณะที่ market factor +28.52%**; มี.ค.–พ.ค. 2009 −49.4%; เม.ย. 2009 เดือนเดียว −34.4% (Fama-French factor) — [LedgerTouch, ส.ค. 2026](https://ledgertouch.com/blog/portfolio-risk/momentum-premium-crashes-turnover-costs)
- momentum 1927–2008 (US): เฉลี่ย **16.5%/ปี, Sharpe 0.82** แต่ monthly skew **−6.3** (เทียบ market −0.58) — [Daniel & Moskowitz, สไลด์ "Momentum Crashes"](https://vintagequants.com/wp-content/uploads/2024/09/2012fall_danielslides.pdf)
- momentum crash ปี 1932 ให้ **−91.6% ใน 2 เดือน** และปี 2009 **−73.4% ใน 3 เดือน**; "แม้แต่ผลตอบแทนสูงของ momentum ก็ไม่ชดเชยนักลงทุนที่ risk aversion สมเหตุสมผลสำหรับ crash กะทันหันเหล่านี้" — [Barroso & Santa-Clara, "Momentum has its moments", JFE (2015)](https://www.sciencedirect.com/science/article/pii/S0304405X14002566)

**Short volatility**
- SVXY ผลตอบแทนปี 2012–2017: **+156%, +104%, −9%, −17%, +80%, +179%** ด้วย volatility **66%/ปี** (S&P 12%) → ลงทุนปลายปี 2011 ถึงสิ้นปี 2017 ได้ +1,870% — แล้ว **5 ก.พ. 2018 ขาดทุนเกือบ −100% ในวันเดียว**; XIV −92% ถึง −96% และถูก liquidate — [Rodex/CAIA, "In Free Fall and Yet Attractive?" (ต.ค. 2018)](https://caia.org/sites/default/files/in_free_fall_and_yet_attractive_short_volatility_etfs.pdf)
- Volatility drag ของ short VIX1m futures: vol 67%/ปี, drag **−45%/ปี**; แม้ VIX จาก 10→20 แบบค่อยเป็นค่อยไปใน 10 วันก็ยังขาดทุน −52.6% — [Artur Sepp, ก.พ. 2018](https://artursepp.com/2018/02/15/lessons-from-the-crash-of-short-volatility-etfs/)
- 5 ก.พ. 2018: VIX +115.6% ในวันเดียว, short-vol ETP assets $3.7B → $525M; XIV/SVXY ถือ short VIX futures ~$280M vega — [Cboe](https://cdn.cboe.com/resources/education/research_publications/after-the-volpocalypse-market-observation.pdf)

**Merger arbitrage / event-driven**
- Global value-weighted merger arb 1992–2023 (ก่อนต้นทุน): annualized **13.45%**, SD **10.84%**, Sharpe **1.03**; ปีแย่สุด −8.1% (1993), −4.3% (2015), −2.3% (2012); abnormal return 8.76%/ปี — [Stockholm School of Economics thesis, พ.ค. 2024, ตาราง III](http://arc.hhs.se/download.aspx?MediumId=5961)
- ในทางปฏิบัติ (ETF, 17 ปี พ.ย. 2009–ต.ค. 2026): **CAGR 2.67%, vol 7.4%, worst DD −16.7%, correlation กับ S&P 0.45**; สัปดาห์แย่สุด **−6.5% (สัปดาห์ 15 มี.ค. 2020)**; ปีขาดทุน 2010, 2011, 2021 (−3.2%), 2022 (−1.6%) — [Papers With Backtest](https://paperswithbacktest.com/strategies/merger-arbitrage)
- BarclayHedge Merger Arbitrage Index รายเดือน 2022–2024: เดือนส่วนใหญ่อยู่ใน **±1.5%**, เดือนแย่สุด −1.20% (มิ.ย. 2022), ปี 2022 +0.95%, 2023 +4.57%, 2024 +4.45% — [BarclayHedge](https://portal.barclayhedge.com/cgi-bin/indices/displayHfIndex.cgi?indexCat=Barclay-Hedge-Fund-Indices&indexName=Merger-Arbitrage-Index)
- โครงสร้างผลตอบแทน: สำเร็จ ~2.0%, ล้มเหลว −2.8% ต่อดีล (835 ดีล ปี 2000–2020, สำเร็จ 89%) → blended ~1.5% ต่อดีล; spread สูง (5–7.5%) ให้ 4.0% แต่ cancellation rate ก็สูงขึ้น — [Alpha Architect, เม.ย. 2023](https://alphaarchitect.com/merger-spread)

**[คำนวณเอง] ข้อสังเกตเชิงเลข**: เดือนแย่สุดของ trend (−13.6%) เมื่อเทียบกับเดือนดีสุด (+14.4%) คือ **ratio ~1:1** แต่ของ momentum คือ **−74% ต่อเดือน** — นี่คือความต่างระหว่าง "negative skew ปกติ" กับ " ruin risk"

### Inferences
- ถ้าเป้าเป็น 3x/เดือน (200%) ต้องได้ผลตอบแทนระดับที่ **สูงกว่าเดือนดีที่สุดในประวัติศาสตร์ของ SG Trend 14 เท่า** และสูงกว่าปีดีที่สุดของ trend ทั้งปี (27.4%) เกือบ 8 เท่า → ไม่มีอยู่ใน distribution ของกลยุทธ์ที่วัดได้
- กลยุทธ์ที่ให้ผลตอบแทนสูงต่อเนื่อง (short vol, merger arb) ล้วนมี **payoff แบบ short put**: กำไรเล็กสม่ำเสมอ ขาดทุนก้อนใหญ่ครั้งเดียว — ซึ่งตรงข้ามกับสิ่งที่บัญชี $147 ต้องการ (ต้องรอดก่อน)
- Trend following เป็นกลยุทธ์เดียวในกลุ่มที่มี **positive skew** และรอดเงื่อนไข "อยู่รอดได้นาน" แต่ให้ผลตอบแทนต่ำ (5.6%/ปี) → ที่ $147 คือ **~$0.7/เดือน** ก่อนหักค่าธรรมเนียม

### Gaps
- **Market making: ไม่พบข้อมูล distribution รายเดือนที่ตรวจสอบได้สำหรับผู้เล่นรายย่อย** — market making ที่มีกำไรต้องมี colocation, rebate, inventory หลายสินทรัพย์; ข้อมูล HFT/ต้นทุนอยู่ในงาน microstructure ที่ไม่ได้ดึงมาในรอบนี้ (เป็น gap ที่ควรระบุตรง ๆ ไม่ควรเดาตัวเลข)
- ไม่พบ monthly return series ของ "event-driven" แบบ pure (earnings/PEAD) ที่ net of costs; merger arb เป็น proxy ที่ใกล้ที่สุด
- ตัวเลข SG Trend บางชุดต่างกันตามสกุลเงิน (EUR: CAGR 4.92%, max DD −30.8%) — ต้องระบุสกุลเงินเมื่ออ้าง

---

## Q4. ความน่าจะเป็นที่จะเปลี่ยน $147 → $441 (3x) ในหนึ่งเดือน ภายใต้ edge และ volatility ที่ plausible

### Takeaway
**3x/เดือนเป็นไปไม่ได้ในเชิงสถิติสำหรับ edge ที่มีอยู่จริง** — ที่ full Kelly และ σ = 1R ต้องมี per-trade Sharpe ~0.19 (win rate 59.3% ที่ 1:1, เดือนละ Sharpe 1.48) ซึ่งไม่มีประชากรรายย่อยใดในงานศึกษาแสดงให้เห็น; ที่ edge 5%/เทรด (สูงมากแล้ว) P(3x ใน 1 เดือน) = **0.36%** และถ้าไปบังคับให้ได้ 3x ด้วยการ overbet เป็น 2× Kelly ถึง 8.7% แต่ **median กลับติดลบ (−2%)** — คือการซื้อลอตเตอรี ไม่ใช่การเทรด

### Model & Assumptions (ของ Q4–Q5)
- โมเดล A (ใช้เป็นหลัก): fixed-fraction bet, 63 เทรด/เดือน (3/วัน × 21), payoff 1:1, σ = 1R, ไม่มีต้นทุน, edge = expected P&L ต่อเทรดเป็นหน่วย R (ไม่ใช่ % ของ notional)
- โมเดล B: leveraged hold, notional คงที่, equity = 1 + L·(S−1), liquidate ที่ 0, GBM ไม่มี drift, BTC σ = 60%/ปี, EURUSD σ = 8%/ปี
- ข้อจำกัด: GBM ไม่มี fat tail/jump → **ประเมิน P(ruin) ต่ำเกินจริง**; ค่าธรรมเนียม/funding ใส่แยกใน Q7
- สคริปต์: `risk_return_ceiling_sim.py` (ไฟล์เดียวกันในโฟลเดอร์นี้ — รันซ้ำได้ ผลตรงกับตาราง)

**[คำนวณเอง] P(3x ภายใน 1 เดือน) — 63 เทรด, 1:1, edge ต่อเทรด**
| edge | risk/trade | P(3x) | P(2x) | P(จบกำไร) | median | P(เหลือ ≤10%) |
|---|---|---|---|---|---|---|
| 0% | 10% | 3.85% | 10.5% | 31.0% | 0.81 | 0.57% |
| 0% | 25% | 6.49% | 10.4% | 15.7% | 0.17 | **40.0%** |
| 5% | **5% (Kelly)** | **0.36%** | 5.2% | 55.9% | 1.07 | 0.00% |
| 5% | 10% (2×Kelly) | **8.54%** | 19.4% | 45.8% | **0.98** | 0.17% |
| 5% | 25% | 13.11% | 19.3% | 27.0% | 0.28 | **25.9%** |
| 10% | 10% (Kelly) | 16.61% | 32.3% | 61.5% | 1.47 | 0.04% |
| 10% | 25% | 23.45% | 32.0% | 41.5% | 0.78 | **14.7%** |

- ต้องมี **g/เทรด = ln(3)/63 = 1.744%** → per-trade Sharpe = √(2g) = **0.187**, เทียบเท่า win rate **59.3%** ที่ 1:1 และ monthly Sharpe **1.48** [คำนวณเอง]
- สำหรับ edge ที่ "ดีแต่สมจริง" (4%/เทรด = win rate 52% ที่ 1:1): P(แตะ 3x ภายใน 1 ปี) = **42.9%**, median 1 ปี = **1.81x**, P(จบ ≤30% ของทุน) = 5.0% [คำนวณเอง]
- leverage path: BTC 20x ถือ 1 เดือน → **P(จบ ≥3x) = 16.1%** แต่ **P(แตะ 3x) = 33.2%** และ **รอด 27.9%** (median = 0) [คำนวณเอง]
- เทียบฐาน: เงิน $147 ที่ +5%/เดือน (edge 4%/เทรด full Kelly) = **+$7.35/เดือน**; ที่ 8.2%/เดือน = **+$12/เดือน** [คำนวณเอง จาก Q2]

### Cited Findings
- งานศึกษาไม่พบใครที่ทำผลตอบแทนระดับนี้: top 500 day traders ที่เก่งที่สุดในไต้หวันได้ **+37.9 bps/วัน** (~+8%/เดือน) *ก่อน* ที่จะคิดว่ากลุ่มนี้คือ 0.1% ของประชากร — [Barber et al. 2014](https://www.sciencedirect.com/science/article/pii/S1386418113000190)
- เทรดเดอร์ที่เก่งที่สุดในบราซิล (1 คนจาก 19,646) ได้ **US$310/วัน โดย SD US$2,560/วัน** → Sharpe รายวัน ≈ 0.12 ซึ่งใกล้เคียงกับที่โมเดลต้องการแต่ **มาพร้อมความผันผวนที่ทำให้โอกาสขาดทุนสะสมสูงมาก** — [Chague et al. 2020](https://repositorio.fgv.br/server/api/core/bitstreams/0f00dd78-6909-4f91-84d5-aef8803e6436/content)
- "ผู้ชนะ" ในตลาด prop firm (ตัวชี้วัดที่ใกล้ที่สุดของกลุ่มที่อ้างผลตอบแทนสูง): มีเพียง **7% ของผู้ซื้อ challenge ที่ได้ payout อย่างน้อยหนึ่งครั้ง** และ payout เฉลี่ย **~4% ของขนาดบัญชี** — [FPFX Tech ผ่าน Finance Magnates, เม.ย. 2026](https://selectpropfirms.com/prop-firm-statistics/)

### Inferences
- ตัวเลข 3x/เดือนที่โฆษณากันมักมาจาก **การ overbet ไม่ใช่ edge**: ที่ edge 0% และ risk 25%/เทรด มี P(3x) 6.5% ซึ่ง "ดูเหมือนทำได้" แต่ 40% ของบัญชีเหลือ ≤10% — ในกลุ่ม 100 คน จะมี ~7 คนที่เล่าเรื่องได้และ 40 คนที่เงียบ
- การเพิ่ม leverage ไม่ได้เพิ่ม **growth** เกินเพดาน edge²/(2σ²) — มันแค่เพิ่ม variance และย้ายความน่าจะเป็นไปที่ tail ทั้งสองข้าง; ดังนั้นการ "ไล่ 3x" คือการซื้อ right tail ด้วย left tail ที่ใหญ่กว่า
- ถ้าต้องการ 3x/เดือนจริง ๆ คำถามที่ถูกต้องคือ "edge ต่อเทรดต้อง ~19% ของ R ที่ risk" ซึ่งเทียบเท่าคนที่ชนะ 59–60% ด้วย payoff 1:1 ต่อเนื่อง 63 ครั้ง/เดือน — ไม่มีหลักฐานว่าใครทำได้

### Gaps
- ไม่พบการศึกษาที่รายงาน **distribution ของ monthly return สำหรับ retail trader เดี่ยว** (มีแต่ aggregate/mean) → P(3x) ต่อคนจึงต้องมาจากการจำลองเท่านั้น
- ไม่มีการทดสอบว่า edge 10%/เทรดมีอยู่จริงในตลาดใด ๆ ในทางปฏิบัติ — ตัวเลข 10% ในตารางเป็น **upper-bound ทางคณิตศาสตร์** ไม่ใช่ค่าที่คาดหวัง

---

## Q5. Sequence risk, การเติมเงิน, บัญชีที่หมด, survivorship bias ใน track record ที่เผยแพร่ และการตลาดของ "prop firm"

### Takeaway
บัญชี $147 เผชิญ **sequence risk แบบทวีคูณ** เพราะ (ก) ขนาดโพซิชันขั้นต่ำของ broker ทำให้ risk ต่อเทรดสูงกว่าที่ควร, (ข) การเติมเงินเพื่อ "ประคอง" จะทำให้ track record ไม่ต่อเนื่องและซ่อน drawdown จริง และ (ค) หลักฐาน prop firm แสดงว่ากลไกคัดเลือก (14% ผ่าน, 7% ได้รับเงิน, median อายุบัญชี 0.8 วัน) คือสิ่งที่ทำให้ตัวเลขที่โฆษณาดูดี — ไม่ใช่ทักษะของผู้ขายคอร์ส

### Cited Findings
**Sequence risk / path dependence**
- โรงเรียน Kelly: ผลลัพธ์ขึ้นกับ **ลำดับ** ของกำไร/ขาดทุน ไม่ใช่แค่ผลรวม; ที่ full Kelly P(เคยลงไปถึงครึ่ง) ≈ 50% แม้ expected growth สูงสุด — [Thorp (2006)](https://gwern.net/doc/statistics/decision/2006-thorp.pdf); [Chin (2006)](https://condor.depaul.edu/wchin/riskpaper.pdf)
- การจำลอง 20 ปี: ที่ full Kelly **median max drawdown 84%** แม้ Sharpe 0.5 — "ไม่มีกองทุนใดอยู่รอด drawdown 84%" — [BSIC](https://bsic.it/bet-sizing-from-the-kelly-criterion-to-drawdown-control)
- แม้แต่ trend following ที่ Sharpe 0.36 ก็มี drawdown **6 ปี 1 เดือน** (−20.7%) — [curvo.eu](https://curvo.eu/backtest/en/market-index/sg-trend?currency=usd)

**การเติมเงิน / บัญชีหมด**
- ในงาน Hyperliquid: **liquidation = 1% ของจำนวนเทรดที่ขาดทุน แต่ 27% ของเงินที่เสีย**; คนที่ถูกล้างมีโอกาสหยุดเทรด 1 เดือนสูงกว่า 19.7 pp; **คนที่ narrowly escape ยังถือต่อและเสียมากขึ้น** — [Yuan & Li, SSRN 7404518](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7404518)
- CFTC: ขาดทุนก้อนใหญ่ในเทรดแรกสัมพันธ์กับการออกจากตลาดถาวร → บัญชีเล็กที่เจอ drawdown เร็วมัก **ไม่กลับมา** ไม่ใช่ "เติมเงินแล้วสู้ต่อ" — [Ferko, Mixon & Onur (2024)](https://www.cftc.gov/sites/default/files/2024-11/Retail_Traders_Futures_V2_new_ada.pdf)
- ESMA/UK disclosure นับเฉพาะ **ผลตอบแทนสุทธิ รวม unrealized** และ **ตัดบัญชีที่ไม่มีโพซิชันออก** → การเติมเงินไม่สามารถกลบการขาดทุนในสถิติได้ (แต่ใน track record ส่วนตัวทำได้) — [ESMA decision notice](https://www.esma.europa.eu/sites/default/files/library/2018-esma35-43-1397_cfd_renewal_decision_notice_en.pdf)

**Survivorship bias**
- ไต้หวัน: **อัตรารอด 44% (1 ปี) → 15% (3 ปี)** — ถ้าเก็บข้อมูลเฉพาะคนที่ยังเทรดอยู่ จะเห็นเฉพาะ 15% ที่รอด ซึ่งเป็น survivor sample โดยนิยาม — [Barber et al. 2020](https://academic.oup.com/raps/article-abstract/10/1/61/5545095)
- บราซิล: สัดส่วนคนกำไร **ลดลง** ตามจำนวนวัน (29.8% → 3.0%) → การรายงานผลของ "คนที่ยังอยู่" ให้ภาพบวกเกินจริงอย่างเป็นระบบ — [Chague et al. 2020](https://repositorio.fgv.br/server/api/core/bitstreams/0f00dd78-6909-4f91-84d5-aef8803e6436/content)
- ตัวเลข "90% แพ้" ที่แพร่หลาย **ไม่มีแหล่งที่มา**; ตัวเลขที่ตรวจสอบได้คือ 54.4%–84% ของบัญชี CFD (ค่ามัธยฐาน ~72–73.5%) — [rulesbeforeresults, พ.ย. 2026](https://rulesbeforeresults.app/en/what-percentage-of-traders-lose-money); [riskwarnings.com Q3 2026](https://riskwarnings.com/)

**Prop firm marketing**
- **FPFX Tech: >300,000 บัญชี challenge, 100,000 เทรดเดอร์, 10 บริษัท → 14% ผ่าน, 7% ได้รับ payout** — [Select Prop Firms, ก.ย. 2026](https://selectpropfirms.com/prop-firm-statistics/)
- Goat Funded Trader: **22,279 จาก 594,997 คนที่ซื้อ challenge (3.7%)** เคยได้รับเงินถึง 21 ต.ค. 2026 — [Select Prop Firms, ก.ย. 2026](https://selectpropfirms.com/prop-firm-statistics/)
- Topstep 2025: 16.8% ของ Trading Combine ผ่าน; **51.8% ของ*คน*ผ่านอย่างน้อย 1 ครั้ง** (เพราะซื้อหลายครั้ง); 33.3% ของคนที่ถึง funded ได้ payout; **63% ของเทรดเดอร์เสียบัญชีในวันเทรดวันแรก** — [The Prop Journalist, ก.ย. 2026](https://thepropjournalist.com/analysis/prop-firm-pass-rates/)
- Hypernova: **median อายุบัญชี 0.8 วัน** (เฉลี่ย 3.1 วัน) ก่อนผ่าน/ตก/หมดอายุ — [The Prop Journalist](https://thepropjournalist.com/analysis/prop-firm-pass-rates/)
- OneFunded: **93.7% ของการตก challenge มาจาก daily loss limit + max drawdown**; 15% จาก max drawdown อย่างเดียว; ~60% ของการตกเกิดในวันเดียว — [Fortunly สรุป OneFunded/TradersSecondBrain](https://fortunly.com/statistics/prop-firm-challenge-pass-rate-statistics/)
- payout เฉลี่ย **~4% ของขนาดบัญชี** ทั้งหมด (ไม่ใช่ต่อเดือน) — [The Prop Firm Guide, พ.ย. 2026](https://thepropfirmguide.com/prop-firm-statistics)
- **80–100 บริษัท prop firm หยุดดำเนินการระหว่าง ม.ค. 2024–มี.ค. 2026** — [Select Prop Firms](https://selectpropfirms.com/prop-firm-statistics/)
- FTMO ไม่เปิดเผย pass rate (มีแต่ 4.5M+ customers, $650M+ rewards); CEO ให้สัมภาษณ์ Forbes ว่า **8–10%** — [forexop, ต.ค. 2026](https://forexop.com/learning/prop-firm-challenge-pass-rate)
- การจำลอง 3,000 challenges: **คนที่ไม่มี edge เลยผ่าน challenge 2-step 10%/5% ได้ ~32%** — กล่าวคือ pass rate ไม่ใช่หลักฐานของ edge — [forexop](https://forexop.com/learning/prop-firm-challenge-pass-rate)

### Inferences
- ถ้าคนส่วนใหญ่ "*เกือบ* รอด" (narrowly escape) แล้วถือต่อและเสียมากขึ้น (Hyperliquid) การเติมเงินจึงมักยืดเวลาแห่งการขาดทุน ไม่ใช่ซื้อโอกาส — และทำให้การวัด edge เป็นไปไม่ได้เพราะ equity curve ถูกตัดตอน
- ตัวเลข "51.8% ของคนผ่าน" ของ Topstep กับ "16.8% ของ Combine" ต่างกันเพราะ **การซื้อซ้ำ** — การตลาดเลือกใช้ตัวที่สูงกว่าเสมอ; เช่นเดียวกัน track record ส่วนตัวที่เผยแพร่มักเลือกช่วงเวลาหรือบัญชีที่ชนะ (survivorship ภายในตัวบุคคล)
- prop firm เป็นธุรกิจที่ขาย **ความหวังแบบมี leverage**: รายได้หลักคือค่า challenge ไม่ใช่ส่วนแบ่งกำไร; การที่ 80–100 บริษัทปิดตัวแสดงว่าแม้แต่ฝั่งที่ "ขายฝัน" ก็ไม่ได้กำไรเสมอ

### Gaps
- ไม่พบข้อมูล **อัตราการเติมเงิน (top-up) ของบัญชีรายย่อย** จาก broker ใด → ผลของ top-up ต่อผลตอบแทนสุทธิจึงอนุมานได้แค่เชิงคุณภาพ
- ไม่พบสถิติ **prop firm payout ต่อผู้ขอรับ (ไม่ใช่ต่อผู้ซื้อ challenge)** ในระดับอุตสาหกรรม; ตัวเลข 28.5–39.2% เป็นของแต่ละบริษัทและไม่ได้ audit

---

## Q6. กฎความเสี่ยงที่ทำให้บัญชีเล็กอยู่รอดได้นานพอจะทดสอบ edge (โดยไม่แกล้งทำเป็นว่ากฎสร้างผลตอบแทน)

### Takeaway
กฎที่ทำให้รอดคือกฎที่ **จำกัดการสูญเสียต่อหน่วยเวลาให้เล็กพอที่จะได้ตัวอย่างทางสถิติ** ไม่ใช่กฎที่เพิ่มผลตอบแทน: risk 0.5–1% ต่อเทรด, stop ที่ผูกกับออเดอร์, levered notional ≤3x, ขาดทุนรายวัน ≤3%, และหยุดเมื่อขาดทุนสะสม 15% — แต่ต้องยอมรับว่า **ที่ $147 การทดสอบ edge 52% ต้องใช้ ~2,400 เทรด (~2 ปี)** ซึ่งเกินอายุของบัญชีส่วนใหญ่

### Cited Findings
- ต้นทุนเป็นตัวฆ่า: day trader ไต้หวันขาดทุน **−7 bps/วันก่อนต้นทุน → −23.9 bps/วันหลังต้นทุน** (ต้นทุน ~3.4 เท่าของ gross edge) — [Barber et al. 2020](https://academic.oup.com/raps/article-abstract/10/1/61/5545095)
- ต้นทุนที่ถูกกฎหมาย: ไต้หวัน commission 10 bps + sales tax 30 bps = **40 bps ต่อ round trip** ซึ่งเป็นเหตุผลที่ต้องมี gross edge > 40 bps/วันจึงจะรอด — [Barber et al. 2004](https://faculty.haas.berkeley.edu/odean/papers/day%20traders/Day%20Trade%20040330.pdf)
- การจำกัดเลเวอเรจ **ลดการขาดทุนได้จริง**: หลัง CFTC cap 50:1 กลุ่มเลเวอเรจสูงขาดทุนลดลง ~40% (จาก −44%/เดือน) — [Heimer & Simsek, JFE (2019)](https://www.sciencedirect.com/science/article/pii/S0304405X18303076)
- กฎ close-out 50% ของ ESMA ทำให้ **30:1 = ถูกบังคับปิดที่การเคลื่อนไหว 1.67%** — leverage ที่ "ได้รับอนุญาต" ไม่ได้แปลว่ารอด — [Forex Mechanics สรุป ESMA/FCA](https://forexmechanics.com/regulations/esma-retail-protection)
- ตัวอย่าง drawdown ของกลยุทธ์ที่ "ดี": SG Trend −20.7% ยาว 6 ปี; Merger arb ETF −16.7%; momentum −74% ในเดือนเดียว → **position sizing ต้องทำให้ drawdown เหล่านี้อยู่รอดได้ด้วยบัญชีที่ไม่มีการเติมเงิน** — [curvo.eu](https://curvo.eu/backtest/en/market-index/sg-trend?currency=usd); [Papers With Backtest](https://paperswithbacktest.com/strategies/merger-arbitrage)
- ตัวอย่างการวัด edge ที่ไม่พอ: win rate 55% จาก 100 เทรดมี **margin of error ±10 pp** — แยกจาก "ไม่มี edge" ไม่ได้ — [EBC](https://www.ebc.com/forex/kelly-criterion-position-sizing-formula-worked-example-risks)
- people ที่ risk ขนาดใหญ่ในช่วงแรกคือคนที่ตก challenge มากที่สุด (63% ตกในวันแรก) — [The Prop Journalist](https://thepropjournalist.com/analysis/prop-firm-pass-rates/)

**[คำนวณเอง] ขนาดตัวอย่างที่ต้องใช้เพื่อยืนยัน edge (สองด้าน, 95%)**: n ≈ p(1−p)(1.96/δ)²
| win rate จริง | margin ที่ต้องการ | จำนวนเทรด | วันที่ต้องใช้ (3 เทรด/วัน) |
|---|---|---|---|
| 52% | ±2 pp | ~2,400 | ~800 วัน (3.2 ปี) |
| 55% | ±5 pp | ~380 | ~127 วัน |
| 60% | ±5 pp | ~369 | ~123 วัน |

**[คำนวณเอง] ต้นทุนต่อเดือนจากการเทรดที่ leverage สูง** (ค่าธรรมเนียม 0.10% ของ notional ต่อ round trip, 63 เทรด)
| levered notional | ต้นทุน/เทรด (% ทุน) | ทุนเหลือหลัง 63 เทรด |
|---|---|---|
| 1x | 0.10% | 93.9% |
| 3x | 0.30% | 82.8% |
| 5x | 0.50% | 72.9% |
| 10x | 1.00% | 53.1% |
| 20x | 2.00% | 28.0% |

**[คำนวณเอง] ขนาดขั้นต่ำที่ $147 ทำได้** — micro lot 0.01 (EURUSD) = $0.10/pip; stop 15 pip = **$1.50 = 1.02% ของทุน**; stop 10 pip = **0.68%** → บัญชี $147 **ทำ risk 0.5% ไม่ได้ด้วยคู่เงิน FX มาตรฐาน** (ต้องใช้ crypto ที่ min notional $5–10 หรือ fractional share)

### Inferences
- ที่ $147 กฎที่สมเหตุสมผลคือ: **risk 0.7–1.0% ต่อเทรด (บังคับโดยขนาด lot), ไม่เกิน 2–3 เทรด/วัน, levered notional ≤3x, หยุดเมื่อขาดทุน 15%** — ไม่ใช่เพราะกฎเหล่านี้ทำเงิน แต่เพราะทำให้ **จำนวนเทรดที่ต้องใช้ในการทดสอบ (≥380) อยู่ภายในอายุขัยของบัญชี**
- ที่ leverage 10x ขึ้นไป ต้นทุนซื้อขายเพียงอย่างเดียว (0.1%/side) กิน 47–72% ของทุนต่อเดือน → edge ต้องสูงกว่า **~1.5–2% ต่อเทรด** เพียงเพื่อเสมอตัว ซึ่งสูงกว่า edge ของเทรดเดอร์ที่เก่งที่สุดในงานศึกษา (0.38%/วัน)
- กฎที่ "สร้างผลตอบแทน" ไม่มีอยู่; สิ่งที่กฎทำได้คือ **(1) ทำให้ต้นทุนต่อหน่วยเล็ก relative กับ edge, (2) ทำให้ drawdown ไม่ตัดจบก่อนที่ edge จะแสดงตัว, (3) ทำให้ข้อมูลที่เก็บไม่ปนเปื้อนจากการเติมเงิน**

### Gaps
- ไม่พบงานที่ทดลอง **ผลของ leverage cap ต่ออัตราการรอดของบัญชี <$500** โดยตรง; ข้อสรุปเรื่อง minimum lot เป็นการคำนวณจากกติกาตลาดทั่วไป (0.01 lot, $5 min notional) ไม่ใช่จากแหล่งเดียว
- ไม่มีข้อมูลว่า median อายุบัญชี retail (นอก prop firm) ยาวเท่าไร → ไม่สามารถบอกได้ว่าบัญชี $147 โดยทั่วไป "อยู่ได้นานพอ" หรือไม่

---

## Q7. สรุปตัวเลขตอบคำถามหลัก: $147 ทำได้เดือนละเท่าไร และ leverage/sizing แบบไหนรอด

### Takeaway
**คำตอบที่ตรงไปตรงมา: median ที่คาดหวังได้คือ ~$0 ถึง −$3/เดือน และถ้าเป็นคนที่เก่งมากจริง ๆ (top 1–5%) ราว $3–$12/เดือน** — เป้า 3x/เดือน ($294 กำไร) ไม่ได้รับการสนับสนุนจากหลักฐานใดเลย; ส่วน leverage ที่ "ทำให้ตัวเลขดูมีความหมาย" (≥10x) มีต้นทุนซื้อขายกิน 47–72% ของทุนต่อเดือน และมีโอกาสล้างพอร์ต 53–77% ภายในเดือนเดียว

**[คำนวณเอง] ตารางสรุป: $147 กับผลตอบแทนต่อเดือน**
| สถานการณ์ | ผลตอบแทน/เดือน | เป็นเงิน | ที่มา/สมมติฐาน |
|---|---|---|---|
| ค่ากลางของ retail day trader (ไต้หวัน) | −23.9 bps/วัน ≈ **−4.5%/เดือน** | −$6.6 | [Barber et al. 2020](https://academic.oup.com/raps/article-abstract/10/1/61/5545095) |
| บัญชี CFD ทั่วไป (ค่ามัธยฐาน disclosed) | ~72–74% ขาดทุนใน 12 เดือน | — | [rulesbeforeresults](https://rulesbeforeresults.app/en/what-percentage-of-traders-lose-money) |
| edge 2%/เทรด, full Kelly | +1.3% | +$1.9 | จำลองเอง |
| edge 4%/เทรด (win 52%), full Kelly | +5.2% | +$7.6 | จำลองเอง |
| edge 5%/เทรด, full Kelly | +8.2% | +$12.0 | จำลองเอง |
| edge 10%/เทรด, full Kelly (fantasy) | +37% | +$54 | จำลองเอง |
| เป้า 3x/เดือน | +200% | +$294 | ต้อง per-trade Sharpe 0.19 |
| เป้า "ค่าขนม" $50/เดือน | +34%/เดือน | +$50 | ต้อง Sharpe ~0.09 ต่อเทรดต่อเนื่อง |

**คำตอบเรื่อง leverage/sizing ที่รอด:**
- **≤3x levered notional, risk 0.7–1.0%/เทรด, หยุดที่ −15%** = ช่วงที่ต้นทุนยังไม่กิน edge และ drawdown ของกลยุทธ์จริง (−15% ถึง −25%) ยังอยู่รอดได้โดยไม่ต้องเติมเงิน
- **10x** = ต้นทุนกิน ~47%/เดือน + P(ล้างพอร์ต 1 เดือน) 53% (BTC) → ใช้ได้เฉพาะเป็น "lotto ticket" ด้วยเงินที่ยอมเสียทั้งก้อน
- **20x** = P(ล้างพอร์ต) 77%/เดือน, 93%/ปี; แม้มี edge ก็ถูกบังคับออกก่อน — "รอด" ในความหมายทางสถิติคือ 27.9% หลัง 1 เดือน
- **30x FX + กฎ close-out 50%** = ถูกบังคับปิดที่ 1.67% ของการเคลื่อนไหว = ~3.3σ รายวัน → 47% ต่อเดือนถ้าถือต่อเนื่อง

### Cited Findings
- ไม่มีหลักฐานของกลุ่มประชากรรายย่อยที่ทำกำไรระดับ 30%+/เดือนต่อเนื่อง; กลุ่มที่ดีที่สุด (top 500 จาก ~450,000/ปี) ได้ ~8%/เดือน — [Barber et al. 2014](https://www.sciencedirect.com/science/article/pii/S1386418113000190)
- หลักฐานภายในโครงการเอง (ทดสอบด้วยแท่งเทียนที่มี wick, funding และ ruin rate ไม่ใช่แค่ราคาปิดรายวัน): ที่ 20x ทำได้ 6x ใน **18–25% ของเดือน แต่ถูกล้างพอร์ต 54–66%** → กติกาของโครงการคือ "ห้ามดูเลเวอเรจจากราคาปิดอย่างเดียว" — `research/LESSONS.md` ข้อ 6
- สถานะโครงการ ณ 24 พ.ย. 2026: ยังไม่มีวิธีใดที่พิสูจน์ได้ว่าทำกำไรเกินการสุ่ม และเจ้าของเลิกยึดเป้า 3 เท่า/เดือนเป็นข้อสรุปแล้ว (`HANDOFF_3X_PROMPT.md` หัวข้อ "สถานะล่าสุด") → บันทึกนี้ควรถูกใช้เป็น **เพดานอ้างอิงและข้อกำหนดความเสี่ยง** ไม่ใช่การวิพากษ์เป้าเก่า
- prop firm ซึ่งคัดกรองคนที่ "อยากเทรดเป็นอาชีพ" แล้ว: 7% ได้ payout, payout เฉลี่ย 4% ของขนาดบัญชี, median อายุบัญชี 0.8 วัน — [Select Prop Firms](https://selectpropfirms.com/prop-firm-statistics/); [The Prop Journalist](https://thepropjournalist.com/analysis/prop-firm-pass-rates/)
- ต้นทุนซื้อขายเป็นตัวกำหนดผลลัพธ์มากกว่า "ทักษะ": ไต้หวัน gross −7 bps → net −23.9 bps — [Barber et al. 2020](https://academic.oup.com/raps/article-abstract/10/1/61/5545095)
- การจำกัด leverage ปรับปรุงผลตอบแทนของกลุ่มที่ใช้ leverage สูงที่สุดได้จริง ~18 pp/เดือน — [Heimer & Simsek (2019)](https://www.sciencedirect.com/science/article/pii/S0304405X18303076)

### Inferences
- ตัวเลข $147 ที่ "โตเป็น $441 ในเดือนเดียว" เป็น **ผลของ right tail ไม่ใช่ความคาดหวัง**: P(เกิด) อยู่ที่ 0.4% (ถ้ามี edge จริง 5%/เทรด) ถึง 8.7% (ถ้า overbet 2× Kelly) และในกรณีหลัง median ติดลบ
- สำหรับบัญชีขนาดนี้ **ค่าเสียโอกาสและต้นทุนการเรียนรู้นั้นถูก** ($147) แต่ **ต้นทุนทางสถิติแพง**: ต้องใช้ ~380–2,400 เทรดเพื่อยืนยัน edge ซึ่งที่ 3 เทรด/วัน = 4–26 เดือน — นานกว่าที่บัญชีส่วนใหญ่จะมีชีวิตอยู่
- ข้อสรุปที่ honest ที่สุด: $147 ไม่ใช่ "บัญชีทำกำไร" แต่เป็น **ค่าธรรมเนียมการเข้าถึงข้อมูลจริงของตัวเอง**; มูลค่าของมันคือ variance ของผลลัพธ์และคุณภาพของบันทึก ไม่ใช่ yield

### Gaps
- ไม่มีงานศึกษาเฉพาะเจาะจงบัญชี <$500 ที่วัดผลจริง → ตัวเลขทั้งหมดสำหรับ $147 มาจาก (ก) งานประชากรขนาดใหญ่ที่ aggregate แล้ว และ (ข) การจำลองของผู้เขียนบันทึกนี้
- ไม่มีข้อมูลค่าธรรมเนียม/funding เฉพาะ broker ที่ $147 (ขึ้นกับประเทศและสินทรัพย์) → ตารางต้นทุนใช้ 0.10%/round trip ของ notional ซึ่งเป็นค่าตัวอย่างสำหรับ crypto perp taker; FX spread จะต่ำกว่าแต่มี swap
