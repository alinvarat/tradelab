"""Run the LLM trader as its own process (systemd user service on a machine with the opencode CLI).
    python3 -m research.llm_trader.run
Logs to stdout (journal) and to data/llm_trader_log.jsonl. Paper only."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core import llm_trader  # noqa: E402

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s", stream=sys.stdout)
    trader = llm_trader.LlmTrader()
    logging.getLogger("tradelab.llm").info("start model=%s equity=%.2f USD", llm_trader.ai_news.OPENCODE_MODEL, trader.acct.equity())
    llm_trader.loop(trader)
