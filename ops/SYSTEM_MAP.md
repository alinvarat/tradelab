# แผนที่ระบบ TradeLab (อ่านแทนการไล่โค้ดใหม่)

อัปเดตไฟล์นี้ใน PR เดียวกับงานที่เพิ่ม ย้าย หรือลบส่วนใดส่วนหนึ่งของระบบ ถ้าไฟล์นี้ขัดกับโค้ด ให้ถือว่าเป็นบั๊กและแก้ให้ตรงกัน
ตรวจล่าสุด: 2026-11-24

## 1. สิ่งที่รันอยู่และที่ตั้ง
| ส่วน | โค้ด | รันที่ | รอบ | state / ผล | ตรวจด้วย |
|---|---|---|---|---|---|
| บอท DeepSeek (v4.4) | `core/llm_trader.py` | Kuber | สแกนตลอด, เรียกโมเดลเมื่อมีเหตุ | volume `/app/data/llm_trader_v4.json`, log `llm_trader_log_v4.jsonl` | `/api/llm_trader` (`protocol`, `usd_today`, `helper_models`) |
| กติกาและอินพุตของบอท v4.19 (2026-11-27) | `core/desk_rules.py` (กติกาที่ล็อกต่อแท็ก, เบรกความเสี่ยง), `core/desk_feeds.py` (ข่าวเร็ว, summary ของ ledger จาก data branch, funding OKX) | Kuber | ทุกรอบสแกน; thread พื้นหลังรีเฟรช ledger ทุก 10 นาที, funding ทุก 5 นาที | `desk_outcomes/<วัน UTC>.jsonl` บน volume (หนึ่งแถวต่อ candidate ต่อ horizon) | `/api/llm_trader` คีย์ `v4_19` (`risk`, `stale_feeds`, `entries_today`), `evaluation.claude_v4_19`; `/api/llm_log` (`rule_veto`, `rule_reduce`) |
| ห่วงโซ่ปรับปรุงบอทรายสัปดาห์ (2026-11-27) | `core/desk_publish.py` (pod ส่ง outcome ขึ้น `data/bot-desk` ทุก 30 นาที ต้องมี `TRADELAB_DATA_PUSH_TOKEN`), `.github/workflows/bot_weekly.yml` + `research/llm_trader/weekly.py` | Pod + Actions | keeper dispatch วันอาทิตย์ 04:00 UTC | branch `data/bot-desk`; รายงานและข้อเสนอที่ `research/llm_trader/weekly/` ใน branch `bot/weekly-<วัน>` | PR หรือ issue ชื่อ "Bot weekly review"; `/api/llm_trader` `v4_19.outcome_publish` |
| Event trader (กติกาเดิม) | `core/event_trader.py` | Kuber | 10 วิ | `event_trader.json` | `/api/events` |
| บอทกติกาแบบกว้าง (broad-v1) | `core/event_trader_broad.py` | Kuber | 30 วิ | `event_trader_broad.json` | `/api/events_broad` |
| ตัวเก็บข้อมูลตลาด + บัญชี L1b/L1d/L1f | `core/market_collect.py` | Kuber | venues 5 วิ, ประกาศ 30 วิ, Deribit 30 นาที | `/app/data/collect/` | `/api/collect` (`listings`, `l1b`, `l1d`, `l1f`) |
| ขาชอร์ตผ่านมาร์จิ้น L1f (l1fm, ใหม่ 2026-11-27, ทดสอบเดินหน้าแบบกระดาษ) | `core/margin_arm.py`, `margin_step` ใน `core/market_collect.py`, `core/margin_publish.py` | Kuber (ตัวเก็บข้อมูลตลาด รอบประกาศ 30 วิ; ปิดได้ด้วย `TRADELAB_MARGIN_ARM=0`) | เห็นประกาศ Binance delist ครั้งแรก: บันทึก snapshot ของ bapi `vip/spec/list-all` (กู้ได้ไหม, ดอกเบี้ยรายวัน, วงเงิน) แล้วชอร์ตที่ bid ของ Binance spot หลัง 60 วิ ปิดที่ ask หลัง 4 ชม. (หรือ stop 25%) หักดอกเบี้ยกู้ที่วัดจริง; heartbeat ทุก 30 นาที | volume `/app/data/collect/margin_arm/<วัน>.jsonl`, state `delist_margin_state.json`; branch `data/l1f-margin` (`margin_arm/<วัน>/<start>-<end>.jsonl`, ต้องมี `TRADELAB_DATA_PUSH_TOKEN`) | `/api/collect` คีย์ `l1fm`, `l1fm_publish`; `git ls-tree -r origin/data/l1f-margin`; protocol `research/studies/protocol_l1f_margin_arm_20261127.md` (ล็อกด้วย sha256) |
| บัญชี L4f (Polymarket) | `core/market_collect.py` (`l4f_once`) + `research/studies/l4f_forward.py` | GitHub Actions job `l4f` | ทุก 30 นาที (:17, :47) | branch `data/l4f-forward` | `git show origin/data/l4f-forward:l4f_summary.json` |
| บัญชี forward L12B_F / L8B_F (spike ชอร์ตคริปโต) | `core/fwd_crypto.py` + `research/studies/fwd_crypto_spikes.py` | GitHub Actions job `fwd_crypto` (`study=fwd_crypto_spikes`) | ทุกชั่วโมงนาทีที่ 5 (systemd timer บนเครื่องเจ้าของ) | branch `data/fwd-crypto-spikes` | `git show origin/data/fwd-crypto-spikes:fwd_crypto_summary.json` |
| ออปชันแบบเดินหน้า | `research/studies/options_forward.py`, `core/options_forward.py` | Actions job `options` | จ.–ศ. 15:00 UTC | branch `data/options-forward` | `git show origin/data/options-forward:options_forward_summary.json` |
| ข่าวงบแบบเดินหน้า | `run.py llm_earnings_forward` | Actions job `forward` | อาทิตย์ 03:00 UTC | branch `data/llm-earnings` | ไฟล์ใน branch นั้น |
| ความหน่วงข่าว (forward) | `research/studies/news_latency_fwd.py`, `core/news_latency_fwd.py` | Actions workflow `news_latency_fwd.yml` (โหมด probe / run / summary; run วนโพลประมาณ 5 ชม. 45 นาที ต่อตัวเอง และ keeper เช็กทุกชั่วโมง) | ต่อเนื่อง หลัง protocol ล็อกและ merge | branch `data/news-latency-fwd` | `git show origin/data/news-latency-fwd:summary.json` |
| ด่านคัดกรองย้อนหลัง | `research/studies/run.py` (`STUDIES`), `core/screens.py` | Actions job `study` | สั่งรันเองเท่านั้น | artifact `study-<name>` | `gh run download <id> -n study-<name>` |
| ด่านคัดกรองแบบแบ่ง shard | `run.py` (`rows_<study>`, `summarize_<study>`), `research/studies/sharding.py`, `binance_vision.py` | `.github/workflows/research_sharded.yml` (plan → shard ×N → merge) | สั่งรันเองเท่านั้น (`gh workflow run research_sharded.yml -f study=<name> -f shards=20`) | artifact `part-<study>-<i>`, `study-<study>` | `gh run download <id> -n study-<study>` |
| ตัวรับข่าวเร็ว (วัดอย่างเดียว; ตั้งแต่ v4.19 บอทอ่านไฟล์ล็อกแบบอ่านอย่างเดียวผ่าน `core/desk_feeds.py`) | `core/news_ingest.py` | Kuber | poll 2-10 วิ + websocket EquationNews + แหล่งทดลองที่แข่งกับตัวควบคุม (2026-11-27): `binance_{listings,news,delist}_fast` (หมุนคีย์แคช CloudFront ตาม Age ~120 วิ), `binance_{listings,news,delist}_apex`, `binance_news_cat` (เส้นทางอื่นของ Binance), แถว `event:"health"` ทุก 10 นาที, `okx_ann_my`, `okx_ann_listings`, `okx_help_latest`, `okx_help_listings` (แถว `via`/`publish_time` ในล็อก; ไม่เรียก LLM)| volume `/app/data/collect/news_ingest/*.jsonl` (t_pub, t_seen, t_llm) | `/api/news_latency` คีย์ `ingest` (median/p90 ต่อแหล่ง) |
| ตัวส่งล็อกข่าวเร็วขึ้น git (ใหม่ 2026-11-26) | `core/news_publish.py` (thread ของตัวเอง ใน `news_ingest.loop`) | Kuber | ทุก 10 นาที (`TRADELAB_NEWS_PUSH_MINUTES`); ไม่ทำอะไรจนกว่าจะมี secret `TRADELAB_DATA_PUSH_TOKEN` | branch `data/news-ingest` ไฟล์สร้างครั้งเดียวไม่แก้ `news_ingest/<YYYYMMDD>/<start>-<end>.jsonl` (cursor อยู่ที่ `.publish_cursor.json` บน volume) | `/api/news_latency` คีย์ `ingest.publish` (`enabled`, `last_ok_utc`, `last_error`); `git ls-tree -r origin/data/news-ingest`; ผู้อ่านคือ `research/news_train/run_ingest_fwd.py` (R2 `fwd` เขียน `fwd/ingest_timing.json`, R3 `fwd_ingest` นับอย่างเดียว) ตาม `protocol_ingest_addendum_20261126.md` |
| บัญชีทดสอบประกาศเอ็กซ์เชนจ์ notice_fwd (Q2, ใหม่ 2026-11-26) | `core/notice_fwd.py`, `research/studies/notice_fwd.py`, `.github/workflows/notice_fwd.yml` | Actions (keeper dispatch ทุก 30 นาที ที่นาที 11 และ 41) | branch `data/notice-fwd` (`state.json`, `notices.jsonl`, `trades.jsonl`, `summary.json`, `counts.json`) | อ่านส่วนที่ `data/news-ingest`; เข้า 5 วินาทีหลัง pod เห็น (ราคาจาก tape ของ OKX); โหมด `counts` ไม่อ่านราคา; ตัดสินตาม `research/studies/protocol_notice_fwd_20261126.md` (n ขั้นต่ำ 30, deadline 2027-02-06) |
| อื่นๆ บน Kuber | autotrader, hunter, buzz, news archive, DVOL, steward | Kuber | ตามโค้ด | volume | `/healthz` |

- **Deploy:** push เข้า `main` จะรัน `.github/workflows/kuber.yml` (Test แล้ว Deploy) ถ้าล้มที่ฝั่ง Kuber ให้ทำตาม RUNBOOK ข้อ 6.1
- **หน้าเว็บ:** `https://tradelab.dgnr.us` ต้องล็อกอิน จึงต้องเปิดผ่าน Chrome (curl ได้แค่ 302)
- **โครงหน้าเว็บ (`ui/`):** แท็บหลัก = ภาพรวม, บอท AI, Event trader, บอทหลัก, บันทึกการตัดสินใจ, พอร์ต; แท็บอื่นอยู่ในเมนู "เพิ่มเติม" หน้าภาพรวม/บอท AI/Event trader แสดงข้อสรุปหนึ่งบรรทัด แถบความคืบหน้าสู่เป้า 3 เท่า สถานะที่ถืออยู่ และการตัดสินใจล่าสุด ส่วนรายละเอียดกางดูได้ ข้อความใหม่ในสามหน้านี้เขียนสองภาษาด้วย `L(en, th)` ใน `ui/app.js` และวาดซ้ำเมื่อสลับภาษา; ข้อมูลสุขภาพระบบมาจาก `/healthz` (ตอบ 503 พร้อม JSON เมื่อมีงานช้า)

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
| บอท: การตัดสินใจสุดท้าย | DeepSeek v4.1 flash 1017 ผ่าน ai.thirx.com (ตั้งแต่ 24 พ.ย. 17:04 UTC; เครดิต OpenRouter หมด) | ตรวจแล้ว: model `custom/deepseek-v4.1-flash-1017` ใน `/api/llm_log` |
| บอท: นักวิเคราะห์, bull/bear, risk, pre-open; steward | DeepSeek ผ่าน thirx (v4.16); โมเดลฟรีของ OpenRouter ใช้เฉพาะเมื่อไม่ได้ตั้ง thirx | จำนวนครั้งดูที่ `helper_models` |
| ให้คะแนนพาดหัวข่าว | DeepSeek (thirx ก่อน, OpenRouter สำรอง) | เพดาน 600 ข่าวต่อวัน (`core/news_archive.py`) |
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

## 5. เจ้าของต้องทำ: เปิดการส่งล็อกข่าวจาก pod ขึ้น `data/news-ingest`
Pod ไม่มี GitHub token (env มีแค่ `CLAUDE_CODE_OAUTH_TOKEN` และ `TRADELAB_SEC_UA`) จึงยังไม่ส่งอะไรจนกว่าจะทำ 3 ข้อนี้ ห้ามส่ง token ในแชต:
1. สร้าง fine-grained personal access token ที่ GitHub: Settings > Developer settings > Fine-grained tokens; Repository access = Only select repositories > `alinvarat/tradelab` เท่านั้น; Permissions: Contents = Read and write (ไม่ต้องมีอย่างอื่น); ตั้งวันหมดอายุ 90 วัน
2. เก็บเป็น secret ของ repo: `gh secret set TRADELAB_DATA_PUSH_TOKEN -R alinvarat/tradelab` แล้ววาง token ตอนที่ถาม
3. deploy ใหม่เพื่อให้ pod ได้ secret: `gh workflow run "Test and deploy" -R alinvarat/tradelab --ref main` (หรือ re-run deploy ล่าสุดบน main) แล้วเปิด `https://tradelab.dgnr.us/api/news_latency` ดู `ingest.publish.enabled = true` และภายใน 10-20 นาทีมี `last_ok_utc` กับ branch `data/news-ingest` ขึ้นมา
token หมดอายุหรือถูกเพิกถอน: `ingest.publish.last_error` จะขึ้น ล็อกยังอยู่บน volume (เก็บ 14 วัน) และส่งต่อจาก cursor เมื่อเปลี่ยน token แล้ว deploy ใหม่
