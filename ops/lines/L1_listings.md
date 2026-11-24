# L1 เหรียญเข้า listing ใหม่

**สมมติฐาน:** เมื่อ exchange ใหญ่ประกาศว่าจะ list เหรียญ ราคาของเหรียญนั้นที่ exchange อื่นยังขึ้นต่ออีกหลังเวลาประกาศ ระยะที่ทุนเล็กเข้าทันคือ +1 นาทีขึ้นไป
**หลักฐานเบื้องต้น:** abnormal return +5.7% ในวันแรก และ +10% ใน 7 วัน (BRL 2019; Springer 2021) ตามบันทึกค้นคว้า crypto_futures.md (ในเครื่องเจ้าของ ไม่อยู่ใน repo)
**ความถี่ที่คาด:** Binance และ Upbit รวมกันหลายครั้งต่อสัปดาห์

## ข้อมูล (ตรวจแล้ว 24 พ.ย. 2026 ว่าเรียกได้โดยไม่ต้องใช้ key)
| ข้อมูล | Endpoint | หมายเหตุ |
|---|---|---|
| ประกาศ Binance | `https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId=48&pageNo=<n>&pageSize=50` | มี 2,301 ประกาศ ย้อนถึงปี 2023; ใช้ `releaseDate` (ms UTC); ต้องกรองเฉพาะหัวข้อ "Will List" หรือ "Adds ... Spot" และตัดข่าว Launchpool, margin และ bots ออก |
| ประกาศ Upbit | `https://api-manager.upbit.com/api/v1/announcements?os=web&page=<n>&per_page=20&category=trade` | มี 823 ประกาศ ย้อนถึงปี 2021; ใช้ `first_listed_at` (เวลา +09:00); ดึงชื่อเหรียญจากวงเล็บในหัวข้อ เช่น "(NEAR, YGG)" |
| ราคา 1 นาที / 1 ชม. | `https://data-api.binance.vision/api/v3/klines?symbol=<SYM>USDT&interval=1m&startTime=<ms>` | ใช้ได้จาก Actions; ใช้กับเหรียญที่มีคู่ USDT บน Binance อยู่แล้ว (กรณี Upbit list) |
| ราคา Coinbase | `https://api.exchange.coinbase.com/products/<SYM>-USD/candles?granularity=60&start=<iso>&end=<iso>` | ใช้กับกรณีที่ Binance list เหรียญซึ่งมีบน Coinbase อยู่แล้ว |

## ด่านคัดกรอง (ย้อนหลัง 2024-01-01 ถึง 2026-10-31)
1. สร้างรายการ event (Binance ใช้ราคา Coinbase, Upbit ใช้ราคา Binance spot) ที่มีฟิลด์ `{venue, symbol, ts_announce}` โดยเก็บเฉพาะเหรียญที่มีราคาซื้อขายอยู่ที่ exchange อื่น **ก่อน** เวลาประกาศ
2. ราคาเข้า = ราคาปิดของแท่ง 1 นาทีที่ `ts_announce + 60s` บวกต้นทุน taker 0.1% และ slippage 0.2%
3. วัดผลตอบแทนที่ +15 นาที, +1 ชม., +4 ชม., +1 วัน และ +7 วัน
4. control: ผลตอบแทน BTC ในช่วงเวลาเดียวกัน (ปรับจากร่างแรกก่อนดึงข้อมูล เพราะไม่มีข้อมูล market cap ย้อนหลังฟรีสำหรับสุ่มเหรียญขนาดใกล้กัน)
5. ใช้สถิติชุดเดียวกับงานเดิม คือ `block_bootstrap_p` ใน `core/news_backtest.py` โดยใช้ cluster รายวัน
6. แบ่งข้อมูลตามเวลา: 2024 = train, 2025 = validation, 2026 = test ห้ามดู 2026 จนกว่าจะเลือก horizon จาก train และ validation แล้ว

**งานที่เกี่ยวข้องและปิดไปแล้ว:** การ rebound หลังประกาศ delisting ของ Bybit ไม่ผ่าน (`research/LESSONS.md` บรรทัด 89) และเดือนที่ดีที่สุดเกิดจาก ALPACA ไม้เดียว (บรรทัด 73) เส้นนี้ทดสอบเหตุการณ์ฝั่ง listing ซึ่งต่างจากงานเดิม แต่ต้องรายงานผลเมื่อตัดเหตุการณ์ที่ดีที่สุด 1 และ 5 ครั้งออกด้วย ถ้าผลกลายเป็น ≤ 0 ให้ถือว่าไม่ผ่าน

**ผ่าน:** horizon ที่เลือกจาก train มีผลสุทธิเฉลี่ยมากกว่า 0 และ p < 0.05 ใน validation และเครื่องหมายเดียวกันใน test
**ตัด:** ผลสุทธิของ validation ≤ 0 หรือ p > 0.2

## ถ้าผ่าน
- เขียน `protocol_L1_listings.md` และล็อกขนาดไม้ (Kelly ครึ่งหนึ่งจากผล validation, เพดาน 20% ของบัญชีต่อไม้)
- เพิ่มตัวตรวจประกาศใน `core/market_collect.py` ให้ poll ทุก 30 วินาที แล้วส่งสัญญาณเข้าบัญชีจำลองบน Kuber
- ตัดสินแบบเดินหน้าด้วย `core/sequential.py` (หน่วย = 1 วัน, `lo` = ขาดทุนสูงสุดต่อไม้ตาม stop)
