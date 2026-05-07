import json
import os
from datetime import datetime

class TacticalDataStore:
    def __init__(self, store_path="tactical_intelligence_vault.json"):
        self.store_path = store_path
        if not os.path.exists(self.store_path):
            with open(self.store_path, 'w') as f:
                json.dump({"metadata": {"version": "1.0", "provider": "VAEP-360-Tactical"}, "matches": {}}, f)

    def save_match_metrics(self, match_id, match_info, team_summary):
        with open(self.store_path, 'r') as f: data = json.load(f)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "match_info": match_info,
            "tactical_kpis": team_summary.to_dict(orient='records')
        }
        data["matches"][str(match_id)] = entry
        with open(self.store_path, 'w') as f: json.dump(data, f, indent=4)
