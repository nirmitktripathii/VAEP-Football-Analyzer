import sys
import os
import pandas as pd

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from compute_tactical_metrics import compute_360_tactical_metrics

def test_match(match_id):
    print(f"Testing Match ID: {match_id}")
    summary = compute_360_tactical_metrics(match_id)
    if summary is not None:
        print("Success!")
        print(summary[['team', 'def_line_height_m', 'def_line_height_yds', 'team_width_m', 'team_width_yds']])
        for i, row in summary.iterrows():
            print(f"Positions for {row['team']}: {len(row['player_positions'])} players")
    else:
        print("Failed: Summary is None")

if __name__ == "__main__":
    # Test Euro 2024 Final
    test_match(3943043)
    
    # Test Bundesliga Match
    test_match(3895302)
