import pandas as pd
from statsbombpy import sb
from socceraction.data.statsbomb import StatsBombLoader
import socceraction.spadl as spadl
import socceraction.xthreat as xT
import socceraction.vaep as vaep
import socceraction.vaep.formula as vaep_formula
import os
import warnings

# Suppress NoAuthWarning from statsbombpy
warnings.filterwarnings("ignore", category=UserWarning)

class FootballAnalyticsEngine:
    def __init__(self, l=16, w=12):
        self.loader = StatsBombLoader()
        self.l = l
        self.w = w
        self.xt_model = xT.ExpectedThreat(l=l, w=w)

    def load_match_data(self, match_id):
        """Loads and converts StatsBomb data to SPADL actions."""
        print(f"Loading match {match_id}...")
        df_teams = self.loader.teams(match_id)
        df_players = self.loader.players(match_id)
        df_actions = self.loader.events(match_id)
        
        # Convert to SPADL
        actions = spadl.statsbomb.convert_to_actions(df_actions, home_team_id=df_teams.iloc[0].team_id)
        
        # Add names for readability
        actions = (
            actions.merge(spadl.actiontypes_df(), how="left")
            .merge(spadl.results_df(), how="left")
            .merge(df_players[["player_id", "player_name", "nickname"]], how="left")
            .merge(df_teams[["team_id", "team_name"]], how="left")
        )
        # Use nickname if available
        actions["player_name"] = actions["nickname"].fillna(actions["player_name"])
        return actions

    def train_xt_model(self, match_ids):
        """Trains the xT model on a set of matches."""
        print(f"Training xT model on {len(match_ids)} matches...")
        all_actions = []
        for mid in match_ids:
            try:
                all_actions.append(self.load_match_data(mid))
            except Exception as e:
                print(f"Failed to load match {mid}: {e}")
        
        if not all_actions:
            return False
            
        combined_actions = pd.concat(all_actions)
        self.xt_model.fit(combined_actions)
        print("xT Model trained successfully.")
        return True

    def compute_metrics(self, match_id):
        """Computes xT and VAEP for a specific match."""
        actions = self.load_match_data(match_id)
        
        print("Computing Expected Threat (xT)...")
        # xT only applies to successful offensive actions (passes, dribbles)
        actions["xt_value"] = self.xt_model.rate(actions)
        
        # For commercial portal, we'd also load pre-trained VAEP models
        # Here we provide a simplified 'Action Value' based on xT + Shot Result
        print("Summarizing Player Performance...")
        summary = actions.groupby(["player_name", "team_name"]).agg({
            "xt_value": "sum",
            "type_name": "count"
        }).rename(columns={"type_name": "total_actions"})
        
        # Sort by impact
        summary = summary.sort_values("xt_value", ascending=False)
        return summary, actions

if __name__ == "__main__":
    engine = FootballAnalyticsEngine()
    
    # Let's use Euro 2024 Final: Spain vs England (3943043)
    # Step 1: In a real app, we'd train on the whole tournament
    # For this prototype, we'll "train" and "predict" on the same match to show the pipe
    match_id = 3943043 
    
    if engine.train_xt_model([match_id]):
        summary, actions = engine.compute_metrics(match_id)
        print("\nTop Players by Expected Threat (xT) - Euro 2024 Final:")
        print(summary.head(10).to_markdown())
        
        # Save to CSV for the Portal to pick up
        summary.to_csv("euro_2024_xt_summary.csv")
        print(f"\nAnalysis complete. Results saved to euro_2024_xt_summary.csv")
