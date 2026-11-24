# L5 ออปชันจากข่าวทุกประเภท (ทดสอบแบบเดินหน้า)

**สถานะ:** โค้ดเดิมอ่านเฉพาะข่าวงบ ส่วน PR #79 (draft จาก Codex) ขยายให้อ่าน 8-K ทุกประเภท และ PR #77 เพิ่มรายงาน e-process
**รันที่ไหน:** Actions จ.–ศ. 15:00 UTC โดย state อยู่ใน branch `data/options-forward`

## งานที่ต้องทำ (ตามลำดับ)
1. ตรวจผลรอบเปิดตลาดรอบแรก
   ```bash
   gh run list -w "Research studies" -L 5
   git fetch origin data/options-forward
   git show origin/data/options-forward:options_forward_summary.json
   ```
   ค่า `gaps` ต้องว่าง หรือมีเฉพาะสาเหตุที่อธิบายได้ (เช่นไม่มี chain)
2. รีวิว PR #77 และ #79 โดยอ่าน diff ทั้งหมดและตรวจว่า:
   - ไม่เปลี่ยนกติกาที่ล็อกไว้ใน `protocol_llm_options_forward.md` โดยไม่มี addendum ลงวันที่
   - มีเทสต์ใหม่ และ CI ผ่าน
3. merge แล้วตรวจรอบ 15:00 UTC ถัดไปว่ามีเทรดจากข่าวประเภทใหม่เข้ามาจริง
4. ทุกวันหลัง 15:30 UTC: บันทึกจำนวนเทรดที่ปิดแล้ว (เป้าคือ 150) และค่า e-process ลง `reports/STATUS.md`

- **ตัด:** e-process ตัดสินว่า "no edge (negative)" หรือครบ 150 เทรดแล้วไม่ผ่านเกณฑ์ที่ล็อกไว้
