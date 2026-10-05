#!/usr/bin/env python3
"""
Automated 24/7 Market Scanner with Dual-Key Failover.
Supports both:
1. Short-Term MT5 Trading Signals (GOLD / XAU/USD, EUR/USD, BTC, NAS100) with exact Entry, SL, TP1, TP2!
2. Long-Term Stock & ETF Investment DCA signals (VOO, QQQ, SCHD, AAPL).
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

# Default watchlist includes GOLD (XAU/USD) + Top ETFs & Stocks
WATCHLIST_RAW    = os.environ.get("WATCHLIST", "").strip() or "GOLD,VOO,QQQ,SCHD,AAPL"
clean_tickers    = []
for t in WATCHLIST_RAW.split(","):
    cleaned = t.upper().replace("SECRET:", "").replace("SECRET", "").strip()
    if cleaned:
        clean_tickers.append(cleaned)
WATCHLIST        = clean_tickers if clean_tickers else ["GOLD", "VOO", "QQQ", "SCHD", "AAPL"]

# Map short-term assets to their MT5 tickers and labels
SHORT_TERM_MAP = {
    "GOLD": ("GC=F", "GOLD (XAU/USD)"),
    "XAU": ("GC=F", "GOLD (XAU/USD)"),
    "XAU/USD": ("GC=F", "GOLD (XAU/USD)"),
    "XAUUSD": ("GC=F", "GOLD (XAU/USD)"),
    "EUR/USD": ("EURUSD=X", "EUR/USD"),
    "EURUSD": ("EURUSD=X", "EUR/USD"),
    "GBP/USD": ("GBPUSD=X", "GBP/USD"),
    "GBPUSD": ("GBPUSD=X", "GBP/USD"),
    "BTC": ("BTC-USD", "BITCOIN (BTC/USD)"),
    "BITCOIN": ("BTC-USD", "BITCOIN (BTC/USD)"),
    "OIL": ("CL=F", "CRUDE OIL (USOIL)"),
    "USOIL": ("CL=F", "CRUDE OIL (USOIL)"),
    "NAS100": ("NQ=F", "US TECH 100 (NAS100)"),
    "NQ=F": ("NQ=F", "US TECH 100 (NAS100)")
}

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
            # If Markdown parsing failed, retry as plain text immediately
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

def analyze_long_term(ticker: str) -> str | None:
    """Calls Gemini for long-term stock/ETF analysis with automatic key failover."""
    from analyzer import analyze_stock
    for idx, key in enumerate(GEMINI_KEYS):
        try:
            result = analyze_stock(ticker, key, model_choice=MODEL_CHOICE)
            if any(term in str(result) for term in ["Quota Limit", "RESOURCE_EXHAUSTED", "Rate Limit"]):
                log(f"Key #{idx+1} reached quota limit. Rotating to next key...")
                continue
            return result
        except Exception as e:
            log(f"Key #{idx+1} error for {ticker}: {e}. Rotating to backup key...")
            continue
    return None

def analyze_short_term(ticker: str, asset_name: str, timeframe: str = "1h") -> str | None:
    """Calls Gemini for short-term MT5 trade signals (Entry, SL, TP1, TP2) with key failover."""
    from short_term_analyzer import analyze_short_term_trade
    for idx, key in enumerate(GEMINI_KEYS):
        try:
            result = analyze_short_term_trade(ticker, asset_name, key, model_choice=MODEL_CHOICE, timeframe=timeframe)
            if any(term in str(result) for term in ["Rate Limit", "RESOURCE_EXHAUSTED", "Quota"]):
                log(f"Key #{idx+1} reached rate limit on MT5 scan. Rotating to next key...")
                continue
            return result
        except Exception as e:
            log(f"Key #{idx+1} error on MT5 scan for {ticker}: {e}. Rotating to backup key...")
            continue
    return None

def is_short_term_actionable(text: str) -> tuple[bool, str]:
    """Returns (is_actionable, action_type: 'BUY' | 'SELL' | 'WAIT')."""
    upper = text.upper()
    if "WAIT" in upper or "NO TRADE" in upper:
        return False, "WAIT"
    if "BUY" in upper or "LONG" in upper:
        return True, "BUY"
    if "SELL" in upper or "SHORT" in upper:
        return True, "SELL"
    return False, "WAIT"

def is_long_term_buy(text: str) -> bool:
    keywords = ["BUY", "ACCUMULATE", "DCA", "STRONG BUY", "HEAVY DCA"]
    upper = text.upper()
    return any(kw in upper for kw in keywords)

def format_mt5_card(asset_label: str, analysis: str, price: str = "N/A") -> str:
    """Formats MT5 trade card into a simplified, high-impact Telegram alert."""
    lines = []
    lines.append(f"⚡ *MT5 TRADE ALERT: {asset_label}* ⚡")
    if price != "N/A":
        lines.append(f"💵 Market Price: {price}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    clean_text = analysis.replace("**", "*").replace("### ", "").replace("## ", "")
    if len(clean_text) > 3500:
        clean_text = clean_text[:3400] + "\n\n_(View full trade card on Web App)_"

    lines.append(clean_text)
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ _Risk rule: Max 1-2% account balance. Set Stop Loss immediately on MT5._")
    return "\n".join(lines)

def format_long_term_alert(ticker: str, analysis: str, price: str = "N/A") -> str:
    header = f"🚨 *INVESTMENT SIGNAL: {ticker}* 🚨\n"
    header += f"💰 Price: {price}\n"
    header += "━━━━━━━━━━━━━━━━━━━━\n"
    body = analysis.replace("**", "*")
    if len(body) > 3500:
        body = body[:3400] + "\n\n_(View full report on web app)_"
    footer = "\n━━━━━━━━━━━━━━━━━━━━\n"
    footer += "📱 _Check your broker app for order execution._"
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

    for item in WATCHLIST:
        item_upper = item.upper().strip()
        is_short_term = item_upper in SHORT_TERM_MAP

        # ── Branch A: Short-Term MT5 Trade (GOLD, EUR/USD, BTC, etc.) ───
        if is_short_term:
            yf_ticker, asset_label = SHORT_TERM_MAP[item_upper]
            log(f"Scanning MT5 Short-Term: {asset_label} ({yf_ticker})...")
            try:
                import yfinance as yf
                data = yf.download(yf_ticker, period="2d", interval="1h", progress=False)
                price = data['Close'].iloc[-1].item() if not data.empty else "N/A"
                price_str = f"${price:.2f}" if isinstance(price, (int, float)) else str(price)
            except Exception as e:
                log(f"Price fetch note: {e}")
                price_str = "N/A"

            analysis = analyze_short_term(yf_ticker, asset_label, timeframe="1h")
            if not analysis:
                scan_summary.append(f"• {asset_label}: Analysis failed")
                continue

            actionable, action_type = is_short_term_actionable(analysis)
            if actionable:
                emoji = "🟢" if action_type == "BUY" else "🔴"
                log(f"🎯 Actionable {action_type} signal detected for {asset_label} at {price_str}!")
                msg = format_mt5_card(asset_label, analysis, price_str)
                sent = send_telegram(msg)
                scan_summary.append(f"• {asset_label}: {emoji} {action_type} trade card {'sent' if sent else 'delivery failed'}")
                if sent:
                    alerts_sent += 1
            else:
                log(f"{asset_label}: Neutral/Wait - no trade triggered.")
                scan_summary.append(f"• {asset_label}: ⚪ Wait (No Trade)")

        # ── Branch B: Long-Term Stock/ETF (VOO, QQQ, SCHD, AAPL) ────────
        else:
            log(f"Scanning Long-Term Investment: {item_upper}...")
            try:
                import yfinance as yf
                info = yf.Ticker(item_upper).info or {}
                price = info.get("currentPrice") or info.get("regularMarketPrice", "N/A")
                price_str = f"${price:.2f}" if isinstance(price, (int, float)) else str(price)
            except Exception as e:
                log(f"Price fetch note: {e}")
                price_str = "N/A"

            analysis = analyze_long_term(item_upper)
            if not analysis:
                scan_summary.append(f"• {item_upper}: Analysis failed")
                continue

            if is_long_term_buy(analysis):
                log(f"BUY/DCA signal detected for {item_upper} at {price_str}!")
                msg = format_long_term_alert(item_upper, analysis, price_str)
                sent = send_telegram(msg)
                scan_summary.append(f"• {item_upper}: 🟢 BUY/DCA alert {'sent' if sent else 'delivery failed'}")
                if sent:
                    alerts_sent += 1
            else:
                log(f"{item_upper}: Neutral/Hold - no alert sent.")
                scan_summary.append(f"• {item_upper}: 🟡 Neutral / Hold")

        # Pause between items to avoid rate limits
        time.sleep(3)

    # Send summary overview to Telegram
    if TG_BOT_TOKEN and TG_CHAT_ID:
        summary_lines = ["📊 *Automated Market Scan Summary*", ""]
        summary_lines += scan_summary
        summary_lines += ["", f"_Scanned {len(WATCHLIST)} assets. Actionable setups: {alerts_sent}_"]
        send_telegram("\n".join(summary_lines))

    log("=" * 60)
    log(f"Scan complete. {alerts_sent} actionable alert(s) processed.")
    log("=" * 60)

if __name__ == "__main__":
    main()
