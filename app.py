import streamlit as st
import pandas as pd
import os
import matplotlib.pyplot as plt
import matplotsoccer
from statsbombpy import sb
from Automated_Goal_plots import id_return, nice_time
import socceraction.spadl as spadl
import socceraction.xthreat as xT
import plotly.graph_objects as go
from compute_xt_statsbomb import FootballAnalyticsEngine
from llm_tactical_reporter import TacticalLLMReporter
from tactical_viz import plot_tactical_summary_pitch
from freeze_frame_viz import plot_tactical_evolution_plotly

# Initialize LLM Reporter
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY and "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

llm_reporter = TacticalLLMReporter(GROQ_API_KEY) if GROQ_API_KEY else None

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

# StatsBomb Data Fetching
@st.cache_data
def get_sb_competitions():
    comps = sb.competitions()
    # Filter for competitions with available match data
    comps = comps[comps['match_available'].notna()]
    # Create a display name: "Competition Name (Season)"
    comps['display_name'] = comps['competition_name'] + " (" + comps['season_name'] + ")"
    # Create a map for easy lookup
    comp_dict = {row['display_name']: (row['competition_id'], row['season_id']) for _, row in comps.iterrows()}
    return comp_dict

if data_source == "Latest StatsBomb (Open Data)":
    st.sidebar.warning("StatsBomb integration is in PROTOTYPE mode. Data is fetched live from StatsBomb Open Data.")
    sb_comp_map = get_sb_competitions()
    chosen_league = st.sidebar.selectbox("Select Competition", sorted(list(sb_comp_map.keys())))
else:
    chosen_league = st.sidebar.selectbox("Select League", leagues)

# Function to get teams and matches
@st.cache_data
def get_sb_matches(league):
    if league in sb_comp_map:
        cid, sid = sb_comp_map[league]
        return sb.matches(competition_id=cid, season_id=sid)
    return pd.DataFrame()

if data_source == "Latest StatsBomb (Open Data)":
    matches_df = get_sb_matches(chosen_league)
    if not matches_df.empty:
        # Get all unique teams that participated
        all_teams = sorted(list(set(matches_df["home_team"]) | set(matches_df["away_team"])))
        home_team = st.sidebar.selectbox("Home Team", all_teams)
        
        # Filter away teams: find all opponents of the selected home team in any match
        opponents = set(matches_df[matches_df.home_team == home_team]["away_team"]) | \
                    set(matches_df[matches_df.away_team == home_team]["home_team"])
        
        away_options = sorted(list(opponents))
        away_team = st.sidebar.selectbox("Away Team", away_options)
    else:
        st.sidebar.error("Failed to fetch matches for this competition. Try another one.")
        home_team, away_team = None, None
else:
    # Legacy logic for teams
    def get_league_teams(league):
        if league == "World Cup":
            spadl_h5 = os.path.join('spadl', "spadl-WorldCup-2018.h5")
            if os.path.exists(spadl_h5):
                with pd.HDFStore(spadl_h5) as store:
                    games = store["games"]
                    return sorted(list(set(games["home_team_name"].unique()) | set(games["away_team_name"].unique())))
            return []
        col_name = league.replace(" ", "_")
        if col_name in teams_df.columns:
            return teams_df[col_name].dropna().tolist()
        return []

    league_teams = get_league_teams(chosen_league)
    home_team = st.sidebar.selectbox("Home Team", league_teams, index=0)
    away_teams = [t for t in league_teams if t != home_team]
    away_team = st.sidebar.selectbox("Away Team", away_teams, index=0)

display_option = st.sidebar.radio("Display Option", ["Goal Plots", "VAEP/xT Ranking"])

# Data Generation Logic (adapted for both sources)
def data_generation(home_team_name, away_team_name, league_name, source):
    if source == "Latest StatsBomb (Open Data)":
        from socceraction.data.statsbomb import StatsBombLoader
        
        cid, sid = sb_comp_map[league_name]
        loader = StatsBombLoader()
        
        matches = sb.matches(competition_id=cid, season_id=sid)
        # Check both directions
        match = matches[((matches.home_team == home_team_name) & (matches.away_team == away_team_name)) | 
                        ((matches.home_team == away_team_name) & (matches.away_team == home_team_name))]
        
        if len(match) == 0:
            return None, None, None
            
        match_id = match.iloc[0].match_id
        df_actions = loader.events(match_id)
        df_teams = loader.teams(match_id)
        df_players = loader.players(match_id)
        
        # Convert to SPADL
        actions = spadl.statsbomb.convert_to_actions(df_actions, home_team_id=df_teams.iloc[0].team_id)
        
        # Ensure original_event_id is present (socceraction usually provides this)
        if "original_event_id" not in actions.columns:
            # Fallback mapping if not present
            actions["original_event_id"] = df_actions.loc[actions.index, "event_id"].values

        # Add names
        actions = (
            actions.merge(spadl.actiontypes_df(), how="left")
            .merge(spadl.results_df(), how="left")
            .merge(df_players[["player_id", "player_name", "nickname"]], how="left")
            .merge(df_teams[["team_id", "team_name"]], how="left")
        )
        actions["short_name"] = actions["nickname"].fillna(actions["player_name"])
        
        goal = actions[((actions["type_name"] == "shot") | (actions["type_name"] == "shot_penalty") | (actions["type_name"] == "shot_freekick")) &
                       (actions["result_name"] == "success")]
        
        # Mock games df for compatibility
        games = pd.DataFrame([{"game_id": match_id, "home_team_name": home_team_name, "away_team_name": away_team_name}])
        return actions, goal, games

    # Legacy Wyscout Logic
    if league_name == "Bundes Liga":
        league_file_name = "Bundesliga"
    elif league_name == "World Cup":
        league_file_name = "WorldCup-2018"
    else:
        league_file_name = league_name
        
    spadl_h5 = os.path.join('spadl', f"spadl-{league_file_name}.h5")
    if not os.path.exists(spadl_h5):
        return None, None, None

    with pd.HDFStore(spadl_h5) as spadlstore:
        games = spadlstore["games"]
        league_id_key = league_name if league_name != "Bundes Liga" else "Bundesliga"
        game_id = games[(games.competition_id == id_return(league_id_key))
                      & ((games.home_team_name == home_team_name)
                      & (games.away_team_name == away_team_name))].game_id.values
        
        if len(game_id) == 0:
            return None, None, games

        actions_list = []
        for g_id in game_id:
            action = spadlstore[f"actions/game_{g_id}"]
            action = (
                action.merge(spadlstore["actiontypes"], how="left")
                .merge(spadlstore["results"], how="left")
                .merge(spadlstore["players"], how="left")
                .merge(spadlstore["teams"], how="left")
            )
            actions_list.append(action)
        
        actions = pd.concat(actions_list, ignore_index=True)
        goal = actions[((actions["type_name"] == "shot") | (actions["type_name"] == "shot_penalty") | (actions["type_name"] == "shot_freekick")) &
                       (actions["result_name"] == "success")]
        return actions, goal, games

# Initialize Session State
if 'match_analysis' not in st.session_state:
    st.session_state.match_analysis = None

tab_match, tab_team, tab_tactical, tab_league = st.tabs(["🎯 Match Analysis", "🛡️ Team Analytics", "🧠 Tactical Insights (360)", "🏆 League Leaderboards"])

with tab_match:
    st.subheader("Match-wise Action Valuation")
    
    if st.button("Analyze Match", key="btn_match"):
        with st.spinner("Generating match analysis..."):
            actions, goal, games = data_generation(home_team, away_team, chosen_league, data_source)
            
            if actions is not None:
                # 1. PRE-COMPUTE METRICS
                with st.spinner("Computing Action Values (xT & VAEP)..."):
                    xt_model = xT.ExpectedThreat(l=16, w=12)
                    xt_model.fit(actions)
                    actions["xt_value"] = xt_model.rate(actions)
                    actions["vaep_value"] = actions["xt_value"] + (actions["result_name"] == "success").astype(int) * 0.05
                    
                    goal_mask = (actions["type_name"].str.contains("shot", case=False)) & (actions["result_name"] == "success")
                    actions.loc[goal_mask, "xt_value"] = 1.0
                    actions.loc[goal_mask, "vaep_value"] = 1.0
                    
                    actions["nice_time"] = actions.apply(nice_time, axis=1)
                    if "short_name" not in actions.columns:
                        actions["short_name"] = actions["player_name"].fillna("Unknown")
                    
                    # Store in session state for persistence
                    st.session_state.match_analysis = {
                        'actions': actions,
                        'goal': goal,
                        'games': games,
                        'home': home_team,
                        'away': away_team
                    }
            else:
                st.warning("No data found for this match combination.")

    # 2. UI RENDERING FROM SESSION STATE
    if st.session_state.match_analysis:
        ma = st.session_state.match_analysis
        actions = ma['actions']
        goal = ma['goal']
        games = ma['games']
        home_team = ma['home']
        away_team = ma['away']

        if len(goal) == 0:
            st.info("No goals were scored in this match.")
        else:
            st.markdown(f"### ⚽ Goals in {home_team} vs {away_team}")
            for i in range(len(goal)):
                # We use goal_idx as key to avoid collisions
                goal_idx = goal.index[i]
                a = actions[goal_idx-5:goal_idx+1].copy()
                goal_action = a.iloc[-1]
                scorer = goal_action["short_name"]
                team = goal_action["team_name"]
                minute = int(goal_action["time_seconds"] // 60)
                
                st.markdown(f"**Goal {i+1}: {scorer} ({team})** - {minute}'")
                fig, ax = plt.subplots(figsize=(10, 7))
                matplotsoccer.actions(
                    location=a[["start_x", "start_y", "end_x", "end_y"]],
                    action_type=a.type_name,
                    team=a.team_name,
                    result=a.result_name == "success",
                    label=a[["nice_time", "type_name", "short_name"]],
                    labeltitle=["time", "actiontype", "short_name"],
                    zoom=False, show=False, ax=ax
                )
                for collection in ax.collections: collection.set_sizes([15])
                st.pyplot(fig)
                plt.close(fig)

                # New: Interactive 360 Tactical Evolution (Manual Control)
                if data_source == "Latest StatsBomb (Open Data)":
                    # --- TACTICAL 360 EVOLUTION VIEWER ---
                    st.divider()
                    st.subheader("🧬 360° Tactical Intelligence Evolution")
                    
                    from freeze_frame_viz import plot_tactical_evolution_plotly
                    
                    # Prepare match info
                    scoring_team = team
                    match_info = {'home_team': home_team, 'away_team': away_team}
                    selected_match_id = int(games.iloc[0].game_id)
                    opp_name = match_info['home_team'] if match_info['away_team'] == scoring_team else match_info['away_team']
                    
                    # Get action sequence and define unique key for the goal
                    action_sequence = actions.loc[max(0, goal_idx-5):goal_idx].to_dict('records')
                    goal_key = str(goal_idx)
                    
                    # Fetch (or retrieve from cache) the tactical evolution
                    fig_evol, hull_areas = plot_tactical_evolution_plotly(selected_match_id, action_sequence, scoring_team, opp_name)
                    
                    if fig_evol and len(fig_evol.frames) > 0:
                        # --- INTERACTIVE TACTICAL VIDEO ROOM ---
                        st.subheader("🎥 Tactical Video Room: Phase Analysis")
                        
                        num_phases = len(action_sequence)
                        selected_phase_idx = st.select_slider(
                            "Scrub Buildup Phases",
                            options=list(range(num_phases)),
                            format_func=lambda x: f"Phase {x+1}: {action_sequence[x].get('type_name', 'Action')}",
                            value=num_phases - 1,
                            key=f"slider_{goal_key}"
                        )
                        
                        # Update Plotly figure to selected phase
                        try:
                            # Extract data for the selected frame
                            selected_frame_data = fig_evol.frames[selected_phase_idx].data
                            fig_static = go.Figure(data=selected_frame_data, layout=fig_evol.layout)
                            
                            # Add phase-specific title
                            curr_act = action_sequence[selected_phase_idx]
                            fig_static.update_layout(
                                title=f"Phase {selected_phase_idx+1}: {curr_act.get('player_name', 'Team')} - {curr_act.get('type_name')}",
                                margin=dict(l=20, r=20, t=60, b=20)
                            )
                            st.plotly_chart(fig_static, use_container_width=True, key=f"pitch_viz_{goal_key}_{selected_phase_idx}")
                        except Exception as e:
                            st.error(f"Error rendering phase visualization: {e}")
                            st.plotly_chart(fig_evol, use_container_width=True)

                        # --- COACH'S NOTEBOOK ---
                        st.markdown("### 📋 Coach's Notebook")
                        if llm_reporter:
                            insight_key = f"insight_{goal_key}_{selected_phase_idx}"
                            if insight_key not in st.session_state:
                                with st.spinner(f"Strategic analysis for Phase {selected_phase_idx + 1}..."):
                                    try:
                                        curr_action = action_sequence[selected_phase_idx]
                                        phase_data = {
                                            "player": curr_action.get('short_name'),
                                            "action": curr_action.get('type_name'),
                                            "vaep": curr_action.get('vaep_value', 0),
                                            "xt": curr_action.get('xt_value', 0)
                                        }
                                        h_area = hull_areas.get(selected_phase_idx, 0)
                                        phase_insight = llm_reporter.generate_phase_insight(phase_data, h_area, selected_phase_idx)
                                        st.session_state[insight_key] = phase_insight
                                    except Exception as e:
                                        st.session_state[insight_key] = f"⚠️ Tactical Analysis Unavailable: {e}"
                            st.markdown(st.session_state[insight_key])
                        else:
                            st.info("💡 Connect Groq API Key in secrets to enable AI Coaching Insights.")

                        # --- TECHNICAL METRICS SUMMARY ---
                        with st.expander("📝 Buildup Data: Phase Metrics"):
                            cols = st.columns(num_phases)
                            for idx, action in enumerate(action_sequence):
                                with cols[idx]:
                                    st.markdown(f"**P{idx+1}**")
                                    st.metric("xT", f"{round(action.get('xt_value', 0), 2)}")
                                    st.metric("VAEP", f"{round(action.get('vaep_value', 0), 2)}")
                    else:
                        st.info("💡 360° Tactical Data not available for this specific match buildup.")

                st.divider()
                # Match VAEP/xT Ranking
                st.markdown(f"### 📊 Player Impact (xT) Ranking")
                if data_source == "Latest StatsBomb (Open Data)":
                    summary = actions.groupby(["short_name", "team_name"]).agg({
                        "xt_value": "sum", "type_name": "count"
                    }).rename(columns={"type_name": "total_actions", "xt_value": "Expected Threat (xT)"})
                    summary = summary.sort_values("Expected Threat (xT)", ascending=False)
                    st.dataframe(summary, width="stretch")
                else:
                    st.info("Match-wise rankings are being optimized for legacy data. View full league rankings in the Leaderboards tab.")

with tab_team:
    st.subheader(f"🛡️ Team Analytics: {home_team}")
    if data_source == "Latest StatsBomb (Open Data)":
        if st.button(f"Analyze {home_team} Season Contribution"):
            engine = FootballAnalyticsEngine()
            comp_id, season_id = sb_comp_map[chosen_league]
            
            with st.spinner(f"Fetching season data for {home_team}..."):
                matches = sb.matches(competition_id=comp_id, season_id=season_id)
                team_matches = matches[(matches.home_team == home_team) | (matches.away_team == home_team)]
                
                all_actions = []
                for _, m in team_matches.head(5).iterrows(): # Sample 5
                    try:
                        actions = engine.load_match_data(m.match_id)
                        all_actions.append(actions[actions.team_name == home_team])
                    except: pass
                
                if all_actions:
                    df_team = pd.concat(all_actions)
                    st.markdown(f"#### Most Threatening Players for {home_team}")
                    # Simple xT summary
                    xt_model = xT.ExpectedThreat(l=16, w=12)
                    xt_model.fit(df_team)
                    df_team["xt_value"] = xt_model.rate(df_team)
                    summary = df_team.groupby("player_name").agg({"xt_value": "sum"}).sort_values("xt_value", ascending=False)
                    st.dataframe(summary, width="stretch")
                else:
                    st.warning("Could not find enough data for this team.")
    else:
        st.info("Team analytics are available for StatsBomb Open Data.")

with tab_tactical:
    st.subheader("🧠 Tactical Insights (StatsBomb 360)")
    st.markdown("""
    This section uses **StatsBomb 360** high-fidelity data to analyze team shape, defensive posture, and off-the-ball runs.
    """)
    
    if data_source == "Latest StatsBomb (Open Data)":
        if st.button("Run 360 Tactical Analysis", key="btn_360"):
            from compute_tactical_metrics import compute_360_tactical_metrics
            
            # Find the match_id
            cid, sid = sb_comp_map[chosen_league]
            matches = sb.matches(competition_id=cid, season_id=sid)
            match = matches[((matches.home_team == home_team) & (matches.away_team == away_team)) | 
                            ((matches.home_team == away_team) & (matches.away_team == home_team))]
            
            if not match.empty:
                match_id = match.iloc[0].match_id
                
                with st.spinner("Extracting 360 frames and computing tactical metrics..."):
                    summary = compute_360_tactical_metrics(match_id)
                    
                    if summary is not None:
                        st.success("Tactical metrics successfully extracted!")
                        
                        # New: Graphical Pitch Map
                        st.markdown("#### 🏟️ Visual Tactical Summary")
                        fig_pitch = plot_tactical_summary_pitch(summary)
                        st.pyplot(fig_pitch)
                        plt.close(fig_pitch)
                        
                        st.divider()
                        # Display Metrics in Columns
                        cols = st.columns(2)
                        for i, team_name in enumerate(summary['team'].unique()):
                            team_stats = summary[summary['team'] == team_name].iloc[0]
                            with cols[i % 2]:
                                st.markdown(f"### {team_name}")
                                st.metric("Defensive Line Height", f"{team_stats['def_line_height_m']:.1f}m | {team_stats['def_line_height_yds']:.1f} yds")
                                st.metric("Runners on Shoulder (Avg)", f"{team_stats['runners_on_shoulder']:.2f}")
                                st.metric("Peak Run Speed", f"{team_stats['peak_run_speed_m']:.1f} m/s | {team_stats['peak_run_speed_yds']:.1f} yds/s")
                                st.metric("Congestion (5m)", f"{team_stats['congestion_5m']:.2f}")
                                st.metric("Team Width", f"{team_stats['team_width_m']:.1f}m | {team_stats['team_width_yds']:.1f} yds")
                                st.metric("Team Length", f"{team_stats['team_length_m']:.1f}m | {team_stats['team_length_yds']:.1f} yds")
                        
                        st.divider()
                        st.markdown("### 📋 Technical Scouting Report")
                        with st.spinner("Generating tactical intelligence report via LLM..."):
                            # Convert summary to JSON for LLM
                            kpi_json = summary.to_dict(orient='records')
                            if llm_reporter:
                                report = llm_reporter.generate_report(kpi_json)
                                st.markdown(report)
                            else:
                                st.warning("⚠️ Groq API Key missing. Technical scouting report generation is disabled. Please set the GROQ_API_KEY environment variable.")
                        
                        st.divider()
                        st.info("Detailed event-wise tactical data has been generated for advanced modeling.")
                    else:
                        st.warning("360 data is not available for this specific match. Please try a major tournament like Euro 2024 or World Cup 2022.")
            else:
                st.error("Match not found.")
    else:
        st.warning("StatsBomb 360 data is only available for 'Latest StatsBomb (Open Data)' source.")

with tab_league:
    st.subheader(f"🏆 League Leaderboard: {chosen_league}")
    if data_source == "Latest StatsBomb (Open Data)":
        sample_size = st.slider("Number of matches to analyze", 1, 50, 5)
        if st.button("Generate Season Rankings"):
            engine = FootballAnalyticsEngine()
            comp_id, season_id = sb_comp_map[chosen_league]
            
            with st.spinner(f"Computing impact for {sample_size} matches..."):
                leaderboard = engine.get_competition_leaderboard(comp_id, season_id, max_matches=sample_size)
                if not leaderboard.empty:
                    st.markdown(f"#### Top Players by xT (Sample: {sample_size} matches)")
                    st.dataframe(leaderboard, width="stretch")
                    st.success(f"Successfully processed {sample_size} matches.")
                else:
                    st.error("Failed to generate leaderboard.")
    else:
        # Legacy logic remains...
        league_file_map = {
            "Serie A": "VAEP_score_Serie_A.csv",
            "La Liga": "VAEP_score_La_Liga.csv",
            "Premier League": "VAEP_score_Premier_League.csv",
            "Ligue 1": "VAEP_score_Ligue_1.csv",
            "Bundes Liga": "VAEP_score_Bundesliga.csv"
        }
        if chosen_league in league_file_map:
            csv_file = league_file_map[chosen_league]
            if os.path.exists(csv_file):
                df_vaep = pd.read_csv(csv_file)
                st.dataframe(df_vaep, width="stretch")
            else:
                st.error("VAEP leaderboard not found.")
        else:
            st.info("Rankings available for legacy European leagues.")

st.sidebar.markdown("---")
st.sidebar.info(f"Data Source: {data_source}")
