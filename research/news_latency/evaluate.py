"""Print the news-latency evaluation (latency.jsonl on the news volume). No orders, no network."""
import json

from core import news_latency

if __name__ == "__main__":
    print(json.dumps(news_latency.evaluate(use_cache=False), indent=1))
