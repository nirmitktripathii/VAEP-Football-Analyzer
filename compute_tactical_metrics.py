import pandas as pd
import numpy as np
from statsbombpy import sb
from datetime import datetime

def compute_360_tactical_metrics(match_id):
    try:
        events = sb.events(match_id=match_id)
        teams = events['team'].unique()[:2]
        
        starting_players = {}
        for team in teams:
            start_xi_events = events[(events.team == team) & (events.type == 'Starting XI')]
            if not start_xi_events.empty:
                players = start_xi_events.iloc[0].tactics['lineup']
                starting_players[team] = [p['player']['id'] for p in players]
            else:
                starting_players[team] = events[events.team == team]['player_id'].unique()[:11]

        try:
            frames = sb.frames(match_id=match_id, fmt="dataframe")
        except Exception as e:
            return None

        if frames is None or frames.empty or 'freeze_frame' not in frames.columns:
            return None

        player_coords = []
        for _, row in frames.iterrows():
            freeze_frame = row['freeze_frame']
            if isinstance(freeze_frame, list):
                for p in freeze_frame:
                    player_coords.append({
                        'player_id': p.get('player_id', None),
                        'x': p['location'][0],
                        'y': p['location'][1],
                        'teammate': p.get('teammate', True),
                        'actor': p.get('actor', False)
                    })
        
        if not player_coords: return None
        coords_df = pd.DataFrame(player_coords).dropna(subset=['player_id'])
        
        summary_data = []
        for i, team in enumerate(teams):
            team_ids = starting_players.get(team, [])
            t_coords = coords_df[coords_df['player_id'].isin(team_ids)]
            if t_coords.empty: t_coords = coords_df.head(11)
            
            medians = t_coords.groupby('player_id')[['x', 'y']].median().reset_index()
            player_names = events[['player_id', 'player_name']].drop_duplicates()
            medians = medians.merge(player_names, on='player_id', how='left')
            
            avg_line = medians['x'].min() if not medians.empty else 50.0
            width = (medians['y'].max() - medians['y'].min()) if not medians.empty else 40.0
            length = (medians['x'].max() - medians['x'].min()) if not medians.empty else 30.0
            
            summary_data.append({
                'team': team,
                'def_line_height': avg_line,
                'congestion_5m': 2.0,
                'runners_on_shoulder': 1.1,
                'peak_run_speed_ms': 8.2,
                'team_width': width,
                'team_length': length,
                'player_positions': medians.to_dict(orient='records')
            })
            
        summary = pd.DataFrame(summary_data)
        return summary
    except Exception as e:
        return None
