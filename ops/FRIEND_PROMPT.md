# Prompt สำหรับ AI ของเพื่อน (dmgnr)

ช่วยทำงานต่อใน repo alinvarat/tradelab
เป้าหมายเดียวของโปรเจกต์: บัญชีจำลอง 147 USD โต 3 เท่าต่อเดือนขึ้นไป ให้เร็วที่สุด งานที่ไม่ช่วยเป้านี้ไม่ต้องทำ

## อ่านก่อนเริ่ม (ตามลำดับ)
1. `AGENTS.md`: กฎหลัก เช่นห้ามรันโปรเจกต์บนเครื่องตัวเอง ห้ามใส่ key หรืออีเมลในโค้ด และล็อกกติกาก่อนดูข้อมูล
2. `ops/RUNBOOK.md`: ขั้นตอนทำงาน นิยามคำว่า "เสร็จ" และวิธีแก้เมื่อมีปัญหา
3. `reports/STATUS.md`: สถานะและคิวงาน แถวที่คอลัมน์ผู้ทำเป็น "เพื่อน (dmgnr)" คืองานของคุณ
4. `ROADMAP.md` ข้อ 1.5: แผน sprint แบบเร็ว

## งานของคุณ
| issue | งาน | สเปก |
|---|---|---|
| #89 (ด่วนที่สุด) | ทำให้ deploy บน Kuber เสถียร: ตรวจ DNS ของ registry, ใส่ paths-ignore สำหรับไฟล์เอกสาร, retry อัตโนมัติ, แจ้งเตือนเมื่อ deploy ล้ม | ข้อความใน issue (error ที่เจอ: `Unable to resolve pushed image digest: getaddrinfo ETIMEOUT cncf-distribution-svc.registry.svc.cluster.local` และ `KuberApiError: Service Unavailable`) |
| #85 | ด่านคัดกรอง L3: หุ้นเล็กที่มีข่าวนอกเวลาตลาด | `ops/lines/L3_smallcap_news.md` |
| #86 | ด่านคัดกรอง L4: Polymarket ขายฝั่ง longshot แบบ maker | `ops/lines/L4_polymarket_maker.md` |
| #87 | ด่านคัดกรอง L6: insider ซื้อในหุ้นเล็ก | `ops/lines/L6_smallcap_insider.md` |
| #88 | หาแหล่งข้อมูล token unlock ย้อนหลังแบบฟรี (จำกัดเวลา 2 ชม.) | `ops/lines/L2_unlocks.md` |

## วิธีทำด่านคัดกรอง (ตาม `ops/RUNBOOK.md` ข้อ 4)
1. เขียนเกณฑ์ผ่านและเกณฑ์ตัดลง `research/studies/RESULTS.md` **ก่อน** ดึงข้อมูล
2. เขียนฟังก์ชันคำนวณใน `core/screens.py` พร้อมเทสต์ใน `tests/test_screens.py` ใช้ L1 ที่ทำเสร็จแล้วเป็นตัวอย่าง
3. เพิ่ม `study_<ชื่อ>` ใน `research/studies/run.py` แล้วใส่ชื่อ study ลงใน matrix ของ `.github/workflows/research.yml`
4. สั่งรันเฉพาะ study นั้น:
   ```bash
   gh workflow run "Research studies" -f study=<ชื่อ> --ref <branch>
   ```
   **ห้าม push ไปที่ branch `research-run/**`** เพราะจะรันทุก study รวมถึงตัวที่เรียก LLM ซึ่งเสียเงิน
5. อ่านตัวเลขจริงจาก artifact แล้วตัดสินตามเกณฑ์ที่ล็อกไว้ ห้ามปรับเกณฑ์หลังเห็นผล
6. บันทึกผลลง `RESULTS.md` อัปเดตแถวของงานใน `reports/STATUS.md` แล้วเปิด PR

## ข้อควรรู้
- Actions รันบนเครื่องในสหรัฐ ซึ่ง `api.binance.com` และ Upbit บล็อกไว้ ให้ใช้ `data-api.binance.vision` สำหรับราคา Binance หรือใช้ KuCoin แทน
- ผล L1: ไม่ผ่านตามกฎที่ล็อกไว้ แต่การถือ 4 ชม. หลังประกาศ listing ได้ผลบวกทุกช่วง ตอนนี้กำลังทดสอบแบบเดินหน้าเป็น L1b บน Kuber (ต้องรอ deploy ผ่านก่อน)
- ทำงานผ่าน branch และ PR เสมอ และให้ CI ผ่านก่อน merge
- งานที่แตะแอปต้องเปิด https://tradelab.dgnr.us ตรวจหลัง deploy ว่าค่าที่เปลี่ยนขึ้นจริง ถ้ายังไม่ขึ้นให้รายงานว่า "ยังไม่ขึ้นระบบ" ไม่ใช่ "เสร็จ"
- ถ้าต้องเรียก LLM ให้ใช้ `deepseek/deepseek-v4.1-flash-1017` เท่านั้น
- จบงานแต่ละชิ้น: อัปเดต `reports/STATUS.md` (สถานะและขั้นต่อไป) และคอมเมนต์ผลเป็นตัวเลขจริงใน issue นั้น
