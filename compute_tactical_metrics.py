import pandas as pd
from statsbombpy import sb
import numpy as np
import warnings
import requests

# Suppress warnings
warnings.filterwarnings("ignore", message="credentials were not supplied")

def compute_360_tactical_metrics(match_id):
    print(f"Fetching data for match {match_id}...")
    
    # Fetch events and 360 frames
    try:
        events = sb.events(match_id=match_id)
        frames = sb.frames(match_id=match_id, fmt="dataframe")
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error fetching data: {e}")
        return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None
    
    if frames.empty:
        print("No 360 data found for this match.")
        return None
        
    print(f"Found {len(frames)} 360 frames.")
    
    # Conversion factor: yards to meters
    YARDS_TO_METERS = 0.9144
    
    # Add time and sorted index
    events['time_seconds'] = events['minute'] * 60 + events['second']
    events_sorted = events.sort_values(['time_seconds', 'index'])
    
    # Merge events with frames to get context
    frames_events = pd.merge(frames, events[['id', 'type', 'team', 'player', 'time_seconds', 'pass_recipient']], 
                             on='id')
    
    # Split location [x, y] into separate columns
    frames_events['location_x'] = frames_events['location'].apply(lambda x: x[0])
    frames_events['location_y'] = frames_events['location'].apply(lambda x: x[1])
    
    # Initialize metric storage
    team_metrics = []
    
    # Group by event to analyze each 'snapshot'
    grouped = frames_events.groupby('id')
    
    # To store teammate positions for run tracking
    # Key: event_id, Value: dict of teammate locations
    event_snapshot_data = {}
    
    for event_id, frame in grouped:
        actor = frame[frame['actor'] == True]
        if actor.empty: continue
        
        teammates = frame[frame['teammate'] == True]
        opponents = frame[frame['teammate'] == False]
        
        event_snapshot_data[event_id] = {
            'actor_loc': (actor.iloc[0]['location_x'], actor.iloc[0]['location_y']),
            'teammates': teammates[['location_x', 'location_y']].values.tolist(),
            'opponents': opponents[['location_x', 'location_y']].values.tolist(),
            'team': actor.iloc[0]['team'],
            'time': actor.iloc[0]['time_seconds']
        }

    for event_id, frame in grouped:
        event_info = frame.iloc[0]
        team_name = event_info['team']
        event_type = event_info['type']
        player_name = event_info['player']
        time_s = event_info['time_seconds']
        
        teammates = frame[frame['teammate'] == True]
        opponents = frame[frame['teammate'] == False]
        actor = frame[frame['actor'] == True]
        
        if actor.empty: continue
            
        actor_x, actor_y = actor.iloc[0]['location_x'], actor.iloc[0]['location_y']
        
        # --- Metrics ---
        
        # 1. Congestion around actor (m/s)
        opponents['dist_to_actor'] = np.sqrt((opponents['location_x'] - actor_x)**2 + 
                                             (opponents['location_y'] - actor_y)**2)
        congestion_5m = len(opponents[opponents['dist_to_actor'] <= (5 / YARDS_TO_METERS)])
        
        # 2. Defensive Line Height & Runners "On the Shoulder"
        if not opponents.empty:
            # Deepest defender (min x if attacking right)
            def_line_height = opponents['location_x'].min() 
            
            # Runners on shoulder: Teammates within 2 yards (1.8m) of the defensive line
            # specifically those NOT offside yet (x <= def_line_height) but very close
            runners_on_shoulder = len(teammates[(teammates['location_x'] <= def_line_height) & 
                                               (teammates['location_x'] > def_line_height - 3)])
        else:
            def_line_height = np.nan
            runners_on_shoulder = 0

        # 3. Shape
        if not teammates.empty:
            team_width = (teammates['location_y'].max() - teammates['location_y'].min()) * YARDS_TO_METERS
            team_length = (teammates['location_x'].max() - teammates['location_x'].min()) * YARDS_TO_METERS
        else:
            team_width, team_length = 0, 0
            
        # 4. Run Speed Tracking (for Pass Receivers)
        run_speed = 0
        if event_type == 'Ball Receipt*':
            # Find the corresponding Pass event
            # This is complex in raw events, but we can look for the most recent Pass by the same team
            prev_pass = events_sorted[(events_sorted['team'] == team_name) & 
                                      (events_sorted['type'] == 'Pass') & 
                                      (events_sorted['time_seconds'] < time_s)].tail(1)
            
            if not prev_pass.empty:
                pass_id = prev_pass.iloc[0]['id']
                if pass_id in event_snapshot_data:
                    pass_data = event_snapshot_data[pass_id]
                    dt = time_s - pass_data['time']
                    if 0 < dt < 5:
                        # Find the teammate in the pass frame closest to where the receiver is now
                        # (assuming the runner was one of the teammates in the pass frame)
                        min_dist = float('inf')
                        best_prev_loc = None
                        for tloc in pass_data['teammates']:
                            d = np.sqrt((actor_x - tloc[0])**2 + (actor_y - tloc[1])**2)
                            if d < min_dist:
                                min_dist = d
                                best_prev_loc = tloc
                        
                        if best_prev_loc and min_dist < 30: # 30 yard run limit for matching
                            # Distance covered during the run
                            run_dist = np.sqrt((actor_x - best_prev_loc[0])**2 + (actor_y - best_prev_loc[1])**2)
                            run_speed = (run_dist * YARDS_TO_METERS) / dt # meters / sec
            
        team_metrics.append({
            'event_id': event_id,
            'team': team_name,
            'type': event_type,
            'player': player_name,
            'congestion_5m': congestion_5m,
            'runners_on_shoulder': runners_on_shoulder,
            'def_line_height': def_line_height * YARDS_TO_METERS,
            'team_width': team_width,
            'team_length': team_length,
            'run_speed_ms': run_speed
        })
        
    metrics_df = pd.DataFrame(team_metrics)
    
    # Aggregate by team
    summary = metrics_df.groupby('team').agg({
        'congestion_5m': 'mean',
        'runners_on_shoulder': 'mean',
        'run_speed_ms': 'max', # Peak run speed detected
        'def_line_height': 'mean',
        'team_width': 'mean',
        'team_length': 'mean'
    }).reset_index()
    
    summary.rename(columns={'run_speed_ms': 'peak_run_speed_ms'}, inplace=True)
    
    return summary

if __name__ == "__main__":
    # Test with Euro 2024 Final: Spain vs England
    res = compute_360_tactical_metrics(3943043)
    if res is not None:
        print(res.to_markdown(index=False))
