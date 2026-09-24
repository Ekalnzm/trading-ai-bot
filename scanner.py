import time
import threading
import datetime
from config import load_config, save_config
from analyzer import analyze_stock, get_stock_data
from notifier import send_telegram_message, format_signal_for_telegram

_scanner_thread = None
_scanner_running = False

def log_scan_event(message: str):
    """Appends a timestamped log entry to scanner logs."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {message}"
    cfg = load_config()
    logs = cfg.get("scanner_logs", [])
    logs.insert(0, entry)
    cfg["scanner_logs"] = logs[:50]  # keep latest 50 logs
    save_config(cfg)

def run_single_scan() -> list[str]:
    """Runs a single pass across the watchlist and sends Telegram alerts for actionable signals."""
    cfg = load_config()
    gemini_key = cfg.get("gemini_api_key", "").strip()
    tg_bot_token = cfg.get("telegram_bot_token", "").strip()
    tg_chat_id = cfg.get("telegram_chat_id", "").strip()
    watchlist = cfg.get("watchlist", [])
    model_choice = cfg.get("model_choice", "gemini-flash-latest")
    last_scanned = cfg.get("last_scanned", {})

    if not gemini_key:
        log_scan_event("Scan aborted: Gemini API key not configured.")
        return ["Gemini API key is missing."]

    has_telegram = bool(tg_bot_token and tg_chat_id)
    results = []
    now = time.time()

    log_scan_event(f"Starting automated scan on {len(watchlist)} assets: {', '.join(watchlist)}")

    for ticker in watchlist:
        ticker = ticker.strip().upper()
        if not ticker:
            continue

        # Throttle check: Don't re-alert the same ticker within 18 hours
        last_time = last_scanned.get(ticker, 0)
        if now - last_time < 18 * 3600:
            log_scan_event(f"Skipping {ticker} (recently scanned within 18h).")
            continue

        try:
            # 1. Quick fundamental check
            fundamentals, hist = get_stock_data(ticker)
            if "error" in fundamentals:
                log_scan_event(f"Error checking {ticker}: {fundamentals['error']}")
                continue

            current_price = fundamentals.get("Current Price", "N/A")
            currency = "$"
            price_str = f"{currency}{current_price:.2f}" if isinstance(current_price, (int, float)) else f"{current_price}"

            # 2. Run AI Analysis
            analysis = analyze_stock(ticker, gemini_key, model_choice=model_choice)
            
            # 3. Check if verdict is actionable (BUY or ACCUMULATE or DCA)
            is_buy_signal = any(kw in analysis.upper() for kw in ["**BUY**", "**ACCUMULATE**", "**DCA**", "BUY SIGNAL", "STRONG BUY"])
            
            if is_buy_signal:
                log_scan_event(f"🎯 Actionable BUY/DCA signal detected for {ticker} at {price_str}!")
                results.append(f"{ticker}: BUY/ACCUMULATE signal detected.")

                if has_telegram:
                    tg_text = format_signal_for_telegram(ticker, analysis, current_price=price_str)
                    success, msg = send_telegram_message(tg_bot_token, tg_chat_id, tg_text)
                    if success:
                        log_scan_event(f"✅ Telegram alert delivered for {ticker}.")
                    else:
                        log_scan_event(f"❌ Failed to deliver Telegram alert for {ticker}: {msg}")
                else:
                    log_scan_event(f"ℹ️ Telegram not configured, signal saved to app log only.")

                # Update last scanned timestamp only on actionable alert
                last_scanned[ticker] = now
            else:
                log_scan_event(f"Neutral/Hold for {ticker}. No alert sent.")
                results.append(f"{ticker}: Neutral / Hold.")

        except Exception as e:
            log_scan_event(f"Exception scanning {ticker}: {str(e)}")

    cfg["last_scanned"] = last_scanned
    save_config(cfg)
    return results

def _background_worker():
    global _scanner_running
    log_scan_event("Automated background scanner thread started.")
    while _scanner_running:
        cfg = load_config()
        if not cfg.get("auto_scan_enabled", False):
            break

        run_single_scan()

        # Sleep interval in hours (default 12 hours)
        interval_hours = max(1, cfg.get("scan_interval_hours", 12))
        sleep_seconds = interval_hours * 3600
        
        # Check every 10 seconds if we should stop early
        elapsed = 0
        while elapsed < sleep_seconds and _scanner_running:
            time.sleep(10)
            elapsed += 10
            # Reload to see if user disabled it mid-sleep
            if not load_config().get("auto_scan_enabled", False):
                _scanner_running = False
                break

    _scanner_running = False
    log_scan_event("Automated background scanner thread stopped.")

def start_background_scanner():
    """Starts the background monitoring loop in a daemon thread."""
    global _scanner_thread, _scanner_running
    if _scanner_running and _scanner_thread and _scanner_thread.is_alive():
        return True, "Scanner is already running."

    cfg = load_config()
    cfg["auto_scan_enabled"] = True
    save_config(cfg)

    _scanner_running = True
    _scanner_thread = threading.Thread(target=_background_worker, daemon=True)
    _scanner_thread.start()
    return True, "Automated background scanner started."

def stop_background_scanner():
    """Stops the background monitoring loop."""
    global _scanner_running
    cfg = load_config()
    cfg["auto_scan_enabled"] = False
    save_config(cfg)
    _scanner_running = False
    return True, "Scanner stopped."

def is_scanner_running() -> bool:
    global _scanner_running, _scanner_thread
    return _scanner_running and (_scanner_thread is not None and _scanner_thread.is_alive())
