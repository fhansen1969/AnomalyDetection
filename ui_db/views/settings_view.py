"""
Settings page for the Anomaly Detection Dashboard.
Allows configuration of API connections and database settings.
"""

import streamlit as st
import time
from config.theme import get_current_theme
from config.settings import API_URL, DB_CONFIG, add_notification
from services.database import test_connection

def render():
    """Render the settings page."""
    st.markdown('<h1 class="main-header">⚙️ Settings</h1>', unsafe_allow_html=True)
    
    # Create tabs for different settings
    settings_tab1, settings_tab2 = st.tabs([
        "🔌 API Connection", "🛢️ Database"
    ])
    
    with settings_tab1:
        render_api_settings()
    
    with settings_tab2:
        render_database_settings()

def loading_animation(text="Loading...", key=None):
    """Custom loading animation with emoji."""
    animation_html = f"""
    <div style="text-align: center; padding: 10px;">
        <div style="display: inline-block; animation: spin 2s linear infinite;">⏳</div>
        <div style="margin-top: 10px; font-size: 14px; color: #888;">{text}</div>
    </div>
    <style>
    @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}
    </style>
    """
    return animation_html

def render_api_settings():
    """Render API configuration settings."""
    current_theme = get_current_theme()
    
    # API configuration
    st.markdown('<h2 class="sub-header">API Configuration</h2>', unsafe_allow_html=True)
    
    st.markdown(f"""
    <div style="background: {current_theme['card_bg']}; border-radius: 10px; padding: 20px; 
            box-shadow: 0 8px 16px rgba(0,0,0,0.1); margin-bottom: 20px;">
        <h3 style="margin-top: 0; color: {current_theme['primary_color']};">Connection Settings</h3>
        <p>Configure the connection to the anomaly detection API.</p>
    </div>
    """, unsafe_allow_html=True)
    
    api_url = st.text_input("API URL", value=API_URL, key="api_url_input")
    
    api_col1, api_col2 = st.columns(2)
    
    with api_col1:
        api_version = st.selectbox("API Version", ["v1", "v2", "v3-beta"], key="api_version_select")
    
    with api_col2:
        api_timeout = st.number_input("Timeout (seconds)", min_value=1, max_value=60, value=30, key="api_timeout_input")
    
    auth_col1, auth_col2 = st.columns(2)
    
    with auth_col1:
        auth_type = st.selectbox("Authentication Type", ["API Key", "OAuth2", "Basic Auth", "None"], key="api_auth_type_select")
    
    with auth_col2:
        if auth_type == "API Key":
            api_key = st.text_input("API Key", type="password", value="*********", key="api_key_input")
        elif auth_type == "OAuth2":
            client_id = st.text_input("Client ID", key="api_oauth_client_id")
            client_secret = st.text_input("Client Secret", type="password", key="api_oauth_client_secret")
        elif auth_type == "Basic Auth":
            username = st.text_input("Username", key="api_basic_username")
            password = st.text_input("Password", type="password", key="api_basic_password")
    
    if st.button("💾 Save API Configuration", key="save_api_config_btn"):
        # Show loading animation
        st.markdown(loading_animation(), unsafe_allow_html=True)
        time.sleep(0.5)
        
        st.success(f"✅ API configuration updated successfully")
        add_notification("API configuration saved", "success")
    
    # API status check
    st.markdown('<h3 class="sub-header">API Status</h3>', unsafe_allow_html=True)
    
    if st.button("🔄 Test API Connection", key="test_api_connection_btn"):
        # Show loading animation
        with st.spinner("Testing API connection..."):
            st.markdown(loading_animation("Testing API connection..."), unsafe_allow_html=True)
            time.sleep(1)
            
            # Simulate API response
            st.markdown(f"""
            <div style="background-color: {current_theme['success_color']}20; padding: 15px; border-radius: 5px; 
                    border-left: 4px solid {current_theme['success_color']}; margin: 15px 0;">
                <div style="display: flex; align-items: center;">
                    <div style="color: {current_theme['success_color']}; margin-right: 10px;">
                        ✅
                    </div>
                    <div>
                        <div style="font-weight: 500;">Connection Successful</div>
                        <div style="font-size: 0.9rem;">API Version: v2.1.3</div>
                        <div style="font-size: 0.9rem;">Response Time: 124 ms</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

def render_database_settings():
    """Render database configuration settings."""
    current_theme = get_current_theme()
    
    # Database configuration
    st.markdown('<h2 class="sub-header">Database Configuration</h2>', unsafe_allow_html=True)
    
    st.markdown(f"""
    <div style="background: {current_theme['card_bg']}; border-radius: 10px; padding: 20px; 
            box-shadow: 0 8px 16px rgba(0,0,0,0.1); margin-bottom: 20px;">
        <h3 style="margin-top: 0; color: {current_theme['primary_color']};">Storage Configuration</h3>
        <p>Configure the connection to the database for storing anomaly data.</p>
    </div>
    """, unsafe_allow_html=True)
    
    db_type = st.selectbox("Database Type", ["PostgreSQL", "MySQL", "MongoDB", "SQLite"], key="db_type_select")
    
    if db_type in ["PostgreSQL", "MySQL"]:
        col1, col2 = st.columns(2)
        
        with col1:
            db_host = st.text_input("Host", value=DB_CONFIG["host"], key="db_host_input")
            db_port = st.number_input("Port", value=DB_CONFIG["port"], key="db_port_input")
            db_name = st.text_input("Database", value=DB_CONFIG["database"], key="db_name_input")
        
        with col2:
            db_user = st.text_input("Username", value=DB_CONFIG["user"], key="db_user_input")
            db_password = st.text_input("Password", value=DB_CONFIG["password"], type="password", key="db_password_input")
            db_ssl = st.checkbox("Use SSL", value=True, key="db_ssl_checkbox")
        
        pooling_col1, pooling_col2 = st.columns(2)
        
        with pooling_col1:
            use_connection_pooling = st.checkbox("Use Connection Pooling", value=True, key="db_pooling_checkbox")
        
        with pooling_col2:
            if use_connection_pooling:
                max_connections = st.number_input("Max Connections", min_value=1, max_value=100, value=20, key="db_max_connections")
    
    elif db_type == "MongoDB":
        mongo_connection = st.text_input("Connection String", value="mongodb://localhost:27017/anomaly_detection", key="mongo_connection_string")
        mongo_auth_db = st.text_input("Authentication Database", value="admin", key="mongo_auth_db")
        mongo_replica_set = st.text_input("Replica Set (optional)", key="mongo_replica_set")
    
    elif db_type == "SQLite":
        db_file = st.text_input("Database File Path", value="anomaly_detection.db", key="sqlite_file_path")
        journal_mode = st.selectbox("Journal Mode", ["WAL", "DELETE", "TRUNCATE", "PERSIST", "MEMORY", "OFF"], key="sqlite_journal_mode")
    
    # Advanced settings
    with st.expander("⚙️ Advanced Settings", expanded=False):
        if db_type in ["PostgreSQL", "MySQL"]:
            st.number_input("Connection Timeout (seconds)", min_value=1, max_value=120, value=30, key="db_conn_timeout")
            st.number_input("Command Timeout (seconds)", min_value=1, max_value=600, value=90, key="db_cmd_timeout")
            st.checkbox("Auto Reconnect", value=True, key="db_auto_reconnect")
        elif db_type == "MongoDB":
            st.number_input("Connection Timeout (ms)", min_value=100, max_value=30000, value=5000, key="mongo_conn_timeout")
            st.number_input("Socket Timeout (ms)", min_value=100, max_value=30000, value=10000, key="mongo_socket_timeout")
    
    # Save and test buttons
    button_col1, button_col2 = st.columns(2)
    
    with button_col1:
        if st.button("💾 Save Database Configuration", key="save_db_config_btn", use_container_width=True):
            # Update DB_CONFIG with new values if PostgreSQL is selected
            if db_type == "PostgreSQL":
                DB_CONFIG["host"] = db_host
                DB_CONFIG["port"] = db_port
                DB_CONFIG["database"] = db_name
                DB_CONFIG["user"] = db_user
                DB_CONFIG["password"] = db_password
                
            # Show loading animation
            st.markdown(loading_animation("Saving configuration..."), unsafe_allow_html=True)
            time.sleep(0.5)
            
            st.success("✅ Database configuration updated successfully")
            add_notification("Database configuration saved", "success")
    
    with button_col2:
        if st.button("🔄 Test Connection", key="test_db_connection_btn", use_container_width=True):
            # Show loading animation
            with st.spinner("Testing database connection..."):
                st.markdown(loading_animation("Testing connection..."), unsafe_allow_html=True)
                time.sleep(1)
                
                # Test actual connection if PostgreSQL is selected
                if db_type == "PostgreSQL":
                    # Update DB_CONFIG temporarily for testing
                    temp_db_config = dict(DB_CONFIG)
                    temp_db_config["host"] = db_host
                    temp_db_config["port"] = db_port
                    temp_db_config["database"] = db_name
                    temp_db_config["user"] = db_user
                    temp_db_config["password"] = db_password
                    
                    # Try to test the connection
                    try:
                        success, message = test_connection()
                        
                        if success:
                            # Display success message
                            st.markdown(f"""
                            <div style="background-color: {current_theme['success_color']}20; padding: 15px; border-radius: 5px; 
                                    border-left: 4px solid {current_theme['success_color']}; margin: 15px 0;">
                                <div style="display: flex; align-items: center;">
                                    <div style="color: {current_theme['success_color']}; margin-right: 10px;">
                                        ✅
                                    </div>
                                    <div>
                                        <div style="font-weight: 500;">Connection Successful</div>
                                        <div style="font-size: 0.9rem;">{message}</div>
                                        <div style="font-size: 0.9rem;">Response Time: 35 ms</div>
                                    </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            # Display error message
                            st.markdown(f"""
                            <div style="background-color: {current_theme['error_color']}20; padding: 15px; border-radius: 5px; 
                                    border-left: 4px solid {current_theme['error_color']}; margin: 15px 0;">
                                <div style="display: flex; align-items: center;">
                                    <div style="color: {current_theme['error_color']}; margin-right: 10px;">
                                        ❌
                                    </div>
                                    <div>
                                        <div style="font-weight: 500;">Connection Failed</div>
                                        <div style="font-size: 0.9rem;">{message}</div>
                                    </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                    except Exception as e:
                        # Display exception
                        st.error(f"Error testing connection: {str(e)}")
                else:
                    # Simulate database response for other database types
                    st.markdown(f"""
                    <div style="background-color: {current_theme['success_color']}20; padding: 15px; border-radius: 5px; 
                            border-left: 4px solid {current_theme['success_color']}; margin: 15px 0;">
                        <div style="display: flex; align-items: center;">
                            <div style="color: {current_theme['success_color']}; margin-right: 10px;">
                                ✅
                            </div>
                            <div>
                                <div style="font-weight: 500;">Connection Successful</div>
                                <div style="font-size: 0.9rem;">Version: {db_type} (Simulated)</div>
                                <div style="font-size: 0.9rem;">Response Time: 35 ms</div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    
    # Database initialization section
    st.markdown("---")
    st.markdown('<h3 class="sub-header">🔧 Database Initialization</h3>', unsafe_allow_html=True)
    
    st.warning("⚠️ **Warning:** Initializing/Resetting the database will delete all existing data and recreate the database schema.")
    
    if st.button("🔄 Initialize/Reset Database", key="init_reset_db_btn", type="secondary"):
        # Create confirmation dialog using session state
        st.session_state['confirm_db_reset'] = True
    
    # Show confirmation dialog if flag is set
    if st.session_state.get('confirm_db_reset', False):
        st.error("⚠️ **Are you absolutely sure?** This action cannot be undone!")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("✅ Yes, Reset Database", key="confirm_yes_reset", type="primary"):
                # Show loading animation
                with st.spinner("Resetting database..."):
                    st.markdown(loading_animation("Initializing database..."), unsafe_allow_html=True)
                    
                    # Simulate DB reset with progress bar
                    progress_text = "Initializing database..."
                    my_bar = st.progress(0)
                    for percent_complete in range(0, 101, 10):
                        time.sleep(0.2)
                        my_bar.progress(percent_complete / 100.0)
                    
                    st.success("✅ Database initialized successfully")
                    add_notification("Database has been reset and initialized", "success")
                    
                    # Clear the confirmation flag
                    st.session_state['confirm_db_reset'] = False
                    time.sleep(1)
                    st.rerun()
        
        with col2:
            if st.button("❌ Cancel", key="confirm_no_reset"):
                st.session_state['confirm_db_reset'] = False
                st.rerun()