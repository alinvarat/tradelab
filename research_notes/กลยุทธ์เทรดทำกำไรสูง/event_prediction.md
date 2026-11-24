# Event-Driven & Prediction-Market Strategies — บันทึกวิจัย (ณ 24 พ.ย. 2026)

ขอบเขต: บัญชีจำลองขนาดเล็ก, public data เท่านั้น, ไม่เปิดบัญชีจริง. ทุกตัวเลขเป็น "ก่อน/หลังต้นทุน" ตามที่ระบุไว้ในแต่ละบรรทัด. หมายเหตุสำคัญ: งานวิชาการส่วนใหญ่เป็น in-sample, ข้อมูลสหรัฐ, ช่วงก่อน 2015 และคิดต้นทุนต่ำ/ไม่คิด — ต้องอ่านคู่กับหลักฐาน "หลังต้นทุน" ที่ใส่ไว้ท้ายแต่ละหัวข้อ.

อ่านคู่กับ **หัวข้อ 9** ซึ่งระบุว่าอะไรในที่นี้ทับซ้อนกับงานที่ TradeLab ปิดไปแล้ว (FOMC next-session, Polymarket 490 ตลาด, GDELT ที่ถูกบล็อก, event trader หุ้นใหญ่ +5%) — ห้ามนำข้อสมมติฐานไปรันซ้ำในรูปแบบเดิม.

---

## 1. Corporate events: drift ตัวไหนรอดหลังหักต้นทุน และเร็วแค่ไหน

### Takeaway
PEAD แบบคลาสสิก "ตายแล้ว" สำหรับหุ้นใหญ่ (เหลือแต่ microcap ที่ซื้อขายจริงไม่ได้กำไร) — edge ที่ยังวัดได้ชัดคือ **reaction ใน 1–3 วันของ insider Form 4 ใน microcap** และ **spread ของ merger arb** ซึ่งทั้งคู่ถูกกัดด้วย spread/ต้นทุนจนเหลือน้อยมากสำหรับบัญชีเล็ก. Index inclusion และ spinoff เป็น event ที่ตลาด price ไปเกือบหมดแล้ว.

### Cited Findings

**PEAD (post-earnings announcement drift)**
- ภาพรวมงานเก่า: abnormal return 2.6%–9.37% ต่อไตรมาสตามผู้แต่ง שונים; EAR strategy ให้ 7.55%/ปี และ EAR+SUE ~12.5%/ปี ใน sample 1987–2004 — [Quantpedia / Brandt et al.](https://quantpedia.com/strategies/post-earnings-announcement-effect); [Sojka, "50 Years in PEAD Research"](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3281679)
- Martineau (2022) "Rest in Peace Post-Earnings Announcement Drift": drift เริ่มหายจากหุ้น non-microcap ปี 2001 และหายสนิทราวปี 2006; อธิบายด้วย decimalization + Reg NMS + HFT — สรุปโดย [UCLA Anderson Review, 21 ม.ค. 2026](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/)
- Replication ของ Subrahmanyam (ก.พ. 2001–ธ.ค. 2024): earnings-drift factor t = 2.18 เมื่อรวมทุกหุ้น แต่ t = 1.43 เมื่อตัด microcap ออก → "PEAD ที่เหลือคือ microcap effect" — [UCLA Anderson Review](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/)
- Hedge PEAD ลดลง ~2 basis point ต่อไตรมาส: จาก 6.24% (เริ่ม 1974Q2) → ~3% ปลายทศวรรษ 2010 → แยกจากศูนย์ไม่ได้หลังปี 2017; สาเหตุหนึ่งคือ SUE persistence ลดลง (ไม่ใช่แค่ arbitrage) — [Kettell, McInnis & Zhao, เม.ย. 2022 (Columbia CEASA PDF)](https://business.columbia.edu/sites/default/files-efs/imce-uploads/CEASA/Events%20Page/PEAD_Declined_over_time.pdf)

**Insider filings (SEC Form 4, code P)**
- 13,534 บรรทัด / 1,192 ผู้ออก / 2018–2024, mcap $30–500M: abnormal return วันที่ 1 หลังยื่น = **4.13%** ใน quintile ที่ราคาต่ำกว่า 52-week high มากที่สุด เทียบ **0.86%** ใน quintile ใกล้ high (two-way t = 9.77); วันปกติของหุ้นเดียวกัน = 0.14% — [Zhao, arXiv:2602.06198v2, ก.ย. 2026](https://arxiv.org/abs/2602.06198)
- ปฏิกิริยาวิ่งต่อ 2–3 session; drift วันที่ 2–30 "ไม่แม่น" (t = 1.70) และ **calendar-time portfolio ที่ข้ามวันแรกได้ alpha ไม่มีนัยสำคัญ** — [arXiv:2602.06198](https://arxiv.org/abs/2602.06198)
- ต้นทุน/สภาพคล่องของ sample นี้: median mcap $209.6M, median ADDV เพียง **$910k/วัน**, median มูลค่าซื้อ $45,400 → spread 1–3% กินกำไรเกือบหมด; ผู้เขียนสรุปตรง ๆ ว่า "ไม่ได้ establish trading rule ที่ทำกำไร" — [arXiv:2602.06198](https://arxiv.org/abs/2602.06198)
- งานอื่นวัดปฏิกิริยา 5 วันหลังยื่น Form 4 ประมาณ **2%** (มีนัยสำคัญ) — [Columbia Blue Sky Blog, 22 ก.ย. 2026](https://clsbluesky.law.columbia.edu/2026/09/22/when-are-insider-purchases-credible-signals-of-private-information)
- กติกาเวลา: Form 4 ต้องยื่นภายใน 2 business days; acceptance time ก่อน/หลัง 16:00 ET ตัดสินว่าปฏิกิริยาเกิดวันยื่นหรือวันถัดไป (ผ่าน overnight gap) — [arXiv:2602.06198](https://arxiv.org/abs/2602.06198)

**M&A / merger arbitrage**
- Goldman Sachs (ต้น ส.ค. 2025): median annualized US merger-arb spread **7.7%** (เฉพาะดีลที่ประกาศแล้ว); spread เคยกว้างชั่วคราวเมื่อ เม.ย. 2025 — [Carmignac](https://carmignac.com/en/articles/bumps-are-back-terminations-low-stars-align-for-merger-arbitrage-3412-11786)
- UBS (สิ้นปี 2025): median annualized spread ~**4%** ในสหรัฐ — [Carmignac, Q4 2025](https://carmignac.com/en-fi/articles/carmignac-portfolio-merger-arbitrage-plus-letter-from-the-fund-managers-q4-2025-3610-12632)
- 1,200 ดีลสหรัฐ 2000–2025: ~0.85%/เดือน ≈ **7.5%/ปีหลังต้นทุน** (ตามผู้วิเคราะห์) — [Finexus](https://api.finexus.net/api/news/events/e6b6a4e2-166d-4b80-af38-76d1c5507fb3/html)
- ขนาด premium: UK 2025 average bid premium ~46% เทียบราคาก่อน offer period แต่เพียง ~12% เมื่อคิดจาก 30-day average → ตัวเลข premium ขึ้นกับฐานที่ใช้มาก — [DealAcademy, 13 ส.ค. 2026](https://dealacademy.co.uk/blog/premiums-paid-analysis-explained); [LexisNexis UK M&A 2025](https://www.lexisnexis.co.uk/insights/market-standards-trend-report-trends-in-uk-public-m-a-deals-in-2025/index.html)
- ความเสี่ยงแบบ binary: ดีลล้ม = ขาดทุนเกือบเต็ม spread + gap; ไม่มี stop ที่มีความหมาย

**Spinoffs**
- 623 ดีล 38 ประเทศ 2000–2024: 3-day CAR **2.64%** (อเมริกาเหนือ 3.03%, เอเชียแปซิฟิก 2.02%, ยุโรปตะวันตก 2.19%) — [Aalto thesis, 2026](https://aaltodoc.aalto.fi/handle/123456789/147211)
- 206 ดีลยุโรป 2000–2025: 3-day CAR **3.77%** — [Aalto 2025](https://aaltodoc.aalto.fi/items/8f80bd51-ae74-499b-b338-3b53c3d82223/full)
- 140 ดีลสหรัฐ 2010–2022: CAR **3.63%**; **ไม่มี abnormal return 36 เดือนหลัง completion** ทั้ง parent และ spun-off — [Aalto 2023](https://aaltodoc.aalto.fi/items/2205e355-7665-4f76-94ff-034354473fd6)
- 249 ดีลสหรัฐ 2007–2017: CAR(-1,+1) = **3.06%**, CAR ตลอดช่วงถึง completion = 4.10% — [Nature Humanities & Social Sciences Comm., 2021](https://www.nature.com/articles/s41599-021-00807-9)

**Index inclusion/deletion**
- Abnormal return ของหุ้นที่ถูกเพิ่มเข้า S&P 500 ลดจาก **7.4% (ทศวรรษ 1990) → 0.3% ในทศวรรษล่าสุด** — [HBS working paper 23-025](https://hbs.edu/ris/download.aspx?name=23-025.pdf)
- อีกเวอร์ชัน: 3.4% (1980s) → 7.6% (1990s) → **0.8%** ในทศวรรษล่าสุด; หุ้นที่ถูกตัดออกเคยติดลบหนักในยุค 1990 แต่เหลือ **0.1% ช่วง 2010–2020** — [NBER w30748, "The Disappearing Index Effect"](https://nber.org/system/files/working_papers/w30748/w30748.pdf)
- สรุปจาก S&P DJI เอง: median excess return ทั้งช่วง announcement→effective ลดลงทั้งสองกลุ่ม — [S&P DJI research](https://www.spglobal.com/spdji/en/documents/research/research-what-happened-to-the-index-effect.pdf)

**FDA / PDUFA**
- 534 การตัดสินใจ 2024–26: median absolute move (วันตัดสินหรือวันถัดไป) = **14.1%** nano-cap (<$50M), 7.2% micro, 5.8% small, 4.1% mid, **1.5%** large (>$10B) — [pdufa.bio, อัปเดต 21 พ.ย. 2026](https://pdufa.bio/research/pdufa-stock-run-up-by-market-cap)
- Run-up T-120 (median): **+34.6%** nano, +20.1% micro, +3.4% small, +13.3% mid, +7.4% large — ผู้เขียนเตือนว่า noisy และไม่เรียงตามขนาดจริง — [pdufa.bio](https://pdufa.bio/research/pdufa-stock-run-up-by-market-cap)
- 92 เหตุการณ์ที่มีข้อมูลราคา: เฉลี่ย **−1.9% ในวันตัดสิน** และ **−3.6% ใน 5 วันถัดมา** (ค่าเฉลี่ย ไม่ใช่ median; ถูกดึงด้วย CRL และ small cap) — [BioRadar](https://bioradar.io/how-biotech-stocks-move-around-fda-decisions)
- PDUFA คือ "goal date" ไม่ใช่เวลาประกาศ; FDA ตัดสินก่อน/หลัง/ตรงวันได้ และไม่มีการันตีเวลา — [Tradar](https://trytradar.com/blog/do-stocks-go-up-after-fda-approval)

**Contract awards**
- หลักฐานเก่า/บาง: งานปี 2002 ใน Journal of Public Procurement ศึกษาปฏิกิริยาราคาต่อการประกาศรับcontractรัฐ vs เอกชน — [Emerald, JoPP 2002](https://emerald.com/insight/content/doi/10.1108/jopp-02-02-2002-b004/full/html)
- งาน 2024 (Ferris et al.) วัด CAR รอบการประกาศสัญญารัฐขนาดใหญ่และวิเคราะห์ผ่าน DuPont — [PDF](https://blakerayfield.com/publication/government_contracts/J_Corp_Accounting%20Finance%20-%202024%20-%20Ferris%20-%20Corporate%20Value%20Creation%20and%20the%20Award%20of%20Procurement_Contracts.pdf)
- ไม่พบงาน 2020–2026 ที่วัด drift หลังประกาศสัญญารัฐแบบ after-cost ที่เชื่อถือได้ → อยู่ใน Gaps

### Inferences
- PEAD ที่ยัง trade ได้จริงคือ microcap/nano-cap ซึ่ง **ต้นทุน spread + market impact สูงกว่า edge** สำหรับบัญชีเล็ก; การเอา PEAD ไปใช้กับ large cap ในปี 2026 เท่ากับเทรดสัญญาณที่ t < 1.5.
- Insider Form 4 เป็น event ที่ **timestamp ชัดที่สุด** ในกลุ่ม corporate (acceptance time ระบุวินาที) แต่กำไรส่วนใหญ่อยู่ใน overnight gap ที่คนเห็น filing หลังปิดตลาดไม่ได้; ส่วนที่เหลือ (2–3 session) คือของที่ต้องแข่งกับ spread 1–3%.
- M&A arb ให้ผลตอบแทนคาดหวัง 4–8%/ปี แต่ distribution เป็น "เก็บเล็กบ่อย ๆ เจ็บหนักครั้งเดียว" — เหมาะกับ basket ไม่เหมาะกับ 1–2 ดีลในบัญชีเล็ก.
- Index effect หายไปแล้วอย่างมีนัยสำคัญ → ใช้เป็น **falsification test** ของ data pipeline ได้ (ถ้ากลยุทธ์ทำเงินจาก index add ในปี 2026 แปลว่า pipeline มี look-ahead).

### Gaps
- ไม่พบตัวเลข after-cost ที่ทันสมัยของ PEAD ในตลาดเกิดใหม่/ตลาดไทย (ส่วนใหญ่งาน US).
- ไม่พบ event study ที่เชื่อถือได้ของ **spinoff completion drift** หลังปี 2020 (งานส่วนใหญ่หยุดที่ 2022).
- ไม่มีหลักฐานชัดของ **guidance change / 8-K Item 2.02** แยกจาก earnings surprise; งานส่วนใหญ่รวมเป็น PEAD.
- Contract awards: ไม่มีตัวเลข CAR/drift 2020–2026 ที่ตรวจสอบได้.
- ไม่มีข้อมูลว่า retail API (เช่น broker ไทย) เห็น Form 4 ช้ากว่า acceptance time เท่าไร.

---

## 2. Macro events: FOMC / CPI / NFP — อะไรถูก price ไปก่อนแล้ว

### Takeaway
**Pre-FOMC drift ตายไปหลังปี 2015** และ **event-day option pricing โดยเฉลี่ย "fair"** (priced 1.31× เทียบ moved 1.30× ของวันปกติ) → ทั้ง drift และ long-vol แบบไม่เงื่อนไขไม่มี edge เหลือ. สิ่งที่ยังเป็นไปได้คือ **drift แบบมีเงื่อนไขความไม่แน่นอน (VIX สูง)** ซึ่งเป็นกลไกที่งานวิจัยต้นทางเสนอเอง.

### Cited Findings
- Pre-FOMC drift เดิม: +**49 bp** ใน 24 ชม. ก่อนประกาศ (ก.ย. 1994–มี.ค. 2011) คิดเป็น ~80% ของ equity premium ทั้งปี — [Lucca & Moench, J. Finance 2015 ผ่าน NY Fed LSE](https://libertystreeteconomics.newyorkfed.org/2018/11/the-pre-fomc-announcement-drift-more-recent-evidence/)
- หลังปี 2011 ค่าเฉลี่ยเหลือ **4.7 bp** (SE 6.0) เทียบวันปกติ 3.8 bp; แยกช่วง มี.ค. 2011–ธ.ค. 2015 ได้ 44.5 bp แต่ **ม.ค. 2016–ธ.ค. 2019 เหลือ 9.2 bp** (Wilcoxon p<0.01 ว่าค่ามัธยฐานต่างกัน) — [Kurov, Wolfe & Gilbert, Finance Research Letters 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC7525326/)
- คำอธิบาย: drift สัมพันธ์กับ VIX (coef 0.229, t~3.3); VIX เฉลี่ย 17.7 ก่อน ZLB liftoff → 14.7 หลัง → [Kurov et al. 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC7525326/)
- เวลาที่แน่นอน: FOMC statement **14:00 ET** ตั้งแต่ มี.ค. 2013; press conference **14:30 ET**; ก่อนหน้านั้น 12:30/14:15 — [NY Fed LSE, 26 พ.ย. 2018](https://libertystreeteconomics.newyorkfed.org/2018/11/the-pre-fomc-announcement-drift-more-recent-evidence/)
- CPI ถูกจัดเป็น release ที่กระทบมากที่สุด; β ของ index futures ต่อ CPI surprise = **−0.3386** (แรงกว่า NFP) — [SSRN 7403718, intraday event study](https://papers.ssrn.com/sol3/Delivery.cfm/7403718.pdf?abstractid=7403718&mirid=1)
- CPI ประกาศ **08:30 ET**; งาน Fed วัดว่า CPI มี impact 26% ของความแปรปรวนใน 30 นาทีแรก (ตารางในกระดาษ) — [Fed FEDS 2025-022](https://federalreserve.gov/econres/feds/files/2025022pap.pdf)
- ORATS WHAM (16 พ.ค. 2022–17 พ.ย. 2026, 1,109 วัน): 136 วัน Fed/CPI/NFP ถูก price ที่ **1.31× วันปกติ** และเคลื่อนจริง **1.30×**; คิดเป็น "moved/priced" = **0.99** (p = 0.88 จากการ reshuffle 20,000 ครั้ง) → ตลาด option price event day ได้แม่นมาก — [ORATS ผ่าน IBKR, 19 พ.ย. 2026](https://www.interactivebrokers.com/campus/ibkr-quant-news/sp-500-options-fed-cpi-and-jobs-days-moved-about-as-much-as-priced/)
- ข้อยกเว้นเล็กน้อย: RUT (ตั้งแต่ 2024) moved น้อยกว่า priced ~16% (p=0.10); วันจันทร์ moved น้อยกว่า priced 15–18% (p=0.03) — [ORATS](https://www.interactivebrokers.com/campus/ibkr-quant-news/sp-500-options-fed-cpi-and-jobs-days-moved-about-as-much-as-priced/)
- หลักฐานสวนทาง (regime-specific): 12 รายงาน CPI ถึง ก.พ. 2025 — 1-day ATM straddle ของ NDX/SPX overpriced เพียง 4/12 ครั้ง; ผู้ขาย straddle ขาดทุนสุทธิ — [Nasdaq, 11 ก.พ. 2025](https://www.nasdaq.com/articles/ndx-straddle-buyers-love-cpi-day-volatility)
- ทางกลับกัน เม.ย. 2026: 8/12 ครั้งที่ straddle underpriced; JPM desk price CPI-day implied ~1.0–1.1% ขณะ actual เฉลี่ย 0.72% — [Monaco Macro, 7 เม.ย. 2026](https://monacomacro.substack.com/p/the-cpi-coiled-spring-why-friday) (เป็นบล็อก ไม่ใช่ peer-reviewed)
- มีงานเรื่อง **pre-announcement drift ก่อนข่าวมหภาคสหรัฐ** (private information about public announcements) — [ECB WP 1901](https://www.ecb.europa.eu/pub/pdf/scpwps/ecbwp1901.en.pdf) (ดึง PDF ไม่สำเร็จ; อ้างจากชื่อ/หัวข้อเท่านั้น)

### Inferences
- ตัวเลข "priced 1.31× / moved 1.30×" คือหลักฐานเชิงประจักษ์ว่า **การซื้อ straddle ก่อน CPI/FOMC แบบไม่มีเงื่อนไขไม่มี edge หลังต้นทุน** และการขายก็ไม่มี edge เช่นกัน — alpha ต้องมาจากการ forecast surprise ไม่ใช่จาก vol.
- การที่ drift หายไปพร้อม VIX ที่ลดลงบอกว่า **edge เป็นฟังก์ชันของ uncertainty ไม่ใช่ของปฏิทิน** → กลยุทธ์ที่คิดจาก "วัน FOMC" เฉย ๆ จะ fail out-of-sample.
- CPI แรงกว่า NFP ประมาณ 2–3 เท่าในเชิง coefficient → ถ้าจะเลือก เหตุการณ์ เดียว ให้เลือก CPI.
- สำหรับบัญชีเล็ก ต้นทุนของ option (spread + ค่าธรรมเนียม) กิน edge ที่เหลืออยู่แล้วในกรณีที่ดีที่สุด.

### Gaps
- ไม่มีตัวเลข "residual move ที่ tradeable" หลัง 30 นาทีแรก ของ CPI/NFP สำหรับปี 2023–2026 (งานส่วนใหญ่หยุดที่ 2022).
- ไม่พบข้อมูล consensus/nowcast ฟรีที่แม่นพอจะคำนวณ surprise แบบ real-time (BLS ไม่เผยแพร่ consensus; ต้องใช้ Bloomberg/Reuters).
- ไม่มีหลักฐานชัดเรื่อง tariff/geopolitical shock drift หลัง 2025 (งานส่วนใหญ่เป็น case study).
- ECB WP 1901: ไม่สามารถยืนยันรายละเอียดเชิงตัวเลขได้ (PDF ถูกบล็อก).

---

## 3. Prediction markets (Polymarket / Kalshi): fees, liquidity, resolution, arbitrage, longshot bias

### Takeaway
**Taker fee ที่ 50¢ คือ 2.5% (Polymarket) ถึง 3.5% (Kalshi) ของเงินที่วาง** → กลยุทธ์ taker ไป-กลับกลาง book ขาดทุนเกือบแน่นอน; **cross-venue arbitrage ที่ retail = 0 จาก 15 ตลาด**; edge เดียวที่วัดซ้ำได้คือ **favorite–longshot bias** แต่กำไรฝั่ง favorite เพียง ~0.3–0.8% ต่อไม้ และหายไปใน sports.

### Cited Findings

**Fee structure (สำคัญที่สุด)**
- Polymarket: taker fee = `C × rate × p × (1−p)`; **maker = 0 เสมอ**. Rate ตามหมวด: crypto 5/15-min 0.05, crypto อื่น 0.01, sports 0.05, finance 0.05, tech 0.05, politics-เลือกตั้ง 0.05, politics อื่น 0.01, economics 0.01, culture 0.01, weather 0.01, **geopolitics 0**, combos 0.05 — [Polymarket docs, ดึง 24 พ.ย. 2026](https://docs.polymarket.com/trading/fees)
- Fee peak ที่ p = 0.50 = **$1.25 ต่อ 100 shares** (ไม่ใช่ $1.25 ต่อ $100) → บน stake $50 = **2.5%**; ที่ p = 0.10 fee/stake = 0.01×0.9 = **0.9%**; ที่ p = 0.90 = **0.1%** — คำนวณจากสูตรเดียวกับ [docs](https://docs.polymarket.com/trading/fees)
- Kalshi: taker = `0.07 × C × p × (1−p)` ปัดขึ้นเป็น cent, ช่วง **$0.07–$1.75 ต่อ 100 สัญญา**; maker = 0 ในseries ปกติ หรือ 25% ของ taker ใน series ที่กำหนด (NFL) และ 1/8 (MLB) — [Kalshi fee schedule](https://kalshi.com/fee-schedule); [Kalshi Help, 19 เม.ย. 2026](https://help.kalshi.com/en/articles/13823805-fees)
- แปลว่า max ที่ 50¢ = $1.75/$50 = **3.5% ของ stake**; ไป-กลับ taker = 7% → taker-only ต้องชนะ >7% ต่อรอบจึงจะคุ้ม
- มีการเปลี่ยนโครงสร้าง พ.ย. 2026 (taker fee + maker rebate เป็นทางการ) — [Polymarket changelog](https://docs.polymarket.com/programs/fee-and-rebate-changes-november-2026)

**Liquidity / capacity**
- 30 วันถึง 21 พ.ย. 2026: Kalshi **$117.88B** notional (84.3% share), Polymarket US $16.40B, Polymarket international $5.58B; OI 23 พ.ย. 2026: Kalshi **$1.39B**, Polymarket international **$311.1M** — [Castle Labs, 17 พ.ย. 2026](https://castlelabs.io/research/prediction-markets)
- OI แยกหมวด (Kalshi / Polymarket): politics & world $535.9M / $186.2M; sports $647.3M / $18.7M; **economy & finance เพียง $85.0M / $21.6M** — [Castle Labs](https://castlelabs.io/research/prediction-markets)
- Turnover: politics/elections = 0.95× ต่อสัปดาห์ (ถือยาว), crypto 13.15×, sports 9.46×, economics 0.59× → ตลาด macro/politics มี OI แต่หมุนช้า — [VIP-Grinders, พ.ย. 2026](https://www.vip-grinders.com/research/prediction-markets-report/)
- ตัวอย่าง depth จริง: Kalshi NYK YES มี 4.65M สัญญา bid ที่ $0.01 และ NO 8.15M ที่ $0.01 (boundary stub) — [microstructure repo](https://github.com/adityanbhosale/kalshi-polymarket-microstructure)

**Cross-venue arbitrage**
- 16 ตลาด cross-listed (NBA Finals, US Senate, Colombia/Peru/Seoul/LA elections, M&A), 30-second poller >14 ชม., 1,748 snapshots: **0 จาก 15 ตลาดที่มีข้อมูล มี takeable arb ที่ fee tier retail**; maker rebate ไม่ช่วยให้มี — [adityanbhosale/kalshi-polymarket-microstructure, พ.ค. 2026](https://github.com/adityanbhosale/kalshi-polymarket-microstructure)
- Fee cliff อยู่ที่ **~0.30% taker / 0.20% maker rebate** (ระดับ institutional ที่ไม่มีใครเข้าถึง); ที่ระดับนั้น 8 ตลาดมี edge median **$190.82/snapshot** — เป็น counterfactual ไม่ใช่ของจริง — [repo เดียวกัน](https://github.com/adityanbhosale/kalshi-polymarket-microstructure)
- Liquidity provision ก็ไม่รอด: post-fill markout ที่ 5 นาที **ติดลบทุกตลาด** → spread ที่เห็นคือ adverse selection ไม่ใช่ edge — [repo](https://github.com/adityanbhosale/kalshi-polymarket-microstructure)
- ราคาข้าม venue converge ได้เองโดยไม่มี arb (OKC: 1.00¢ → 0.50¢ → 0.00¢ ใน ~22 ชม.) → market maker ฝั่งหนึ่งอ่านอีกฝั่ง — [repo](https://github.com/adityanbhosale/kalshi-polymarket-microstructure)
- มีงานศึกษา **settlement asymmetry** ระหว่าง Kalshi กับ Polymarket โดยใช้เหตุการณ์โจมตีอิหร่าน 28 ก.พ. 2026 เป็น natural experiment → กฎ settlement ต่างกันจำกัดการ reprice ข้าม venue — [SSRN 6704139, "Kalshi's Ceiling"](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6704139) (อ่านได้แค่ abstract)
- งาน 2.6M ตลาดถึง 19 ก.ค. 2026: ที่ sampling รายชั่วโมง ราคาเคลื่อน **39% มากกว่า** ความไม่แน่นอนที่ถูก resolve — [SSRN 7705802](https://ssrn.com/abstract=7705802) (abstract เท่านั้น; SSRN บล็อก 403)

**Favorite–longshot bias (FLB)**
- 588M trades, 2.48M wallets, 11 พ.ย. 2022–29 มี.ค. 2026, $23.67B ซื้อ: ซื้อที่ราคา **<10¢ ขาดทุน −6.30%** (95% CI −8.38 ถึง −4.22) แบบ equal-weight ต่อ child market; **−19.35%** แบบ pooled; **+4.09%** เมื่อถ่วงน้ำหนักต่อ parent event — [Cardozo & Rivero-Wildemauwe, arXiv:2609.12878, 11 ก.ย. 2026](https://arxiv.org/abs/2609.12878)
- ซื้อที่ **≥90¢ ได้ +0.277%** (equal-child), **+0.83%** (pooled), **+0.392%** (parent-event) — [arXiv:2609.12878](https://arxiv.org/abs/2609.12878)
- หมวดที่เห็นสองด้านชัด: **Crypto และ Politics**; **Sports เป็นข้อยกเว้น — longshot ให้ผลบวก** ทั้งสองวิธี; Weather เปลี่ยนเครื่องหมายตาม weighting — [arXiv:2609.12878](https://arxiv.org/abs/2609.12878)
- ข้อสังเกตของผู้เขียน: การรวม child markets ที่สัมพันธ์กันซ้ำ ๆ ทำให้ผลเปลี่ยนเครื่องหมาย → "FLB" ขึ้นกับหน่วยนับ ไม่ใช่กฎสากล — [arXiv:2609.12878](https://arxiv.org/abs/2609.12878)
- งานแยก (1,902 ตลาด) อ้างว่า longshot ชนะบ่อยกว่าที่ price 2.2 เท่าใน bucket 0–5% — [polymarkettrader.com](https://polymarkettrader.com/odds/longshot-bias) (ข้อมูล experiential, ไม่ใช่ peer-reviewed; ขัดกับงานข้างบน → ระวัง)

**Resolution / counterparty risk**
- Polymarket international = on-chain, ใช้ UMA oracle ตัดสิน; Polymarket US = CFTC-regulated DCM (QCX LLC) แยกผลิตภัณฑ์ — [VIP-Grinders](https://www.vip-grinders.com/research/prediction-markets-report/)
- Kalshi = CFTC-regulated exchange, มี clearinghouse → counterparty risk ต่ำกว่า แต่ resolution ขึ้นกับ rulebook ของแต่ละ series
- มีกรณีราคาในตลาด "lighthouse mode" (bid 0.001/ask 0.999) และการ delist หลังผลรู้แล้วบน Polymarket ขณะ Kalshi ยัง quote ต่อ — [repo](https://github.com/adityanbhosale/kalshi-polymarket-microstructure)

### Inferences
- ด้วย fee 2.5–3.5% ที่กลาง book, **strategies ที่ต้อง taker 2 ขาเป็นไปไม่ได้ในทางคณิตศาสตร์** เว้นแต่ edge > 5–7% ต่อรอบ — ซึ่งมีเฉพาะตอน resolution ข่าวใหญ่ และตอนนั้น liquidity หาย.
- FLB ฝั่ง favorite (+0.28% ถึง +0.83%) **รอดค่า fee** เพราะ fee/stake ที่ p=0.95 มีเพียง 0.05% (Polymarket) → net ~+0.23% ถึง +0.78% ต่อไม้; แต่ต้อง hold ถึง resolution (duration เป็นเดือน) → annualized ไม่สูงอย่างที่คิด และ Capital ถูก lock.
- FLB ฝั่ง longshot (−6% ถึง −19%) เป็น **ค่าเช่าทางพฤติกรรม** ไม่ใช่ arbitrage: การขาย longshot = ซื้อ NO ที่ราคา >90¢ ซึ่งมี liquidity ตื้นกว่าฝั่ง YES มาก.
- Cross-venue "arb" ที่เห็นใน Twitter/Reddit ส่วนใหญ่เป็น **paper mid discrepancy** ไม่ใช่ executable; งานเดียวที่วัด depth จริงเจอ 0/15.

### Gaps
- ไม่มีตัวเลข **after-fee net return** ของ FLB ในงานต้นทาง (ผู้เขียนบอกเองว่าคำนวณก่อน fee และก่อนเวลา).
- ไม่มีข้อมูล capacity ต่อตลาด (depth ที่ ±1¢) สำหรับ macro/financials events — OI รวมเท่านั้น.
- ไม่พบงานที่วัด **resolution risk premium** (ราคา fair ควรหักความน่าจะเป็นที่ oracle ตัดสินผิด) เป็นตัวเลข.
- งาน SSRN 7705802 / 6704139 อ่านได้แค่ abstract → รายละเอียด ระเบียบวิธี ยังไม่ยืนยัน.

---

## 4. ข้อจำกัดของบัญชีเล็ก (simulation only)

### Takeaway
ข้อจำกัดที่ผูกพันจริงไม่ใช่เงินทุน แต่คือ **(ก) minimum stake/ขนาดสัญญา, (ข) fee ที่เป็น % ของ stake, (ค) ระยะเวลา lock capital, (ง) KYC/ภูมิศาสตร์**. บัญชีเล็กได้เปรียบเรื่อง capacity แต่เสียเปรียบเรื่อง minimum tick และ dilution ของค่าธรรมเนียม.

### Cited Findings
- Polymarket international: **ไม่ต้อง KYC** (email/Google/wallet); limit order ขั้นต่ำ **5 shares**, market order ขั้นต่ำ **$1** — [startpolymarket, 2026](https://startpolymarket.com/guides/polymarket-for-crypto-traders) (แหล่ง secondary)
- Polymarket: ไม่มีค่า deposit/withdraw ของแพลตฟอร์ม แต่ intermediary (Coinbase/MoonPay/bridge) คิดเอง; bridge ขั้นต่ำ ~$2 บน Polygon, $7 Ethereum, $9 Bitcoin/Tron — [gamblebetscout review 2026](https://gamblebetscout.com/review/polymarket) (secondary)
- Polymarket US ต้อง KYC เต็มรูปแบบ (SSN) เพราะเป็น DCM ภายใต้ CFTC — [Polymarket US docs](https://docs.polymarket.us/partners/get-connected/quickstart); [gamblebetscout](https://gamblebetscout.com/review/polymarket)
- Kalshi: CFTC-regulated, ใช้ USD, KYC; สัญญา granularity $1 → ขนาดไม้เล็กทำได้ — [Kalshi regulatory](https://kalshi.com/regulatory)
- Polymarket international ถูก block ในสหรัฐ; พลเมืองสหรัฐต้องใช้ Polymarket US — [VIP-Grinders](https://www.vip-grinders.com/research/prediction-markets-report/)
- ความเสี่ยงแยกตาม venue: Polymarket intl = smart contract + oracle (UMA); Kalshi = exchange/clearinghouse; Polymarket US = DCM — [VIP-Grinders](https://www.vip-grinders.com/research/prediction-markets-report/)

### Inferences
- สำหรับบัญชีจำลองเล็กระดับ $1k–$10k: จำนวนไม้ที่ทำได้จริงคือ **หลักสิบถึงหลักร้อยสัญญา** — เพียงพอต่อการทดสอบ statistical edge แต่ไม่พอต่อการ diversify ข้ามเหตุการณ์.
- Minimum 5 shares ที่ราคา 5¢ = $0.25 → ต่ำมาก; แต่ fee ขั้นต่ำ 0.00001 USDC ทำให้ไม้จิ๋ว "fee-free" โดยพฤติกรรม (ไม่ใช่เชิงเศรษฐกิจ).
- ภาษา/ภูมิศาสตร์: การใช้ Polymarket international จากไทยทำได้ทางเทคนิค แต่ความเสี่ยงทางกฎหมาย/การถอนเงินเป็นของผู้ใช้; ห้ามตีความบันทึกนี้เป็นการแนะนำให้เปิดบัญชี.

### Gaps
- ไม่มีตัวเลขค่าธรรมเนียม on-ramp/off-ramp ที่แน่นอนสำหรับผู้ใช้ในไทย (ขึ้นกับวิธีและเชน).
- ไม่มีข้อมูล time-to-withdraw จริงของ Polymarket international ในปี 2026.
- ไม่มีข้อมูล tax treatment ของ event contracts สำหรับผู้มีถิ่นฐานนอกสหรัฐ.

---

## 5. แหล่งข้อมูลฟรี/ถูก: วันเวลาเหตุการณ์และ timestamp

### Takeaway
**EDGAR เป็นแหล่งเดียวที่ให้ timestamp ระดับวินาที (acceptanceDateTime) และ latency <1 วินาที** สำหรับ corporate events; macro มีเวลาตายตัว (08:30/14:00 ET) แต่ consensus ต้องซื้อ; FDA/PDUFA ไม่มีเวลาตายตัวและเป็นแหล่งที่ latency แย่ที่สุด; GDELT ให้ 15 นาที.

### Cited Findings
- EDGAR submissions API อัปเดต "real time" ตลอดวัน; submissions API มี processing delay **น้อยกว่า 1 วินาที** โดยปกติ — [SEC EDGAR API docs](https://sec.gov/edgar/sec-api-documentation); [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- `acceptanceDateTime` คือเวลาที่รับไฟล์; `filingDate` คือวันที่ทางกฎหมาย — ไฟล์ที่รับหลัง 17:30 ET และลงวันที่พรุ่งนี้จะถูกกันจาก feed ชั่วคราว — [edgar.tools, 2026](https://edgar.tools/blog/sec-filing-date-vs-acceptance-time)
- เอกสาร (HTML/PDF) อาจตามหลัง metadata เป็นชั่วโมง: index page สร้างพร้อม acceptance แต่การ upload ไฟล์ "could take hours" — [john-friedman/Reverse-Engineering-EDGAR](https://github.com/john-friedman/Reverse-Engineering-How-the-SEC-s-EDGAR-Works/blob/master/readme.md) (reverse engineering, ไม่ใช่เอกสาร SEC)
- มี bug ที่พบได้บ่อย: `acceptanceDateTime` คลาดเคลื่อนตาม ET offset ใน ~1/3 ของ 8-K (สายไป 4–5 ชม.) — [eBull issue #3714](https://github.com/Luke-Bradford/eBull/issues/3714) → ต้อง normalize timezone เอง
- Form 4 ต้องยื่นภายใน **2 business days** — [SEC rules อ้างใน arXiv:2602.06198](https://arxiv.org/abs/2602.06198)
- BLS/CPI/FOMC: 08:30 ET และ 14:00 ET ตามลำดับ (FOMC 14:00 ตั้งแต่ มี.ค. 2013, press conf 14:30) — [NY Fed LSE](https://libertystreeteconomics.newyorkfed.org/2018/11/the-pre-fomc-announcement-drift-more-recent-evidence/); [BLS schedule](https://www.bls.gov/schedule/)
- GDELT 2.0 Event + GKG อัปเดตทุก **15 นาที** ตลอด 24/7; GEG อัปเดตทุกนาที — [GDELT blog](https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime); [GDELT data](https://gdeltproject.org/data.html). **แต่ในสภาพแวดล้อมของโปรเจกต์นี้ GDELT ถูกปฏิเสธทุกคำขอ** (`research/LESSONS.md` ข้อ 8) → ห้ามออกแบบกลยุทธ์ที่พึ่ง GDELT; ใช้ "รอยเท้าของราคา" (gap + volume) แทน
- PDUFA: เป็น goal date ไม่มีเวลาประกาศ; FDA อาจประกาศก่อน/หลัง; ต้องใช้FDA press release + company 8-K — [Tradar](https://trytradar.com/blog/do-stocks-go-up-after-fda-approval); [pdufa.bio calendar](https://pdufa.bio/calendar)
- Index changes: S&P DJI ประกาศหลังปิดตลาด ปกติ effective ก่อนเปิดในวัน rebalance — [S&P DJI research](https://www.spglobal.com/spdji/en/documents/research/research-what-happened-to-the-index-effect.pdf)

### Inferences (announcement time vs retail API)
| Event | เวลาประกาศ | เวลาที่ retail เห็น (ประมาณ) | Leakage ที่เหลือ |
|---|---|---|---|
| Form 4 | acceptance ระดับวินาที | <1 วินาที (API) แต่ไฟล์ตามทีหลัง | overnight gap หายก่อนเปิด |
| 8-K/10-Q | acceptance | <1 วินาที metadata | บางครั้งมี leak ก่อนหน้า |
| CPI/NFP | 08:30:00 ET | ทันที (feed) | 0–30 วินาที; retail ช้ากว่า HFT |
| FOMC | 14:00:00 ET | ทันที | press conf 14:30 เป็น event ที่สอง |
| PDUFA/FDA | ไม่มีเวลา | เป็นชั่วโมงถึงวัน | สูงมาก; มัก leak ผ่าน adcomm |
| GDELT | — | 15–19 นาที | ใช้เป็น lagging confirmation เท่านั้น |

- สำหรับงานวิจัยนี้ **ใช้ acceptanceDateTime ของ EDGAR เป็น t0** และถือว่า retail เห็นช้ากว่า 0–60 วินาที; ถ้าผลลัพธ์ยังอยู่หลังหักค่านี้ แปลว่า edge ไม่ได้มาจาก latency.

### Gaps
- ไม่พบข้อมูล latency จริงของ broker/API ที่คนไทยใช้ (เช่น streaming ของ settrade/liberator) เทียบกับ EDGAR.
- ไม่มีเอกสาร BLS ที่ยืนยัน sub-second release mechanism (มีแค่เวลา 08:30).
- ไม่พบ API ฟรีที่ให้ consensus ของ CPI/NFP (ต้องใช้ Bloomberg/Reuters/LSEG หรือ scrape จาก news).

---

## 6. ข้อสมมติฐานที่ทดสอบได้ (2–3 ข้อ) พร้อมกฎเข้า/ออก, control, แหล่งข้อมูล

> ทั้งสามข้อออกแบบให้รันด้วยข้อมูลฟรี + simulated fills, มี kill criteria ชัด, และ **ไม่ใช้ real money**.

### H1 — Insider Form 4 microcap: จับเฉพาะ reaction หลังวันยื่น (continuation 2–3 session)
**สมมติฐาน:** หลังหัก spread แล้ว ปฏิกิริยาวันที่ 2–3 ของ Form 4 code P ใน microcap ที่ราคาต่ำกว่า 52-week high มาก ยังให้ผลบวกสุทธิ > 0.

- **Signal:** Form 4, transaction code P, accepted ก่อน 16:00 ET (เพื่อให้เข้าได้ทัน close วันเดียวกัน) หรือหลัง 16:00 (เข้า open วันถัดไป)
- **Universe filter:** mcap $30–500M; ราคา ≥ $5; ADDV30 ≥ $1M; มูลค่าซื้อต่อ insider ≥ $50k; ไม่มี 8-K concurrent (ตัด confounding)
- **Entry:** นาทีแรกที่ซื้อขายได้หลัง signal (close วันยื่น ถ้า before-close; open วันถัดไป ถ้า after-close) — **ห้ามใช้ราคา close ของวัน signal ถ้า signal มาหลัง close**
- **Exit:** close ของ session ที่ +2 (hold 2 วันทำการ) — ห้ามถือข้าม 30 วัน
- **Position size:** เท่ากันทุกไม้ (equal weight), cap 5% ของพอร์ตต่อชื่อ, สูงสุด 10 ชื่อพร้อมกัน
- **Costs:** สมมติ round-trip 3.0% (spread 1.5% + impact 1.0% + commission 0.5%) สำหรับ microcap — ถ้า net ≤ 0 ให้เพิ่มเป็น 4% เพื่อ stress
- **Control:** (ก) วันสุ่มของหุ้นเดียวกัน (non-event) แบบเดียวกัน; (ข) จับคู่ตาม mcap/volatility/ราคา; (ค) placebo: ใช้ Form 4 code S (ขาย) เป็น negative control
- **ข้อมูล:** [SEC EDGAR submissions API](https://sec.gov/edgar/sec-api-documentation) (acceptanceDateTime), [OpenInsider](http://openinsider.com) สำหรับ screener ฟรี, ราคาจาก yfinance/Polygon free (ระวัง survivorship 34.7% ตามงานวิจัย)
- **Kill criteria:** ถ้า net CAR[1,2] < +1.0% หรือ t < 2.0 ใน out-of-sample 2023–2024 → ปิด; ถ้า turnover-adjusted Sharpe < 0.5 → ปิด
- **Capacity ประมาณ:** median ADDV $910k → ไม้ละ ≤ $9k (1% ของ ADDV) → เหมาะกับพอร์ต ≤ $200k
- **ความเสี่ยงหลัก:** survivorship (งานวิจัยเสีย 34.7% ของ sample เพราะ ticker หาย), corporate action mis-adjustment, และการที่ edge ส่วนใหญ่อยู่ใน overnight gap ที่เข้าไม่ได้

### H2 — Prediction-market favorite/longshot: ขาย longshot แบบ maker-only (ไม่จ่าย taker fee)
**สมมติฐาน:** การวาง offer ขาย YES ที่ราคา 3–8¢ (หรือซื้อ NO ที่ 92–97¢) ในตลาด Politics/Crypto ที่ hold ถึง resolution ให้ผลตอบแทนสุทธิ > 0 หลังจาก fee และ adverse selection.

- **Signal:** เลือกตลาดที่ (ก) อยู่ในหมวด Politics (ไม่ใช่ election) หรือ Crypto, (ข) ราคา YES ≤ 0.08, (ค) เวลาเหลือถึง resolution ≥ 14 วัน, (ง) OI ≥ $50k
- **Entry:** วาง limit **maker** ฝั่งขาย YES ที่ mid + 1 tick (ไม่ cross) — ถ้าไม่ fill ภายใน 48 ชม. ยกเลิก
- **Exit:** ถือถึง resolution; ทางเลือกปิดก่อนด้วยการซื้อคืนที่ ≤ 50% ของราคาที่ขาย (take-profit) เพื่อลด tail risk
- **Position size:** ≤ 2% ของพอร์ตต่อตลาด, ≤ 10% ต่อเหตุการณ์ (parent event) — เพราะ correlated
- **Costs:** fee = 0 (maker) + slippage 1 tick; ถ้าต้อง taker ให้คิด fee ตามสูตร `C×rate×p×(1−p)` (จะทำให้ edge หาย → เป็นการทดสอบว่า maker จำเป็นจริง)
- **Control:** (ก) กลุ่ม longshot ที่ราคา 10–20¢ (ควรให้ผลใกล้ 0); (ข) sports longshots (งานวิจัยบอกว่าผลเป็นบวก → ควร fail); (ค) เทียบ Brier score กับราคา ณ entry
- **ข้อมูล:** [Polymarket Gamma API + CLOB](https://docs.polymarket.com/) (public, no auth), [Kalshi Trade API](https://docs.kalshi.com/) — เก็บ orderbook snapshot ทุก 30 วินาที
- **Kill criteria:** ถ้า realized return ต่อไม้ < +0.20% หลังต้นทุน, หรือ fill rate < 20%, หรือ max drawdown > 15% → ปิด
- **ข้อบังคับเรื่อง sample (จากบทเรียนเดิม):** โปรเจกต์เคยทดสอบ Polymarket 490 ตลาด แล้วเจอว่า **เครื่องหมายผลตอบแทนพลิกตาม horizon** → ห้ามสรุปจากหลักพันตลาด; H2 ต้องใช้ dataset ≥ 100k resolved markets (ชุด 588M trades ของ arXiv:2609.12878 ครอบ 591,187 child markets) และรายงานแยกตามหมวด + ระยะเวลาถึง resolution
- **ความสะอาดของข้อมูล:** Kalshi archive คืนราคาเป็น decimal-dollar string ในฟิลด์ที่ไม่มี suffix → **อย่าหารด้วย 100** ยกเว้นฟิลด์ที่เป็น integer cents (`research/LESSONS.md`)
- **Capacity:** favorites คิดเป็น 43% ของเงิน ($9.66B) → ลึกพอสำหรับบัญชีเล็ก; แต่ตลาด economics/financials มี OI เพียง $21.6M–$85M → อย่าขยายไปหมวดนั้น
- **ความเสี่ยงหลัก:** resolution/oracle risk (ถ้า UMA ตัดสินผิด = ขาดทุน 100% ของไม้), delisting, และการที่ longshot ขนาดเล็กอาจ "ชนะ" ใน cluster ที่ correlated

### H3 — Pre-FOMC drift แบบมีเงื่อนไข VIX (ทดสอบกลไก uncertainty)
**สมมติฐาน:** drift ก่อน FOMC ที่หายไปหลัง 2015 **กลับมาเมื่อ VIX สูง** เพราะกลไกคือ premium for heightened uncertainty ไม่ใช่ปฏิทิน.

- **Signal:** FOMC scheduled meeting; ใช้ VIX close 2 วันก่อน meeting (VIXCLS จาก FRED) ≥ 20 (หรือ quintile สูงสุดของ trailing 2 ปี)
- **Entry:** open ของวันก่อน announcement (T−1 open) — ตามหน้าต่างที่ NY Fed ใช้
- **Exit:** 14:00 ET ของวัน announcement (ก่อน statement) — ไม่ถือผ่าน announcement
- **Instrument:** SPY/ES (หรือ SPX CFD ใน simulation) — ไม่ใช้ option เพราะต้นทุน spread
- **Position size:** ≤ 20% ของพอร์ต, ไม่ leverage
- **Costs:** 2 bp commission + 2 bp slippage ต่อขา
- **Control:** (ก) FOMC days ที่ VIX < 15 (ควรได้ ~0); (ข) non-FOMC days ที่ VIX ≥ 20 (ควรได้ 0); (ค) placebo: ใช้ "day before CPI" แทน FOMC (ควรได้ 0)
- **ข้อมูล:** [Fed FOMC calendar](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm), [FRED VIXCLS](https://fred.stlouisfed.org/series/VIXCLS), ราคา SPY รายวัน/นาที
- **Sample:** 2016-01 ถึง 2026-11 (~80 meetings) — out-of-sample ตามธรรมชาติเพราะเป็นช่วงที่ drift ตายแล้ว
- **Kill criteria:** ถ้า mean return < +10 bp ต่อ event หรือ t < 2.0 หรือถ้าผลมาจาก 2–3 events เดียว (>50% ของผลรวม) → ปิด
- **Capacity:** SPY ลึกมาก; ปัญหาคือ sample size (80 events) ไม่ใช่ liquidity → ต้องรายงาน bootstrap CI และไม่สรุปจาก t-test เดียว
- **ความเสี่ยงหลัก:** publication bias (กลไกนี้ถูกเขียนในงานวิจัยปี 2019 → อาจถูก arbitrage ไปแล้ว), และ regime shift จาก ZLB
- **สถานะในโปรเจกต์ (ห้ามทำซ้ำ):** TradeLab ทดสอบ FOMC แล้วแบบ **next-session** (ซื้อ SPY หลังประกาศถือข้าม session) ได้ **−0.701% net** และ rate futures เคลื่อนภายใน announcement window — [research/LESSONS.md](../../research/LESSONS.md) → H3 นี้ต่างเพราะเข้าที่ **T−1 open และออกก่อน 14:00 ET** (ไม่ถือผ่านประกาศ) แต่ต้องรายงานชัดว่าไม่ใช่การรันซ้ำ และถ้าผลออกมาใกล้ศูนย์ให้สรุปว่า "ไม่พบ"

---

## 7. สรุปเชิงปฏิบัติสำหรับบัญชีจำลองเล็ก (1 ย่อหน้า)

เรียงตามความน่าจะรอดหลังต้นทุน: **(1) H2 maker-only longshot selling** — ต้นทุนต่ำสุด (maker fee = 0), มีงาน 588M trades รองรับทิศทาง, แต่ผลตอบแทนต่อไม้เล็กและต้อง lock capital; **(2) H1 insider continuation** — timestamp ดีที่สุดในบรรดา event ทั้งหมด แต่ spread 3% ใน microcap กินกำไรส่วนใหญ่ และ survivorship bias สูง; **(3) H3 conditional pre-FOMC** — กลไกมีงานรองรับชัด แต่ sample เล็กและมีความเสี่ยงว่า arbitraged ไปแล้ว. สิ่งที่ **ไม่ควรลงทุนเวลา** ในปี 2026: PEAD large-cap, index inclusion, cross-venue arb แบบ taker, การซื้อ straddle ก่อน CPI/FOMC แบบไม่มีเงื่อนไข.

---

## 8. Publication bias / ข้อควรระวังเชิงระเบียบวิธี (สรุป)

- งาน PEAD/spinoff/index ส่วนใหญ่เป็น **US, pre-2015, gross of costs** และมี survivorship/CRSP bias; ตัวเลข 7.55%/ปี ของ EAR คือ 1987–2004.
- งานที่ "เจอ edge" มักถูกตีพิมพ์เพราะเจอ; งานที่ replicate แล้วไม่เจอ (Martineau 2022, Kurov 2021, repo 2026) คือหลักฐานที่มีค่าที่สุดในที่นี้ เพราะเป็น **out-of-sample ของ anomaly ที่ถูกค้นพบแล้ว**.
- ตัวเลข FLB เปลี่ยนเครื่องหมายตาม weighting → อย่าใช้ "−19%" เป็น prior โดยไม่ระบุหน่วยนับ.
- งาน prediction-market ส่วนใหม่ยังไม่ผ่าน peer review (arXiv 2026); ตัวเลข fee/liquidity จาก docs/แพลตฟอร์มเชื่อถือได้กว่า.
- ทุกตัวเลขในบันทึกนี้เป็น **gross** ยกเว้นที่ระบุ "หลังต้นทุน" ชัดเจน.

---

## 9. ความทับซ้อนกับงานที่ TradeLab ปิด/ล็อกแล้ว (อ่านก่อนออกแบบการทดลอง)

### Takeaway
สามในห้าข้อของบันทึกนี้แตะพื้นที่ที่โปรเจกต์เคยทดสอบแล้วและได้ผลลบ; ต้องอ้างผลเดิมและออกแบบให้ **ต่างจริง** ไม่ใช่รันซ้ำ.

### Cited Findings (จากในโปรเจกต์)
- **FOMC (ปิดแล้ว):** rate futures เคลื่อน *ภายใน* announcement window; กฎ "ซื้อ SPY session ถัดไป" ได้ **−0.701% net** — [`research/LESSONS.md`](../../research/LESSONS.md) หัวข้อ world signals
- **Polymarket (ปิดแล้วบางส่วน):** 490 ตลาด เครื่องหมายผลตอบแทน **พลิกตาม horizon** → กติกาโปรเจกต์: "no conclusion under a few thousand cases" — [`research/LESSONS.md`](../../research/LESSONS.md) ข้อ 7
- **GDELT (ปิด):** ถูกปฏิเสธทุกคำขอ → ใช้ราคา/ปริมาณเป็นตัวแทน — [`research/LESSONS.md`](../../research/LESSONS.md) ข้อ 8
- **Event trader (ล็อก, รอผล):** ซื้อหุ้นใหญ่ที่พุ่ง ≥5% เทียบหุ้นสุ่ม, หยุด 8%, ถือ 20 ชม., ต้องครบ 30 คู่ก่อนสรุป — [`research/event_trader/protocol.md`](../../research/event_trader/protocol.md)
- **CPI gate (ปิด):** ปฏิทิน CPI ไม่ช่วยกู้ weekly BTC options; ปฏิทินย้อนหลังไม่ยืนยันฉบับที่รู้ ณ เวลานั้น (เลื่อนประกาศ) — [`research/LESSONS.md`](../../research/LESSONS.md)
- **วันที่เพี้ยน:** helper ราคา Yahoo เติม 12 ชม. ทำให้ event trade กลายเป็น same-day; ต้อง join ด้วย New York session date จาก timestamp ดิบ — [`research/LESSONS.md`](../../research/LESSONS.md) หัวข้อ world signals
- **Kalshi:** decimal-dollar string ในฟิลด์ไม่มี suffix → ห้ามหาร 100 — [`research/LESSONS.md`](../../research/LESSONS.md)
- **ข่าวช้า:** โปรเจกต์วัด US quote ใหม่ 1–6 วินาที (ไม่ใช่ 15 นาที) → latency ที่ต้องสมมติคือ scan interval ไม่ใช่ data delay — [`research/event_trader/protocol.md`](../../research/event_trader/protocol.md) addendum 2026-11-24

### Inferences
- H1 (insider microcap) **ไม่ทับซ้อน** กับ event trader (คนละ universe, คนละ trigger, คนละ holding) → เดินต่อได้ แต่ต้องใช้ EDGAR acceptance timestamp ไม่ใช่ Yahoo date.
- H2 ต้องยกระดับจาก "490 ตลาด" เป็น dataset ระดับแสนตลาด และรายงานแยก horizon; ถ้ายังพลิกเครื่องหมายตาม weighting ให้สรุปว่าไม่พบ.
- H3 อนุญาตเฉพาะเวอร์ชัน **pre-announcement** และต้องรายงานผลลบถ้าไม่ผ่าน — ห้าม re-label ผล next-session เดิมว่าเป็นหลักฐานใหม่.

### Gaps
- ไม่มีผลในโปรเจกต์ที่ทดสอบ insider Form 4 มาก่อน → H1 เป็นพื้นที่ใหม่จริง.
- ไม่มีผลในโปรเจกต์ที่ทดสอบ spinoff/PDUFA/index effect แบบ after-cost → ทั้งสามยังเป็นช่องว่าง (แต่หลักฐานภายนอกชี้ว่าหมด edge แล้ว).
- ไม่มีข้อมูลว่า scan interval ของ Kuber (10 s สำหรับ event, 15 นาทีสำหรับ DeepSeek) เพียงพอต่อ H1/H2 หรือไม่.
