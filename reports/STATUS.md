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
| L1 listing | `ops/lines/L1_listings.md` | todo | — | ลงทะเบียนเกณฑ์ใน RESULTS แล้วเขียนตัวดึงประกาศ Binance + Upbit |
| L2 unlock | `ops/lines/L2_unlocks.md` | todo | — | หาแหล่งข้อมูลฟรี (จำกัด 2 ชม.) |
| L3 หุ้นเล็กมีข่าว | `ops/lines/L3_smallcap_news.md` | todo | — | ลงทะเบียนเกณฑ์ แล้วสร้างรายการ event 8-K นอกเวลา |
| L4 Polymarket maker | `ops/lines/L4_polymarket_maker.md` | todo | — | ดึงรายการตลาดที่จบแล้ว |
| L5 ออปชันข่าวทุกประเภท | `ops/lines/L5_options_all_news.md` | forward | 0/150 | ตรวจรอบ 15:00 UTC; รีวิว PR #77, #79 |
| L6 insider หุ้นเล็ก | `ops/lines/L6_smallcap_insider.md` | todo | — | หลัง L1–L4 |

สถานะที่ใช้ได้: `todo`, `screening`, `passed-screen`, `locked`, `forward`, `paper`, `done`, `killed`, `parked`

## คิวงาน (เรียงตามลำดับ)
| # | งาน | เจ้าของงาน | สถานะ | หมายเหตุ |
|---|---|---|---|---|
| 1 | ทำให้ deploy ผ่าน แล้วตรวจหน้าเว็บด้วย Chrome | AI | done | 09:47 |
| 2 | ด่านคัดกรอง L1 | AI | todo | |
| 3 | ด่านคัดกรอง L3 | AI | todo | |
| 4 | รีวิวและ merge PR #77, #79 (และ #78 protocol คริปโต) | AI | todo | อ่าน diff ทั้งหมด |
| 5 | หาแหล่งข้อมูล L2 | AI | todo | จำกัดเวลา 2 ชม. |
| 6 | ด่านคัดกรอง L4 | AI | todo | |
| 7 | ด่านคัดกรอง L6 | AI | todo | |

## รอเจ้าของตัดสิน
- ไม่มี
