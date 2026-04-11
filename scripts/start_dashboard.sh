#!/bin/bash
set -e

cd /home/aditya-gupta/repos/AI-Idea-Iterative-Research

echo "Stopping any existing Streamlit processes..."
pkill -f "streamlit run" || true
sleep 1

echo "Starting Streamlit dashboard..."
source venv/bin/activate
streamlit run dashboard/app.py
