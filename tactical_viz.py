import matplotlib.pyplot as plt
import matplotlib.patches as patches

def plot_tactical_summary_pitch(summary_df):
    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    for i, ax in enumerate(axes):
        team_name = summary_df.iloc[i]['team']
        stats = summary_df.iloc[i]
        ax.set_xlim(0, 120); ax.set_ylim(0, 80)
        ax.add_patch(patches.Rectangle((0, 0), 120, 80, fill=False, edgecolor='black', linewidth=2))
        ax.plot([60, 60], [0, 80], color='black')
        line_x = stats['def_line_height']
        ax.axvline(x=line_x, color='red', linestyle='--', label='Defensive Line', alpha=0.7)
        width = stats['team_width']; length = stats['team_length']
        ax.add_patch(patches.Rectangle((line_x, 40 - width/2), length, width, color='blue', alpha=0.2, label='Team Shape'))
        congestion_radius = stats['congestion_5m'] * 2
        ax.add_patch(patches.Circle((80, 40), congestion_radius, color='orange', alpha=0.4, label='Congestion Zone'))
        ax.set_title(f"Tactical Structure: {team_name}")
        ax.set_aspect('equal'); ax.axis('off')
        if i == 0: ax.legend(loc='upper left')
    plt.tight_layout()
    return fig
