# Broker costs for TradeLab simulations (Webull US options, XM MT5 CFDs)

Read 2026-11-25. Simulated money only; nothing here opens an account or places an order. Code: `core/broker_costs.py` (tests `tests/test_broker_costs.py`). **EST** = estimated or only found on a third-party page, not confirmed from the broker's own page. Re-check before relying on a number; change code and this file together.

Access note: `xm.com` returned HTTP 403 / decompression errors to every automated request (pages and PDFs), so **no XM figure below comes from an XM page read in this session**. XM rows cite third-party review pages that quote XM's published numbers, and are marked as such.

## 1. Webull, US stock/ETF options (account: self-directed individual, cash or margin)

| Item | Value | Source | Read |
|---|---|---|---|
| Commission, US-listed options | 0 USD | https://www.webull.com/pricing ("does not charge commissions for stocks, ETFs and options listed on U.S. exchanges") | 2026-11-25 |
| Per-contract fee, single-stock options | 0 USD | https://webull.com/options | 2026-11-25 |
| Per-contract fee, certain index options | 0.50 USD | https://www.webull.com/pricing | 2026-11-25 |
| Oversized orders (more than 500 contracts, not index) | +0.10 USD per contract | https://webull.com/options | 2026-11-25 |
| SEC fee | 0.0000206 x sale proceeds, sells only | https://www.webull.com/pricing (regulatory table) | 2026-11-25 |
| CAT fee | 0.000003 per unit of volume, buys and sells | https://www.webull.com/pricing | 2026-11-25 |
| FINRA regulatory fee (equity table) | 0 | https://www.webull.com/pricing | 2026-11-25 |
| Options regulatory fee (ORF) | 0.02685 USD per contract, buys and sells (**EST**: Webull FAQ snippet; other copies 0.02675 to 0.02695) | https://www.webull.com/help/faq/10793-[Webull-Omnibus-What-are-the-trading-fees-on-Webull-Are-you-commission-free | 2026-11-25 |
| OCC clearing fee | 0.025 USD per contract, buys and sells (**EST**, third-party copies of the schedule; one page says 0.055; OCC temporarily waived its own fee in Dec 2025) | https://www.wallstreetsurvivor.com/webull-fees/ , https://prd-web-deploy.theocc.com/Company-Information/Schedule-of-Fees | 2026-11-25 |
| FINRA TAF on options sells | 0.00279 USD per contract, capped 8.38 USD per trade (**EST**, regulator rate, not itemised on the Webull page) | not confirmed | 2026-11-25 |
| Minimum | none stated for options; options need an approved options application | https://www.webull.com/pricing | 2026-11-25 |
| Effective date of the schedule | not stated on the pages (only "(c) 2026 Webull Financial LLC") | | 2026-11-25 |

Net result for one contract: about 0.052 USD per side (ORF + OCC + CAT) plus about 0.003 USD on a sell plus 0.0000206 x proceeds. The forward-test model used a flat 0.65 USD per contract per side, so it overstates Webull cost by roughly 12 times on a one-contract order. The bid/ask spread is not a fee and is already in the model (entry at ask, exit at bid, plus the 10% exit-bid stress).

**Webull OpenAPI and options.** Webull's developer docs list the US region as supporting equities and single-stock options (index options excluded), including single-leg and multi-leg orders; the Thailand-region page says single-leg only; a third-party skills table (not Webull) shows options only in the US region, not HK or JP. US production base URL `https://api.webull.com/`. Sources: https://developer.webull.com/apis/docs/about-open-api , https://developer.webull.com/apis/docs/trade-api/overview , https://developer.webull.hk/apis/docs/trade-api/overview (read 2026-11-25). **Not found:** US API access requirements and account eligibility. TradeLab does not use the API (simulated money, no orders); this is only a mapping note.

## 2. XM Global on MT5, CFDs (FX, gold, commodities)

| Item | Value | Account | Source | Read |
|---|---|---|---|---|
| EURUSD spread | average 2.0 pips, as low as 1.6 | Standard | https://fxrecap.com/top-broker/xm-review/xm-spreads (quotes XM's published figures, checked 2026-09-30) | 2026-11-25 |
| EURUSD spread | from 0.8 pips, no commission | Ultra Low | same page | 2026-11-25 |
| EURUSD spread | from 0.0 pips, about 0.1 average in peak hours | Zero | https://tradelytic.com/brokers/reviews/xm/ (page dated 2026-09-07) | 2026-11-25 |
| Zero commission | 3.50 USD per lot per side (7 USD round turn) | Zero | https://tradelytic.com/brokers/reviews/xm/ ; conflicting: fxrecap says XM has **no Zero account** (only Shares charges commission) and another source says Zero is CySEC-only. **Availability unverified.** | 2026-11-25 |
| USDJPY | from 2 pips | Standard | https://tradergulf.com/guides/xm-fees-complete-guide-2026 (updated 2026-11-19) | 2026-11-25 |
| XAUUSD (gold) | average 5.5 "pips", as low as 4.0 | Standard | fxrecap spreads page; pip size for gold not stated, 0.10 USD assumed (**EST**: about 0.55 USD) | 2026-11-25 |
| XAUUSD (gold) | average 3.0 "pips", as low as 2.4 | Ultra Low | same (about 0.30 USD, **EST**) | 2026-11-25 |
| XAGUSD (silver) | 0.025 | account not stated | https://brokerchooser.com/sv/cfd/trading/trading-tips-strategies/xm-commodity-cfds (updated 2026-05-06) | 2026-11-25 |
| GBPUSD, AUDUSD | not found; Standard 2.5 / Ultra Low 1.3 / Zero 0.3 pips | all | **EST** | |
| WTI, Brent, natural gas, copper | not found; EST Standard/Ultra Low/Zero: WTI and Brent 0.05/0.04/0.02 USD; natgas 0.008/0.006/0.003; copper 0.004/0.003/0.0015 | all | **EST** (instruments exist on XM per https://commodity.com/brokers/XM-review/) | |
| Commission, Standard and Ultra Low | 0 | Standard, Ultra Low | fxrecap, tradelytic | 2026-11-25 |
| Swap / overnight financing | no rates published on any page read. Accrues past 22:00 GMT rollover as interbank rate plus a broker markup; Ultra Low swaps are lower than Standard; triple-swap day and exact values are in the MT5 symbol specification (Market Watch, right-click symbol, Specification: swap long / swap short). Islamic accounts have no swap but a fair-value adjustment on overnight gold and platinum. Model uses a flat 3% a year of notional as cost only (**EST**) | all | https://tradergulf.com/guides/xm-fees-complete-guide-2026 | 2026-11-25 |
| Max leverage | 1:1000 on most accounts; CySEC (EU) entity 1:30 on major FX; older XM disclosures put gold at 1:20 (**check per instrument**) | all | https://fxrecap.com/learn-forex/brokers/xm-account-types ; https://tradelytic.com/brokers/reviews/xm/ ; https://www.xm.com/assets/pdf/new/docs/XMAU-Product-Disclosure-Statement.pdf (via search snippet) | 2026-11-25 |
| Minimum lot | 0.01 lot (**EST**); Micro and Ultra Low Micro accounts use 1,000-unit lots; Standard lot = 100,000 units | all | fxrecap account types (micro 1,000 units) | 2026-11-25 |
| Stop-out level | **not found** in any source read. Do not assume; read it in the account's MT5 terminal or XM's Client Agreement | all | | |
| Minimum deposit | about 5 USD (varies by entity and payment method); sources conflict (5, 50, 100) | Standard, Ultra Low | fxrecap | 2026-11-25 |

Contract sizes in code (**EST**): FX 100,000 units, gold 100 oz, silver 5,000 oz, oil 1,000 bbl, natural gas 10,000 MMBtu, copper 25,000 lb. They only matter for the commission on a Zero account and the USD size of a lot; the fractional costs do not use them.

## 3. How the models use these numbers

- `webull_option_cost(contracts, side, premium=None)`: USD fees for one order; the SEC part needs the option price on a sell.
- `xm_cfd_cost(symbol, lots_or_notional, account, nights, *, unit, price)`: round-trip USD breakdown; `xm_cfd_cost_fraction(symbol, account, price, nights, mult)` gives the fraction of notional (spread, commission, financing, `trade_per_side`) that a backtest such as `core/fxcom.py` charges. `mult=2.0` is the 2x stress. A re-run of the FX batch with XM costs must be pre-registered as its own variant before it is run; `core/fxcom.py` is not edited here.
- Spreads are typical averages, not what a signal sees at a news spike or the rollover hour; use the 2x stress.

## 4. Options forward test (decision 2026-11-25)

`data/options-forward` already held 6 open trades (27 calls, 0 closed) in the summary of 2026-11-24T23:48Z, so the protocols `protocol_llm_options_forward.md` and `protocol_llm_options_forward_v2_sec_20261124.md` are **not changed**. The Webull schedule is reported as a separate variant, `webull_cost_variant` inside each protocol's summary (`research/studies/options_forward.py`): same closed trades, flat 0.65 USD per side replaced by the fees above, own account replay (whole and fractional contracts), own verdict. It never feeds the locked verdict, which keeps the 0.65 USD fee and the 10% exit-bid stress.
