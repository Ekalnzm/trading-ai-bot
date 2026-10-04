#!/usr/bin/env python3
"""
Standalone GitHub Actions scanner.
Reads all credentials from environment variables (set as GitHub Secrets).
Scans the watchlist, analyzes fundamentals & MT5 signals, and sends
BUY/DCA alerts to Telegram — completely independent of the Streamlit app.
"""

import os
import sys
import time
import datetime

# ── Credentials from GitHub Secrets (environment variables) ──────────────
GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY", "").strip()
TG_BOT_TOKEN     = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT_ID       = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
MODEL_CHOICE     = os.environ.get("MODEL_CHOICE", "gemini-flash-latest").strip()

# Watchlist — comma-separated in the secret, e.g. "VOO,QQQ,SCHD,AAPL,NVDA"
WATCHLIST_RAW    = os.environ.get("WATCHLIST", "VOO,QQQ,SCHD,AAPL")
WATCHLIST        = [t.strip().upper() for t in WATCHLIST_RAW.split(",") if t.strip()]

def log(msg: str):
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{ts}] {msg}", flush=True)

def send_telegram(message: str) -> bool:
    import requests
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        log("⚠️  Telegram credentials missing — alert not sent.")
        return False
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        if data.get("ok"):
            log(f"✅ Telegram alert sent!")
            return True
        else:
            log(f"❌ Telegram error: {data.get('description')}")
            return False
    except Exception as e:
        log(f"❌ Telegram request failed: {e}")
        return False

def analyze(ticker: str) -> str | None:
    """Calls Gemini to analyze the ticker. Returns analysis text or None on error."""
    from analyzer import analyze_stock
    try:
        result = analyze_stock(ticker, GEMINI_API_KEY, model_choice=MODEL_CHOICE)
        return result
    except Exception as e:
        log(f"❌ Error analyzing {ticker}: {e}")
        return None

def is_buy_signal(text: str) -> bool:
    keywords = ["**BUY**", "**ACCUMULATE**", "**DCA**", "STRONG BUY",
                "HEAVY DCA", "🟢 STRONG BUY", "🟢 ACCUMULATE"]
    upper = text.upper()
    return any(kw.upper() in upper for kw in keywords)

def format_alert(ticker: str, analysis: str, price: str = "N/A") -> str:
    header = f"🚨 *AI SIGNAL ALERT: {ticker}* 🚨\n"
    header += f"💰 Price: {price}\n"
    header += "━━━━━━━━━━━━━━━━━━━━\n"
    body = analysis.replace("**", "*")
    if len(body) > 3500:
        body = body[:3400] + "\n\n_(View full report on web app)_"
    footer = "\n━━━━━━━━━━━━━━━━━━━━\n"
    footer += "📱 _AI-assisted research. Not certified financial advice._"
    return header + body + footer

def main():
    log("=" * 60)
    log("🤖 AI Trading Signal Bot — GitHub Actions Scan Started")
    log(f"Watchlist: {', '.join(WATCHLIST)}")
    log(f"AI Model:  {MODEL_CHOICE}")
    log("=" * 60)

    if not GEMINI_API_KEY:
        log("❌ GEMINI_API_KEY secret is not set. Aborting.")
        sys.exit(1)

    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        log("⚠️  TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — results will print only.")

    alerts_sent = 0
    scan_summary = []

    for ticker in WATCHLIST:
        log(f"🔍 Scanning {ticker}...")
        try:
            import yfinance as yf
            info = yf.Ticker(ticker).info or {}
            price = info.get("currentPrice") or info.get("regularMarketPrice", "N/A")
            price_str = f"${price:.2f}" if isinstance(price, (int, float)) else str(price)
        except Exception:
            price_str = "N/A"

        analysis = analyze(ticker)
        if not analysis:
            scan_summary.append(f"• {ticker}: ❌ Analysis failed")
            continue

        if is_buy_signal(analysis):
            log(f"🎯 BUY/DCA signal detected for {ticker} at {price_str}!")
            msg = format_alert(ticker, analysis, price_str)
            sent = send_telegram(msg)
            scan_summary.append(f"• {ticker}: 🟢 BUY/DCA alert {'sent ✅' if sent else 'failed ❌'}")
            if sent:
                alerts_sent += 1
        else:
            log(f"📊 {ticker}: Neutral/Hold — no alert sent.")
            scan_summary.append(f"• {ticker}: 🟡 Neutral / Hold")

        # Pause between tickers to avoid Gemini rate limits
        time.sleep(3)

    # Send a daily summary to Telegram
    summary_lines = ["📊 *Daily Scan Summary*", ""]
    summary_lines += scan_summary
    summary_lines += ["", f"_Alerts sent: {alerts_sent}/{len(WATCHLIST)}_"]
    summary_msg = "\n".join(summary_lines)
    log("📤 Sending daily summary...")
    send_telegram(summary_msg)

    log("=" * 60)
    log(f"✅ Scan complete. {alerts_sent} alert(s) delivered to Telegram.")
    log("=" * 60)

if __name__ == "__main__":
    main()
