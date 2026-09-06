from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from data.cache import CACHE_DIR


def list_tse_symbols(cache_dir: str | Path | None = None) -> list[str]:
    """Return all Tokyo Stock Exchange symbols currently available in the cache.

    TSE tickers in this project are stored with the .T suffix, e.g. "7203.T".
    """
    root = Path(cache_dir) if cache_dir is not None else CACHE_DIR
    if not root.exists():
        return []

    symbols = [
        child.name
        for child in root.iterdir()
        if child.is_dir() and child.name.endswith(".T")
    ]
    return sorted(symbols)


def main() -> None:
    symbols = list_tse_symbols()
    print(f"Tokyo Stock Exchange symbols ({len(symbols)}):")
    for symbol in symbols:
        print(symbol)


if __name__ == "__main__":
    main()
