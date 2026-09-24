@echo off
title Moomoo AI Trading Terminal
echo Starting Moomoo & MT5 AI Trading Terminal...
cd /d "C:\Users\haika\.gemini\antigravity\scratch\moomoo_ai_signals"
start http://localhost:8501
python -m streamlit run app.py
pause
