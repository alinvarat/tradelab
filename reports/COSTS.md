# ค่าใช้จ่าย AI และข้อมูล

ให้บันทึกทุกงานที่เรียก LLM หรือใช้บริการเสียเงิน ใช้ค่า `usage.cost` จริงจาก OpenRouter ห้ามใช้ค่าประมาณ
ค่าใช้จ่ายรายวันของบอทให้อ่านจาก `usd_today` ใน `/api/llm_trader`

| วันที่ (UTC) | งาน | USD | หมายเหตุ |
|---|---|---|---|
| 2026-11-23 | news_v2 (งานวิจัย) | 1.89 | เกินประมาณการเดิมที่ 0.6–0.9 |
| 2026-11-24 | บอท DeepSeek | 0.40 | ค่า ณ 09:50 UTC จาก 72 calls |
| 2026-11-24 | บอท DeepSeek (ทั้งวัน ถึง 19:25 UTC) | 2.89 | 247 calls ≈ 0.012 USD/ครั้ง สูงกว่าช่วงปกติ 0.005–0.01 เล็กน้อยหลังย้ายไปผู้ให้บริการตรง; ไม่มีเพดานงบ |
| 2026-11-24 | `probe_llm_cost` (รันโดยไม่ตั้งใจจาก push ไป research-run/l1_listings) | ยังไม่ทราบ | ยกเลิกงานอื่นทันที ตัวนี้รันจบไปก่อน |
| 2026-11-26 | `news_latency_fwd` (forward, Claude Haiku 5.5 ผ่าน CLI บนแผน Max) | 0.00 (แผนไม่มีบิลต่อครั้ง) | เพดาน 500 ข่าวหุ้น + 400 ข่าวคริปโตต่อวัน; จำนวนครั้ง/โทเคน/มูลค่า list-price (notional) อยู่ใน `llm_spend_this_process` ของ `summary.json` บน branch `data/news-latency-fwd`; จะคัดลงตารางนี้เมื่อรีวิวผล |
| 2026-11-26 | news_train (Claude Haiku 5.5, Max plan): leak probe, v0-v4 evals, sealed run 45771881654 | 0 (แผน Max) | ตัวอย่างที่นับได้: eval รอบแรก 8,955 calls, 15.6M tokens เข้า / 1.9M ออก, list-price เชิงสมมติ 3.74 USD; sealed 717 calls, 1.87M tokens เข้า, 0.46 USD เชิงสมมติ; รอบ v3/v4 และ leak ดูใน log ของ run 45770547487 / 45759766585; ไม่ได้จ่ายจริง |

**กติกา:** ไม่มีเพดานงบ (เจ้าของตัดสินแล้ว) แต่ถ้างานใดใช้เกิน 2 เท่าของที่ประมาณไว้ ให้บันทึกสาเหตุไว้ในแถวของงานนั้น

งานออปชันแบบเดินหน้าบันทึกค่า LLM สะสมแยกตามโปรโตคอลไว้ใน `llm_cost_usd_recorded` ของ summary ใน branch `data/options-forward` ให้คัดค่าจริงมาลงตารางนี้เมื่อรีวิวผล
| 2026-11-26 | key-person 8-K 5.02 labels (Haiku, 3,962 calls) | 0.00 paid | Max plan; notional list price 1.56 USD (7.77M in, 0.99M out tokens); run 45754052124 |
| 2026-11-26 | news_train round 2 (Claude Haiku 5.5, Max plan): evals w0-w3 train+validation, analysis, sealed crypto run 45801945782 | 0 paid (Max) | sealed crypto 1,971 calls, 2.03M tokens in / 0.70M out, notional 0.76 USD; eval run 45789213718 about 4 x 5,000 calls (tokens in the Actions logs); forward job adds about 13 items a day |
| 2026-11-26 | news_train round 3 (Claude Haiku 5.5, Max plan): Track A evals m0-m2 train+validation (run 45810083006, 3 x about 2,950 calls), sealed A run 45817169940; Track B eval w1 run 45819459351 (about 2,130 calls), sealed run 45820758150 | 0 paid (Max) | sealed A 518 calls, 1.01M tokens in / 0.17M out, notional 0.29 USD; sealed B 1,798 calls, 1.90M in / 0.65M out, notional 0.71 USD; dev eval token totals in the Actions logs (SPEND line of each eval_merge) |
| 2026-11-26 | news_train CMP (Sonnet 5.5 vs Haiku 5.5, Max plan, owner exception): Sonnet leak probe run 45839708983, historical paired run 45860187012 | 0 paid (Max) | Sonnet: 3,007 historical + 840 probe calls, 4.60M tokens in / 0.34M out (historical), notional 20.63 USD (+ about 1.4 probe incl. in 840-call probe notional 1.42); Haiku: 3,007 calls, 4.66M in / 1.09M out, notional 1.42 USD; no usage limit hit; forward job adds a few hundred calls a day, counts in fwd/progress.json |
