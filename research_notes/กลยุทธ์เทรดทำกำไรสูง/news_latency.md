# ข่าวสาร–ความสนใจระยะสั้น (News & Attention Edges) สำหรับบัญชีจำลอง ~147 USD

ขอบเขต: หาหลักฐานที่ทดสอบได้ว่าข่าว/ความสนใจทางสังคมสร้างกำไรหลังหักต้นทุนได้จริงหรือไม่ ภายใต้ latency และค่าธรรมเนียมแบบ retail ปี 2020–2026 (อ้าง foundational study เก่าตามจำเป็น)
ระดับหลักฐาน: `[PR]` peer-reviewed, `[WP]` working paper, `[GOV]` regulator/exchange, `[VENDOR]` ผู้ขายข้อมูล/โบรกเกอร์, `[ANEC]` บล็อก/ประสบการณ์ (ใช้อ้างอิงเชิงปฏิบัติเท่านั้น ไม่ใช่อ้างว่ากลยุทธ์ได้ผล)

---

## 1. หลักฐานวิชาการและอุตสาหกรรม: PEAD, analyst revisions, sentiment, Google Trends, Reddit/StockTwits, surprise events

### Takeaway
PEAD แบบคลาสสิก “ตาย” ในหุ้นที่ไม่ใช่ microcap ตั้งแต่ราวปี 2006 และสิ่งที่เหลืออยู่กระจุกในหุ้นเล็กที่ต้นทุนซื้อขายสูงมาก ข่าวที่ตลาดใหญ่ reacts ภายในวินาที–มิลลิวินาที ขณะที่ edge ที่อาจเหลือให้ retail คือ “ข่าวที่ตีความยาก/หุ้นที่สภาพคล่องต่ำ” ซึ่งต้องแลกมาด้วย spread 2–7% ต่อรอบ

### Cited Findings
- PEAD หายไปจากหุ้น non-microcap: เริ่มจางลงปี 2001 และหายจริงราวปี 2006 หลัง decimalization และกฎเร่ง HFT ปี 2005 — Martineau, “Rest in Peace Post-Earnings Announcement Drift”, *Critical Finance Review* 11(3–4): 613–646 (2022) — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3111607), สรุปโดย [UCLA Anderson Review, 21 Jan 2026](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/) `[PR]`
- งานปี 2025 สองชิ้นอ้างว่า PEAD ยังอยู่ แต่ Subrahmanyam (2025) replication ด้วยข้อมูล US ก.พ. 2001–ธ.ค. 2024 พบ t-stat = 2.18 เมื่อรวมทุกหุ้น และลดเหลือ 1.43 เมื่อตัด microcap (bottom 20% NYSE market cap) ออก — [UCLA Anderson Review](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/); ต้นฉบับ [SSRN 5930255](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5930255) `[WP]`
- หุ้น microcap คิดเป็นจำนวนมากแต่เพียง ~3% ของมูลค่าตลาดรวม และเป็นกลุ่มที่ทำให้ผลทดสอบ PEAD ดูมีนัยสำคัญ — [UCLA Anderson Review](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/) `[WP]`
- แม้ตัดต้นทุนออก PEAD ยังแรงกว่าในหุ้นเล็ก: Novy-Marx & Velikov รายงาน gross Sharpe ของ PEAD (SUE) = 2.03 (microcap), 1.18 (small), 0.56 (large) และ **net Sharpe** = 1.05, 0.75, 0.28 ตามลำดับ (แบบจำลองต้นทุนสำหรับ institutional AUM ไม่ใช่บัญชี 147 USD) — “A Taxonomy of Anomalies and their Trading Costs”, *RFS* (2016) — [PDF](https://mysimon.rochester.edu/novy-marx/research/ToAatTC.pdf) `[PR]`
- Text-based PEAD (SUE.txt จากถ้อยคำใน filing) ให้ drift ใหญ่กว่า classic PEAD ในทุกช่วง quarter ภายใน 1 ปี — Meursault et al., “PEAD.txt”, Philadelphia Fed WP 21-07 (2021) / *JFQA* 58 (2023): 2299–2326 — [PDF](https://www.philadelphiafed.org/-/media/frbp/assets/working-papers/2021/wp21-07.pdf), [JFQA](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/most-read) `[WP]/[PR]`
- Review ของ Fink (2021) ยืนยันว่า drift ยังมีในหลายตลาดและอยู่มานานกว่า 2 ทศวรรษหลังตีพิมพ์ แต่หลักฐานเรื่องขนาด/ความคงอยู่ขัดแย้งกันตามวิธีวัด — [J. Behavioral and Experimental Finance](https://www.sciencedirect.com/science/article/pii/S2214635020303750) `[PR]`
- Analyst recommendation revisions: ตลาดตอบทันทีราว 2.7% (upgrades) และ 2.8% (downgrades) และงานเก่าพบ drift ต่อเนื่อง 3–9 เดือน แต่ผลขึ้นกับ “influential revisions” เพียง ~12% ของทั้งหมด — Bradshaw, Flake & Piorkowski (2022) — [PDF](https://www.bayes.citystgeorges.ac.uk/__data/assets/pdf_file/0009/681939/Flake_20220318.pdf) `[WP]`
- Social network/news diffusion: Hirshleifer, Peng & Wang (*RFS* 38(3), 2025) พบ PEAD แรงในกลุ่มที่ social connectedness ต่ำ (t ~14) แต่ Subrahmanyam โต้แย้งว่าเมื่อควบคุม market cap ผลจะไม่ robust — [RFS](https://academic.oup.com/rfs/article-abstract/38/3/883/7698199), [UCLA Review](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/) `[PR]/[WP]`
- Headline sentiment: Tetlock (2007) พบถ้อยคำลบในคอลัมน์ข่าวpredict แรงกดดันราคาลงในวันถัดไปแล้ว revert ภายหลัง (sentiment มีผลระยะสั้น ไม่ใช่ drift ยาว) — “Giving Content to Investor Sentiment”, *Journal of Finance* 62(3): 1139–1168 — [DOI](https://doi.org/10.1111/j.1540-6261.2007.01232.x) `[PR]`
- Google Trends: Preis et al. (2013) รายงานกลยุทธ์จากคำค้น “debt” ให้ผลตอบแทนสะสม +326% ช่วง ม.ค. 2004–ก.พ. 2011 จาก 98 คำ (US search volume); ค่าเฉลี่ยทั้ง 98 คำสูงกว่า random strategy 0.60 SD (t=8.65) — แต่เป็นการทดสอบ in-sample, ซื้อขายสัปดาห์ละครั้ง, **ไม่หักค่าธรรมเนียม** — [Scientific Reports via PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC3635219/) `[PR]`
- Google Trends (งานทบทวนภายหลัง): search volume สูงทำนายผลตอบแทนบวก 1–2 สัปดาห์ แล้วตามด้วยการ revert — Bijl et al. (2016) — [J. Empirical Finance](https://www.sciencedirect.com/science/article/abs/pii/S105752191630045X) `[PR]`
- Reddit r/wallstreetbets: portfolio ตามโพสต์ buy/sell ให้ daily alpha (หลังหักครึ่ง bid-ask spread) ของ long–short = +0.23%** ที่ 1 วัน, +0.07% (ไม่ significant) ที่ 1 สัปดาห์ และ −0.01% ที่ 1 เดือน; ขา long alpha ไม่ significant (−0.03%) ขณะที่กลุ่มหุ้นที่ถูกแนะนำให้ขาย underperform −0.35%*** ดังนั้น alpha แทบทั้งหมดมาจาก **ขา short** ซึ่ง retail long-only ทำไม่ได้ — “Will the reddit rebellion take you to the moon?”, 2022 — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9210333/) `[PR]`
- WSB attention (2024) ทำให้เกิด uninformed trading ทั้ง long และ short, เพิ่มความเสี่ยง และ **ลด holding-period returns** — [International Review of Financial Analysis](https://www.sciencedirect.com/science/article/pii/S1057521924006537) `[PR]`
- Due-diligence (DD) posts บน WSB ทำนายผลตอบแทนได้ก่อน GME squeeze แต่ความสามารถนั้นหายไปหลังเหตุการณ์ — Bradley et al. (2024) อ้างใน [arXiv 2610.25468](https://arxiv.org/html/2610.25468v1) `[WP]`
- Surprise events แบบ binary (FDA/clinical topline/M&A) ไม่มีหลักฐาน after-cost out-of-sample ที่ retail เข้าทัน; ราคาเป้าหมาย M&A กระโดดเกือบทันทีเมื่อข่าวออก จึงจัดเป็น “เข้าไม่ทัน” มากกว่ากลยุทธ์ — ข้อสรุปนี้เป็น inference จากหลักฐาน latency ข้อ 2 (ดู Gaps)

### Inferences
- PEAD ที่ยังเหลือคือ **microcap/small-cap + text-based** ซึ่งเป็นจุดที่ retail รายเล็กได้เปรียบเรื่อง capacity (ออร์เดอร์ 147 USD ไม่กระทบราคา) แต่เสียเปรียบเรื่อง spread/ค่าคอมขั้นต่ำอย่างรุนแรง
- Analyst revisions และ Google Trends ให้สัญญาณช้ากว่าวินาที (เป็นวัน–สัปดาห์) จึงเป็นกลุ่มที่ retail latency 1–5 นาที “ไม่เป็นอุปสรรค” แต่ข้อมูล consensus/trends ที่ดีมีต้นทุนหรือถูกจำกัด
- Reddit/WSB ไม่ใช่สัญญาณ long ที่ทำเงินหลังหักต้นทุน; มันเป็น short-side alpha ซึ่งบัญชี 147 USD ทำไม่ได้ (ไม่มี margin/short) — ใช้ได้เพียงเป็น “สัญญาณออก” หรือตัวกรองความสนใจ

### Gaps
- ไม่พบงานที่วัด **microcap PEAD net ของต้นทุนจริงระดับ 147 USD** (ค่าคอมขั้นต่ำ $0.35 + spread 2–7%) — งานที่มี (Novy-Marx) ใช้สมมติฐานต้นทุน institutional
- ไม่พบตัวเลข effect size ของ PEAD ปี 2020–2025 แยกตาม decile ที่เผยแพร่ฟรีและตรวจสอบ replication ได้; ตัวเลขส่วนใหญ่มาจาก paper ที่ต้องซื้อหรือ working paper
- StockTwits sentiment: งานวิชาการส่วนใหญ่ใช้ข้อมูลก่อน 2020 และ API ปัจจุบันจำกัด (ดูข้อ 3) จึงไม่ยืนยันว่ายังใช้ได้

---

## 2. ต้องเข้าเร็วแค่ไหน และ move หายไปเท่าไรก่อนที่ retail API จะเห็นข่าว

### Takeaway
สำหรับหุ้นใหญ่ที่ข่าวดัง (= liquidity สูง) ตลาดดูดซับข่าวใน **มิลลิวินาที–ไม่กี่วินาที**; ที่ 60 วินาที เหลือเพียง ~24% ของ reaction แรก (และน้อยกว่านั้นในตลาดปัจจุบัน) ดังนั้น กลยุทธ์ “อ่าน headline แล้วไล่ซื้อ” บนหุ้นใหญ่แทบไม่มีทางชนะต้นทุน เว้นแต่ข่าวจะทำให้ราคาเคลื่อน >4–8% และเราเน้นหุ้นเล็กที่ HFT ไม่ยอมถือ inventory

### Cited Findings
- ในข้อมูล NASDAQ HFT + RavenPack (ก.พ. 2004–ส.ค. 2012): หุ้นตอบสนองข่าวคุณภาพสูงภายใน **1 วินาที** และเพียง **13% ของ reaction 120 วินาที** เกิดขึ้นใน 5 วินาทีแรก; สัดส่วนสะสมโดยประมาณ 28–35% ที่ 10 วิ, 42–49% ที่ 20 วิ, 53–58% ที่ 30 วิ, 69–70% ที่ 50 วิ และ **76% ที่ 60 วิ** — von Beschwitz, Keim & Massa, “First to ‘Read’ the News”, *Review of Asset Pricing Studies* 10(1): 122–178 (2020) — [RAPS](https://academic.oup.com/raps/article/10/1/122/5555424), [Fed PDF](https://www.federalreserve.gov/econres/ifdp/files/ifdp1233.pdf) `[PR]`
- ข่าวที่มี relevance สูงทำให้เกิด cumulative signed return เฉลี่ยเพียง ~2.05 basis points ที่ 120 วินาที (จาก ~−0.1 bp ที่ t=0) — กล่าวคือ “move” เฉลี่ยของ press release ทั่วไปเล็กมากจนต้นทุนกลบ — von Beschwitz et al. (2020), Figure 1 — [Fed PDF](https://www.federalreserve.gov/econres/ifdp/files/ifdp1233.pdf) `[PR]`
- ตลาดเกิดใหม่ (ตุรกี, ข่าว Q4 2010): ข่าวบวกราคาเริ่มขยับ ~4 วินาที ข่าวลบ ~10 วินาที; ผู้ที่เทรดภายใน 5 วินาทีได้เพียง 18% ของการเคลื่อนไหวถึง 120 วินาที; **มนุษย์ที่เข้าใน 60 วินาทีได้กำไรเฉลี่ย 0.23%** ก่อนหักค่าธรรมเนียม — [Emerging Markets Review](https://www.sciencedirect.com/science/article/abs/pii/S1566014120305872) `[PR]`
- Earnings announcements: ข้อมูล after-hours quote 89 พันล้านรายการพบราคากระโดดใน **>90% ของกรณี** และสำหรับหุ้นใหญ่ราคาขยับภายใน **มิลลิวินาที**; ผู้วิจัยสรุปว่าโอกาสหลัง announcement “แทบหายไป” หากมีความหน่วงเพียง 2–3 วินาที — Christensen, Veliyev & Timmermann, *JFE* (2025) — [UCSD](https://today.ucsd.edu/story/earnings-news-cause-immediate-stock-price-jumps-sometimes-moving-whole-market), [paper PDF](https://www.dropbox.com/scl/fi/6ztyz4plri1cf6dbwmn93/JFE_24-00558_Accepted_Manuscript.pdf?rlkey=tpfy5tdrsae8uxkg7ih2eedjz&e=1&dl=0) `[PR]`
- ตลาดสหรัฐฯ วัด reaction ต่อ scheduled macro news ได้ภายใน 5 มิลลิวินาทีแรก และงาน HFT ชี้ว่าความเร็วระดับนี้เป็นเรื่องของ co-location/infra ไม่ใช่ API retail — อ้างในบทนำของ [Emerging Markets Review](https://www.sciencedirect.com/science/article/abs/pii/S1566014120305872) `[PR]`
- ผลกระทบ spillover: ข่าว earnings ของบริษัทหนึ่งทำให้หุ้นในอุตสาหกรรมเดียวกัน (และบางครั้งทั้งตลาด) กระโดดตามภายในไม่กี่วินาที เช่น Qualcomm → INTC/AMD/MU — [UCSD](https://today.ucsd.edu/story/earnings-news-cause-immediate-stock-price-jumps-sometimes-moving-whole-market) `[PR]`

### Inferences
- สูตร break-even แบบง่าย: ให้ F(t) = สัดส่วน reaction ที่เกิดขึ้นแล้วเมื่อเราเข้า; residual = (1−F)·ΔP ต้องมากกว่า round-trip cost
  - เข้า 5 วิ (F≈0.13): ต้องมี ΔP > 1.15× ต้นทุน → ต้นทุน 50 bps ต้องมี move > 57 bps
  - เข้า 60 วิ (F≈0.76): ต้องมี ΔP > 4.2× ต้นทุน → ต้นทุน 50 bps ต้องมี move > 2.1%; ต้นทุน 200 bps ต้องมี move > 8.3%
- ตัวเลข F(60s)=0.76 มาจากข้อมูล 2004–2012; ตลาดปี 2026 เร็วกว่านั้นมาก (UCSD 2025: ms) ดังนั้น residual จริงของหุ้นใหญ่ใกล้ 0 → **“headline scalping” บนหุ้นใหญ่ไม่ใช่ edge สำหรับ retail**
- โครงการนี้มี protocol ล็อกอยู่แล้ว (`research/news_latency/protocol.md`, ล็อก 24 พ.ย. 2026) ที่วัด +1 นาที และ +5 นาทีหลัง `first_seen_utc` ของพาดหัวที่โยงหุ้น 104 ตัวใหญ่ เทียบหุ้นสุ่มเดียวกัน หักต้นทุนไปกลับ 0.14% และต้องมี 100 คู่ครบก่อนสรุป — นี่คือการทดสอบคำถามนี้โดยตรงในเงื่อนไขของเรา; ข้อจำกัดที่ระบุไว้คือ `first_seen_utc` มี polling delay 30 วินาที, quote Yahoo อาจเก่า 1–40 วินาที และ control เป็น large cap ไม่ได้ match sector/volatility
- ดังนั้นงานใหม่ไม่ควรทดสอบซ้ำ large-cap +1m/+5m; ควรทำเฉพาะ **ส่วนขยาย small-cap/sub-$500M** ที่ literature ชี้ว่าอาจมี residual เหลือ (ดู H3)
- ช่องว่างที่ยังมีเหตุผล: (ก) หุ้นเล็กที่ HFT ไม่ยอมรับความเสี่ยง inventory ทำให้ reaction ล่าช้าเป็นนาที–ชั่วโมง; (ข) ข่าวที่ต้องตีความเชิงลึก (8-K, guidance, ภาษาใน filing) ซึ่ง algos ราคาถูกอ่านเพียง surface; (ค) ข่าวนอกเวลา/หลังปิดที่ liquidity บาง
- แต่ (ก) และ (ข) แลกมาด้วย spread 2–7% และค่าคอมขั้นต่ำ → ต้องมี move ใหญ่มากพอ (≈8%+) จึงคุ้ม ซึ่งเกิดไม่บ่อยและมักเป็น binary event ที่เข้าไม่ทัน

### Gaps
- ไม่มีงานวิชาการที่วัด **end-to-end latency ของ retail API** (feed timestamp → broker fill) ปี 2024–2026; ตัวเลขที่มีเป็น vendor claim และการทดสอบของบล็อก
- ไม่มีหลักฐานว่า free feed (RSS/Finnhub/GDELT) ประกาศข่าวช้ากว่าที่ตลาดรู้กี่วินาทีอย่างเป็นระบบ — ต้องวัดเอง (ดูสมมติฐาน H3)
- งาน Turkey/M&A/FDA ที่ให้ตัวเลข after-cost สำหรับ retail โดยตรงมีน้อยและ sample เก่า

---

## 3. แหล่งข้อมูลฟรี/ต้นทุนต่ำ: latency, rate limits, licensing

### Takeaway
ข้อมูล “ฟรี” ที่ใช้ได้จริงสำหรับกลยุทธ์ช้า (นาที–วัน) คือ SEC EDGAR, RSS/IR feeds, Finnhub free และ Reddit OAuth (GDELT ใช้ได้ถ้าเข้าถึง API ได้ เพราะโครงการนี้เคยถูกปฏิเสธ); ส่วนข้อมูล real-time ระดับวินาที (SIP, Benzinga real-time, news analytics) ต้องจ่าย $99/เดือนขึ้นไป ซึ่งเกิน 60% ของทุน 147 USD ต่อเดือน

### Cited Findings
| แหล่ง | สิ่งที่ได้ | Latency/ข้อจำกัด | ราคา/สัญญาอนุญาต | หลักฐาน |
|---|---|---|---|---|
| SEC EDGAR full-text + submissions API | 8-K/10-Q/10-K, full-text search | filing เข้าใกล้ real-time; rate limit ~10 req/s | ฟรี, ข้อมูลสาธารณะ | [SEC API docs](https://www.sec.gov/edgar/sec-api-documentation) `[GOV]` |
| GDELT 2.0 (Events/GKG/DOC API) | ข่าวโลก + entity/theme, 65 ภาษา | **อัปเดตทุก 15 นาที**; entity mapping มี noise; โครงการนี้เคยถูก GDELT ปฏิเสธทุก request (LESSONS #8) จึงต้องทดสอบสิทธิ์/IP ก่อนพึ่งพา | ฟรี 100%, open data | [GDELT Data](https://www.gdeltproject.org/data.html) `[GOV]/[PR]` |
| Finnhub Free | real-time quote, company news 1 ปี, WS 50 symbols | **60 calls/min** (สูงสุด 30/sec ตามเอกสาร); 29 จาก 118 endpoints ฟรี; ข่าวบางส่วน delay | ฟรี; แผนเสียเงินเริ่ม $49.99/เดือน | [rate limit](https://finnhub.io/docs/api/rate-limit), [pricing](https://finnhub.io/pricing), [สรุป endpoint ฟรี](https://edgrapi.com/blog/finnhub-api) `[VENDOR]` |
| Polygon.io (เปลี่ยนชื่อ Massive ต.ค. 2025) | trades/quotes/bars | free: **5 req/min, 15-min delayed**; real-time ต้องแผนเสียเงิน | free; แผนเสียเงินแยก | [pricing](https://massive.com/pricing), [KB](https://massive.com/knowledge-base/article/how-quickly-can-i-access-massives-market-date) `[VENDOR]` |
| Alpaca Market Data Basic | quotes/trades/bars | **IEX เท่านั้น (real-time)**; SIP แบบ 15-min delay; rate limit สูง | ฟรี; **Algo Trader Plus $99/เดือน** สำหรับ SIP ทุก exchange | [docs](https://docs.alpaca.markets/us/docs/about-market-data-api), [forum](https://forum.alpaca.markets/t/iex-or-sip-with-a-free-account/17141) `[VENDOR]` |
| Benzinga News/Analyst/Earnings API | ข่าว real-time, ratings, guidance | latency ขึ้นกับ feed; ต้องซื้อแยก dataset | **$99/เดือน ต่อ dataset**; Benzinga Pro (terminal) ~$30.58/เดือน (annual promo) แต่ไม่ใช่ API | [Massive/Benzinga](https://massive.com/partners/benzinga), [Pro pricing](https://www.benzinga.com/pro/pricing) `[VENDOR]` |
| Reddit API | posts/comments ของ WSB ฯลฯ | OAuth ~**100 QPM**; unauthenticated ~10 QPM; ต้องขอ approval และมีข้อจำกัด commercial | ฟรีสำหรับการใช้เล็กน้อย; เงื่อนไข commercial เข้มขึ้นตั้งแต่ 2023 | [สรุป rate limit 2026](https://www.painpointmap.com/blog/reddit-api-rate-limits-guide), [GitHub wiki](https://github.com/MalloyDelacroix/DownloaderForReddit/wiki/The-Ongoing-Impact-of-Reddits-API-Rate-Limits) `[VENDOR]/[ANEC]` |
| StockTwits API | messages/sentiment | API นักพัฒนาเปิดแบบจำกัด/partner; เอกสารใหม่มี gateway | ต้องติดต่อ/จ่าย; ไม่เหมาะเป็นแหล่งฟรี | [api-docs](https://api-docs.stocktwits.com/) `[VENDOR]` |
| Google Trends | search interest รายวัน/สัปดาห์ | **ไม่มี official API**; pytrends ไม่เป็นทางการ มักโดน 429; ข้อมูลถูก revise | ฟรี แต่ไม่มี SLA | [pytrends](https://github.com/GeneralMills/pytrends) `[ANEC]` |
| RSS/IR + GlobeNewswire/PR Newswire | press release, 8-K summary | วินาที–ไม่กี่นาที; ไม่มี historical archive ฟรี; ToS ห้าม redistribute | ฟรี/ถูก | ข้อสังเกตจากการใช้งาน `[ANEC]` |

- ในทางปฏิบัติ feed ที่ “ถูกที่สุดและเร็วพอ” สำหรับกลยุทธ์ช้าคือ **EDGAR + RSS + GDELT**; Finnhub free ใช้เป็น confirm ราคา/quotes ได้ แต่ไม่ควรถือเป็น real-time news ที่ชนะตลาด
- Alpaca/Trading API: zero commission แต่ order ถูก route ผ่าน wholesaler; PFOF เฉลี่ยของ Robinhood อยู่ที่ **$0.0023/หุ้น (Q4 2020)** ซึ่งบ่งชี้ว่า “ฟรี” ถูกชดเชยจาก spread/price improvement ไม่ใช่ของฟรีจริง — [Robinhood](https://robinhood.com/newsroom/demystifying-payment-for-order-flow/) `[VENDOR]`
- งานทดลอง 150,000 ออร์เดอร์ มูลค่า $22.4 ล้าน (ธ.ค. 2021–พ.ค. 2023) ผ่าน E*Trade, Fidelity, IBKR Pro/Lite, Robinhood, Schwab, TD Ameritrade พบต้นทุน effective spread ต่างกันมากและ persist ต่อ broker/wholesaler; PFOF เองไม่สัมพันธ์กับคุณภาพ execution อย่างมีนัยสำคัญ — Fed FEDS 2024-080 — [PDF](https://www.federalreserve.gov/econres/feds/files/2024080pap.pdf) `[GOV]/[WP]`

### Inferences
- งบข้อมูลที่สมเหตุสมผลสำหรับบัญชี 147 USD: **$0/เดือน** (EDGAR+RSS+GDELT+Finnhub free+Reddit) และอาจจ่าย $99/เดือนได้เฉพาะเมื่อพิสูจน์ edge ได้แล้วเท่านั้น (คิดเป็น 67% ของทุน)
- ข้อมูล real-time ที่แท้จริง (SIP + ข่าว Benzinga) มีต้นทุนขั้นต่ำ ~$100–200/เดือน → ต้องมี capital อย่างน้อย $20k–50k เพื่อให้ต้นทุนข้อมูล <1%/เดือน
- latency ของแหล่งฟรี (15 นาทีสำหรับ GDELT, poll 1–5 นาทีสำหรับ RSS) ทำให้กลยุทธ์ที่ต้องเข้าใน <60 วินาทีเป็นไปไม่ได้โดยโครงสร้าง

### Gaps
- ไม่ได้ตรวจสอบสัญญาอนุญาตฉบับเต็มของ Benzinga/Finnhub เรื่องการ redistribute หรือใช้เชิงพาณิชย์; ตัวเลขราคาอาจเปลี่ยนตามโปรโมชัน
- StockTwits สถานะ API ปี 2026 ไม่ชัด (เอกสารมี แต่ชุมชนรายงานว่าปิด) — ต้องทดสอบด้วย key จริงก่อนใช้
- ไม่พบตัวเลข latency ที่วัด independently ของ Finnhub/Benzinga (มีแต่ claim)

---

## 4. ต้นทุนและ capacity ของบัญชี 147 USD (5,000 THB)

### Takeaway
ต้นทุนที่ฆ่ากลยุทธ์ไม่ใช่ค่าคอมอย่างเดียว แต่คือ **spread ของหุ้นเล็ก + ค่าคอมขั้นต่ำ $0.35 + FX + ข้อจำกัด cash account T+1**; round-trip จริงของหุ้น microcap อยู่ที่ ~200–800 bps ทำให้ต้องมี move มากกว่า 2–8% ก่อนจึงจะกำไร

### Cited Findings
- **ค่าคอม IBKR Pro (US)**: $0.0035/หุ้น, ขั้นต่ำ **$0.35/ออร์เดอร์**, สูงสุด 1% ของมูลค่าซื้อขาย; IBKR Lite $0 (PFOF) — [IBKR commissions](https://www.interactivebrokers.com/en/pricing/commissions-stocks.php) `[VENDOR]`
- ผลคำนวณ: ออร์เดอร์ $147 → $0.35 = **0.238% ต่อ side, 0.476% round trip**; ถ้าเทรด 8 ไม้ไป-กลับ/เดือน (16 ออร์เดอร์) = $5.60 = **3.8% ของทุน/เดือน** (ยังไม่รวม spread)
- **SEC Section 31 fee**: $0.00 ถึง 3 เม.ย. 2026 และ **$20.60 ต่อ $1 ล้าน (0.206 bps)** ตั้งแต่ 4 เม.ย. 2026 เป็นต้นไป (เฉพาะขาย) — [SEC Fee Advisory 2026-2](https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2) `[GOV]`
- **FINRA TAF**: ~$0.000166/หุ้น (สูงสุด $8.30/ออร์เดอร์) — ค่าธรรมเนียมเล็กน้อยแต่ต้องตรวจอัตราปัจจุบันก่อนใช้ (`[GOV]` โดยประมาณ; ไม่ได้ดึงหน้าล่าสุด)
- **FX**: IBKR FX ขั้นต่ำ **$2.00/ออร์เดอร์** → แลก $147 = **1.36%**; ช่องทางอื่น (Wise/โบรกไทย) ~0.4–1.5% — [IBKR pricing](https://www.interactivebrokers.com/en/pricing/commissions-home.php) `[VENDOR]`
- **Margin/PDT**: กฎ PDT ($25,000, 4 day trades/5 วัน) ถูกแทนที่ด้วย intraday margin ใหม่ **effective 4 มิ.ย. 2026** (phase-in ถึง 20 ต.ค. 2027) — [FINRA Notice 26-10](https://www.finra.org/rules-guidance/notices/26-10) `[GOV]`; แต่ margin account ยังต้องมี equity ขั้นต่ำ **$2,000** — [E*Trade](https://us.etrade.com/knowledge/library/margin/pattern-day-trading-rule-change) `[VENDOR]`
- ดังนั้นบัญชี $147 ต้องเป็น **cash account**: day trade ได้เฉพาะด้วย settled cash; T+1 settlement → ใช้ทุนเดิมได้ ~1 รอบ/วัน; **ซอร์ตไม่ได้** (ไม่มี margin/borrow)
- **Spread**: ตัวอย่างจริง หุ้น $3.10 bid / $3.35 ask = 25¢ = **~7.5%**; หุ้น growth $18.40/$18.65 = 1.36% — [StockAlarm](https://pro.stockalarm.io/blog/bid-ask-spread-explained) `[ANEC]`; งานเก่ารายงาน small-cap spread สูงถึง ~6.55% และ bottom-20% volume ~2.06% — [Damodaran](https://pages.stern.nyu.edu/adamodar/New_Home_Page/invemgmt/trading.htm) `[PR/ตำรา]`
- **Borrow (short)**: หุ้น small/microcap จำนวนมากไม่ให้ยืม หรือคิดดอกเบี้ยรายปี 10–100%+; บัญชี $147 เข้าไม่ถึงเงื่อนไข margin จึง **ตัด short ออกทั้งหมด** (ตัวเลข borrow เป็น gap ที่ยังไม่ได้เก็บหลักฐานเฉพาะ)
- **Capacity**: ออร์เดอร์ $147 คิดเป็น <0.1% ของ ADV ของหุ้น $50M–$1B (ADV $1M+) → market impact ~0; แต่ข้อจำกัดจริงคือ **1 position = 100% ของพอร์ต**, odd-lot pricing และ spread

### Inferences
- ต้นทุน round-trip โดยประมาณ:
  - **0.14% (14 bps) ที่ engine ใช้อยู่ (`research/news_latency/protocol.md`) เป็นสมมติฐานสำหรับ large cap เท่านั้น** — ใช้กับ small/microcap ไม่ได้ เพราะ spread กว้างกว่าหลายเท่า
  - หุ้นใหญ่ $50–$200, spread 1¢: ~2–4 bps + ค่าคอม $0 (Alpaca/Robinhood) → ถูก แต่ edge จากข่าวก็หมดไปแล้ว
  - หุ้นเล็ก $10–$30, spread 5–10¢: ~170–500 bps + ค่าคอม → ต้องมี move >2–5%
  - microcap $3–$5, spread 10–25¢: ~200–830 bps → ต้องมี move >2–8%
- งบ 147 USD ไม่สามารถ “ diversify ข้าม events” ได้; ความผันผวนเฉพาะตัวต่อไม้ (~5–10%/วัน) ใหญ่กว่า edge ที่หวัง (1–3%) มาก → การทดสอบด้วยเงินจริงจะสรุปอะไรไม่ได้ทางสถิติ ต้อง backtest/paper trading
- ค่าคอมขั้นต่ำ $0.35 ทำให้ IBKR แพงกว่า zero-commission broker สำหรับไม้ <$350; แต่ zero-commission มีต้นทุนแฝงจาก routing/spread ที่วัดได้ยาก

### Gaps
- ไม่ได้รวบรวมตาราง borrow fee รายตัวจาก IBKR; ตัวเลข 10–100%+ เป็นช่วงกว้างที่ต้องยืนยันก่อนใช้
- ไม่มีตัวเลข TAF ล่าสุดจากหน้า FINRA (ใช้ค่าที่รู้จักและระบุให้ตรวจสอบ)
- ไม่มีข้อมูล commission/FX ของโบรกที่คนไทยใช้จริง (Dime, Webull TH, Tiger) — ต้องเก็บเพิ่มถ้าจะเลือกโบรก

---

## 5. สมมติฐานที่ทดสอบได้ 2–3 ข้อ (กฎเข้า/ออก + ตัวควบคุม)

### Takeaway
สามข้อที่ควรทดสอบเรียงตามความน่าเป็นไปได้: (H1) PEAD หุ้นเล็ก long-only 20 วัน, (H2) slow-text drift จาก 8-K/ข่าว 3–5 วัน, (H3) ส่วนขยาย small-cap ของการวัด residual หลังข่าว (ต่อยอด protocol large-cap ที่มีอยู่ ไม่ทดสอบซ้ำ) — ทั้งหมดต้องรายงาน gross และ net, ใช้ point-in-time data และ out-of-sample 2024–2026

### Cited Findings
- พื้นฐาน H1: PEAD net Sharpe 0.75 ใน small-cap และ 1.05 ใน microcap จากแบบจำลองต้นทุน institutional — [Novy-Marx & Velikov](https://mysimon.rochester.edu/novy-marx/research/ToAatTC.pdf) `[PR]`; แต่ Martineau/Subrahmanyam ชี้ว่า edge กระจุกใน microcap จนอาจไม่ robust — [UCLA Review](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/) `[WP]`
- พื้นฐาน H2: text-based drift ใหญ่กว่า classic PEAD — [PEAD.txt](https://www.philadelphiafed.org/-/media/frbp/assets/working-papers/2021/wp21-07.pdf); sentiment ลบกดราคาวันถัดไปแล้ว revert — [Tetlock (2007)](https://doi.org/10.1111/j.1540-6261.2007.01232.x) `[PR]`
- พื้นฐาน H3: 76% ของ reaction 120 วินาทีเกิดภายใน 60 วินาที และ reaction เฉลี่ยของ press release เพียง ~2 bps — [von Beschwitz et al.](https://www.federalreserve.gov/econres/ifdp/files/ifdp1233.pdf) `[PR]`; หุ้นใหญ่ราคาขยับใน ms — [UCSD](https://today.ucsd.edu/story/earnings-news-cause-immediate-stock-price-jumps-sometimes-moving-whole-market) `[PR]`

### H1 — Small-cap earnings drift (long-only, 20 วัน)
- **จักรวาล**: US, 2020-01-01 ถึง 2026-06-30, ราคา > $3, mcap $50M–$1B, ADV20 > $1M, ประกาศผลหลังปิด (AMC)
- **สัญญาณ**: SUE top decile (seasonal random walk with drift หรือ analyst consensus ถ้ามี) + revenue surprise > 0 + gap วันถัดไป +2% ถึง +15% (ตัดพวก gap >15% ที่ priced เกิน)
- **เข้า**: MOC ที่ราคาปิดของวันถัดไป (หรือ VWAP 30 นาทีแรก) — ไม่ใช้ market order ที่ open เพราะ auction spread กว้าง
- **ออก**: MOC วันที่ 20; stop ถ้าปิดต่ำกว่า −10%; ไม่ถือข้าม earnings รอบถัดไป
- **ควบคุม**: (1) กลุ่ม SUE middle decile ขนาด/BM/momentum ใกล้เคียง, (2) placebo entry ที่วัน announcement −10, (3) ควบคุม market/size/momentum factor, (4) ตัด M&A/offering/biotech binary
- **ต้นทุน**: 150 bps base, 300 bps stress; รายงานทั้ง gross/net และ turnover
- **เกณฑ์ตัดสิน**: net alpha t-stat (Newey-West) ≥ 2.0 in-sample และ ≥ 1.5 out-of-sample 2024–2026; ถ้า net alpha < 150 bps/เดือน ให้ยกเลิก
- **กำลังทางสถิติ**: ต้องมี ~800 events เพื่อจับ edge 1%/เดือนที่ vol 10% ด้วย power 80% (หรือ ~400 events สำหรับ edge 1.4%/เดือน)

### H2 — Slow-text drift จาก 8-K/ข่าว (3–5 วัน, latency-tolerant)
- **จักรวาล**: US, mcap < $2B, ราคา > $3, ADV > $500k
- **เหตุการณ์**: 8-K item 2.02/7.01/8.01 หรือ press release ผ่าน RSS; เผยแพร่ 09:30–16:00 ET หรือ AMC
- **สัญญาณ**: tone (FinBERT/LM) extreme decile บวกหรือลบ; **under-reaction proxy**: |ราคาเปลี่ยน 30 นาทีแรก| < 50% ของ median reaction ของ tone ระดับเดียวกัน; pre-event 5-day abnormal volume < 1.5×; ไม่มี run-up 20 วัน > 15%
- **เข้า**: 10:00 ET วันทำการถัดไป (AMC) หรือ T+30 นาที (RTH)
- **ออก**: ปิดวันที่ 3 (หรือ 5); stop −8%
- **ควบคุม**: tone-neutral events, size/BM/momentum matched, placebo ด้วยการสุ่มวันที่, ตัด M&A/offering/clinical topline
- **ต้นทุน**: 200 bps base, 400 bps stress
- **เกณฑ์ตัดสิน**: net tone-spread ต้อง > 200 bps และ t ≥ 2.0; ถ้า specific-tone portfolio ไม่ชนะ neutral อย่างมีนัยสำคัญ → reject

### H3 — ส่วนขยาย small-cap ของ news latency (ไม่ทดสอบซ้ำ large-cap)
- **ทำก่อน**: อ่านผลของ `research/news_latency/protocol.md` (large cap 104 ตัว, +1m/+5m, 100 คู่, หัก 0.14%) — ถ้า large-cap ไม่มี edge ให้ถือเป็นฐานและไปต่อที่ small cap
- **ข้อมูล**: 500–1,000 press releases ของหุ้น $50M–$500M (RSS/EDGAR timestamp) + quotes จาก Alpaca IEX หรือ Polygon paid trial; ใช้ harness/paired-control เดียวกับ protocol เดิม
- **วัด**: abnormal return ที่ +1m, +5m, +30m และปิดวัน เทียบหุ้นสุ่มที่ match ขนาด/วอลุ่ม (ไม่ใช่ large cap)
- **ต้นทุน**: 150 bps base, 300 bps stress (ไม่ใช่ 0.14%)
- **เกณฑ์**: มีสิทธิ์ทดสอบต่อเมื่อ **mean net paired difference > 0 และ bootstrap 95% interval อยู่เหนือ 0** ด้วย n ≥ 100 คู่ครบ (กฎเดียวกับ protocol เดิม) และ residual median > 2× spread
- **คาดการณ์**: หุ้น >$1B residual ≈ 0 (ปฏิเสธ); หุ้น <$300M อาจ residual เป็นบวก แต่ fill risk/spread จะกินกำไร
- **ควบคุม**: วัดทั้ง market order และ limit at bid; รายงาน fill rate และ slippage; แยกช่วงตลาดปกติ/หลังปิด

### Inferences
- H1/H2 เป็น “slow edge” ที่ retail พอสู้ได้ แต่ผลตอบแทนคาดหวังหลังต้นทุนอยู่ในระดับ 0–2%/เดือน และมีโอกาสสูงที่จะไม่ผ่านเกณฑ์เมื่อใส่ spread จริง
- H3 เป็นการทดสอบที่ถูกที่สุดและให้คำตอบเร็วที่สุด (หลายสัปดาห์–ไม่กี่เดือน, ข้อมูลฟรี/ถูก) — ควรทำก่อนเสี่ยงเงินจริง
- หาก H3 ล้มเหลว (residual < costs) แปลว่ากลยุทธ์ “ไล่ข่าว” ทั้งหมดจบ; เหลือเพียง H1/H2 ที่ต้องถือข้ามวันและทนความผันผวน

### Gaps
- ยังไม่มีชุดข้อมูล point-in-time ที่ตรวจสอบแล้วสำหรับ SUE/tone ในสภาพแวดล้อมฟรี; ต้องสร้างเองและระวัง look-ahead
- ไม่ได้ประมาณการ “expected drift size” ของ microcap PEAD ปี 2020–2025 เป็นตัวเลขเดียว เพราะแหล่งฟรีไม่ให้ตาราง decile return
- ยังไม่ได้ทดสอบว่า IEX quotes เป็น proxy ที่ดีพอสำหรับ microcap (spread อาจกว้างกว่า SIP) — ต้องเทียบก่อนใช้ใน H3

---

## ภาคผนวก: ข้อสรุปที่ “ห้ามอ้าง” ว่าทำเงินได้ (จากหลักฐานที่มี)
- การไล่ซื้อหุ้นใหญ่ทันทีหลัง headline: ไม่มีหลักฐาน after-cost; ตรงกันข้าม หลักฐาน latency ชี้ว่าเหลือ <24% ของ reaction ที่ 60 วินาที และ reaction เฉลี่ยเพียง ~2 bps
- PEAD หุ้นใหญ่/non-microcap: หลักฐานชี้ว่าหายไปตั้งแต่ ~2006
- Google Trends long-only: ผล 326% เป็น in-sample, ไม่หักต้นทุน, และมี survivorship/selection ของคำค้น
- Reddit/WSB long portfolio: alpha 1 วัน ~0.23% หลัง half-spread และมาจาก short side; ไม่ใช่ edge สำหรับบัญชี long-only
- Analyst revisions: drift เดิม 3–9 เดือน แต่ข้อมูล consensus real-time มีต้นทุน $99/เดือน และผลหลัง 2010 อ่อนลงมาก
- **เทียบกับเป้าโครงการ (~3 เท่าต่อเดือน):** edge ที่หลักฐานสนับสนุนในสาย news/attention อยู่ในระดับ ~0–2%/เดือนหลังต้นทุน (และหลายกรณีไม่ผ่านเกณฑ์) ห่างจากเป้าหมายมาก — สายนี้ใช้เป็น “ส่วนประกอบ” หรือเพื่อหักล้างสมมติฐานได้ แต่ไม่พอเป็นกลไกหลักของเป้า 3 เท่า
