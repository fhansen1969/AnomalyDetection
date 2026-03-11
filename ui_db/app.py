"""
Anomaly Detection Dashboard - Main Application Entry Point

This is the main entry point for the Streamlit-based Anomaly Detection Dashboard.
It handles page routing and state management.
"""

import streamlit as st
import warnings
import json
import numpy as np
import pandas as pd
from datetime import datetime

# Set page config - MUST BE FIRST STREAMLIT COMMAND
st.set_page_config(
    page_title="Anomaly Detection Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Now do all other imports after set_page_config
from config.settings import initialize_session_state
from config.theme import inject_custom_css, load_material_icons

# Import the render functions directly
from views.dashboard import render as dashboard_render
from views.anomalies import render as anomalies_render
from views.agent_viz import render as agent_viz_render
from views.system_status import render as system_status_render

# Also import the functions from agent_viz module directly
from views.agent_viz import render_animation_controls

from components.notifications import handle_notifications

# Import database connection to test it early
from services.database import test_connection
from services.data_service import get_system_status

from utils.json_utils import EnhancedJSONEncoder, json_dumps, json_loads, ensure_serializable, safe_altair_chart

# Silence the specific FutureWarning from plotly/pandas
warnings.filterwarnings(
    "ignore", 
    message="When grouping with a length-1 list-like.*",
    category=FutureWarning
)

def load_custom_css():
    """Load custom CSS for the Streamlit app."""
    st.markdown("""
    <style>
        /* Main styling for headers */
        .main-header {
            color: #1e1e1e;
            font-size: 2.3rem;
            font-weight: 700;
            margin-bottom: 1rem;
        }
        
        .sub-header {
            color: #2c3e50;
            font-size: 1.8rem;
            font-weight: 600;
            margin: 1.5rem 0 1rem 0;
        }
        
        /* Card styling */
        .dashboard-card {
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            height: 100%;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .dashboard-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 15px rgba(0,0,0,0.1);
        }
        
        /* Severity styling */
        .severity-high {
            background-color: rgba(230, 57, 70, 0.2);
            color: #e63946;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 4px;
        }
        
        .severity-medium {
            background-color: rgba(244, 162, 97, 0.2);
            color: #f4a261;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 4px;
        }
        
        .severity-low {
            background-color: rgba(42, 157, 143, 0.2);
            color: #2a9d8f;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 4px;
        }
        
        /* Animations */
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .fadeIn {
            animation: fadeIn 0.5s ease-out;
        }
        
        /* Material Icons - fallback if not loaded */
        .material-icons {
            font-family: 'Arial', sans-serif;
            font-weight: normal;
            font-style: normal;
            font-size: 24px;
            line-height: 1;
            letter-spacing: normal;
            text-transform: none;
            display: inline-block;
            white-space: nowrap;
            word-wrap: normal;
            direction: ltr;
            -webkit-font-feature-settings: 'liga';
            -webkit-font-smoothing: antialiased;
        }
        
        /* Tooltip styling */
        .tooltip {
            position: relative;
            display: inline-block;
        }

        .tooltip .tooltiptext {
            visibility: hidden;
            background-color: #333;
            color: #fff;
            text-align: center;
            border-radius: 6px;
            padding: 5px 10px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            margin-left: -60px;
            opacity: 0;
            transition: opacity 0.3s;
        }

        .tooltip:hover .tooltiptext {
            visibility: visible;
            opacity: 1;
        }
        
        /* Button styling */
        .stButton>button {
            background-color: #4361ee;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 0.5rem 1rem;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        
        .stButton>button:hover {
            background-color: #3a56d4;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        
        /* Progress bar styling */
        .stProgress > div > div > div > div {
            background-color: #4361ee;
        }
    </style>
    """, unsafe_allow_html=True)

def safe_display_chart(chart, use_container_width=True):
    """Safely display an Altair chart, handling NumPy serialization issues.
    
    Args:
        chart: An Altair chart object
        use_container_width: Whether to use the full container width
        
    Returns:
        The Streamlit chart component
    """
    import json
    import altair as alt
    
    # Custom JSON serializer to handle NumPy types
    def serialize_numpy_data(obj):
        # Handle different NumPy data types
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, bool):
            return bool(obj)
        elif isinstance(obj, (np.datetime64, np.timedelta64)):
            return str(obj)
        elif isinstance(obj, (datetime, pd.Timestamp)):
            return obj.isoformat()
        elif isinstance(obj, pd.Timedelta):
            return str(obj)
        elif isinstance(obj, pd.Series):
            return obj.tolist()
        
        # Return original object if it's not a NumPy type
        return obj
    
    try:
        # Convert the chart to a dict
        chart_dict = chart.to_dict()
        
        # Convert the dict to JSON and back with custom serializer
        chart_json = json.dumps(chart_dict, default=serialize_numpy_data)
        chart_dict = json.loads(chart_json)
        
        # Recreate the chart from the sanitized dict
        safe_chart = alt.Chart.from_dict(chart_dict)
        
        # Display the chart
        return st.altair_chart(safe_chart, use_container_width=use_container_width)
    except Exception as e:
        st.error(f"Error displaying chart: {str(e)}")
        st.warning("Attempting to display chart with fallback method...")
        
        try:
            # Try directly displaying the chart but with warning
            return st.altair_chart(chart, use_container_width=use_container_width)
        except Exception as e2:
            st.error(f"Fallback display also failed: {str(e2)}")
            
            # Extract data for a simple alternative visualization
            try:
                # Try to extract the data from the chart
                if hasattr(chart, 'data') and chart.data is not None:
                    st.write("Displaying chart data as table:")
                    return st.dataframe(chart.data, use_container_width=use_container_width)
                else:
                    st.error("Could not extract data from chart.")
            except:
                st.error("Could not display chart or extract data.")

def main():
    """Main application function that handles routing and rendering."""
    # Initialize session state if needed
    initialize_session_state()
    
    # Apply custom CSS
    inject_custom_css()
    
    # Add our additional custom CSS
    load_custom_css()
    
    # Load Material Icons
    load_material_icons()
    
    # Handle any pending notifications
    handle_notifications()
    
    # Test database connection
    success, message = test_connection()
    if not success:
        st.error(f"Database connection failed: {message}")
        st.warning("Please check database settings and ensure the PostgreSQL server is running.")
        st.info("Configure your database connection in config/settings.py")
        return
    
    # Render sidebar
    render_sidebar()
    
    # Route to the correct page based on selection
    if st.session_state.selected_page == "Dashboard":
        dashboard_render()
    elif st.session_state.selected_page == "Anomalies":
        anomalies_render()
    elif st.session_state.selected_page == "Agent Visualization":
        agent_viz_render()
    elif st.session_state.selected_page == "System Status":
        system_status_render()

def icon_card(icon, title, value, subtitle, color="#4361ee"):
    """Generate HTML for a styled card with an icon."""
    return f"""
    <div class="dashboard-card">
        <div style="color: {color}; font-size: 2rem; margin-bottom: 0.5rem;">{icon}</div>
        <h3 style="margin: 0; color: #333;">{title}</h3>
        <h2 style="margin: 5px 0; color: {color};">{value}</h2>
        <div style="font-size: 0.8rem; opacity: 0.8;">{subtitle}</div>
    </div>
    """

def render_dashboard_summary_cards():
    """Render statistics cards at the top of the dashboard."""
    import streamlit as st
    from datetime import datetime
    
    # Get data for stats
    try:
        # Try to get real data from the database
        from services.data_service import get_anomalies, get_models
        anomalies = get_anomalies(limit=5000) or []
        models = get_models() or []
        
        # Calculate statistics
        total_anomalies = len(anomalies)
        
        # Count high severity anomalies
        high_severity = sum(1 for anomaly in anomalies if anomaly and 
                          isinstance(anomaly.get('analysis'), dict) and 
                          anomaly.get('analysis', {}).get('severity') in ['Critical', 'High'])
        
        # Calculate today's anomalies
        today = datetime.now().date()
        today_anomalies = sum(1 for anomaly in anomalies if anomaly and 
                              isinstance(anomaly.get('timestamp'), str) and 
                              today.isoformat() in anomaly.get('timestamp', ''))
        
        # Active models
        active_models = sum(1 for model in models if model and model.get('status') == 'trained')
        total_models = len(models)
    except Exception as e:
        # Fall back to sample data if database fetch fails
        total_anomalies = 4
        high_severity = 0
        today_anomalies = 0
        active_models = 0
        total_models = 6
    
    # Get current date for today's anomalies card
    current_date = datetime.now().strftime("%b %d")
    
    # Create columns for cards
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)
    
    # Total Anomalies card
    with col1:
        st.markdown(
            f"""
            <div style="background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); height: 100%;">
                <div style="color: #4361ee; font-size: 2rem; margin-bottom: 0.5rem;">📊</div>
                <h3 style="margin: 0; color: #333;">Total Anomalies</h3>
                <h2 style="margin: 5px 0; color: #4361ee;">{total_anomalies}</h2>
                <div style="font-size: 0.8rem; opacity: 0.8;">Total detected anomalies</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # High Severity card
    with col2:
        st.markdown(
            f"""
            <div style="background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); height: 100%;">
                <div style="color: #e63946; font-size: 2rem; margin-bottom: 0.5rem;">⚠️</div>
                <h3 style="margin: 0; color: #333;">High Severity</h3>
                <h2 style="margin: 5px 0; color: #e63946;">{high_severity}</h2>
                <div style="font-size: 0.8rem; opacity: 0.8;">Critical and high severity</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Today's Anomalies card
    with col3:
        st.markdown(
            f"""
            <div style="background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); height: 100%;">
                <div style="color: #4361ee; font-size: 2rem; margin-bottom: 0.5rem;">📅</div>
                <h3 style="margin: 0; color: #333;">Today's Anomalies</h3>
                <h2 style="margin: 5px 0; color: #4361ee;">{today_anomalies}</h2>
                <div style="font-size: 0.8rem; opacity: 0.8;">Detected on {current_date}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Active Models card
    with col4:
        st.markdown(
            f"""
            <div style="background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); height: 100%;">
                <div style="color: #4361ee; font-size: 2rem; margin-bottom: 0.5rem;">📈</div>
                <h3 style="margin: 0; color: #333;">Active Models</h3>
                <h2 style="margin: 5px 0; color: #4361ee;">{active_models} / {total_models}</h2>
                <div style="font-size: 0.8rem; opacity: 0.8;">Out of {total_models} total models</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        
def render_sidebar():
    """Render the sidebar with navigation and real-time system status overview."""
    with st.sidebar:
        # Theme toggle button
        theme_col1, theme_col2 = st.columns([1, 3])
        with theme_col1:
            if st.button("🌓", help="Toggle Light/Dark Theme"):
                st.session_state.theme = "dark" if st.session_state.theme == "light" else "light"
                # Add notification
                if 'notifications' not in st.session_state:
                    st.session_state.notifications = []
                st.session_state.notifications.append({
                    'message': f"Switched to {st.session_state.theme} theme",
                    'type': "info"
                })
                # Force a rerun to apply the theme
                st.rerun()
        
        with theme_col2:
            st.write(f"**{st.session_state.theme.capitalize() if 'theme' in st.session_state else 'Light'} Mode**")
        
        # Logo and title with animation
        st.markdown("""
        <div style="text-align: center; animation: float 3s ease-in-out infinite;">
            <img src="https://img.icons8.com/fluency/96/000000/security-checked.png" width="80">
        </div>
        """, unsafe_allow_html=True)
        
        from config.theme import get_current_theme
        current_theme = get_current_theme()
        
        st.markdown(f"""
        <h1 style="text-align: center; background: linear-gradient(90deg, {current_theme['primary_color']}, {current_theme['secondary_color']}); 
                -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
                margin-bottom: 20px; font-size: 2.2rem; font-weight: 700;">
            Anomaly Detection
        </h1>
        """, unsafe_allow_html=True)
        
        # Navigation with custom styling
        st.markdown("""
        <style>
            div[data-testid="stRadio"] > div:first-child {
                background-color: transparent;
                padding: 0;
            }
            div[data-testid="stRadio"] > div:first-child > label {
                background-color: transparent;
                padding: 10px 15px;
                border-radius: 5px;
                margin-bottom: 5px;
                transition: all 0.3s ease;
                border-left: 3px solid transparent;
            }
            div[data-testid="stRadio"] > div:first-child > label:hover {
                background-color: rgba(67, 97, 238, 0.1);
                border-left: 3px solid rgba(67, 97, 238, 0.5);
            }
            div[data-testid="stRadio"] > div:first-child > label[data-baseweb="radio"] > div:first-child {
                background-color: transparent;
            }
            div[data-testid="stRadio"] > div:first-child > label[data-baseweb="radio"] > div:first-child[aria-checked="true"] {
                background-color: #4361ee;
                border-color: #4361ee;
            }
        </style>
        """, unsafe_allow_html=True)
        
        # Create a list of navigation options with icons (no Settings)
        nav_options = [
            "📊 Dashboard",
            "🔍 Anomalies",
            "🤖 Agent Visualization",
            "📡 System Status"
        ]
        
        # Initialize selected_page if it doesn't exist
        if 'selected_page' not in st.session_state:
            st.session_state.selected_page = "Dashboard"
        
        # Display radio buttons for navigation
        selected_option = st.radio("Navigation", nav_options)
        
        # Extract the page name from the selected option
        st.session_state.selected_page = selected_option.split(" ", 1)[1]
        
        st.divider()
        
        # Use real-time system metrics for the System Status summary
        import psutil
        import platform
        import datetime
        
        # Get real uptime data
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.datetime.now() - boot_time
        days, remainder = divmod(uptime.total_seconds(), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)
        uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m"
        
        # Get real CPU, memory, and disk usage
        cpu_usage = psutil.cpu_percent()
        memory_usage = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage('/').percent
        
        # Function to determine status color based on usage
        def get_status_color(value):
            if value < 50:
                return current_theme['success_color']
            elif value < 80:
                return current_theme['warning_color']
            else:
                return current_theme['error_color']
        
        # System status summary with real data
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, rgba(67, 97, 238, 0.2), rgba(58, 12, 163, 0.1));
                    padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 1px solid rgba(67, 97, 238, 0.3);">
            <h3 style="margin: 0 0 10px 0; font-size: 1.2rem; color: {current_theme['primary_color']}; font-weight: 600;">
                System Status
            </h3>
            <div style="display: flex; align-items: center; margin-bottom: 10px;">
                <div style="color: {current_theme['success_color']}; margin-right: 10px;">
                    ✅
                </div>
                <span>System Active</span>
            </div>
            <div style="margin-bottom: 8px; font-size: 0.9rem;">
                <strong>Uptime:</strong> {uptime_str}
            </div>
            <div style="margin-bottom: 8px; font-size: 0.9rem;">
                <strong>OS:</strong> {platform.system()} {platform.release()}
            </div>
            <div style="margin-bottom: 8px; font-size: 0.9rem;">
                <strong>Active Processes:</strong> {len(psutil.pids())}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Quick stats with real system metrics
        st.markdown(f"""
        <h3 style="margin: 0 0 10px 0; font-size: 1.2rem; color: {current_theme['primary_color']}; font-weight: 600;">
            Quick Stats
        </h3>
        """, unsafe_allow_html=True)

        from utils.ui_components import progress_bar

        # CPU Usage with real data
        cpu_color = get_status_color(cpu_usage)
        cpu_bar_html = progress_bar(cpu_usage)
        st.markdown(f"""
        <div style="margin-bottom: 15px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span style="font-size: 0.9rem; font-weight: 500;">CPU Usage</span>
                <span style="font-size: 0.9rem; font-weight: 600; color: {cpu_color};">{cpu_usage}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(cpu_bar_html, unsafe_allow_html=True)

        # Memory Usage with real data
        memory_color = get_status_color(memory_usage)
        memory_bar_html = progress_bar(memory_usage)
        st.markdown(f"""
        <div style="margin-bottom: 15px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span style="font-size: 0.9rem; font-weight: 500;">Memory Usage</span>
                <span style="font-size: 0.9rem; font-weight: 600; color: {memory_color};">{memory_usage}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(memory_bar_html, unsafe_allow_html=True)

        # Disk Usage with real data
        disk_color = get_status_color(disk_usage)
        disk_bar_html = progress_bar(disk_usage)
        st.markdown(f"""
        <div style="margin-bottom: 15px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span style="font-size: 0.9rem; font-weight: 500;">Disk Usage</span>
                <span style="font-size: 0.9rem; font-weight: 600; color: {disk_color};">{disk_usage}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(disk_bar_html, unsafe_allow_html=True)
        
        st.divider()
        
        # Agent Animation Controls (only show on Agent Visualization page)
        if st.session_state.selected_page == "Agent Visualization":
            # Use the directly imported function
            render_animation_controls()

# Add floating action button
def render_floating_action_button():
    """Render a floating action button for feedback/help."""
    from config.theme import get_current_theme
    current_theme = get_current_theme()
    
    st.markdown(f"""
    <div style="position: fixed; bottom: 20px; right: 20px; z-index: 9999;">
        <div style="width: 60px; height: 60px; border-radius: 50%; background-color: {current_theme['primary_color']}; 
                display: flex; justify-content: center; align-items: center; box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                cursor: pointer; transition: all 0.3s ease;" 
            onmouseover="this.style.transform='scale(1.1)'" onmouseout="this.style.transform='scale(1)'">
            <div style="color: white; font-size: 30px;">❓</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
    render_floating_action_button()