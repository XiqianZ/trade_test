"""
Check the current ticker_names.json
Compare the folder stored in data/cache with the ticker_names.json file.
If any folder names are missing from the ticker_names.json, delete those folders from the cache.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))  # Add parent directory to sys.path for imports

from data.cache import CACHE_DIR, list_cached_symbols, load_ticker_name_symbols

def cleanup_cache() -> None:
    """Remove any cached symbol folders that are not in ticker_names.json."""
    symbols_in_json = set(load_ticker_name_symbols())
    symbols_in_cache = set(list_cached_symbols())
    missing_symbols = symbols_in_cache - symbols_in_json
    print(f"Cleaning up {len(missing_symbols)} cached symbols not in ticker_names.json: {missing_symbols}")

    for symbol in missing_symbols:
        folder_path = CACHE_DIR / symbol
        if folder_path.is_dir():
            for file in folder_path.iterdir():
                file.unlink()
            folder_path.rmdir()
            print(f"Removed cached symbol folder: {folder_path}")
            
            

if __name__ == "__main__":
    cleanup_cache()