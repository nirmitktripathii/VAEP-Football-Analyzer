import streamlit as st
import pandas as pd
import os
import matplotlib.pyplot as plt
import matplotsoccer
from Automated_Goal_plots import id_return, nice_time

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

if data_source == "Latest StatsBomb (Open Data)":
    st.sidebar.warning("StatsBomb integration is in PROTOTYPE mode. Latest matches (Euro 2024, La Liga 22/23) will be available soon.")
    chosen_league = st.sidebar.selectbox("Select Competition", ["Euro 2024", "La Liga (Messi Era)", "Champions League"])
else:
    chosen_league = st.sidebar.selectbox("Select League", leagues)

# Function to get teams for chosen league
def get_league_teams(league):
    if league == "World Cup":
        spadl_h5 = os.path.join('spadl', "spadl-WorldCup-2018.h5")
        if os.path.exists(spadl_h5):
            with pd.HDFStore(spadl_h5) as store:
                games = store["games"]
                home_teams = games["home_team_name"].unique()
                away_teams = games["away_team_name"].unique()
                return sorted(list(set(home_teams) | set(away_teams)))
        return []
    
    # Map 'Bundes Liga' to 'Bundes_Liga' to match CSV header
    col_name = league.replace(" ", "_")
    return teams_df[col_name].dropna().tolist()

league_teams = get_league_teams(chosen_league)

home_team = st.sidebar.selectbox("Home Team", league_teams, index=0)
# Exclude home team from away team list
away_teams = [t for t in league_teams if t != home_team]
away_team = st.sidebar.selectbox("Away Team", away_teams, index=0)

display_option = st.sidebar.radio("Display Option", ["Goal Plots", "VAEP Ranking"])

# Data Generation Logic (adapted from Automated_Goal_plots.py)
def data_generation(home_team_name, away_team_name, league_name):
    # Fix league name for file path if needed
    if league_name == "Bundes Liga":
        league_file_name = "Bundesliga"
    elif league_name == "World Cup":
        league_file_name = "WorldCup-2018"
    else:
        league_file_name = league_name
        
    spadl_h5 = os.path.join('spadl', f"spadl-{league_file_name}.h5")
    
    if not os.path.exists(spadl_h5):
        st.error(f"Data file not found: {spadl_h5}")
        return None, None, None

    with pd.HDFStore(spadl_h5) as spadlstore:
        games = spadlstore["games"]
        # Use league_file_name for ID return too
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
                .merge(spadlstore["bodyparts"], how="left")
                .merge(spadlstore["players"], how="left")
                .merge(spadlstore["teams"], how="left")
            )
            actions_list.append(action)
        
        actions = pd.concat(actions_list, ignore_index=True)
        goal = actions[((actions["type_name"] == "shot") | (actions["type_name"] == "shot_penalty") | (actions["type_name"] == "shot_freekick")) &
                       (actions["result_name"] == "success")]
        
        return actions, goal, games

# Main content
if st.sidebar.button("Analyze"):
    if display_option == "Goal Plots":
        with st.spinner("Generating goal plots..."):
            actions, goal, games = data_generation(home_team, away_team, chosen_league)
            
            if actions is None:
                st.warning("No data found for this match combination.")
            elif len(goal) == 0:
                st.info("No goals were scored in this match.")
            else:
                st.subheader(f"Goals in {home_team} vs {away_team}")
                
                for i in range(len(goal)):
                    # Get goal details from the last action of the sequence
                    a = actions[goal.index[i]-5:goal.index[i]+1].copy()
                    goal_action = a.iloc[-1]
                    scorer = goal_action["short_name"]
                    team = goal_action["team_name"]
                    
                    # Calculate minute and second
                    total_seconds = goal_action["period_id"] * 45 * 60 + goal_action["time_seconds"] if "period_id" in goal_action else goal_action["time_seconds"]
                    minute = int(goal_action["time_seconds"] // 60)
                    second = int(goal_action["time_seconds"] % 60)
                    period = int(goal_action["period_id"])
                    
                    st.markdown(f"#### ⚽ Goal {i+1}: {scorer} ({team})")
                    st.markdown(f"**Minute:** {minute}:{second:02d} (Period {period})")
                    
                    fig, ax = plt.subplots(figsize=(10, 7))
                    
                    # Adapted plotting logic
                    g = games[games.game_id == a.game_id.values[0]].iloc[0]
                    
                    a["nice_time"] = a.apply(nice_time, axis=1)
                    labels = a[["nice_time", "type_name", "short_name"]]
                    
                    # Use matplotsoccer with miniature markers if supported, 
                    # or standard sizes with zoomed out view
                    matplotsoccer.actions(
                        location=a[["start_x", "start_y", "end_x", "end_y"]],
                        action_type=a.type_name,
                        team=a.team_name,
                        result=a.result_name == "success",
                        label=labels,
                        labeltitle=["time", "actiontype", "short_name"],
                        zoom=False,
                        show=False,
                        ax=ax
                    )
                    
                    # Decrease marker sizes by iterating through scatter collections
                    for collection in ax.collections:
                        collection.set_sizes([15]) # Miniature size
                    
                    st.pyplot(fig)
                    plt.close(fig)

    else:  # VAEP Ranking
        st.subheader(f"Top 10 Players in {chosen_league} by VAEP")
        league_file_map = {
            "Serie A": "VAEP_score_Serie_A.csv",
            "La Liga": "VAEP_score_La_Liga.csv",
            "Premier League": "VAEP_score_Premier_League.csv",
            "Ligue 1": "VAEP_score_Ligue_1.csv",
            "Bundes Liga": "VAEP_score_Bundesliga.csv"
        }
        csv_file = league_file_map[chosen_league]
        if os.path.exists(csv_file):
            # The CSV seems to have 10 rows and some columns, based on the GUI code grid
            # Let's read it and display as a nice table
            df_vaep = pd.read_csv(csv_file)
            st.dataframe(df_vaep, use_container_width=True)
        else:
            st.error(f"VAEP score file not found: {csv_file}")

st.sidebar.markdown("---")
st.sidebar.info("Data source: Wyscout 2017-18 Season")
