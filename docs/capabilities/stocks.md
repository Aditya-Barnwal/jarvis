# Capability: Stocks & markets

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [../build/](../build/).

**What you want:** "How's TCS doing?", "Show me the Nifty", "What did the market do today?"

**Reality:** ✅ fully doable and free. Live quotes, history, basic analysis — all read-only. **Not** trading (that's a hard line — see below).

---

## Data sources

Free market-data APIs cover quotes and history for Indian and global markets:

- **yfinance** (Yahoo Finance) — you've used this before in the stock-forecasting project. Free, covers NSE/BSE (`TCS.NS`, `^NSEI` for Nifty) and global tickers. Great for quotes + history.
- Alternatives if yfinance rate-limits: Alpha Vantage (free tier, key needed), or NSE's own endpoints (fiddly).

## Tools

```python
# src/tools/stocks.py
import yfinance as yf

@tool({
    "name": "get_quote",
    "description": "Get the latest price and day change for a ticker (e.g. 'TCS.NS', '^NSEI').",
    "parameters": {"type": "object",
        "properties": {"symbol": {"type": "string"}},
        "required": ["symbol"]},
})
def get_quote(symbol: str):
    t = yf.Ticker(symbol)
    info = t.history(period="2d")
    last = info["Close"].iloc[-1]
    prev = info["Close"].iloc[-2]
    return {"symbol": symbol, "price": round(float(last), 2),
            "change_pct": round((last - prev) / prev * 100, 2)}

@tool({
    "name": "market_summary",
    "description": "Summarize major Indian indices (Nifty, Sensex) for today.",
    "parameters": {"type": "object", "properties": {}},
})
def market_summary():
    out = {}
    for name, sym in {"Nifty": "^NSEI", "Sensex": "^BSESN"}.items():
        out[name] = get_quote(sym)
    return out
```

## Analysis (still read-only)

Beyond quotes, the brain can reason over data you fetch:

- "Is TCS up or down over the last month?" → pull history, compute, explain.
- "How volatile has the Nifty been this week?" → fetch, compute stdev, describe.
- Simple technicals (moving averages, % change) — you already know these from the forecasting project.

This dovetails with your quant-prep interest: the same data plumbing you build here feeds a proper backtesting/risk-metrics project later. Reuse it.

## The hard line: no trading

Jarvis **views and analyzes**; it does not **trade**. Executing buys/sells, transferring funds, or placing orders is off the table — it's in the "never build" list for the same reason job-copilot never auto-submits:

- Financial transactions are irreversible and high-stakes.
- Broker automation risks account terms and real money.
- Jarvis giving *personalized* buy/sell advice would be it acting as an unlicensed financial advisor.

So Jarvis will happily tell you TCS is down 0.6% and what its month looked like. It will not decide to sell your TCS, and it won't tell you whether *you* should. Information, not instructions.

## Example

```
You: "How are markets and how's TCS?"
Jarvis: "Nifty's roughly flat today, up 0.1%. TCS is at ₹3,842, down 0.6%.
         Over the last month TCS is down about 3% — want the chart?"
```
