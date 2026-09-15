#!/usr/bin/env python3
"""Create the runtime-only local search index."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from momentlab_context.search import write_search_index


if __name__ == "__main__":
    print(write_search_index(ROOT))
