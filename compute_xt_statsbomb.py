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

    def get_competition_leaderboard(self, competition_id, season_id, max_matches=None):
        """Fetches all matches for a competition and aggregates player impacts."""
        matches = sb.matches(competition_id=competition_id, season_id=season_id)
        if max_matches:
            matches = matches.head(max_matches)
            
        print(f"Processing {len(matches)} matches for Competition {competition_id}...")
        
        all_summaries = []
        for _, match in matches.iterrows():
            try:
                # For leaderboards, we compute xT for each match and aggregate
                # In production, we'd use a pre-fitted model for consistent xT across matches
                actions = self.load_match_data(match.match_id)
                self.xt_model.fit(actions) # Refit or use global
                actions["xt_value"] = self.xt_model.rate(actions)
                
                # Aggregate per match
                m_summary = actions.groupby(["player_name", "team_name"]).agg({
                    "xt_value": "sum",
                    "type_name": "count"
                })
                all_summaries.append(m_summary)
            except Exception as e:
                print(f"Error processing match {match.match_id}: {e}")
                
        if not all_summaries:
            return pd.DataFrame()
            
        # Combine all matches
        leaderboard = pd.concat(all_summaries).groupby(["player_name", "team_name"]).sum()
        leaderboard = leaderboard.sort_values("xt_value", ascending=False)
        return leaderboard

if __name__ == "__main__":
    engine = FootballAnalyticsEngine()
    # Demo: Get Euro 2024 Leaderboard (Top 5 matches)
    df = engine.get_competition_leaderboard(55, 282, max_matches=5)
    print(df.head(20).to_markdown())
