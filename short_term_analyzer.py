import yfinance as yf
from duckduckgo_search import DDGS
from google import genai
import pandas as pd
import numpy as np

# Mapping of popular MT5 assets to yfinance tickers and human-readable names
MT5_ASSET_MAP = {
    "GOLD (XAU/USD)": {"ticker": "GC=F", "tv_symbol": "OANDA:XAUUSD", "name": "Gold / USD Spot Futures"},
    "EUR/USD": {"ticker": "EURUSD=X", "tv_symbol": "FX:EURUSD", "name": "Euro / US Dollar"},
    "GBP/USD": {"ticker": "GBPUSD=X", "tv_symbol": "FX:GBPUSD", "name": "British Pound / US Dollar"},
    "CRUDE OIL (USOIL)": {"ticker": "CL=F", "tv_symbol": "TVC:USOIL", "name": "WTI Crude Oil"},
    "BITCOIN (BTC/USD)": {"ticker": "BTC-USD", "tv_symbol": "BINANCE:BTCUSDT", "name": "Bitcoin"},
    "US TECH 100 (NAS100)": {"ticker": "NQ=F", "tv_symbol": "NASDAQ:QQQ", "name": "Nasdaq 100 Futures"},
    "NVIDIA (NVDA)": {"ticker": "NVDA", "tv_symbol": "NASDAQ:NVDA", "name": "NVIDIA Corporation"},
    "TESLA (TSLA)": {"ticker": "TSLA", "tv_symbol": "NASDAQ:TSLA", "name": "Tesla Inc."}
}

def calculate_short_term_technicals(df: pd.DataFrame) -> dict:
    """Calculates EMA9, EMA21, EMA50, RSI(14), and ATR(14) on price history."""
    if df is None or len(df) < 20:
        return {}

    # EMAs
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()

    # RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0.0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    # ATR (14) - Average True Range for volatility-based Stop-Loss
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=14).mean()

    latest = df.iloc[-1]
    prev_24 = df.iloc[-24:] if len(df) >= 24 else df

    return {
        "current_price": round(float(latest['Close']), 4),
        "ema9": round(float(latest['EMA9']), 4) if pd.notna(latest['EMA9']) else "N/A",
        "ema21": round(float(latest['EMA21']), 4) if pd.notna(latest['EMA21']) else "N/A",
        "ema50": round(float(latest['EMA50']), 4) if pd.notna(latest['EMA50']) else "N/A",
        "rsi": round(float(rsi.iloc[-1]), 1) if pd.notna(rsi.iloc[-1]) else "N/A",
        "atr": round(float(atr.iloc[-1]), 4) if pd.notna(atr.iloc[-1]) else "N/A",
        "recent_high": round(float(prev_24['High'].max()), 4),
        "recent_low": round(float(prev_24['Low'].min()), 4),
    }

def get_short_term_data(ticker_symbol: str, interval="1h", period="1mo"):
    """Fetches short-term OHLCV candles."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            # Fallback to daily if hourly unavailable for specific contract
            df = ticker.history(period="3mo", interval="1d")
        
        technicals = calculate_short_term_technicals(df)
        return technicals, df
    except Exception as e:
        return {"error": str(e)}, None

def get_short_term_news(asset_name: str, max_results=5):
    """Fetches breaking market catalysts & news for the asset."""
    try:
        ddgs = DDGS()
        query = f"{asset_name} trading market breaking news sentiment analysis"
        results = list(ddgs.text(query, max_results=max_results))
        return [{"title": r.get('title', ''), "snippet": r.get('body', '')} for r in results]
    except Exception as e:
        return [{"error": f"News fetch error: {str(e)}"}]

def analyze_short_term_trade(ticker_symbol: str, asset_label: str, api_key: str, model_choice="gemini-flash-latest", timeframe="1h"):
    """
    Generates an actionable MT5 scalp/swing signal with explicit Entry, Stop-Loss,
    Take-Profit levels, and Capital Protection rules.
    """
    period = "1mo" if timeframe in ["1h", "4h"] else "5d"
    technicals, df = get_short_term_data(ticker_symbol, interval=timeframe, period=period)
    
    if "error" in technicals or df is None or df.empty:
        return f"⚠️ **Data Error:** Unable to retrieve short-term price data for `{ticker_symbol}`. Please check symbol or timeframe."

    news = get_short_term_news(asset_label)
    curr_price = technicals.get("current_price", "N/A")
    atr = technicals.get("atr", "N/A")
    rsi = technicals.get("rsi", "N/A")
    ema9 = technicals.get("ema9", "N/A")
    ema21 = technicals.get("ema21", "N/A")
    ema50 = technicals.get("ema50", "N/A")
    high = technicals.get("recent_high", "N/A")
    low = technicals.get("recent_low", "N/A")

    prompt = f"""
You are a top-tier proprietary trading desk risk manager and MT5 intraday/swing trader.
Your primary objective is CAPITAL PRESERVATION and avoiding losses, while capturing high-probability setups with at least a 1:1.5 to 1:2+ Risk-Reward Ratio (R:R).

Asset: {asset_label} ({ticker_symbol})
Chart Timeframe: {timeframe}
Current Price: {curr_price}

--- TECHNICAL METRICS ---
RSI (14): {rsi} (Overbought > 70, Oversold < 30)
ATR (14 - Volatility): {atr}
EMA 9: {ema9}
EMA 21: {ema21}
EMA 50: {ema50}
Recent Range High: {high}
Recent Range Low: {low}

--- BREAKING NEWS & CATALYSTS ---
"""
    for n in news:
        if "error" in n:
            prompt += f"- {n['error']}\n"
        else:
            prompt += f"- {n.get('title')}: {n.get('snippet')}\n"

    prompt += f"""
--- INSTRUCTIONS FOR MT5 TRADE SIGNAL ---
Analyze the current price structure, momentum indicators, and news sentiment. 
Then produce a structured, high-precision trade card formatted in clean Markdown:

### 1. 🎯 Executive Trade Verdict
State clearly in bold: **🟢 BUY / LONG**, **🔴 SELL / SHORT**, or **⚪ WAIT (NO TRADE)**.
*(Rule: If the market is choppy, in tight consolidation, or news is ambiguous, you MUST choose **WAIT (NO TRADE)** to prevent loss of money!)*

### 2. 📊 Trade Parameters (Exact MT5 Execution Levels)
Provide exact numerical price figures:
- **Action**: BUY / SELL / WAIT
- **Entry Zone**: (e.g. 2,650.00 - 2,652.50)
- **🛑 Stop Loss (SL)**: (CRITICAL: Must be placed logically beyond support/resistance using the ATR {atr} as a buffer to prevent premature stop-outs)
- **🎯 Take Profit 1 (TP1)**: (Conservative profit target at ~1:1.5 R:R)
- **🎯 Take Profit 2 (TP2)**: (Extended runner target at ~1:2.5+ R:R)
- **Risk / Reward Ratio (R:R)**: (e.g. 1:2.0)

### 3. 🛡️ Capital Preservation & Money Management Rules
- **Account Risk**: Recommend risking no more than 1% to 2% of total MT5 account equity on this trade.
- **Trade Management**: Explain when to move Stop Loss to Breakeven (e.g. once TP1 is achieved).
- **Invalidation Level**: The exact price condition that voids this trade idea.

### 4. 📰 Catalyst & Technical Justification
Summarize in 2-3 bullet points why this setup is valid based on RSI, EMA alignment, and current news sentiment.

Disclaimer: Always note this is an AI trading signal and strict risk management must be exercised on MT5.
"""

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_choice,
            contents=prompt,
        )
        return response.text
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            return "⚠️ **Rate Limit:** Gemini API rate limit reached. Please switch to `gemini-flash-latest` in the sidebar or wait 30 seconds."
        return f"⚠️ **Error generating MT5 signal:** {err}"
