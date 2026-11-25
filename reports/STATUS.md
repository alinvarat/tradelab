# สถานะงาน TradeLab (กระดานกลาง)

อัปเดตทุกครั้งที่จบงาน ตามขั้นตอนใน `ops/RUNBOOK.md` เวลาในไฟล์นี้เป็น UTC
งานถัดไป = แถวบนสุดของตาราง "คิวงาน" ที่ยังไม่ใช่ `done` หรือ `killed`

## ด่วน (2026-11-25 line/thin-b)
- **Thin B (ตลาดทำนายสภาพคล่องต่ำ 7 กติกา):** run 45523514648: B1 และ B2 ถูกตัด (validation -6.2% / -6.9%); B3, B4, B5, B7 ไม่มีข้อมูล (หา event ไม่เจอ); B6 ข้อมูลไม่ valid (ซ้ำ 65%); ไม่มีกติกาผ่าน; ส่วนตะกร้าที่ยังไม่ได้ทดสอบต้องแก้ตัวดึงข้อมูลภายใต้ addendum ใหม่ (PR #180)

## ด่วน (2026-11-25 line/opt-vol-sell)
- **opt_vrp (PR #175):** ถูกตัด (run 45520875720) ทั้ง 16 test หยุดที่ step 0 เพราะแม้ชนะทุกไม้ก็ไม่ถึง 3 เท่าต่อเดือน และมีโอกาสสูงสุด 0.94 ครั้ง/สัปดาห์ (R2)

## ด่วน (2026-11-25 ผลด่าน H1-H4 และ factory_crypto_2)
- **ผลทั้ง 5 ด่านลง `research/studies/RESULTS.md` แล้ว** (PR #173, #172, #170, #174, #164 merge เข้า main; ตัวเลขจาก summary JSON ของ Actions): ไม่มีเส้นไหนผ่าน ไม่มีอะไรให้ทดสอบเดินหน้า
- **H1 `long_discount` = inconclusive** (run 45515874060): 47,964 เหตุการณ์; validation +0.614% p 0.0005, ต้นทุน 2 เท่า +0.414%, แต่ test -0.075% (n 35,018) และเฉลี่ยรายปีลดจาก 2024 +1.02% → 2025 +0.06% → 2026 -0.16%; control ออกเมื่อครบ 4 ชม. validation +1.19% test +0.20% p 0.34 → edge หายในช่วง test จึงไม่ทดสอบเดินหน้า เว้นแต่มีสมมติฐานใหม่ที่ลงทะเบียนก่อน; `short_premium` killed (validation -0.724%)
- **H2 killed ทั้งสองฝั่ง** (run 45515954945): long d7 validation -1.519% (p 0.945), short d1 validation -0.924%, ต้นทุน 2 เท่าติดลบทั้งคู่
- **H3 killed** (run 45515911822): market making แบบ passive ขาดทุนสุทธิทุกช่วงและทุกระยะ k (k8 validation -0.343 clip ต่อ symbol-day, p 1.0; แย่กว่าวันที่กลับเวลา -0.143)
- **H4 killed** (run 45515772654): ทุกการถือ (15/30/60 นาที) ติดลบทุกช่วง (m30 validation -0.265%); มีเหตุการณ์ 1.84 ครั้งต่อสัปดาห์ น้อยกว่าเกณฑ์ 3
- **factory_crypto_2 รอบ 2 killed 0/7** (run 45518490639): validation เฉลี่ยรายวันติดลบทั้ง 7 กติกา (A1 -0.0035%, A6 -1.34%); ครอบคลุมข้อมูลครบแล้ว (898 perps มีแท่ง, ดาวน์โหลดล้ม 0) ผลเท่ารอบ 1

## ด่วน (2026-11-25 line/thin-a)
- **Thin A (ตลาดคริปโตรอง KuCoin/MEXC/Bitget/Gate):** กติกา 6 ข้อ ลงทะเบียนก่อนดึงข้อมูลใน RESULTS.md ("Thin A"); run 45523510003: A1/A2 (ซื้อเหรียญลิสต์ใหม่) ผ่านตามตัวเลขแต่**ไม่รับ** เพราะกำไรมาจาก MEXC เหรียญมีมไม่กี่ตัว (ตัดบนสุด 5% แล้วติดลบ), A3/A6 inconclusive, A4/A5 ตัด. ไม่มีข้อมูลเหรียญที่ถูก delist (ทุกที่ไม่ให้) จึงเปิดตัวเก็บแบบเดินหน้า F1-F3 (job `thin_a`, branch `data/thin-a-forward`, ตัวจับเวลา systemd ฝั่งเครื่องเจ้าของ `tradelab-dispatch-thin_a_forward.timer` ทุกชั่วโมงที่ :23)

## ด่วน (2026-11-25 line/h1_basis_snapback)
- **H1 (perp ต่ำกว่า index แล้วเด้งกลับ + ฝั่งตรงข้าม):** ลงทะเบียนกติกาใน `research/studies/RESULTS.md` แล้ว (ก่อนดึงข้อมูล); โค้ด `core.screens.basis_snap_rows` + `rows_/summarize_h1_basis_snapback` ใน `run.py`; เทสต์ `tests/test_h1_basis.py`; ยังไม่ได้รัน → หลัง merge: `gh workflow run research_sharded.yml -f study=h1_basis_snapback -f shards=20`

## ด่วน (2026-11-25 ops/sharded-runner)
- **ตัวรันแบบแบ่ง shard:** workflow `research_sharded.yml` กระจายหนึ่งด่านไปหลาย job พร้อมกัน (ค่าเริ่ม 20) แล้วรวมผล; ด่านที่จะใช้ต้องมี `rows_<study>(symbols_slice)` และ `summarize_<study>(all_rows)` ใน `run.py`; ยังไม่ได้ทดสอบบน Actions จริง (workflow_dispatch ใช้ได้หลัง merge เข้า main) → หลัง merge ให้รัน `study=selftest_shard` ก่อน

## ด่วน (2026-11-24 23:30 UTC)
- **factory_crypto_3 (2026-11-25, run 45524122159):** กติกา trend/event 10 ข้อบน perp สภาพคล่องสูง 6 ตัว ไม่ผ่านทั้งหมด (validation p ดีสุด 0.17 เทียบเกณฑ์ 0.005); เดือน 3x มี 2 เดือนที่ 8x แต่ median 0.95x จึงเป็นความแปรปรวน ปิดตระกูลนี้ รายละเอียดใน RESULTS.md
- **เครดิต DeepSeek หมด:** probe บน Actions (run 45509191649) เรียก `api.deepseek.com` model `deepseek-flash` ได้ HTTP 402 Payment Required ทุกครั้ง → N1 news_v3 สองรอบไม่ได้เรียกโมเดลเลย (v3 = 0 เทรด, ผลใช้ไม่ได้) และบอท DeepSeek บน Kuber ก็เรียกไม่ได้เช่นกัน; ต้องให้เจ้าของเติมเครดิตหรือเลือกโมเดลอื่นด้วย protocol ใหม่
- **ผลวันนี้:** L12 ผ่านบนทุกเหรียญ แต่ L12b (เฉพาะเหรียญที่ short ได้จริง + funding จริง) ไม่ผ่าน; factory ชุด 1 ไม่ผ่านทั้ง 11 กติกา; workflow ค้นไอเดีย 4 มุมกำลังเขียน `factory_crypto_2` และ `factory_us_pit_1`

## ด่วน (2026-11-24 22:05 UTC)
- **รันบนเครื่องเจ้าของชั่วคราว (เจ้าของสั่ง):** unit `tradelab-local` ที่ `~/Project/tradelab-local` → http://127.0.0.1:8770; บอท v4.18 Claude Haiku 5.5 ผ่าน Claude Code ที่ล็อกอิน Max (ตรวจ 22:00 UTC: protocol v4.18, model claude/claude-haiku-5-5, error ไม่มี) เป็นบัญชีจำลองแยกจาก Kuber เริ่ม 147.5 USD
- **N1 run 45481243341 ใช้ไม่ได้** (env ของ provider ว่าง ไม่ได้เรียกโมเดลเลย) → รันใหม่จาก main: 45495806547
- **L8b:** ไม่ผ่าน (validation +0.52% p 0.17, ต้นทุน 2 เท่าติดลบ)
- **cron ของ GitHub ไม่เคยยิง** → ใช้ systemd timer บนเครื่องเจ้าของสั่ง `gh workflow run` แทน: L4f ทุก :17/:47, ออปชัน จ.–ศ. 15:00 UTC, ข่าวงบ อา. 03:00 UTC (unit `tradelab-dispatch-*`); ตรวจแล้ว L4f run 45495947030 สำเร็จและ commit ledger 21:55 UTC; ทำงานเฉพาะตอนเครื่องเปิด
- **Actions รันได้แล้ว:** repo เปลี่ยนเป็น public (เจ้าของเลือก แทนการจ่ายเงิน) หลังนาทีฟรีของ repo private หมด
- **deploy ยังล้ม:** Kuber ปฏิเสธที่ "Uploading context: 0 B" ภายใน 1–2 วินาทีทุกครั้งตั้งแต่ 20:04 UTC (issue #80) → เว็บจริงค้างที่ build 19:17 UTC; PR #149–#155 merge แล้วแต่ยังไม่ขึ้นเครื่อง
- **บอท DeepSeek v4.17 รันอยู่จริง** (ตรวจ `/api/llm_trader` ผ่าน Chrome 20:58 UTC): 284 calls วันนี้, ถือ 8 ไม้, ปิด 28/30 คู่, 142.81 vs สุ่ม 146.98 USD; หน้าเว็บโชว์ "Could not load: openrouter 402" เพราะบั๊ก `api()` (แก้แล้วใน PR #154 รอ deploy)
- **cron ไม่เคยยิง:** ไม่มีรันจาก schedule เลย → L4f, ออปชัน, ข่าวงบรายสัปดาห์ ยังไม่เก็บข้อมูลจริง
- **v4.18 Claude Haiku 5.5:** merge แล้ว รอ `CLAUDE_CODE_OAUTH_TOKEN` + deploy ที่ผ่าน; ผลจะไม่รวมกับ DeepSeek (PR #156)
- **เส้นวันนี้:** L8, L9, L10, L11 ถูกตัด; บั๊กสูตร short ใน screens (L7/L8/L10) แก้แล้ว; L8b (ทุกเหรียญที่เคยลิสต์) กำลังรัน; N1 news_v3 กำลังรัน

## สุขภาพระบบ (ตรวจล่าสุด 2026-11-24 19:25 UTC)
| ส่วน | สถานะ | รายละเอียด |
|---|---|---|
| deploy main | ผ่าน | PR #143 (ผล L7) และ #145 (ผู้ให้บริการ LLM ทั่วไป) merge แล้ว deploy ผ่าน (run 45467480935 success) |
| บอท DeepSeek (v4.17) | รันอยู่ | `error` ว่าง, `paused` false, `last_scan_age_s` 21; 142.72 USD เทียบบัญชีสุ่ม 147.07 USD; ปิดแล้ว 22/30 คู่ |
| ค่า AI วันนี้ | เฝ้าดู | `usd_today` 2.89 จาก 247 calls (ราว 0.012 USD/ครั้ง) ยังไม่ถึงเพดาน 1,000 รอบ/วัน; ไม่มีเพดานงบตามที่เจ้าของกำหนด — บันทึกใน `reports/COSTS.md` |
| ออปชันแบบเดินหน้า | เก็บข้อมูล | 0/150 เทรด, `gaps` 0 |
| ข่าวงบ H5 แบบเดินหน้า | รอ | เริ่มนับ 1 ธ.ค. |
| ตัวเก็บข้อมูล (`/api/collect`) | เก็บอยู่ | venues และ deribit มีไฟล์ของวันนี้, `errors` 0, `paused_low_disk` false; Upbit ยัง 403 จาก Kuber |

## บอท DeepSeek (ตรวจ Chrome 2026-11-24 18:16 UTC)
- แท็ก v4.17; ทุกบทบาทใช้ DeepSeek v4.1 flash 1017 ผ่าน ai.thirx.com (OpenRouter เครดิตหมด 402 ตั้งแต่ 16:59)
- ทำงานเองอัตโนมัติ: desk_stats + similar_past + 8-K + sector + ความรู้ (ops/knowledge) และทุก 3 ชม. DeepSeek สรุป desk_lessons ให้ตัวเอง (รอบแรกได้ 8 บทเรียน)
- เพดาน 1,000 รอบ/วัน
- ข้อสังเกต: บทเรียนรอบแรกบางข้ออ้างกลุ่มที่ n < 10 แม้ prompt สั่งไว้ ต้องเฝ้าดู
- งานถัดไป (ROADMAP 1.4.3): N1 ผล v3 (กำลังรันบน thirx, run 45447954735), N4 ซ้อมย้อนหลังจำนวนมาก, N5 ตัวให้คะแนนที่เรียนจากข้อมูล

## เส้นกลยุทธ์ (sprint ข้อ 1.5 ใน ROADMAP)
| เส้น | สเปก | สถานะ | ผลล่าสุด | ขั้นต่อไป |
|---|---|---|---|---|
| L1 listing | `ops/lines/L1_listings.md` | killed (ตามกฎ) → L1b | รอบ 2: กฎเลือก 7 วันแล้วไม่ผ่าน; ถือ 4 ชม. บวกทุกช่วง (validation +10.2% p 0.0075, test +9.3%) แต่มีเหตุการณ์แค่ราว 1 ครั้งต่อเดือน | L1b: ล็อกกติกาถือ 4 ชม. แบบเดินหน้า + เพิ่มตัวดึงประกาศหลาย exchange บน Kuber |
| L2 unlock | `ops/lines/L2_unlocks.md` | inconclusive | 1,172 เหตุการณ์; pick post0_7 test −1.5%; pre7_0 บวกทุกช่วงแต่แพ้ต้นทุน 2 เท่า | ถ้าจะทดสอบต่อ ต้องล็อกโปรโตคอลใหม่ |
| L3 หุ้นเล็กมีข่าว | `ops/lines/L3_smallcap_news.md` | killed | ไม่มีกลุ่มผ่าน (Bonferroni) | — |
| L4 Polymarket maker | `ops/lines/L4_polymarket_maker.md` | killed; L4f รันต่อ (ไม่มีค่าใช้จ่าย, ความสำคัญต่ำ) | รอบ 4: ราว break-even | — |
| L5 ออปชันข่าวทุกประเภท | `ops/lines/L5_options_all_news.md` | forward | 0/150 | ตรวจรอบ 15:00 UTC; รีวิว PR #77, #79 |
| L6 insider หุ้นเล็ก | `ops/lines/L6_smallcap_insider.md` | killed | ไม่มี edge หลังต้นทุน | — |
| L7 first red day | `ops/lines/L7_first_red_day.md` | killed (ต้นทุน 2 เท่า) / ไม่ผ่านที่ต้นทุนปกติ | h5: train +2.55% p 0.001, validation +1.29% p **0.085**, test +4.23% p 0.0005; ต้นทุน 2 เท่า validation +0.29% และตัดไม้ที่ดีที่สุดออกแล้วติดลบ | — |

สถานะที่ใช้ได้: `todo`, `screening`, `passed-screen`, `locked`, `forward`, `paper`, `done`, `killed`, `parked`

## คิวงาน (ทำคู่ขนาน ตามแผนแบบเร็วใน ROADMAP 1.5.4)
เป้าเดียวของทุกงานคือบัญชีโต 3 เท่าต่อเดือนขึ้นไป งานที่ไม่ช่วยเป้านี้ไม่เข้าคิว

| # | งาน | ผู้ทำ | วัน | สถานะ | หมายเหตุ |
|---|---|---|---|---|---|
| 1 | deploy ผ่านและตรวจผ่าน Chrome | Claude | 1 | done | 09:47 |
| 2 | ด่านคัดกรอง L1 | Claude | 1 | done | killed ตามกฎ; เปิด L1b |
| 2b | L1b: protocol ถือ 4 ชม. + ตัวดึงประกาศ listing บน Kuber + บัญชีจำลอง | Claude | 2 | forward | ขึ้นระบบแล้ว (ตรวจ Chrome 10:52): Binance poll ทุก 30 วิ ไม่มี error, บัญชี 147/441 USD; Upbit ตอบ 403 จาก Kuber แม้ใช้ UA แบบเบราว์เซอร์ (น่าจะบล็อก IP) |
| 2d | L1c ด่านคัดกรอง (Binance futures launch / Will Add) | Claude | 1 | killed | 115 เหตุการณ์ ซื้อแล้วลบทุกระยะ; 7 วันลบทุกช่วง → เปิด L1d |
| 2e | L1d: short 7 วันหลังประกาศ futures launch (เดินหน้า) | Claude | 2 | forward | ขึ้นระบบแล้ว (ตรวจ Chrome 12:20): ledger l1d 147 USD ใน /api/collect |
| 2f | L1e ด่านคัดกรอง short หลังประกาศ delist | Claude | 1 | killed (ตามกฎ) → L1f | กฎเลือก 7 วัน ALPACA squeeze; ถือ 4 ชม. บวก 91/105 ครั้ง ทุกช่วง (test +11.2% p 0.0005) |
| 2g | L1f: short 4 ชม. หลังประกาศ delist, stop 25% (เดินหน้า) | Claude | 2 | forward | ขึ้นระบบแล้ว (ตรวจ Chrome 12:33): ledger l1f 147 USD; Binance delist poll ไม่มี error |
| 2h | L1g ด่านคัดกรอง short หลัง Binance Alpha removal | Claude | 1 | no verdict | หาราคาได้ 13/132 (ปี 2026 เท่านั้น) ต้องมีแหล่งราคา DEX |
| 2i | บอทกติกาแบบกว้าง broad-v1 (จักรวาลเดียวกับ DeepSeek) | Claude | 1 | forward | ขึ้นระบบ 13:40, /api/events_broad 5 เหตุการณ์ 147.28 USD |
| 2j | v4.3: โมเดลฟรีสำหรับบทบาทผู้ช่วย, DeepSeek ตัดสินใจ | Claude | 1 | live | ดู helper_models ใน /api/llm_trader |
| 2k | L7 ด่านคัดกรอง: short วันแรกที่ปิดแดงหลังหุ้นเล็กวิ่งหลายวัน (Tim Sykes "first red day") | Claude | 2 | **killed** | run 45463480460: 1,597 เหตุการณ์, 3.1 ครั้ง/สัปดาห์; h5 validation +1.29% p 0.085 (ไม่ผ่านเกณฑ์ 0.05) และต้นทุน 2 เท่าติดลบหลังตัดไม้ที่ดีที่สุด → หยุดเส้นนี้ ตามเกณฑ์ที่ลงทะเบียนไว้ก่อนรัน |
| 2l | L8 ด่านคัดกรอง: short เหรียญที่ขึ้น ≥ 20% ในวัน UTC (Binance spot, h1/h3/h7) | Claude | 1 | locked | PR #151; รอ Actions กลับมา |
| 2m | L9 ด่านคัดกรอง: long เหรียญที่ร่วง ≥ 20% ในวัน UTC | Claude | 1 | locked | PR #151; ล็อกก่อนเห็นผล L8 |
| 2n | v4.18: ทุกบทบาทใช้ Claude Haiku 5.5 ผ่าน Claude Code CLI (Max plan) | Claude | 1 | รอเจ้าของ | ต้องตั้ง `CLAUDE_CODE_OAUTH_TOKEN` + deploy ผ่าน |
| 2c | เพิ่มแหล่งประกาศ listing ที่ Kuber เข้าถึงได้ (Upbit ทางอื่น, Bithumb, OKX, Bybit, Coinbase) ด้วย addendum ก่อนเหตุการณ์แรก | เพื่อน (dmgnr) หรือ Claude | 2 | todo | เพิ่มความถี่ของ L1b |
| 3 | ด่านคัดกรอง L3 | Claude (รับแทน) | 1 | killed | 315 เหตุการณ์; กลุ่ม 2.02 ไม่ผ่าน, กลุ่มอื่นน้อยเกิน |
| 4 | ด่านคัดกรอง L4 | Claude (รับแทน) | 1 | killed | รอบ 4 (ข้อมูลไม่ซ้ำ 2,613 เหตุการณ์): validation +0.35%/ครั้ง p 0.39 |
| 4b | L4f: ขาย longshot บน Polymarket 1 วันก่อนปิด (เดินหน้า, Actions ทุก 30 นาที) | Claude | 1 | forward | data/l4f-forward; 14:12 เข้า 2 ตลาด (Barcelona NO 0.09, BTC>56k NO 0.042) |
| 4c | forward L12B_F (short หลังแท่ง 1 ชม. ขึ้น ≥ 8%) และ L8B_F (short หลังวัน UTC ขึ้น ≥ 20%): ทดสอบเดินหน้าของ screen ที่ยังไม่สรุป ไม่ใช่การผ่าน | Claude | 1 | forward | protocol_fwd_crypto_spikes_20261125.md; ราคา spot data-api.binance.vision + perp/funding OKX (fapi 451); data/fwd-crypto-spikes; ทุกชม. นาทีที่ 5 |
| 5 | หาแหล่งข้อมูล L2 | Claude | 1 | done | DefiLlama datasets (ฟรี) |
| 6 | deploy ให้เสถียร (registry DNS, ข้าม deploy เมื่อแก้แค่เอกสาร, แจ้งเตือน) | เพื่อน (dmgnr) | 1 | todo | issue #89, #80 |
| 7 | รีวิว PR #77–#79 ของ Codex | Claude | 1 | done | merge แล้ว: ออปชันอ่าน 8-K ทุกประเภทตั้งแต่ 25 พ.ย. (options-v2-sec) + e-process รายวัน |
| 8 | หน้าเว็บแสดงความคืบหน้าสู่ 3 เท่าแทน "x/30 คู่" | Claude | 1 | done | ตรวจแล้วว่า app.js บนเว็บมี target3x |
| 9 | ด่านคัดกรอง L6 | Claude (รับแทน) | 2 | killed | 3,857 เหตุการณ์ข้อมูลสะอาด; validation h5 -0.4% |
| 10 | ล็อก protocol ของเส้นที่ผ่าน | ผู้ทำเส้นนั้น | 2 | todo | |
| 11 | ส่งสัญญาณของเส้นที่ผ่านเข้าบัญชีจำลองบน Kuber | Claude | 3 | todo | |

## งานเปิดสำหรับผู้ร่วมงานใหม่ (ดู `ops/ONBOARDING.md`)
| issue | งาน | สถานะ |
|---|---|---|
| #113 | หน้าเว็บสำหรับบัญชีทดสอบแบบเดินหน้า (L1b/L1d/L1f/L4f) และบอทกติกาแบบกว้าง | ว่าง |
| #114 | แหล่งประกาศ listing ที่ Kuber เข้าถึงได้ (เพิ่มเหตุการณ์ L1b) | ว่าง |
| #115 | แหล่งราคา DEX สำหรับเหรียญ Binance Alpha (L1g) | ว่าง |
| #88 | หาแหล่งข้อมูล token unlock ฟรี (L2) | done (Claude) |
| #89 | ทำให้ deploy บน Kuber เสถียร | dmgnr |

## ความคืบหน้าหน้าเว็บ
- PR #130 เพิ่มคำแปลไทยสำหรับ Auto/Markets/Chart/Portfolio/Backtest พร้อมเทสต์ Chrome ใน CI จากข้อมูลจำลอง รอรีวิวก่อนรวม หลัง deploy ให้ตรวจสลับภาษาไทย↔อังกฤษบน Kuber แบบอ่านอย่างเดียวทั้งห้าหน้า (รอบนี้ยังตรวจเว็บจริงไม่ได้: Chrome `Target closed` / Cloudflare Access 302 เมื่อไม่ได้ล็อกอิน)

## รอเจ้าของตัดสิน
- (ทำแล้ว) Actions กลับมาด้วยการเปิด repo เป็น public; แผนระยะยาว: self-hosted runner บน Kuber แล้วกลับเป็น private
- เพื่อน (dmgnr) ตรวจ Kuber deploy ที่ปฏิเสธทุกครั้ง (issue #80)
- สร้าง token: รัน `claude setup-token` ใน terminal ของตัวเอง แล้ว `gh secret set CLAUDE_CODE_OAUTH_TOKEN -R alinvarat/tradelab` (วางที่ prompt แบบซ่อน ไม่ส่งในแชต); บอทจะใช้โควตา Max ร่วมกับการใช้ Claude ของเจ้าของ
