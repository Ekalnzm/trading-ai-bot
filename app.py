import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import plotly.graph_objects as go
from analyzer import analyze_stock, get_stock_data
from short_term_analyzer import (
    analyze_short_term_trade,
    get_short_term_data,
    MT5_ASSET_MAP
)
from config import load_config, save_config
from notifier import (
    send_telegram_message,
    get_telegram_chat_id,
    get_bot_info,
    format_signal_for_telegram,
    format_mt5_signal_for_telegram
)
from scanner import (
    start_background_scanner,
    stop_background_scanner,
    is_scanner_running,
    run_single_scan
)

st.set_page_config(page_title="AI Trading Signals & Real-Time Terminal", page_icon="📈", layout="wide")

# Load persistent user settings
cfg = load_config()

# Ensure background scanner keeps running if enabled
if cfg.get("auto_scan_enabled", False) and not is_scanner_running():
    start_background_scanner()

# ----------------- TRADINGVIEW WIDGET HELPERS -----------------
def render_ticker_tape(theme="dark"):
    """Embeds a live tick-by-tick scrolling market ticker tape."""
    html_tape = f"""
    <!-- TradingView Widget BEGIN -->
    <div class="tradingview-widget-container" style="margin-bottom: 12px;">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>
      {{
      "symbols": [
        {{"proName": "FOREXCOM:XAUUSD", "title": "Gold (XAU/USD)"}},
        {{"proName": "FX_IDC:EURUSD", "title": "EUR/USD"}},
        {{"proName": "FX_IDC:GBPUSD", "title": "GBP/USD"}},
        {{"proName": "TVC:USOIL", "title": "Crude Oil (WTI)"}},
        {{"proName": "BINANCE:BTCUSDT", "title": "Bitcoin"}},
        {{"proName": "AMEX:SPY", "title": "S&P 500"}},
        {{"proName": "NASDAQ:QQQ", "title": "Nasdaq 100"}},
        {{"proName": "NASDAQ:NVDA", "title": "NVIDIA"}},
        {{"proName": "NASDAQ:TSLA", "title": "Tesla"}},
        {{"proName": "NASDAQ:AAPL", "title": "Apple"}}
      ],
      "showSymbolLogo": true,
      "isTransparent": false,
      "displayMode": "adaptive",
      "colorTheme": "{theme}",
      "locale": "en"
    }}
      </script>
    </div>
    <!-- TradingView Widget END -->
    """
    components.html(html_tape, height=75)

def render_tradingview_chart(symbol: str, interval: str = "60", theme: str = "dark", height: int = 500, container_id: str = "tv_chart"):
    """Embeds the official TradingView Advanced Real-Time Chart widget."""
    tf_map = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240", "1d": "D", "1D": "D"}
    tv_interval = tf_map.get(interval, "60")
    
    html_chart = f"""
    <!-- TradingView Widget BEGIN -->
    <div class="tradingview-widget-container" style="height: {height}px; width: 100%;">
      <div id="{container_id}" style="height: {height}px; width: 100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
        "autosize": true,
        "symbol": "{symbol}",
        "interval": "{tv_interval}",
        "timezone": "Etc/UTC",
        "theme": "{theme}",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "{'#131722' if theme == 'dark' else '#f1f3f6'}",
        "enable_publishing": false,
        "hide_side_toolbar": false,
        "allow_symbol_change": true,
        "container_id": "{container_id}"
      }}
      );
      </script>
    </div>
    <!-- TradingView Widget END -->
    """
    components.html(html_chart, height=height + 15)

def get_tv_symbol_for_stock(ticker: str) -> str:
    """Converts a standard ticker to TradingView exchange format."""
    t = ticker.upper().strip()
    if t in ["VOO", "SPY", "SCHD", "IVV"]:
        return f"AMEX:{t}"
    elif t in ["QQQ", "AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "META", "AMD"]:
        return f"NASDAQ:{t}"
    elif t.endswith(".HK"):
        code = t.replace(".HK", "").lstrip("0")
        return f"HKEX:{code}"
    elif t.endswith(".KL"):
        return f"MYX:{t.replace('.KL', '')}"
    elif t.endswith(".SI"):
        return f"SGX:{t.replace('.SI', '')}"
    return t

# ----------------- SIDEBAR CONFIGURATION -----------------
st.session_state.setdefault("is_admin", False)

# ----------------- SIDEBAR CONFIGURATION (DUAL-VIEW) -----------------
with st.sidebar:
    # ------------------ ADMIN MODE ------------------
    if st.session_state["is_admin"]:
        st.header("👑 Admin Control Center")
        if st.button("🚪 Log Out of Admin", use_container_width=True):
            st.session_state["is_admin"] = False
            st.rerun()
            
        st.divider()
        st.subheader("🧠 Master Gemini AI Configuration")
        current_master_key = cfg.get("gemini_api_key", "").strip()
        if current_master_key:
            masked_key = current_master_key[:6] + "..." + current_master_key[-4:]
            st.success(f"Master Key Active: `{masked_key}`")
        else:
            st.error("No master Gemini API key set!")

        new_key = st.text_input("Update Master Gemini Key", type="password", placeholder="Paste new key")
        
        available_models = ["gemini-flash-latest", "gemini-3.8-flash", "gemini-3.6-flash"]
        saved_model = cfg.get("model_choice", "gemini-flash-latest")
        default_model_idx = available_models.index(saved_model) if saved_model in available_models else 0
        admin_model_choice = st.selectbox("Default AI Model", options=available_models, index=default_model_idx)

        if st.button("💾 Save AI Settings", use_container_width=True):
            if new_key.strip():
                cfg["gemini_api_key"] = new_key.strip()
            cfg["model_choice"] = admin_model_choice
            save_config(cfg)
            st.success("Admin AI settings saved!")
            st.rerun()

        st.divider()
        st.subheader("📬 Master Telegram Alert Destination")
        admin_tg_token = st.text_input("Bot Token (@BotFather)", value=cfg.get("telegram_bot_token", ""), type="password")
        admin_tg_chat_id = st.text_input("Chat ID", value=cfg.get("telegram_chat_id", ""), placeholder="e.g. 123456789")
        
        if st.button("🔍 Auto-Detect My Chat ID", use_container_width=True):
            if admin_tg_token:
                with st.spinner("Checking for messages sent to your bot..."):
                    ok, result = get_telegram_chat_id(admin_tg_token.strip())
                    if ok:
                        detected_id, detected_name = result.split("|", 1)
                        cfg["telegram_chat_id"] = detected_id
                        save_config(cfg)
                        st.success(f"Chat ID detected: `{detected_id}` ({detected_name})")
                        st.rerun()
                    else:
                        st.error(result)
            else:
                st.error("Enter your Bot Token first.")

        col_adm_test, col_adm_save = st.columns(2)
        if col_adm_test.button("🧪 Test Alert", use_container_width=True):
            if admin_tg_token and admin_tg_chat_id:
                with st.spinner("Sending Telegram test..."):
                    ok, resp = send_telegram_message(admin_tg_token, admin_tg_chat_id, "🔔 *Admin Alert Test:* Telegram connection verified! ✅")
                    if ok:
                        st.success("Test alert delivered to Telegram!")
                    else:
                        st.error(resp)
            else:
                st.error("Enter both Bot Token & Chat ID.")

        if col_adm_save.button("💾 Save Telegram", use_container_width=True):
            cfg["telegram_bot_token"] = admin_tg_token.strip()
            cfg["telegram_chat_id"] = admin_tg_chat_id.strip()
            save_config(cfg)
            st.success("Telegram settings saved!")

        st.divider()
        st.subheader("🤖 Automated Background Scanner")
        scanner_active = is_scanner_running()

        if scanner_active:
            st.success("🟢 Scanner: **MONITORING ACTIVE**")
            if st.button("⏹️ Stop Automated Alerts", use_container_width=True):
                stop_background_scanner()
                st.rerun()
        else:
            st.info("⚪ Scanner: **STOPPED**")
            if st.button("▶️ Start Automated Alerts", type="primary", use_container_width=True):
                start_background_scanner()
                st.rerun()

        # Watchlist editor
        raw_watchlist = st.text_input("Watchlist (comma-separated)", value=", ".join(cfg.get("watchlist", ["VOO", "QQQ", "SCHD", "AAPL"])))
        interval = st.selectbox("Scan Frequency", options=[4, 8, 12, 24], index=[4, 8, 12, 24].index(cfg.get("scan_interval_hours", 12)), format_func=lambda x: f"Every {x} hours")

        if st.button("Update Watchlist & Frequency", use_container_width=True):
            cfg["watchlist"] = [t.strip().upper() for t in raw_watchlist.split(",") if t.strip()]
            cfg["scan_interval_hours"] = interval
            save_config(cfg)
            st.success("Watchlist updated!")

        if st.button("⚡ Run Scan Now", use_container_width=True):
            with st.spinner("Scanning now..."):
                results = run_single_scan()
                st.write(results)
                st.rerun()

        with st.expander("📜 Scanner Activity Log"):
            logs = cfg.get("scanner_logs", [])
            for l in logs[:15]:
                st.caption(l)

        st.divider()
        st.subheader("🔑 Change Admin Password")
        new_pass = st.text_input("New Admin Password", type="password")
        if st.button("Update Password", use_container_width=True):
            if new_pass.strip():
                cfg["admin_password"] = new_pass.strip()
                save_config(cfg)
                st.success("Admin password updated!")

    # ------------------ PUBLIC VISITOR MODE ------------------
    else:
        st.header("⚙️ Terminal Settings")
        
        theme = st.selectbox(
            "🎨 Chart & Terminal Theme",
            options=["dark", "light"],
            index=0,
            format_func=lambda x: "🌙 Dark Mode (Pro Desk)" if x == "dark" else "☀️ Light Mode"
        )

        auto_refresh_signals = st.checkbox(
            "🔴 Live Auto-Refresh (Every 30s)",
            value=False,
            help="Periodically updates technical metrics and AI signals."
        )

        st.divider()
        st.header("🧠 AI Trading Engine")
        st.success("🤖 **AI Status: Online & Automated**")
        st.caption("Powered by Google Gemini Flash. Signals and risk calculations are processed automatically without exposing any backend keys.")

        model_choice = cfg.get("model_choice", "gemini-flash-latest")

        st.divider()
        st.header("📬 Receive Alerts on Telegram")
        st.caption("Get AI trade signals delivered directly to your Telegram:")

        master_tg_token = cfg.get("telegram_bot_token", "").strip()

        if master_tg_token:
            bot_info = get_bot_info(master_tg_token)
            bot_username = bot_info.get("username", "")
            bot_display = f"@{bot_username}" if bot_username else "Our Official Trading Bot"
            bot_link = f"https://t.me/{bot_username}" if bot_username else "#"

            st.markdown(f"""
            **How to connect in 10 seconds:**
            1. Open our bot on Telegram: [👉 **{bot_display}**]({bot_link})
            2. Tap **START** in Telegram
            3. Click the button below to connect!
            """)

            connected_chat = st.session_state.get("visitor_tg_chat", "")
            if connected_chat:
                st.success(f"✅ **Connected to Telegram!** (ID: `{connected_chat}`)")

            col_detect, col_test = st.columns(2)
            if col_detect.button("🔍 Connect / Detect", use_container_width=True):
                with st.spinner("Connecting to your Telegram..."):
                    ok, result = get_telegram_chat_id(master_tg_token)
                    if ok:
                        detected_id, detected_name = result.split("|", 1)
                        st.session_state["visitor_tg_chat"] = detected_id
                        st.success(f"Connected: {detected_name} (`{detected_id}`)!")
                        st.rerun()
                    else:
                        st.error("Please click the bot link above and tap START first, then click here!")

            if col_test.button("🧪 Test Alert", use_container_width=True):
                target_chat = st.session_state.get("visitor_tg_chat", "")
                if not target_chat:
                    st.error("Tap START on the bot and click 'Connect / Detect' first!")
                else:
                    with st.spinner("Sending test alert..."):
                        ok, resp = send_telegram_message(
                            master_tg_token,
                            target_chat,
                            "🔔 *Welcome to AI Trading Signals!* Your Telegram is successfully connected. You will now receive live buy/sell trade alerts! 📈"
                        )
                        if ok:
                            st.success("Test alert sent! Check your Telegram.")
                        else:
                            st.error(f"Error: {resp}")

            with st.expander("⚙️ Manual Chat ID (Optional)"):
                manual_id = st.text_input("Enter Chat ID directly", value=st.session_state.get("visitor_tg_chat", ""), placeholder="e.g. 123456789")
                if st.button("Save Chat ID", key="save_manual_chat"):
                    st.session_state["visitor_tg_chat"] = manual_id.strip()
                    st.success("Chat ID set!")
                    st.rerun()
        else:
            st.info("ℹ️ Telegram bot is currently being initialized by Admin. Check back shortly!")

        # Discrete Admin Login at bottom
        st.divider()
        with st.expander("🔐 Admin Login"):
            admin_input = st.text_input("Admin Password", type="password", placeholder="Enter password")
            if st.button("Log In as Admin", use_container_width=True):
                correct_pass = cfg.get("admin_password", "admin123")
                if admin_input == correct_pass:
                    st.session_state["is_admin"] = True
                    st.success("Access granted!")
                    st.rerun()
                else:
                    st.error("Incorrect password.")

# Set active credentials for analysis
active_gemini_key = cfg.get("gemini_api_key", "").strip()
active_model_choice = cfg.get("model_choice", "gemini-flash-latest")
theme = "dark" if "theme" not in locals() else theme
auto_refresh_signals = False if "auto_refresh_signals" not in locals() else auto_refresh_signals
active_tg_token = cfg.get("telegram_bot_token", "").strip()
active_tg_chat = st.session_state.get("visitor_tg_chat", cfg.get("telegram_chat_id", "")).strip()

# ----------------- MAIN HEADER & LIVE TICKER TAPE -----------------
st.title("📈 AI Trading Terminal: Live Real-Time Watching")
st.markdown("Real-time streaming charts, breaking news catalysts, and AI-driven signals with explicit Stop-Loss & Take-Profit targets.")

# Render Live Ticker Tape across the top
render_ticker_tape(theme=theme)

# Auto-refresh JS if enabled
if auto_refresh_signals:
    components.html("""
    <script>
    setTimeout(function() {
        window.parent.location.reload();
    }, 30000);
    </script>
    """, height=0)

# ----------------- MAIN DUAL-TAB INTERFACE -----------------
tab_longterm, tab_shortterm = st.tabs([
    "🏛️ Long-Term Moomoo Investment (DCA & Fundamentals)",
    "⚡ Short-Term MT5 Trading (News + Scalp + TP/SL)"
])

# ====================================================================
# TAB 1: LONG-TERM MOOMOO INVESTMENT
# ====================================================================
with tab_longterm:
    st.subheader("🔍 Long-Term Stock & ETF Analysis (1-5 Year Horizon)")

    # Preset buttons
    st.caption("Quick Presets (Popular on Moomoo):")
    cols = st.columns(6)
    preset_lt = None
    if cols[0].button("VOO", key="lt_voo"):
        preset_lt = "VOO"
    if cols[1].button("QQQ", key="lt_qqq"):
        preset_lt = "QQQ"
    if cols[2].button("SCHD", key="lt_schd"):
        preset_lt = "SCHD"
    if cols[3].button("AAPL", key="lt_aapl"):
        preset_lt = "AAPL"
    if cols[4].button("NVDA", key="lt_nvda"):
        preset_lt = "NVDA"
    if cols[5].button("MSFT", key="lt_msft"):
        preset_lt = "MSFT"

    default_ticker_lt = preset_lt if preset_lt else st.session_state.get("lt_ticker", "VOO")
    col_input, col_chart_opt, col_btn = st.columns([2, 1, 1])
    with col_input:
        ticker_lt = st.text_input("Enter Stock / ETF Symbol", value=default_ticker_lt, key="input_lt").strip().upper()
        st.session_state["lt_ticker"] = ticker_lt

    with col_chart_opt:
        chart_mode_lt = st.selectbox(
            "Chart Engine",
            options=["🔴 Live TradingView (Streaming)", "📊 Static Plotly Candlesticks"],
            index=0,
            key="chart_mode_lt_select"
        )

    with col_btn:
        st.write("")
        analyze_lt_btn = st.button("🚀 Analyze Fundamentals", type="primary", use_container_width=True, key="btn_lt")

    # Display chart & metrics
    if ticker_lt:
        try:
            t = yf.Ticker(ticker_lt)
            data_lt = t.history(period="1y")
            info_lt = t.info or {}
            
            if not data_lt.empty:
                name = info_lt.get("shortName") or info_lt.get("longName") or ticker_lt
                quote_type = info_lt.get("quoteType", "EQUITY")
                current_price = info_lt.get("currentPrice") or info_lt.get("regularMarketPrice") or data_lt['Close'].iloc[-1]
                prev_close = info_lt.get("previousClose") or data_lt['Close'].iloc[-2] if len(data_lt) > 1 else current_price
                price_change = current_price - prev_close if (current_price and prev_close) else 0
                pct_change = (price_change / prev_close) * 100 if prev_close else 0

                st.markdown(f"### {name} (`{ticker_lt}`) — {quote_type}")
                
                # Key metric cards
                m1, m2, m3, m4 = st.columns(4)
                currency = info_lt.get("currency", "$")
                price_display = f"{currency}{current_price:.2f}" if isinstance(current_price, (int, float)) else f"{currency}{current_price}"
                m1.metric("Current Price", price_display, f"{pct_change:+.2f}%")
                
                if quote_type == "ETF":
                    expense_ratio = info_lt.get("netExpenseRatio", info_lt.get("annualReportExpenseRatio", "N/A"))
                    m2.metric("Expense Ratio", f"{expense_ratio:.2%}" if isinstance(expense_ratio, float) else f"{expense_ratio}")
                    div_yield = info_lt.get("yield", info_lt.get("dividendYield", "N/A"))
                    m3.metric("Yield", f"{div_yield:.2%}" if isinstance(div_yield, float) else f"{div_yield}")
                    m4.metric("52W High / Low", f"{info_lt.get('fiftyTwoWeekHigh', 'N/A')} / {info_lt.get('fiftyTwoWeekLow', 'N/A')}")
                else:
                    pe = info_lt.get("trailingPE", "N/A")
                    m2.metric("Trailing P/E", f"{pe:.2f}" if isinstance(pe, (int, float)) else f"{pe}")
                    pb = info_lt.get("priceToBook", "N/A")
                    m3.metric("P/B Ratio", f"{pb:.2f}" if isinstance(pb, (int, float)) else f"{pb}")
                    div_yield = info_lt.get("dividendYield", "N/A")
                    m4.metric("Div Yield", f"{div_yield:.2%}" if isinstance(div_yield, float) else f"{div_yield}")

                # Choose between Live Streaming TradingView or Plotly Candlestick
                if "Live TradingView" in chart_mode_lt:
                    tv_stock_sym = get_tv_symbol_for_stock(ticker_lt)
                    render_tradingview_chart(tv_stock_sym, interval="D", theme=theme, height=480, container_id="tv_lt_chart")
                else:
                    fig_lt = go.Figure(data=[go.Candlestick(
                        x=data_lt.index,
                        open=data_lt['Open'],
                        high=data_lt['High'],
                        low=data_lt['Low'],
                        close=data_lt['Close'],
                        name="Price"
                    )])
                    fig_lt.update_layout(
                        xaxis_rangeslider_visible=False,
                        margin=dict(l=0, r=0, t=10, b=10),
                        height=360,
                        template="plotly_dark" if theme == "dark" else "plotly_white"
                    )
                    st.plotly_chart(fig_lt, use_container_width=True)
            else:
                st.warning(f"⚠️ Could not load data for **'{ticker_lt}'**.")
        except Exception as e:
            st.error(f"Error fetching data: {e}")

    # Handle Long-Term Analysis
    if analyze_lt_btn:
        if not active_gemini_key:
            st.error("🔑 AI Engine is offline. (Admin: Please configure the master Gemini key).")
        elif not ticker_lt:
            st.error("Please enter a stock ticker.")
        else:
            with st.spinner(f"Analyzing {ticker_lt} fundamentals and news..."):
                result_lt = analyze_stock(ticker_lt, active_gemini_key, model_choice=active_model_choice)
                st.session_state[f"last_analysis_{ticker_lt}"] = result_lt

    if f"last_analysis_{ticker_lt}" in st.session_state:
        res = st.session_state[f"last_analysis_{ticker_lt}"]
        st.markdown("---")
        col_hdr, col_btn_fwd = st.columns([3, 1])
        with col_hdr:
            st.subheader(f"🤖 Long-Term Investment Verdict: {ticker_lt}")
        with col_btn_fwd:
            if st.button("📬 Forward to Telegram", key="fwd_lt", use_container_width=True):
                if not active_tg_token or not active_tg_chat:
                    st.error("Set up your Telegram Bot Token & Chat ID in the sidebar first!")
                else:
                    tg_msg = format_signal_for_telegram(ticker_lt, res)
                    ok, msg = send_telegram_message(active_tg_token, active_tg_chat, tg_msg)
                    if ok:
                        st.success("Forwarded to your Telegram! 📬")
                    else:
                        st.error(f"Telegram Error: {msg}")
        st.markdown(res)

# ====================================================================
# TAB 2: SHORT-TERM MT5 TRADING (NEWS + SCALP + TP/SL)
# ====================================================================
with tab_shortterm:
    st.subheader("⚡ Live MT5 Trading Terminal (Zero-Lag Streaming + News + TP/SL)")
    st.markdown("Watch tick-by-tick market action with live candlesticks and generate AI-calculated **Entry, Stop-Loss (SL), and Take-Profit (TP1/TP2)** levels.")

    # MT5 Asset Selection Presets
    st.caption("Quick MT5 Asset Presets:")
    col_presets = st.columns(len(MT5_ASSET_MAP))
    selected_mt5_label = st.session_state.get("mt5_label", "GOLD (XAU/USD)")
    
    for idx, (label, item) in enumerate(MT5_ASSET_MAP.items()):
        if col_presets[idx].button(label.split(" ")[0], key=f"mt5_btn_{idx}"):
            selected_mt5_label = label
            st.session_state["mt5_label"] = label

    # Choose Asset, Timeframe, Chart Mode
    col_a, col_tf, col_chart_st, col_go = st.columns([2, 1, 1, 1])
    with col_a:
        asset_options = list(MT5_ASSET_MAP.keys())
        default_idx = asset_options.index(selected_mt5_label) if selected_mt5_label in asset_options else 0
        asset_choice = st.selectbox("Select MT5 Asset", options=asset_options, index=default_idx)
        selected_asset_info = MT5_ASSET_MAP[asset_choice]
        mt5_ticker = selected_asset_info["ticker"]
        mt5_tv_symbol = selected_asset_info.get("tv_symbol", "OANDA:XAUUSD")
        mt5_name = selected_asset_info["name"]

    with col_tf:
        timeframe = st.selectbox(
            "Timeframe",
            options=["1m", "5m", "15m", "1h", "4h", "1d"],
            index=3,
            help="1m/5m/15m for scalping, 1h for day trading, 4h/1d for swing trading."
        )

    with col_chart_st:
        chart_mode_st = st.selectbox(
            "Chart Engine",
            options=["🔴 Live Streaming (TradingView)", "📈 Custom EMA & Indicators"],
            index=0,
            key="chart_mode_st_select"
        )

    with col_go:
        st.write("")
        st.write("")
        run_mt5_btn = st.button("⚡ Generate MT5 Signal", type="primary", use_container_width=True)

    # Fetch Short-Term Technicals & Display Metrics
    try:
        api_interval = "15m" if timeframe in ["1m", "5m", "15m"] else ("1h" if timeframe in ["1h", "4h"] else "1d")
        technicals, df_st = get_short_term_data(mt5_ticker, interval=api_interval, period="1mo" if api_interval == "1h" else "5d")
        if technicals and "error" not in technicals:
            curr_price = technicals.get("current_price", "N/A")
            rsi_val = technicals.get("rsi", "N/A")
            atr_val = technicals.get("atr", "N/A")
            ema9 = technicals.get("ema9", "N/A")
            ema21 = technicals.get("ema21", "N/A")
            high_24 = technicals.get("recent_high", "N/A")
            low_24 = technicals.get("recent_low", "N/A")

            # Technical Cards
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Live Market Price", f"{curr_price}")
            
            # RSI with condition
            if isinstance(rsi_val, (int, float)):
                rsi_state = "Overbought ⚠️" if rsi_val > 70 else ("Oversold 🟢" if rsi_val < 30 else "Neutral")
                c2.metric("RSI (14)", f"{rsi_val}", rsi_state)
            else:
                c2.metric("RSI (14)", f"{rsi_val}")

            c3.metric("ATR (14 - Volatility)", f"{atr_val}", "Used for SL Buffer")
            c4.metric("Recent Range (High / Low)", f"{high_24} / {low_24}")
    except Exception as e:
        st.caption(f"Note: Technical metrics background loading ({e})")

    # Render Chosen Chart: Live TradingView or Custom Plotly
    if "Live Streaming" in chart_mode_st:
        render_tradingview_chart(mt5_tv_symbol, interval=timeframe, theme=theme, height=520, container_id="tv_mt5_chart")
    else:
        if df_st is not None and not df_st.empty:
            fig_st = go.Figure()
            fig_st.add_trace(go.Candlestick(
                x=df_st.index,
                open=df_st['Open'],
                high=df_st['High'],
                low=df_st['Low'],
                close=df_st['Close'],
                name="Price"
            ))
            if 'EMA9' in df_st.columns:
                fig_st.add_trace(go.Scatter(x=df_st.index, y=df_st['EMA9'], mode='lines', line=dict(color='#2962FF', width=1.5), name="EMA 9 (Fast)"))
            if 'EMA21' in df_st.columns:
                fig_st.add_trace(go.Scatter(x=df_st.index, y=df_st['EMA21'], mode='lines', line=dict(color='#FF6D00', width=1.5), name="EMA 21 (Trend)"))

            fig_st.update_layout(
                xaxis_rangeslider_visible=False,
                margin=dict(l=0, r=0, t=10, b=10),
                height=420,
                template="plotly_dark" if theme == "dark" else "plotly_white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_st, use_container_width=True)

    # Generate MT5 Trade Signal
    if run_mt5_btn:
        if not active_gemini_key:
            st.error("🔑 AI Engine is offline. (Admin: Please configure the master Gemini key).")
        else:
            with st.spinner(f"Analyzing {asset_choice} live action, news, RSI, ATR, and momentum on {timeframe} timeframe..."):
                mt5_result = analyze_short_term_trade(
                    mt5_ticker,
                    asset_choice,
                    active_gemini_key,
                    model_choice=active_model_choice,
                    timeframe=timeframe
                )
                st.session_state[f"last_mt5_{mt5_ticker}"] = mt5_result

    if f"last_mt5_{mt5_ticker}" in st.session_state:
        res_mt5 = st.session_state[f"last_mt5_{mt5_ticker}"]
        st.markdown("---")
        col_hdr, col_btn_fwd = st.columns([3, 1])
        with col_hdr:
            st.subheader(f"🎯 Actionable MT5 Trade Setup: {asset_choice}")
        with col_btn_fwd:
            if st.button("📬 Forward Setup to Telegram", key="fwd_mt5", use_container_width=True):
                if not active_tg_token or not active_tg_chat:
                    st.error("Set up your Telegram Bot Token & Chat ID in the sidebar first!")
                else:
                    live_p = technicals.get("current_price", "N/A") if 'technicals' in locals() and technicals else "N/A"
                    tg_mt5_msg = format_mt5_signal_for_telegram(asset_choice, res_mt5, current_price=str(live_p))
                    ok, msg = send_telegram_message(active_tg_token, active_tg_chat, tg_mt5_msg)
                    if ok:
                        st.success("Trade setup forwarded to your Telegram! 📬")
                    else:
                        st.error(f"Telegram Error: {msg}")
        
        st.markdown(res_mt5)
