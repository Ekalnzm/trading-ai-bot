import yfinance as yf
from duckduckgo_search import DDGS
from google import genai
from google.genai import types
import pandas as pd
import time

def get_stock_data(ticker_symbol):
    """Fetches fundamental and technical data for a given ticker (supports stocks and ETFs)."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info or {}
        
        # Verify ticker actually returned valid data
        if not info or ("shortName" not in info and "longName" not in info and "regularMarketPrice" not in info and "currentPrice" not in info):
            hist_check = ticker.history(period="5d")
            if hist_check.empty:
                return {"error": f"Ticker '{ticker_symbol}' not found. Please verify the symbol (e.g. VOO for S&P 500 ETF, AAPL for Apple)."}, None

        # Get historical data for the last year
        hist = ticker.history(period="1y")
        quote_type = info.get("quoteType", "EQUITY")
        
        # Check if it's an ETF or standard stock
        if quote_type == "ETF":
            fundamentals = {
                "Type": "ETF (Exchange Traded Fund)",
                "Fund Name": info.get("shortName") or info.get("longName", ticker_symbol),
                "Category": info.get("category", "N/A"),
                "Fund Family": info.get("fundFamily", "N/A"),
                "Total Assets / AUM": info.get("totalAssets", "N/A"),
                "Expense Ratio (Net)": f"{info.get('netExpenseRatio', info.get('annualReportExpenseRatio', 'N/A'))}",
                "Dividend Yield": info.get("yield") or info.get("dividendYield", "N/A"),
                "52 Week High": info.get("fiftyTwoWeekHigh", "N/A"),
                "52 Week Low": info.get("fiftyTwoWeekLow", "N/A"),
                "Current Price": info.get("currentPrice") or info.get("regularMarketPrice", "N/A"),
                "Trailing P/E": info.get("trailingPE", "N/A"),
                "Beta (3Y)": info.get("beta3Year", "N/A"),
                "YTD Return": info.get("ytdReturn", "N/A")
            }
        else:
            fundamentals = {
                "Type": "Stock / Equity",
                "Company Name": info.get("shortName") or info.get("longName", ticker_symbol),
                "Sector": info.get("sector", "N/A"),
                "Industry": info.get("industry", "N/A"),
                "Market Cap": info.get("marketCap", "N/A"),
                "Trailing P/E": info.get("trailingPE", "N/A"),
                "Forward P/E": info.get("forwardPE", "N/A"),
                "PEG Ratio": info.get("pegRatio", "N/A"),
                "Price to Book (P/B)": info.get("priceToBook", "N/A"),
                "Enterprise Value / EBITDA": info.get("enterpriseToEbitda", "N/A"),
                "Operating Margin": info.get("operatingMargins", "N/A"),
                "Profit Margin": info.get("profitMargins", "N/A"),
                "Return on Equity (ROE)": info.get("returnOnEquity", "N/A"),
                "Free Cash Flow": info.get("freeCashflow", "N/A"),
                "Total Cash": info.get("totalCash", "N/A"),
                "Total Debt": info.get("totalDebt", "N/A"),
                "Current Ratio (Liquidity)": info.get("currentRatio", "N/A"),
                "Debt to Equity": info.get("debtToEquity", "N/A"),
                "Revenue Growth (YoY)": info.get("revenueGrowth", "N/A"),
                "Earnings Growth (YoY)": info.get("earningsGrowth", "N/A"),
                "Dividend Yield": info.get("dividendYield", "N/A"),
                "Payout Ratio": info.get("payoutRatio", "N/A"),
                "Wall St Consensus Target": info.get("targetMeanPrice", "N/A"),
                "Wall St Target Range": f"{info.get('targetLowPrice', 'N/A')} - {info.get('targetHighPrice', 'N/A')}",
                "Wall St Recommendation": info.get("recommendationKey", "N/A"),
                "52 Week High": info.get("fiftyTwoWeekHigh", "N/A"),
                "52 Week Low": info.get("fiftyTwoWeekLow", "N/A"),
                "Current Price": info.get("currentPrice") or info.get("regularMarketPrice", "N/A")
            }
        
        return fundamentals, hist
    except Exception as e:
        return {"error": str(e)}, None

def get_recent_news(ticker_symbol, max_results=5):
    """Fetches recent news headlines for the ticker."""
    try:
        ddgs = DDGS()
        query = f"{ticker_symbol} stock investment news"
        results = list(ddgs.text(query, max_results=max_results))
        news = [{"title": r.get('title', ''), "snippet": r.get('body', '')} for r in results]
        return news
    except Exception as e:
        return [{"error": f"Could not fetch news: {str(e)}"}]

def analyze_stock(ticker, api_key, model_choice='gemini-flash-latest'):
    """Combines fundamental & technical data and asks Gemini for an institutional fundamental signal."""
    # 1. Gather Data
    fundamentals, hist = get_stock_data(ticker)
    if "error" in fundamentals:
        return f"⚠️ **Data Error:** {fundamentals['error']}"
        
    news = get_recent_news(ticker)
    
    # Calculate key technicals for price positioning
    if hist is not None and not hist.empty:
        current_price = hist['Close'].iloc[-1]
        ma_50 = round(hist['Close'].rolling(window=50).mean().iloc[-1], 2) if len(hist) >= 50 else "N/A"
        ma_200 = round(hist['Close'].rolling(window=200).mean().iloc[-1], 2) if len(hist) >= 200 else "N/A"
    else:
        current_price = "N/A"
        ma_50 = "N/A"
        ma_200 = "N/A"

    is_etf = fundamentals.get("Type") == "ETF (Exchange Traded Fund)"
    name = fundamentals.get("Fund Name") if is_etf else fundamentals.get("Company Name", ticker)

    # 2. Construct Prompt
    prompt = f"""
You are an institutional fundamental equity analyst & portfolio manager.
Provide an in-depth, rigorous fundamental assessment for:

Asset: {ticker} ({name})
Asset Type: {fundamentals.get('Type')}

--- COMPREHENSIVE FUNDAMENTALS & BALANCE SHEET ---
"""
    for k, v in fundamentals.items():
        prompt += f"{k}: {v}\n"

    prompt += f"""
--- PRICE & MOVING AVERAGE CONTEXT ---
Current Price: {current_price}
50-Day Moving Average: {ma_50}
200-Day Moving Average: {ma_200}
52-Week Range: {fundamentals.get('52 Week Low')} - {fundamentals.get('52 Week High')}

--- RECENT NEWS & SENTIMENT ---
"""
    for n in news:
        if "error" in n:
             prompt += f"- {n['error']}\n"
        else:
             prompt += f"- {n.get('title')}: {n.get('snippet')}\n"

    prompt += f"""
--- REQUIRED OUTPUT FORMAT (INSTITUTIONAL FUNDAMENTAL SCORECARD) ---
Format your response in professional, clean Markdown with clear headings:

### 1. 🏆 Executive Verdict & Fundamental Score
- **Verdict**: State clearly in bold: **🟢 STRONG BUY / HEAVY DCA**, **🟢 ACCUMULATE / DCA**, **🟡 HOLD / WAIT FOR DIP**, or **🔴 OVERVALUED / REDUCE**.
- **Fundamental Quality Score**: Rate from **1/10 to 10/10** with rationale.
- **Investment Horizon**: Long-term (1-5+ years).

### 2. 💎 Valuation & Fair Value Margin of Safety
- **Estimated Fair Value Range**: Provide an estimated intrinsic fair value (or PEG/DCF baseline) vs Current Price ({current_price}).
- **Discount / Premium**: State whether it is currently undervalued (at a discount) or trading at an extended premium.
- **Wall Street Consensus**: Compare with Wall Street analyst target if available.

### 3. 🎯 Concrete Buy & DCA Accumulation Zones (Exact Dollar Levels)
Provide explicit price ranges so the investor knows exactly what to do:
- **🟢 Heavy Buy / Value Zone**: (Specific price range where this asset is a great bargain)
- **🟡 Standard DCA Zone**: (Specific price range for recurring weekly/monthly automated investing)
- **🔴 Trim / Pause Zone**: (Price level where new capital should wait for a pullback)

### 4. 📊 Fundamental Health & Competitive Moat
{"- **ETF Efficiency & Strategy**: Analyze its expense ratio, index diversification, sector weightings, and resilience during bear markets." if is_etf else "- **Moat & Pricing Power**: What is the company's competitive advantage?\n- **Financial Health & Solvency**: Analyze cash flow, margins, and debt safety.\n- **Growth & Reinvestment**: Revenue and earnings growth trajectory."}

### 5. ⚠️ Top 3 Fundamental Risks
Detail the top 3 fundamental or macroeconomic risks that could impact this asset.

### 6. 📱 Actionable Moomoo Execution Blueprint
Specific advice on how to execute on Moomoo (e.g. Dollar-Cost Averaging schedule, limit orders at key support zones, or lump-sum timing).

Disclaimer: Conclude with a standard reminder that this is AI-assisted research and not certified financial advice.
"""

    # 3. Call Gemini with auto-retry and model fallback
    fallback_models = [model_choice, "gemini-2.5-flash", "gemini-flash-latest", "gemini-3.8-flash"]
    seen = set()
    models_to_try = [m for m in fallback_models if not (m in seen or seen.add(m))]
    
    last_err = ""
    for model in models_to_try:
        for attempt in range(2):
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                if response and response.text:
                    return response.text
            except Exception as e:
                last_err = str(e)
                if "503" in last_err or "UNAVAILABLE" in last_err or "429" in last_err:
                    time.sleep(1.5)
                    continue
                else:
                    break

    if "429" in last_err or "RESOURCE_EXHAUSTED" in last_err:
        return "⚠️ **Gemini Free Tier Quota Limit Reached:** Google free tier limit reached. Please wait 1 minute before retrying."
    if "503" in last_err or "UNAVAILABLE" in last_err:
        return "⚠️ **Google Gemini High Demand:** Google servers are temporarily experiencing high traffic spikes. Please click **Analyze Fundamentals** again in a few moments."
    return f"⚠️ **Error communicating with Gemini API:** {last_err}"
