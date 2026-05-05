import os
import pandas as pd
import matplotsoccer


def id_return(league_name):
    leagues = {'Serie A' :524,'Premier League':364 ,'La Liga': 795,'Ligue 1':412,'Bundesliga':426}
    return leagues[league_name]

def nice_time(row):
            minute = int((row.period_id-1)*45 +row.time_seconds // 60)
            second = int(row.time_seconds % 60)
            return f"{minute}m{second}s"


def data_generation(home_team_name,away_team_name,league_name):
   actions = pd.DataFrame()
   if home_team_name == away_team_name:
       return (None, None, None)
   spadl_h5 = os.path.join('spadl', f"spadl-{league_name}.h5")
   with pd.HDFStore(spadl_h5) as spadlstore:
    games = spadlstore["games"]
    game_id = games[(games.competition_id == id_return(league_name))
                  & ((games.home_team_name == home_team_name)
                  & (games.away_team_name == away_team_name))].game_id.values
    for i in range(len(game_id)):
       action = spadlstore[f"actions/game_{game_id[i]}"]
       action = (
            action.merge(spadlstore["actiontypes"],how="left")
            .merge(spadlstore["results"],how="left")
            .merge(spadlstore["bodyparts"],how="left")
            .merge(spadlstore["players"],how="left")
            .merge(spadlstore["teams"],how="left")
            )
       actions = action.append(actions, ignore_index = True)
    goal=actions.loc[#((actions ["short_team_name"] == "Manchester United")) &
    ((actions["type_name"] == "shot") | (actions["type_name"] == "shot_penalty") | (actions["type_name"] == "shot_freekick")) &
    ((actions["result_name"] == "success"))]
    return (actions,goal,games)

def plotting(goal,actions,games,i,ax):
    c=d=0
    x =actions.game_id.unique()
    k=0
    home_score = 0
    away_score = 0


    a = actions[goal.index[i]-5:goal.index[i]+1].copy()
    g = list(games[games.game_id == a.game_id.values[0]].itertuples())[0]
    if x[k] != g.game_id:
        home_score = 0
        away_score = 0
        k +=1
    minute = int((a.period_id.values[0]-1)*45 +a.time_seconds.values[0] // 60)
    if actions.short_team_name.iloc[goal.index[i]] == g.home_team_name :
        home_score+=1
        c+=1
    elif actions.short_team_name.iloc[goal.index[i]] == g.away_team_name:
        away_score+=1
        d+=1


    a["nice_time"] = a.apply(nice_time,axis=1)
    labels = a[["nice_time", "type_name", "short_name"]]

    matplotsoccer.actions(
        location=a[["start_x", "start_y", "end_x", "end_y"]],
        action_type=a.type_name,
        team=a.team_name,
        result=a.result_name == "success",
        label=labels,
        labeltitle=["time","actiontype","short_name"],
        zoom=False,
        show=False,
        ax = ax
        )
