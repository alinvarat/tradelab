# แผนที่ระบบ TradeLab (อ่านแทนการไล่โค้ดใหม่)

อัปเดตไฟล์นี้ใน PR เดียวกับงานที่เพิ่ม ย้าย หรือลบส่วนใดส่วนหนึ่งของระบบ ถ้าไฟล์นี้ขัดกับโค้ด ให้ถือว่าเป็นบั๊กและแก้ให้ตรงกัน
ตรวจล่าสุด: 2026-11-24

## 1. สิ่งที่รันอยู่และที่ตั้ง
| ส่วน | โค้ด | รันที่ | รอบ | state / ผล | ตรวจด้วย |
|---|---|---|---|---|---|
| บอท DeepSeek (v4.4) | `core/llm_trader.py` | Kuber | สแกนตลอด, เรียกโมเดลเมื่อมีเหตุ | volume `/app/data/llm_trader_v4.json`, log `llm_trader_log_v4.jsonl` | `/api/llm_trader` (`protocol`, `usd_today`, `helper_models`) |
| Event trader (กติกาเดิม) | `core/event_trader.py` | Kuber | 10 วิ | `event_trader.json` | `/api/events` |
| บอทกติกาแบบกว้าง (broad-v1) | `core/event_trader_broad.py` | Kuber | 30 วิ | `event_trader_broad.json` | `/api/events_broad` |
| ตัวเก็บข้อมูลตลาด + บัญชี L1b/L1d/L1f | `core/market_collect.py` | Kuber | venues 5 วิ, ประกาศ 30 วิ, Deribit 30 นาที | `/app/data/collect/` | `/api/collect` (`listings`, `l1b`, `l1d`, `l1f`) |
| บัญชี L4f (Polymarket) | `core/market_collect.py` (`l4f_once`) + `research/studies/l4f_forward.py` | GitHub Actions job `l4f` | ทุก 30 นาที (:17, :47) | branch `data/l4f-forward` | `git show origin/data/l4f-forward:l4f_summary.json` |
| ออปชันแบบเดินหน้า | `research/studies/options_forward.py`, `core/options_forward.py` | Actions job `options` | จ.–ศ. 15:00 UTC | branch `data/options-forward` | `git show origin/data/options-forward:options_forward_summary.json` |
| ข่าวงบแบบเดินหน้า | `run.py llm_earnings_forward` | Actions job `forward` | อาทิตย์ 03:00 UTC | branch `data/llm-earnings` | ไฟล์ใน branch นั้น |
| ด่านคัดกรองย้อนหลัง | `research/studies/run.py` (`STUDIES`), `core/screens.py` | Actions job `study` | สั่งรันเองเท่านั้น | artifact `study-<name>` | `gh run download <id> -n study-<name>` |
| อื่นๆ บน Kuber | autotrader, hunter, buzz, news archive, DVOL, steward | Kuber | ตามโค้ด | volume | `/healthz` |

- **Deploy:** push เข้า `main` จะรัน `.github/workflows/kuber.yml` (Test แล้ว Deploy) ถ้าล้มที่ฝั่ง Kuber ให้ทำตาม RUNBOOK ข้อ 6.1
- **หน้าเว็บ:** `https://tradelab.dgnr.us` ต้องล็อกอิน จึงต้องเปิดผ่าน Chrome (curl ได้แค่ 302)

## 2. ข้อจำกัดเครือข่าย (ตรวจจริงแล้ว)
| ปลายทาง | Actions (สหรัฐ) | Kuber |
|---|---|---|
| `api.binance.com`, `fapi.binance.com` | ถูกบล็อก (ใช้ `data-api.binance.vision`) | ใช้ได้ |
| ประกาศ Binance (`www.binance.com/bapi`) | ใช้ได้ | ใช้ได้ |
| Upbit (`api-manager.upbit.com`) | ล้ม | 403 (แม้ใช้ UA แบบเบราว์เซอร์) |
| KuCoin, Coinbase | ใช้ได้ | ใช้ได้ |
| Polymarket gamma/clob | ใช้ได้ | connection reset |
| SEC EDGAR | ใช้ได้ (ต้องมี `TRADELAB_SEC_UA`) | — |

## 3. AI และค่าใช้จ่าย
| ผู้เรียก | โมเดล | หมายเหตุ |
|---|---|---|
| บอท: การตัดสินใจสุดท้าย | DeepSeek v4.1 flash 1017 | ราว 0.0026 USD ต่อรอบ (v4.3 ขึ้นไป) |
| บอท: นักวิเคราะห์, bull/bear, risk, pre-open; steward | โมเดลฟรี (`ai_news.HELPER_MODELS`) แล้วจึง DeepSeek ถ้าฟรีล้ม | จำนวนครั้งดูที่ `helper_models` |
| ให้คะแนนพาดหัวข่าว | DeepSeek | เพดาน 600 ข่าวต่อวัน (`core/news_archive.py`) |
| ออปชันและข่าวงบแบบเดินหน้า | DeepSeek | บันทึกค่าใช้จ่ายใน summary ของ data branch |
| study ที่ชื่อขึ้นต้น `llm_`, `news_v2`, `polymarket_llm` | DeepSeek | เสียเงินทุกครั้งที่รัน: สั่งรันเฉพาะเมื่อตั้งใจ |
| OpenCode ในเครื่องเจ้าของ | DeepSeek | ใช้ key เดียวกัน; คำขอจากระบบเราขึ้นชื่อ "TradeLab" ใน OpenRouter |
| ผู้ให้บริการทางเลือก (ai.thirx.com) | ตามตัวแปร `THIRX_MODEL` | ใช้กับทุกคำขอที่เสียเงินเมื่อมี secret `THIRX_API_KEY` และ variable `THIRX_MODEL` ใน repo; ถ้าล้มจะกลับไปใช้ OpenRouter; โมเดลฟรีของผู้ช่วยยังอยู่บน OpenRouter |

## 4. เอกสารหลัก (แต่ละเรื่องมีที่เดียว)
| เรื่อง | ไฟล์ |
|---|---|
| เป้าและแผน | `ROADMAP.md` |
| ขั้นตอนทำงาน | `ops/RUNBOOK.md` |
| แผนที่ระบบ | `ops/SYSTEM_MAP.md` (ไฟล์นี้) |
| สถานะและคิวงาน | `reports/STATUS.md` |
| ผลทดสอบทุกตัว (รวมที่ถอนผล) | `research/studies/RESULTS.md` |
| บทเรียน | `research/LESSONS.md` |
| กติกาที่ล็อกของแต่ละการทดสอบ | `research/studies/protocol_*.md`, `research/llm_trader/protocol.md`, `research/event_trader/protocol_broad.md` |
| สเปกแต่ละเส้น | `ops/lines/` |
