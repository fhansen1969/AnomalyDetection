"""
Helper functions for the Anomaly Detection Dashboard.
Provides utility functions that don't fit into other categories.
"""

import random
import string
import json
import datetime
import pandas as pd

def generate_id(prefix="", length=8):
    """Generate a random ID with optional prefix.
    
    Args:
        prefix (str, optional): Prefix for the ID. Defaults to "".
        length (int, optional): Length of the random part. Defaults to 8.
    
    Returns:
        str: Generated ID.
    """
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choice(chars) for _ in range(length))
    
    if prefix:
        return f"{prefix}-{random_part}"
    return random_part

def format_datetime(dt, format_str="%Y-%m-%d %H:%M:%S"):
    """Format a datetime object or string.
    
    Args:
        dt (datetime or str): Datetime to format.
        format_str (str, optional): Format string. Defaults to "%Y-%m-%d %H:%M:%S".
    
    Returns:
        str: Formatted datetime string.
    """
    if isinstance(dt, str):
        try:
            dt = pd.to_datetime(dt)
        except:
            return dt
    
    if isinstance(dt, (datetime.datetime, pd.Timestamp)):
        return dt.strftime(format_str)
    
    return str(dt)

def format_timestamp_relative(timestamp):
    """Format a timestamp as a relative time (e.g., "2 hours ago").
    
    Args:
        timestamp (str or datetime): Timestamp to format.
    
    Returns:
        str: Relative time string.
    """
    if isinstance(timestamp, str):
        timestamp = pd.to_datetime(timestamp)
    
    now = datetime.datetime.now()
    
    if not isinstance(timestamp, (datetime.datetime, pd.Timestamp)):
        return "Unknown time"
    
    diff = now - timestamp
    
    # Convert to total seconds
    diff_seconds = int(diff.total_seconds())
    
    if diff_seconds < 60:
        return "just now" if diff_seconds < 10 else f"{diff_seconds} seconds ago"
    
    diff_minutes = diff_seconds // 60
    if diff_minutes < 60:
        return f"{diff_minutes} minute{'s' if diff_minutes > 1 else ''} ago"
    
    diff_hours = diff_minutes // 60
    if diff_hours < 24:
        return f"{diff_hours} hour{'s' if diff_hours > 1 else ''} ago"
    
    diff_days = diff_hours // 24
    if diff_days < 30:
        return f"{diff_days} day{'s' if diff_days > 1 else ''} ago"
    
    diff_months = diff_days // 30
    if diff_months < 12:
        return f"{diff_months} month{'s' if diff_months > 1 else ''} ago"
    
    diff_years = diff_months // 12
    return f"{diff_years} year{'s' if diff_years > 1 else ''} ago"

def safe_json_loads(json_str, default=None):
    """Safely load a JSON string.
    
    Args:
        json_str (str): JSON string to parse.
        default (any, optional): Default value if parsing fails. Defaults to None.
    
    Returns:
        any: Parsed JSON object or default value.
    """
    if not json_str:
        return default
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return default

def truncate_string(text, max_length=100, suffix="..."):
    """Truncate a string to a maximum length.
    
    Args:
        text (str): String to truncate.
        max_length (int, optional): Maximum length. Defaults to 100.
        suffix (str, optional): Suffix to add if truncated. Defaults to "...".
    
    Returns:
        str: Truncated string.
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def format_file_size(size_bytes):
    """Format a file size in bytes to a human-readable string.
    
    Args:
        size_bytes (int): File size in bytes.
    
    Returns:
        str: Formatted file size.
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    
    # Convert to kilobytes
    size_kb = size_bytes / 1024
    if size_kb < 1024:
        return f"{size_kb:.1f} KB"
    
    # Convert to megabytes
    size_mb = size_kb / 1024
    if size_mb < 1024:
        return f"{size_mb:.1f} MB"
    
    # Convert to gigabytes
    size_gb = size_mb / 1024
    return f"{size_gb:.2f} GB"

def get_severity_color(severity):
    """Get the color associated with a severity level.
    
    Args:
        severity (str): Severity level (High, Medium, Low, etc.).
    
    Returns:
        str: Color hex code.
    """
    from config.theme import get_current_theme
    
    current_theme = get_current_theme()
    
    severity_map = {
        "Critical": current_theme['error_color'],
        "High": current_theme['error_color'],
        "Medium": current_theme['warning_color'],
        "Low": current_theme['success_color'],
    }
    
    return severity_map.get(severity, current_theme['primary_color'])

def format_config_dict(config_dict):
    """Format a configuration dictionary in a readable way.
    
    Args:
        config_dict (dict): Configuration dictionary.
    
    Returns:
        str: Formatted configuration string.
    """
    if not config_dict:
        return "No configuration"
    
    lines = []
    for key, value in config_dict.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for sub_key, sub_value in value.items():
                lines.append(f"  {sub_key}: {sub_value}")
        else:
            lines.append(f"{key}: {value}")
    
    return "\n".join(lines)

# Add these functions to a file like utils/ui_helpers.py or directly in your views module

def icon_card(icon, title, value, subtitle, color="#4361ee"):
    """Generate HTML for a styled card with an icon.
    
    Args:
        icon (str): Unicode emoji icon
        title (str): Card title
        value (str): Main value to display
        subtitle (str): Explanatory text
        color (str): Hex color code for the icon and value
    
    Returns:
        str: HTML string for the card
    """
    return f"""
    <div style="background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); height: 100%;">
        <div style="color: {color}; font-size: 2rem; margin-bottom: 0.5rem;">{icon}</div>
        <h3 style="margin: 0; color: #333;">{title}</h3>
        <h2 style="margin: 5px 0; color: {color};">{value}</h2>
        <div style="font-size: 0.8rem; opacity: 0.8;">{subtitle}</div>
    </div>
    """

def severity_badge(severity):
    """Generate HTML for a severity badge.
    
    Args:
        severity (str): Severity level ('High', 'Medium', 'Low', or any other value)
    
    Returns:
        str: HTML string for the severity badge
    """
    if severity == 'High':
        return f'<span style="background-color: rgba(230, 57, 70, 0.2); color: #e63946; font-weight: bold; padding: 2px 8px; border-radius: 4px;">High</span>'
    elif severity == 'Medium':
        return f'<span style="background-color: rgba(244, 162, 97, 0.2); color: #f4a261; font-weight: bold; padding: 2px 8px; border-radius: 4px;">Medium</span>'
    elif severity == 'Low':
        return f'<span style="background-color: rgba(42, 157, 143, 0.2); color: #2a9d8f; font-weight: bold; padding: 2px 8px; border-radius: 4px;">Low</span>'
    else:
        return f'<span style="background-color: rgba(128, 128, 128, 0.2); color: #666; font-weight: bold; padding: 2px 8px; border-radius: 4px;">{severity}</span>'

def info_card(title, content, icon="ℹ️", bg_color="#f8f9fa", border_color="#4361ee"):
    """Generate HTML for an information card.
    
    Args:
        title (str): Card title
        content (str): Main content
        icon (str): Unicode emoji icon
        bg_color (str): Background color
        border_color (str): Border color
    
    Returns:
        str: HTML string for the info card
    """
    return f"""
    <div style="background-color: {bg_color}; padding: 15px; border-radius: 8px; margin: 10px 0; 
              border-left: 4px solid {border_color};">
        <div style="display: flex; align-items: center; margin-bottom: 8px;">
            <div style="font-size: 1.2rem; margin-right: 8px;">{icon}</div>
            <div style="font-size: 1.1rem; font-weight: 600;">{title}</div>
        </div>
        <div style="margin-left: 30px;">{content}</div>
    </div>
    """

def action_button(label, icon, help_text=""):
    """Generate HTML for a styled action button.
    
    Args:
        label (str): Button text
        icon (str): Unicode emoji icon
        help_text (str): Tooltip text
    
    Returns:
        str: HTML string for the button
    """
    return f"""
    <button class="action-button" title="{help_text}">
        <span style="margin-right: 5px;">{icon}</span> {label}
    </button>
    """
    # Note: This button is just HTML and won't function without JavaScript
    # For functional buttons, use Streamlit's native st.button()

def create_metrics_row(metrics):
    """Create a row of metric cards.
    
    Args:
        metrics (list): List of dictionaries with keys 'label', 'value', 'delta', 'icon'
    
    Returns:
        None: Displays metrics directly using st.metric
    """
    import streamlit as st
    
    # Calculate column width based on number of metrics
    cols = st.columns(len(metrics))
    
    # Display each metric in its column
    for i, metric in enumerate(metrics):
        with cols[i]:
            st.metric(
                label=f"{metric.get('icon', '')} {metric['label']}", 
                value=metric['value'],
                delta=metric.get('delta', None)
            )