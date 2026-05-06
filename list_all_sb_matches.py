from statsbombpy import sb
import pandas as pd
import warnings

# Suppress the NoAuthWarning for clean output
warnings.filterwarnings("ignore", message="credentials were not supplied")

def list_all_available_matches():
    print("Fetching all available competitions from StatsBomb Open Data...")
    comps = sb.competitions()
    
    # We want to group by competition name and season
    all_matches_list = []
    
    print(f"Found {len(comps)} Competition-Season combinations.")
    print("-" * 80)
    
    for index, row in comps.iterrows():
        comp_name = row['competition_name']
        season_name = row['season_name']
        cid = row['competition_id']
        sid = row['season_id']
        
        print(f"Fetching matches for: {comp_name} ({season_name})...")
        
        try:
            matches = sb.matches(competition_id=cid, season_id=sid)
            # Add competition info to each match row
            matches['competition'] = comp_name
            matches['season'] = season_name
            
            # Select relevant columns
            match_subset = matches[[
                'match_id', 'competition', 'season', 'match_date', 
                'home_team', 'away_team', 'home_score', 'away_score'
            ]]
            all_matches_list.append(match_subset)
        except Exception as e:
            print(f"Could not fetch matches for {comp_name}: {e}")
            
    if all_matches_list:
        final_df = pd.concat(all_matches_list, ignore_index=True)
        
        # Save to CSV for the user
        output_file = "all_statsbomb_open_matches.csv"
        final_df.to_csv(output_file, index=False)
        
        print("-" * 80)
        print(f"SUCCESS! Found a total of {len(final_df)} matches.")
        print(f"Full list saved to: {output_file}")
        
        # Display a summary table
        print("\n--- Summary by Competition ---")
        summary = final_df.groupby(['competition', 'season']).size().reset_index(name='match_count')
        print(summary.to_markdown(index=False))
        
        return final_df
    else:
        print("No matches found.")
        return None

if __name__ == "__main__":
    list_all_available_matches()
