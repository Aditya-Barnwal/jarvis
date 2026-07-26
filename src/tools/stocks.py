"""Stocks & markets — read-only quotes via Yahoo's public chart API (no key, no
new deps). Indian tickers: TCS.NS, RELIANCE.NS; indices: ^NSEI (Nifty), ^BSESN
(Sensex). VIEWING ONLY — no trading, no buy/sell advice (project hard line)."""
import json
import urllib.parse
import urllib.request

from brain import tool

_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

# Spoken-name → ticker for the common Indian asks. The model can also pass
# explicit tickers directly ("AAPL", "INFY.NS").
_ALIASES = {
    "nifty": "^NSEI", "sensex": "^BSESN", "tcs": "TCS.NS", "infosys": "INFY.NS",
    "reliance": "RELIANCE.NS", "hdfc": "HDFCBANK.NS", "hdfc bank": "HDFCBANK.NS",
    "wipro": "WIPRO.NS", "zomato": "ZOMATO.NS", "tata motors": "TATAMOTORS.NS",
    "sbi": "SBIN.NS", "icici": "ICICIBANK.NS", "airtel": "BHARTIARTL.NS",
    "apple": "AAPL", "google": "GOOGL", "microsoft": "MSFT", "tesla": "TSLA",
    "nvidia": "NVDA", "amazon": "AMZN",
}


@tool({"name": "get_stock",
       "description": "Current price and day change for a stock or index (read-only; "
                      "e.g. 'TCS', 'Nifty', 'Apple', or a ticker like 'INFY.NS').",
       "parameters": {"type": "object",
           "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}})
def get_stock(symbol: str):
    sym = _ALIASES.get(symbol.strip().lower(), symbol.strip().upper())
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(sym)}?range=5d&interval=1d")
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.load(r)
        res = data["chart"]["result"][0]
        meta = res["meta"]
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        if price is None:
            return {"error": f"no price data for '{sym}'"}
        out = {"symbol": sym, "name": meta.get("shortName") or sym,
               "price": round(price, 2), "currency": meta.get("currency", "")}
        if prev:
            out["change_pct"] = round((price - prev) / prev * 100, 2)
            out["previous_close"] = round(prev, 2)
        return out
    except Exception as e:
        return {"error": f"couldn't fetch '{sym}' ({type(e).__name__}) — "
                         "check the ticker or try the full symbol like TCS.NS"}
