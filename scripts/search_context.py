#!/usr/bin/env python3
"""Search MomentLab runtime Context and print source-grounded JSON."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from momentlab_context.search import ContextSearchEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Search MomentLab runtime Context")
    parser.add_argument("query", help="질문 또는 검색어")
    parser.add_argument("--top-k", type=int, default=5, help="최대 검색 결과 수")
    args = parser.parse_args()
    engine = ContextSearchEngine.from_project(ROOT)
    print(json.dumps(engine.search(args.query, top_k=args.top_k), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
