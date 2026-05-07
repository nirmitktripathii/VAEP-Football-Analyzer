import streamlit as st
import pandas as pd
import os
import matplotlib.pyplot as plt
import matplotsoccer
from statsbombpy import sb
from Automated_Goal_plots import id_return, nice_time
import socceraction.spadl as spadl
import socceraction.xthreat as xT
from compute_xt_statsbomb import FootballAnalyticsEngine
from llm_tactical_reporter import TacticalLLMReporter

# Initialize LLM Reporter
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
llm_reporter = TacticalLLMReporter(GROQ_API_KEY) if GROQ_API_KEY else None

# Page configuration
st.set_page_config(page_title="Football VAEP Analyzer", layout="wide")

# ... (Previous code) ...

with tab_tactical:
    st.subheader("🧠 Tactical Insights (StatsBomb 360)")
    if data_source == "Latest StatsBomb (Open Data)":
        if st.button("Run 360 Tactical Analysis", key="btn_360"):
            from compute_tactical_metrics import compute_360_tactical_metrics
            # (Fetching match_id logic)
            # ...
            summary = compute_360_tactical_metrics(match_id)
            if summary is not None:
                # Display metrics...
                # ...
                st.divider()
                st.markdown("### 📋 Technical Scouting Report")
                if llm_reporter:
                    with st.spinner("Generating tactical intelligence report via LLM..."):
                        kpi_json = summary.to_dict(orient='records')
                        report = llm_reporter.generate_report(kpi_json)
                        st.markdown(report)
                else:
                    st.warning("LLM Reporter not initialized. Please set GROQ_API_KEY in Hugging Face Secrets.")
