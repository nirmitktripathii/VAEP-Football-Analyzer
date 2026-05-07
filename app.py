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

# Page configuration
st.set_page_config(page_title="Football VAEP Analyzer", layout="wide")

st.title("⚽ Football Action Valuation (VAEP)")
st.markdown("""
This app evaluates football actions using the **VAEP (Valuing Actions by Estimating Probabilities)** framework. 
Select a league and a match to visualize goal-scoring sequences or view the top players by VAEP score.
""")

# Load teams data
@st.cache_data
def load_teams():
    return pd.read_csv('teams.csv')

teams_df = load_teams()

# Sidebar for selections
st.sidebar.header("Selections")

def id_return(league_name):
    leagues = {'Serie A': 524, 'Premier League': 364, 'La Liga': 795, 'Ligue 1': 412, 'Bundesliga': 426, 'World Cup': 28}
    return leagues[league_name]

leagues = ['Serie A', 'Premier League', 'La Liga', 'Bundes Liga', 'Ligue 1', 'World Cup']
data_source = st.sidebar.radio("Data Source", ["Legacy Wyscout (2017/18)", "Latest StatsBomb (Open Data)"])

# --- StatsBomb Data Fetching Functions ---

@st.cache_data(show_spinner=False)
def get_sb_competitions(only_360_filter=False):
    comps = sb.competitions()
    comps = comps[comps['match_available'].notnull()]
    if only_360_filter:
        comps = comps[comps['match_available_360'].notnull()]
        comps = comps[comps['match_available_360'].astype(str).str.len() > 5]
    comps['display_name'] = comps['competition_name'] + " (" + comps['season_name'] + ")"
    return {row['display_name']: (row['competition_id'], row['season_id']) for _, row in comps.iterrows()}

@st.cache_data(show_spinner=False)
def get_sb_matches(cid, sid):
    return sb.matches(competition_id=cid, season_id=sid)

# --- Persona Report Generator ---

def generate_technical_report(summary):
    if summary is None or summary.empty:
        return "No data available for tactical analysis."
    
    report = "### 👔 Guardiola x Ferguson: Tactical Intelligence Report\n\n"
    report += "> *\"A combination of technical mastery and the character to seize the moment.\"*\n\n"
    
    for _, stats in summary.iterrows():
        team = stats['team']
        report += f"#### **{team} Assessment**\n"
        
        # Pep Style (Tactical/Spatial)
        if stats['def_line_height'] > 48:
            pep = f"We compressed the pitch beautifully with a **{stats['def_line_height']:.1f}m** line. It allowed us to sustain pressure in the final third."
        else:
            pep = f"The block was too deep at **{stats['def_line_height']:.1f}m**. We lacked the verticality to punish their transitions from this depth."
            
        # Sir Alex Style (Management/Speed)
        if stats['peak_run_speed_ms'] > 8.5:
            gaffer = f"That **{stats['peak_run_speed_ms']:.1f} m/s** burst on the shoulder is exactly what I like to see. No fear, just pure aggression."
        else:
            gaffer = f"A bit pedestrian in the breaks. **{stats['peak_run_speed_ms']:.1f} m/s** isn't going to win you a title in the dying minutes, is it?"
            
        report += f"*   **The Professor (Guardiola)**: {pep}\n"
        report += f"*   **The Gaffer (Ferguson)**: {gaffer}\n"
        report += f"*   **Spatial Insight**: Team Width (**{stats['team_width']:.1f}m**) vs Congestion (**{stats['congestion_5m']:.2f}**) suggests efficient usage of half-spaces.\n\n"
        
    return report

# --- Sidebar Logic ---

only_360 = False
if data_source == "Latest StatsBomb (Open Data)":
    st.sidebar.divider()
    analysis_mode = st.sidebar.selectbox("Analysis Mode", ["Full Match Analysis", "Tactical 360 Insights (Spatial)"])
    only_360 = (analysis_mode == "Tactical 360 Insights (Spatial)")
    st.sidebar.warning("StatsBomb integration: Live Open Data API.")
    sb_comp_map = get_sb_competitions(only_360_filter=only_360)
    
    if not sb_comp_map:
        st.sidebar.error("No 360-enabled competitions found.")
        chosen_league = None
    else:
        chosen_league = st.sidebar.selectbox("Select Competition", sorted(list(sb_comp_map.keys())))
        cid, sid = sb_comp_map[chosen_league]
        matches_df = get_sb_matches(cid, sid)
        if not matches_df.empty:
            all_teams = sorted(list(set(matches_df["home_team"]) | set(matches_df["away_team"])))
            home_team = st.sidebar.selectbox("Home Team", all_teams)
            opponents = sorted(list(set(matches_df[matches_df.home_team == home_team]["away_team"]) | set(matches_df[matches_df.away_team == home_team]["home_team"])))
            away_team = st.sidebar.selectbox("Away Team", opponents)
else:
    chosen_league = st.sidebar.selectbox("Select League", leagues)
    def get_league_teams(league):
        return []
    home_team = st.sidebar.selectbox("Home Team", ["Select League First"], disabled=True)
    away_team = st.sidebar.selectbox("Away Team", ["Select League First"], disabled=True)

# --- Main Tabs ---

tab_match, tab_team, tab_tactical, tab_league = st.tabs(["🎯 Match Analysis", "🛡️ Team Analytics", "🧠 Tactical Insights (360)", "🏆 League Leaderboards"])

with tab_match:
    st.subheader("Match-wise Action Valuation")
    if st.button("Analyze Match", key="btn_match"):
        with st.spinner("Generating match analysis..."):
            # ... analysis logic
            st.info("Analysis logic active.")

with tab_tactical:
    st.subheader("🧠 Tactical Insights (StatsBomb 360)")
    if data_source == "Latest StatsBomb (Open Data)":
        if not only_360:
            st.info("💡 **Tip**: Switch to 'Tactical 360' mode in the sidebar to only see tournaments with spatial data.")
        if chosen_league and home_team and away_team:
            cid, sid = sb_comp_map[chosen_league]
            matches = get_sb_matches(cid, sid)
            match = matches[((matches.home_team == home_team) & (matches.away_team == away_team)) | 
                            ((matches.home_team == away_team) & (matches.away_team == home_team))]
            if not match.empty:
                match_id = match.iloc[0].match_id
                if st.button("Run 360 Tactical Analysis"):
                    from compute_tactical_metrics import compute_360_tactical_metrics
                    with st.spinner("Extracting 360 spatial data..."):
                        summary = compute_360_tactical_metrics(match_id)
                        if summary is not None:
                            st.success("Tactical metrics successfully extracted!")
                            cols = st.columns(2)
                            for i, team in enumerate(summary['team'].unique()):
                                stats = summary[summary['team'] == team].iloc[0]
                                with cols[i % 2]:
                                    st.markdown(f"### {team}")
                                    st.metric("Defensive Line Height", f"{stats['def_line_height']:.1f}m")
                                    st.metric("Runners on Shoulder (Avg)", f"{stats['runners_on_shoulder']:.2f}")
                                    st.metric("Peak Run Speed", f"{stats['peak_run_speed_ms']:.1f} m/s")
                                    st.metric("Team Width/Length", f"{stats['team_width']:.1f}m / {stats['team_length']:.1f}m")
                            
                            st.divider()
                            st.markdown(generate_technical_report(summary))
                        else: st.error("No 360 data found.")
            else: st.error("Match not found.")
    else: st.warning("360 data only for StatsBomb Open Data.")

with tab_team: st.subheader("🛡️ Team Analytics")
with tab_league: st.subheader("🏆 League Leaderboards")

st.sidebar.markdown("---")
st.sidebar.info(f"Data Source: {data_source}")
