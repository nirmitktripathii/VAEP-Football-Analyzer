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

# StatsBomb Data Fetching
@st.cache_data
def get_sb_competitions(only_360=False):
    comps = sb.competitions()
    # Filter for competitions with available match data
    comps = comps[comps['match_available'].notna()]
    
    if only_360:
        # Filter for competitions that have 360 data available
        comps = comps[comps['match_available_360'].notna()]
        
    # Create a display name: "Competition Name (Season)"
    comps['display_name'] = comps['competition_name'] + " (" + comps['season_name'] + ")"
    # Create a map for easy lookup
    comp_dict = {row['display_name']: (row['competition_id'], row['season_id']) for _, row in comps.iterrows()}
    return comp_dict

# Logic for 360 filtering
only_360 = False
if data_source == "Latest StatsBomb (Open Data)":
    st.sidebar.divider()
    analysis_mode = st.sidebar.selectbox("Analysis Mode", ["Full Match Analysis", "Tactical 360 Insights (Spatial)"])
    only_360 = (analysis_mode == "Tactical 360 Insights (Spatial)")
    
    if only_360:
        st.sidebar.info("Filtering for competitions/matches with 360-degree spatial data.")
    
    st.sidebar.warning("StatsBomb integration is in PROTOTYPE mode. Data is fetched live from StatsBomb Open Data.")
    sb_comp_map = get_sb_competitions(only_360=only_360)
    
    if not sb_comp_map:
        st.sidebar.error("No 360-enabled competitions found.")
        chosen_league = None
    else:
        chosen_league = st.sidebar.selectbox("Select Competition", sorted(list(sb_comp_map.keys())))
else:
    chosen_league = st.sidebar.selectbox("Select League", leagues)

# Function to get teams and matches
@st.cache_data
def get_sb_matches(league, only_360=False):
    if league in sb_comp_map:
        cid, sid = sb_comp_map[league]
        matches = sb.matches(competition_id=cid, season_id=sid)
        if only_360:
            # Ensure the match has 360 data
            matches = matches[matches['match_available_360'].notna()]
        return matches
    return pd.DataFrame()

if data_source == "Latest StatsBomb (Open Data)":
    if chosen_league:
        matches_df = get_sb_matches(chosen_league, only_360=only_360)
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
            st.sidebar.error("No matches found for this selection.")
            home_team, away_team = None, None
    else:
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

# Main content
# Main content with Tabs
tab_match, tab_team, tab_tactical, tab_league = st.tabs(["🎯 Match Analysis", "🛡️ Team Analytics", "🧠 Tactical Insights (360)", "🏆 League Leaderboards"])

with tab_match:
    st.subheader("Match-wise Action Valuation")
    if st.button("Analyze Match", key="btn_match"):
        with st.spinner("Generating match analysis..."):
            actions, goal, games = data_generation(home_team, away_team, chosen_league, data_source)
            
            if actions is None:
                st.warning("No data found for this match combination.")
            else:
                # Prepare plotting labels
                actions["nice_time"] = actions.apply(nice_time, axis=1)
                # Goal Plots section
                if len(goal) == 0:
                    st.info("No goals were scored in this match.")
                else:
                    st.markdown(f"### ⚽ Goals in {home_team} vs {away_team}")
                    for i in range(len(goal)):
                        a = actions[goal.index[i]-5:goal.index[i]+1].copy()
                        goal_action = a.iloc[-1]
                        scorer = goal_action["short_name"]
                        team = goal_action["team_name"]
                        minute = int(goal_action["time_seconds"] // 60)
                        
                        # Ensure all required columns for plotting exist in 'a'
                        if "nice_time" not in a.columns:
                            a["nice_time"] = a.apply(nice_time, axis=1)
                        if "short_name" not in a.columns and "player_name" in a.columns:
                            a["short_name"] = a["player_name"]
                        
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

                st.divider()
                # Match VAEP/xT Ranking
                st.markdown(f"### 📊 Player Impact (xT) Ranking")
                if data_source == "Latest StatsBomb (Open Data)":
                    xt_model = xT.ExpectedThreat(l=16, w=12)
                    xt_model.fit(actions)
                    actions["xt_value"] = xt_model.rate(actions)
                    
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
        if not only_360:
            st.info("💡 **Tip**: Switch the **Analysis Mode** in the sidebar to 'Tactical 360 Insights' to filter for 360-enabled matches.")
            
        if chosen_league and home_team and away_team:
            # Find the match_id and check 360 availability
            cid, sid = sb_comp_map[chosen_league]
            matches = sb.matches(competition_id=cid, season_id=sid)
            match = matches[((matches.home_team == home_team) & (matches.away_team == away_team)) | 
                            ((matches.home_team == away_team) & (matches.away_team == home_team))]
            
            if not match.empty:
                match_id = match.iloc[0].match_id
                is_360_available = match.iloc[0].get('match_available_360') is not None
                
                if is_360_available:
                    if st.button("Run 360 Tactical Analysis", key="btn_360"):
                        from compute_tactical_metrics import compute_360_tactical_metrics
                        
                        with st.spinner("Extracting 360 frames and computing tactical metrics..."):
                            summary = compute_360_tactical_metrics(match_id)
                            
                            if summary is not None:
                                st.success("Tactical metrics successfully extracted!")
                                
                                # Display Metrics in Columns
                                cols = st.columns(2)
                                for i, team_name in enumerate(summary['team'].unique()):
                                    team_stats = summary[summary['team'] == team_name].iloc[0]
                                    with cols[i % 2]:
                                        st.markdown(f"### {team_name}")
                                        st.metric("Defensive Line Height", f"{team_stats['def_line_height']:.1f}m")
                                        st.metric("Runners on Shoulder (Avg)", f"{team_stats['runners_on_shoulder']:.2f}")
                                        st.metric("Peak Run Speed", f"{team_stats['peak_run_speed_ms']:.1f} m/s")
                                        st.metric("Congestion (5m)", f"{team_stats['congestion_5m']:.2f}")
                                        st.metric("Team Width/Length", f"{team_stats['team_width']:.1f}m / {team_stats['team_length']:.1f}m")
                                
                                st.divider()
                                st.info("Detailed event-wise tactical data has been generated for advanced modeling.")
                            else:
                                st.error("Failed to extract tactical metrics.")
                else:
                    st.warning(f"⚠️ **StatsBomb 360 data is NOT available** for this match.")
                    st.info("Try a match from **UEFA Euro 2024**, **FIFA World Cup 2022**, or **La Liga 2020/21**.")
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

st.sidebar.markdown("---\")
st.sidebar.info(f"Data Source: {data_source}")
