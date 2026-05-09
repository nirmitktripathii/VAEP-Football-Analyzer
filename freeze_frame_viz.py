import plotly.graph_objects as go
import numpy as np
import pandas as pd
from statsbombpy import sb
from scipy.spatial import Voronoi, ConvexHull
from shapely.geometry import Polygon
import streamlit as st

@st.cache_data(show_spinner=False)
def plot_tactical_evolution_plotly(match_id, action_sequence, team_name, opponent_name):
    """
    Highly optimized, clipped, and data-stable interactive tactical animation.
    """
    try:
        # 1. Fetch frames with specialized error handling for missing data
        import requests
        try:
            frames_all = sb.frames(match_id=match_id, fmt="dataframe")
        except Exception as e:
            if "404" in str(e):
                return None # Graceful exit for older matches without 360 data
            raise e
            
        pitch_poly = Polygon([(0, 0), (120, 0), (120, 80), (0, 80)])
        
        fig = go.Figure()

        # --- ANIMATION CORE: STABLE TRACE SLOTS ---
        plotly_frames = []
        hull_areas_dict = {}
        
        # Fetch lineups once for efficiency
        try:
            lineups = sb.lineups(match_id=match_id)
            jersey_map = {}
            for team_df in lineups.values():
                for _, row in team_df.iterrows():
                    jersey_map[row['player_name']] = row['jersey_number']
        except:
            jersey_map = {}
        
        for step, action in enumerate(action_sequence):
            # Default empty traces (7 slots now: 0-6)
            current_traces = [go.Scatter(x=[None], y=[None], showlegend=False) for _ in range(7)]
            
            event_id = action.get('original_event_id')
            frame_data = frames_all[frames_all.id == event_id] if event_id is not None else pd.DataFrame()
            
            if frame_data.empty:
                # 360 Data Missing - Add Ball at default action start position
                ball_pos = [action['start_x'] * 120/105, action['start_y'] * 80/68]
                current_traces[6] = go.Scatter(
                    x=[ball_pos[0]], y=[ball_pos[1]], 
                    mode='markers', 
                    marker=dict(size=10, color='white', opacity=0.3, line=dict(width=1, color='gray')), 
                    name='Ball (Approx)', hoverinfo='skip'
                )
                current_traces.append(go.Scatter(
                    x=[60], y=[40], mode='text',
                    text=["360 Data Unavailable for this Phase"],
                    textfont=dict(color='gray', size=14, family="Arial Black"),
                    showlegend=False, hoverinfo='skip'
                ))
                plotly_frames.append(go.Frame(data=current_traces, name=str(step)))
                hull_areas_dict[step] = 0
                continue
            
            points = np.array(frame_data['location'].tolist())
            is_actor = frame_data.get('actor', pd.Series([False]*len(frame_data))).values
            
            # Action Data
            p_name = action.get('short_name', 'Unknown')
            a_type = action.get('type_name', 'Action').upper()
            vaep = action.get('vaep_value', 0)
            xt = action.get('xt_value', 0)
            act_team = action.get('team_name')
            
            # --- TEAM ALIGNMENT ---
            is_scoring_team = (act_team == team_name)
            scoring_team_mask = (frame_data['teammate'] == True) if is_scoring_team else (frame_data['teammate'] == False)
            
            # 1. TM VORONOI
            tm_points = points[scoring_team_mask]
            if len(tm_points) >= 4:
                try:
                    vor = Voronoi(tm_points)
                    for region_idx in vor.point_region:
                        region = vor.regions[region_idx]
                        if -1 not in region and len(region) > 0:
                            polygon = Polygon([vor.vertices[i] for i in region])
                            clipped = polygon.intersection(pitch_poly)
                            if not clipped.is_empty:
                                x, y = clipped.exterior.xy
                                current_traces[0] = go.Scatter(x=list(x), y=list(y), fill="toself", fillcolor='rgba(0, 255, 204, 0.05)', line=dict(color='rgba(0, 255, 204, 0.1)', width=0.5), showlegend=False, hoverinfo='skip')
                except: pass

            # 2. OP VORONOI
            opp_points = points[~scoring_team_mask]
            if len(opp_points) >= 4:
                try:
                    vor_op = Voronoi(opp_points)
                    for region_idx in vor_op.point_region:
                        region = vor_op.regions[region_idx]
                        if -1 not in region and len(region) > 0:
                            polygon = Polygon([vor_op.vertices[i] for i in region])
                            clipped = polygon.intersection(pitch_poly)
                            if not clipped.is_empty:
                                x, y = clipped.exterior.xy
                                current_traces[1] = go.Scatter(x=list(x), y=list(y), fill="toself", fillcolor='rgba(255, 51, 102, 0.05)', line=dict(color='rgba(255, 51, 102, 0.1)', width=0.5), showlegend=False, hoverinfo='skip')
                except: pass

            # 3. DEFENSIVE HULL & STRESS
            hull_area = 0
            if len(opp_points) >= 3:
                try:
                    hull = ConvexHull(opp_points)
                    hull_area = round(float(hull.volume), 2)
                    h_pts = opp_points[hull.vertices]
                    current_traces[2] = go.Scatter(x=np.append(h_pts[:, 0], h_pts[0, 0]), y=np.append(h_pts[:, 1], h_pts[0, 1]), fill="toself", fillcolor='rgba(255, 51, 102, 0.2)', line=dict(color='rgba(255, 51, 102, 0.5)', width=1, dash='dot'), name='Defensive Block', hoverinfo='skip')
                except: pass

            # 4. SCORING TEAM MARKERS
            tm_pts = points[scoring_team_mask]
            tm_hovers, tm_labels = [], []
            tm_actors = is_actor[scoring_team_mask]
            
            for i in range(len(tm_pts)):
                j_num = frame_data[scoring_team_mask].iloc[i].get('jersey_number')
                if pd.isna(j_num) or j_num == '': 
                    j_num = jersey_map.get(action.get('player_name'), '') if tm_actors[i] else ''
                
                label = str(int(j_num)) if (pd.notnull(j_num) and j_num != '') else 'T'
                tm_labels.append(label)
                if tm_actors[i]:
                    tm_hovers.append(f"<b>{p_name} (#{label})</b><br>VAEP: {round(vaep, 2)}<br>xT: {round(xt, 2)}")
                else:
                    tm_hovers.append(f"Teammate (#{label})")
            
            current_traces[3] = go.Scatter(
                x=tm_pts[:,0], y=tm_pts[:,1], mode='markers+text',
                marker=dict(size=18, color='#00FFCC', line=dict(width=1.5, color='white')),
                text=tm_labels, textfont=dict(color='black', size=9, family="Arial Black"),
                textposition="middle center", name=team_name, hovertext=tm_hovers, hoverinfo='text'
            )

            # 5. OPPONENT MARKERS
            opp_pts = points[~scoring_team_mask]
            opp_labels = []
            for i in range(len(opp_pts)):
                oj = frame_data[~scoring_team_mask].iloc[i].get('jersey_number')
                opp_labels.append(str(int(oj)) if (pd.notnull(oj) and oj != '') else 'O')
                
            current_traces[4] = go.Scatter(
                x=opp_pts[:,0], y=opp_pts[:,1], mode='markers+text',
                marker=dict(size=18, color='#FF3366', symbol='circle', line=dict(width=1.5, color='white')),
                text=opp_labels, textfont=dict(color='white', size=9, family="Arial Black"),
                textposition="middle center", name=opponent_name, hoverinfo='skip'
            )

            # 6. ACTOR HIGHLIGHT
            if any(is_actor):
                act_pos = points[is_actor][0]
                current_traces[5] = go.Scatter(
                    x=[act_pos[0]], y=[act_pos[1]], 
                    mode='markers', 
                    marker=dict(size=34, color='rgba(244, 208, 63, 0.2)', line=dict(width=2, color='#F4D03F')), 
                    showlegend=False, hoverinfo='skip'
                )
                ball_pos = act_pos
            else:
                ball_pos = [action['start_x'] * 120/105, action['start_y'] * 80/68]

            # 7. THE BALL (White Dot)
            current_traces[6] = go.Scatter(
                x=[ball_pos[0]], y=[ball_pos[1]], 
                mode='markers', 
                marker=dict(size=10, color='white', line=dict(width=1, color='black')), 
                name='Ball', hoverinfo='skip'
            )

            # 8. SEQUENCE & METRICS
            hull_areas_dict[step] = hull_area
            fig_frame_traces = list(current_traces)
            if hull_area > 0:
                fig_frame_traces.append(go.Scatter(
                    x=[110], y=[75], mode='text',
                    text=[f"Def. Area: {hull_area}m²"],
                    textfont=dict(color='#FF3366', size=12, family="Arial Black"),
                    showlegend=False, hoverinfo='skip'
                ))
            
            for i in range(step):
                pa = action_sequence[i]
                fig_frame_traces.append(go.Scatter(
                    x=[pa['start_x'] * 120/105], y=[pa['start_y'] * 80/68],
                    mode='markers+text',
                    marker=dict(size=20, color='rgba(14, 17, 23, 0.8)', line=dict(width=1, color='#F4D03F')),
                    text=[str(i+1)], textfont=dict(color='#F4D03F', size=10),
                    textposition="middle center", showlegend=False, hoverinfo='skip'
                ))

            is_dribble = "dribble" in action['type_name'].lower()
            fig_frame_traces.append(go.Scatter(
                x=[ball_pos[0], action['end_x'] * 120/105], y=[ball_pos[1], action['end_y'] * 80/68],
                mode='lines+markers',
                line=dict(color='#F4D03F', width=4, dash='dash' if is_dribble else 'solid'),
                marker=dict(symbol='arrow', size=15, angleref='previous', standoff=10),
                name='Active Play', showlegend=False, hoverinfo='skip'
            ))

            fig_frame_traces.append(go.Scatter(
                x=[ball_pos[0]], y=[ball_pos[1]],
                mode='markers', 
                marker=dict(size=14, color='white', line=dict(width=3, color='black'), symbol='circle-dot'),
                name='BALL', showlegend=True
            ))

            plotly_frames.append(go.Frame(data=fig_frame_traces, name=str(step)))

        # --- LAYOUT & PITCH ---
        # Pitch Boundary
        fig.add_shape(type="rect", x0=0, y0=0, x1=120, y1=80, line_color="#444444", fillcolor="#0E1117", layer="below")
        # Markings
        for x in [0, 102]: fig.add_shape(type="rect", x0=x, y0=18, x1=x+18, y1=62, line_color="#444444", line_width=1)
        fig.add_shape(type="line", x0=60, y0=0, x1=60, y1=80, line_color="#444444")
        fig.add_shape(type="circle", x0=50.85, y0=30.85, x1=69.15, y1=49.15, line_color="#444444")

        # Initial Trace Setup
        if plotly_frames:
            for trace in plotly_frames[0].data: fig.add_trace(trace)

        fig.update_layout(
            title=dict(text=f"TACTICAL INTELLIGENCE EVOLUTION: {team_name.upper()} BUILDUP", font=dict(size=20, color='white', family="Arial Black"), x=0.5, y=0.97),
            paper_bgcolor='#0E1117', plot_bgcolor='#0E1117',
            margin=dict(l=5, r=5, t=50, b=5), height=700,
            xaxis=dict(showgrid=False, zeroline=False, visible=False, range=[-1, 121]),
            yaxis=dict(showgrid=False, zeroline=False, visible=False, range=[-1, 81], scaleanchor="x", scaleratio=1),
            updatemenus=[dict(
                type="buttons", x=0.05, y=0.03, showactive=False,
                buttons=[dict(label="▶ PLAY SEQUENCE", method="animate", args=[None, {"frame": {"duration": 1000, "redraw": True}, "fromcurrent": True, "transition": {"duration": 500, "easing": "cubic-in-out"}}])]
            )],
            sliders=[dict(
                steps=[dict(method="animate", args=[[str(k)], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}], label=f"Phase {k+1}") for k in range(len(plotly_frames))],
                active=0, transition={"duration": 300},
                currentvalue={"prefix": "Current Stage: ", "font": {"color": "#00FFCC", "size": 15}, "offset": 20},
                pad={"t": 30, "b": 10}, len=0.9, x=0.05, y=0, font=dict(color='white')
            )],
            legend=dict(orientation="h", yanchor="bottom", y=0.05, xanchor="right", x=0.95, font=dict(color='white', size=11))
        )
        
        fig.frames = plotly_frames
        return fig, hull_areas_dict

    except Exception as e:
        print(f"Error in tactical evolution: {e}")
        return None, {}
