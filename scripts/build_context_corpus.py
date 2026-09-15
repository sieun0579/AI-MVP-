#!/usr/bin/env python3
"""Build scope-separated MomentLab context corpora."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from momentlab_context.converter import write_corpora


def main() -> None:
    outputs = write_corpora(ROOT)
    for scope, path in outputs.items():
        print(f"{scope}: {path}")


if __name__ == "__main__":
    main()
