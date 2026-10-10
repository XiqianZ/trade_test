import json
from pathlib import Path
import pytest

import data.cache as cache_mod
import data.housekeeping as housekeeping_mod


def test_cleanup_cache_removes_missing_symbols(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cache_mod, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(housekeeping_mod, "CACHE_DIR", cache_dir)

    # Setup ticker_names.json with AAPL and 7203.T
    payload = {"AAPL": "Apple", "7203.T": "Toyota"}
    (cache_dir / "ticker_names.json").write_text(json.dumps(payload), encoding="utf-8")

    # Create folders: AAPL, 7203.T, and OBSOLETE
    (cache_dir / "AAPL").mkdir()
    (cache_dir / "AAPL" / "1d.parquet").write_text("data")
    (cache_dir / "7203.T").mkdir()
    (cache_dir / "7203.T" / "1d.parquet").write_text("data")
    (cache_dir / "OBSOLETE").mkdir()
    (cache_dir / "OBSOLETE" / "1d.parquet").write_text("data")

    deleted = housekeeping_mod.cleanup_cache(dry_run=False)

    assert deleted == ["OBSOLETE"]
    assert (cache_dir / "AAPL").exists()
    assert (cache_dir / "7203.T").exists()
    assert not (cache_dir / "OBSOLETE").exists()


def test_cleanup_cache_dry_run_does_not_delete(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cache_mod, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(housekeeping_mod, "CACHE_DIR", cache_dir)

    payload = {"AAPL": "Apple"}
    (cache_dir / "ticker_names.json").write_text(json.dumps(payload), encoding="utf-8")

    (cache_dir / "AAPL").mkdir()
    (cache_dir / "OBSOLETE").mkdir()

    deleted = housekeeping_mod.cleanup_cache(dry_run=True)

    assert deleted == ["OBSOLETE"]
    assert (cache_dir / "AAPL").exists()
    assert (cache_dir / "OBSOLETE").exists()


def test_cleanup_cache_aborts_if_ticker_names_empty(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cache_mod, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(housekeeping_mod, "CACHE_DIR", cache_dir)

    # Empty payload or missing file
    (cache_dir / "AAPL").mkdir()

    deleted = housekeeping_mod.cleanup_cache(dry_run=False)

    assert deleted == []
    assert (cache_dir / "AAPL").exists()
