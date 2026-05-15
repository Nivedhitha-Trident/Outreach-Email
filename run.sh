#!/bin/bash
cd "$(dirname "$0")"
BROWSER="open -a 'Google Chrome'" .venv/bin/streamlit run app.py
