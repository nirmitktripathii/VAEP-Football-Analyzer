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
    # Fetch competitions
    comps = sb.competitions()
    # Basic availability filter
    comps = comps[comps['match_available'].notnull()]
    
    if only_360_filter:
        # Strict 360 availability check
        # StatsBomb stores these as timestamps or None. 
        # We filter for any non-null, non-empty strings, and ensure they look like timestamps.
        comps = comps[comps['match_available_360'].notnull()]
        comps = comps[comps['match_available_360'].astype(str).str.len() > 5]
        
    # Create display names
    comps['display_name'] = comps['competition_name'] + " (" + comps['season_name'] + ")"
    return {row['display_name']: (row['competition_id'], row['season_id']) for _, row in comps.iterrows()}

@st.cache_data(show_spinner=False)
def get_sb_matches(cid, sid):
    return sb.matches(competition_id=cid, season_id=sid)

# --- Sidebar Selection Logic ---

only_360 = False
if data_source == "Latest StatsBomb (Open Data)":
    st.sidebar.divider()
    analysis_mode = st.sidebar.selectbox(
        "Analysis Mode", 
        ["Full Match Analysis", "Tactical 360 Insights (Spatial)"],
        help="Select 'Tactical 360' to hide tournaments that lack spatial frame data."
    )
    only_360 = (analysis_mode == "Tactical 360 Insights (Spatial)")
    
    st.sidebar.warning("StatsBomb integration: Data is fetched live from Open Data API.")
    
    # Get competition map based on mode
    sb_comp_map = get_sb_competitions(only_360_filter=only_360)
    
    if not sb_comp_map:
        st.sidebar.error("No competitions found matching your filter.")
        chosen_league = None
        home_team, away_team = None, None
    else:
        comp_options = sorted(list(sb_comp_map.keys()))
        chosen_league = st.sidebar.selectbox("Select Competition", comp_options)
        
        cid, sid = sb_comp_map[chosen_league]
        matches_df = get_sb_matches(cid, sid)
        
        if not matches_df.empty:
            # Get unique teams
            all_teams = sorted(list(set(matches_df["home_team"]) | set(matches_df["away_team"])))
            home_team = st.sidebar.selectbox("Home Team", all_teams)
            
            # Find opponents
            opponents = set(matches_df[matches_df.home_team == home_team]["away_team"]) | \
                        set(matches_df[matches_df.away_team == home_team]["home_team"])
            
            away_options = sorted(list(opponents))
            away_team = st.sidebar.selectbox("Away Team", away_options)
        else:
            st.sidebar.error("No matches found.")
            home_team, away_team = None, None
else:
    # Legacy logic
    chosen_league = st.sidebar.selectbox("Select League", leagues)
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
    away_team = st.sidebar.selectbox("Away Team", [t for t in league_teams if t != home_team], index=0)

display_option = st.sidebar.radio("Display Option", ["Goal Plots", "VAEP/xT Ranking"])

# --- Core Logic Implementation ---

def data_generation(home_team_name, away_team_name, league_name, source):
    if source == "Latest StatsBomb (Open Data)":
        from socceraction.data.statsbomb import StatsBombLoader
        cid, sid = sb_comp_map[league_name]
        loader = StatsBombLoader()
        matches = get_sb_matches(cid, sid)
        match = matches[((matches.home_team == home_team_name) & (matches.away_team == away_team_name)) | 
                        ((matches.home_team == away_team_name) & (matches.away_team == home_team_name))]
        if match.empty: return None, None, None
        match_id = match.iloc[0].match_id
        df_actions = loader.events(match_id)
        df_teams = loader.teams(match_id); df_players = loader.players(match_id)
        actions = spadl.statsbomb.convert_to_actions(df_actions, home_team_id=df_teams.iloc[0].team_id)
        actions = (actions.merge(spadl.actiontypes_df(), how="left").merge(spadl.results_df(), how="left")
                  .merge(df_players[["player_id", "player_name", "nickname"]], how="left")
                  .merge(df_teams[["team_id", "team_name"]], how="left"))
        actions["short_name"] = actions["nickname"].fillna(actions["player_name"])
        goal = actions[((actions["type_name"] == "shot") | (actions["type_name"] == "shot_penalty") | (actions["type_name"] == "shot_freekick")) &
                       (actions["result_name"] == "success")]
        return actions, goal, pd.DataFrame([{"game_id": match_id}])
    
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

# --- Main Tabs ---

tab_match, tab_team, tab_tactical, tab_league = st.tabs(["🎯 Match Analysis", "🛡️ Team Analytics", "🧠 Tactical Insights (360)", "🏆 League Leaderboards"])

with tab_match:
    st.subheader("Match-wise Action Valuation")
    if st.button("Analyze Match", key="btn_match"):
        with st.spinner("Generating match analysis..."):
            actions, goal, games = data_generation(home_team, away_team, chosen_league, data_source)
            if actions is None:
                st.warning("No data found for this match combination.")
            else:
                actions["nice_time"] = actions.apply(nice_time, axis=1)
                if len(goal) == 0:
                    st.info("No goals were scored in this match.")
                else:
                    st.markdown(f"### ⚽ Goals in {home_team} vs {away_team}")
                    for i in range(len(goal)):
                        a = actions[goal.index[i]-5:goal.index[i]+1].copy()
                        goal_action = a.iloc[-1]
                        scorer = goal_action["short_name"]; team = goal_action["team_name"]
                        st.markdown(f"**Goal {i+1}: {scorer} ({team})**")
                        fig, ax = plt.subplots(figsize=(10, 7))
                        matplotsoccer.actions(
                            location=a[["start_x", "start_y", "end_x", "end_y"]],
                            action_type=a.type_name, team=a.team_name,
                            result=a.result_name == "success",
                            label=a[["nice_time", "type_name", "short_name"]],
                            labeltitle=["time", "actiontype", "short_name"],
                            zoom=False, show=False, ax=ax
                        )
                        st.pyplot(fig); plt.close(fig)
                st.divider()
                st.markdown(f"### 📊 Player Impact (xT) Ranking")
                if data_source == "Latest StatsBomb (Open Data)":
                    xt_model = xT.ExpectedThreat(l=16, w=12); xt_model.fit(actions)
                    actions["xt_value"] = xt_model.rate(actions)
                    summary = actions.groupby(["short_name", "team_name"]).agg({"xt_value": "sum", "type_name": "count"}).rename(columns={"type_name": "total_actions", "xt_value": "Expected Threat (xT)"})
                    st.dataframe(summary.sort_values("Expected Threat (xT)", ascending=False), width="stretch")

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
                        else:
                            st.error("No 360 data found for this match.")
    else:
        st.warning("StatsBomb 360 data is only available for 'Latest StatsBomb (Open Data)'.")

with tab_team:
    st.subheader(f"🛡️ Team Analytics: {home_team}")
    if data_source == "Latest StatsBomb (Open Data)" and chosen_league:
        if st.button(f"Analyze {home_team} Season Contribution"):
            engine = FootballAnalyticsEngine(); cid, sid = sb_comp_map[chosen_league]
            with st.spinner("Fetching season data..."):
                matches = get_sb_matches(cid, sid)
                team_matches = matches[(matches.home_team == home_team) | (matches.away_team == home_team)]
                all_actions = []
                for _, m in team_matches.head(5).iterrows():
                    try: actions = engine.load_match_data(m.match_id); all_actions.append(actions[actions.team_name == home_team])
                    except: pass
                if all_actions:
                    df_team = pd.concat(all_actions); xt_model = xT.ExpectedThreat(l=16, w=12); xt_model.fit(df_team)
                    df_team["xt_value"] = xt_model.rate(df_team)
                    st.dataframe(df_team.groupby("player_name").agg({"xt_value": "sum"}).sort_values("xt_value", ascending=False), width="stretch")

with tab_league:
    st.subheader(f"🏆 League Leaderboard: {chosen_league}")
    if data_source == "Latest StatsBomb (Open Data)" and chosen_league:
        sample_size = st.slider("Matches to analyze", 1, 50, 5)
        if st.button("Generate Season Rankings"):
            engine = FootballAnalyticsEngine(); cid, sid = sb_comp_map[chosen_league]
            with st.spinner("Computing season rankings..."):
                leaderboard = engine.get_competition_leaderboard(cid, sid, max_matches=sample_size)
                if not leaderboard.empty: st.dataframe(leaderboard, width="stretch")

st.sidebar.markdown("---")
st.sidebar.info(f"Data Source: {data_source}")
