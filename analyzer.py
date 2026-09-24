import yfinance as yf
from duckduckgo_search import DDGS
from google import genai
from google.genai import types
import pandas as pd

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
                "Beta (3Y)": info.get("beta3Year", "N/A")
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
                "Price to Book": info.get("priceToBook", "N/A"),
                "Debt to Equity": info.get("debtToEquity", "N/A"),
                "Return on Equity": info.get("returnOnEquity", "N/A"),
                "Revenue Growth (YoY)": info.get("revenueGrowth", "N/A"),
                "Earnings Growth (YoY)": info.get("earningsGrowth", "N/A"),
                "Dividend Yield": info.get("dividendYield", "N/A"),
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
    """Combines fundamental & technical data and asks Gemini for an investment signal."""
    # 1. Gather Data
    fundamentals, hist = get_stock_data(ticker)
    if "error" in fundamentals:
        return f"⚠️ **Data Error:** {fundamentals['error']}"
        
    news = get_recent_news(ticker)
    
    # Calculate some basic technicals for context
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
You are an expert financial advisor specializing in long-term investing (1-5+ years horizon).
The investor executes trades manually on the Moomoo trading platform and seeks disciplined, fundamental-oriented guidance.

Asset: {ticker} ({name})
Asset Type: {fundamentals.get('Type')}

--- FUNDAMENTALS & METRICS ---
"""
    for k, v in fundamentals.items():
        prompt += f"{k}: {v}\n"

    prompt += f"""
--- TECHNICAL CONTEXT ---
50-Day Moving Average: {ma_50}
200-Day Moving Average: {ma_200}
52-Week Range: {fundamentals.get('52 Week Low')} - {fundamentals.get('52 Week High')}

--- RECENT NEWS & MARKET SENTIMENT ---
"""
    for n in news:
        if "error" in n:
             prompt += f"- {n['error']}\n"
        else:
             prompt += f"- {n.get('title')}: {n.get('snippet')}\n"

    prompt += f"""
--- ANALYSIS INSTRUCTIONS ---
Provide an objective, structured report formatted in clean Markdown:
1. **Executive Verdict**: Give a clear, bold **BUY**, **ACCUMULATE/DCA (Dollar-Cost Average)**, **HOLD**, or **SELL** recommendation for a long-term horizon.
2. **Fundamental Health & Valuation**:
   - {"For this ETF, analyze its expense ratio, index/sector exposure, and long-term diversification benefits." if is_etf else "Analyze the company's valuation (P/E, PEG), profitability, debt safety, and moat/growth potential."}
3. **Long-Term Risk Factors**: What are the top 2-3 risks investors should be aware of?
4. **Actionable Moomoo Plan**: Suggested entry strategy (e.g. Lump sum vs regular DCA, price levels to watch, or limit order advice on Moomoo).

Disclaimer: Conclude with a standard reminder that this is AI-assisted research and not certified financial advice.
"""

    # 3. Call Gemini
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_choice,
            contents=prompt,
        )
        return response.text
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            return "⚠️ **Gemini Free Tier Quota Limit Reached:** You hit the free tier rate limit. Please switch to `gemini-flash-latest` in the sidebar or wait a minute before retrying."
        return f"⚠️ **Error communicating with Gemini API:** {err_msg}"
