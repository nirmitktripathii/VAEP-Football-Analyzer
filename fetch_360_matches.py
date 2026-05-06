from statsbombpy import sb
import pandas as pd
import warnings

# Suppress warnings
warnings.filterwarnings("ignore", message="credentials were not supplied")

def fetch_all_360_matches():
    print("Fetching competitions...")
    comps = sb.competitions()
    comps_360 = comps[comps['match_available_360'].notna()]
    
    all_matches = []
    for _, row in comps_360.iterrows():
        cid = row['competition_id']
        sid = row['season_id']
        cname = row['competition_name']
        sname = row['season_name']
        
        print(f"Fetching matches for {cname} ({sname})...")
        try:
            m = sb.matches(competition_id=cid, season_id=sid)
            m['competition'] = cname
            m['season'] = sname
            # Keep only matches with available 360
            if 'match_status_360' in m.columns:
                m = m[m['match_status_360'] == 'available']
            all_matches.append(m)
        except Exception as e:
            print(f"Error for {cname}: {e}")
            
    if all_matches:
        final_df = pd.concat(all_matches, ignore_index=True)
        # Select key columns
        cols = ['match_id', 'competition', 'season', 'match_date', 'home_team', 'away_team', 'home_score', 'away_score']
        final_df[cols].to_csv("matches_with_360_data.csv", index=False)
        print(f"Saved {len(final_df)} matches to matches_with_360_data.csv")
    else:
        print("No 360 matches found.")

if __name__ == "__main__":
    fetch_all_360_matches()
