import requests
import urllib.parse

def send_whatsapp_message(phone: str, api_key: str, message: str) -> tuple[bool, str]:
    """
    Sends a WhatsApp message using the free CallMeBot API.
    phone: Phone number with country code, e.g. +60123456789 or +14155552671
    api_key: The API key received from CallMeBot on WhatsApp
    message: The text to send
    Returns (success: bool, response_text: str)
    """
    if not phone or not api_key:
        return False, "Phone number or CallMeBot API key is missing."

    # Format phone number: remove spaces, dashes, parentheses
    clean_phone = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if clean_phone.startswith("+"):
        clean_phone = clean_phone[1:]  # CallMeBot expects without '+' or URL encoded

    # Ensure message is URL-encoded
    encoded_message = urllib.parse.quote(message)
    url = f"https://api.callmebot.com/whatsapp.php?phone={clean_phone}&text={encoded_message}&apikey={api_key}"

    try:
        response = requests.get(url, timeout=15)
        # CallMeBot returns HTTP 200 with text like "Message queued" or "Message sent"
        if response.status_code == 200 and ("queued" in response.text.lower() or "success" in response.text.lower() or "sent" in response.text.lower()):
            return True, "WhatsApp alert sent successfully!"
        elif response.status_code == 200:
            return True, f"Server responded: {response.text.strip()}"
        else:
            return False, f"Failed (HTTP {response.status_code}): {response.text.strip()}"
    except Exception as e:
        return False, f"Connection error: {str(e)}"

def format_signal_for_whatsapp(ticker: str, signal_text: str, current_price="N/A") -> str:
    """Formats an AI analysis report into a compact, WhatsApp-friendly alert."""
    summary_lines = []
    summary_lines.append(f"🚨 *MOOMOO LONG-TERM SIGNAL: {ticker}* 🚨")
    if current_price != "N/A":
        summary_lines.append(f"💰 Current Price: {current_price}")
    summary_lines.append("──────────────────────")
    
    # Extract verdict or first few bullet points if possible
    # We truncate if too long for WhatsApp readability (CallMeBot handles up to ~1500 chars well)
    clean_text = signal_text.replace("**", "*")  # Convert standard markdown bold to WhatsApp bold
    if len(clean_text) > 1200:
        clean_text = clean_text[:1150] + "...\n\n_(View full report in Web App)_"

    summary_lines.append(clean_text)
    summary_lines.append("──────────────────────")
    summary_lines.append("📱 _Check your Moomoo app for order execution._")
    
    return "\n".join(summary_lines)

def format_mt5_signal_for_whatsapp(asset_label: str, signal_text: str, current_price="N/A") -> str:
    """Formats an MT5 trade setup (Entry, SL, TP1, TP2) cleanly for WhatsApp."""
    summary_lines = []
    summary_lines.append(f"⚡ *MT5 SHORT-TERM TRADE SIGNAL: {asset_label}* ⚡")
    if current_price != "N/A":
        summary_lines.append(f"💵 Market Price: {current_price}")
    summary_lines.append("──────────────────────")

    clean_text = signal_text.replace("**", "*").replace("### ", "").replace("## ", "")
    if len(clean_text) > 1300:
        clean_text = clean_text[:1250] + "...\n\n_(View full trade card in Web App)_"

    summary_lines.append(clean_text)
    summary_lines.append("──────────────────────")
    summary_lines.append("⚠️ _Risk rule: Max 1-2% account balance. Set Stop Loss immediately on MT5._")
    return "\n".join(summary_lines)

