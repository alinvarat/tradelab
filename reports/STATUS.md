# สถานะงาน TradeLab (กระดานกลาง)

อัปเดตทุกครั้งที่จบงาน ตามขั้นตอนใน `ops/RUNBOOK.md` เวลาในไฟล์นี้เป็น UTC
งานถัดไป = แถวบนสุดของตาราง "คิวงาน" ที่ยังไม่ใช่ `done` หรือ `killed`

## สุขภาพระบบ (ตรวจล่าสุด 2026-11-24 09:47)
| ส่วน | สถานะ | รายละเอียด |
|---|---|---|
| deploy main | ผ่าน | ล้มฝั่ง Kuber ตั้งแต่ 07:07 แล้วผ่านเมื่อรันซ้ำตอน 09:45; ตรวจผ่าน Chrome แล้วว่า PR #69–#76 ขึ้นระบบจริง (ตำแหน่งมีฟิลด์ `market_open` และ `exit_queued`) |
| บอท DeepSeek (v4.2) | รันอยู่ | ปิดได้ 3/30 คู่, 144.46 USD เทียบบัญชีสุ่ม 147.05 USD, `usd_today` 0.44, 73 calls, `error` ว่าง |
| ออปชันแบบเดินหน้า | เก็บข้อมูล | 0/150 เทรด, `gaps` 0 (อัปเดต 04:40) |
| ข่าวงบ H5 แบบเดินหน้า | รอ | เริ่มนับ 1 ธ.ค. |
| ตัวเก็บข้อมูล (`/api/collect`) | เก็บอยู่ | venues และ deribit มีไฟล์ของวันนี้, `errors` 0, `paused_low_disk` false |

## เส้นกลยุทธ์ (sprint ข้อ 1.5 ใน ROADMAP)
| เส้น | สเปก | สถานะ | ผลล่าสุด | ขั้นต่อไป |
|---|---|---|---|---|
| L1 listing | `ops/lines/L1_listings.md` | killed (ตามกฎ) → L1b | รอบ 2: กฎเลือก 7 วันแล้วไม่ผ่าน; ถือ 4 ชม. บวกทุกช่วง (validation +10.2% p 0.0075, test +9.3%) แต่มีเหตุการณ์แค่ราว 1 ครั้งต่อเดือน | L1b: ล็อกกติกาถือ 4 ชม. แบบเดินหน้า + เพิ่มตัวดึงประกาศหลาย exchange บน Kuber |
| L2 unlock | `ops/lines/L2_unlocks.md` | todo | — | หาแหล่งข้อมูลฟรี (จำกัด 2 ชม.) |
| L3 หุ้นเล็กมีข่าว | `ops/lines/L3_smallcap_news.md` | killed | ไม่มีกลุ่มผ่าน (Bonferroni) | — |
| L4 Polymarket maker | `ops/lines/L4_polymarket_maker.md` | killed; L4f รันต่อ (ไม่มีค่าใช้จ่าย, ความสำคัญต่ำ) | รอบ 4: ราว break-even | — |
| L5 ออปชันข่าวทุกประเภท | `ops/lines/L5_options_all_news.md` | forward | 0/150 | ตรวจรอบ 15:00 UTC; รีวิว PR #77, #79 |
| L6 insider หุ้นเล็ก | `ops/lines/L6_smallcap_insider.md` | killed | ไม่มี edge หลังต้นทุน | — |

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
| 2c | เพิ่มแหล่งประกาศ listing ที่ Kuber เข้าถึงได้ (Upbit ทางอื่น, Bithumb, OKX, Bybit, Coinbase) ด้วย addendum ก่อนเหตุการณ์แรก | เพื่อน (dmgnr) หรือ Claude | 2 | todo | เพิ่มความถี่ของ L1b |
| 3 | ด่านคัดกรอง L3 | Claude (รับแทน) | 1 | killed | 315 เหตุการณ์; กลุ่ม 2.02 ไม่ผ่าน, กลุ่มอื่นน้อยเกิน |
| 4 | ด่านคัดกรอง L4 | Claude (รับแทน) | 1 | killed | รอบ 4 (ข้อมูลไม่ซ้ำ 2,613 เหตุการณ์): validation +0.35%/ครั้ง p 0.39 |
| 4b | L4f: ขาย longshot บน Polymarket 1 วันก่อนปิด (เดินหน้า, Actions ทุก 30 นาที) | Claude | 1 | forward | data/l4f-forward; 14:12 เข้า 2 ตลาด (Barcelona NO 0.09, BTC>56k NO 0.042) |
| 5 | หาแหล่งข้อมูล L2 | เพื่อน (dmgnr) | 1 | todo | issue #88 |
| 6 | deploy ให้เสถียร (registry DNS, ข้าม deploy เมื่อแก้แค่เอกสาร, แจ้งเตือน) | เพื่อน (dmgnr) | 1 | todo | issue #89, #80 |
| 7 | รีวิว PR #77–#79 ของ Codex | Claude | 1 | done | merge แล้ว: ออปชันอ่าน 8-K ทุกประเภทตั้งแต่ 25 พ.ย. (options-v2-sec) + e-process รายวัน |
| 8 | หน้าเว็บแสดงความคืบหน้าสู่ 3 เท่าแทน "x/30 คู่" | Claude | 1 | done | ตรวจแล้วว่า app.js บนเว็บมี target3x |
| 9 | ด่านคัดกรอง L6 | Claude (รับแทน) | 2 | killed | 3,857 เหตุการณ์ข้อมูลสะอาด; validation h5 -0.4% |
| 10 | ล็อก protocol ของเส้นที่ผ่าน | ผู้ทำเส้นนั้น | 2 | todo | |
| 11 | ส่งสัญญาณของเส้นที่ผ่านเข้าบัญชีจำลองบน Kuber | Claude | 3 | todo | |

## รอเจ้าของตัดสิน
- ไม่มี
