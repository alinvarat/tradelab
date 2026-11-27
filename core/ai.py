"""On-demand AI analyst: runs the local `claude` CLI with no tools, from /tmp, with the analysis and
headlines as input. Every call is logged to data/ai_log.jsonl. Called only when the user presses the button."""
import json
import shutil
import subprocess
import time
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "data" / "ai_log.jsonl"
MODEL = "claude-haiku-5-5"  # owner 2026-11-28: Haiku only, no Sonnet anywhere in TradeLab
SYSTEM = ("You are a careful market analyst inside a paper-trading simulator. Use only the data given. "
          "Write plain English with these sections: Summary, Trend and momentum, Key levels, News and sentiment, "
          "Risks, Scenario plan (bullish / bearish triggers with price levels), Position sizing note. "
          "Be concrete, cite the numbers you use, state uncertainty, never promise profit, keep it under 350 words. "
          "End with: 'Simulation analysis only, not financial advice.'")


def analyst(symbol: str, analysis: dict, news: dict, question: str = "") -> dict:
    slim = {k: analysis.get(k) for k in ("symbol", "name", "price", "currency", "score", "rating", "signals",
                                          "events", "trend", "momentum", "volatility", "levels", "performance", "risk")}
    heads = [{"title": x["title"], "source": x["source"], "age_h": round((time.time() - x["ts"]) / 3600, 1),
              "sentiment": x["sentiment"]} for x in news.get("items", [])[:15]]
    prompt = json.dumps({"technical": slim, "news_summary": news.get("summary"), "headlines": heads,
                         "user_question": question or None}, default=str)
    if shutil.which("claude") is None:  # e.g. inside the production container
        return {"text": "", "error": "AI analyst is not available on this server (no claude CLI installed).",
                "seconds": 0, "model": MODEL}
    t0 = time.time()
    rec = {"ts": t0, "symbol": symbol, "model": MODEL, "input": prompt}
    try:
        r = subprocess.run(["claude", "-p", "--model", MODEL, "--tools", "", "--system-prompt", SYSTEM,
                            "--no-session-persistence", "--disable-slash-commands", "--setting-sources", ""],
                           input=prompt, capture_output=True, text=True, timeout=180, cwd="/tmp")
        text = r.stdout.strip()
        err = None if r.returncode == 0 and text else (r.stderr.strip()[-400:] or f"exit {r.returncode}")
    except Exception as e:  # noqa: BLE001
        text, err = "", str(e)
    rec.update(output=text, error=err, seconds=round(time.time() - t0, 1))
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return {"text": text, "error": err, "seconds": rec["seconds"], "model": MODEL}
