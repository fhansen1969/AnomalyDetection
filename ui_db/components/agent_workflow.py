"""
Agent workflow visualization components for the Anomaly Detection Dashboard.
Provides functions for visualizing agent activities and workflows.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
from datetime import datetime, timedelta
import numpy as np
import random
import json

from services.data_service import get_agent_activities
from utils.ui_components import loading_animation, status_badge

def display_agent_workflow(anomaly_id=None):
    """
    Display a graph visualization of agent workflow for an anomaly investigation.
    
    Args:
        anomaly_id (str, optional): ID of the anomaly to visualize. Defaults to None.
        
    Returns:
        plotly.graph_objects.Figure: The workflow graph figure
    """
    # Load agent activities data
    activities = get_agent_activities(anomaly_id)
    
    # Create a directed graph
    G = nx.DiGraph()
    
    # Color map for different activity types
    color_map = {
        "analysis": "#4361ee",
        "investigation": "#3a0ca3",
        "correlation": "#4cc9f0",
        "remediation": "#f72585",
        "notification": "#7209b7"
    }
    
    # Default color for unknown types
    default_color = "#888888"
    
    # Process activities and add to graph
    nodes = []
    edges = []
    
    # Keep track of last agent action for each agent
    last_action = {}
    
    for activity in activities:
        # Extract node data
        agent_id = activity.get("agent_id", activity.get("agent", "unknown"))
        action = activity.get("activity_type", activity.get("action", "unknown"))
        activity_id = f"{agent_id}_{action}_{activity.get('id', random.randint(1000, 9999))}"
        timestamp = activity.get("timestamp", datetime.now().isoformat())
        description = activity.get("description", "Activity")
        status = activity.get("status", "completed")
        
        # Determine color based on activity type
        color = color_map.get(action.lower(), default_color)
        
        # Add node
        nodes.append({
            "id": activity_id,
            "label": action.capitalize(),
            "title": description,
            "color": color,
            "agent": agent_id,
            "timestamp": timestamp,
            "status": status
        })
        
        # Add edge if there was a previous action by this agent
        if agent_id in last_action:
            edges.append({
                "from": last_action[agent_id],
                "to": activity_id,
                "arrows": "to"
            })
        
        # Update last action for this agent
        last_action[agent_id] = activity_id
        
        # Add edges between related activities based on details
        details = activity.get("details", {})
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except:
                details = {}
                
        related_activities = details.get("related_activities", [])
        for related in related_activities:
            edges.append({
                "from": related,
                "to": activity_id,
                "arrows": "to",
                "dashes": True
            })
    
    # Create a dataframe for nodes
    nodes_df = pd.DataFrame(nodes)
    edges_df = pd.DataFrame(edges)
    
    # If no activities, create a simple demo graph
    if len(nodes) == 0:
        # Create demo data
        nodes_df, edges_df = create_demo_workflow_data()
    
    # Create positions for nodes using a layout algorithm
    if len(nodes_df) > 0:
        # Convert to NetworkX graph
        G = nx.DiGraph()
        
        # Add nodes
        for _, node in nodes_df.iterrows():
            G.add_node(node["id"], **node.to_dict())
        
        # Add edges
        for _, edge in edges_df.iterrows():
            G.add_edge(edge["from"], edge["to"])
        
        # Apply layout
        pos = nx.spring_layout(G)
        
        # Update node positions
        for node_id, coords in pos.items():
            mask = nodes_df["id"] == node_id
            nodes_df.loc[mask, "x"] = coords[0]
            nodes_df.loc[mask, "y"] = coords[1]
    
    # Create figure
    fig = go.Figure()
    
    # Add edges first (so they're under the nodes)
    for _, edge in edges_df.iterrows():
        # Find the node coordinates
        from_node = nodes_df[nodes_df["id"] == edge["from"]]
        to_node = nodes_df[nodes_df["id"] == edge["to"]]
        
        if len(from_node) > 0 and len(to_node) > 0:
            x0, y0 = from_node.iloc[0]["x"], from_node.iloc[0]["y"]
            x1, y1 = to_node.iloc[0]["x"], to_node.iloc[0]["y"]
            
            # Add edge
            fig.add_trace(
                go.Scatter(
                    x=[x0, x1],
                    y=[y0, y1],
                    mode="lines",
                    line=dict(width=1, color="#888888", dash="solid" if not edge.get("dashes") else "dash"),
                    hoverinfo="none"
                )
            )
            
            # Add arrow in the middle of the edge
            dx, dy = x1 - x0, y1 - y0
            mid_x, mid_y = x0 + dx * 0.55, y0 + dy * 0.55
            angle = np.arctan2(dy, dx)
            
            # Arrow head coordinates
            arrow_size = 0.02
            arrow_x0 = mid_x - arrow_size * np.cos(angle - np.pi/6)
            arrow_y0 = mid_y - arrow_size * np.sin(angle - np.pi/6)
            arrow_x1 = mid_x
            arrow_y1 = mid_y
            arrow_x2 = mid_x - arrow_size * np.cos(angle + np.pi/6)
            arrow_y2 = mid_y - arrow_size * np.sin(angle + np.pi/6)
            
            # Add arrow
            fig.add_trace(
                go.Scatter(
                    x=[arrow_x0, arrow_x1, arrow_x2],
                    y=[arrow_y0, arrow_y1, arrow_y2],
                    mode="lines",
                    line=dict(width=1, color="#888888"),
                    fill="toself",
                    hoverinfo="none"
                )
            )
    
    # Add nodes
    for _, node in nodes_df.iterrows():
        fig.add_trace(
            go.Scatter(
                x=[node["x"]],
                y=[node["y"]],
                mode="markers+text",
                marker=dict(
                    size=30,
                    color=node["color"],
                    line=dict(width=2, color="white")
                ),
                text=node["label"],
                textposition="middle center",
                textfont=dict(color="white", size=10),
                name=node["label"],
                hovertext=f"<b>{node['label']}</b><br>{node['title']}<br>Agent: {node['agent']}<br>Status: {node['status']}",
                hoverinfo="text"
            )
        )
    
    # Update layout
    fig.update_layout(
        title="Agent Workflow Graph",
        showlegend=False,
        hovermode="closest",
        margin=dict(l=20, r=20, t=60, b=20),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=600
    )
    
    return fig

def display_agent_activity_timeline():
    """
    Display a timeline of agent activities.
    
    Returns:
        plotly.graph_objects.Figure: The timeline figure
    """
    # Show loading animation
    loading = loading_animation("Loading agent activity data...")
    
    # Load agent activities data
    activities = get_agent_activities()
    
    # Hide loading animation
    loading.empty()
    
    # Create a DataFrame
    data = []
    for activity in activities:
        # Extract data
        agent_id = activity.get("agent_id", activity.get("agent", "unknown"))
        action = activity.get("activity_type", activity.get("action", "unknown"))
        timestamp = activity.get("timestamp", datetime.now().isoformat())
        description = activity.get("description", "Activity")
        status = activity.get("status", "completed")
        anomaly_id = activity.get("anomaly_id", "")
        
        # Try to parse timestamp
        try:
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except:
            timestamp = datetime.now() - timedelta(hours=random.randint(1, 24))
            
        # Add to data
        data.append({
            "agent": agent_id,
            "action": action,
            "timestamp": timestamp,
            "description": description,
            "status": status,
            "anomaly_id": anomaly_id
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # If no data, create demo data
    if len(df) == 0:
        df = create_demo_timeline_data()
    
    # Ensure the timestamp column exists and is correctly named
    if 'timestamp' in df.columns:
        # Convert to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    elif 'time' in df.columns:
        # If the column is named 'time' instead of 'timestamp'
        df['timestamp'] = pd.to_datetime(df['time'])
    else:
        # Create a timestamp column if neither exists
        df['timestamp'] = pd.to_datetime(datetime.now() - timedelta(days=1))
    
    # Sort by timestamp
    df = df.sort_values("timestamp")
    
    # Create color map
    color_map = {
        "analysis": "#4361ee",
        "pattern_detection": "#3a0ca3",
        "investigation": "#7209b7",
        "correlation_analysis": "#4cc9f0",
        "threat_intelligence_lookup": "#f72585",
        "remediation_action": "#06d6a0",
        "notification_sent": "#ff9e00",
        "analysis_completed": "#4CAF50"
    }
    
    # Create a figure
    fig = go.Figure()
    
    # Get unique agents
    agents = df["agent"].unique()
    
    # Add a trace for each agent
    for i, agent in enumerate(agents):
        agent_df = df[df["agent"] == agent]
        
        # Add a horizontal line for the agent
        fig.add_trace(
            go.Scatter(
                x=[agent_df["timestamp"].min(), agent_df["timestamp"].max()],
                y=[i, i],
                mode="lines",
                line=dict(color="#dddddd", width=2),
                hoverinfo="none",
                name=agent
            )
        )
        
        # Add points for each activity
        for _, row in agent_df.iterrows():
            # Get color
            color = color_map.get(row["action"].lower(), "#888888")
            
            # Add point
            fig.add_trace(
                go.Scatter(
                    x=[row["timestamp"]],
                    y=[i],
                    mode="markers",
                    marker=dict(
                        size=15,
                        color=color,
                        line=dict(width=2, color="white")
                    ),
                    name=row["action"],
                    hovertext=f"<b>{row['action']}</b><br>{row['description']}<br>Status: {row['status']}<br>Time: {row['timestamp']}",
                    hoverinfo="text"
                )
            )
    
    # Update layout
    fig.update_layout(
        title="Agent Activity Timeline",
        xaxis=dict(title="Time", gridcolor="#eeeeee"),
        yaxis=dict(
            title="Agent",
            tickvals=list(range(len(agents))),
            ticktext=agents,
            gridcolor="#eeeeee"
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hovermode="closest",
        height=400,
        margin=dict(l=20, r=20, t=60, b=20)
    )
    
    return fig

def create_demo_workflow_data():
    """
    Create demo data for agent workflow visualization.
    
    Returns:
        tuple: (nodes_df, edges_df) - DataFrames for nodes and edges
    """
    # Create nodes
    nodes = [
        {
            "id": "analyst_1_analysis",
            "label": "Analysis",
            "title": "Initial analysis of anomaly",
            "color": "#4361ee",
            "agent": "analyst_1",
            "timestamp": (datetime.now() - timedelta(hours=3)).isoformat(),
            "status": "completed",
            "x": 0,
            "y": 0
        },
        {
            "id": "investigator_1_investigation",
            "label": "Investigation",
            "title": "Detailed investigation of anomaly",
            "color": "#3a0ca3",
            "agent": "investigator_1",
            "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
            "status": "completed",
            "x": 1,
            "y": 0
        },
        {
            "id": "investigator_1_correlation",
            "label": "Correlation",
            "title": "Correlation with other events",
            "color": "#4cc9f0",
            "agent": "investigator_1",
            "timestamp": (datetime.now() - timedelta(hours=1, minutes=30)).isoformat(),
            "status": "completed",
            "x": 2,
            "y": 0
        },
        {
            "id": "responder_1_remediation",
            "label": "Remediation",
            "title": "Implementing remediation actions",
            "color": "#f72585",
            "agent": "responder_1",
            "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
            "status": "in_progress",
            "x": 3,
            "y": 0
        },
        {
            "id": "responder_1_notification",
            "label": "Notification",
            "title": "Sending notifications to stakeholders",
            "color": "#7209b7",
            "agent": "responder_1",
            "timestamp": (datetime.now() - timedelta(minutes=30)).isoformat(),
            "status": "completed",
            "x": 4,
            "y": 0
        }
    ]
    
    # Create edges
    edges = [
        {
            "from": "analyst_1_analysis",
            "to": "investigator_1_investigation",
            "arrows": "to"
        },
        {
            "from": "investigator_1_investigation",
            "to": "investigator_1_correlation",
            "arrows": "to"
        },
        {
            "from": "investigator_1_correlation",
            "to": "responder_1_remediation",
            "arrows": "to"
        },
        {
            "from": "responder_1_remediation",
            "to": "responder_1_notification",
            "arrows": "to"
        }
    ]
    
    # Apply spring layout to position nodes
    G = nx.DiGraph()
    for node in nodes:
        G.add_node(node["id"], **{k: v for k, v in node.items() if k != "id"})
        
    for edge in edges:
        G.add_edge(edge["from"], edge["to"])
    
    pos = nx.spring_layout(G)
    
    # Update node positions
    for i, node in enumerate(nodes):
        coords = pos[node["id"]]
        nodes[i]["x"] = float(coords[0])
        nodes[i]["y"] = float(coords[1])
    
    # Create DataFrames
    nodes_df = pd.DataFrame(nodes)
    edges_df = pd.DataFrame(edges)
    
    return nodes_df, edges_df

def create_agent_workflow_graph(anomaly_id=None, height=600, width=None):
    """
    Create an interactive graph visualization of agent workflow for an anomaly.
    
    Args:
        anomaly_id (str, optional): ID of the anomaly to visualize. Defaults to None.
        height (int, optional): Height of the graph in pixels. Defaults to 600.
        width (int, optional): Width of the graph in pixels. Defaults to None.
        
    Returns:
        plotly.graph_objects.Figure: The workflow graph figure
    """
    # Use the existing display_agent_workflow function with parameters
    fig = display_agent_workflow(anomaly_id)
    
    # Update height and width if specified
    if height:
        fig.update_layout(height=height)
    
    if width:
        fig.update_layout(width=width)
    
    # Add additional interactive features
    fig.update_layout(
        dragmode="pan",
        clickmode="event+select",
        hovermode="closest",
        modebar=dict(
            orientation="v",
            bgcolor="rgba(255,255,255,0.7)",
            color="#333333"
        )
    )
    
    # Add legend for activity types
    activity_types = {
        "Analysis": "#4361ee",
        "Investigation": "#3a0ca3",
        "Correlation": "#4cc9f0",
        "Remediation": "#f72585",
        "Notification": "#7209b7"
    }
    
    # Add invisible traces just for the legend
    for activity, color in activity_types.items():
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=10, color=color),
                name=activity,
                showlegend=True
            )
        )
    
    # Update legend position
    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    return fig

def display_agent_messages(anomaly_id=None, max_messages=20):
    """
    Display agent messages in a chat-like interface.
    
    Args:
        anomaly_id (str, optional): ID of the anomaly to show messages for. Defaults to None.
        max_messages (int, optional): Maximum number of messages to display. Defaults to 20.
    """
    # Show loading animation
    loading = loading_animation("Loading agent messages...")
    
    # Load agent messages data
    from services.data_service import get_agent_messages
    messages = get_agent_messages(anomaly_id)
    
    # Hide loading animation
    loading.empty()
    
    # Check if we have messages
    if not messages:
        st.info("No agent messages available for this anomaly.")
        return
    
    # Get current theme for styling
    try:
        from config.theme import get_current_theme
        theme = get_current_theme()
    except:
        theme = {
            "primary_color": "#4361ee",
            "secondary_color": "#3a0ca3",
            "error_color": "#f44336",
            "warning_color": "#ff9100",
            "success_color": "#4CAF50"
        }
    
    # Sort messages by timestamp
    messages = sorted(messages, key=lambda x: x.get('timestamp', ''))
    
    # Display messages
    st.markdown("### Agent Conversation")
    
    # Custom CSS for message styling
    st.markdown("""
    <style>
    .agent-message {
        padding: 10px 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        max-width: 80%;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        animation: fadeIn 0.3s ease-out;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .agent-message-left {
        background-color: rgba(67, 97, 238, 0.1);
        border-left: 3px solid #4361ee;
        float: left;
        clear: both;
        position: relative;
    }
    
    .agent-message-right {
        background-color: rgba(58, 12, 163, 0.1);
        border-left: 3px solid #3a0ca3;
        float: right;
        clear: both;
        position: relative;
    }
    
    .agent-name {
        font-weight: bold;
        margin-bottom: 5px;
        font-size: 0.9rem;
    }
    
    .message-time {
        font-size: 0.7rem;
        opacity: 0.7;
        margin-top: 5px;
        text-align: right;
    }
    
    .message-type {
        display: inline-block;
        padding: 2px 5px;
        border-radius: 3px;
        font-size: 0.7rem;
        margin-left: 5px;
        color: white;
    }
    
    .message-type-info {
        background-color: #4361ee;
    }
    
    .message-type-warning {
        background-color: #ff9100;
    }
    
    .message-type-error {
        background-color: #f44336;
    }
    
    .message-type-success {
        background-color: #4CAF50;
    }
    
    .message-type-question {
        background-color: #9c27b0;
    }
    
    .message-type-answer {
        background-color: #00bcd4;
    }
    
    .message-type-analysis {
        background-color: #4361ee;
    }
    
    .message-type-investigation {
        background-color: #ff9100;
    }
    
    .message-type-assessment {
        background-color: #4CAF50;
    }
    
    .agent-messages-container {
        overflow-y: auto;
        max-height: 500px;
        padding: 10px;
        background-color: rgba(0,0,0,0.02);
        border-radius: 10px;
    }
    
    .message-content {
        word-wrap: break-word;
    }
    
    /* Clearfix for float behavior */
    .clearfix::after {
        content: "";
        clear: both;
        display: table;
    }
    
    /* Agent-specific colors */
    .agent-security-analyst {
        border-left-color: #4361ee;
        background-color: rgba(67, 97, 238, 0.1);
    }
    
    .agent-pattern-detector {
        border-left-color: #ff9100;
        background-color: rgba(255, 145, 0, 0.1);
    }
    
    .agent-threat-investigator {
        border-left-color: #f44336;
        background-color: rgba(244, 67, 54, 0.1);
    }
    
    .agent-risk-assessor {
        border-left-color: #4CAF50;
        background-color: rgba(76, 175, 80, 0.1);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Create container for messages
    st.markdown('<div class="agent-messages-container">', unsafe_allow_html=True)
    
    # Keep track of agents seen so far
    seen_agents = set()
    agent_positions = {}
    
    # Map agent IDs to display names
    agent_display_names = {
        "security_analyst": "Security Analyst",
        "pattern_detector": "Pattern Detector",
        "threat_investigator": "Threat Investigator",
        "risk_assessor": "Risk Assessor",
        "coordinator_agent": "Coordinator",
        "analyzer_agent": "Analyzer",
        "investigator_agent": "Investigator",
        "responder_agent": "Responder"
    }
    
    # Display up to max_messages
    for i, message in enumerate(messages[-max_messages:]):
        # Extract message data
        agent_id = message.get('agent_id', message.get('agent', 'unknown'))
        content = message.get('message', message.get('content', 'No message content'))
        message_type = message.get('message_type', 'info')
        timestamp = message.get('timestamp', '')
        
        # Format timestamp
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                formatted_time = timestamp.strftime('%H:%M:%S')
            except:
                formatted_time = timestamp
        else:
            formatted_time = str(timestamp)
        
        # Get display name for agent
        display_name = agent_display_names.get(agent_id, agent_id.replace('_', ' ').title())
        
        # Determine message position
        if agent_id not in agent_positions:
            agent_positions[agent_id] = len(agent_positions) % 2
        
        position = "left" if agent_positions[agent_id] == 0 else "right"
        
        # Get agent-specific class
        agent_class = f"agent-{agent_id.replace('_', '-')}"
        
        # Create HTML for message
        message_html = f"""
        <div class="agent-message agent-message-{position} {agent_class}">
            <div class="agent-name">
                {display_name}
                <span class="message-type message-type-{message_type}">{message_type}</span>
            </div>
            <div class="message-content">
                {content}
            </div>
            <div class="message-time">
                {formatted_time}
            </div>
        </div>
        <div class="clearfix"></div>
        """
        
        # Display message
        st.markdown(message_html, unsafe_allow_html=True)
    
    # Close container
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Show message statistics
    if messages:
        st.markdown("### 📊 Communication Statistics")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Messages", len(messages))
        
        with col2:
            unique_agents = len(set(m.get('agent_id', 'unknown') for m in messages))
            st.metric("Active Agents", unique_agents)
        
        with col3:
            # Calculate average response time
            if len(messages) > 1:
                times = []
                for i in range(1, len(messages)):
                    try:
                        t1 = datetime.fromisoformat(messages[i-1].get('timestamp', '').replace('Z', '+00:00'))
                        t2 = datetime.fromisoformat(messages[i].get('timestamp', '').replace('Z', '+00:00'))
                        times.append((t2 - t1).total_seconds())
                    except:
                        pass
                
                if times:
                    avg_time = sum(times) / len(times)
                    st.metric("Avg Response Time", f"{avg_time:.1f}s")
                else:
                    st.metric("Avg Response Time", "N/A")
            else:
                st.metric("Avg Response Time", "N/A")
    
    # Show export option if messages exist
    if messages:
        if st.button("📥 Export Conversation", key="export_conversation"):
            # Convert messages to markdown
            markdown_content = f"# Agent Conversation Log\n\n"
            markdown_content += f"**Anomaly ID:** {anomaly_id}\n"
            markdown_content += f"**Total Messages:** {len(messages)}\n"
            markdown_content += f"**Export Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            markdown_content += "---\n\n"
            
            for message in messages:
                agent_id = message.get('agent_id', message.get('agent', 'unknown'))
                content = message.get('message', message.get('content', 'No message content'))
                message_type = message.get('message_type', 'info')
                timestamp = message.get('timestamp', '')
                
                # Format timestamp
                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        formatted_time = timestamp
                else:
                    formatted_time = str(timestamp)
                
                # Get display name
                display_name = agent_display_names.get(agent_id, agent_id.replace('_', ' ').title())
                
                # Add to markdown
                markdown_content += f"## {display_name} ({message_type})\n"
                markdown_content += f"**Time:** {formatted_time}\n\n"
                markdown_content += f"{content}\n\n"
                markdown_content += "---\n\n"
            
            # Create download button
            st.download_button(
                label="Download Conversation Log",
                data=markdown_content,
                file_name=f"agent_conversation_{anomaly_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown"
            )

def display_demo_agent_messages():
    """Display demo agent messages for development and testing."""
    # Get current theme for styling
    try:
        from config.theme import get_current_theme
        theme = get_current_theme()
    except:
        theme = {
            "primary_color": "#4361ee",
            "secondary_color": "#3a0ca3",
            "error_color": "#f44336",
            "warning_color": "#ff9100",
            "success_color": "#4CAF50"
        }
    
    # Custom CSS for message styling (same as in display_agent_messages)
    st.markdown("""
    <style>
    .agent-message {
        padding: 10px 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        max-width: 80%;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        animation: fadeIn 0.3s ease-out;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .agent-message-left {
        background-color: rgba(67, 97, 238, 0.1);
        border-left: 3px solid #4361ee;
        float: left;
        clear: both;
        position: relative;
    }
    
    .agent-message-right {
        background-color: rgba(58, 12, 163, 0.1);
        border-left: 3px solid #3a0ca3;
        float: right;
        clear: both;
        position: relative;
    }
    
    .agent-name {
        font-weight: bold;
        margin-bottom: 5px;
        font-size: 0.9rem;
    }
    
    .message-time {
        font-size: 0.7rem;
        opacity: 0.7;
        margin-top: 5px;
        text-align: right;
    }
    
    .message-type {
        display: inline-block;
        padding: 2px 5px;
        border-radius: 3px;
        font-size: 0.7rem;
        margin-left: 5px;
        color: white;
    }
    
    .message-type-info {
        background-color: #4361ee;
    }
    
    .message-type-warning {
        background-color: #ff9100;
    }
    
    .message-type-error {
        background-color: #f44336;
    }
    
    .message-type-success {
        background-color: #4CAF50;
    }
    
    .message-type-question {
        background-color: #9c27b0;
    }
    
    .message-type-answer {
        background-color: #00bcd4;
    }
    
    .agent-messages-container {
        overflow-y: auto;
        max-height: 500px;
        padding: 10px;
    }
    
    .message-content {
        word-wrap: break-word;
    }
    
    /* Clearfix for float behavior */
    .clearfix::after {
        content: "";
        clear: both;
        display: table;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Create demo messages
    demo_messages = [
        {
            "agent_id": "analyzer_agent",
            "message": "Starting analysis of suspicious login activity from IP 192.168.1.105",
            "message_type": "info",
            "timestamp": (datetime.now() - timedelta(hours=2, minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "agent_id": "analyzer_agent",
            "message": "Detected unusual login time outside normal working hours",
            "message_type": "warning",
            "timestamp": (datetime.now() - timedelta(hours=2, minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "agent_id": "investigator_agent",
            "message": "Initiating investigation of suspicious login",
            "message_type": "info",
            "timestamp": (datetime.now() - timedelta(hours=2, minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "agent_id": "investigator_agent",
            "message": "Correlating with recent login attempts from same IP",
            "message_type": "info",
            "timestamp": (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "agent_id": "investigator_agent",
            "message": "Found 3 failed login attempts before successful login",
            "message_type": "warning",
            "timestamp": (datetime.now() - timedelta(hours=1, minutes=55)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "agent_id": "coordinator_agent",
            "message": "Is this part of a brute force attack?",
            "message_type": "question",
            "timestamp": (datetime.now() - timedelta(hours=1, minutes=50)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "agent_id": "investigator_agent",
            "message": "Analysis indicates 87% probability of brute force attack",
            "message_type": "answer",
            "timestamp": (datetime.now() - timedelta(hours=1, minutes=45)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "agent_id": "responder_agent",
            "message": "Implementing temporary lockout for affected account",
            "message_type": "info",
            "timestamp": (datetime.now() - timedelta(hours=1, minutes=40)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "agent_id": "responder_agent",
            "message": "Account locked successfully. IP 192.168.1.105 added to watchlist.",
            "message_type": "success",
            "timestamp": (datetime.now() - timedelta(hours=1, minutes=35)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "agent_id": "coordinator_agent",
            "message": "Notifying security team about potential breach attempt",
            "message_type": "info",
            "timestamp": (datetime.now() - timedelta(hours=1, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "agent_id": "analyzer_agent",
            "message": "Additional analysis shows this IP has accessed 3 different user accounts in the past 24 hours",
            "message_type": "error",
            "timestamp": (datetime.now() - timedelta(hours=1, minutes=25)).strftime("%Y-%m-%d %H:%M:%S")
        },
        {
            "agent_id": "responder_agent",
            "message": "Escalating incident to high severity. Blocking IP across all systems.",
            "message_type": "warning",
            "timestamp": (datetime.now() - timedelta(hours=1, minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
        }
    ]
    
    # Create container for messages
    st.markdown('<div class="agent-messages-container">', unsafe_allow_html=True)
    
    # Keep track of agents seen so far
    seen_agents = set()
    
    # Display demo messages
    for message in demo_messages:
        # Extract message data
        agent_id = message.get('agent_id', 'unknown')
        content = message.get('message', 'No message content')
        message_type = message.get('message_type', 'info')
        formatted_time = message.get('timestamp', '')
        
        # Determine message class based on agent (alternate sides)
        if agent_id in seen_agents:
            # Even indices get left-aligned, odd get right-aligned
            seen_agent_list = list(seen_agents)
            agent_index = seen_agent_list.index(agent_id)
            message_class = "agent-message-left" if agent_index % 2 == 0 else "agent-message-right"
        else:
            # First time seeing this agent
            message_class = "agent-message-left" if len(seen_agents) % 2 == 0 else "agent-message-right"
            seen_agents.add(agent_id)
        
        # Create HTML for message
        message_html = f"""
        <div class="agent-message {message_class}">
            <div class="agent-name">
                {agent_id}
                <span class="message-type message-type-{message_type}">{message_type}</span>
            </div>
            <div class="message-content">
                {content}
            </div>
            <div class="message-time">
                {formatted_time}
            </div>
        </div>
        <div class="clearfix"></div>
        """
        
        # Display message
        st.markdown(message_html, unsafe_allow_html=True)
    
    # Close container
    st.markdown('</div>', unsafe_allow_html=True)
    
def create_demo_timeline_data():
    """
    Create demo data for agent activity timeline.
    
    Returns:
        pd.DataFrame: DataFrame with demo timeline data
    """
    # Generate timestamps
    now = datetime.now()
    timestamps = [
        now - timedelta(hours=24),
        now - timedelta(hours=22),
        now - timedelta(hours=21),
        now - timedelta(hours=20),
        now - timedelta(hours=18),
        now - timedelta(hours=16),
        now - timedelta(hours=14),
        now - timedelta(hours=12),
        now - timedelta(hours=10),
        now - timedelta(hours=8),
        now - timedelta(hours=6),
        now - timedelta(hours=4),
        now - timedelta(hours=2),
        now - timedelta(hours=1),
        now - timedelta(minutes=30)
    ]
    
    # Generate data
    data = []
    
    # Agent activities
    activities = [
        ("analyzer_agent", "analysis_started", "Started anomaly analysis", "completed"),
        ("analyzer_agent", "pattern_detection", "Detected unusual login pattern", "completed"),
        ("analyzer_agent", "analysis_completed", "Completed initial analysis", "completed"),
        ("investigator_agent", "investigation", "Started detailed investigation", "completed"),
        ("investigator_agent", "correlation_analysis", "Analyzed related events", "completed"),
        ("investigator_agent", "threat_intelligence_lookup", "Checked threat intelligence", "completed"),
        ("responder_agent", "remediation_action", "Implemented account lockout", "completed"),
        ("responder_agent", "notification_sent", "Notified security team", "completed"),
        ("analyzer_agent", "analysis_started", "Started second analysis", "completed"),
        ("analyzer_agent", "pattern_detection", "Detected data exfiltration attempt", "completed"),
        ("analyzer_agent", "analysis_completed", "Completed second analysis", "completed"),
        ("investigator_agent", "investigation", "Investigated data movement", "completed"),
        ("responder_agent", "remediation_action", "Blocked suspicious IP", "in_progress"),
        ("responder_agent", "notification_sent", "Escalated to incident response", "completed"),
        ("coordinator_agent", "analysis_completed", "Generated incident report", "completed")
    ]
    
    # Create data
    for i, (agent, action, description, status) in enumerate(activities):
        data.append({
            "agent": agent,
            "action": action,
            "timestamp": timestamps[i],
            "description": description,
            "status": status,
            "anomaly_id": f"anomaly_{i % 3 + 1}"
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    return df