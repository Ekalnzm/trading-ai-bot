import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULT_CONFIG = {
    "gemini_api_key": "",
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "model_choice": "gemini-flash-latest",
    "watchlist": ["VOO", "QQQ", "SCHD", "AAPL"],
    "scan_interval_hours": 12,
    "auto_scan_enabled": False,
    "last_scanned": {},
    "admin_password": "admin123"
}

def load_config() -> dict:
    """Loads configuration from JSON file or creates defaults, with fallback to Streamlit secrets/env."""
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    cfg[k] = data.get(k, v)
        except Exception:
            pass

    # Fallback to Streamlit secrets (for Streamlit Community Cloud) or Environment Variables
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            if not cfg.get("gemini_api_key") and "GEMINI_API_KEY" in st.secrets:
                cfg["gemini_api_key"] = st.secrets["GEMINI_API_KEY"]
            if not cfg.get("telegram_bot_token") and "TELEGRAM_BOT_TOKEN" in st.secrets:
                cfg["telegram_bot_token"] = st.secrets["TELEGRAM_BOT_TOKEN"]
            if not cfg.get("telegram_chat_id") and "TELEGRAM_CHAT_ID" in st.secrets:
                cfg["telegram_chat_id"] = st.secrets["TELEGRAM_CHAT_ID"]
            if "ADMIN_PASSWORD" in st.secrets:
                cfg["admin_password"] = st.secrets["ADMIN_PASSWORD"]
    except Exception:
        pass

    return cfg

def save_config(cfg: dict) -> bool:
    """Saves configuration to JSON file."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        return True
    except Exception:
        return False
