"""
Notification system for the Anomaly Detection Dashboard.
Provides functions for creating and managing notifications.
"""

import streamlit as st
from config.theme import get_current_theme

def create_notification(message, type='info'):
    """Create a notification popup."""
    current_theme = get_current_theme()
    
    icon = {
        'info': 'info',
        'success': 'check_circle',
        'warning': 'warning',
        'error': 'error'
    }.get(type, 'info')
    
    color = {
        'info': current_theme['primary_color'],
        'success': current_theme['success_color'],
        'warning': current_theme['warning_color'],
        'error': current_theme['error_color']
    }.get(type, current_theme['primary_color'])
    
    notification_html = f"""
    <div class="notification" style="background-color: {color};">
        <span class="material-icons" style="margin-right: 10px;">{icon}</span>
        {message}
    </div>
    """
    
    st.markdown(notification_html, unsafe_allow_html=True)

def add_notification(message, type='info'):
    """Add a notification to the session state."""
    import datetime
    
    st.session_state.notifications.append({
        'message': message,
        'type': type,
        'time': datetime.datetime.now().isoformat()
    })

def handle_notifications():
    """Process and display any pending notifications."""
    if hasattr(st.session_state, 'notifications') and st.session_state.notifications:
        # Get the latest notification
        notification = st.session_state.notifications.pop(0)
        create_notification(notification['message'], notification['type'])