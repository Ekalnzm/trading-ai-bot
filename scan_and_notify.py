#!/usr/bin/env python3
"""
Standalone GitHub Actions scanner with Dual-Key Failover.
Reads credentials from environment variables (GitHub Secrets).
Automatically fails over between GEMINI_API_KEY and GEMINI_API_KEY_2
if one reaches its daily free rate limit!
"""

import os
import sys
import time
import datetime

# Ensure stdout/stderr handles UTF-8 smoothly
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ── API Key Pool (Automatic Failover) ──────────────────────────────────
GEMINI_KEYS = []
for k in [os.environ.get("GEMINI_API_KEY", ""), os.environ.get("GEMINI_API_KEY_2", "")]:
    if k.strip() and k.strip() not in GEMINI_KEYS:
        GEMINI_KEYS.append(k.strip())

TG_BOT_TOKEN     = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT_ID       = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
MODEL_CHOICE     = os.environ.get("MODEL_CHOICE", "").strip() or "gemini-flash-latest"

WATCHLIST_RAW    = os.environ.get("WATCHLIST", "").strip() or "VOO,QQQ,SCHD,AAPL"
clean_tickers    = []
for t in WATCHLIST_RAW.split(","):
    cleaned = t.upper().replace("SECRET:", "").replace("SECRET", "").strip()
    if cleaned:
        clean_tickers.append(cleaned)
WATCHLIST        = clean_tickers if clean_tickers else ["VOO", "QQQ", "SCHD", "AAPL"]

def log(msg: str):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{ts}] {msg}", flush=True)

def send_telegram(message: str) -> bool:
    import requests
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        log("Telegram credentials missing or empty — alert not sent.")
        return False

    token = TG_BOT_TOKEN.strip().strip("\"'")
    if token.lower().startswith("bot"):
        token = token[3:]
    chat_id = TG_CHAT_ID.strip().strip("\"'")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, json=payload, timeout=20)
        data = resp.json()
        if data.get("ok"):
            log("Telegram alert delivered successfully.")
            return True
        else:
            err_desc = str(data.get("description", ""))
            if "not found" in err_desc.lower():
                log("Telegram API Error: 'Not Found'. Your TELEGRAM_BOT_TOKEN in GitHub Secrets is invalid or has a typo. Copy the exact HTTP API token from @BotFather.")
                return False
            if "parse" in err_desc.lower() or "entity" in err_desc.lower():
                payload.pop("parse_mode", None)
                retry_resp = requests.post(url, json=payload, timeout=20)
                if retry_resp.json().get("ok"):
                    log("Telegram alert delivered successfully (plain-text fallback).")
                    return True
            log(f"Telegram API response: {err_desc}")
            return False
    except Exception as e:
        log(f"Telegram request failed: {e}")
        return False

def analyze(ticker: str) -> str | None:
    """Calls Gemini with automatic key rotation / failover if a key is rate-limited."""
    from analyzer import analyze_stock
    for idx, key in enumerate(GEMINI_KEYS):
        try:
            result = analyze_stock(ticker, key, model_choice=MODEL_CHOICE)
            # If the result message indicates a quota exhaustion, try the backup key
            if any(term in str(result) for term in ["Quota Limit", "RESOURCE_EXHAUSTED", "Rate Limit"]):
                log(f"Key #{idx+1} reached quota limit. Rotating to next key...")
                continue
            return result
        except Exception as e:
            log(f"Key #{idx+1} error for {ticker}: {e}. Rotating to backup key...")
            continue
    return None

def is_buy_signal(text: str) -> bool:
    keywords = ["BUY", "ACCUMULATE", "DCA", "STRONG BUY", "HEAVY DCA"]
    upper = text.upper()
    return any(kw in upper for kw in keywords)

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
    log("AI Trading Signal Bot - GitHub Actions Scan Started")
    log(f"Watchlist: {', '.join(WATCHLIST)}")
    log(f"AI Model:  {MODEL_CHOICE}")
    log(f"Gemini API Keys Available: {len(GEMINI_KEYS)} (Multi-Key Failover Active)")
    log(f"Has Telegram Bot: {'Yes' if bool(TG_BOT_TOKEN) else 'NO (Missing!)'}")
    log(f"Has Chat ID:      {'Yes' if bool(TG_CHAT_ID) else 'NO (Missing!)'}")
    log("=" * 60)

    if not GEMINI_KEYS:
        log("ERROR: No GEMINI_API_KEY found in repository secrets. Aborting.")
        sys.exit(1)

    alerts_sent = 0
    scan_summary = []

    for ticker in WATCHLIST:
        log(f"Scanning {ticker}...")
        try:
            import yfinance as yf
            info = yf.Ticker(ticker).info or {}
            price = info.get("currentPrice") or info.get("regularMarketPrice", "N/A")
            price_str = f"${price:.2f}" if isinstance(price, (int, float)) else str(price)
        except Exception as e:
            log(f"Warning fetching price for {ticker}: {e}")
            price_str = "N/A"

        analysis = analyze(ticker)
        if not analysis:
            scan_summary.append(f"• {ticker}: Analysis failed")
            continue

        if is_buy_signal(analysis):
            log(f"BUY/DCA signal detected for {ticker} at {price_str}!")
            msg = format_alert(ticker, analysis, price_str)
            sent = send_telegram(msg)
            scan_summary.append(f"• {ticker}: BUY/DCA alert {'sent' if sent else 'delivery failed'}")
            if sent:
                alerts_sent += 1
        else:
            log(f"{ticker}: Neutral/Hold - no alert sent.")
            scan_summary.append(f"• {ticker}: Neutral / Hold")

        # Pause briefly between tickers to prevent burst limits
        time.sleep(3)

    # Send summary message to Telegram
    if TG_BOT_TOKEN and TG_CHAT_ID:
        summary_lines = ["📊 *Automated Market Scan Summary*", ""]
        summary_lines += scan_summary
        summary_lines += ["", f"_Scanned {len(WATCHLIST)} assets. Actionable alerts: {alerts_sent}_"]
        send_telegram("\n".join(summary_lines))

    log("=" * 60)
    log(f"Scan complete. {alerts_sent} actionable alert(s) processed.")
    log("=" * 60)

if __name__ == "__main__":
    main()
