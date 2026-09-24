# 24/7 Cloud Deployment Guide

This guide explains how to host your AI Trading Terminal online 24/7 so it runs continuously without your laptop.

---

## Method 1: Streamlit Community Cloud (100% Free Forever — Recommended)

With this method, your app runs on Streamlit's high-speed cloud infrastructure. You get a public URL accessible from your smartphone anytime.

### Step 1: Create a GitHub Repository
1. Go to [github.com](https://github.com) and create a **Private** repository (e.g. `trading-ai-bot`).
2. In your local terminal, initialize and push your code:
   ```bash
   cd "C:\Users\haika\.gemini\antigravity\scratch\moomoo_ai_signals"
   git init
   git add .
   git commit -m "Initial commit for 24/7 trading terminal"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/trading-ai-bot.git
   git push -u origin main
   ```
   *(Note: Your `.gitignore` automatically keeps your `config.json` safe from being uploaded).*

### Step 2: Deploy on Streamlit Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io) and log in with your GitHub account.
2. Click **"New app"**.
3. Select your repository: `trading-ai-bot`, Branch: `main`, Main file path: `app.py`.
4. Click **Advanced settings...** ➔ **Secrets**, and paste your keys:
   ```toml
   GEMINI_API_KEY = "your_gemini_api_key_here"
   WHATSAPP_PHONE = "+60123456789"
   WHATSAPP_API_KEY = "your_callmebot_api_key"
   ```
5. Click **Deploy!**
6. In ~60 seconds, your app will be live 24/7 at `https://your-custom-name.streamlit.app`!

---

## Method 2: Cheap Linux VPS (RackNerd / Hetzner — ~$1 to $3 / month)

If you purchase a cheap Ubuntu VPS:

### Step 1: Connect to your VPS via SSH
```bash
ssh root@YOUR_SERVER_IP
```

### Step 2: Install Python & Clone Code
```bash
sudo apt update && sudo apt install -y python3-pip python3-venv git
git clone https://github.com/YOUR_USERNAME/trading-ai-bot.git
cd trading-ai-bot
pip install -r requirements.txt
```

### Step 3: Run as a 24/7 Background System Service (systemd)
Create a service file so it restarts automatically even if the VPS reboots:
```bash
sudo nano /etc/systemd/system/tradingbot.service
```
Paste this configuration:
```ini
[Unit]
Description=Trading AI Terminal 24/7
After=network.target

[Service]
User=root
WorkingDirectory=/root/trading-ai-bot
ExecStart=/usr/local/bin/streamlit run app.py --server.port 8501 --server.headless true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable tradingbot
sudo systemctl start tradingbot
```
Your app is now permanently running at `http://YOUR_SERVER_IP:8501`!
