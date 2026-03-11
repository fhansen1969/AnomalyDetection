"""
Dashboard view module for the Anomaly Detection Dashboard.
Enhanced version with modern UI, improved visualizations, and better user experience.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
import requests
import logging
import json
from typing import List, Dict, Any, Optional
import time

# Import from data service
from services.data_service import get_anomalies as get_anomalies_from_db
from services.data_service import get_models as get_models_from_db

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("dashboard")

# Custom CSS for enhanced UI
def inject_custom_css():
    """Inject custom CSS for enhanced UI styling."""
    st.markdown("""
    <style>
    /* Modern color scheme */
    :root {
        --primary-color: #6366f1;
        --secondary-color: #8b5cf6;
        --success-color: #10b981;
        --warning-color: #f59e0b;
        --danger-color: #ef4444;
        --dark-bg: #1f2937;
        --light-bg: #f9fafb;
        --card-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
        --card-hover-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    }
    
    /* Enhanced headers */
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
        letter-spacing: -0.05em;
    }
    
    .sub-header {
        font-size: 1.5rem;
        font-weight: 700;
        color: #374151;
        margin-top: 2rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e5e7eb;
    }
    
    /* Card styling */
    .metric-card {
        background: white;
        border-radius: 0.75rem;
        padding: 1.5rem;
        box-shadow: var(--card-shadow);
        transition: all 0.3s ease;
        border: 1px solid #e5e7eb;
        height: 100%;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--card-hover-shadow);
    }
    
    .metric-icon {
        width: 48px;
        height: 48px;
        border-radius: 0.5rem;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        margin-bottom: 0.75rem;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        line-height: 1;
        margin-bottom: 0.25rem;
    }
    
    .metric-label {
        font-size: 0.875rem;
        color: #6b7280;
        font-weight: 500;
    }
    
    .metric-change {
        font-size: 0.75rem;
        font-weight: 500;
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        margin-top: 0.5rem;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
    }
    
    .metric-change.positive {
        color: var(--success-color);
        background: rgba(16, 185, 129, 0.1);
    }
    
    .metric-change.negative {
        color: var(--danger-color);
        background: rgba(239, 68, 68, 0.1);
    }
    
    /* Enhanced status badges */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.375rem;
        padding: 0.375rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.875rem;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    
    .status-badge.success {
        background: rgba(16, 185, 129, 0.1);
        color: var(--success-color);
        border: 1px solid rgba(16, 185, 129, 0.2);
    }
    
    .status-badge.warning {
        background: rgba(245, 158, 11, 0.1);
        color: var(--warning-color);
        border: 1px solid rgba(245, 158, 11, 0.2);
    }
    
    .status-badge.danger {
        background: rgba(239, 68, 68, 0.1);
        color: var(--danger-color);
        border: 1px solid rgba(239, 68, 68, 0.2);
    }
    
    /* Anomaly cards */
    .anomaly-card {
        background: white;
        border-radius: 0.75rem;
        padding: 1.25rem;
        margin-bottom: 1rem;
        box-shadow: var(--card-shadow);
        border: 1px solid #e5e7eb;
        transition: all 0.3s ease;
        position: relative;
    }
    
    .anomaly-card:hover {
        box-shadow: var(--card-hover-shadow);
        border-color: var(--primary-color);
    }
    
    .severity-indicator {
        width: 4px;
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        border-radius: 0.75rem 0 0 0.75rem;
    }
    
    .severity-critical { background: var(--danger-color); }
    .severity-high { background: #f97316; }
    .severity-medium { background: var(--warning-color); }
    .severity-low { background: var(--success-color); }
    
    /* Progress indicators */
    .progress-ring {
        transform: rotate(-90deg);
    }
    
    /* Agent dialogue styling */
    .dialogue-entry {
        padding: 0.75rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
        border-left: 3px solid;
    }
    
    .dialogue-question {
        background: rgba(99, 102, 241, 0.05);
        border-color: var(--primary-color);
    }
    
    .dialogue-challenge {
        background: rgba(245, 158, 11, 0.05);
        border-color: var(--warning-color);
    }
    
    .dialogue-consensus {
        background: rgba(16, 185, 129, 0.05);
        border-color: var(--success-color);
    }
    
    /* Enhanced buttons */
    .stButton > button {
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
        color: white;
        border: none;
        padding: 0.5rem 1.5rem;
        border-radius: 0.5rem;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 1rem;
        background: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 0.75rem 1.5rem;
        background: transparent;
        border-radius: 0.5rem;
        font-weight: 500;
    }
    
    .stTabs [aria-selected="true"] {
        background: var(--primary-color);
        color: white;
    }
    
    /* Animations */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .fade-in {
        animation: fadeIn 0.5s ease-out;
    }
    
    /* Loading spinner */
    .loading-spinner {
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 3px solid rgba(99, 102, 241, 0.3);
        border-radius: 50%;
        border-top-color: var(--primary-color);
        animation: spin 1s ease-in-out infinite;
    }
    
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    </style>
    """, unsafe_allow_html=True)

# API configuration
def get_api_url():
    """Get the API URL from environment variable or use default."""
    import os
    return os.environ.get("ANOMALY_DETECTION_API_URL", "http://localhost:8000")

# System capabilities check with caching
@st.cache_data(ttl=300)  # Cache for 5 minutes
def check_system_capabilities():
    """Check which system capabilities are available."""
    capabilities = {
        "api_available": False,
        "agents_available": False,
        "storage_available": False,
        "models_available": False,
        "real_time_available": False
    }
    
    try:
        url = f"{get_api_url()}"
        response = requests.get(url, timeout=2)
        capabilities["api_available"] = response.status_code == 200
        
        if capabilities["api_available"]:
            # Check various endpoints
            endpoints_to_check = {
                "agents_available": "/agents/status",
                "storage_available": "/database/status",
                "models_available": "/models",
                "real_time_available": "/stream/status"
            }
            
            for capability, endpoint in endpoints_to_check.items():
                try:
                    resp = requests.get(f"{get_api_url()}{endpoint}", timeout=1)
                    capabilities[capability] = resp.status_code == 200
                except:
                    capabilities[capability] = False
                    
    except Exception as e:
        logger.warning(f"Error checking system capabilities: {e}")
    
    return capabilities

# Initialize system capabilities
SYSTEM_CAPABILITIES = check_system_capabilities()

# Helper function to parse timestamp
def parse_timestamp(timestamp):
    """Parse timestamp from various formats to datetime object."""
    if timestamp is None:
        return None
    
    if isinstance(timestamp, datetime):
        return timestamp
    
    if isinstance(timestamp, str):
        try:
            # Try ISO format first
            return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except:
            try:
                # Try other common formats
                return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            except:
                return None
    
    return None

# Helper function to extract severity - ADDED THIS
def get_anomaly_severity(anomaly):
    """Extract severity from anomaly - consistent with anomalies.py."""
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

# API wrapper functions
def get_anomalies(limit=22, min_score=0.0, model=None, use_cache=True):
    """Get anomalies with caching support."""
    cache_key = f"anomalies_{limit}_{min_score}_{model}"
    
    if use_cache and cache_key in st.session_state:
        cache_time = st.session_state.get(f"{cache_key}_time")
        if cache_time and (datetime.now() - cache_time).seconds < 60:  # 1 minute cache
            return st.session_state[cache_key]
    
    # Always try to get from database first
    data = get_anomalies_from_db(limit=limit, min_score=min_score, model=model)
    
    # Cache the results
    st.session_state[cache_key] = data
    st.session_state[f"{cache_key}_time"] = datetime.now()
    
    return data

def get_models():
    """Get available models."""
    # Always try to get from database
    return get_models_from_db()

def analyze_anomalies(anomalies):
    """Analyze anomalies using the agent system."""
    if not SYSTEM_CAPABILITIES["agents_available"]:
        for anomaly in anomalies:
            if "analysis" not in anomaly:
                anomaly["analysis"] = {}
            anomaly["analysis"]["agent_notice"] = "Agent analysis not available"
        return anomalies
    
    try:
        # Show progress
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Try detailed analysis
        url = f"{get_api_url()}/agents/analyze-detailed"
        status_text.text("Initiating agent analysis...")
        progress_bar.progress(10)
        
        response = requests.post(
            url,
            json=anomalies,
            params={"include_dialogue": True, "include_evidence": True},
            timeout=10
        )
        
        if response.status_code == 200:
            job = response.json()
            job_id = job.get("job_id")
            
            # Poll for completion with visual feedback
            start_time = datetime.now()
            timeout = timedelta(seconds=60)
            
            while (datetime.now() - start_time) < timeout:
                elapsed = (datetime.now() - start_time).seconds
                progress = min(10 + (elapsed / 60) * 80, 90)  # Max 90% during polling
                progress_bar.progress(int(progress))
                
                status_text.text(f"Agents analyzing anomalies... ({elapsed}s)")
                
                job_url = f"{get_api_url()}/jobs/{job_id}"
                job_response = requests.get(job_url, timeout=5)
                
                if job_response.status_code == 200:
                    job_status = job_response.json()
                    if job_status.get("status") == "completed":
                        progress_bar.progress(100)
                        status_text.text("Analysis complete!")
                        time.sleep(0.5)
                        progress_bar.empty()
                        status_text.empty()
                        
                        results = job_status.get("result", {}).get("detailed_results", [])
                        if results:
                            return results
                
                time.sleep(2)
        
        progress_bar.empty()
        status_text.empty()
        return anomalies
        
    except Exception as e:
        logger.warning(f"Error in analyze_anomalies: {str(e)}")
        if 'progress_bar' in locals():
            progress_bar.empty()
        if 'status_text' in locals():
            status_text.empty()
        return anomalies

# UI Components
def render_metric_card(title, value, subtitle="", trend=None, icon="📊", color="#6366f1"):
    """Render an enhanced metric card with trend indicator."""
    trend_html = ""
    if trend is not None:
        if trend > 0:
            trend_html = f'<div class="metric-change positive">↑ {abs(trend)}%</div>'
        elif trend < 0:
            trend_html = f'<div class="metric-change negative">↓ {abs(trend)}%</div>'
    
    card_html = f"""
    <div class="metric-card fade-in">
        <div class="metric-icon" style="background: {color}20; color: {color};">
            {icon}
        </div>
        <div class="metric-value" style="color: {color};">
            {value}
        </div>
        <div class="metric-label">
            {title}
        </div>
        {f'<div style="font-size: 0.75rem; color: #9ca3af; margin-top: 0.25rem;">{subtitle}</div>' if subtitle else ''}
        {trend_html}
    </div>
    """
    
    st.markdown(card_html, unsafe_allow_html=True)

def render_status_badge(status, text):
    """Render a status badge with appropriate styling."""
    status_class = "success" if status == "online" else "warning" if status == "degraded" else "danger"
    icon = "✅" if status == "online" else "⚠️" if status == "degraded" else "❌"
    
    badge_html = f"""
    <div class="status-badge {status_class}">
        <span>{icon}</span>
        <span>{text}</span>
    </div>
    """
    
    st.markdown(badge_html, unsafe_allow_html=True)

def get_time_ago(dt):
    """Get human-readable time ago string."""
    if dt is None:
        return "Unknown"
    
    now = datetime.now()
    if dt.tzinfo is not None:
        now = now.replace(tzinfo=dt.tzinfo)
    
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days}d ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600}h ago"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60}m ago"
    else:
        return "just now"

def get_severity_color(severity):
    """Get color for severity level."""
    colors = {
        "Critical": "#ef4444",
        "High": "#f97316",
        "Medium": "#f59e0b",
        "Low": "#10b981",
        "Unknown": "#6b7280"
    }
    return colors.get(severity, "#6b7280")

# Main render function
def render():
    """Render the enhanced dashboard."""
    # Inject custom CSS
    inject_custom_css()
    
    # Header
    st.markdown("# 🛡️ Anomaly Detection Dashboard")
    st.markdown("Real-time monitoring and analysis of system anomalies")
    
    # Add debug expander at the top
    with st.expander("🔧 Debug Info", expanded=False):
        st.markdown("### Database Status")
        
        # Check anomalies
        all_anomalies = get_anomalies(min_score=0.0)
        st.write(f"**Total anomalies in database:** {len(all_anomalies)}")
        
        if all_anomalies:
            # Show sample anomaly
            sample = all_anomalies[0]
            st.write("**Sample anomaly structure:**")
            st.json({
                'id': sample.get('id'),
                'model': sample.get('model'),
                'score': sample.get('score'),
                'severity': sample.get('severity'),
                'status': sample.get('status'),
                'has_analysis': 'analysis' in sample,
                'has_features': 'features' in sample,
                'timestamp': str(sample.get('timestamp'))
            })
            
            # Count by model
            model_counts = {}
            for a in all_anomalies:
                model = a.get('model', 'Unknown')
                model_counts[model] = model_counts.get(model, 0) + 1
            
            st.write("**Anomalies by model:**")
            st.json(model_counts)
        
        # Check models
        all_models = get_models()
        st.write(f"**Total models in database:** {len(all_models)}")
        
        if all_models:
            st.write("**Models:**")
            for m in all_models:
                st.write(f"- {m.get('name')}: {m.get('status')}")
    
    # Metrics overview
    render_metrics_overview()
    
    # Anomaly trends - full width
    st.markdown("## 📈 Anomaly Trends")
    render_anomaly_trends()

        
def render_metrics_overview():
    """Render metrics overview cards."""
    # Get data
    anomalies = get_anomalies()
    models = get_models()

    # Calculate metrics
    total_anomalies = len(anomalies)
    
    # Calculate trends (comparing to previous period)
    now = datetime.now()
    today_count = 0
    yesterday_count = 0
    
    for a in anomalies:
        if a:
            timestamp = parse_timestamp(a.get('timestamp'))
            if timestamp:
                if timestamp.date() == now.date():
                    today_count += 1
                elif timestamp.date() == (now - timedelta(days=1)).date():
                    yesterday_count += 1
    
    trend = ((today_count - yesterday_count) / max(yesterday_count, 1)) * 100 if yesterday_count > 0 else 0
    
    # Count by severity - UPDATED TO USE HELPER FUNCTION
    critical_count = sum(1 for a in anomalies if a and get_anomaly_severity(a) == 'Critical')
    high_count = sum(1 for a in anomalies if a and get_anomaly_severity(a) == 'High')
    
    # Active models
    active_models = sum(1 for m in models if m and m.get('status') == 'trained')
    
    # Average confidence - UPDATED TO HANDLE STRING ANALYSIS
    confidences = []
    for a in anomalies:
        if not a:
            continue
        analysis = a.get('analysis', {})
        if isinstance(analysis, str):
            try:
                analysis = json.loads(analysis)
            except:
                analysis = {}
        if isinstance(analysis, dict) and analysis.get('confidence'):
            confidences.append(analysis['confidence'])
    
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    # Create columns for cards
    cols = st.columns(5)
    
    # Render custom metric cards using the HTML structure
    with cols[0]:
        render_metric_card(
            title="Total Anomalies",
            value=f"{total_anomalies:,}",
            subtitle="All time detections",
            trend=trend if trend != 0 else None,
            icon="📊",
            color="#6366f1"
        )
    
    with cols[1]:
        render_metric_card(
            title="Critical",
            value=f"{critical_count}",
            subtitle="Immediate action required",
            trend=None,
            icon="🚨",
            color="#ef4444"
        )
    
    with cols[2]:
        render_metric_card(
            title="High Priority",
            value=f"{high_count}",
            subtitle="Review needed",
            trend=None,
            icon="⚠️",
            color="#f97316"
        )
    
    with cols[3]:
        render_metric_card(
            title="Active Models",
            value=f"{active_models}",
            subtitle=f"of {len(models)} total",
            trend=None,
            icon="🤖",
            color="#10b981"
        )
    
    with cols[4]:
        render_metric_card(
            title="Avg Confidence",
            value=f"{avg_confidence:.1%}",
            subtitle="Detection confidence",
            trend=None,
            icon="🎯",
            color="#8b5cf6"
        )

def render_anomaly_trends():
    """Render enhanced anomaly trends visualization."""
    # Time range selector
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        time_range = st.selectbox(
            "Time Range",
            ["Last 7 days", "Last 30 days", "Last 90 days"],
            label_visibility="collapsed"
        )
    
    # Calculate days based on selection
    days_map = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90}
    days = days_map[time_range]
    
    # Get anomalies
    anomalies = get_anomalies(limit=2000)
    
    if not anomalies:
        st.info("No anomaly data available to display trends.")
        return
    
    # Process data for visualization
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Create date range
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # Initialize data structure
    trend_data = {
        'date': [],
        'Critical': [],
        'High': [],
        'Medium': [],
        'Low': []
    }
    
    # Count anomalies by date and severity - UPDATED TO USE HELPER FUNCTION
    for date in date_range:
        date_str = date.strftime('%Y-%m-%d')
        trend_data['date'].append(date_str)
        
        for severity in ['Critical', 'High', 'Medium', 'Low']:
            count = 0
            for a in anomalies:
                if a:
                    timestamp = parse_timestamp(a.get('timestamp'))
                    if timestamp and timestamp.date() == date.date():
                        if get_anomaly_severity(a) == severity:
                            count += 1
            trend_data[severity].append(count)
    
    df = pd.DataFrame(trend_data)
    
    # Create interactive chart
    fig = go.Figure()
    
    colors = {
        'Critical': '#ef4444',
        'High': '#f97316',
        'Medium': '#f59e0b',
        'Low': '#10b981'
    }
    
    for severity in ['Low', 'Medium', 'High', 'Critical']:  # Stack order
        fig.add_trace(go.Bar(
            name=severity,
            x=df['date'],
            y=df[severity],
            marker_color=colors[severity],
            hovertemplate=f'<b>{severity}</b><br>Date: %{{x}}<br>Count: %{{y}}<extra></extra>'
        ))
    
    fig.update_layout(
        barmode='stack',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            showgrid=False,
            title="",
            tickformat='%b %d'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(0,0,0,0.05)',
            title="Number of Anomalies"
        ),
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)

def get_anomaly_type(anomaly):
    """Determine a meaningful type/description for the anomaly."""
    # Check if there's a type in analysis
    analysis = anomaly.get('analysis', {})
    if isinstance(analysis, str):
        try:
            analysis = json.loads(analysis)
        except:
            analysis = {}
    
    if isinstance(analysis, dict):
        if analysis.get('threat_type'):
            return analysis['threat_type']
        if analysis.get('type'):
            return analysis['type']
    
    # Try to infer from features
    features = anomaly.get('features', [])
    if features:
        if isinstance(features, list) and len(features) > 0:
            # Use first feature as type
            return str(features[0]).replace('_', ' ').title()
        elif isinstance(features, dict):
            # Get first key from dict
            keys = list(features.keys())
            if keys:
                return keys[0].replace('_', ' ').title()
    
    # Try to infer from data
    data = anomaly.get('data', {})
    if isinstance(data, dict):
        if 'bytes_transferred' in data and data.get('bytes_transferred', 0) > 1000000:
            return "High Data Transfer"
        if 'protocol' in data:
            return f"{data['protocol']} Activity"
    
    # Use model name as fallback
    model = anomaly.get('model', 'Unknown')
    return f"{model.replace('_', ' ').title()} Detection"

def render_recent_anomalies():
    """Render recent anomalies with detailed information."""
    # Controls
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # Get all unique severities from current anomalies - NO FILTER, SHOW ALL
        all_severities = ["Critical", "High", "Medium", "Low", "Unknown"]
        
        severity_filter = st.multiselect(
            "Filter by Severity",
            all_severities,
            default=all_severities  # Show all by default
        )
    
    with col2:
        # Get all models - without pre-filtering
        all_anomalies_for_models = get_anomalies(limit=1000, min_score=0.0)
        all_models = sorted(list(set(a.get('model', '') for a in all_anomalies_for_models if a and a.get('model'))))
        
        model_filter = st.selectbox(
            "Filter by Model",
            ["All Models"] + all_models
        )
    
    with col3:
        if SYSTEM_CAPABILITIES["agents_available"]:
            analyze_button = st.button("🔍 Analyze", use_container_width=True)
        else:
            analyze_button = False
    
    # Get filtered anomalies - NO MIN SCORE FILTER
    anomalies = get_anomalies(limit=50, min_score=0.0)
    
    # Apply filters - UPDATED TO USE HELPER FUNCTION
    if severity_filter:
        filtered_anomalies = []
        for a in anomalies:
            if a:
                severity = get_anomaly_severity(a)
                if severity in severity_filter:
                    filtered_anomalies.append(a)
        
        anomalies = filtered_anomalies
    
    if model_filter != "All Models":
        anomalies = [a for a in anomalies if a and a.get('model') == model_filter]
    
    # Display anomalies
    if not anomalies:
        st.info("No anomalies found matching the selected filters.")
    else:
        # Render anomaly cards
        for idx, anomaly in enumerate(anomalies[:10]):  # Show max 10
            if anomaly:
                severity = get_anomaly_severity(anomaly)
                severity_class = f"severity-{severity.lower()}"
                severity_color = get_severity_color(severity)
                
                timestamp = parse_timestamp(anomaly.get('timestamp'))
                time_ago = get_time_ago(timestamp) if timestamp else "Unknown"
                
                # Get anomaly type using helper function
                anomaly_type = get_anomaly_type(anomaly)
                
                # Get analysis for summary
                analysis = anomaly.get('analysis', {})
                if isinstance(analysis, str):
                    try:
                        analysis = json.loads(analysis)
                    except:
                        analysis = {}
                
                # Get summary text
                summary_text = "No details available"
                if isinstance(analysis, dict):
                    summary_text = analysis.get('summary', analysis.get('description', ''))
                
                # If no summary, try to create one from features
                if not summary_text or summary_text == "No details available":
                    features = anomaly.get('features', [])
                    if features:
                        if isinstance(features, list):
                            summary_text = f"Detected: {', '.join(str(f) for f in features[:3])}"
                        elif isinstance(features, dict):
                            summary_text = f"Anomaly detected with score {anomaly.get('score', 0):.3f}"
                
                # Anomaly card HTML
                card_html = f"""
                <div class="anomaly-card">
                    <div class="{severity_class} severity-indicator"></div>
                    <div style="margin-left: 1rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                            <h4 style="margin: 0; color: #1f2937; font-size: 1.1rem;">{anomaly_type}</h4>
                            <span class="status-badge {severity.lower()}" style="font-size: 0.75rem;">
                                {severity}
                            </span>
                        </div>
                        <div style="color: #6b7280; font-size: 0.875rem; margin-bottom: 0.5rem;">
                            <span>🤖 {anomaly.get('model', 'Unknown Model')}</span>
                            <span style="margin-left: 1rem;">⏱️ {time_ago}</span>
                            <span style="margin-left: 1rem;">📊 Score: {anomaly.get('score', 0):.2f}</span>
                        </div>
                        <div style="color: #374151; font-size: 0.9rem;">
                            {summary_text}
                        </div>
                    </div>
                </div>
                """
                
                st.markdown(card_html, unsafe_allow_html=True)
                
                # Add expander for more details
                with st.expander(f"View Details - Anomaly #{anomaly.get('id', idx + 1)}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Raw Features:**")
                        features = anomaly.get('features', {})
                        if isinstance(features, str):
                            try:
                                features = json.loads(features)
                            except:
                                pass
                        st.json(features)
                    
                    with col2:
                        st.write("**Analysis Results:**")
                        st.json(analysis)
        
def render_model_performance():
    """Render model performance metrics."""
    models = get_models()

    if not models:
        st.info("No model data available. Please ensure models are loaded in the database.")
        return
    
    # Show model count and status
    st.markdown(f"**Total Models:** {len(models)}")
    
    # Count by status
    status_counts = {}
    for m in models:
        if m:
            status = m.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
    
    # Display status breakdown
    status_cols = st.columns(len(status_counts) if status_counts else 1)
    for idx, (status, count) in enumerate(status_counts.items()):
        with status_cols[idx]:
            status_emoji = "✅" if status == "trained" else "⚙️" if status == "training" else "❌"
            st.metric(status.replace('_', ' ').title(), count, label_visibility="visible")
    
    # Filter trained models with performance data
    trained_models = []
    for m in models:
        if m and m.get('status') == 'trained':
            # Check if performance data exists
            perf = m.get('performance', {})
            if isinstance(perf, str):
                try:
                    perf = json.loads(perf)
                except:
                    perf = {}
            
            # Ensure we have valid performance metrics
            if perf and any(perf.get(metric, 0) > 0 for metric in ['accuracy', 'precision', 'recall', 'f1']):
                m['performance'] = perf
                trained_models.append(m)
    
    if not trained_models:
        st.info("""
        **No performance data available yet**
        
        Models need to be trained with test data to show performance metrics.
        """)
        
        # Show all models in a nice table
        if models:
            st.markdown("### Models Overview")
            model_data = []
            for model in models:
                if model:
                    model_data.append({
                        'Name': model.get('name', 'Unknown'),
                        'Type': model.get('type', 'Unknown'),
                        'Status': model.get('status', 'unknown')
                    })
            
            if model_data:
                st.dataframe(model_data, use_container_width=True, hide_index=True)
        return
    
    # Create performance comparison
    model_names = []
    metrics = {'Accuracy': [], 'Precision': [], 'Recall': [], 'F1': []}
    
    for model in trained_models[:6]:  # Show top 6
        name = model['name'].replace('_model', '').replace('_', ' ').title()
        model_names.append(name)
        
        perf = model['performance']
        metrics['Accuracy'].append(perf.get('accuracy', 0))
        metrics['Precision'].append(perf.get('precision', 0))
        metrics['Recall'].append(perf.get('recall', 0))
        metrics['F1'].append(perf.get('f1', 0))
    
    # Create radar chart
    fig = go.Figure()
    
    for i, model_name in enumerate(model_names):
        values = [
            metrics['Accuracy'][i],
            metrics['Precision'][i],
            metrics['Recall'][i],
            metrics['F1'][i]
        ]
        
        fig.add_trace(go.Scatterpolar(
            r=values + [values[0]],  # Close the polygon
            theta=['Accuracy', 'Precision', 'Recall', 'F1', 'Accuracy'],
            fill='toself',
            name=model_name,
            opacity=0.6,
            hovertemplate='%{theta}: %{r:.1%}<extra></extra>'
        ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                tickformat='.0%'
            )
        ),
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.1
        ),
        margin=dict(l=0, r=100, t=0, b=0),
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Model training status
    training_models = [m for m in models if m and m.get('status') == 'training']
    if training_models:
        st.markdown("### Training Progress")
        for model in training_models:
            progress = model.get('training_progress', 0)
            st.progress(progress, text=f"{model['name']} - {progress:.0%}")

def render_live_feed():
    """Render live anomaly feed (simulated)."""
    # Initialize feed data in session state
    if 'live_feed_data' not in st.session_state:
        st.session_state.live_feed_data = []
        st.session_state.last_feed_update = datetime.now()
    
    # Container with custom styling
    st.markdown("""
    <style>
    .feed-container {
        background: #f9fafb;
        padding: 1rem;
        border-radius: 0.5rem;
        height: 400px;
        overflow-y: auto;
    }
    .feed-item {
        background: white;
        padding: 0.75rem;
        margin-bottom: 0.5rem;
        border-radius: 0.25rem;
        border-left: 3px solid;
        transition: all 0.2s ease;
    }
    .feed-item:hover {
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Add auto-refresh toggle
    col1, col2 = st.columns([3, 1])
    with col1:
        auto_refresh = st.checkbox("Auto-refresh", value=True, key="live_feed_auto_refresh")
    with col2:
        if st.button("🔄 Refresh", key="manual_refresh"):
            # Generate new anomaly on manual refresh
            severities = ['Low', 'Medium', 'High', 'Critical']
            models = ['isolation_forest', 'autoencoder', 'lstm_model']
            
            new_anomaly = {
                'id': len(st.session_state.live_feed_data) + 1,
                'timestamp': datetime.now(),
                'severity': np.random.choice(severities, p=[0.4, 0.3, 0.2, 0.1]),
                'model': np.random.choice(models),
                'score': np.random.uniform(0.7, 0.99),
                'type': np.random.choice(['Network spike', 'CPU anomaly', 'Memory leak', 'Disk I/O surge'])
            }
            
            st.session_state.live_feed_data.append(new_anomaly)
            st.session_state.live_feed_data = st.session_state.live_feed_data[-10:]  # Keep last 10
    
    # Create feed container
    feed_container = st.container()
    
    with feed_container:
        if not st.session_state.live_feed_data:
            # Show placeholder when no data
            st.markdown("""
            <div style="text-align: center; padding: 2rem; color: #6b7280;">
                <div class="loading-spinner" style="margin: 0 auto;"></div>
                <p style="margin-top: 1rem;">Waiting for anomalies...</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Display anomalies using Streamlit components
            for entry in reversed(st.session_state.live_feed_data[-5:]):  # Show last 5
                severity_color = get_severity_color(entry['severity'])
                time_ago = get_time_ago(entry['timestamp'])
                
                # Create a nice card for each anomaly
                with st.container():
                    st.markdown(f"""
                    <div style="background: white; padding: 0.75rem; margin-bottom: 0.5rem; 
                              border-radius: 0.25rem; border-left: 3px solid {severity_color};">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <strong style="color: #1f2937;">{entry['type']}</strong>
                            <small style="color: #6b7280;">{time_ago}</small>
                        </div>
                        <div style="margin-top: 0.25rem; font-size: 0.875rem; color: #6b7280;">
                            <span style="color: {severity_color}; font-weight: 500;">{entry['severity']}</span>
                            • Model: {entry['model']} • Score: {entry['score']:.2f}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    
    # Auto-refresh logic without blocking the UI
    if auto_refresh:
        # Use Streamlit's native auto-refresh with fragment
        time_since_update = (datetime.now() - st.session_state.last_feed_update).seconds
        if time_since_update >= 10:  # Update every 10 seconds
            # Generate new anomaly
            severities = ['Low', 'Medium', 'High', 'Critical']
            models = ['isolation_forest', 'autoencoder', 'lstm_model']
            
            new_anomaly = {
                'id': len(st.session_state.live_feed_data) + 1,
                'timestamp': datetime.now(),
                'severity': np.random.choice(severities, p=[0.4, 0.3, 0.2, 0.1]),
                'model': np.random.choice(models),
                'score': np.random.uniform(0.7, 0.99),
                'type': np.random.choice(['Network spike', 'CPU anomaly', 'Memory leak', 'Disk I/O surge'])
            }
            
            st.session_state.live_feed_data.append(new_anomaly)
            st.session_state.live_feed_data = st.session_state.live_feed_data[-10:]
            st.session_state.last_feed_update = datetime.now()
            st.rerun()

# Run the dashboard
if __name__ == "__main__":
    render()