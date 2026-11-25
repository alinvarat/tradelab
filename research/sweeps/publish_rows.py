"""CLI used by research_sharded.yml: python research/sweeps/publish_rows.py <merged study json> <out jsonl.gz>."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from research.sweeps import hooks   # noqa: E402

if __name__ == "__main__":
    print(hooks.export_trades(sys.argv[1], sys.argv[2]), "trades")
