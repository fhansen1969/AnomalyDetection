"""
Enhanced anomaly details component that shows comprehensive information about anomaly origins.
This version uses REAL data from the API/database with beautiful, modern UI components.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
import numpy as np
from typing import Dict, Any, List, Optional

# Import data service functions for real data
from services.data_service import (
    get_anomalies,
    get_anomaly_by_id,
    get_anomaly_analysis,
    get_agent_activities,
    get_agent_messages,
    execute_query
)

def render_anomaly_origin_details(anomaly: Dict[str, Any]):
    """Render comprehensive details about where an anomaly came from using REAL data."""
    
    st.markdown("## 🔎 Anomaly Origin & Context")
    
    # Create tabs for different aspects of the anomaly
    tabs = st.tabs([
        "🏢 Source Location",
        "🌐 Network Details", 
        "📊 Data Context",
        "🔎 Detection Path",
        "📈 Feature Analysis",
        "🕐 Timeline"
    ])
    
    with tabs[0]:
        render_source_location(anomaly)
    
    with tabs[1]:
        render_network_details(anomaly)
    
    with tabs[2]:
        render_data_context(anomaly)
    
    with tabs[3]:
        render_detection_path(anomaly)
    
    with tabs[4]:
        render_feature_analysis(anomaly)
    
    with tabs[5]:
        render_anomaly_timeline(anomaly)

def render_source_location(anomaly: Dict[str, Any]):
    """Render information about where the anomaly originated using REAL data."""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🏢 System Information")
        
        # Extract REAL location data from anomaly
        location_data = {
            "Data Center": anomaly.get('location', 'Unknown'),
            "Server ID": anomaly.get('server_id', 'Unknown'),
            "Source IP": anomaly.get('src_ip', 'N/A'),
            "Destination IP": anomaly.get('dst_ip', 'N/A'),
            "Model": anomaly.get('model', 'Unknown'),
            "Detection Time": format_timestamp(anomaly.get('detection_time', anomaly.get('timestamp')))
        }
        
        # Add additional system info if available in the data field
        data = anomaly.get('data', {})
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                data = {}
        
        if isinstance(data, dict):
            if 'cluster' in data:
                location_data["Server Cluster"] = data['cluster']
            if 'service' in data:
                location_data["Service"] = data['service']
            if 'environment' in data:
                location_data["Environment"] = data['environment']
            if 'region' in data:
                location_data["Region"] = data['region']
        
        for key, value in location_data.items():
            st.metric(key, value)
    
    with col2:
        st.markdown("### 🗺️ Geographic Location")
        
        # Create a map visualization based on REAL location data
        location_coords = {
            'us-east-1': {'lat': 38.7469, 'lon': -77.4758, 'name': 'US East (Virginia)'},
            'us-west-2': {'lat': 45.5152, 'lon': -122.6784, 'name': 'US West (Oregon)'},
            'eu-central-1': {'lat': 50.1109, 'lon': 8.6821, 'name': 'EU (Frankfurt)'},
            'ap-south-1': {'lat': 19.0760, 'lon': 72.8777, 'name': 'Asia Pacific (Mumbai)'},
            'sa-east-1': {'lat': -23.5505, 'lon': -46.6333, 'name': 'South America (São Paulo)'}
        }
        
        location = anomaly.get('location', 'us-east-1')
        coords = location_coords.get(location, location_coords['us-east-1'])
        
        # If we have actual lat/lon in the data, use those
        if 'latitude' in data and 'longitude' in data:
            coords = {
                'lat': data['latitude'],
                'lon': data['longitude'],
                'name': location
            }
        
        fig = go.Figure(go.Scattergeo(
            lon=[coords['lon']],
            lat=[coords['lat']],
            text=coords['name'],
            mode='markers+text',
            marker=dict(
                size=20,
                color='red',
                line=dict(width=2, color='white')
            ),
            textposition="top center"
        ))
        
        fig.update_layout(
            geo=dict(
                projection_type='natural earth',
                showland=True,
                landcolor='rgb(243, 243, 243)',
                coastlinecolor='rgb(204, 204, 204)',
                showlakes=True,
                lakecolor='rgb(255, 255, 255)'
            ),
            height=300,
            margin=dict(l=0, r=0, t=0, b=0)
        )
        
        st.plotly_chart(fig, use_container_width=True)

def render_network_details(anomaly: Dict[str, Any]):
    """Render network-related information about the anomaly using REAL data."""
    
    st.markdown("### 🌐 Network Flow Analysis")
    
    # Extract REAL network data from anomaly
    data = anomaly.get('data', {})
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            data = {}
    
    # Network details from REAL data
    network_data = {
        "Source IP": anomaly.get('src_ip', data.get('src_ip', 'Unknown')),
        "Destination IP": anomaly.get('dst_ip', data.get('dst_ip', 'Unknown')),
        "Source Port": data.get('src_port', 'N/A'),
        "Destination Port": data.get('dst_port', 'N/A'),
        "Protocol": data.get('protocol', 'Unknown'),
        "Bytes Transferred": f"{data.get('bytes_transferred', 0):,}" if 'bytes_transferred' in data else 'N/A',
        "Packets": f"{data.get('packets', 0):,}" if 'packets' in data else 'N/A',
        "Duration": f"{data.get('duration', 0)} seconds" if 'duration' in data else 'N/A'
    }
    
    # Display in columns
    cols = st.columns(4)
    for i, (key, value) in enumerate(network_data.items()):
        with cols[i % 4]:
            st.metric(key, value)
    
    # Network path visualization based on REAL data
    st.markdown("### 🛤️ Network Path")
    
    # Build network path from real data
    path_nodes = []
    
    # Source
    if anomaly.get('src_ip'):
        path_nodes.append({"name": f"Source\n{anomaly.get('src_ip')}", "type": "source"})
    
    # Intermediate nodes based on data
    if 'network_path' in data:
        for hop in data['network_path']:
            path_nodes.append({"name": hop, "type": "network"})
    else:
        # Default path if not specified
        if 'firewall' in data or data.get('firewall_rule'):
            path_nodes.append({"name": "Firewall\n(Ingress)", "type": "security"})
        if 'load_balancer' in data:
            path_nodes.append({"name": f"Load Balancer\n{data['load_balancer']}", "type": "network"})
    
    # Destination
    if anomaly.get('dst_ip'):
        path_nodes.append({"name": f"Destination\n{anomaly.get('dst_ip')}", "type": "destination"})
    
    if path_nodes:
        fig = create_network_path_diagram(path_nodes)
        st.plotly_chart(fig, use_container_width=True)
    
    # Additional REAL network context
    with st.expander("🔍 Additional Network Context"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Connection Details**")
            connection_details = {}
            
            # Extract real connection details from data
            if 'tcp_flags' in data:
                connection_details["TCP Flags"] = data['tcp_flags']
            if 'window_size' in data:
                connection_details["Window Size"] = data['window_size']
            if 'ttl' in data:
                connection_details["TTL"] = data['ttl']
            if 'mss' in data:
                connection_details["MSS"] = data['mss']
            
            if connection_details:
                st.json(connection_details)
            else:
                st.info("No additional connection details available")
        
        with col2:
            st.markdown("**Security Context**")
            security_context = {}
            
            # Extract real security context from data
            if 'firewall_rule' in data:
                security_context["Firewall Rule"] = data['firewall_rule']
            if 'ids_alert' in data:
                security_context["IDS Alert"] = data['ids_alert']
            if 'dpi_result' in data:
                security_context["DPI Result"] = data['dpi_result']
            if 'tls_version' in data:
                security_context["SSL/TLS Version"] = data['tls_version']
            
            if security_context:
                st.json(security_context)
            else:
                st.info("No security context available")

def render_data_context(anomaly: Dict[str, Any]):
    """Render the REAL data context that triggered the anomaly with beautiful formatting."""
    
    st.markdown("### 📊 Data Context")
    
    # Get the ACTUAL data that triggered the anomaly
    anomaly_data = anomaly.get('data', {})
    
    if isinstance(anomaly_data, str):
        try:
            anomaly_data = json.loads(anomaly_data)
        except:
            anomaly_data = {"raw_data": anomaly_data}
    
    # Create tabs for better organization
    tab1, tab2, tab3 = st.tabs(["🎯 Key Information", "📊 Triggering Metrics", "📥 Data Source"])
    
    with tab1:
        render_key_information_card(anomaly, anomaly_data)
    
    with tab2:
        render_triggering_metrics_card(anomaly, anomaly_data)
    
    with tab3:
        render_data_source_card(anomaly, anomaly_data)

def render_key_information_card(anomaly: Dict[str, Any], anomaly_data: Dict[str, Any]):
    """Render a beautiful card with key anomaly information."""
    
    # Get basic info
    anomaly_id = anomaly.get('id', 'Unknown')
    detection_time = format_timestamp(anomaly.get('detection_time', anomaly.get('timestamp')))
    location = anomaly.get('location', 'Unknown')
    src_ip = anomaly.get('src_ip', 'N/A')
    dst_ip = anomaly.get('dst_ip', 'N/A')
    threshold = anomaly.get('threshold', 0.5)
    
    # Create styled card
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 25px;
        color: white;
        box-shadow: 0 10px 25px rgba(0,0,0,0.2);
        margin-bottom: 20px;
    ">
        <h3 style="margin: 0 0 20px 0; font-size: 1.5rem; font-weight: 700;">
            🔍 Basic Information
        </h3>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
            <div style="background: rgba(255,255,255,0.1); padding: 12px; border-radius: 8px;">
                <div style="font-size: 0.85rem; opacity: 0.9; margin-bottom: 5px;">Anomaly ID</div>
                <div style="font-size: 1.1rem; font-weight: 600;">{anomaly_id}</div>
            </div>
            
            <div style="background: rgba(255,255,255,0.1); padding: 12px; border-radius: 8px;">
                <div style="font-size: 0.85rem; opacity: 0.9; margin-bottom: 5px;">Detection Time</div>
                <div style="font-size: 1.1rem; font-weight: 600;">{detection_time}</div>
            </div>
            
            <div style="background: rgba(255,255,255,0.1); padding: 12px; border-radius: 8px;">
                <div style="font-size: 0.85rem; opacity: 0.9; margin-bottom: 5px;">Location</div>
                <div style="font-size: 1.1rem; font-weight: 600;">{location}</div>
            </div>
            
            <div style="background: rgba(255,255,255,0.1); padding: 12px; border-radius: 8px;">
                <div style="font-size: 0.85rem; opacity: 0.9; margin-bottom: 5px;">Detection Threshold</div>
                <div style="font-size: 1.1rem; font-weight: 600;">{threshold:.2f}</div>
            </div>
        </div>
        
        <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 8px;">
            <div style="font-size: 0.85rem; opacity: 0.9; margin-bottom: 8px;">Network Details</div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="opacity: 0.8; font-size: 0.9rem;">Source:</span>
                    <span style="font-weight: 600; margin-left: 8px;">{src_ip}</span>
                </div>
                <div style="opacity: 0.6;">→</div>
                <div>
                    <span style="opacity: 0.8; font-size: 0.9rem;">Destination:</span>
                    <span style="font-weight: 600; margin-left: 8px;">{dst_ip}</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Triggering Features Card
    features = anomaly.get('features', [])
    
    if features:
        # Convert features to list if needed
        if isinstance(features, str):
            try:
                features = json.loads(features)
            except:
                features = [features]
        elif isinstance(features, dict):
            features = list(features.keys())
        
        if features:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                border-radius: 15px;
                padding: 25px;
                color: white;
                box-shadow: 0 10px 25px rgba(0,0,0,0.2);
                margin-bottom: 20px;
            ">
                <h3 style="margin: 0 0 15px 0; font-size: 1.5rem; font-weight: 700;">
                    🎯 Triggering Features
                </h3>
                <div style="display: flex; flex-wrap: wrap; gap: 10px;">
            """, unsafe_allow_html=True)
            
            for feature in features[:10]:  # Limit to 10 features
                feature_str = str(feature)
                st.markdown(f"""
                    <div style="
                        background: rgba(255,255,255,0.2);
                        padding: 8px 15px;
                        border-radius: 20px;
                        font-size: 0.9rem;
                        font-weight: 500;
                        display: inline-block;
                    ">
                        ✓ {feature_str}
                    </div>
                """, unsafe_allow_html=True)
            
            st.markdown("</div></div>", unsafe_allow_html=True)
    
    # Additional Details Card
    details = anomaly.get('details', {})
    
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except:
            details = {}
    
    if details and isinstance(details, dict) and len(details) > 0:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            border-radius: 15px;
            padding: 25px;
            color: white;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
        ">
            <h3 style="margin: 0 0 15px 0; font-size: 1.5rem; font-weight: 700;">
                📋 Additional Details
            </h3>
        """, unsafe_allow_html=True)
        
        # Display details in a grid
        detail_items = list(details.items())[:8]  # Limit to 8 items
        
        for key, value in detail_items:
            value_str = str(value)
            if len(value_str) > 50:
                value_str = value_str[:47] + "..."
            
            st.markdown(f"""
            <div style="
                background: rgba(255,255,255,0.15);
                padding: 12px 15px;
                border-radius: 8px;
                margin-bottom: 10px;
            ">
                <div style="font-size: 0.85rem; opacity: 0.9; margin-bottom: 3px;">{key}</div>
                <div style="font-size: 1rem; font-weight: 600;">{value_str}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)

def render_triggering_metrics_card(anomaly: Dict[str, Any], anomaly_data: Dict[str, Any]):
    """Render triggering metrics in a beautiful card format."""
    
    # Extract actual metrics from the data
    metrics = extract_real_metrics(anomaly_data, anomaly)
    
    if metrics:
        st.markdown("""
        <div style="margin-bottom: 20px;">
            <h4 style="color: #333; margin-bottom: 15px;">📊 Key Metrics</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # Display metrics in cards
        cols = st.columns(min(len(metrics), 3))
        
        for i, (metric, value) in enumerate(metrics.items()):
            with cols[i % len(cols)]:
                # Check if this metric contributed to the anomaly
                is_anomalous = check_if_metric_anomalous(metric, value, anomaly)
                
                # Choose color based on anomalous status
                if is_anomalous:
                    gradient = "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)"
                    badge_color = "#ff4757"
                    badge_text = "⚠️ Anomalous"
                else:
                    gradient = "linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)"
                    badge_color = "#2ed573"
                    badge_text = "✓ Normal"
                
                formatted_value = format_metric_value(value)
                
                st.markdown(f"""
                <div style="
                    background: {gradient};
                    border-radius: 12px;
                    padding: 20px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                    margin-bottom: 15px;
                    color: white;
                ">
                    <div style="
                        display: inline-block;
                        background: {badge_color};
                        padding: 3px 10px;
                        border-radius: 12px;
                        font-size: 0.75rem;
                        font-weight: 600;
                        margin-bottom: 10px;
                    ">
                        {badge_text}
                    </div>
                    <div style="font-size: 0.9rem; opacity: 0.95; margin-bottom: 5px;">
                        {metric}
                    </div>
                    <div style="font-size: 1.8rem; font-weight: 700;">
                        {formatted_value}
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
    # Show the ACTUAL raw data in an expandable section
    with st.expander("📄 View Raw Data"):
        if anomaly_data:
            st.json(anomaly_data)
        else:
            st.info("No raw data available")

def render_data_source_card(anomaly: Dict[str, Any], anomaly_data: Dict[str, Any]):
    """Render data source information in a beautiful card."""
    
    # Extract real source info
    source_info = {
        "Collection Method": anomaly.get('collection_method', anomaly_data.get('collection_method', 'Unknown')),
        "Data Pipeline": anomaly.get('pipeline', anomaly_data.get('pipeline', 'Unknown')),
        "Ingestion Time": format_timestamp(anomaly.get('ingestion_time', anomaly.get('timestamp'))),
        "Model Used": anomaly.get('model', 'Unknown'),
        "Anomaly Score": f"{anomaly.get('score', 0):.3f}",
        "Threshold": f"{anomaly.get('threshold', 0.5):.2f}"
    }
    
    # Add processing info if available
    if 'processing_latency' in anomaly_data:
        try:
            latency = float(anomaly_data['processing_latency'])
            source_info["Processing Latency"] = f"{latency:.2f}s"
        except (ValueError, TypeError):
            source_info["Processing Latency"] = str(anomaly_data['processing_latency'])
    
    if 'data_quality' in anomaly_data:
        try:
            # Try to convert to float if it's a number
            quality = float(anomaly_data['data_quality'])
            # If it's already a percentage (> 1), just format it, otherwise multiply by 100
            if quality > 1:
                source_info["Data Quality Score"] = f"{quality:.2f}%"
            else:
                source_info["Data Quality Score"] = f"{quality:.2%}"
        except (ValueError, TypeError):
            # If it's already a string, just use it as is
            source_info["Data Quality Score"] = str(anomaly_data['data_quality'])
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 25px;
        color: white;
        box-shadow: 0 10px 25px rgba(0,0,0,0.2);
    ">
        <h3 style="margin: 0 0 20px 0; font-size: 1.5rem; font-weight: 700;">
            📥 Data Source Information
        </h3>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
    """, unsafe_allow_html=True)
    
    for key, value in source_info.items():
        st.markdown(f"""
        <div style="
            background: rgba(255,255,255,0.15);
            padding: 15px;
            border-radius: 8px;
            border-left: 3px solid rgba(255,255,255,0.5);
        ">
            <div style="font-size: 0.85rem; opacity: 0.9; margin-bottom: 5px;">{key}</div>
            <div style="font-size: 1.1rem; font-weight: 600;">{value}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("</div></div>", unsafe_allow_html=True)

def render_detection_path(anomaly: Dict[str, Any]):
    """Show how the anomaly was ACTUALLY detected through the system."""
    
    st.markdown("### 🔎 Detection Path")
    
    # Get REAL agent activities for this anomaly
    activities = get_agent_activities(anomaly_id=anomaly.get('id'))
    
    if activities:
        # Show actual detection steps from agent activities
        st.markdown("#### Real Detection Timeline")
        
        for activity in activities:
            timestamp = activity.get('timestamp')
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    time_str = timestamp.strftime('%H:%M:%S')
                except:
                    time_str = 'Unknown'
            else:
                time_str = 'Unknown'
            
            agent = activity.get('agent_id', activity.get('agent', 'Unknown'))
            action = activity.get('activity_type', activity.get('action', 'Unknown'))
            status = activity.get('status', 'Unknown')
            
            col1, col2, col3 = st.columns([1, 3, 1])
            
            with col1:
                if status == 'completed':
                    st.success(f"✅ {agent}")
                elif status == 'failed':
                    st.error(f"❌ {agent}")
                else:
                    st.info(f"🔄 {agent}")
            
            with col2:
                st.markdown(f"**{action}**")
                if 'description' in activity:
                    st.caption(activity['description'])
            
            with col3:
                st.caption(time_str)
    
    else:
        # If no activities, show detection info from anomaly data
        st.markdown("#### Detection Information")
        
        detection_info = {
            "Detection Time": format_timestamp(anomaly.get('detection_time', anomaly.get('timestamp'))),
            "Model": anomaly.get('model', 'Unknown'),
            "Model Version": anomaly.get('model_version', 'Unknown'),
            "Anomaly Score": f"{anomaly.get('score', 0):.3f}",
            "Detection Threshold": f"{anomaly.get('threshold', 0.5):.2f}",
            "Status": anomaly.get('status', 'Unknown')
        }
        
        # Add model-specific info if available
        data = anomaly.get('data', {})
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                data = {}
        
        if 'model_confidence' in data:
            detection_info["Model Confidence"] = f"{data['model_confidence']:.1%}"
        if 'detection_method' in data:
            detection_info["Detection Method"] = data['detection_method']
        
        cols = st.columns(3)
        for i, (key, value) in enumerate(detection_info.items()):
            with cols[i % 3]:
                st.metric(key, value)
    
    # Show REAL model decision details if available
    analysis = get_anomaly_analysis(anomaly.get('id'))
    if analysis:
        st.markdown("#### 🤖 Model Analysis Details")
        
        if 'analysis_content' in analysis:
            analysis_content = analysis['analysis_content']
            if isinstance(analysis_content, str):
                try:
                    analysis_content = json.loads(analysis_content)
                except:
                    pass
            
            if isinstance(analysis_content, dict):
                col1, col2 = st.columns(2)
                
                with col1:
                    if 'threat_level' in analysis_content:
                        st.metric("Threat Level", analysis_content['threat_level'])
                    if 'confidence' in analysis_content:
                        st.metric("Confidence", f"{analysis_content['confidence']:.1%}")
                
                with col2:
                    if 'threat_type' in analysis_content:
                        st.metric("Threat Type", analysis_content['threat_type'])
                    if 'risk_score' in analysis_content:
                        st.metric("Risk Score", f"{analysis_content['risk_score']:.2f}")

def render_feature_analysis(anomaly: Dict[str, Any]):
    """Analyze and visualize the REAL features that contributed to the anomaly."""
    
    st.markdown("### 📈 Feature Analysis")
    
    # Get REAL features from the anomaly
    features = anomaly.get('features', [])
    
    # If features is a string, try to parse it
    if isinstance(features, str):
        try:
            features = json.loads(features)
        except:
            # If it's not JSON, split by common delimiters
            features = [f.strip() for f in features.split(',') if f.strip()]
    
    # Get additional feature data from the data field
    data = anomaly.get('data', {})
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            data = {}
    
    # Extract feature importance if available
    feature_importance = data.get('feature_importance', {})
    feature_values = data.get('feature_values', {})
    
    if features or feature_importance:
        # Convert to structured format
        feature_data = []
        
        if feature_importance:
            # Use actual feature importance data
            for feature_name, importance in feature_importance.items():
                feature_data.append({
                    "name": feature_name,
                    "importance": importance,
                    "value": feature_values.get(feature_name, 0),
                    "baseline": data.get('feature_baselines', {}).get(feature_name, 0)
                })
        else:
            # Use features list with estimated importance based on anomaly score
            base_score = float(anomaly.get('score', 0.5))
            for i, feature in enumerate(features):
                if isinstance(feature, dict):
                    feature_data.append(feature)
                else:
                    # Estimate importance based on position in list and anomaly score
                    importance = base_score * (1 - i * 0.1) if i < 10 else base_score * 0.1
                    feature_data.append({
                        "name": str(feature),
                        "importance": max(0.1, importance),
                        "value": "Triggered",
                        "baseline": "Normal"
                    })
        
        # Sort by importance
        feature_data.sort(key=lambda x: x.get('importance', 0), reverse=True)
        
        # Create feature importance chart
        if feature_data:
            df = pd.DataFrame(feature_data[:10])  # Top 10 features
            
            fig = px.bar(
                df,
                x='importance',
                y='name',
                orientation='h',
                title='Feature Importance',
                labels={'importance': 'Importance Score', 'name': 'Feature'},
                color='importance',
                color_continuous_scale='RdYlBu_r'
            )
            
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        # Show feature details
        st.markdown("#### 📊 Feature Details")
        
        # Display top features with their values
        for i, feature in enumerate(feature_data[:5]):
            with st.expander(f"{feature['name']} (Importance: {feature.get('importance', 0):.2f})"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Current Value", str(feature.get('value', 'N/A')))
                
                with col2:
                    st.metric("Baseline", str(feature.get('baseline', 'N/A')))
                
                # Show deviation if numeric values
                try:
                    current = float(feature.get('value', 0))
                    baseline = float(feature.get('baseline', 0))
                    deviation = abs(current - baseline)
                    st.metric("Deviation", f"{deviation:.2f}")
                except:
                    pass
    else:
        st.info("No feature data available for this anomaly")

def render_anomaly_timeline(anomaly: Dict[str, Any]):
    """Show timeline of events related to this anomaly using REAL data."""
    
    st.markdown("### 🕐 Anomaly Timeline")
    
    # Get REAL timeline data
    anomaly_time = parse_timestamp(anomaly.get('timestamp'))
    if not anomaly_time:
        anomaly_time = datetime.now()
    
    # Get related activities and messages
    activities = get_agent_activities(anomaly_id=anomaly.get('id'))
    messages = get_agent_messages(anomaly_id=anomaly.get('id'))
    
    # Combine into timeline events
    timeline_events = []
    
    # Add the anomaly detection event
    timeline_events.append({
        "time": anomaly_time,
        "event": f"Anomaly detected (Score: {anomaly.get('score', 0):.3f})",
        "type": "anomaly",
        "source": "Detection System"
    })
    
    # Add activities
    for activity in activities:
        activity_time = parse_timestamp(activity.get('timestamp'))
        if activity_time:
            timeline_events.append({
                "time": activity_time,
                "event": activity.get('description', activity.get('action', 'Activity')),
                "type": "action",
                "source": activity.get('agent_id', activity.get('agent', 'Agent'))
            })
    
    # Add messages
    for message in messages:
        msg_time = parse_timestamp(message.get('timestamp'))
        if msg_time:
            timeline_events.append({
                "time": msg_time,
                "event": message.get('content', message.get('message', 'Message'))[:100] + "...",
                "type": message.get('message_type', 'info'),
                "source": message.get('agent_id', message.get('agent', 'Agent'))
            })
    
    # Sort by time
    timeline_events.sort(key=lambda x: x['time'])
    
    if timeline_events:
        # Create timeline visualization
        fig = go.Figure()
        
        # Add timeline line
        fig.add_trace(go.Scatter(
            x=[event['time'] for event in timeline_events],
            y=[0] * len(timeline_events),
            mode='lines',
            line=dict(color='gray', width=2),
            showlegend=False
        ))
        
        # Add events
        for event in timeline_events:
            color = {
                'normal': 'green',
                'warning': 'orange',
                'anomaly': 'red',
                'alert': 'purple',
                'action': 'blue',
                'info': 'lightblue',
                'error': 'darkred'
            }.get(event['type'], 'gray')
            
            fig.add_trace(go.Scatter(
                x=[event['time']],
                y=[0],
                mode='markers+text',
                marker=dict(size=15, color=color),
                text=[event['event'][:30] + "..."],
                textposition='top center',
                showlegend=False,
                hovertext=f"{event['event']}<br>Source: {event['source']}<br>{event['time'].strftime('%Y-%m-%d %H:%M:%S')}"
            ))
        
        fig.update_layout(
            title='Event Timeline',
            xaxis_title='Time',
            yaxis=dict(showticklabels=False, showgrid=False, range=[-0.5, 0.5]),
            height=300,
            hovermode='closest'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show event details
        st.markdown("#### 📋 Event Details")
        
        # Create a table of events
        event_data = []
        for event in timeline_events[-10:]:  # Last 10 events
            event_data.append({
                "Time": event['time'].strftime('%H:%M:%S'),
                "Source": event['source'],
                "Event": event['event'][:100],
                "Type": event['type']
            })
        
        df_events = pd.DataFrame(event_data)
        st.dataframe(df_events, use_container_width=True, hide_index=True)
    else:
        st.info("No timeline data available")
    
    # Show REAL related anomalies
    st.markdown("#### 🔗 Related Anomalies")
    
    # Query for actual related anomalies
    related = find_real_related_anomalies(anomaly)
    
    if related:
        for rel_anomaly in related[:3]:
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("ID", rel_anomaly['id'])
                
                with col2:
                    st.metric("Score", f"{rel_anomaly['score']:.3f}")
                
                with col3:
                    st.metric("Time Diff", rel_anomaly['time_diff'])
                
                with col4:
                    st.metric("Correlation", f"{rel_anomaly['correlation']:.1%}")
    else:
        st.info("No related anomalies found")

# Helper functions

def create_network_path_diagram(nodes):
    """Create a network path visualization."""
    fig = go.Figure()
    
    # Node positions
    x_positions = list(range(len(nodes)))
    y_position = 0
    
    # Add edges
    for i in range(len(nodes) - 1):
        fig.add_trace(go.Scatter(
            x=[x_positions[i], x_positions[i+1]],
            y=[y_position, y_position],
            mode='lines',
            line=dict(color='gray', width=2),
            showlegend=False
        ))
    
    # Add nodes
    for i, node in enumerate(nodes):
        color = {
            'source': 'lightblue',
            'destination': 'lightgreen',
            'security': 'orange',
            'network': 'lightgray'
        }.get(node['type'], 'lightgray')
        
        fig.add_trace(go.Scatter(
            x=[x_positions[i]],
            y=[y_position],
            mode='markers+text',
            marker=dict(size=50, color=color, line=dict(width=2, color='white')),
            text=[node['name']],
            textposition='top center',
            showlegend=False
        ))
    
    fig.update_layout(
        showlegend=False,
        xaxis=dict(showticklabels=False, showgrid=False),
        yaxis=dict(showticklabels=False, showgrid=False, range=[-1, 1]),
        height=200,
        margin=dict(l=0, r=0, t=0, b=0)
    )
    
    return fig

def extract_real_metrics(data, anomaly):
    """Extract REAL key metrics from anomaly data."""
    metrics = {}
    
    if isinstance(data, dict):
        # Extract numeric values that are likely metrics
        for key, value in data.items():
            if isinstance(value, (int, float)) and key not in ['id', 'timestamp', 'model_id']:
                # Clean up the key name
                clean_key = key.replace('_', ' ').title()
                metrics[clean_key] = value
    
    # Add anomaly score as a metric
    if 'score' in anomaly:
        metrics['Anomaly Score'] = float(anomaly['score'])
    
    # Limit to most relevant metrics (highest values or specific important ones)
    important_keys = ['CPU Usage', 'Memory Usage', 'Network Traffic', 'Response Time', 
                     'Error Rate', 'Bytes Transferred', 'Connection Count', 'Anomaly Score']
    
    # Filter to important metrics or top 6 by value
    filtered_metrics = {}
    
    # First add important metrics if they exist
    for key in important_keys:
        if key in metrics:
            filtered_metrics[key] = metrics[key]
    
    # Then add remaining metrics sorted by value
    remaining = {k: v for k, v in metrics.items() if k not in filtered_metrics}
    for key, value in sorted(remaining.items(), key=lambda x: abs(x[1]), reverse=True):
        if len(filtered_metrics) < 6:
            filtered_metrics[key] = value
    
    return filtered_metrics

def check_if_metric_anomalous(metric, value, anomaly):
    """Check if a specific metric value contributed to the anomaly."""
    # Check if metric is mentioned in features
    features = anomaly.get('features', [])
    if isinstance(features, str):
        features = [features]
    
    metric_lower = metric.lower().replace(' ', '_')
    
    for feature in features:
        if isinstance(feature, str) and metric_lower in feature.lower():
            return True
    
    # Check against thresholds if available
    data = anomaly.get('data', {})
    if isinstance(data, dict):
        thresholds = data.get('thresholds', {})
        if metric_lower in thresholds:
            threshold = thresholds[metric_lower]
            if isinstance(threshold, dict):
                if 'max' in threshold and value > threshold['max']:
                    return True
                if 'min' in threshold and value < threshold['min']:
                    return True
    
    # Check if it's an extreme value
    if isinstance(value, (int, float)):
        if 'CPU' in metric and value > 80:
            return True
        if 'Memory' in metric and value > 85:
            return True
        if 'Error' in metric and value > 5:
            return True
        if 'Response Time' in metric and value > 300:
            return True
    
    return False

def format_metric_value(value):
    """Format metric value for display."""
    if isinstance(value, (int, float)):
        if value >= 1000000:
            return f"{value/1000000:.1f}M"
        elif value >= 1000:
            return f"{value/1000:.1f}K"
        elif isinstance(value, float):
            return f"{value:.2f}"
        else:
            return f"{value:,}"
    return str(value)

def format_timestamp(timestamp):
    """Format timestamp for display."""
    if not timestamp:
        return "Unknown"
    
    if isinstance(timestamp, str):
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return timestamp
    
    if isinstance(timestamp, datetime):
        return timestamp.strftime('%Y-%m-%d %H:%M:%S')
    
    return str(timestamp)

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
            try:
                return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            except:
                return None
    
    return None

def find_real_related_anomalies(anomaly):
    """Find REAL anomalies related to the current one from the database."""
    # Get recent anomalies
    all_anomalies = get_anomalies(limit=100)
    
    if not all_anomalies:
        return []
    
    anomaly_id = anomaly.get('id')
    anomaly_time = parse_timestamp(anomaly.get('timestamp'))
    anomaly_score = float(anomaly.get('score', 0))
    anomaly_src_ip = anomaly.get('src_ip')
    anomaly_location = anomaly.get('location')
    
    related = []
    
    for other in all_anomalies:
        if other.get('id') == anomaly_id:
            continue
        
        # Calculate correlation based on real factors
        correlation = 0
        
        # Same source IP
        if anomaly_src_ip and other.get('src_ip') == anomaly_src_ip:
            correlation += 0.4
        
        # Same location
        if anomaly_location and other.get('location') == anomaly_location:
            correlation += 0.2
        
        # Similar score
        other_score = float(other.get('score', 0))
        score_diff = abs(anomaly_score - other_score)
        if score_diff < 0.1:
            correlation += 0.3
        elif score_diff < 0.2:
            correlation += 0.2
        
        # Time proximity
        other_time = parse_timestamp(other.get('timestamp'))
        if anomaly_time and other_time:
            time_diff = abs((anomaly_time - other_time).total_seconds())
            
            if time_diff < 300:  # Within 5 minutes
                correlation += 0.4
                time_str = f"{int(time_diff/60)} min"
            elif time_diff < 3600:  # Within 1 hour
                correlation += 0.2
                time_str = f"{int(time_diff/60)} min"
            elif time_diff < 86400:  # Within 1 day
                correlation += 0.1
                time_str = f"{int(time_diff/3600)} hours"
            else:
                continue  # Skip if too far apart
        else:
            time_str = "Unknown"
        
        if correlation > 0.3:  # Only include if correlation is significant
            related.append({
                'id': other['id'],
                'score': other_score,
                'time_diff': time_str,
                'correlation': correlation
            })
    
    # Sort by correlation
    return sorted(related, key=lambda x: x['correlation'], reverse=True)

# Integration function for the anomalies page
def add_origin_details_to_anomaly_page(anomaly):
    """Add this to the anomaly details view in anomalies.py"""
    with st.expander("🔎 Origin & Context Details", expanded=True):
        render_anomaly_origin_details(anomaly)