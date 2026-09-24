import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULT_CONFIG = {
    "gemini_api_key": "",
    "whatsapp_phone": "",
    "whatsapp_api_key": "",
    "model_choice": "gemini-flash-latest",
    "watchlist": ["VOO", "QQQ", "SCHD", "AAPL"],
    "scan_interval_hours": 12,
    "auto_scan_enabled": False,
    "last_scanned": {}
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
            if not cfg.get("whatsapp_phone") and "WHATSAPP_PHONE" in st.secrets:
                cfg["whatsapp_phone"] = st.secrets["WHATSAPP_PHONE"]
            if not cfg.get("whatsapp_api_key") and "WHATSAPP_API_KEY" in st.secrets:
                cfg["whatsapp_api_key"] = st.secrets["WHATSAPP_API_KEY"]
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
