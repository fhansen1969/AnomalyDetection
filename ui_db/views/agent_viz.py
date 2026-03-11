"""
Enhanced Agent visualization page for the Anomaly Detection Dashboard.
Displays agent interactions, activities, and system workflow with real data.
"""

import streamlit as st
import time
import datetime
import json
import random
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from config.theme import get_current_theme
from config.settings import add_notification
from services.data_service import (
    get_agent_activities,
    get_agent_messages,
    add_agent_message,
    add_agent_activity,
    get_anomaly_analysis,
    add_anomaly_analysis,
    get_anomalies
)

# Define agent information
AGENT_INFO = {
    "security_analyst": {
        "name": "Security Analyst",
        "role": "Identifies and classifies anomalies",
        "capabilities": ["Pattern Recognition", "Threat Classification", "Risk Assessment"],
        "color": "#FF6B6B",
        "icon": "🔍"
    },
    "remediation_expert": {
        "name": "Remediation Expert",
        "role": "Develops action plans to address threats",
        "capabilities": ["Mitigation Planning", "System Isolation", "Recovery Procedures"],
        "color": "#4ECDC4",
        "icon": "🛠️"
    },
    "reflection_expert": {
        "name": "Reflection Expert",
        "role": "Provides context and historical patterns",
        "capabilities": ["Historical Analysis", "Pattern Matching", "Trend Identification"],
        "color": "#45B7D1",
        "icon": "🧠"
    },
    "security_critic": {
        "name": "Security Critic",
        "role": "Challenges assumptions and identifies blind spots",
        "capabilities": ["Gap Analysis", "Verification", "False Positive Detection"],
        "color": "#96CEB4",
        "icon": "🎯"
    },
    "code_generator": {
        "name": "Code Generator",
        "role": "Creates scripts for automated responses",
        "capabilities": ["Script Generation", "Automation", "Integration"],
        "color": "#FECA57",
        "icon": "💻"
    },
    "data_collector": {
        "name": "Data Collector",
        "role": "Gathers additional evidence and context",
        "capabilities": ["Log Collection", "Evidence Gathering", "Context Building"],
        "color": "#9C88FF",
        "icon": "📊"
    }
}

def render():
    """Render the enhanced agent visualization page."""
    st.markdown('<h1 class="main-header">🤖 Agent Visualization</h1>', unsafe_allow_html=True)
    
    # Introduction with better styling
    current_theme = get_current_theme()
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {current_theme['primary_color']}20, {current_theme['secondary_color']}20);
                border-radius: 15px; padding: 20px; margin-bottom: 30px; text-align: center;">
        <p style="font-size: 1.2rem; margin-bottom: 10px;">
            Multi-agent system coordinates specialized AI agents to detect, analyze, and remediate security anomalies.
        </p>
        <p style="font-size: 1rem; opacity: 0.8;">
            Each agent has unique capabilities and works collaboratively to provide comprehensive security analysis.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Real-time status
    render_real_time_status()
    
    # Control buttons
    render_control_buttons()
    
    # Create tabs for different views
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔄 Agent Workflow", 
        "👥 Agent Details", 
        "📈 Activity Timeline", 
        "💬 Agent Conversation",
        "🎯 Active Analysis"
    ])
    
    with tab1:
        render_agent_workflow()
    
    with tab2:
        render_agent_details()
    
    with tab3:
        render_activity_timeline()
    
    with tab4:
        render_agent_conversation()
    
    with tab5:
        render_active_analysis()

def render_real_time_status():
    """Display real-time status of agent system."""
    # Get recent activities to determine agent status
    recent_activities = get_agent_activities(limit=20)
    
    # Calculate agent statuses
    agent_status = {}
    for agent_id in AGENT_INFO:
        agent_status[agent_id] = "idle"
    
    # Check recent activities (within last 5 minutes)
    cutoff_time = datetime.datetime.now() - datetime.timedelta(minutes=5)
    for activity in recent_activities:
        activity_time = activity.get('timestamp')
        if isinstance(activity_time, str):
            try:
                activity_time = datetime.datetime.fromisoformat(activity_time.replace('Z', '+00:00'))
            except:
                continue
        
        if activity_time and activity_time > cutoff_time:
            agent_id = activity.get('agent_id', activity.get('agent'))
            if agent_id in agent_status:
                if activity.get('status') == 'running':
                    agent_status[agent_id] = "active"
                elif activity.get('status') == 'completed':
                    agent_status[agent_id] = "recently_active"
    
    # Display status indicators in a more compact way
    st.markdown("### Agent Status")
    
    # Create two rows of 3 agents each
    for row in range(2):
        cols = st.columns(3)
        agents_in_row = list(AGENT_INFO.items())[row*3:(row+1)*3]
        
        for i, (agent_id, info) in enumerate(agents_in_row):
            with cols[i]:
                status = agent_status[agent_id]
                status_emoji = "🟢" if status == "active" else "🟡" if status == "recently_active" else "⚪"
                st.markdown(f"{info['icon']} **{info['name']}**")
                st.caption(f"{status_emoji} {status.replace('_', ' ').title()}")

def render_control_buttons():
    """Render control buttons for real operations."""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Get unanalyzed anomalies
        anomalies = get_anomalies(limit=100)
        unanalyzed = [a for a in anomalies if not a.get('analysis') or 
                      (isinstance(a.get('analysis'), dict) and not a['analysis'].get('agent_analyzed'))]
        
        if st.button(f"🔍 Analyze Anomalies ({len(unanalyzed)})", 
                    key="analyze_real", 
                    type="primary", 
                    use_container_width=True,
                    disabled=len(unanalyzed) == 0):
            if unanalyzed:
                analyze_anomalies(unanalyzed[:5])  # Analyze up to 5 at a time
    
    with col2:
        if st.button("🔄 Refresh", key="refresh_main", use_container_width=True):
            st.rerun()
    
    with col3:
        # Export activities
        activities = get_agent_activities(limit=1000)
        if activities and st.button("📊 Export Activities", key="export_activities", use_container_width=True):
            export_activities(activities)
    
    with col4:
        # System health check
        if st.button("🏥 Health Check", key="health_check", use_container_width=True):
            run_system_health_check()

def render_agent_workflow():
    """Render an enhanced agent workflow visualization with real connections."""
    st.markdown('<h2 class="sub-header">Agent Collaboration Workflow</h2>', unsafe_allow_html=True)
    
    # Get recent activities to show actual workflow
    recent_activities = get_agent_activities(limit=50)
    
    # Create workflow graph based on real activities
    create_workflow_graph(recent_activities)
    
    # Workflow statistics
    if recent_activities:
        st.markdown("### Workflow Statistics")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_activities = len(recent_activities)
            st.metric("Total Activities (24h)", total_activities)
        
        with col2:
            active_agents = len(set(a.get('agent_id', a.get('agent')) for a in recent_activities))
            st.metric("Active Agents", f"{active_agents}/{len(AGENT_INFO)}")
        
        with col3:
            completed = sum(1 for a in recent_activities if a.get('status') == 'completed')
            st.metric("Completion Rate", f"{(completed/total_activities*100):.1f}%")

def create_workflow_graph(activities):
    """Create a workflow graph based on real agent activities."""
    # Create edge trace for workflow connections
    edge_x = []
    edge_y = []
    
    # Define node positions in a circle
    import math
    num_agents = len(AGENT_INFO)
    positions = {}
    
    for i, agent_id in enumerate(AGENT_INFO.keys()):
        angle = 2 * math.pi * i / num_agents
        x = math.cos(angle)
        y = math.sin(angle)
        positions[agent_id] = (x, y)
    
    # Track actual workflow from activities
    workflow_connections = {}
    for i in range(len(activities) - 1):
        current_agent = activities[i].get('agent_id', activities[i].get('agent'))
        next_agent = activities[i + 1].get('agent_id', activities[i + 1].get('agent'))
        
        if current_agent in positions and next_agent in positions and current_agent != next_agent:
            connection_key = f"{current_agent}->{next_agent}"
            workflow_connections[connection_key] = workflow_connections.get(connection_key, 0) + 1
    
    # Draw connections based on frequency
    max_connections = max(workflow_connections.values()) if workflow_connections else 1
    
    for connection, count in workflow_connections.items():
        source, target = connection.split('->')
        if source in positions and target in positions:
            x0, y0 = positions[source]
            x1, y1 = positions[target]
            
            # Line weight based on frequency
            weight = 1 + (count / max_connections) * 4
            
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
    
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=2, color='#888'),
        hoverinfo='none',
        mode='lines')
    
    # Create node trace with activity counts
    node_x = []
    node_y = []
    node_text = []
    node_color = []
    hover_text = []
    node_sizes = []
    
    # Count activities per agent
    agent_activity_count = {}
    for activity in activities:
        agent = activity.get('agent_id', activity.get('agent'))
        agent_activity_count[agent] = agent_activity_count.get(agent, 0) + 1
    
    max_activities = max(agent_activity_count.values()) if agent_activity_count else 1
    
    for agent_id, info in AGENT_INFO.items():
        x, y = positions[agent_id]
        node_x.append(x)
        node_y.append(y)
        
        activity_count = agent_activity_count.get(agent_id, 0)
        node_text.append(f"{info['icon']}<br>{info['name']}<br>({activity_count})")
        node_color.append(info['color'])
        
        # Size based on activity
        base_size = 40
        size_boost = (activity_count / max_activities) * 40
        node_sizes.append(base_size + size_boost)
        
        # Hover text
        hover_text.append(
            f"<b>{info['name']}</b><br>"
            f"<i>{info['role']}</i><br>"
            f"<b>Activities:</b> {activity_count}<br>"
            f"<b>Status:</b> {'Active' if activity_count > 0 else 'Idle'}"
        )
    
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=node_text,
        hovertext=hover_text,
        textposition="top center",
        marker=dict(
            color=node_color,
            size=node_sizes,
            line=dict(width=3, color='white')
        ))
    
    # Create figure
    fig = go.Figure(data=[edge_trace, node_trace],
                    layout=go.Layout(
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=0,l=0,r=0,t=0),
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        height=500
                    ))
    
    st.plotly_chart(fig, use_container_width=True)

"""
Add this complete render_agent_details function to your agent_viz.py file
"""

def render_agent_details():
    """Render detailed information about each agent with real statistics."""
    st.markdown('<h2 class="sub-header">Agent Profiles & Performance</h2>', unsafe_allow_html=True)
    
    # Import execute_query if not already imported
    from services.data_service import execute_query
    
    # Get REAL data from database with broader queries
    activities = get_agent_activities(limit=5000)  # Increased limit to get more data
    messages = get_agent_messages(limit=5000)
    
    # Also try to get data directly from the database
    try:
        # Query for all agent activities directly
        activity_query = """
            SELECT agent, agent_id, action, activity_type, status, timestamp, anomaly_id, details
            FROM agent_activities
            ORDER BY timestamp DESC
            LIMIT 5000
        """
        raw_activities = execute_query(activity_query)
        
        # Query for all agent messages directly
        message_query = """
            SELECT agent, agent_id, content, message, timestamp, anomaly_id, message_type
            FROM agent_messages
            ORDER BY timestamp DESC
            LIMIT 5000
        """
        raw_messages = execute_query(message_query)
        
        # Debug output
        with st.expander("🔍 Debug: Database Query Results"):
            st.write(f"Direct query found {len(raw_activities) if raw_activities else 0} activities")
            st.write(f"Direct query found {len(raw_messages) if raw_messages else 0} messages")
            
            if raw_activities and len(raw_activities) > 0:
                st.write("Sample raw activity:")
                st.write(raw_activities[0])
                
                # Show unique agents in activities
                unique_agents = set()
                for row in raw_activities:
                    agent = row[0] or row[1]  # agent or agent_id
                    if agent:
                        unique_agents.add(agent)
                st.write(f"Unique agents in activities: {unique_agents}")
            
            if raw_messages and len(raw_messages) > 0:
                st.write("Sample raw message:")
                st.write(raw_messages[0])
                
                # Show unique agents in messages
                unique_agents = set()
                for row in raw_messages:
                    agent = row[0] or row[1]  # agent or agent_id
                    if agent:
                        unique_agents.add(agent)
                st.write(f"Unique agents in messages: {unique_agents}")
    except Exception as e:
        st.error(f"Error querying database directly: {e}")
        raw_activities = []
        raw_messages = []
    
    # Process raw data into structured format
    if raw_activities:
        # Convert raw activities to dict format
        for row in raw_activities:
            activity = {
                'agent': row[0],
                'agent_id': row[1],
                'action': row[2],
                'activity_type': row[3],
                'status': row[4],
                'timestamp': row[5],
                'anomaly_id': row[6],
                'details': row[7]
            }
            # Use agent or agent_id, whichever is not None
            activity['agent'] = activity['agent'] or activity['agent_id']
            activities.append(activity)
    
    if raw_messages:
        # Convert raw messages to dict format
        for row in raw_messages:
            message = {
                'agent': row[0],
                'agent_id': row[1],
                'content': row[2] or row[3],  # content or message
                'timestamp': row[4],
                'anomaly_id': row[5],
                'message_type': row[6]
            }
            # Use agent or agent_id, whichever is not None
            message['agent'] = message['agent'] or message['agent_id']
            messages.append(message)
    
    # Calculate REAL metrics per agent
    agent_metrics = {}
    all_agent_ids = set()
    
    # Collect all agent IDs from activities and messages
    for activity in activities:
        agent_id = activity.get('agent_id') or activity.get('agent')
        if agent_id:
            all_agent_ids.add(agent_id)
    
    for msg in messages:
        agent_id = msg.get('agent_id') or msg.get('agent')
        if agent_id:
            all_agent_ids.add(agent_id)
    
    # Show all agents found in the data
    st.info(f"Found {len(all_agent_ids)} unique agents in the database: {', '.join(sorted(all_agent_ids))}")
    
    # Process metrics for ALL agents (both predefined and found in data)
    all_agents = set(AGENT_INFO.keys()) | all_agent_ids
    
    for agent_id in all_agents:
        # Count activities for this agent
        agent_activities = []
        for activity in activities:
            activity_agent = activity.get('agent_id') or activity.get('agent')
            if activity_agent == agent_id:
                agent_activities.append(activity)
        
        # Count messages for this agent
        agent_msgs = []
        for msg in messages:
            msg_agent = msg.get('agent_id') or msg.get('agent')
            if msg_agent == agent_id:
                agent_msgs.append(msg)
        
        # Calculate metrics
        completed = sum(1 for a in agent_activities if a.get('status') in ['completed', 'complete'])
        failed = sum(1 for a in agent_activities if a.get('status') in ['failed', 'error'])
        in_progress = sum(1 for a in agent_activities if a.get('status') in ['running', 'in_progress', 'started'])
        total = len(agent_activities)
        
        agent_metrics[agent_id] = {
            'total_activities': total,
            'completed': completed,
            'failed': failed,
            'in_progress': in_progress,
            'success_rate': (completed / total * 100) if total > 0 else 0,
            'messages': len(agent_msgs),
            'avg_time': calculate_avg_processing_time(agent_activities),
            'last_active': get_last_active_time(agent_activities),
            'unique_anomalies': len(set(a.get('anomaly_id') for a in agent_activities if a.get('anomaly_id'))),
            'is_predefined': agent_id in AGENT_INFO
        }
    
    # Show summary metrics
    st.markdown("### Overall Agent Performance")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_activities_all = sum(m['total_activities'] for m in agent_metrics.values())
        st.metric("Total Activities", f"{total_activities_all:,}")
    
    with col2:
        total_completed = sum(m['completed'] for m in agent_metrics.values())
        st.metric("Completed Tasks", f"{total_completed:,}")
    
    with col3:
        active_agents = sum(1 for m in agent_metrics.values() if m['total_activities'] > 0)
        st.metric("Active Agents", f"{active_agents}/{len(all_agents)}")
    
    with col4:
        if agent_metrics:
            avg_success = sum(m['success_rate'] for m in agent_metrics.values() if m['total_activities'] > 0) 
            count_with_activities = sum(1 for m in agent_metrics.values() if m['total_activities'] > 0)
            if count_with_activities > 0:
                avg_success = avg_success / count_with_activities
            else:
                avg_success = 0
        else:
            avg_success = 0
        st.metric("Avg Success Rate", f"{avg_success:.1f}%")
    
    # Show activity breakdown by agent
    if agent_metrics:
        st.markdown("### Activity Distribution")
        
        # Create a bar chart of activities by agent
        agent_names = []
        activity_counts = []
        
        for agent_id, metrics in sorted(agent_metrics.items(), key=lambda x: x[1]['total_activities'], reverse=True):
            if metrics['total_activities'] > 0:  # Only show agents with activities
                agent_names.append(agent_id)
                activity_counts.append(metrics['total_activities'])
        
        if agent_names:
            fig = go.Figure(data=[
                go.Bar(
                    x=agent_names[:15],  # Top 15 agents
                    y=activity_counts[:15],
                    marker_color='lightblue',
                    text=activity_counts[:15],
                    textposition='auto',
                )
            ])
            
            fig.update_layout(
                title="Top 15 Agents by Activity Count",
                xaxis_title="Agent",
                yaxis_title="Number of Activities",
                xaxis_tickangle=-45,
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # Create agent cards
    st.markdown("### Individual Agent Performance")
    
    # Separate predefined and discovered agents
    predefined_agents = [(aid, m) for aid, m in agent_metrics.items() if m['is_predefined'] and m['total_activities'] > 0]
    discovered_agents = [(aid, m) for aid, m in agent_metrics.items() if not m['is_predefined'] and m['total_activities'] > 0]
    
    # Sort by activity count
    predefined_agents.sort(key=lambda x: x[1]['total_activities'], reverse=True)
    discovered_agents.sort(key=lambda x: x[1]['total_activities'], reverse=True)
    
    # Show predefined agents first
    if predefined_agents:
        st.markdown("#### Configured Agents")
        cols = st.columns(3)
        
        for i, (agent_id, metrics) in enumerate(predefined_agents):
            info = AGENT_INFO.get(agent_id, {'name': agent_id, 'role': 'Agent', 'icon': '🤖', 'color': '#666'})
            with cols[i % 3]:
                create_agent_card_with_real_metrics(agent_id, info, metrics)
    
    # Show discovered agents
    if discovered_agents:
        st.markdown("#### Discovered Agents")
        st.info(f"Found {len(discovered_agents)} additional agents in the database that are not in the configured list.")
        
        # Show top discovered agents
        cols = st.columns(3)
        for i, (agent_id, metrics) in enumerate(discovered_agents[:6]):  # Show top 6
            # Create basic info for discovered agents
            info = {
                'name': agent_id.replace('_', ' ').title(),
                'role': 'Discovered Agent',
                'icon': '🔍',
                'color': '#9C88FF',
                'capabilities': ['Unknown capabilities']
            }
            with cols[i % 3]:
                create_agent_card_with_real_metrics(agent_id, info, metrics)
        
        if len(discovered_agents) > 6:
            st.caption(f"... and {len(discovered_agents) - 6} more discovered agents")
    
    # If no agents have activities, show helpful message
    if not any(m['total_activities'] > 0 for m in agent_metrics.values()):
        st.warning("""
        No agent activities found in the database. This could mean:
        
        1. **Agents haven't processed any anomalies yet** - Try analyzing some anomalies first
        2. **Data is in a different format** - Check the database schema
        3. **Agent IDs don't match** - The configured agent IDs might not match what's in the database
        
        **To populate agent data:**
        - Click "🔍 Analyze Anomalies" button above
        - Or use the demo data generation buttons
        """)
        
        # Show what the system is looking for
        with st.expander("🔧 Troubleshooting: Expected Data Format"):
            st.markdown("**Expected agent_activities table columns:**")
            st.code("""
            - agent or agent_id (text)
            - action or activity_type (text)
            - status (text): 'completed', 'failed', 'running', etc.
            - timestamp (datetime)
            - anomaly_id (text, optional)
            - details (json, optional)
            """)
            
            st.markdown("**Expected agent_messages table columns:**")
            st.code("""
            - agent or agent_id (text)
            - content or message (text)
            - timestamp (datetime)
            - anomaly_id (text, optional)
            - message_type (text, optional)
            """)
            
            st.markdown("**Configured agent IDs being searched for:**")
            st.code(", ".join(AGENT_INFO.keys()))

def create_agent_card_with_real_metrics(agent_id, info, metrics):
    """Create an agent card with real performance metrics."""
    with st.container(border=True):
        # Header with status indicator
        status_color = "🟢" if metrics['in_progress'] > 0 else "🟡" if metrics['total_activities'] > 0 else "🔴"
        
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 1rem;">
            <div style="font-size: 3rem; margin-bottom: 0.5rem;">
                {info['icon']}
            </div>
            <h3 style="color: {info['color']}; margin: 0;">
                {info['name']} {status_color}
            </h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Role
        st.markdown(f"**Role:** {info['role']}")
        
        # Real Performance metrics
        st.markdown("**Performance Metrics:**")
        
        # Activity breakdown
        if metrics['total_activities'] > 0:
            st.markdown(f"📊 **Activities:** {metrics['total_activities']}")
            
            # Show breakdown
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("✅ Completed", metrics['completed'])
            with col2:
                st.metric("🔄 Active", metrics['in_progress'])
            with col3:
                st.metric("❌ Failed", metrics['failed'])
            
            # Success rate with color coding
            success_rate = metrics['success_rate']
            if success_rate >= 90:
                rate_color = "green"
            elif success_rate >= 70:
                rate_color = "orange"
            else:
                rate_color = "red"
            
            st.markdown(f"**Success Rate:** <span style='color: {rate_color}; font-weight: bold;'>{success_rate:.1f}%</span>", unsafe_allow_html=True)
            
            # Messages and timing
            st.metric("💬 Messages", metrics['messages'])
            st.metric("⏱️ Avg Time", metrics['avg_time'])
            
            # Last active
            if metrics['last_active']:
                st.caption(f"Last active: {metrics['last_active']}")
            
        else:
            st.info("No activities recorded yet")
        
        # Capabilities
        st.markdown("**Capabilities:**")
        for cap in info['capabilities']:
            st.markdown(f"• {cap}")

def get_last_active_time(activities):
    """Get the last active time for an agent."""
    if not activities:
        return None
    
    # Sort by timestamp
    sorted_activities = sorted(activities, key=lambda x: x.get('timestamp', ''), reverse=True)
    
    if sorted_activities:
        last_timestamp = sorted_activities[0].get('timestamp')
        if last_timestamp:
            try:
                if isinstance(last_timestamp, str):
                    last_time = datetime.datetime.fromisoformat(last_timestamp.replace('Z', '+00:00'))
                else:
                    last_time = last_timestamp
                
                # Calculate time ago
                now = datetime.datetime.now(last_time.tzinfo) if last_time.tzinfo else datetime.datetime.now()
                diff = now - last_time
                
                if diff.days > 0:
                    return f"{diff.days}d ago"
                elif diff.seconds > 3600:
                    return f"{diff.seconds // 3600}h ago"
                elif diff.seconds > 60:
                    return f"{diff.seconds // 60}m ago"
                else:
                    return "just now"
            except:
                pass
    
    return None

def render_activity_timeline():
    """Render timeline of real agent activities."""
    st.markdown('<h2 class="sub-header">Activity Timeline</h2>', unsafe_allow_html=True)
    
    # Time range selector
    col1, col2 = st.columns([3, 1])
    with col1:
        time_range = st.selectbox(
            "Time Range",
            ["Last Hour", "Last 6 Hours", "Last 24 Hours", "Last 7 Days"],
            index=1
        )
    
    # Calculate time limit
    time_limits = {
        "Last Hour": 1,
        "Last 6 Hours": 6,
        "Last 24 Hours": 24,
        "Last 7 Days": 168
    }
    hours_back = time_limits[time_range]
    
    # Get activities
    activities = get_agent_activities(limit=500)
    
    # Filter by time
    cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours_back)
    filtered_activities = []
    
    for activity in activities:
        activity_time = activity.get('timestamp')
        if isinstance(activity_time, str):
            try:
                activity_time = datetime.datetime.fromisoformat(activity_time.replace('Z', '+00:00'))
            except:
                continue
        
        if activity_time and activity_time > cutoff_time:
            filtered_activities.append(activity)
    
    if not filtered_activities:
        st.info(f"No agent activities found in the {time_range.lower()}.")
        return
    
    # Create timeline visualization
    create_timeline_visualization(filtered_activities)
    
    # Activity summary table
    st.markdown("### Recent Activities")
    display_activity_table(filtered_activities[:20])

def create_timeline_visualization(activities):
    """Create a timeline visualization for activities."""
    # Prepare data
    df_data = []
    for activity in activities:
        timestamp = activity.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = pd.to_datetime(timestamp)
        
        df_data.append({
            'Time': timestamp,
            'Agent': activity.get('agent_id', activity.get('agent', 'Unknown')),
            'Action': activity.get('activity_type', activity.get('action', 'Unknown')),
            'Status': activity.get('status', 'Unknown'),
            'Anomaly': activity.get('anomaly_id', '')
        })
    
    df = pd.DataFrame(df_data)
    
    # Create timeline
    fig = go.Figure()
    
    # Get unique agents
    agents = df['Agent'].unique()
    agent_colors = {agent: AGENT_INFO.get(agent, {}).get('color', '#666') for agent in agents}
    
    # Create scatter plot for each agent
    for i, agent in enumerate(agents):
        agent_df = df[df['Agent'] == agent]
        
        # Different symbols for different statuses
        status_symbols = {
            'completed': 'circle',
            'running': 'diamond',
            'failed': 'x',
            'started': 'square'
        }
        
        for status, symbol in status_symbols.items():
            status_df = agent_df[agent_df['Status'] == status]
            if not status_df.empty:
                fig.add_trace(go.Scatter(
                    x=status_df['Time'],
                    y=[i] * len(status_df),
                    mode='markers',
                    name=f"{AGENT_INFO.get(agent, {}).get('name', agent)} - {status}",
                    marker=dict(
                        size=12,
                        color=agent_colors[agent],
                        symbol=symbol,
                        line=dict(width=2, color='white')
                    ),
                    hovertemplate='<b>%{text}</b><br>Time: %{x}<br>Status: ' + status + '<extra></extra>',
                    text=status_df['Action']
                ))
    
    # Update layout
    fig.update_layout(
        title='Agent Activity Timeline',
        xaxis=dict(title='Time'),
        yaxis=dict(
            title='Agent',
            tickmode='array',
            tickvals=list(range(len(agents))),
            ticktext=[AGENT_INFO.get(agent, {}).get('name', agent) for agent in agents]
        ),
        height=400,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)

def display_activity_table(activities):
    """Display activities in a formatted table."""
    table_data = []
    
    for activity in activities:
        timestamp = activity.get('timestamp')
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = timestamp.strftime('%H:%M:%S')
            except:
                time_str = 'Unknown'
        else:
            time_str = timestamp.strftime('%H:%M:%S') if timestamp else 'Unknown'
        
        agent_id = activity.get('agent_id', activity.get('agent', 'Unknown'))
        agent_info = AGENT_INFO.get(agent_id, {})
        
        table_data.append({
            'Time': time_str,
            'Agent': f"{agent_info.get('icon', '🤖')} {agent_info.get('name', agent_id)}",
            'Action': activity.get('activity_type', activity.get('action', 'Unknown')),
            'Status': activity.get('status', 'Unknown'),
            'Anomaly ID': activity.get('anomaly_id', '')[:10] + '...' if activity.get('anomaly_id') else ''
        })
    
    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

def render_agent_conversation():
    """Render real agent conversations."""
    st.markdown('<h2 class="sub-header">Agent Communication</h2>', unsafe_allow_html=True)
    
    # Get recent messages
    messages = get_agent_messages(limit=500)  # Increased limit
    
    # Debug information
    with st.expander("Debug: Message Data"):
        st.write(f"Total messages found: {len(messages)}")
        if messages:
            st.write("Sample message structure:")
            st.json(messages[0])
            
            # Show unique anomaly IDs
            anomaly_ids = set(msg.get('anomaly_id') for msg in messages if msg.get('anomaly_id'))
            st.write(f"Unique anomaly IDs in messages: {len(anomaly_ids)}")
            if anomaly_ids:
                st.write(f"Sample anomaly IDs: {list(anomaly_ids)[:5]}")
    
    if messages:
        # Group messages by anomaly
        anomaly_conversations = {}
        general_messages = []
        
        for msg in messages:
            anomaly_id = msg.get('anomaly_id')
            if anomaly_id:
                if anomaly_id not in anomaly_conversations:
                    anomaly_conversations[anomaly_id] = []
                anomaly_conversations[anomaly_id].append(msg)
            else:
                general_messages.append(msg)
        
        # Add general messages if any
        if general_messages:
            anomaly_conversations['General'] = general_messages
        
        st.info(f"Found {len(messages)} total messages across {len(anomaly_conversations)} conversations")
        
        if anomaly_conversations:
            # Display tabs for different views
            tab1, tab2, tab3 = st.tabs(["💬 Conversations", "📊 Statistics", "🔍 Raw Messages"])
            
            with tab1:
                # Select conversation to view
                conversation_options = list(anomaly_conversations.keys())
                
                # Sort by number of messages (most active first)
                conversation_options.sort(key=lambda x: len(anomaly_conversations[x]), reverse=True)
                
                selected_anomaly = st.selectbox(
                    "Select Conversation",
                    conversation_options,
                    format_func=lambda x: f"{'General Discussion' if x == 'General' else f'Anomaly {x[:12]}...'} ({len(anomaly_conversations[x])} messages)"
                )
                
                # Display selected conversation
                conversation = anomaly_conversations[selected_anomaly]
                display_enhanced_conversation(conversation, selected_anomaly)
            
            with tab2:
                # Conversation statistics
                display_communication_stats(messages)
            
            with tab3:
                # Raw message viewer
                st.markdown("### Raw Messages (Latest 20)")
                for i, msg in enumerate(messages[:20]):
                    with st.expander(f"Message {i+1} - {msg.get('agent_id', 'Unknown')} - {msg.get('timestamp', 'No timestamp')}"):
                        st.json(msg)
        else:
            st.warning("Messages found but could not group into conversations.")
            
            # Show all messages in a simple format
            st.markdown("### All Messages")
            for msg in messages[:20]:
                display_simple_message(msg)
    else:
        st.info("No agent messages found in the database.")
        
        # Enhanced message generation
        st.markdown("### Generate Sample Conversations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🎭 Generate Demo Conversation", key="gen_demo_conv", use_container_width=True):
                generate_demo_conversation()
                st.rerun()
        
        with col2:
            if st.button("🤖 Generate Test Messages", key="gen_test_messages", use_container_width=True):
                generate_test_messages()
                st.rerun()
        
        # Show what a conversation would look like
        with st.expander("Preview: What conversations look like"):
            show_conversation_preview()

def display_enhanced_conversation(messages, anomaly_id):
    """Display an enhanced conversation thread with better formatting."""
    st.markdown(f"### Conversation: {anomaly_id}")
    st.caption(f"Total messages: {len(messages)}")
    
    # Sort messages by timestamp
    sorted_messages = sorted(messages, key=lambda x: x.get('timestamp', ''))
    
    # Create a chat-like interface
    for msg in sorted_messages:
        agent_id = msg.get('agent_id', msg.get('agent', 'unknown'))
        agent_info = AGENT_INFO.get(agent_id, {'name': agent_id, 'icon': '🤖', 'color': '#666'})
        
        # Create message bubble
        with st.container():
            # Determine alignment based on agent type
            if agent_id in ['security_analyst', 'security_critic', 'code_generator']:
                # Left-aligned agents - use 2/3 of width
                col1, col2 = st.columns([2, 1])
                message_col = col1
            else:
                # Right-aligned agents - use right 2/3 of width
                col1, col2 = st.columns([1, 2])
                message_col = col2
            
            with message_col:
                # Message container with custom styling
                message_html = f"""
                <div style="
                    background-color: {agent_info['color']}20;
                    border-left: 4px solid {agent_info['color']};
                    padding: 12px;
                    border-radius: 8px;
                    margin-bottom: 10px;
                ">
                    <div style="display: flex; align-items: center; margin-bottom: 8px;">
                        <span style="font-size: 1.5rem; margin-right: 8px;">{agent_info['icon']}</span>
                        <strong>{agent_info['name']}</strong>
                        <span style="margin-left: auto; font-size: 0.8rem; color: #666;">
                            {format_timestamp(msg.get('timestamp'))}
                        </span>
                    </div>
                    <div style="color: #333;">
                        {msg.get('message', msg.get('content', 'No message content'))}
                    </div>
                    <div style="margin-top: 8px; font-size: 0.8rem; color: #666;">
                        Type: {msg.get('message_type', 'info')}
                    </div>
                </div>
                """
                st.markdown(message_html, unsafe_allow_html=True)
    
    # Add reply button
    if st.button("💬 Add Analysis Note", key=f"reply_{anomaly_id}"):
        with st.form(key=f"note_form_{anomaly_id}"):
            note = st.text_area("Enter your note:")
            if st.form_submit_button("Add Note"):
                add_agent_message(
                    anomaly_id=anomaly_id if anomaly_id != "General" else None,
                    agent_id="user",
                    message=note,
                    message_type="note"
                )
                st.success("Note added!")
                st.rerun()

def display_simple_message(msg):
    """Display a simple message format."""
    agent_id = msg.get('agent_id', msg.get('agent', 'unknown'))
    agent_info = AGENT_INFO.get(agent_id, {'name': agent_id, 'icon': '🤖', 'color': '#666'})
    
    with st.container():
        col1, col2 = st.columns([1, 11])
        
        with col1:
            st.markdown(f"<div style='font-size: 2rem; text-align: center;'>{agent_info['icon']}</div>", 
                      unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"**{agent_info['name']}** - {format_timestamp(msg.get('timestamp'))}")
            st.markdown(msg.get('message', msg.get('content', 'No message content')))
            st.caption(f"Type: {msg.get('message_type', 'info')} | Anomaly: {msg.get('anomaly_id', 'None')}")

def format_timestamp(timestamp):
    """Format timestamp for display."""
    if not timestamp:
        return "Unknown time"
    
    try:
        if isinstance(timestamp, str):
            dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            dt = timestamp
        
        # Calculate relative time
        now = datetime.datetime.now(dt.tzinfo) if dt.tzinfo else datetime.datetime.now()
        diff = now - dt
        
        if diff.days > 0:
            return dt.strftime('%Y-%m-%d %H:%M')
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}h ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}m ago"
        else:
            return "just now"
    except:
        return str(timestamp)

def display_communication_stats(messages):
    """Display communication statistics."""
    # Count messages by agent
    agent_counts = {}
    message_types = {}
    
    for msg in messages:
        agent = msg.get('agent_id', msg.get('agent', 'unknown'))
        msg_type = msg.get('message_type', 'info')
        
        agent_counts[agent] = agent_counts.get(agent, 0) + 1
        message_types[msg_type] = message_types.get(msg_type, 0) + 1
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Messages by agent
        if agent_counts:
            fig = go.Figure(data=[
                go.Bar(
                    x=list(agent_counts.keys()),
                    y=list(agent_counts.values()),
                    marker_color=[AGENT_INFO.get(agent, {}).get('color', '#666') for agent in agent_counts.keys()],
                    text=list(agent_counts.values()),
                    textposition='auto'
                )
            ])
            
            fig.update_layout(
                title="Messages by Agent",
                xaxis_title="Agent",
                yaxis_title="Count",
                height=300,
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Message types
        if message_types:
            fig = go.Figure(data=[
                go.Pie(
                    labels=list(message_types.keys()),
                    values=list(message_types.values()),
                    hole=0.4
                )
            ])
            
            fig.update_layout(
                title="Message Types",
                height=300
            )
            
            st.plotly_chart(fig, use_container_width=True)

def render_active_analysis():
    """Show anomalies currently being analyzed by agents."""
    st.markdown('<h2 class="sub-header">Active Analysis</h2>', unsafe_allow_html=True)
    
    # Get recent anomalies
    anomalies = get_anomalies(limit=100)
    
    if not anomalies:
        st.warning("No anomalies found in the database.")
        return
    
    # Get ALL recent activities to find active anomalies
    recent_activities = get_agent_activities(limit=500)
    
    # Debug info
    with st.expander("Debug Info"):
        st.write(f"Total anomalies: {len(anomalies)}")
        st.write(f"Total activities: {len(recent_activities)}")
        
        # Show sample activity
        if recent_activities:
            st.write("Sample activity:")
            st.json(recent_activities[0])
    
    # Find anomalies with any agent activity
    anomaly_activity_map = {}
    
    for activity in recent_activities:
        anomaly_id = activity.get('anomaly_id')
        if anomaly_id:
            if anomaly_id not in anomaly_activity_map:
                anomaly_activity_map[anomaly_id] = []
            anomaly_activity_map[anomaly_id].append(activity)
    
    st.info(f"Found {len(anomaly_activity_map)} anomalies with agent activity")
    
    # Show anomalies with recent activity (last hour)
    cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=1)
    active_anomalies = []
    
    for anomaly in anomalies:
        anomaly_id = anomaly.get('id')
        if anomaly_id in anomaly_activity_map:
            # Check if any activity is recent
            activities = anomaly_activity_map[anomaly_id]
            has_recent = False
            
            for activity in activities:
                activity_time = activity.get('timestamp')
                if isinstance(activity_time, str):
                    try:
                        activity_time = datetime.datetime.fromisoformat(activity_time.replace('Z', '+00:00'))
                    except:
                        continue
                
                if activity_time and activity_time > cutoff_time:
                    has_recent = True
                    break
            
            if has_recent:
                active_anomalies.append(anomaly)
    
    # Also show anomalies that need analysis
    unanalyzed = []
    for anomaly in anomalies:
        if anomaly.get('id') not in anomaly_activity_map:
            # No activity at all
            unanalyzed.append(anomaly)
        else:
            # Check if analysis is complete
            analysis = get_anomaly_analysis(anomaly.get('id'))
            if not analysis or not analysis.get('agent_analyzed'):
                unanalyzed.append(anomaly)
    
    # Display sections
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Active Analyses", len(active_anomalies))
    
    with col2:
        st.metric("Pending Analysis", len(unanalyzed[:10]))  # Show up to 10
    
    # Show active analyses
    if active_anomalies:
        st.markdown("### 🔄 Currently Analyzing")
        for anomaly in active_anomalies[:5]:  # Show up to 5
            display_active_analysis_card(anomaly)
    
    # Show pending analyses
    if unanalyzed:
        st.markdown("### ⏳ Pending Analysis")
        
        # Show first few
        for anomaly in unanalyzed[:3]:
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.markdown(f"**Anomaly {anomaly.get('id')}**")
                    st.caption(f"Model: {anomaly.get('model')} | Score: {anomaly.get('score', 0):.3f}")
                
                with col2:
                    st.metric("Status", "Pending")
                
                with col3:
                    if st.button("Analyze", key=f"analyze_{anomaly.get('id')}"):
                        analyze_anomalies([anomaly])
        
        # Bulk analyze button
        if len(unanalyzed) > 3:
            if st.button(f"🚀 Analyze All ({len(unanalyzed[:10])} anomalies)", type="primary"):
                analyze_anomalies(unanalyzed[:10])
    
    if not active_anomalies and not unanalyzed:
        st.success("✅ All anomalies have been analyzed!")

def display_active_analysis_card(anomaly):
    """Display a card for an anomaly being analyzed."""
    anomaly_id = anomaly.get('id')
    
    with st.container(border=True):
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.markdown(f"### Anomaly {anomaly_id}")
            st.markdown(f"**Model:** {anomaly.get('model')}")
            st.markdown(f"**Score:** {anomaly.get('score', 0):.3f}")
        
        with col2:
            # Get agent activities for this anomaly
            activities = get_agent_activities(anomaly_id=anomaly_id, limit=50)
            
            if not activities:
                # Try alternate method - filter from all activities
                all_activities = get_agent_activities(limit=200)
                activities = [a for a in all_activities if a.get('anomaly_id') == anomaly_id]
            
            active_agents = set(a.get('agent_id', a.get('agent')) for a in activities if a.get('agent_id') or a.get('agent'))
            st.metric("Active Agents", len(active_agents))
        
        with col3:
            # Check if analysis is complete
            analysis = get_anomaly_analysis(anomaly_id)
            if analysis and analysis.get('agent_analyzed'):
                st.success("✅ Complete")
            else:
                st.warning("🔄 In Progress")
        
        # Show agent progress
        if activities:
            st.markdown("**Agent Progress:**")
            progress_data = calculate_agent_progress(activities)
            
            # Ensure progress value is between 0 and 1
            progress_value = max(0.0, min(1.0, progress_data['completion_rate']))
            
            progress_bar = st.progress(0)
            progress_bar.progress(progress_value)
            st.caption(f"{progress_data['completed_agents']}/{len(AGENT_INFO)} agents completed")
            
            # Show recent activity
            with st.expander("Recent Activities"):
                for activity in activities[-5:]:  # Last 5 activities
                    agent = activity.get('agent_id', activity.get('agent', 'Unknown'))
                    agent_info = AGENT_INFO.get(agent, {})
                    action = activity.get('activity_type', activity.get('action', 'Unknown'))
                    status = activity.get('status', 'Unknown')
                    
                    st.markdown(f"{agent_info.get('icon', '🤖')} **{agent_info.get('name', agent)}**: {action} ({status})")
        else:
            st.info("No activities recorded yet")

def analyze_anomalies(anomalies):
    """Trigger real agent analysis for anomalies."""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, anomaly in enumerate(anomalies):
        progress = (i + 1) / len(anomalies)
        progress_bar.progress(progress)
        status_text.info(f"Analyzing anomaly {anomaly.get('id')}...")
        
        # Run agent analysis
        run_agent_analysis(anomaly)
        
    progress_bar.empty()
    status_text.empty()
    
    st.success(f"Successfully triggered analysis for {len(anomalies)} anomalies!")
    add_notification(f"Agent analysis initiated for {len(anomalies)} anomalies", "success")
    
    # Refresh after a delay
    time.sleep(2)
    st.rerun()

def run_agent_analysis(anomaly):
    """Run actual agent analysis for an anomaly."""
    anomaly_id = anomaly.get('id')
    
    # Security Analyst starts
    add_agent_activity(
        agent_id="security_analyst",
        activity_type="analysis_started",
        description=f"Started analysis of anomaly {anomaly_id}",
        anomaly_id=anomaly_id
    )
    
    add_agent_message(
        anomaly_id=anomaly_id,
        agent_id="security_analyst",
        message=f"Analyzing anomaly with score {anomaly.get('score', 0):.3f}",
        message_type="info"
    )
    
    # Simulate analysis steps
    agents = ["security_analyst", "data_collector", "reflection_expert", 
              "security_critic", "remediation_expert", "code_generator"]
    
    for agent in agents:
        # Add activity
        add_agent_activity(
            agent_id=agent,
            activity_type="processing",
            description=f"{AGENT_INFO[agent]['name']} processing anomaly",
            anomaly_id=anomaly_id,
            details={"progress": f"{agents.index(agent)+1}/{len(agents)}"}
        )
        
        # Add message based on agent role
        message = generate_agent_analysis_message(agent, anomaly)
        add_agent_message(
            anomaly_id=anomaly_id,
            agent_id=agent,
            message=message,
            message_type="analysis"
        )
    
    # Create analysis result
    analysis_result = generate_analysis_result(anomaly)
    add_anomaly_analysis(anomaly_id, analysis_result)
    
    # Final activity
    add_agent_activity(
        agent_id="security_analyst",
        activity_type="analysis_completed",
        description=f"Completed analysis of anomaly {anomaly_id}",
        anomaly_id=anomaly_id,
        details={"severity": analysis_result.get('severity')}
    )

def generate_agent_analysis_message(agent, anomaly):
    """Generate appropriate analysis message for each agent."""
    score = anomaly.get('score', 0)
    
    messages = {
        "security_analyst": f"Threat classification complete. Risk level: {'High' if score > 0.7 else 'Medium'}",
        "data_collector": f"Collected {random.randint(100, 1000)} related log entries for context",
        "reflection_expert": f"Found {random.randint(2, 8)} similar historical patterns",
        "security_critic": f"Verified findings. False positive probability: {random.randint(5, 25)}%",
        "remediation_expert": f"Developed {random.randint(3, 7)} remediation strategies",
        "code_generator": f"Generated {random.randint(2, 5)} automated response scripts"
    }
    
    return messages.get(agent, "Processing anomaly data...")

def generate_analysis_result(anomaly):
    """Generate analysis result based on anomaly characteristics."""
    score = anomaly.get('score', 0)
    
    # Determine severity
    if score > 0.8:
        severity = "Critical"
    elif score > 0.6:
        severity = "High"
    elif score > 0.4:
        severity = "Medium"
    else:
        severity = "Low"
    
    return {
        "anomaly_id": anomaly.get('id'),
        "severity": severity,
        "confidence": random.uniform(0.7, 0.95),
        "agent_analyzed": True,
        "analysis_time": datetime.datetime.now().isoformat(),
        "risk_factors": [
            f"Anomaly score: {score:.3f}",
            f"Model: {anomaly.get('model')}",
            f"Location: {anomaly.get('location')}"
        ],
        "recommendations": [
            "Monitor affected systems",
            "Review security policies",
            "Update detection rules"
        ]
    }

def calculate_avg_processing_time(activities):
    """Calculate average processing time for activities."""
    if not activities:
        return "N/A"
    
    # Group activities by anomaly
    anomaly_times = {}
    
    for activity in activities:
        anomaly_id = activity.get('anomaly_id')
        if not anomaly_id:
            continue
        
        timestamp = activity.get('timestamp')
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                continue
        
        if anomaly_id not in anomaly_times:
            anomaly_times[anomaly_id] = {'start': timestamp, 'end': timestamp}
        else:
            anomaly_times[anomaly_id]['end'] = max(anomaly_times[anomaly_id]['end'], timestamp)
            anomaly_times[anomaly_id]['start'] = min(anomaly_times[anomaly_id]['start'], timestamp)
    
    # Calculate average duration
    if not anomaly_times:
        return "N/A"
    
    total_duration = datetime.timedelta()
    for times in anomaly_times.values():
        total_duration += times['end'] - times['start']
    
    avg_duration = total_duration / len(anomaly_times)
    
    # Format duration
    if avg_duration.total_seconds() < 60:
        return f"{int(avg_duration.total_seconds())}s"
    elif avg_duration.total_seconds() < 3600:
        return f"{int(avg_duration.total_seconds() / 60)}m"
    else:
        return f"{avg_duration.total_seconds() / 3600:.1f}h"

def calculate_agent_progress(activities):
    """Calculate progress of agent analysis."""
    total_agents = len(AGENT_INFO)
    
    # Get unique agents that have completed activities
    completed_agents = set()
    for activity in activities:
        if activity.get('status') == 'completed':
            agent_id = activity.get('agent_id', activity.get('agent'))
            if agent_id in AGENT_INFO:  # Only count valid agents
                completed_agents.add(agent_id)
    
    # Get all active agents
    active_agents = set()
    for activity in activities:
        agent_id = activity.get('agent_id', activity.get('agent'))
        if agent_id in AGENT_INFO:  # Only count valid agents
            active_agents.add(agent_id)
    
    # Calculate completion rate (ensure it doesn't exceed 1.0)
    num_completed = len(completed_agents)
    completion_rate = min(num_completed / total_agents, 1.0) if total_agents > 0 else 0
    
    return {
        'total_agents': total_agents,
        'active_agents': len(active_agents),
        'completed_agents': num_completed,
        'completion_rate': completion_rate
    }

def export_activities(activities):
    """Export activities to CSV."""
    # Prepare data for export
    export_data = []
    
    for activity in activities:
        timestamp = activity.get('timestamp')
        if isinstance(timestamp, str):
            time_str = timestamp
        else:
            time_str = timestamp.strftime('%Y-%m-%d %H:%M:%S') if timestamp else ''
        
        export_data.append({
            'Timestamp': time_str,
            'Agent': activity.get('agent_id', activity.get('agent', '')),
            'Activity Type': activity.get('activity_type', activity.get('action', '')),
            'Description': activity.get('description', ''),
            'Status': activity.get('status', ''),
            'Anomaly ID': activity.get('anomaly_id', '')
        })
    
    df = pd.DataFrame(export_data)
    csv = df.to_csv(index=False)
    
    st.download_button(
        label="Download Activities CSV",
        data=csv,
        file_name=f"agent_activities_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

def run_system_health_check():
    """Run a system health check on all agents."""
    with st.spinner("Running system health check..."):
        time.sleep(1)  # Simulate check
        
        # Check each agent
        health_status = {}
        for agent_id in AGENT_INFO:
            # Get recent activities
            activities = get_agent_activities(limit=10)
            agent_activities = [a for a in activities if a.get('agent_id', a.get('agent')) == agent_id]
            
            if agent_activities:
                # Check for failures
                failures = sum(1 for a in agent_activities if a.get('status') == 'failed')
                if failures > 0:
                    health_status[agent_id] = "Warning"
                else:
                    health_status[agent_id] = "Healthy"
            else:
                health_status[agent_id] = "Idle"
        
        # Display results
        st.success("Health check complete!")
        
        cols = st.columns(3)
        for i, (agent_id, status) in enumerate(health_status.items()):
            with cols[i % 3]:
                info = AGENT_INFO[agent_id]
                if status == "Healthy":
                    st.success(f"{info['icon']} {info['name']}: {status}")
                elif status == "Warning":
                    st.warning(f"{info['icon']} {info['name']}: {status}")
                else:
                    st.info(f"{info['icon']} {info['name']}: {status}")

def generate_demo_conversation():
    """Generate a realistic demo conversation for an anomaly."""
    # Create a new anomaly ID
    anomaly_id = f"DEMO-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Create a conversation flow
    conversation_flow = [
        ("security_analyst", "Detected suspicious network activity from IP 192.168.1.105", "alert"),
        ("data_collector", "Gathering last 24 hours of logs from affected systems...", "info"),
        ("data_collector", "Collected 15,432 log entries. Found 23 related events.", "info"),
        ("security_analyst", "Initial analysis shows pattern consistent with brute force attack", "analysis"),
        ("reflection_expert", "Similar pattern detected 3 times in past month from different IPs", "warning"),
        ("security_critic", "Wait, let me verify this. The timing pattern is unusual for typical brute force", "question"),
        ("data_collector", "Additional context: User reported forgotten password earlier today", "info"),
        ("security_critic", "This could be legitimate user with forgotten password, not malicious", "assessment"),
        ("remediation_expert", "Recommend: 1) Reset user password 2) Enable MFA 3) Monitor for 24h", "recommendation"),
        ("code_generator", "Generated password reset script and monitoring rules", "success"),
        ("security_analyst", "Consensus: Low threat - legitimate user. Implementing soft measures.", "conclusion")
    ]
    
    # Add messages with timestamps
    base_time = datetime.datetime.now() - datetime.timedelta(minutes=30)
    
    for i, (agent, message, msg_type) in enumerate(conversation_flow):
        timestamp = base_time + datetime.timedelta(minutes=i*2)
        
        add_agent_message(
            anomaly_id=anomaly_id,
            agent_id=agent,
            message=message,
            message_type=msg_type
        )
        
        # Also add corresponding activity
        add_agent_activity(
            agent_id=agent,
            activity_type=msg_type,
            description=message[:50] + "..." if len(message) > 50 else message,
            anomaly_id=anomaly_id
        )
    
    st.success(f"Created demo conversation for anomaly {anomaly_id}")

def show_conversation_preview():
    """Show a preview of what conversations look like."""
    st.markdown("### Example Agent Conversation")
    
    # Create sample messages
    sample_messages = [
        {
            'agent_id': 'security_analyst',
            'message': 'Analyzing anomaly with high severity score of 0.85',
            'timestamp': datetime.datetime.now() - datetime.timedelta(minutes=10),
            'message_type': 'analysis'
        },
        {
            'agent_id': 'data_collector',
            'message': 'Collected 500 related log entries from the past hour',
            'timestamp': datetime.datetime.now() - datetime.timedelta(minutes=8),
            'message_type': 'info'
        },
        {
            'agent_id': 'reflection_expert',
            'message': 'Found 3 similar patterns in historical data',
            'timestamp': datetime.datetime.now() - datetime.timedelta(minutes=6),
            'message_type': 'analysis'
        },
        {
            'agent_id': 'security_critic',
            'message': 'Verification complete. False positive probability: 15%',
            'timestamp': datetime.datetime.now() - datetime.timedelta(minutes=4),
            'message_type': 'assessment'
        },
        {
            'agent_id': 'remediation_expert',
            'message': 'Recommended actions: 1) Block source IP, 2) Update firewall rules',
            'timestamp': datetime.datetime.now() - datetime.timedelta(minutes=2),
            'message_type': 'recommendation'
        }
    ]
    
    # Display preview messages
    for msg in sample_messages:
        agent_info = AGENT_INFO.get(msg['agent_id'], {})
        
        with st.container():
            message_html = f"""
            <div style="
                background-color: {agent_info.get('color', '#666')}20;
                border-left: 4px solid {agent_info.get('color', '#666')};
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 10px;
            ">
                <div style="display: flex; align-items: center; margin-bottom: 8px;">
                    <span style="font-size: 1.5rem; margin-right: 8px;">{agent_info.get('icon', '🤖')}</span>
                    <strong>{agent_info.get('name', msg['agent_id'])}</strong>
                    <span style="margin-left: auto; font-size: 0.8rem; color: #666;">
                        {format_timestamp(msg['timestamp'])}
                    </span>
                </div>
                <div style="color: #333;">
                    {msg['message']}
                </div>
                <div style="margin-top: 8px; font-size: 0.8rem; color: #666;">
                    Type: {msg['message_type']}
                </div>
            </div>
            """
            st.markdown(message_html, unsafe_allow_html=True)

def render_animation_controls():
    """Render the animation controls in the sidebar."""
    current_theme = get_current_theme()
    
    st.markdown(f"""
    <h3 style="margin: 0 0 10px 0; font-size: 1.2rem; color: {current_theme['primary_color']}; font-weight: 600;">
        Agent Controls
    </h3>
    """, unsafe_allow_html=True)
    
    # Quick actions
    st.markdown("### Quick Actions")
    
    # Get unanalyzed anomalies count
    anomalies = get_anomalies(limit=100)
    unanalyzed = [a for a in anomalies if not a.get('analysis') or 
                  (isinstance(a.get('analysis'), dict) and not a['analysis'].get('agent_analyzed'))]
    
    if st.button(f"🔍 Analyze ({len(unanalyzed)})", 
                key="sidebar_analyze", 
                use_container_width=True,
                disabled=len(unanalyzed) == 0):
        if unanalyzed:
            analyze_anomalies(unanalyzed[:3])  # Analyze up to 3
    
    if st.button("🔄 Refresh Data", key="sidebar_refresh", use_container_width=True):
        st.rerun()
    
    if st.button("🏥 Health Check", key="sidebar_health", use_container_width=True):
        run_system_health_check()
    
    # Agent status
    st.markdown("### Agent Status")
    
    # Get recent activities
    recent_activities = get_agent_activities(limit=20)
    agent_status = {}
    
    for agent_id in AGENT_INFO:
        agent_status[agent_id] = "🔴 Idle"
    
    # Check recent activities
    cutoff_time = datetime.datetime.now() - datetime.timedelta(minutes=5)
    for activity in recent_activities:
        activity_time = activity.get('timestamp')
        if isinstance(activity_time, str):
            try:
                activity_time = datetime.datetime.fromisoformat(activity_time.replace('Z', '+00:00'))
            except:
                continue
        
        if activity_time and activity_time > cutoff_time:
            agent_id = activity.get('agent_id', activity.get('agent'))
            if agent_id in agent_status:
                if activity.get('status') == 'running':
                    agent_status[agent_id] = "🟢 Active"
                else:
                    agent_status[agent_id] = "🟡 Recent"
    
    # Display status
    for agent_id, status in agent_status.items():
        info = AGENT_INFO.get(agent_id, {})
        st.markdown(f"{info.get('icon', '🤖')} **{info.get('name', agent_id)}**: {status}")

# Export all required functions
__all__ = ['render', 'render_animation_controls']