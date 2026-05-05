---
title: VAEP Football Analyzer
emoji: ⚽
colorFrom: green
colorTo: indigo
sdk: streamlit
app_file: app.py
pinned: false
---

# VAEP Football Action Valuation

This project implements the **VAEP (Valuing Actions by Estimating Probabilities)** framework to value player actions in football matches. 

## Features
- **Goal Visualization**: Interactive plots of the 5 actions leading up to every goal in a match.
- **VAEP Rankings**: Top 10 players by total VAEP score for major European leagues (2017-18 Season).
- **Multi-League Support**: Data for Premier League, La Liga, Serie A, Ligue 1, Bundesliga, and **World Cup 2018**.

## Technology Stack
- **Backend**: Python, Pandas, Socceraction
- **Visualization**: Matplotlib, Matplotsoccer
- **Web App**: Streamlit

## Data Source
Wyscout event data for the 2017-18 season, converted to SPADL format.
