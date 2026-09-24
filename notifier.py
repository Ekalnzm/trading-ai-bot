import requests

def send_telegram_message(bot_token: str, chat_id: str, message: str) -> tuple[bool, str]:
    """
    Sends a Telegram message using the Telegram Bot API.
    bot_token: The bot token from @BotFather (e.g. 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11)
    chat_id: The chat ID of the recipient (user or group/channel)
    message: The text to send (supports Markdown formatting)
    Returns (success: bool, response_text: str)
    """
    if not bot_token or not chat_id:
        return False, "Telegram Bot Token or Chat ID is missing."

    url = f"https://api.telegram.org/bot{bot_token.strip()}/sendMessage"
    payload = {
        "chat_id": chat_id.strip(),
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        data = response.json()
        if data.get("ok"):
            return True, "Telegram alert sent successfully!"
        else:
            error_desc = data.get("description", "Unknown error")
            return False, f"Telegram API Error: {error_desc}"
    except Exception as e:
        return False, f"Connection error: {str(e)}"


def get_telegram_chat_id(bot_token: str) -> tuple[bool, str]:
    """
    Fetches the chat ID from the most recent message sent to the bot.
    User must send any message to the bot first, then call this to auto-detect the chat ID.
    """
    if not bot_token:
        return False, "Bot token is missing."

    url = f"https://api.telegram.org/bot{bot_token.strip()}/getUpdates"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("ok") and data.get("result"):
            # Get the most recent message's chat ID
            latest = data["result"][-1]
            chat = latest.get("message", {}).get("chat", {})
            chat_id = str(chat.get("id", ""))
            chat_name = chat.get("first_name", "") or chat.get("title", "Unknown")
            if chat_id:
                return True, f"{chat_id}|{chat_name}"
        return False, "No messages found. Please send any message to your bot first, then try again."
    except Exception as e:
        return False, f"Error: {str(e)}"


def format_signal_for_telegram(ticker: str, signal_text: str, current_price="N/A") -> str:
    """Formats an AI analysis report into a compact Telegram-friendly alert."""
    lines = []
    lines.append(f"🚨 *LONG-TERM SIGNAL: {ticker}* 🚨")
    if current_price != "N/A":
        lines.append(f"💰 Current Price: {current_price}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    clean_text = signal_text.replace("**", "*")
    if len(clean_text) > 3500:
        clean_text = clean_text[:3400] + "\n\n_(View full report in Web App)_"

    lines.append(clean_text)
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("📱 _Check your broker app for order execution._")

    return "\n".join(lines)


def format_mt5_signal_for_telegram(asset_label: str, signal_text: str, current_price="N/A") -> str:
    """Formats an MT5 trade setup (Entry, SL, TP1, TP2) cleanly for Telegram."""
    lines = []
    lines.append(f"⚡ *MT5 TRADE SIGNAL: {asset_label}* ⚡")
    if current_price != "N/A":
        lines.append(f"💵 Market Price: {current_price}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    clean_text = signal_text.replace("**", "*").replace("### ", "").replace("## ", "")
    if len(clean_text) > 3500:
        clean_text = clean_text[:3400] + "\n\n_(View full trade card in Web App)_"

    lines.append(clean_text)
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ _Risk rule: Max 1-2% account balance. Set Stop Loss immediately on MT5._")
    return "\n".join(lines)
