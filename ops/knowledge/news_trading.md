# ความรู้การเทรดตามข่าว (สรุปจากงานวิจัย หนังสือ และนักเทรด) — 2026-11-24

ใช้เป็นจุดตั้งต้น (prior) ของบอทเท่านั้น ข้อมูลผลจริงของ desk (`desk_stats`, `similar_past`) มีน้ำหนักกว่าเสมอ ทุกข้อด้านล่างระบุระดับหลักฐานไว้ด้วย

## หลักทั่วไป
| หลัก | ระดับหลักฐาน | ที่มา |
|---|---|---|
| ราคาที่ขยับแรง **มีข่าวรองรับ** มักไปต่อ (โดยเฉพาะข่าวร้าย) ส่วนที่ขยับแรง **ไม่มีข่าว** มักกลับตัว | งานวิจัยตีพิมพ์ | Chan (2003), "Stock price reaction to news and no-news", J. Financial Economics |
| ข่าวซ้ำหรือข่าวเก่า (stale news) ทำให้ตลาดตอบสนองเกินแล้วกลับตัว | งานวิจัยตีพิมพ์ | Tetlock (2011), "All the news that's fit to reprint", Review of Financial Studies |
| หุ้นเล็กที่เปิด gap แรงตอนเช้ามักคืนกำไรบางส่วนระหว่างวัน โดยเฉพาะ 2 ชม. แรก และตอนตลาดผันผวน | วิทยานิพนธ์และบทความ practitioner | [utupub thesis](https://www.utupub.fi/bitstreams/88057d2a-1ee8-4c05-9592-c535a21b502c/download), [Concretum](https://concretumgroup.substack.com/p/identifying-stocks-to-fade) |
| ในหุ้นใหญ่และ ETF ทั้ง fade gap และตาม gap ไม่มี edge ชัด | บทความวิจัยอิสระ (12,306 เหตุการณ์) | [Tradescope](https://tradescope-six.vercel.app/research/gap-fill-rate) |

## ตามประเภทข่าว
| ประเภท | สิ่งที่รู้ | ระดับหลักฐาน | ที่มา |
|---|---|---|---|
| งบ | drift หลังงบในหุ้นใหญ่แทบหายไปตั้งแต่ราว 2006; การปรับประมาณการของนักวิเคราะห์หลังงบอธิบาย drift ได้ดีกว่าตัวเลข surprise | งานวิจัย | [Columbia (Zhang)](https://business.columbia.edu/sites/default/files-efs/pubfiles/3737/zhang.pdf), [NYU](https://www.stern.nyu.edu/sites/default/files/assets/documents/con_034482.pdf) |
| งบ (practitioner) | "Episodic pivot": gap ขึ้น ≥ 10% ด้วยปริมาณ ≥ 2–3 เท่าของปกติ จากงบหรือ guidance ที่ดีกว่าคาดมาก ซื้อเมื่อทะลุกรอบช่วงเปิดตลาด | คำบอกเล่าของนักเทรด ไม่มีการทดสอบอิสระ (ถือเป็นสมมติฐาน) | [Chartmill](https://www.chartmill.com/trading-ideas/737-The-Qullamaggie-Episodic-Pivot-Setup), [Tradingsim](https://tradingsim.com/blog/episodic-pivot-power-earnings-gap-buyable-gap-up-explained/) |
| ควบรวม | ผู้ซื้อโดยเฉลี่ยได้ผลราว 0 ตอนประกาศ แต่ดีลที่จ่ายเป็นหุ้นมักลบ (ส่อว่าหุ้นผู้ซื้อแพง); ถ้าดีลล้ม ผู้ซื้อแบบหุ้นลงราว −17% | งานวิจัย | [NBER w18211](https://www.nber.org/papers/w18211.pdf), [UGA](https://www.terry.uga.edu/sites/default/files/inline-files/bidder1_1.pdf), [Cambridge](https://www.jbs.cam.ac.uk/wp-content/uploads/2020/08/wp0106-1.pdf) |
| นักวิเคราะห์ | upgrade ได้ราว +3% วันแรก ส่วน downgrade ราว −4% และ drift ต่ออีกหลายเดือน (downgrade มีข้อมูลมากกว่า) | งานวิจัยตีพิมพ์ | Womack (1996), "Do brokerage analysts' recommendations have investment value?", J. Finance |

## ข้อควรระวัง
- นักเทรดชื่อดังหลายรายไม่มีบัญชีตรวจสอบได้ครบ และ FTC พบว่าลูกค้าคอร์สเทรดหุ้นเล็กส่วนใหญ่ขาดทุน (ดู `research_notes/` market_wizards.md ในเครื่องเจ้าของ) ให้ใช้กฎของนักเทรดเป็นสมมติฐานเพื่อทดสอบเท่านั้น
- ตัวเลขในงานวิจัยมักเป็นข้อมูลก่อนปี 2015 และยังไม่หักต้นทุน
