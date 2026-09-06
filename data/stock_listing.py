"""download and cache stock ticker information.

 - US tickers are fetched from Nasdaq Trader and SEC EDGAR.
 - JPX tickers are fetched directly from the JPX website.
 - We are not considering US tickers for now by 2026.09.26 & but we may revisit this decision in the future.
"""
import io
import json
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import pandas as pd

def fetch_us_tickers() -> pd.DataFrame:
    # """Fetches US common stocks from Nasdaq Trader directory."""
    # url = "ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqtraded.txt"
    # # Fallback to HTTP via SEC EDGAR if FTP is firewalled
    # try:
    #     df = pd.read_csv(url, sep="|")
    #     # Remove the file creation timestamp trailer
    #     df = df[df["Test Issue"] == "N"]
    #     # Keep common stocks only (filter out ETFs and test issues)
    #     df = df[df["ETF"] == "N"]
        
    #     # Clean ticker symbols for yfinance (e.g., BRK.B -> BRK-B)
    #     df["clean_symbol"] = df["Symbol"].str.replace(".", "-", regex=False)
    #     return df[["clean_symbol", "Security Name", "Listing Exchange"]].rename(
    #         columns={"clean_symbol": "symbol", "Security Name": "name", "Listing Exchange": "exchange"}
    #     )
    # except Exception:
    #     # SEC fallback
    #     headers = {"User-Agent": "ResearchDesk admin@sampledomain.com"}
    #     res = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers)
    #     data = res.json()
    #     df = pd.DataFrame.from_dict(data, orient="index")
    #     df["symbol"] = df["ticker"].str.replace(".", "-", regex=False)
    #     return df[["symbol", "title"]].rename(columns={"title": "name"})
    return pd.DataFrame(columns=["symbol", "name", "exchange"])

def fetch_jpx_tickers(
    markets: list[str] | None = None,
    save_path: str | None = "universe_jpx.parquet"
) -> pd.DataFrame:
    """
    Scrapes the dynamic Excel file link from the JPX directory page,
    extracts listed equity metadata, and formats symbols for yfinance.
    
    Target page: https://www.jpx.co.jp/markets/statistics-equities/misc/01.html
    """
    page_url = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 1. Scrape the page to locate the live download URL for data_j.xls / data_j.xlsx
    res = requests.get(page_url, headers=headers, timeout=15)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    link_node = soup.find(
        "a", 
        href=lambda href: bool(href) and ("data_j.xls" in href or href.endswith((".xls", ".xlsx")))
    )

    if not link_node or not link_node.get("href"):
        raise RuntimeError("Failed to resolve the Excel file download URL on JPX page.")

    href = link_node.get("href")
    if not isinstance(href, str):
        raise RuntimeError("Resolved JPX download link has an invalid href type.")
    excel_url = urljoin(page_url, href)

    # 2. Download and read binary Excel stream
    excel_res = requests.get(excel_url, headers=headers, timeout=30)
    excel_res.raise_for_status()

    # Engine fallback accommodates both legacy .xls and newer .xlsx files
    try:
        df = pd.read_excel(io.BytesIO(excel_res.content), engine="xlrd")
    except Exception:
        df = pd.read_excel(io.BytesIO(excel_res.content), engine="openpyxl")

    # 3. Filter out ETFs, ETNs, REITs, and foreign markets unless requested
    target_segments = markets or ["プライム", "スタンダード", "グロース"]
    pattern = "|".join(target_segments)
    
    # Column: 市場・商品区分 (Market/Product Section)
    df = df[df["市場・商品区分"].astype(str).str.contains(pattern, na=False)].copy()

    # 4. Standardize columns and format tickers for yfinance compatibility
    # Ensure code is string-cast first to protect leading zeros and new alphanumeric codes
    df["code"] = df["コード"].astype(str).str.strip()
    df["symbol"] = df["code"] + ".T"
    df["name"] = df["銘柄名"].astype(str).str.strip()
    df["market"] = df["市場・商品区分"].astype(str).str.strip()
    df["sector_33"] = df["33業種区分"].astype(str).str.strip() if "33業種区分" in df.columns else ""
    df["sector_17"] = df["17業種区分"].astype(str).str.strip() if "17業種区分" in df.columns else ""

    result = df[["symbol", "code", "name", "market", "sector_33", "sector_17"]].reset_index(drop=True)

    if save_path:
        result.to_parquet(save_path, index=False)

    return result

def sync_ticker_universe(target: str = "US") -> list[str]:
    df = fetch_us_tickers() if target == "US" else fetch_jpx_tickers()
    symbols = df["symbol"].dropna().unique().tolist()
    cache_dir = Path("data/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_dir / f"universe_{target.lower()}.parquet", index=False)
    return symbols

def convert_to_yfinance_symbol_tokyo(code: str) -> str:
    return f"{code}.T"

def convert_to_yfinance_symbol_us(code: str) -> str:
    return code

def update_ticker_list() -> None:
    """Convert the cached JPX universe parquet into data/cache/ticker_names.json.

    The parquet file stores rows like:
        symbol, name, market, ...
    The JSON target is a simple symbol -> company name map used elsewhere in the app.
    """
    parquet_path = Path("data/cache/universe_jpx.parquet")
    names_path = Path("data/cache/ticker_names.json")

    if not parquet_path.exists():
        raise FileNotFoundError(f"Missing JPX universe file: {parquet_path}")

    df = pd.read_parquet(parquet_path)
    required = {"symbol", "name"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"JPX universe parquet is missing required columns: {missing}")

    name_map: dict[str, str] = {}
    for _, row in df.dropna(subset=["symbol", "name"]).iterrows():
        symbol = str(row["symbol"]).strip()
        name = str(row["name"]).strip()
        if symbol and name:
            name_map[symbol] = name

    names_path.parent.mkdir(parents=True, exist_ok=True)
    names_path.write_text(json.dumps(name_map, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    # us_symbols = sync_ticker_universe("US")
    # print(f"Loaded {len(us_symbols)} active US equities.")

    jpx_symbols = sync_ticker_universe("JPX")
    update_ticker_list()
    print(f"Loaded {len(jpx_symbols)} active JPX equities.")