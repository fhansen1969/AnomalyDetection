"""
Enhanced Anomaly Correlation Visualization System
Creates beautiful, interactive visualizations for understanding anomaly relationships
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import networkx as nx
from datetime import datetime, timedelta
import json
import math

def render_enhanced_correlation_analysis(anomaly, all_anomalies):
    """Render enhanced correlation analysis with multiple visualization options."""
    st.subheader("🔗 Correlation Analysis")
    
    # Get correlations using the existing logic
    related_anomalies = find_correlations(anomaly, all_anomalies)
    
    if not related_anomalies:
        st.info("No significant correlations found with other anomalies")
        return
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Related Anomalies", len(related_anomalies))
    
    with col2:
        high_corr = sum(1 for r in related_anomalies if r['score'] > 0.7)
        st.metric("High Correlation", high_corr)
    
    with col3:
        avg_corr = sum(r['score'] for r in related_anomalies) / len(related_anomalies)
        st.metric("Avg Correlation", f"{avg_corr:.1%}")
    
    with col4:
        # Most common correlation reason
        all_reasons = []
        for r in related_anomalies:
            all_reasons.extend(r['reasons'])
        if all_reasons:
            most_common = max(set(all_reasons), key=all_reasons.count)
            st.metric("Top Factor", most_common)
    
    # Visualization tabs
    viz_tabs = st.tabs([
        "🌐 3D Network", 
        "📊 Correlation Matrix", 
        "🎯 Force Graph", 
        "📈 Timeline Flow",
        "🗺️ Geographic Map",
        "🔥 Heatmap"
    ])
    
    with viz_tabs[0]:
        render_3d_network(anomaly, related_anomalies)
    
    with viz_tabs[1]:
        render_correlation_matrix(anomaly, related_anomalies, all_anomalies)
    
    with viz_tabs[2]:
        render_force_directed_graph(anomaly, related_anomalies)
    
    with viz_tabs[3]:
        render_timeline_flow(anomaly, related_anomalies)
    
    with viz_tabs[4]:
        render_geographic_correlation(anomaly, related_anomalies)
    
    with viz_tabs[5]:
        render_correlation_heatmap(anomaly, related_anomalies)
    
    # Detailed correlation table
    render_correlation_details(related_anomalies)

def render_3d_network(anomaly, correlations):
    """Create an interactive 3D network visualization."""
    st.markdown("### 🌐 3D Correlation Network")
    
    # Create 3D coordinates using force-directed layout
    G = nx.Graph()
    G.add_node(anomaly['id'], type='target')
    
    for corr in correlations[:20]:  # Limit to top 20
        G.add_node(corr['anomaly']['id'], type='related')
        G.add_edge(anomaly['id'], corr['anomaly']['id'], weight=corr['score'])
    
    # 3D spring layout
    pos = nx.spring_layout(G, dim=3, k=3, iterations=50)
    
    # Extract coordinates
    edge_trace = []
    
    for edge in G.edges(data=True):
        x0, y0, z0 = pos[edge[0]]
        x1, y1, z1 = pos[edge[1]]
        
        # Create edge trace with gradient color
        edge_trace.append(go.Scatter3d(
            x=[x0, x1, None],
            y=[y0, y1, None],
            z=[z0, z1, None],
            mode='lines',
            line=dict(
                color=f'rgba(125, 125, 125, {edge[2]["weight"]})',
                width=edge[2]['weight'] * 10
            ),
            hoverinfo='none'
        ))
    
    # Node traces
    node_trace_target = go.Scatter3d(
        x=[pos[anomaly['id']][0]],
        y=[pos[anomaly['id']][1]],
        z=[pos[anomaly['id']][2]],
        mode='markers+text',
        marker=dict(
            size=20,
            color='red',
            symbol='diamond',
            line=dict(color='white', width=2)
        ),
        text=[f"{anomaly['id']}<br>Target"],
        textposition="top center",
        hoverinfo='text',
        hovertext=f"Target Anomaly<br>ID: {anomaly['id']}<br>Score: {anomaly.get('score', 0):.3f}"
    )
    
    # Related nodes
    node_x, node_y, node_z = [], [], []
    node_text = []
    node_color = []
    hover_text = []
    
    for corr in correlations[:20]:
        node_id = corr['anomaly']['id']
        if node_id in pos:
            node_x.append(pos[node_id][0])
            node_y.append(pos[node_id][1])
            node_z.append(pos[node_id][2])
            node_text.append(node_id[:8])
            node_color.append(corr['score'])
            
            # Create hover text
            reasons_text = '<br>'.join(corr['reasons'][:3])
            hover_text.append(
                f"ID: {node_id}<br>"
                f"Correlation: {corr['score']:.1%}<br>"
                f"Score: {corr['anomaly'].get('score', 0):.3f}<br>"
                f"<br>Reasons:<br>{reasons_text}"
            )
    
    node_trace_related = go.Scatter3d(
        x=node_x, y=node_y, z=node_z,
        mode='markers+text',
        marker=dict(
            size=10,
            color=node_color,
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(
                title="Correlation<br>Strength",
                tickformat='.0%'
            ),
            line=dict(width=1, color='white')
        ),
        text=node_text,
        textposition="top center",
        hoverinfo='text',
        hovertext=hover_text
    )
    
    # Create figure
    fig = go.Figure(data=edge_trace + [node_trace_target, node_trace_related])
    
    fig.update_layout(
        title='3D Anomaly Correlation Network',
        showlegend=False,
        height=600,
        scene=dict(
            xaxis=dict(showgrid=False, showticklabels=False, title=''),
            yaxis=dict(showgrid=False, showticklabels=False, title=''),
            zaxis=dict(showgrid=False, showticklabels=False, title=''),
            bgcolor='rgba(0,0,0,0)'
        ),
        margin=dict(l=0, r=0, t=40, b=0)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Add controls
    st.info("🖱️ Drag to rotate • Scroll to zoom • Double-click to reset")

def render_correlation_matrix(anomaly, correlations, all_anomalies):
    """Create a correlation matrix heatmap."""
    st.markdown("### 📊 Correlation Matrix")
    
    # Select top anomalies for matrix
    selected_ids = [anomaly['id']] + [c['anomaly']['id'] for c in correlations[:15]]
    
    # Build correlation matrix
    matrix_data = []
    labels = []
    
    for id1 in selected_ids:
        row = []
        if id1 == anomaly['id']:
            a1 = anomaly
            labels.append(f"{id1} (Target)")
        else:
            a1 = next((c['anomaly'] for c in correlations if c['anomaly']['id'] == id1), None)
            labels.append(id1[:10])
        
        for id2 in selected_ids:
            if id1 == id2:
                row.append(1.0)
            else:
                # Find correlation score
                if id1 == anomaly['id']:
                    corr = next((c['score'] for c in correlations if c['anomaly']['id'] == id2), 0)
                elif id2 == anomaly['id']:
                    corr = next((c['score'] for c in correlations if c['anomaly']['id'] == id1), 0)
                else:
                    # Calculate correlation between two related anomalies
                    corr = calculate_pairwise_correlation(a1, 
                        next((c['anomaly'] for c in correlations if c['anomaly']['id'] == id2), None))
                
                row.append(corr)
        
        matrix_data.append(row)
    
    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=matrix_data,
        x=labels,
        y=labels,
        colorscale='RdBu_r',
        zmid=0.5,
        text=[[f'{val:.2f}' for val in row] for row in matrix_data],
        texttemplate='%{text}',
        textfont={"size": 10},
        hovertemplate='%{x} ↔ %{y}<br>Correlation: %{z:.1%}<extra></extra>'
    ))
    
    fig.update_layout(
        title='Anomaly Correlation Matrix',
        height=600,
        xaxis=dict(tickangle=45),
        yaxis=dict(autorange='reversed')
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_force_directed_graph(anomaly, correlations):
    """Create an interactive force-directed graph."""
    st.markdown("### 🎯 Force-Directed Correlation Graph")
    
    # Create network
    G = nx.Graph()
    
    # Add nodes with attributes
    G.add_node(anomaly['id'], 
               group='target',
               score=float(anomaly.get('score', 0)),
               severity=get_anomaly_severity(anomaly))
    
    # Add related nodes and edges
    for i, corr in enumerate(correlations[:25]):
        node_id = corr['anomaly']['id']
        G.add_node(node_id,
                   group=f"cluster_{i % 5}",  # Group by similarity
                   score=float(corr['anomaly'].get('score', 0)),
                   severity=get_anomaly_severity(corr['anomaly']))
        
        G.add_edge(anomaly['id'], node_id, 
                   weight=corr['score'],
                   reasons=corr['reasons'])
    
    # Create layout with custom parameters
    pos = nx.spring_layout(G, k=2/math.sqrt(len(G.nodes())), iterations=50, weight='weight')
    
    # Create Plotly figure
    fig = go.Figure()
    
    # Add edges with varying thickness and color
    for edge in G.edges(data=True):
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        
        # Calculate edge color based on weight
        weight = edge[2]['weight']
        color = f'rgba({int(255*(1-weight))}, {int(100*weight)}, {int(255*weight)}, {weight})'
        
        fig.add_trace(go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode='lines',
            line=dict(width=weight*8, color=color),
            hoverinfo='text',
            hovertext=f"Correlation: {weight:.1%}<br>" + 
                     "<br>".join(edge[2]['reasons'][:3]),
            showlegend=False
        ))
    
    # Add nodes
    for node in G.nodes(data=True):
        x, y = pos[node[0]]
        
        # Determine node appearance
        if node[1]['group'] == 'target':
            color = 'red'
            size = 40
            symbol = 'star'
        else:
            severity_colors = {
                'Critical': '#ef4444',
                'High': '#f97316',
                'Medium': '#f59e0b',
                'Low': '#10b981',
                'Unknown': '#6b7280'
            }
            color = severity_colors.get(node[1]['severity'], '#6b7280')
            size = 20 + node[1]['score'] * 20
            symbol = 'circle'
        
        fig.add_trace(go.Scatter(
            x=[x], y=[y],
            mode='markers+text',
            marker=dict(
                size=size,
                color=color,
                symbol=symbol,
                line=dict(width=2, color='white')
            ),
            text=node[0][:8],
            textposition="top center",
            hoverinfo='text',
            hovertext=f"ID: {node[0]}<br>Score: {node[1]['score']:.3f}<br>Severity: {node[1]['severity']}",
            showlegend=False
        ))
    
    # Update layout
    fig.update_layout(
        title='Force-Directed Anomaly Network',
        showlegend=False,
        height=600,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor='rgba(0,0,0,0)',
        hovermode='closest'
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_timeline_flow(anomaly, correlations):
    """Create a timeline flow visualization."""
    st.markdown("### 📈 Temporal Correlation Flow")
    
    # Extract timestamps
    events = []
    
    # Add target anomaly
    target_time = parse_timestamp(anomaly.get('timestamp'))
    if target_time:
        events.append({
            'time': target_time,
            'id': anomaly['id'],
            'type': 'target',
            'score': float(anomaly.get('score', 0)),
            'correlation': 1.0
        })
    
    # Add correlated anomalies
    for corr in correlations:
        corr_time = parse_timestamp(corr['anomaly'].get('timestamp'))
        if corr_time:
            events.append({
                'time': corr_time,
                'id': corr['anomaly']['id'],
                'type': 'correlated',
                'score': float(corr['anomaly'].get('score', 0)),
                'correlation': corr['score']
            })
    
    # Sort by time
    events.sort(key=lambda x: x['time'])
    
    if not events:
        st.info("No temporal data available")
        return
    
    # Create timeline
    fig = go.Figure()
    
    # Add timeline base
    times = [e['time'] for e in events]
    fig.add_trace(go.Scatter(
        x=times,
        y=[0] * len(times),
        mode='lines',
        line=dict(color='gray', width=2),
        showlegend=False,
        hoverinfo='none'
    ))
    
    # Add events
    for i, event in enumerate(events):
        # Y position based on correlation strength
        y_pos = event['correlation'] * 0.5 if event['type'] != 'target' else 0
        
        # Color and size
        if event['type'] == 'target':
            color = 'red'
            size = 30
            symbol = 'star'
        else:
            color = f'rgba(99, 102, 241, {event["correlation"]})'
            size = 15 + event['correlation'] * 15
            symbol = 'circle'
        
        fig.add_trace(go.Scatter(
            x=[event['time']],
            y=[y_pos],
            mode='markers+text',
            marker=dict(
                size=size,
                color=color,
                symbol=symbol,
                line=dict(width=2, color='white')
            ),
            text=event['id'][:8],
            textposition="top center",
            hoverinfo='text',
            hovertext=f"ID: {event['id']}<br>Time: {event['time']}<br>Score: {event['score']:.3f}<br>Correlation: {event['correlation']:.1%}",
            showlegend=False
        ))
        
        # Add connection lines for correlated events
        if event['type'] == 'correlated' and target_time:
            fig.add_trace(go.Scatter(
                x=[target_time, event['time']],
                y=[0, y_pos],
                mode='lines',
                line=dict(
                    color=f'rgba(99, 102, 241, {event["correlation"] * 0.5})',
                    width=event['correlation'] * 5,
                    dash='dot'
                ),
                showlegend=False,
                hoverinfo='none'
            ))
    
    # Add annotations for time periods
    if target_time:
        for hours, label in [(1, '1 hour'), (6, '6 hours'), (24, '24 hours')]:
            fig.add_vrect(
                x0=target_time - timedelta(hours=hours),
                x1=target_time + timedelta(hours=hours),
                fillcolor=f'rgba(99, 102, 241, {0.1 / hours})',
                layer="below",
                line_width=0,
                annotation_text=label,
                annotation_position="top left"
            )
    
    fig.update_layout(
        title='Temporal Correlation Flow',
        xaxis_title='Time',
        yaxis_title='Correlation Strength',
        height=500,
        xaxis=dict(type='date'),
        yaxis=dict(range=[-0.1, 0.6]),
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_geographic_correlation(anomaly, correlations):
    """Create a geographic map of correlated anomalies."""
    st.markdown("### 🗺️ Geographic Correlation Map")
    
    # Location coordinates mapping
    location_coords = {
        'us-east-1': {'lat': 38.7469, 'lon': -77.4758, 'name': 'US East'},
        'us-west-2': {'lat': 45.5152, 'lon': -122.6784, 'name': 'US West'},
        'eu-central-1': {'lat': 50.1109, 'lon': 8.6821, 'name': 'EU Central'},
        'ap-south-1': {'lat': 19.0760, 'lon': 72.8777, 'name': 'Asia Pacific'},
        'sa-east-1': {'lat': -23.5505, 'lon': -46.6333, 'name': 'South America'}
    }
    
    # Prepare data
    map_data = []
    
    # Add target anomaly
    target_loc = anomaly.get('location', 'us-east-1')
    if target_loc in location_coords:
        coords = location_coords[target_loc]
        map_data.append({
            'lat': coords['lat'],
            'lon': coords['lon'],
            'name': coords['name'],
            'id': anomaly['id'],
            'type': 'Target',
            'score': float(anomaly.get('score', 0)),
            'size': 30
        })
    
    # Add correlated anomalies
    for corr in correlations:
        loc = corr['anomaly'].get('location')
        if loc and loc in location_coords:
            coords = location_coords[loc]
            map_data.append({
                'lat': coords['lat'],
                'lon': coords['lon'],
                'name': coords['name'],
                'id': corr['anomaly']['id'],
                'type': 'Correlated',
                'score': float(corr['anomaly'].get('score', 0)),
                'correlation': corr['score'],
                'size': 10 + corr['score'] * 20
            })
    
    if not map_data:
        st.info("No geographic data available")
        return
    
    # Create map
    df = pd.DataFrame(map_data)
    
    fig = px.scatter_geo(
        df,
        lat='lat',
        lon='lon',
        size='size',
        color='type',
        hover_name='id',
        hover_data=['name', 'score'],
        color_discrete_map={'Target': 'red', 'Correlated': 'blue'},
        title='Geographic Distribution of Correlated Anomalies'
    )
    
    # Add connection lines
    if len(df) > 1 and target_loc in location_coords:
        target_coords = location_coords[target_loc]
        
        for _, row in df.iterrows():
            if row['type'] == 'Correlated':
                fig.add_trace(go.Scattergeo(
                    lon=[target_coords['lon'], row['lon']],
                    lat=[target_coords['lat'], row['lat']],
                    mode='lines',
                    line=dict(
                        width=row.get('correlation', 0.5) * 5,
                        color='rgba(99, 102, 241, 0.3)'
                    ),
                    showlegend=False
                ))
    
    fig.update_layout(
        geo=dict(
            projection_type='natural earth',
            showland=True,
            landcolor='rgb(243, 243, 243)',
            coastlinecolor='rgb(204, 204, 204)',
            showcountries=True,
            countrycolor='rgb(204, 204, 204)'
        ),
        height=600
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_correlation_heatmap(anomaly, correlations):
    """Create a multi-dimensional correlation heatmap."""
    st.markdown("### 🔥 Correlation Factor Heatmap")
    
    # Prepare data for heatmap
    factors = ['Network', 'Location', 'Time', 'Pattern', 'Model']
    anomaly_ids = [anomaly['id'][:10] + ' (Target)'] + [c['anomaly']['id'][:10] for c in correlations[:10]]
    
    # Create heatmap data
    heatmap_data = []
    
    for corr in [{'anomaly': anomaly, 'score': 1.0}] + correlations[:10]:
        row = []
        
        # Calculate individual factor contributions
        # This is a simplified version - in practice, you'd calculate these properly
        if corr['anomaly']['id'] == anomaly['id']:
            row = [1.0] * len(factors)  # Perfect correlation with self
        else:
            # Network factor
            network_score = 0.8 if anomaly.get('src_ip') == corr['anomaly'].get('src_ip') else 0.2
            
            # Location factor
            location_score = 0.9 if anomaly.get('location') == corr['anomaly'].get('location') else 0.1
            
            # Time factor (simplified)
            time_score = corr.get('score', 0.5) * 0.8
            
            # Pattern factor
            pattern_score = 0.7 if anomaly.get('model') == corr['anomaly'].get('model') else 0.3
            
            # Model factor
            model_score = abs(float(anomaly.get('score', 0)) - float(corr['anomaly'].get('score', 0)))
            model_score = 1 - min(model_score, 1)  # Invert so similar scores = high correlation
            
            row = [network_score, location_score, time_score, pattern_score, model_score]
        
        heatmap_data.append(row)
    
    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data,
        x=factors,
        y=anomaly_ids,
        colorscale='Viridis',
        text=[[f'{val:.2f}' for val in row] for row in heatmap_data],
        texttemplate='%{text}',
        textfont={"size": 12},
        hovertemplate='%{y}<br>%{x}: %{z:.1%}<extra></extra>'
    ))
    
    fig.update_layout(
        title='Correlation Factors by Anomaly',
        height=500,
        xaxis_title='Correlation Factors',
        yaxis_title='Anomalies'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Factor importance
    st.markdown("#### Factor Importance")
    
    # Calculate average importance per factor
    avg_importance = [sum(row[i] for row in heatmap_data[1:]) / len(heatmap_data[1:]) 
                     for i in range(len(factors))]
    
    fig_importance = go.Figure(data=[
        go.Bar(
            x=factors,
            y=avg_importance,
            marker_color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57'],
            text=[f'{val:.1%}' for val in avg_importance],
            textposition='auto'
        )
    ])
    
    fig_importance.update_layout(
        title='Average Factor Contribution to Correlations',
        yaxis_title='Average Contribution',
        height=300
    )
    
    st.plotly_chart(fig_importance, use_container_width=True)

def render_correlation_details(correlations):
    """Render detailed correlation information."""
    st.markdown("### 📋 Correlation Details")
    
    # Create expandable sections for each correlation
    for i, corr in enumerate(correlations[:10]):
        correlation_score = corr['score']
        severity = get_anomaly_severity(corr['anomaly'])
        
        # Color code based on correlation strength
        if correlation_score > 0.8:
            color = "🔴"
            strength = "Very High"
        elif correlation_score > 0.6:
            color = "🟠"
            strength = "High"
        elif correlation_score > 0.4:
            color = "🟡"
            strength = "Moderate"
        else:
            color = "🟢"
            strength = "Low"
        
        with st.expander(
            f"{color} {corr['anomaly']['id']} - {strength} Correlation ({correlation_score:.1%})"
        ):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Anomaly Score", f"{float(corr['anomaly'].get('score', 0)):.3f}")
                st.metric("Model", corr['anomaly'].get('model', 'Unknown'))
            
            with col2:
                st.metric("Severity", severity)
                st.metric("Status", corr['anomaly'].get('status', 'Unknown'))
            
            with col3:
                st.metric("Location", corr['anomaly'].get('location', 'Unknown'))
                timestamp = parse_timestamp(corr['anomaly'].get('timestamp'))
                if timestamp:
                    st.metric("Time", timestamp.strftime('%Y-%m-%d %H:%M'))
            
            # Correlation reasons
            st.markdown("**Correlation Factors:**")
            for reason in corr['reasons']:
                st.markdown(f"• {reason}")
            
            # Action buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"🔍 Analyze", key=f"analyze_corr_{i}"):
                    st.session_state.selected_anomaly = corr['anomaly']
                    st.rerun()
            
            with col2:
                if st.button(f"📊 Compare", key=f"compare_corr_{i}"):
                    st.info("Comparison view coming soon!")

# Helper functions

def find_correlations(anomaly, all_anomalies):
    """Find correlated anomalies using the existing logic."""
    # This uses your existing correlation logic
    # Just returning the structure expected by the visualizations
    
    anomaly_id = anomaly.get('id')
    anomaly_score = float(anomaly.get('score', 0))
    anomaly_model = anomaly.get('model')
    anomaly_location = anomaly.get('location')
    anomaly_src_ip = anomaly.get('src_ip')
    
    related_anomalies = []
    
    for a in all_anomalies:
        if a.get('id') == anomaly_id:
            continue
        
        correlation_score = 0
        correlation_reasons = []
        
        # Same source IP
        if a.get('src_ip') == anomaly_src_ip and anomaly_src_ip:
            correlation_score += 0.4
            correlation_reasons.append("Same source IP")
        
        # Same location
        if a.get('location') == anomaly_location:
            correlation_score += 0.2
            correlation_reasons.append("Same location")
        
        # Similar score
        if abs(float(a.get('score', 0)) - anomaly_score) < 0.1:
            correlation_score += 0.2
            correlation_reasons.append("Similar anomaly score")
        
        # Same model
        if a.get('model') == anomaly_model:
            correlation_score += 0.1
            correlation_reasons.append("Detected by same model")
        
        # Time proximity
        try:
            a_time = parse_timestamp(a.get('timestamp'))
            anomaly_time = parse_timestamp(anomaly.get('timestamp'))
            if a_time and anomaly_time:
                time_diff = abs((a_time - anomaly_time).total_seconds())
                if time_diff < 3600:  # Within 1 hour
                    correlation_score += 0.3
                    correlation_reasons.append("Time proximity (within 1 hour)")
        except:
            pass
        
        if correlation_score > 0.3:
            related_anomalies.append({
                'anomaly': a,
                'score': correlation_score,
                'reasons': correlation_reasons
            })
    
    # Sort by correlation score
    related_anomalies.sort(key=lambda x: x['score'], reverse=True)
    
    return related_anomalies

def calculate_pairwise_correlation(a1, a2):
    """Calculate correlation between two anomalies."""
    if not a1 or not a2:
        return 0
    
    score = 0
    
    # Similar logic to find_correlations but between any two anomalies
    if a1.get('src_ip') == a2.get('src_ip') and a1.get('src_ip'):
        score += 0.4
    
    if a1.get('location') == a2.get('location'):
        score += 0.2
    
    if abs(float(a1.get('score', 0)) - float(a2.get('score', 0))) < 0.1:
        score += 0.2
    
    if a1.get('model') == a2.get('model'):
        score += 0.1
    
    return min(score, 1.0)

def get_anomaly_severity(anomaly):
    """Get severity from anomaly."""
    if 'severity' in anomaly:
        return anomaly['severity']
    
    analysis = anomaly.get('analysis', {})
    if isinstance(analysis, dict):
        return analysis.get('severity', 'Unknown')
    
    return 'Unknown'

def parse_timestamp(timestamp):
    """Parse timestamp from various formats."""
    if not timestamp:
        return None
    
    if isinstance(timestamp, datetime):
        return timestamp
    
    if isinstance(timestamp, str):
        try:
            return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except:
            return None
    
    return None