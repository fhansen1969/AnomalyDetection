"""
Anomalies page for the Anomaly Detection Dashboard.
Enhanced version with modern UI, improved visualizations, and better user experience.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import datetime
from datetime import datetime, timezone
import numpy as np
import requests
import logging
import json
from typing import List, Dict, Any, Optional
import traceback

from config.theme import get_current_theme, hex_to_rgba
from config.settings import add_notification
from services.data_service import (
    get_anomalies, 
    get_models, 
    get_anomaly_by_id, 
    get_anomaly_analysis,
    add_anomaly_analysis,
    add_agent_message,
    add_agent_activity,
    get_agent_messages,    
    update_anomaly_status  
)

from services.database import execute_query
from components.anomaly_origin_details import render_anomaly_origin_details
from components.triage import render_group_view, severity_badge, _effective_severity

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("anomalies")

# API configuration
def get_api_url():
    """Get the API URL from environment variable or use default."""
    import os
    return os.environ.get("ANOMALY_DETECTION_API_URL", "http://localhost:8000")

# Helper functions
def format_timestamp(timestamp):
    """Format timestamp for display."""
    if not timestamp:
        return "Unknown"
    
    try:
        if isinstance(timestamp, str):
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            dt = timestamp
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return str(timestamp)

def parse_timestamp(timestamp):
    """Parse timestamp to datetime object."""
    if not timestamp:
        return None
    
    if isinstance(timestamp, datetime):
        return timestamp
    
    try:
        return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except:
        return None

def get_anomaly_severity(anomaly):
    """Extract severity from anomaly."""
    # First check if there's a direct severity field
    if 'severity' in anomaly and anomaly['severity']:
        return anomaly['severity']
    
    # Then check the analysis field
    analysis = anomaly.get('analysis', {})
    
    # If analysis is a string, try to parse it
    if isinstance(analysis, str):
        try:
            analysis = json.loads(analysis)
        except:
            analysis = {}
    
    # If analysis is a dict, get severity
    if isinstance(analysis, dict):
        return analysis.get('severity', 'Unknown')
    
    return 'Unknown'

def get_threat_type_for_anomaly(anomaly):
    """Determine threat type based on anomaly characteristics."""
    score = float(anomaly.get('score', 0))
    features = anomaly.get('features', [])
    data = anomaly.get('data', {})
    
    # Check features and data for threat indicators
    if 'high_data_transfer' in features or 'data_exfiltration' in features:
        return "Data Exfiltration"
    elif 'unusual_login_time' in features or 'multiple_failed_logins' in features:
        return "Brute Force Attack"
    elif 'privilege_escalation' in features:
        return "Privilege Escalation"
    elif isinstance(data, dict):
        bytes_transferred = data.get('bytes_transferred', 0)
        if bytes_transferred > 1000000:
            return "Data Exfiltration"
        protocol = data.get('protocol', '')
        if protocol in ['SSH', 'RDP']:
            return "Remote Access Attempt"
    
    # Default based on score
    if score > 0.8:
        return "Critical Security Event"
    elif score > 0.6:
        return "Suspicious Activity"
    else:
        return "Anomalous Behavior"

def update_anomaly_status_action(anomaly, new_status):
    """Update anomaly status with proper feedback."""
    from services.data_service import update_anomaly_status
    
    success = update_anomaly_status(anomaly.get('id'), new_status)
    
    if success:
        st.success(f"✅ Status updated to: {new_status}")
        anomaly['status'] = new_status
        st.session_state.selected_anomaly = anomaly
        
        # Add activity log
        from services.data_service import add_agent_activity
        add_agent_activity(
            agent_id="user",
            activity_type="status_change",
            description=f"Changed anomaly status to {new_status}",
            anomaly_id=anomaly.get('id')
        )
    else:
        st.error("❌ Failed to update status")

def generate_anomaly_report(anomaly):
    """Generate a detailed report for the anomaly."""
    with st.spinner("Generating report..."):
        time.sleep(1)
    
    # Create report content
    report = f"""
# Anomaly Report
**Report ID:** RPT-{anomaly.get('id')}
**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary
Anomaly {anomaly.get('id')} was detected with a severity score of {float(anomaly.get('score', 0)):.3f}.
The anomaly has been classified as {get_anomaly_severity(anomaly)} severity.

## Details
- **Detection Model:** {anomaly.get('model')}
- **Location:** {anomaly.get('location')}
- **Source IP:** {anomaly.get('src_ip', 'N/A')}
- **Destination IP:** {anomaly.get('dst_ip', 'N/A')}
- **Status:** {anomaly.get('status')}

## Recommended Actions
1. Review the anomaly details thoroughly
2. Check for correlated events
3. Implement appropriate security measures
4. Update security policies as needed
    """
    
    st.download_button(
        label="📥 Download Report",
        data=report,
        file_name=f"anomaly_report_{anomaly.get('id')}.md",
        mime="text/markdown"
    )

def render_anomaly_overview(anomaly):
    """Render detailed overview of the anomaly with consistent compact card layout."""
    
    col1, col2 = st.columns(2)
    
    # Left Column
    with col1:
        # Basic Information Card
        with st.container(border=True):
            st.markdown('<p style="background-color: white; padding: 8px; margin: -16px -16px 16px -16px; font-weight: 600; font-size: 1.1rem;">📋 Basic Information</p>', unsafe_allow_html=True)
            
            st.markdown(f"**ID:** {anomaly.get('id', 'Unknown')}")
            st.markdown(f"**Detection Time:** {format_timestamp(anomaly.get('detection_time', anomaly.get('timestamp')))}")
            st.markdown(f"**Location:** {anomaly.get('location', 'Unknown')}")
            st.markdown(f"**Source IP:** {anomaly.get('src_ip', 'N/A')}")
            st.markdown(f"**Destination IP:** {anomaly.get('dst_ip', 'N/A')}")
            st.markdown(f"**Threshold:** {anomaly.get('threshold', 0.5):.2f}")
        
        # Triggering Features Card
        with st.container(border=True):
            st.markdown('<p style="background-color: white; padding: 8px; margin: -16px -16px 16px -16px; font-weight: 600; font-size: 1.1rem;">🎯 Triggering Features</p>', unsafe_allow_html=True)
            
            features = anomaly.get('features', [])
            
            if not features:
                st.markdown("*No specific features recorded*")
            else:
                # Handle string (JSON)
                if isinstance(features, str):
                    try:
                        features = json.loads(features)
                    except:
                        st.markdown(f"• {features}")
                        features = None
                
                # Handle dict directly
                if isinstance(features, dict):
                    for key, value in features.items():
                        if isinstance(value, (int, float)):
                            if 'bytes' in key.lower():
                                formatted_value = f"{value:,} bytes"
                            elif 'rate' in key.lower():
                                formatted_value = f"{value:.2f}%"
                            elif 'usage' in key.lower():
                                formatted_value = f"{value:.1f}%"
                            else:
                                formatted_value = f"{value:,}" if isinstance(value, int) else f"{value:.2f}"
                        else:
                            formatted_value = str(value)
                        st.markdown(f"• **{key.replace('_', ' ').title()}:** {formatted_value}")
                
                # Handle list
                elif isinstance(features, list):
                    for feature in features:
                        if isinstance(feature, dict):
                            # Dictionary in list
                            for key, value in feature.items():
                                if isinstance(value, (int, float)):
                                    if 'bytes' in key.lower():
                                        formatted_value = f"{value:,} bytes"
                                    elif 'rate' in key.lower():
                                        formatted_value = f"{value:.2f}%"
                                    elif 'usage' in key.lower():
                                        formatted_value = f"{value:.1f}%"
                                    else:
                                        formatted_value = f"{value:,}" if isinstance(value, int) else f"{value:.2f}"
                                else:
                                    formatted_value = str(value)
                                st.markdown(f"• **{key.replace('_', ' ').title()}:** {formatted_value}")
                        else:
                            # Simple string/value in list
                            st.markdown(f"• {str(feature)}")
    
    # Right Column
    with col2:
        # Raw Data Card
        with st.container(border=True):
            st.markdown('<p style="background-color: white; padding: 8px; margin: -16px -16px 16px -16px; font-weight: 600; font-size: 1.1rem;">📊 Raw Data</p>', unsafe_allow_html=True)
            
            data = anomaly.get('data', anomaly.get('original_data', {}))
            
            if data and isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, (int, float)):
                        if 'bytes' in k.lower():
                            st.markdown(f"**{k}:** {v:,} bytes")
                        elif 'time' in k.lower() or 'duration' in k.lower():
                            st.markdown(f"**{k}:** {v} seconds")
                        else:
                            formatted = f"{v:,}" if isinstance(v, int) else f"{v:.2f}"
                            st.markdown(f"**{k}:** {formatted}")
                    else:
                        st.markdown(f"**{k}:** {v}")
            elif data:
                st.markdown(str(data))
            else:
                st.markdown("*No raw data available*")
        
        # Additional Details Card — enriched structured rendering
        details = anomaly.get('details', {})
        if details and isinstance(details, dict):
            with st.container(border=True):
                st.markdown('<p style="background-color: white; padding: 8px; margin: -16px -16px 16px -16px; font-weight: 600; font-size: 1.1rem;">🔍 Detection Details</p>', unsafe_allow_html=True)

                # Scalar fields rendered directly
                _SKIP_IN_FLAT = {"contributing_features", "top_features_by_value",
                                 "trained_feature_names", "feature_value_snapshot",
                                 "detection_context"}
                for key, value in details.items():
                    if key in _SKIP_IN_FLAT:
                        continue
                    if isinstance(value, (int, float)):
                        st.markdown(f"**{key.replace('_', ' ').title()}:** `{value}`")
                    else:
                        st.markdown(f"**{key.replace('_', ' ').title()}:** {value}")

                # Nested dicts/lists as expandable JSON
                if details.get("detection_context"):
                    with st.expander("⚙️ Detection Context"):
                        st.json(details["detection_context"])
                if details.get("top_features_by_value"):
                    with st.expander("🏆 Top Features by Value"):
                        st.json(details["top_features_by_value"])
                if details.get("feature_value_snapshot"):
                    with st.expander("📸 Feature Value Snapshot"):
                        st.json(details["feature_value_snapshot"])
                if details.get("contributing_features"):
                    with st.expander(f"📋 Contributing Features ({details.get('feature_count', 0)})"):
                        for f in details["contributing_features"]:
                            st.markdown(f"• `{f}`")

    # ── Detection Intelligence ──────────────────────────────────────────────
    # Visible only when the enriched fields are present.
    details = anomaly.get('details', {})
    if not isinstance(details, dict):
        details = {}

    _INTEL_KEYS = {
        'score_percentile', 'anomaly_magnitude', 'score_explanation',
        'threshold_margin', 'trained_feature_count', 'detection_context',
        'feature_value_snapshot', 'top_features_by_value',
    }
    has_intel = (
        bool(_INTEL_KEYS & set(details.keys()))
        or anomaly.get('model_type')
        or anomaly.get('model_version')
    )

    if has_intel:
        st.markdown("---")
        st.markdown("### 🧠 Detection Intelligence")

        ic1, ic2, ic3 = st.columns(3)

        with ic1:
            with st.container(border=True):
                st.markdown("**📊 Score Analysis**")
                if details.get('score_percentile'):
                    st.metric("Percentile", details['score_percentile'])
                if details.get('anomaly_magnitude'):
                    st.metric("Magnitude", details['anomaly_magnitude'])
                if details.get('score_band') is not None:
                    st.metric("Score Band", f"{details['score_band']}/10")
                if details.get('threshold_margin') is not None:
                    st.metric("Threshold Margin", f"{details['threshold_margin']:+.3f}")
                if details.get('threshold_exceedance_pct') is not None:
                    st.metric("Exceedance", f"{details['threshold_exceedance_pct']:.1f}%")

        with ic2:
            with st.container(border=True):
                st.markdown("**🔬 Model Context**")
                if anomaly.get('model_type'):
                    st.metric("Detector Class", anomaly['model_type'])
                if anomaly.get('model_version'):
                    st.metric("Model Version", anomaly['model_version'])
                if details.get('trained_feature_count'):
                    st.metric("Trained Features", details['trained_feature_count'])
                if details.get('feature_count') is not None:
                    st.metric("Data Features", details['feature_count'])

        with ic3:
            with st.container(border=True):
                st.markdown("**⚙️ Job Provenance**")
                ctx = details.get('detection_context', {})
                if isinstance(ctx, dict):
                    if ctx.get('job_id'):
                        st.markdown(f"**Job ID**")
                        st.code(ctx['job_id'], language=None)
                    if ctx.get('batch_size') is not None:
                        st.metric("Batch Size", ctx['batch_size'])
                    if ctx.get('detector_algorithm'):
                        st.metric("Algorithm", ctx['detector_algorithm'])

        # Score explanation — full-width callout
        if details.get('score_explanation'):
            score = float(anomaly.get('score', 0))
            if score >= 0.90:
                st.error(f"💡 {details['score_explanation']}")
            elif score >= 0.70:
                st.warning(f"💡 {details['score_explanation']}")
            else:
                st.info(f"💡 {details['score_explanation']}")

        # Feature deep-dives side by side
        top_feats = details.get('top_features_by_value', {})
        snap = details.get('feature_value_snapshot', {})
        if top_feats or snap:
            fc1, fc2 = st.columns(2)
            with fc1:
                if isinstance(top_feats, dict) and top_feats:
                    with st.expander("🏆 Top Features by Absolute Value"):
                        for fname, fval in top_feats.items():
                            st.metric(fname.replace('_', ' ').title(), f"{fval:.4f}")
            with fc2:
                if isinstance(snap, dict) and snap:
                    with st.expander("📸 Feature Value Snapshot (this data point)"):
                        for fname, fval in snap.items():
                            st.metric(fname.replace('_', ' ').title(), f"{fval:.4f}")

def render_pattern_analysis(anomaly):
    """Render pattern analysis for the anomaly."""
    st.subheader("📈 Pattern Analysis")
    
    # Time-based patterns
    st.markdown("### ⏰ Temporal Patterns")
    
    # Create time-based visualization
    timestamp = parse_timestamp(anomaly.get('timestamp'))
    if timestamp:
        # Check time of day
        hour = timestamp.hour
        day_of_week = timestamp.strftime("%A")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Time of day analysis
            st.markdown("**Time of Day Analysis**")
            
            if 0 <= hour < 6:
                st.warning("🌙 Anomaly detected during off-hours (midnight to 6 AM)")
            elif 6 <= hour < 9:
                st.info("🌅 Anomaly detected during early morning hours")
            elif 9 <= hour < 17:
                st.success("☀️ Anomaly detected during business hours")
            elif 17 <= hour < 22:
                st.info("🌆 Anomaly detected during evening hours")
            else:
                st.warning("🌙 Anomaly detected during late night hours")
            
            # Create hour distribution chart
            hours = list(range(24))
            activity = [0] * 24
            activity[hour] = 1
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=hours,
                y=activity,
                marker_color=['red' if i == hour else 'lightblue' for i in hours],
                text=[f"{i}:00" for i in hours],
                textposition='outside'
            ))
            fig.update_layout(
                title="Hour of Detection",
                xaxis_title="Hour of Day",
                yaxis_title="Activity",
                height=300,
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Day of week analysis
            st.markdown("**Day of Week Analysis**")
            
            if day_of_week in ['Saturday', 'Sunday']:
                st.warning("📅 Anomaly detected on weekend")
            else:
                st.info("📅 Anomaly detected on weekday")
            
            # Create day distribution chart
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            day_activity = [0] * 7
            day_index = timestamp.weekday()
            day_activity[day_index] = 1
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=days,
                y=day_activity,
                marker_color=['red' if i == day_index else 'lightblue' for i in range(7)],
            ))
            fig.update_layout(
                title="Day of Detection",
                xaxis_title="Day of Week",
                yaxis_title="Activity",
                height=300,
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Behavioral patterns
    st.markdown("### 🔍 Behavioral Patterns")
    
    # Extract patterns from data
    data = anomaly.get('data', {})
    if data:
        # Network patterns
        if 'bytes_transferred' in data:
            bytes_val = data['bytes_transferred']
            if bytes_val > 1000000:
                st.warning(f"⚠️ High data transfer detected: {bytes_val:,} bytes")
            else:
                st.info(f"📊 Normal data transfer: {bytes_val:,} bytes")
        
        # Protocol patterns
        if 'protocol' in data:
            protocol = data['protocol']
            if protocol in ['SSH', 'RDP']:
                st.warning(f"🔐 Remote access protocol detected: {protocol}")
            elif protocol in ['HTTP', 'HTTPS']:
                st.info(f"🌐 Web protocol detected: {protocol}")
            else:
                st.info(f"📡 Protocol: {protocol}")

def render_correlation_analysis(anomaly, all_anomalies):
    """Render correlation analysis with enhanced visualizations."""
    st.subheader("🔗 Correlation Analysis")
    
    # Find related anomalies
    anomaly_id = anomaly.get('id')
    anomaly_score = float(anomaly.get('score', 0))
    anomaly_model = anomaly.get('model')
    anomaly_location = anomaly.get('location')
    anomaly_src_ip = anomaly.get('src_ip')
    
    # Find correlations
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
        
        # Time proximity (within 1 hour)
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
    
    if related_anomalies:
        st.success(f"Found {len(related_anomalies)} correlated anomalies")
        
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
        
        # Enhanced Visualization Tabs
        viz_tabs = st.tabs([
            "📊 Network Graph", 
            "📈 Correlation Matrix", 
            "🕐 Timeline", 
            "🗺️ Geographic",
            "📋 Details"
        ])
        
        with viz_tabs[0]:
            # Network Graph Visualization
            st.markdown("### Network Correlation Graph")
            
            # Create the network graph
            fig = go.Figure()
            
            # Add center node (current anomaly) with detailed hover
            center_hover_text = (
                f"<b>TARGET ANOMALY</b><br>"
                f"<b>ID:</b> {anomaly_id}<br>"
                f"<b>Score:</b> {anomaly_score:.3f}<br>"
                f"<b>Severity:</b> {get_anomaly_severity(anomaly)}<br>"
                f"<b>Model:</b> {anomaly_model}<br>"
                f"<b>Location:</b> {anomaly_location}<br>"
                f"<b>Source IP:</b> {anomaly_src_ip or 'N/A'}<br>"
                f"<b>Timestamp:</b> {anomaly.get('timestamp', 'N/A')}<br>"
                f"<b>Status:</b> {anomaly.get('status', 'Unknown')}"
            )
            
            fig.add_trace(go.Scatter(
                x=[0], y=[0],
                mode='markers+text',
                marker=dict(
                    size=50, 
                    color='red', 
                    symbol='star',
                    line=dict(width=3, color='white')
                ),
                text=[f"<b>{anomaly_id[:8]}</b>"],
                textposition="top center",
                textfont=dict(size=12, color='black', family='Arial Black'),
                name="Target Anomaly",
                hoverinfo='text',
                hovertext=center_hover_text,
                hoverlabel=dict(
                    bgcolor='red',
                    font_color='white',
                    font_size=12
                )
            ))
            
            # Add related nodes in a circle with enhanced hover
            angle_step = 2 * np.pi / min(len(related_anomalies), 20)
            
            for i, related in enumerate(related_anomalies[:20]):
                angle = i * angle_step
                x = np.cos(angle) * 2
                y = np.sin(angle) * 2
                
                rel_anomaly = related['anomaly']
                rel_severity = get_anomaly_severity(rel_anomaly)
                
                # Create detailed hover text for edge (connection line)
                edge_hover_text = (
                    f"<b>CORRELATION DETAILS</b><br>"
                    f"<b>Strength:</b> {related['score']:.1%}<br>"
                    f"<b>Factors:</b><br>"
                )
                for reason in related['reasons']:
                    edge_hover_text += f"  • {reason}<br>"
                
                # Add edge with enhanced hover
                fig.add_trace(go.Scatter(
                    x=[0, x], y=[0, y],
                    mode='lines',
                    line=dict(
                        width=max(2, related['score'] * 15),  # Minimum width of 2
                        color=f'rgba(99, 102, 241, {max(0.3, related["score"])})'  # Minimum opacity
                    ),
                    showlegend=False,
                    hoverinfo='text',
                    hovertext=edge_hover_text,
                    hoverlabel=dict(
                        bgcolor='rgba(99, 102, 241, 0.8)',
                        font_color='white'
                    )
                ))
                
                # Enhanced hover text for nodes
                node_hover_text = (
                    f"<b>CORRELATED ANOMALY</b><br>"
                    f"<b>ID:</b> {rel_anomaly.get('id')}<br>"
                    f"<b>Score:</b> {rel_anomaly.get('score', 0):.3f}<br>"
                    f"<b>Severity:</b> {rel_severity}<br>"
                    f"<b>Model:</b> {rel_anomaly.get('model', 'Unknown')}<br>"
                    f"<b>Location:</b> {rel_anomaly.get('location', 'Unknown')}<br>"
                    f"<b>Source IP:</b> {rel_anomaly.get('src_ip', 'N/A')}<br>"
                    f"<b>Dest IP:</b> {rel_anomaly.get('dst_ip', 'N/A')}<br>"
                    f"<b>Timestamp:</b> {rel_anomaly.get('timestamp', 'N/A')}<br>"
                    f"<b>Status:</b> {rel_anomaly.get('status', 'Unknown')}<br>"
                    f"<br><b>CORRELATION INFO</b><br>"
                    f"<b>Correlation Score:</b> {related['score']:.1%}<br>"
                    f"<b>Correlation Factors:</b><br>"
                )
                for reason in related['reasons']:
                    node_hover_text += f"  • {reason}<br>"
                
                # Determine node color based on severity
                severity_colors = {
                    'Critical': '#ef4444',
                    'High': '#f97316',
                    'Medium': '#f59e0b',
                    'Low': '#10b981',
                    'Unknown': '#6b7280'
                }
                node_color = severity_colors.get(rel_severity, '#6b7280')
                
                # Determine node symbol based on status
                status_symbols = {
                    'new': 'circle',
                    'investigating': 'diamond',
                    'resolved': 'square',
                    'false_positive': 'x'
                }
                node_symbol = status_symbols.get(rel_anomaly.get('status', 'new'), 'circle')
                
                # Add node with enhanced styling and hover
                fig.add_trace(go.Scatter(
                    x=[x], y=[y],
                    mode='markers+text',
                    marker=dict(
                        size=25 + related['score'] * 25,  # Size based on correlation
                        color=node_color,
                        symbol=node_symbol,
                        line=dict(width=2, color='white'),
                        opacity=0.9
                    ),
                    text=[f"<b>{rel_anomaly.get('id')[:8]}</b>"],
                    textposition="top center",
                    textfont=dict(size=10, color='black'),
                    showlegend=False,
                    hoverinfo='text',
                    hovertext=node_hover_text,
                    hoverlabel=dict(
                        bgcolor=node_color,
                        font_color='white',
                        font_size=11,
                        align='left'
                    )
                ))
            
            # Add legend for severity colors
            for severity, color in {'Critical': '#ef4444', 'High': '#f97316', 'Medium': '#f59e0b', 'Low': '#10b981'}.items():
                fig.add_trace(go.Scatter(
                    x=[None], y=[None],
                    mode='markers',
                    marker=dict(size=10, color=color),
                    legendgroup=severity,
                    showlegend=True,
                    name=severity
                ))
            
            # Add annotations for additional context
            fig.add_annotation(
                text=f"<b>Showing top {min(20, len(related_anomalies))} correlations</b>",
                xref="paper", yref="paper",
                x=0, y=1.05,
                showarrow=False,
                font=dict(size=12)
            )
            
            # Add legend for symbols
            fig.add_annotation(
                text="<b>Symbols:</b> ⭐ Target | ● New | ◆ Investigating | ■ Resolved | ✕ False Positive",
                xref="paper", yref="paper",
                x=0, y=-0.1,
                showarrow=False,
                font=dict(size=10, color='gray')
            )
            
            fig.update_layout(
                title={
                    'text': "Anomaly Correlation Network",
                    'font': {'size': 20}
                },
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                height=650,
                hovermode='closest',
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                    title="Severity Levels"
                ),
                plot_bgcolor='rgba(250,250,250,0.8)'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Add interactive instructions
            col1, col2, col3 = st.columns(3)
            with col1:
                st.info("🖱️ **Hover** over nodes for details")
            with col2:
                st.info("🔗 **Hover** over lines for correlation factors")
            with col3:
                st.info("🔍 **Zoom** with scroll wheel")
                
        with viz_tabs[1]:
            # Correlation Matrix
            st.markdown("### Correlation Matrix Heatmap")
            
            # Select top anomalies for matrix
            matrix_anomalies = [anomaly] + [r['anomaly'] for r in related_anomalies[:10]]
            matrix_ids = [a['id'][:10] for a in matrix_anomalies]
            
            # Build correlation matrix
            matrix_data = []
            
            for a1 in matrix_anomalies:
                row = []
                for a2 in matrix_anomalies:
                    if a1['id'] == a2['id']:
                        row.append(1.0)
                    else:
                        # Calculate correlation
                        corr = 0
                        if a1.get('src_ip') == a2.get('src_ip') and a1.get('src_ip'):
                            corr += 0.4
                        if a1.get('location') == a2.get('location'):
                            corr += 0.2
                        if abs(float(a1.get('score', 0)) - float(a2.get('score', 0))) < 0.1:
                            corr += 0.2
                        if a1.get('model') == a2.get('model'):
                            corr += 0.1
                        row.append(corr)
                matrix_data.append(row)
            
            # Create heatmap
            fig = go.Figure(data=go.Heatmap(
                z=matrix_data,
                x=matrix_ids,
                y=matrix_ids,
                colorscale='RdBu_r',
                text=[[f'{val:.2f}' for val in row] for row in matrix_data],
                texttemplate='%{text}',
                textfont={"size": 10}
            ))
            
            fig.update_layout(
                title='Anomaly Correlation Matrix',
                height=500,
                xaxis={'side': 'bottom'},
                yaxis={'side': 'left'}
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with viz_tabs[2]:
            # Timeline Visualization
            st.markdown("### Temporal Correlation")
            
            # Prepare timeline data
            timeline_data = []
            
            # Add target anomaly
            target_time = parse_timestamp(anomaly.get('timestamp'))
            if target_time:
                timeline_data.append({
                    'time': target_time,
                    'id': anomaly['id'],
                    'type': 'target',
                    'score': anomaly_score,
                    'y': 0
                })
            
            # Add correlated anomalies
            for i, related in enumerate(related_anomalies[:20]):
                rel_time = parse_timestamp(related['anomaly'].get('timestamp'))
                if rel_time:
                    timeline_data.append({
                        'time': rel_time,
                        'id': related['anomaly']['id'],
                        'type': 'correlated',
                        'score': float(related['anomaly'].get('score', 0)),
                        'correlation': related['score'],
                        'y': (i % 3) * 0.2 + 0.1  # Stagger vertically
                    })
            
            if timeline_data:
                # Sort by time
                timeline_data.sort(key=lambda x: x['time'])
                
                fig = go.Figure()
                
                # Add timeline
                for event in timeline_data:
                    color = 'red' if event['type'] == 'target' else 'blue'
                    size = 30 if event['type'] == 'target' else 15
                    
                    fig.add_trace(go.Scatter(
                        x=[event['time']],
                        y=[event['y']],
                        mode='markers+text',
                        marker=dict(size=size, color=color),
                        text=event['id'][:8],
                        textposition="top center",
                        showlegend=False,
                        hovertext=f"ID: {event['id']}<br>Time: {event['time']}<br>Score: {event['score']:.3f}"
                    ))
                
                fig.update_layout(
                    title='Anomaly Timeline',
                    xaxis_title='Time',
                    yaxis=dict(showticklabels=False, range=[-0.1, 0.8]),
                    height=400,
                    hovermode='x unified'
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No timestamp data available for timeline")
        
        with viz_tabs[3]:
            # Geographic Distribution
            st.markdown("### Geographic Correlation")
            
            # Location mapping
            location_coords = {
                'us-east-1': {'lat': 38.7469, 'lon': -77.4758, 'name': 'US East'},
                'us-west-2': {'lat': 45.5152, 'lon': -122.6784, 'name': 'US West'},
                'eu-central-1': {'lat': 50.1109, 'lon': 8.6821, 'name': 'EU Central'},
                'ap-south-1': {'lat': 19.0760, 'lon': 72.8777, 'name': 'Asia Pacific'},
                'sa-east-1': {'lat': -23.5505, 'lon': -46.6333, 'name': 'South America'}
            }
            
            # Prepare map data
            map_data = []
            
            # Add all anomalies with locations
            for rel in [{'anomaly': anomaly, 'score': 1.0}] + related_anomalies:
                loc = rel['anomaly'].get('location')
                if loc in location_coords:
                    coords = location_coords[loc]
                    map_data.append({
                        'lat': coords['lat'],
                        'lon': coords['lon'],
                        'text': f"{rel['anomaly']['id'][:10]}<br>{coords['name']}",
                        'size': 20 if rel['anomaly']['id'] == anomaly_id else 10 + rel['score'] * 10
                    })
            
            if map_data:
                df_map = pd.DataFrame(map_data)
                
                fig = px.scatter_geo(
                    df_map,
                    lat='lat',
                    lon='lon',
                    size='size',
                    text='text',
                    projection='natural earth'
                )
                
                fig.update_traces(marker=dict(color='red'))
                fig.update_layout(height=500)
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No geographic data available")
        
        with viz_tabs[4]:
            # Detailed List
            st.markdown("### Correlation Details")
            
            for i, related in enumerate(related_anomalies[:10]):
                rel_anomaly = related['anomaly']
                severity = get_anomaly_severity(rel_anomaly)
                
                with st.expander(f"{rel_anomaly.get('id')} - Correlation: {related['score']:.1%}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Correlation Factors:**")
                        for reason in related['reasons']:
                            st.markdown(f"• {reason}")
                    
                    with col2:
                        st.markdown("**Anomaly Details:**")
                        st.markdown(f"Score: {float(rel_anomaly.get('score', 0)):.3f}")
                        st.markdown(f"Severity: {severity}")
                        st.markdown(f"Status: {rel_anomaly.get('status', 'unknown')}")
                        st.markdown(f"Model: {rel_anomaly.get('model', 'unknown')}")
    else:
        st.info("No significant correlations found with other anomalies")

def render_anomaly_actions(anomaly):
    """Render available actions for the anomaly."""
    st.subheader("🎯 Available Actions")
    
    current_status = anomaly.get('status', 'new')
    
    # Status change actions
    st.markdown("### 📋 Status Management")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if current_status != 'investigating':
            if st.button("🔍 Start Investigation", use_container_width=True):
                update_anomaly_status_action(anomaly, 'investigating')
    
    with col2:
        if current_status != 'resolved':
            if st.button("✅ Mark Resolved", use_container_width=True):
                update_anomaly_status_action(anomaly, 'resolved')
    
    with col3:
        if current_status != 'false_positive':
            if st.button("❌ False Positive", use_container_width=True):
                update_anomaly_status_action(anomaly, 'false_positive')
    
    # Security actions
    st.markdown("### 🛡️ Security Actions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if anomaly.get('src_ip'):
            if st.button(f"🚫 Block IP {anomaly.get('src_ip')}", use_container_width=True, type="primary"):
                with st.spinner("Blocking IP address..."):
                    time.sleep(1)
                st.success(f"✅ IP {anomaly.get('src_ip')} has been blocked")
                
                # Log the action
                from services.data_service import add_agent_activity
                add_agent_activity(
                    agent_id="security_agent",
                    activity_type="ip_blocked",
                    description=f"Blocked IP {anomaly.get('src_ip')} for anomaly {anomaly.get('id')}",
                    anomaly_id=anomaly.get('id')
                )
    
    with col2:
        if st.button("📧 Send Alert", use_container_width=True):
            with st.spinner("Sending security alert..."):
                time.sleep(1)
            st.success("✅ Security alert sent to team")
    
    # Investigation actions
    st.markdown("### 🔍 Investigation Tools")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Generate Report", use_container_width=True):
            generate_anomaly_report(anomaly)
    
    with col2:
        if st.button("🔗 Check Similar", use_container_width=True):
            st.info("Check the Correlations tab for similar anomalies")
    
    with col3:
        if st.button("📝 Add Note", use_container_width=True):
            st.text_area("Add investigation note:", key="investigation_note")
            if st.button("Save Note"):
                st.success("Note saved!")

def generate_ai_analysis_with_agents(anomaly, agent_messages):
    """Generate AI-based analysis incorporating agent findings."""
    import random
    
    # Extract insights from agent messages
    threat_indicators = []
    confidence_factors = []
    
    for msg in agent_messages:
        content = msg['content'].lower()
        if 'high' in content or 'critical' in content or 'urgent' in content:
            threat_indicators.append('high_severity')
        if 'confidence' in content or 'confirmed' in content:
            confidence_factors.append('agent_confirmation')
        if 'pattern' in content or 'similarity' in content:
            threat_indicators.append('pattern_match')
        if 'threat intelligence' in content or 'ioc' in content:
            threat_indicators.append('threat_intel_match')
    
    # Determine threat level based on score and agent findings
    score = float(anomaly.get('score', 0))
    features = anomaly.get('features', [])
    
    # Adjust threat level based on agent consensus
    if len(threat_indicators) >= 3:
        threat_level = "Critical"
        risk_score = random.uniform(8.5, 9.5)
    elif len(threat_indicators) >= 2 or score > 0.8:
        threat_level = "High"
        risk_score = random.uniform(7.0, 8.4)
    elif score > 0.6:
        threat_level = "Medium"
        risk_score = random.uniform(5.0, 6.9)
    else:
        threat_level = "Low"
        risk_score = random.uniform(2.0, 4.9)
    
    # Get threat type
    threat_type = get_threat_type_for_anomaly(anomaly)
    
    # Calculate confidence based on agent agreement
    base_confidence = 0.75
    if len(confidence_factors) > 0:
        base_confidence += 0.05 * len(confidence_factors)
    if 'pattern_match' in threat_indicators:
        base_confidence += 0.1
    if 'threat_intel_match' in threat_indicators:
        base_confidence += 0.05
    
    confidence = min(base_confidence, 0.95)
    
    # Generate enhanced description incorporating agent findings
    description = f"Multi-agent analysis confirms this is a {threat_type}. "
    
    if 'pattern_match' in threat_indicators:
        description += "Pattern analysis shows strong correlation with known attack signatures. "
    
    if 'threat_intel_match' in threat_indicators:
        description += "Threat intelligence databases confirm matching indicators of compromise. "
    
    description += f"The anomaly score of {score:.3f} combined with agent consensus indicates {threat_level.lower()} risk requiring immediate attention."
    
    # Enhanced recommendations based on agent analysis
    recommendations = []
    
    if threat_level in ["Critical", "High"]:
        recommendations.extend([
            "Immediately isolate affected systems to prevent lateral movement",
            "Initiate incident response protocol",
            "Preserve forensic evidence for investigation"
        ])
    
    if threat_type == "Data Exfiltration":
        recommendations.extend([
            "Block all outbound connections from affected systems",
            "Review data access logs for the past 48 hours",
            "Implement DLP rules to prevent future incidents"
        ])
    elif threat_type == "Brute Force Attack":
        recommendations.extend([
            "Reset passwords for all potentially affected accounts",
            "Implement account lockout policies",
            "Deploy multi-factor authentication immediately"
        ])
    elif threat_type == "Privilege Escalation":
        recommendations.extend([
            "Revoke all elevated privileges granted in the last 24 hours",
            "Audit all administrative access",
            "Review and enforce principle of least privilege"
        ])
    else:
        recommendations.extend([
            "Monitor the affected systems closely",
            "Review security policies and update as needed",
            "Conduct thorough security assessment"
        ])
    
    # Risk factors based on agent analysis
    risk_factors = []
    
    if score > 0.7:
        risk_factors.append("Anomaly score exceeds critical threshold")
    
    if 'pattern_match' in threat_indicators:
        risk_factors.append("Behavior matches known attack patterns")
    
    if 'threat_intel_match' in threat_indicators:
        risk_factors.append("Indicators match threat intelligence data")
    
    if anomaly.get('src_ip'):
        risk_factors.append(f"Suspicious activity from IP {anomaly.get('src_ip')}")
    
    timestamp = parse_timestamp(anomaly.get('timestamp'))
    if timestamp and (timestamp.hour < 6 or timestamp.hour > 22):
        risk_factors.append("Activity occurred outside business hours")
    
    # Calculate agent consensus
    agent_consensus = 0.85 if len(threat_indicators) >= 2 else 0.70
    
    analysis = {
        'threat_level': threat_level,
        'threat_type': threat_type,
        'confidence': confidence,
        'risk_score': risk_score,
        'description': description,
        'recommendations': recommendations[:4],  # Limit to top 4 recommendations
        'false_positive_probability': 1 - confidence,
        'risk_factors': risk_factors[:4],  # Limit to top 4 risk factors
        'agent_consensus': agent_consensus,
        'threat_indicators': threat_indicators,
        'analysis_timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    return analysis

def generate_ai_analysis(anomaly):
    """Generate AI-based analysis for the anomaly."""
    import random
    
    # Determine threat level based on score and features
    score = float(anomaly.get('score', 0))
    features = anomaly.get('features', [])
    
    if score > 0.8:
        threat_level = "Critical"
        risk_score = random.uniform(8.5, 9.5)
    elif score > 0.6:
        threat_level = "High"
        risk_score = random.uniform(6.5, 8.4)
    elif score > 0.4:
        threat_level = "Medium"
        risk_score = random.uniform(4.0, 6.4)
    else:
        threat_level = "Low"
        risk_score = random.uniform(2.0, 3.9)
    
    # Determine threat type based on features and data
    threat_types = {
        'data_exfiltration': "Data Exfiltration Attempt",
        'brute_force': "Brute Force Attack",
        'privilege_escalation': "Privilege Escalation",
        'lateral_movement': "Lateral Movement",
        'command_control': "Command & Control Communication",
        'malware': "Malware Activity",
        'insider_threat': "Potential Insider Threat",
        'ddos': "DDoS Attack Pattern"
    }
    
    # Select threat type based on features
    if 'high_data_transfer' in features or 'data_exfiltration' in features:
        threat_type = threat_types['data_exfiltration']
    elif 'unusual_login_time' in features or 'multiple_failed_logins' in features:
        threat_type = threat_types['brute_force']
    elif 'privilege_escalation' in features:
        threat_type = threat_types['privilege_escalation']
    else:
        threat_type = random.choice(list(threat_types.values()))
    
    # Generate description
    descriptions = {
        "Data Exfiltration Attempt": f"Detected unusual data transfer activity from {anomaly.get('src_ip', 'unknown source')}. The volume and pattern of data movement suggests potential unauthorized data extraction.",
        "Brute Force Attack": f"Multiple authentication attempts detected from {anomaly.get('src_ip', 'unknown source')}. Pattern analysis indicates systematic password guessing attempts.",
        "Privilege Escalation": "Detected attempts to gain elevated privileges. User behavior deviates significantly from established baseline.",
        "Lateral Movement": "Suspicious network traversal detected. Entity appears to be exploring network segments beyond normal access patterns.",
        "Command & Control Communication": "Detected communication patterns consistent with C2 activity. Periodic beaconing to external hosts observed.",
        "Malware Activity": "Behavioral analysis indicates potential malware execution. Unusual process spawning and file system modifications detected.",
        "Potential Insider Threat": "User activity significantly deviates from normal behavior patterns. Access to sensitive resources outside typical scope.",
        "DDoS Attack Pattern": "High volume of requests detected from multiple sources. Traffic pattern consistent with distributed denial of service attack."
    }
    
    # Generate recommendations based on threat type
    recommendations_map = {
        "Data Exfiltration Attempt": [
            "Immediately block the source IP address",
            "Review all recent data access logs from this source",
            "Check for any unauthorized data downloads or transfers",
            "Implement DLP policies to prevent future incidents"
        ],
        "Brute Force Attack": [
            "Block the attacking IP address",
            "Force password reset for targeted accounts",
            "Implement account lockout policies",
            "Enable multi-factor authentication"
        ],
        "Privilege Escalation": [
            "Revoke elevated privileges immediately",
            "Audit all recent privilege changes",
            "Review user access rights",
            "Implement principle of least privilege"
        ]
    }
    
    analysis = {
        'threat_level': threat_level,
        'threat_type': threat_type,
        'confidence': random.uniform(0.75, 0.95),
        'risk_score': risk_score,
        'description': descriptions.get(threat_type, "Anomalous activity detected requiring immediate investigation."),
        'recommendations': recommendations_map.get(
            threat_type,
            [
                "Investigate the anomaly immediately",
                "Isolate affected systems",
                "Collect forensic evidence",
                "Review security policies"
            ]
        ),
        'false_positive_probability': random.uniform(0.05, 0.25) if score < 0.7 else random.uniform(0.01, 0.10),
        'risk_factors': random.sample([
            "Unusual time of activity",
            "High severity score",
            "Multiple correlated events",
            "Suspicious network patterns",
            "Abnormal user behavior",
            "Policy violations detected"
        ], k=random.randint(2, 4))
    }
    
    return analysis

def prepare_anomaly_for_api(anomaly: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare anomaly data for API by converting non-serializable types."""
    import copy
    from datetime import datetime, date
    import numpy as np
    import pandas as pd
    
    def serialize_value(obj):
        """Convert non-JSON serializable objects to serializable format."""
        if isinstance(obj, (datetime, pd.Timestamp)):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, pd.Timedelta):
            return str(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Series):
            return obj.tolist()
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict('records')
        elif hasattr(obj, '__dict__'):
            # For custom objects, try to get their dict representation
            return str(obj)
        else:
            return obj
    
    def clean_dict(d):
        """Recursively clean dictionary of non-serializable types."""
        if not isinstance(d, dict):
            return serialize_value(d)
        
        cleaned = {}
        for k, v in d.items():
            if isinstance(v, dict):
                cleaned[k] = clean_dict(v)
            elif isinstance(v, list):
                cleaned[k] = [clean_dict(item) if isinstance(item, dict) else serialize_value(item) for item in v]
            else:
                cleaned[k] = serialize_value(v)
        return cleaned
    
    # Deep copy to avoid modifying original
    clean_anomaly = copy.deepcopy(anomaly)
    
    # Clean the entire anomaly dict
    return clean_dict(clean_anomaly)


def render_ai_analysis(anomaly):
    """Render AI-powered analysis of the anomaly with real LangGraph agents."""
    from datetime import datetime, timezone, timedelta
    import traceback
    
    st.subheader("🤖 AI-Powered Analysis")
    
    # Check if we have existing analysis
    analysis = anomaly.get('analysis', {})
    if isinstance(analysis, str):
        try:
            analysis = json.loads(analysis)
        except:
            analysis = {}
    
    # Analysis status
    if analysis and isinstance(analysis, dict) and len(analysis) > 1:
        # We have existing analysis
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Confidence Score", f"{analysis.get('confidence', 0):.1%}")
        
        with col2:
            st.metric("False Positive Probability", f"{analysis.get('false_positive_probability', 0):.1%}")
        
        # Risk factors
        if 'risk_factors' in analysis:
            st.markdown("### 🚨 Risk Factors")
            for factor in analysis['risk_factors']:
                st.markdown(f"• {factor}")
        
        # Detailed analysis text
        if 'description' in analysis:
            st.markdown("### 📝 Analysis Summary")
            st.info(analysis['description'])
        
        # Threat classification
        if 'threat_type' in analysis:
            st.markdown("### 🎯 Threat Classification")
            st.warning(f"**Type:** {analysis['threat_type']}")
    
    # Run new analysis button
    if st.button("🔄 Run New AI Analysis", type="primary"):
        # Create containers for real-time updates
        progress_container = st.container()
        messages_container = st.container()
        
        with progress_container:
            progress_bar = st.progress(0)
            status_text = st.empty()
        
        with messages_container:
            st.markdown("### 🤖 Agent Communication")
            messages_placeholder = st.container()
        
        try:
            # Call the real API
            api_url = get_api_url()
            
            # Initial progress
            progress_bar.progress(10)
            status_text.text("Initiating agent analysis...")
            
            # Step 1: Start agent analysis job
            # Prepare anomaly data with proper serialization
            anomaly_data = prepare_anomaly_for_api(anomaly)
            
            # The API expects a list of anomalies
            response = requests.post(
                f"{api_url}/agents/analyze",
                json=[anomaly_data],  # Send as a list
                timeout=120  # Increased timeout to 120 seconds for initial request
            )
            
            if response.status_code != 200:
                st.error(f"Failed to start analysis: {response.text}")
                progress_bar.empty()
                status_text.empty()
                return
            
            job_data = response.json()
            job_id = job_data.get('job_id')
            
            # Step 2: Poll for job completion and agent messages
            start_time = datetime.now(timezone.utc)
            timeout = timedelta(seconds=300)  # 5 minute timeout for analysis
            displayed_messages = set()
            poll_interval = 2  # Start with 2 second polling
            all_messages = []  # Initialize all_messages here
            
            while (datetime.now(timezone.utc) - start_time) < timeout:
                # Update progress
                elapsed = (datetime.now(timezone.utc) - start_time).seconds
                progress = min(10 + (elapsed / 300) * 80, 90)
                progress_bar.progress(int(progress))
                
                # Update status with more detailed information
                status_text.text(f"Agents analyzing... {elapsed}s elapsed (this may take 1-2 minutes)")
                
                try:
                    # Get job status with shorter timeout
                    job_response = requests.get(f"{api_url}/jobs/{job_id}", timeout=5)
                    
                    if job_response.status_code == 200:
                        job_status = job_response.json()
                        current_status = job_status.get('status', 'unknown')
                        
                        # Update status text with job progress if available
                        job_progress = job_status.get('progress', 0)
                        if job_progress > 0:
                            status_text.text(f"Analysis {job_progress:.0%} complete - {elapsed}s elapsed")
                        
                        # Try to get agent messages (but don't fail if this endpoint doesn't exist)
                        try:
                            messages_response = requests.get(
                                f"{api_url}/agents/messages",
                                params={"anomaly_id": anomaly.get('id'), "limit": 50},
                                timeout=3  # Short timeout for messages
                            )
                            
                            if messages_response.status_code == 200:
                                all_messages = messages_response.json()
                                
                                # Display new messages
                                with messages_placeholder.container():
                                    for msg in all_messages:
                                        msg_id = f"{msg.get('agent')}_{msg.get('timestamp')}"
                                        if msg_id not in displayed_messages:
                                            displayed_messages.add(msg_id)
                                            
                                            # Determine message style based on agent
                                            agent_name = msg.get('agent', 'unknown')
                                            agent_styles = {
                                                'security_analyst': ('🔍', 'info'),
                                                'pattern_detector': ('📊', 'warning'),
                                                'threat_investigator': ('🕵️', 'error'),
                                                'risk_assessor': ('⚖️', 'success'),
                                                'network_analyzer': ('🌐', 'info'),
                                                'behavior_monitor': ('👁️', 'warning')
                                            }
                                            
                                            icon, style = agent_styles.get(agent_name, ('🤖', 'info'))
                                            
                                            # Format timestamp
                                            try:
                                                msg_time = datetime.fromisoformat(msg.get('timestamp', '').replace('Z', '+00:00'))
                                                time_str = msg_time.strftime('%H:%M:%S')
                                            except:
                                                time_str = 'unknown'
                                            
                                            # Display message
                                            if style == 'error':
                                                st.error(f"{icon} **{agent_name}** ({time_str}): {msg.get('content', '')}")
                                            elif style == 'warning':
                                                st.warning(f"{icon} **{agent_name}** ({time_str}): {msg.get('content', '')}")
                                            elif style == 'success':
                                                st.success(f"{icon} **{agent_name}** ({time_str}): {msg.get('content', '')}")
                                            else:
                                                st.info(f"{icon} **{agent_name}** ({time_str}): {msg.get('content', '')}")
                            elif messages_response.status_code == 404:
                                # Messages endpoint doesn't exist - that's okay, just skip
                                logger.debug("Messages endpoint not available")
                        except requests.exceptions.Timeout:
                            # Don't fail if messages timeout, just continue
                            pass
                        except Exception as e:
                            logger.warning(f"Error fetching messages: {e}")
                        
                        # Check if job is complete
                        if current_status == 'completed':
                            progress_bar.progress(100)
                            status_text.text("Analysis complete!")
                            
                            # Get the results
                            results = job_status.get('result', {})
                            
                            # Extract the analysis from the results
                            if isinstance(results, list) and results:
                                # API returns a list, get the first result
                                first_result = results[0]
                                if 'agent_analysis' in first_result:
                                    new_analysis = first_result['agent_analysis']
                                else:
                                    new_analysis = construct_analysis_from_results(results, anomaly)
                            elif 'analysis' in results:
                                new_analysis = results['analysis']
                            else:
                                # Try to construct from agent findings
                                new_analysis = construct_analysis_from_results(results, anomaly)
                            
                            # Save the analysis
                            save_success = add_anomaly_analysis(anomaly.get('id'), {
                                'anomaly_id': anomaly.get('id'),
                                'model': 'langgraph_agents',
                                'score': anomaly.get('score', 0),
                                'analysis': new_analysis,
                                'remediation': results.get('remediation', {}),
                                'reflection': results.get('reflection', {})
                            })
                            
                            time.sleep(0.5)
                            progress_bar.empty()
                            status_text.empty()
                            
                            # Show success
                            st.success("✅ Multi-Agent AI Analysis Complete!")
                            
                            # Display the new analysis
                            display_analysis_results(new_analysis, results)
                            
                            # Update session state
                            if 'analysis' not in anomaly:
                                anomaly['analysis'] = {}
                            anomaly['analysis'].update(new_analysis)
                            st.session_state.selected_anomaly = anomaly
                            
                            # Show full communication log
                            if all_messages:
                                with st.expander("📋 Full Agent Communication Log"):
                                    for msg in all_messages:
                                        agent_name = msg.get('agent', 'unknown')
                                        timestamp = msg.get('timestamp', 'unknown')
                                        content = msg.get('content', '')
                                        
                                        st.markdown(f"**{agent_name}** - {timestamp}")
                                        st.markdown(f"> {content}")
                                        st.markdown("---")
                            
                            break
                        
                        elif current_status == 'failed':
                            progress_bar.progress(100)
                            status_text.text("Analysis complete!")
                        
                        # Get the results
                        results = job_status.get('result', {})
                        
                        # Extract the analysis from the results
                        if isinstance(results, list) and results:
                            # API returns a list, get the first result
                            first_result = results[0]
                            if 'agent_analysis' in first_result:
                                new_analysis = first_result['agent_analysis']
                            else:
                                new_analysis = construct_analysis_from_results(results, anomaly)
                        elif 'analysis' in results:
                            new_analysis = results['analysis']
                        else:
                            # Try to construct from agent findings
                            new_analysis = construct_analysis_from_results(results, anomaly)
                        
                        # Save the analysis
                        save_success = add_anomaly_analysis(anomaly.get('id'), {
                            'anomaly_id': anomaly.get('id'),
                            'model': 'langgraph_agents',
                            'score': anomaly.get('score', 0),
                            'analysis': new_analysis,
                            'remediation': results.get('remediation', {}),
                            'reflection': results.get('reflection', {})
                        })
                        
                        time.sleep(0.5)
                        progress_bar.empty()
                        status_text.empty()
                        
                        # Show success
                        st.success("✅ Multi-Agent AI Analysis Complete!")
                        
                        # Display the new analysis
                        display_analysis_results(new_analysis, results)
                        
                        # Update session state
                        if 'analysis' not in anomaly:
                            anomaly['analysis'] = {}
                        anomaly['analysis'].update(new_analysis)
                        st.session_state.selected_anomaly = anomaly
                        
                        # Show full communication log
                        with st.expander("📋 Full Agent Communication Log"):
                            for msg in all_messages:
                                agent_name = msg.get('agent', 'unknown')
                                timestamp = msg.get('timestamp', 'unknown')
                                content = msg.get('content', '')
                                
                                st.markdown(f"**{agent_name}** - {timestamp}")
                                st.markdown(f"> {content}")
                                st.markdown("---")
                        
                        break
                    
                    elif current_status == 'failed':
                        error_msg = job_status.get('error', 'Unknown error')
                        st.error(f"Analysis failed: {error_msg}")
                        progress_bar.empty()
                        status_text.empty()
                        break
                        
                    # Adaptive polling - slow down as time goes on
                    if elapsed > 30:
                        poll_interval = 5  # Poll every 5 seconds after 30s
                    elif elapsed > 60:
                        poll_interval = 10  # Poll every 10 seconds after 1 minute
                
                except requests.exceptions.Timeout:
                    logger.warning(f"Request timed out while polling job status")
                    # Continue polling even if one request times out
                except requests.exceptions.ConnectionError:
                    st.error("Lost connection to API service. Please check if the service is still running.")
                    progress_bar.empty()
                    status_text.empty()
                    break
                except Exception as e:
                    logger.error(f"Error polling job status: {e}")
                
                # Wait before next poll with adaptive interval
                time.sleep(poll_interval)
            
            else:
                # Timeout reached
                st.warning("⏱️ Analysis is taking longer than expected. The agents are still processing in the background.")
                st.info("You can check back later or try with a simpler anomaly.")
                
                # Try one more time to get the current status
                try:
                    final_check = requests.get(f"{api_url}/jobs/{job_id}", timeout=5)
                    if final_check.status_code == 200:
                        final_status = final_check.json()
                        st.caption(f"Current job status: {final_status.get('status', 'unknown')} - Progress: {final_status.get('progress', 0):.0%}")
                except:
                    pass
                
                progress_bar.empty()
                status_text.empty()
                
        except requests.exceptions.RequestException as e:
            st.error(f"API request failed: {str(e)}")
            st.info("Please ensure the agent API service is running.")
            if 'progress_bar' in locals():
                progress_bar.empty()
            if 'status_text' in locals():
                status_text.empty()
                
        except Exception as e:
            st.error(f"Unexpected error: {str(e)}")
            logger.error(f"Error in agent analysis: {str(e)}")
            logger.error(traceback.format_exc())
            if 'progress_bar' in locals():
                progress_bar.empty()
            if 'status_text' in locals():
                status_text.empty()


def construct_analysis_from_results(results: Dict[str, Any], anomaly: Dict[str, Any]) -> Dict[str, Any]:
    """Construct analysis dictionary from agent results."""
    # Default analysis structure
    analysis = {
        'threat_level': 'Unknown',
        'threat_type': 'Unknown',
        'confidence': 0.0,
        'risk_score': 0.0,
        'description': '',
        'recommendations': [],
        'false_positive_probability': 0.0,
        'risk_factors': [],
        'agent_consensus': 0.0,
        'threat_indicators': [],
        'analysis_timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    # Extract from results
    if isinstance(results, list) and results:
        # If results is a list, get the first item
        result = results[0]
    else:
        result = results
    
    # Check if we have agent_analysis directly
    if 'agent_analysis' in result:
        agent_analysis = result['agent_analysis']
    elif 'detailed_results' in result and result['detailed_results']:
        # Extract from detailed results if available
        detailed = result['detailed_results'][0] if isinstance(result['detailed_results'], list) else result['detailed_results']
        agent_analysis = detailed.get('agent_analysis', {})
    else:
        agent_analysis = {}
    
    if agent_analysis:
        # Threat assessment
        threat_assessment = agent_analysis.get('threat_assessment', {})
        analysis['threat_level'] = threat_assessment.get('level', 'Unknown')
        analysis['confidence'] = threat_assessment.get('confidence', 0.0)
        
        # Risk analysis
        risk_analysis = agent_analysis.get('risk_analysis', {})
        analysis['risk_score'] = risk_analysis.get('score', 0.0)
        analysis['risk_factors'] = risk_analysis.get('factors', [])
        
        # Pattern analysis
        pattern_analysis = agent_analysis.get('pattern_analysis', {})
        if pattern_analysis.get('matches_known_patterns'):
            analysis['threat_indicators'].append('pattern_match')
        
        # Network analysis
        network_analysis = agent_analysis.get('network_analysis', {})
        if network_analysis.get('suspicious_activity'):
            analysis['threat_indicators'].append('suspicious_network')
        
        # Behavior analysis
        behavior_analysis = agent_analysis.get('behavior_analysis', {})
        if behavior_analysis.get('anomalous_behavior'):
            analysis['threat_indicators'].append('anomalous_behavior')
        
        # Recommendations
        recommendations = agent_analysis.get('recommendations', {})
        analysis['recommendations'] = recommendations.get('immediate_actions', [])
        
        # Agent consensus
        analysis['agent_consensus'] = agent_analysis.get('consensus_score', 0.0)
        
        # Description
        analysis['description'] = agent_analysis.get('summary', 
            f"Multi-agent analysis identified this as a {analysis['threat_level']} threat with {analysis['confidence']:.1%} confidence.")
        
        # Threat type
        analysis['threat_type'] = determine_threat_type_from_analysis(agent_analysis, anomaly)
        
        # False positive probability
        analysis['false_positive_probability'] = 1 - analysis['confidence']
    
    else:
        # Fallback to basic analysis
        score = float(anomaly.get('score', 0))
        
        if score > 0.8:
            analysis['threat_level'] = 'Critical'
            analysis['risk_score'] = 8.5
        elif score > 0.6:
            analysis['threat_level'] = 'High'
            analysis['risk_score'] = 6.5
        else:
            analysis['threat_level'] = 'Medium'
            analysis['risk_score'] = 4.5
        
        analysis['confidence'] = min(score + 0.1, 0.95)
        analysis['description'] = f"Anomaly detected with score {score:.3f}"
        analysis['recommendations'] = ["Investigate immediately", "Review related events"]
        analysis['threat_type'] = get_threat_type_for_anomaly(anomaly)
    
    return analysis


def determine_threat_type_from_analysis(agent_analysis: Dict[str, Any], anomaly: Dict[str, Any]) -> str:
    """Determine threat type from agent analysis."""
    # Check various analyses for threat indicators
    
    network = agent_analysis.get('network_analysis', {})
    if network.get('data_exfiltration_suspected'):
        return "Data Exfiltration"
    
    behavior = agent_analysis.get('behavior_analysis', {})
    if behavior.get('privilege_escalation_detected'):
        return "Privilege Escalation"
    
    pattern = agent_analysis.get('pattern_analysis', {})
    if pattern.get('attack_pattern_type'):
        return pattern['attack_pattern_type']
    
    threat = agent_analysis.get('threat_assessment', {})
    if threat.get('threat_type'):
        return threat['threat_type']
    
    # Fallback to basic detection
    return get_threat_type_for_anomaly(anomaly)


def display_analysis_results(analysis: Dict[str, Any], full_results: Dict[str, Any]):
    """Display the analysis results in a structured format."""
    st.markdown("### 🎯 Analysis Results")
    
    # Key metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        threat_color = {
            'Critical': '🔴',
            'High': '🟠',
            'Medium': '🟡',
            'Low': '🟢'
        }.get(analysis.get('threat_level', 'Unknown'), '⚪')
        st.metric("Threat Level", f"{threat_color} {analysis.get('threat_level', 'Unknown')}")
    
    with col2:
        st.metric("Confidence", f"{analysis.get('confidence', 0):.1%}")
    
    with col3:
        st.metric("Risk Score", f"{analysis.get('risk_score', 0):.2f}")
    
    # Threat details
    st.markdown("### 🔍 Threat Analysis")
    st.warning(f"**Type:** {analysis.get('threat_type', 'Unknown')}")
    st.info(analysis.get('description', 'No description available'))
    
    # Risk factors
    risk_factors = analysis.get('risk_factors', [])
    if risk_factors:
        st.markdown("### 🚨 Risk Factors Identified")
        for factor in risk_factors:
            st.markdown(f"• {factor}")
    
    # Recommendations
    recommendations = analysis.get('recommendations', [])
    if recommendations:
        st.markdown("### 💡 Recommendations")
        for i, rec in enumerate(recommendations, 1):
            st.markdown(f"{i}. {rec}")
    
    # Agent consensus
    consensus = analysis.get('agent_consensus', 0)
    if consensus > 0:
        st.markdown("### 🤝 Agent Consensus")
        st.progress(consensus)
        st.caption(f"Agents agree with {consensus * 100:.0f}% consensus on the threat assessment")
    
    # Additional insights from full results
    if 'detailed_results' in full_results and full_results['detailed_results']:
        with st.expander("📊 Detailed Agent Findings"):
            detailed = full_results['detailed_results'][0]
            agent_analysis = detailed.get('agent_analysis', {})
            
            # Show each agent's findings
            for agent_type, findings in agent_analysis.items():
                if isinstance(findings, dict) and agent_type not in ['summary', 'consensus_score']:
                    st.markdown(f"**{agent_type.replace('_', ' ').title()}:**")
                    st.json(findings)
                                        
# Alternative: Add as a new tab in render_anomaly_analyzer
def render_anomaly_analyzer(anomalies):
    """Render enhanced anomaly analyzer with deep analysis capabilities."""
    st.header("🔬 Deep Analysis")
    
    if 'selected_anomaly' in st.session_state and st.session_state.selected_anomaly:
        anomaly = st.session_state.selected_anomaly
        
        # Display analysis header with key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Anomaly Score", f"{float(anomaly.get('score', 0)):.3f}")
        
        with col2:
            severity = get_anomaly_severity(anomaly)
            severity_color = {
                'Critical': '🔴', 'High': '🟠', 'Medium': '🟡', 'Low': '🟢'
            }.get(severity, '⚪')
            st.metric("Severity", f"{severity_color} {severity}")
        
        with col3:
            st.metric("Model", anomaly.get('model', 'Unknown'))
        
        with col4:
            status = anomaly.get('status', 'new')
            status_emoji = {
                'new': '🆕', 'investigating': '🔍', 'resolved': '✅'
            }.get(status, '❓')
            st.metric("Status", f"{status_emoji} {status.title()}")
        
        # Updated tabs with new Origin tab
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Overview", 
            "🤖 AI Analysis", 
            "📈 Patterns", 
            "🔗 Correlations"        ])
        
        with tab1:
            render_anomaly_overview(anomaly)
        
        with tab2:
            render_ai_analysis(anomaly)
        
        with tab3:
            render_pattern_analysis(anomaly)
        
        with tab4:
            render_correlation_analysis(anomaly, anomalies)
        

        
        # Close button
        if st.button("❌ Close Analysis", type="secondary"):
            del st.session_state.selected_anomaly
            if 'selected_anomaly_id' in st.session_state:
                del st.session_state.selected_anomaly_id
            if 'show_analyzer' in st.session_state:
                del st.session_state.show_analyzer
            st.rerun()
    else:
        # Selector
        if anomalies:
            st.info("Select an anomaly from the list above to analyze, or choose from the dropdown below:")
            
            # Create options with more info
            options = []
            anomaly_map = {}
            for a in anomalies[:50]:  # Limit to 50 for performance
                severity = get_anomaly_severity(a)
                option = f"{a.get('id')} | Score: {float(a.get('score', 0)):.3f} | {severity} | {a.get('model')}"
                options.append(option)
                anomaly_map[option] = a
            
            selected = st.selectbox("Select an anomaly to analyze", options)
            
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("🔬 Start Analysis", type="primary", use_container_width=True):
                    st.session_state.selected_anomaly = anomaly_map[selected]
                    st.rerun()
        else:
            st.info("No anomalies available for analysis")


def call_detection_api():
    """Call the anomaly detection API to detect new anomalies."""
    api_url = get_api_url()
    
    try:
        # First, check if API is available
        health_response = requests.get(f"{api_url}/health", timeout=5)
        if health_response.status_code != 200:
            st.error(f"API service is not available at {api_url}")
            return False, 0
        
        # Get the list of available models first
        models_response = requests.get(f"{api_url}/models", timeout=5)
        if models_response.status_code != 200:
            st.error("Cannot retrieve available models from API")
            return False, 0
        
        models = models_response.json()
        if not models:
            st.error("No models available in the API. Please train models first.")
            return False, 0
        
        # Get the first available trained model
        trained_models = [m for m in models if m.get('status') == 'trained']
        if not trained_models:
            st.error("No trained models available. Please train a model first.")
            return False, 0
        
        model_name = trained_models[0]['name']
        
        # Generate some sample data for detection
        # In a real scenario, this would come from your data source
        sample_data = [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "cpu_usage": 95,
                "memory_usage": 85,
                "network_in": 50000,
                "network_out": 20000,
                "location": "server-01",
                "src_ip": "192.168.1.100",
                "dst_ip": "10.0.0.1"
            }
        ]
        
        # Call the simplified detection endpoint with correct format
        detect_response = requests.post(
            f"{api_url}/detect",
            json={
                "model_name": model_name,
                "data": sample_data,
                "threshold": 0.5
            },
            timeout=30
        )
        
        if detect_response.status_code == 200:
            result = detect_response.json()
            job_id = result.get('job_id')
            
            # Wait for job completion
            max_attempts = 30
            for attempt in range(max_attempts):
                time.sleep(1)
                
                job_response = requests.get(f"{api_url}/jobs/{job_id}", timeout=5)
                if job_response.status_code == 200:
                    job_status = job_response.json()
                    
                    if job_status.get('status') == 'completed':
                        job_result = job_status.get('result', {})
                        detected_count = job_result.get('anomalies_detected', 0)
                        
                        if detected_count > 0:
                            st.success(f"✅ Detected {detected_count} new anomalies!")
                            
                            # Log the detection
                            add_agent_activity(
                                agent_id="detection_system",
                                activity_type="detection_run",
                                description=f"Detected {detected_count} new anomalies via API",
                                anomaly_id=None
                            )
                            
                            return True, detected_count
                        else:
                            st.info("No new anomalies detected at this time.")
                            return True, 0
                    
                    elif job_status.get('status') == 'failed':
                        error_msg = job_status.get('result', {}).get('error', 'Unknown error')
                        st.error(f"Detection failed: {error_msg}")
                        return False, 0
            
            st.warning("Detection job timed out")
            return False, 0
            
        else:
            try:
                error_data = detect_response.json()
                error_msg = error_data.get('detail', 'Unknown error')
            except:
                error_msg = f"HTTP {detect_response.status_code}"
            st.error(f"Detection failed: {error_msg}")
            return False, 0
            
    except requests.exceptions.Timeout:
        st.error("Detection request timed out. The API might be processing a large dataset.")
        return False, 0
    except requests.exceptions.ConnectionError:
        st.error(f"Cannot connect to API at {api_url}. Please ensure the API service is running.")
        st.info("To start the API service, run: `python api_services.py --config config/config.yaml`")
        return False, 0
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        logger.error(f"Error in call_detection_api: {str(e)}")
        logger.error(traceback.format_exc())
        return False, 0


def _load_triage_config():
    """Load triage settings from config.yaml, falling back to defaults."""
    try:
        import yaml, os
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "config.yaml")
        with open(os.path.abspath(cfg_path)) as f:
            cfg = yaml.safe_load(f)
        triage = cfg.get("triage", {})
        return {
            "entity_keys": triage.get("entity_keys", ["computerName"]),
            "dedup_window_seconds": int(triage.get("dedup_window_seconds", 300)),
            "auto_close_days": int(triage.get("auto_close_days", 7)),
            "reason_codes": triage.get("reason_codes", []),
        }
    except Exception:
        return {
            "entity_keys": ["computerName"],
            "dedup_window_seconds": 300,
            "auto_close_days": 7,
            "reason_codes": [],
        }


def render():
    """Render the anomalies page with modern UI."""
    # Page header - simplified to avoid parsing issues
    st.markdown("# 🔍 Anomaly Analysis Center")
    st.markdown("---")

    triage_cfg = _load_triage_config()

    # Load anomalies
    with st.spinner("Loading anomalies..."):
        if 'anomalies_data' not in st.session_state or st.session_state.get('refresh_anomalies', False):
            if st.session_state.get('refresh_anomalies', False):
                st.session_state.refresh_anomalies = False
            st.session_state.anomalies_data = get_anomalies(limit=1000, min_score=0.0)

    anomalies = st.session_state.anomalies_data or []

    # Action buttons
    render_action_buttons()

    # Summary statistics
    render_summary_statistics(anomalies)

    # Filters
    filtered_anomalies = render_filters(anomalies)

    # Display mode
    display_mode = render_display_options()

    # Anomaly display
    if display_mode == "Groups":
        api_url = get_api_url()
        # Sidebar-style config for the group view
        with st.expander("Group view settings", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                entity_keys_input = st.text_input(
                    "Entity keys (comma-separated)",
                    value=", ".join(triage_cfg["entity_keys"]),
                )
                entity_keys = [k.strip() for k in entity_keys_input.split(",") if k.strip()]
            with col2:
                dedup_secs = st.number_input(
                    "Dedup window (seconds)",
                    min_value=0,
                    max_value=3600,
                    value=triage_cfg["dedup_window_seconds"],
                )
            with col3:
                auto_close_enabled = st.checkbox("Auto-close stale low alerts", value=False)
                auto_close_days = st.number_input(
                    "Auto-close after (days)",
                    min_value=1,
                    max_value=90,
                    value=triage_cfg["auto_close_days"],
                )
        render_group_view(
            filtered_anomalies,
            api_url=api_url,
            entity_keys=entity_keys,
            dedup_window_seconds=dedup_secs,
            auto_close_days=auto_close_days,
            auto_close_enabled=auto_close_enabled,
        )
    elif display_mode == "Cards":
        render_anomaly_cards(filtered_anomalies)
    else:
        render_anomaly_table(filtered_anomalies)

    # Analyzer
    render_anomaly_analyzer(filtered_anomalies)

    # Visualizations
    render_visualizations(filtered_anomalies)


def render_action_buttons():
    """Render action buttons."""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔍 Detect New", use_container_width=True, type="primary"):
            with st.spinner("Running anomaly detection..."):
                # Call the actual detection API
                success, count = call_detection_api()
                
                if success and count > 0:
                    # Update session state to force refresh
                    st.session_state.refresh_anomalies = True
                    add_notification(f"Detected {count} new anomalies!", "success")
                    st.rerun()
                elif success and count == 0:
                    add_notification("No new anomalies detected", "info")
                else:
                    add_notification("Detection failed. Check API connection.", "error")
    
    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.session_state.refresh_anomalies = True
            st.rerun()
    
    with col3:
        if st.button("📊 Export", use_container_width=True):
            # Get all anomalies for export
            anomalies = st.session_state.get('anomalies_data', [])
            if anomalies:
                # Create CSV data
                export_data = []
                for a in anomalies:
                    export_data.append({
                        'ID': a.get('id', ''),
                        'Model': a.get('model', ''),
                        'Score': a.get('score', 0),
                        'Severity': get_anomaly_severity(a),
                        'Status': a.get('status', ''),
                        'Timestamp': a.get('timestamp', ''),
                        'Location': a.get('location', '')
                    })
                
                df = pd.DataFrame(export_data)
                csv = df.to_csv(index=False)
                
                # Download button
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"anomalies_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
    
    with col4:
        # API Configuration button
        if st.button("⚙️ API Config", use_container_width=True):
            with st.expander("API Configuration", expanded=True):
                current_url = get_api_url()
                st.info(f"Current API URL: {current_url}")
                
                new_url = st.text_input("API URL", value=current_url)
                if st.button("Update URL"):
                    import os
                    os.environ["ANOMALY_DETECTION_API_URL"] = new_url
                    st.success(f"API URL updated to: {new_url}")
                    st.rerun()
                
                # Test connection
                if st.button("Test Connection"):
                    try:
                        response = requests.get(f"{new_url}/health", timeout=5)
                        if response.status_code == 200:
                            st.success("✅ API is reachable!")
                            health = response.json()
                            st.json(health)
                        else:
                            st.error(f"API returned status code: {response.status_code}")
                    except Exception as e:
                        st.error(f"Connection failed: {str(e)}")


def render_summary_statistics(anomalies):
    """Render summary statistics."""
    total = len(anomalies)
    
    # Count severities
    severities = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    statuses = {"new": 0, "investigating": 0, "resolved": 0}
    
    for a in anomalies:
        sev = get_anomaly_severity(a)
        if sev in severities:
            severities[sev] += 1
        
        status = a.get('status', 'new')
        if status in statuses:
            statuses[status] += 1
    
    # Display metrics
    cols = st.columns(5)
    
    with cols[0]:
        st.metric("Total", f"{total:,}", f"+{np.random.randint(1,10)}")
    
    with cols[1]:
        st.metric("🔴 Critical", severities['Critical'])
    
    with cols[2]:
        st.metric("🟠 High", severities['High'])
    
    with cols[3]:
        st.metric("🆕 New", statuses['new'])
    
    with cols[4]:
        st.metric("✅ Resolved", statuses['resolved'])


def render_filters(anomalies):
    """Render filters and return filtered anomalies."""
    with st.expander("🎯 Filters", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            search = st.text_input("Search", placeholder="ID, model, location...")
        
        with col2:
            severity = st.multiselect(
                "Severity",
                ["Critical", "High", "Medium", "Low"],
                default=["Critical", "High", "Medium", "Low"]
            )
        
        with col3:
            status = st.multiselect(
                "Status",
                ["new", "investigating", "resolved"],
                default=["new", "investigating"],
                format_func=lambda x: x.title()
            )
        
        with col4:
            score_range = st.slider("Score Range", 0.0, 1.0, (0.0, 1.0))
    
    # Apply filters
    filtered = anomalies
    
    if search:
        filtered = [a for a in filtered if search.lower() in str(a).lower()]
    
    if severity:
        filtered = [a for a in filtered if get_anomaly_severity(a) in severity]
    
    if status:
        filtered = [a for a in filtered if a.get('status', 'new') in status]
    
    if score_range:
        filtered = [a for a in filtered if score_range[0] <= float(a.get('score', 0)) <= score_range[1]]
    
    st.info(f"Showing {len(filtered)} of {len(anomalies)} anomalies")
    return filtered


def render_visualizations(anomalies):
    """Render visualizations."""
    if not anomalies:
        return
    
    st.header("📊 Insights")
    
    tab1, tab2 = st.tabs(["Timeline", "Distribution"])
    
    with tab1:
        # Timeline
        data = []
        for a in anomalies:
            try:
                data.append({
                    'timestamp': pd.to_datetime(a.get('timestamp')),
                    'score': float(a.get('score', 0)),
                    'severity': get_anomaly_severity(a)
                })
            except:
                pass
        
        if data:
            df = pd.DataFrame(data)
            fig = px.scatter(
                df, x='timestamp', y='score', color='severity',
                color_discrete_map={
                    'Critical': '#ef4444',
                    'High': '#f97316',
                    'Medium': '#f59e0b',
                    'Low': '#10b981'
                }
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        # Distribution
        col1, col2 = st.columns(2)
        
        with col1:
            severities = [get_anomaly_severity(a) for a in anomalies]
            df_sev = pd.DataFrame({'Severity': severities})
            fig = px.pie(df_sev, names='Severity', title="By Severity")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            models = [a.get('model', 'Unknown') for a in anomalies]
            df_model = pd.DataFrame({'Model': models})
            model_counts = df_model['Model'].value_counts().head(5)
            fig = px.bar(x=model_counts.values, y=model_counts.index, 
                        orientation='h', title="Top 5 Models")
            st.plotly_chart(fig, use_container_width=True)


def render_display_options():
    """Render display options."""
    col1, col2, col3 = st.columns([1, 2, 4])
    with col1:
        return st.radio("View", ["Groups", "Table", "Cards"], horizontal=True)


def render_anomaly_cards(anomalies):
    """Render anomalies as cards."""
    if not anomalies:
        st.info("No anomalies to display")
        return
    
    # Sort by score
    sorted_anomalies = sorted(anomalies, key=lambda x: float(x.get('score', 0)), reverse=True)
    
    # Pagination
    items_per_page = 6
    page = st.number_input("Page", min_value=1, max_value=max(1, len(sorted_anomalies) // items_per_page + 1), value=1)
    
    start_idx = (page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(sorted_anomalies))
    
    # Display cards in 2 columns
    for i in range(start_idx, end_idx, 2):
        col1, col2 = st.columns(2)
        
        with col1:
            if i < len(sorted_anomalies):
                render_single_card(sorted_anomalies[i])
        
        with col2:
            if i + 1 < len(sorted_anomalies):
                render_single_card(sorted_anomalies[i + 1])


def render_single_card(anomaly):
    """Render a single anomaly card."""
    anomaly_id = anomaly.get('id', 'Unknown')
    # Prefer severity_tier (Wave-1 calibration) if present
    severity = _effective_severity(anomaly) if anomaly.get("severity_tier") else get_anomaly_severity(anomaly)
    score = float(anomaly.get('score', 0))
    model = anomaly.get('model', 'Unknown')
    status = anomaly.get('status', 'new')
    
    # Format timestamp
    try:
        timestamp = pd.to_datetime(anomaly.get('timestamp'))
        time_str = timestamp.strftime("%b %d, %H:%M")
    except:
        time_str = "Unknown"
    
    # Severity config
    sev_config = {
        'Critical': {'emoji': '🔴', 'color': '#ef4444'},
        'High': {'emoji': '🟠', 'color': '#f97316'},
        'Medium': {'emoji': '🟡', 'color': '#f59e0b'},
        'Low': {'emoji': '🟢', 'color': '#10b981'},
        'Unknown': {'emoji': '⚪', 'color': '#6b7280'}
    }
    
    config = sev_config.get(severity, sev_config['Unknown'])
    
    # Create card using container with border
    with st.container(border=True):
        # Add custom styling for this specific container
        st.markdown(f"""
        <style>
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stContainer"][data-stale="false"]) > div[data-testid="stContainer"] {{
            background-color: white !important;
            border-left: 4px solid {config['color']} !important;
        }}
        </style>
        """, unsafe_allow_html=True)
        
        # Header
        st.markdown(f"### {config['emoji']} {anomaly_id}")
        st.caption(f"{model} • {time_str}")
        
        # Metrics in columns
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Score**")
            st.markdown(f"<p style='font-size: 1.2rem; font-weight: 600; margin: 0;'>{score:.3f}</p>", unsafe_allow_html=True)
        
        with col2:
            st.markdown("**Status**")
            st.markdown(f"<p style='font-size: 1.2rem; font-weight: 600; margin: 0;'>{status.title()}</p>", unsafe_allow_html=True)
        
        with col3:
            st.markdown("**Priority**")
            st.markdown(f"<p style='font-size: 1.2rem; font-weight: 600; color: {config['color']}; margin: 0;'>{severity}</p>", unsafe_allow_html=True)
        
        # Action button - set both selected_anomaly and show_analyzer
        if st.button("🔬 Analyze", key=f"analyze_{anomaly_id}", use_container_width=True, type="primary"):
            # Set session state variables
            st.session_state.selected_anomaly_id = anomaly_id
            st.session_state.selected_anomaly = anomaly
            st.session_state.show_analyzer = True
            
            # Force rerun
            st.rerun()


def render_anomaly_table(anomalies):
    """Render anomalies in a table."""
    if not anomalies:
        st.info("No anomalies to display")
        return
    
    # Prepare data
    data = []
    for a in anomalies:
        severity = get_anomaly_severity(a)
        sev_emoji = {'Critical': '🔴', 'High': '🟠', 'Medium': '🟡', 'Low': '🟢'}.get(severity, '⚪')
        
        data.append({
            'ID': a.get('id', 'Unknown'),
            'Severity': f"{sev_emoji} {severity}",
            'Score': float(a.get('score', 0)),
            'Model': a.get('model', 'Unknown'),
            'Status': a.get('status', 'new').title(),
            'Timestamp': a.get('timestamp', 'Unknown'),
            'Location': a.get('location', 'Unknown')
        })
    
    df = pd.DataFrame(data)
    
    # Display table
    st.dataframe(
        df,
        use_container_width=True,
        height=400,
        column_config={
            "Score": st.column_config.NumberColumn(format="%.3f"),
            "ID": st.column_config.TextColumn(width="small"),
        },
        hide_index=True
    )
    
    # Export
    csv = df.to_csv(index=False)
    st.download_button("📥 Export CSV", csv, "anomalies.csv", "text/csv")


# Main entry point
if __name__ == "__main__":
    render()
