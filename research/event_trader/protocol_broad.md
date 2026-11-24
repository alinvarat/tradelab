# Broad rule trader (broad-v1), locked 2026-11-24 before any data

Owner request: a rule-based trader that can trade as widely as the DeepSeek trader, to show whether the model adds anything over a simple rule on the same opportunities. The original event trader (`protocol.md`) is unchanged and keeps its own record.

- **Universe and triggers:** the DeepSeek trader's universe (`core.universe.ALL`, 217 symbols) and per-class shock thresholds (`SHOCK_PCT`: stock 5%, ETF 3%, commodity 2%, FX 1%, crypto 5% versus the previous close), first sight per symbol per UTC day, fresh quote (< 30 min) from an open market; stocks and ETFs also need day volume >= 0.5x the 50-day average.
- **Rule (no AI):** trade with the move, up -> long, down -> short. Margin 10% of equity at 3x leverage (30% notional), stop 5% against the entry, exit after 20 hours at the first quote from an open market, at most 5 open positions, no daily halt (owner rule: no restrictions).
- **Control:** at the same moment, a random non-shock symbol of the same class from an open market, same side, size, leverage, stop and exit.
- **Scan:** every 30 s over the whole universe.
- **Known difference from DeepSeek:** no US pre-market/after-hours entries in v1 (DeepSeek has them); adding them needs a dated addendum.
- **Evaluation:** paired returns on margin (model minus control), the fixed rule of `core/event_trader.py` evaluate() and the account against the 3x goal (441 USD from 147 USD). Comparison with DeepSeek: same universe and triggers, so both accounts and their control gaps are read side by side.
