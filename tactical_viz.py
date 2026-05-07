import matplotlib.pyplot as plt
import matplotlib.patches as patches

def plot_tactical_summary_pitch(summary_df):
    fig, axes = plt.subplots(1, 2, figsize=(18, 9), facecolor='#111111')
    for i, ax in enumerate(axes):
        team_name = summary_df.iloc[i]['team']
        stats = summary_df.iloc[i]
        positions = stats.get('player_positions', [])
        ax.set_facecolor('#111111')
        ax.set_xlim(0, 120); ax.set_ylim(0, 80)
        ax.add_patch(patches.Rectangle((0, 0), 120, 80, fill=True, color='#1e1e1e', edgecolor='white', linewidth=2, zorder=0))
        ax.plot([60, 60], [0, 80], color='white', alpha=0.5, zorder=1)
        ax.add_patch(patches.Circle((60, 40), 9.15, fill=False, edgecolor='white', alpha=0.5, zorder=1))
        
        for p in positions:
            name = p.get('player_name', 'Player')
            short_name = name.split(' ')[-1] if ' ' in name else name
            ax.scatter(p['x'], p['y'], s=200, color='#00FFCC', edgecolor='white', linewidth=1, zorder=5)
            ax.text(p['x'], p['y'] - 3, short_name, color='white', ha='center', fontsize=9, fontweight='bold', zorder=6)

        line_x = stats['def_line_height']
        ax.axvline(x=line_x, color='#FF3366', linestyle='--', label='Defensive Line', alpha=0.8, linewidth=2, zorder=2)
        width = stats['team_width']; length = stats['team_length']
        avg_x = sum([p['x'] for p in positions]) / len(positions) if positions else 60
        avg_y = sum([p['y'] for p in positions]) / len(positions) if positions else 40
        ax.add_patch(patches.Rectangle((avg_x - length/2, avg_y - width/2), length, width, color='#00CCFF', alpha=0.1, label='Team Block', zorder=1))
        ax.set_title(f"{team_name}", color='white', fontsize=16, fontweight='bold', pad=15)
        ax.set_aspect('equal'); ax.axis('off')
        if i == 0:
            legend = ax.legend(loc='upper left', facecolor='#111111', edgecolor='white')
            plt.setp(legend.get_texts(), color='white')
    plt.tight_layout()
    return fig
