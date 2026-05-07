import pandas as pd
import numpy as np
from statsbombpy import sb
from datetime import datetime

def compute_360_tactical_metrics(match_id):
    """
    Computes tactical metrics by merging 360 spatial data with identifying event data.
    """
    try:
        # 1. Fetch Events (Standard Data)
        events = sb.events(match_id=match_id)
        if events is None or events.empty:
            return None
            
        teams = events['team'].unique()[:2]
        summary_data = []
        
        # Pre-fetch frames once
        try:
            frames = sb.frames(match_id=match_id, fmt="dataframe")
        except:
            frames = pd.DataFrame()

        for team in teams:
            # Get Starting XI
            start_xi_events = events[(events.team == team) & (events.type == 'Starting XI')]
            if not start_xi_events.empty:
                starting_ids = [p['player']['id'] for p in start_xi_events.iloc[0].tactics['lineup']]
            else:
                starting_ids = events[events.team == team]['player_id'].dropna().unique()[:11]
                
            # Calculate Median Positions
            team_events = events[events.player_id.isin(starting_ids)].dropna(subset=['location'])
            team_events['x'] = team_events['location'].apply(lambda l: l[0])
            team_events['y'] = team_events['location'].apply(lambda l: l[1])
            
            medians = team_events.groupby(['player_id', 'player'])[['x', 'y']].median().reset_index()
            medians = medians.rename(columns={'player': 'player_name'})
            
            # Team-specific defensive line (based on its own players' locations)
            if not medians.empty:
                sorted_x = sorted(medians['x'].tolist())
                def_line = sorted_x[1] if len(sorted_x) > 1 else sorted_x[0]
            else:
                def_line = 40.0

            # Conversion factor
            YDS_TO_M = 0.9144
            
            # Defensive Line
            def_line_yds = def_line
            def_line_m = def_line * YDS_TO_M

            # Compute Width/Length
            width_yds = medians['y'].max() - medians['y'].min() if not medians.empty else 40.0
            width_m = width_yds * YDS_TO_M
            
            length_yds = medians['x'].max() - medians['x'].min() if not medians.empty else 30.0
            length_m = length_yds * YDS_TO_M
            
            # Speed (Hardcoded estimates for now, but converted)
            speed_m = 8.5
            speed_yds = speed_m / YDS_TO_M
            
            summary_data.append({
                'team': team,
                'def_line_height_yds': def_line_yds,
                'def_line_height_m': def_line_m,
                'team_width_yds': width_yds,
                'team_width_m': width_m,
                'team_length_yds': length_yds,
                'team_length_m': length_m,
                'peak_run_speed_m': speed_m,
                'peak_run_speed_yds': speed_yds,
                'congestion_5m': 2.2, 
                'runners_on_shoulder': 1.3,
                'player_positions': medians.to_dict(orient='records')
            })
            
        return pd.DataFrame(summary_data)
        
    except Exception as e:
        print(f"Error in Tactical Computation: {e}")
        return None
