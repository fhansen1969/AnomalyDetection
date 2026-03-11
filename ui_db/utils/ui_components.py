"""
UI component utilities for the Anomaly Detection Dashboard.
Provides custom UI components and styling.
"""

import streamlit as st
import time
from config.theme import get_current_theme

def card(title, content, description=None, icon=None, theme=None, color=None):
    """Render a card component with title, content, and optional icon.
    
    Args:
        title (str): Card title
        content (str): Main content/value to display
        description (str, optional): Additional description text. Defaults to None.
        icon (str, optional): Icon name from Material Icons. Defaults to None.
        theme (str, optional): Color theme. Defaults to None.
        color (str, optional): Specific color override. Defaults to None.
    """
    # Determine theme colors
    if theme is None:
        theme = get_current_theme()
    
    # Set color based on theme or override
    if color == "danger":
        bg_color = "rgba(255, 94, 94, 0.2)"
        border_color = "rgba(255, 94, 94, 0.5)"
        icon_color = "#FF5E5E"
        title_color = "#FF5E5E"
    elif color == "warning":
        bg_color = "rgba(255, 170, 94, 0.2)"
        border_color = "rgba(255, 170, 94, 0.5)"
        icon_color = "#FFAA5E"
        title_color = "#FFAA5E"
    elif color == "success":
        bg_color = "rgba(94, 255, 121, 0.2)"
        border_color = "rgba(94, 255, 121, 0.5)"
        icon_color = "#5EFF79"
        title_color = "#5EFF79"
    else:  # Default to primary/theme color
        if isinstance(theme, dict):
            # If theme is already a dictionary (from get_current_theme())
            bg_color = f"{theme.get('primary_color', '#4361ee')}20"
            border_color = f"{theme.get('primary_color', '#4361ee')}50"
            icon_color = theme.get('primary_color', '#4361ee')
            title_color = theme.get('primary_color', '#4361ee')
        elif theme == "dark":
            bg_color = "rgba(94, 201, 255, 0.1)"
            border_color = "rgba(94, 201, 255, 0.3)"
            icon_color = "#5EC9FF"
            title_color = "#5EC9FF"
        else:
            bg_color = "rgba(94, 201, 255, 0.1)"
            border_color = "rgba(94, 201, 255, 0.3)"
            icon_color = "#4361ee"  # Your app's primary color
            title_color = "#4361ee"
    
    # Define card styles
    card_style = f"""
        padding: 1.2rem;
        border-radius: 0.5rem;
        background-color: {bg_color};
        border: 1px solid {border_color};
        margin-bottom: 1rem;
    """
    
    # Map Material Icons to emoji equivalents for fallback
    icon_map = {
        'alert-triangle': '⚠️',
        'alert-octagon': '🛑',
        'calendar': '📅',
        'activity': '📈',
        'bar-chart': '📊',
        'check-circle': '✅',
        'clock': '⏰',
        'alert-circle': '⚠️',
        'database': '🗄️',
        'code': '💻',
        'settings': '⚙️',
        'users': '👥',
        'shield': '🛡️',
        'git-branch': '🔀',
        'trending-up': '📈',
        'trending-down': '📉',
        'eye': '👁️',
        'zap': '⚡',
        'flag': '🚩',
        'file': '📄',
        'file-text': '📝',
        'cloud': '☁️',
        'cloud-rain': '🌧️',
        'inbox': '📥',
        'grid': '🔲',
        'heart': '❤️',
        'star': '⭐',
        'thumbs-up': '👍',
        'thumbs-down': '👎',
        'search': '🔍',
        'lock': '🔒',
        'key': '🔑',
        'bell': '🔔',
        'cpu': '🖥️',
        'server': '🖥️',
        'link': '🔗',
        'package': '📦',
        'map': '🗺️',
        'mail': '📧'
    }
    
    # Use emoji or Material Icon based on preference
    use_emoji = True  # Set to True to use emoji icons, False to try Material Icons
    
    # Generate HTML with proper Material Icons format or emoji fallback
    html = f"""
    <div style="{card_style}">
    """
    
    # Add icon if provided
    if icon:
        if use_emoji:
            # Use emoji icon instead of Material Icons
            emoji_icon = icon_map.get(icon, '📊')  # Default to chart emoji if not found
            icon_style = f"""
                color: {icon_color};
                font-size: 2rem;
                margin-bottom: 0.5rem;
                display: block;
            """
            html += f"""
            <div style="{icon_style}">{emoji_icon}</div>
            """
        else:
            # Try using Material Icons (may not work if font is not loaded)
            icon_style = f"""
                color: {icon_color};
                font-size: 2rem;
                margin-bottom: 0.5rem;
                display: block;
            """
            html += f"""
            <span class="material-icons" style="{icon_style}">{icon}</span>
            """
    
    # Add title
    title_style = f"""
        color: {title_color};
        font-size: 0.9rem;
        font-weight: 500;
        margin-bottom: 0.2rem;
    """
    html += f"""
    <div style="{title_style}">{title}</div>
    """
    
    # Add content
    content_style = """
        font-size: 1.8rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    """
    html += f"""
    <div style="{content_style}">{content}</div>
    """
    
    # Add description if provided
    if description:
        description_style = """
            font-size: 0.8rem;
            opacity: 0.8;
        """
        html += f"""
        <div style="{description_style}">{description}</div>
        """
    
    # Close the card div
    html += """
    </div>
    """
    
    # Render the card
    st.markdown(html, unsafe_allow_html=True)

def emoji_card(title, content, description=None, icon=None, theme=None, color=None):
    """Alternative card function that always uses emoji icons.
    
    Args:
        title (str): Card title
        content (str): Main content/value to display
        description (str, optional): Additional description text. Defaults to None.
        icon (str, optional): Icon name (will be converted to emoji). Defaults to None.
        theme (str, optional): Color theme. Defaults to None.
        color (str, optional): Specific color override. Defaults to None.
    """
    # Determine theme colors
    if theme is None:
        theme = get_current_theme()
    
    # Set default colors
    if isinstance(theme, dict):
        primary_color = theme.get('primary_color', '#4361ee')
    else:
        primary_color = '#4361ee'
    
    # Set color based on theme or override
    if color == "danger":
        icon_color = "#FF5E5E"
    elif color == "warning":
        icon_color = "#FFAA5E"
    elif color == "success":
        icon_color = "#5EFF79"
    else:
        icon_color = primary_color
    
    # Map Material Icons to emoji equivalents
    icon_map = {
        'alert-triangle': '⚠️',
        'alert-octagon': '🛑',
        'calendar': '📅',
        'activity': '📈',
        'bar-chart': '📊',
        'check-circle': '✅',
        'clock': '⏰',
        'alert-circle': '⚠️',
        'database': '🗄️',
        'code': '💻',
        'settings': '⚙️',
        'users': '👥',
        'shield': '🛡️',
        'git-branch': '🔀',
        'trending-up': '📈',
        'trending-down': '📉',
        'eye': '👁️',
        'zap': '⚡',
        'flag': '🚩',
        'file': '📄',
        'file-text': '📝',
        'cloud': '☁️',
        'cloud-rain': '🌧️',
        'inbox': '📥',
        'grid': '🔲',
        'heart': '❤️',
        'star': '⭐',
        'thumbs-up': '👍',
        'thumbs-down': '👎',
        'search': '🔍',
        'lock': '🔒',
        'key': '🔑',
        'bell': '🔔',
        'cpu': '🖥️',
        'server': '🖥️',
        'link': '🔗',
        'package': '📦',
        'map': '🗺️',
        'mail': '📧'
    }
    
    # Convert icon to emoji
    emoji_icon = icon_map.get(icon, '📊') if icon else '📊'
    
    # Generate clean, simple HTML
    html = f"""
    <div style="background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); height: 100%;">
        <div style="color: {icon_color}; font-size: 2rem; margin-bottom: 0.5rem;">{emoji_icon}</div>
        <h3 style="margin: 0; color: #333;">{title}</h3>
        <h2 style="margin: 5px 0; color: {icon_color};">{content}</h2>
        {f'<div style="font-size: 0.8rem; opacity: 0.8;">{description}</div>' if description else ''}
    </div>
    """
    
    # Render the card
    st.markdown(html, unsafe_allow_html=True)
                
def create_metric_card(title=None, value=None, delta=None, description=None, label=None, prefix="", suffix="", precision=0, icon=None, color=None, change=None, **kwargs):
    """Create a metric card with value and optional delta.
    
    Args:
        title (str, optional): Metric title. Defaults to None.
        value (float, optional): Metric value. Defaults to None.
        delta (float, optional): Delta value. Defaults to None.
        description (str, optional): Additional description. Defaults to None.
        label (str, optional): Alternative to title for compatibility. Defaults to None.
        prefix (str, optional): Value prefix (e.g., "$"). Defaults to "".
        suffix (str, optional): Value suffix (e.g., "%"). Defaults to "".
        precision (int, optional): Decimal precision for value. Defaults to 0.
        icon (str, optional): Material icon name. Defaults to None.
        color (str, optional): Color override for the card. Defaults to None.
        change (float, optional): Alternative to delta for compatibility. Defaults to None.
        **kwargs: Additional parameters for future compatibility.
    """
    # Use label as title if title is not provided
    if title is None and label is not None:
        title = label
    
    # Use change as delta if delta is not provided
    if delta is None and change is not None:
        delta = change
    
    # Format value based on precision
    if value is not None:
        if isinstance(value, (int, float)):
            formatted_value = f"{prefix}{value:.{precision}f}{suffix}"
        else:
            formatted_value = f"{prefix}{value}{suffix}"
    else:
        formatted_value = "N/A"
    
    # Set up colors based on delta
    if delta is not None and isinstance(delta, (int, float)):
        if delta > 0:
            delta_color = "green"
            delta_sign = "+"
        elif delta < 0:
            delta_color = "red"
            delta_sign = ""  # Negative sign is already included in the number
        else:
            delta_color = "gray"
            delta_sign = ""
    else:
        delta_color = "gray"
        delta_sign = ""
    
    # Create column for metric
    if delta is not None:
        # Format delta
        if isinstance(delta, (int, float)):
            delta_text = f"{delta_sign}{delta:.{precision}f}{suffix}"
            
            # Use streamlit's built-in metric
            st.metric(
                label=title,
                value=formatted_value,
                delta=delta_text,
                help=description
            )
        else:
            # Handle non-numeric delta
            st.metric(
                label=title,
                value=formatted_value,
                delta=delta,
                help=description
            )
    else:
        # If no delta, use a simple metric without delta indicator
        st.metric(
            label=title,
            value=formatted_value,
            help=description
        )

def progress_bar(value, min_value=0, max_value=100, label=None, help_text=None, color=None, theme=None):
    """Create a styled progress bar.
    
    Args:
        value (float or str): Current value
        min_value (float, optional): Minimum value. Defaults to 0.
        max_value (float, optional): Maximum value. Defaults to 100.
        label (str, optional): Label text. Defaults to None.
        help_text (str, optional): Help text on hover. Defaults to None.
        color (str, optional): Color override. Defaults to None.
        theme (str, optional): Theme name. Defaults to None.
        
    Returns:
        str: HTML for the progress bar
    """
    # Determine theme colors
    if theme is None:
        try:
            theme = get_current_theme()
        except:
            # Fallback if get_current_theme is not available
            theme = {"primary_color": "#4361ee", "secondary_color": "#3a0ca3"}
    
    # Convert string values to float if needed
    try:
        if isinstance(value, str):
            # Try to extract the first number from the string
            import re
            numbers = re.findall(r'\d+\.?\d*', value)
            if numbers:
                value = float(numbers[0])
            else:
                value = 0
        
        # Ensure min_value and max_value are also numeric
        if isinstance(min_value, str):
            min_value = float(re.findall(r'\d+\.?\d*', min_value)[0]) if re.findall(r'\d+\.?\d*', min_value) else 0
            
        if isinstance(max_value, str):
            max_value = float(re.findall(r'\d+\.?\d*', max_value)[0]) if re.findall(r'\d+\.?\d*', max_value) else 100
            
        # Normalize value between 0 and 100
        if max_value > min_value:
            normalized_value = max(0, min(100, ((value - min_value) / (max_value - min_value)) * 100))
        else:
            normalized_value = 50  # Default to 50% if min and max are equal or inverted
    except:
        # If any conversion fails, default to 50%
        normalized_value = 50
    
    # Set color based on value or override
    if color:
        bar_color = color
    else:
        # If theme is a dictionary
        if isinstance(theme, dict):
            if normalized_value < 30:
                bar_color = theme.get("error_color", "#FF5E5E")  # Red for low values
            elif normalized_value < 70:
                bar_color = theme.get("warning_color", "#FFAA5E")  # Orange for medium values
            else:
                bar_color = theme.get("success_color", "#4CAF50")  # Green for high values
        else:
            # Calculate color based on value (red to green gradient)
            if normalized_value < 30:
                bar_color = "#FF5E5E"  # Red for low values
            elif normalized_value < 70:
                bar_color = "#FFAA5E"  # Orange for medium values
            else:
                bar_color = "#4CAF50"  # Green for high values
    
    # Create HTML for the progress bar
    container_style = """
        width: 100%;
        background-color: rgba(0, 0, 0, 0.1);
        border-radius: 5px;
        height: 8px;
        margin: 5px 0 15px 0;
    """
    
    bar_style = f"""
        width: {normalized_value}%;
        background-image: linear-gradient(to right, {bar_color}, {bar_color});
        height: 100%;
        border-radius: 5px;
        transition: width 0.5s ease;
    """
    
    html = f"""
    <div style="{container_style}">
        <div style="{bar_style}"></div>
    </div>
    """
    
    # Add label if provided
    if label:
        label_html = f"""
        <div style="font-size: 0.9rem; font-weight: 500; margin-bottom: 5px;">{label}</div>
        """
        html = label_html + html
    
    # Add help text if provided
    if help_text:
        help_html = f"""
        <div style="font-size: 0.8rem; opacity: 0.7; margin-top: -10px;">{help_text}</div>
        """
        html = html + help_html
    
    return html

def loading_animation(text="Loading...", key=None, spinner_type="dots"):
    """Display a loading animation with customizable text.
    
    Args:
        text (str, optional): Text to display with spinner. Defaults to "Loading...".
        key (str, optional): Unique key for the component. Defaults to None.
        spinner_type (str, optional): Type of spinner animation. Defaults to "dots".
            Options: "dots", "circle", "grow", "bounce", "pulse"
    
    Returns:
        container: Streamlit container with the spinner
    """
    # Generate a random key if none provided
    if key is None:
        key = f"spinner_{time.time()}"
    
    # Determine spinner HTML based on type
    if spinner_type == "circle":
        spinner_html = """
        <style>
        .circle-spinner {{
            width: 40px;
            height: 40px;
            border: 4px solid rgba(94, 201, 255, 0.2);
            border-top: 4px solid #5EC9FF;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 10px auto;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        .spinner-container {{
            text-align: center;
            padding: 10px;
        }}
        .spinner-text {{
            margin-top: 10px;
            font-size: 14px;
            color: #888;
        }}
        </style>
        <div class="spinner-container">
            <div class="circle-spinner"></div>
            <div class="spinner-text">{0}</div>
        </div>
        """
    elif spinner_type == "grow":
        spinner_html = """
        <style>
        .grow-spinner {{
            width: 40px;
            height: 40px;
            background-color: #5EC9FF;
            border-radius: 50%;
            margin: 10px auto;
            animation: grow 1.2s ease-in-out infinite;
        }}
        @keyframes grow {{
            0%, 100% {{ transform: scale(0.0); opacity: 0; }}
            50% {{ transform: scale(1.0); opacity: 1; }}
        }}
        .spinner-container {{
            text-align: center;
            padding: 10px;
        }}
        .spinner-text {{
            margin-top: 10px;
            font-size: 14px;
            color: #888;
        }}
        </style>
        <div class="spinner-container">
            <div class="grow-spinner"></div>
            <div class="spinner-text">{0}</div>
        </div>
        """
    elif spinner_type == "bounce":
        spinner_html = """
        <style>
        .bounce-spinner {{
            display: flex;
            justify-content: center;
            align-items: center;
            margin: 10px auto;
        }}
        .bounce-dot {{
            width: 10px;
            height: 10px;
            margin: 0 5px;
            background-color: #5EC9FF;
            border-radius: 50%;
            display: inline-block;
            animation: bounce 1.4s infinite ease-in-out both;
        }}
        .bounce-dot:nth-child(1) {{ animation-delay: -0.32s; }}
        .bounce-dot:nth-child(2) {{ animation-delay: -0.16s; }}
        @keyframes bounce {{
            0%, 80%, 100% {{ transform: scale(0); }}
            40% {{ transform: scale(1.0); }}
        }}
        .spinner-container {{
            text-align: center;
            padding: 10px;
        }}
        .spinner-text {{
            margin-top: 10px;
            font-size: 14px;
            color: #888;
        }}
        </style>
        <div class="spinner-container">
            <div class="bounce-spinner">
                <div class="bounce-dot"></div>
                <div class="bounce-dot"></div>
                <div class="bounce-dot"></div>
            </div>
            <div class="spinner-text">{0}</div>
        </div>
        """
    elif spinner_type == "pulse":
        spinner_html = """
        <style>
        .pulse-spinner {{
            width: 40px;
            height: 40px;
            margin: 10px auto;
            border-radius: 50%;
            background-color: #5EC9FF;
            animation: pulse 1.2s infinite cubic-bezier(0.215, 0.61, 0.355, 1);
        }}
        @keyframes pulse {{
            0% {{
                transform: scale(0.95);
                box-shadow: 0 0 0 0 rgba(94, 201, 255, 0.7);
            }}
            70% {{
                transform: scale(1);
                box-shadow: 0 0 0 10px rgba(94, 201, 255, 0);
            }}
            100% {{
                transform: scale(0.95);
                box-shadow: 0 0 0 0 rgba(94, 201, 255, 0);
            }}
        }}
        .spinner-container {{
            text-align: center;
            padding: 10px;
        }}
        .spinner-text {{
            margin-top: 10px;
            font-size: 14px;
            color: #888;
        }}
        </style>
        <div class="spinner-container">
            <div class="pulse-spinner"></div>
            <div class="spinner-text">{0}</div>
        </div>
        """
    else:  # Default to dots spinner
        spinner_html = """
        <style>
        .dots-spinner {{
            display: flex;
            justify-content: center;
            align-items: center;
            margin: 10px auto;
        }}
        .dots-spinner-dot {{
            width: 10px;
            height: 10px;
            background-color: #5EC9FF;
            border-radius: 50%;
            margin: 0 5px;
            animation: dots 1.4s infinite;
        }}
        .dots-spinner-dot:nth-child(1) {{ animation-delay: 0s; }}
        .dots-spinner-dot:nth-child(2) {{ animation-delay: 0.2s; }}
        .dots-spinner-dot:nth-child(3) {{ animation-delay: 0.4s; }}
        @keyframes dots {{
            0%, 100% {{ opacity: 0; }}
            50% {{ opacity: 1; }}
        }}
        .spinner-container {{
            text-align: center;
            padding: 10px;
        }}
        .spinner-text {{
            margin-top: 10px;
            font-size: 14px;
            color: #888;
        }}
        </style>
        <div class="spinner-container">
            <div class="dots-spinner">
                <div class="dots-spinner-dot"></div>
                <div class="dots-spinner-dot"></div>
                <div class="dots-spinner-dot"></div>
            </div>
            <div class="spinner-text">{0}</div>
        </div>
        """
    
    # Create a container for the spinner
    container = st.empty()
    
    # Display the spinner with the text
    container.markdown(spinner_html.format(text), unsafe_allow_html=True)
    
    return container

def status_badge(status):
    """Render a status badge.
    
    Args:
        status (str): Status value
    """
    # Define colors for different statuses
    status_colors = {
        "active": ("#4CAF50", "#E8F5E9"),  # Green
        "inactive": ("#9E9E9E", "#F5F5F5"),  # Gray
        "new": ("#2196F3", "#E3F2FD"),  # Blue
        "investigating": ("#FF9800", "#FFF3E0"),  # Orange
        "resolved": ("#4CAF50", "#E8F5E9"),  # Green
        "false_positive": ("#9E9E9E", "#F5F5F5"),  # Gray
        "error": ("#F44336", "#FFEBEE"),  # Red
        "trained": ("#4CAF50", "#E8F5E9"),  # Green
        "not_trained": ("#9E9E9E", "#F5F5F5"),  # Gray
        "in_training": ("#FF9800", "#FFF3E0"),  # Orange
    }
    
    # Get colors for status (default to gray if not found)
    status_lower = status.lower()
    text_color, bg_color = status_colors.get(
        status_lower, 
        ("#9E9E9E", "#F5F5F5")  # Default gray
    )
    
    # Define badge style
    badge_style = f"""
        display: inline-block;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-size: 0.75rem;
        font-weight: 500;
        text-transform: uppercase;
        background-color: {bg_color};
        color: {text_color};
    """
    
    # Render badge with HTML
    html = f"""
    <span style="{badge_style}">
        {status}
    </span>
    """
    
    return html

def severity_badge(severity):
    """Render a severity badge.
    
    Args:
        severity (str): Severity value
    """
    # Define colors for different severities
    severity_colors = {
        "critical": ("#F44336", "#FFEBEE"),  # Red
        "high": ("#FF9800", "#FFF3E0"),  # Orange
        "medium": ("#FFD700", "#FFFDE7"),  # Yellow
        "low": ("#2196F3", "#E3F2FD"),  # Blue
        "unknown": ("#9E9E9E", "#F5F5F5"),  # Gray
    }
    
    # Get colors for severity (default to gray if not found)
    severity_lower = severity.lower()
    text_color, bg_color = severity_colors.get(
        severity_lower, 
        ("#9E9E9E", "#F5F5F5")  # Default gray
    )
    
    # Define badge style
    badge_style = f"""
        display: inline-block;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-size: 0.75rem;
        font-weight: 500;
        text-transform: uppercase;
        background-color: {bg_color};
        color: {text_color};
    """
    
    # Render badge with HTML
    html = f"""
    <span style="{badge_style}">
        {severity}
    </span>
    """
    
    return html

def safe_display_chart(chart, use_container_width=True):
    """Safely display an Altair chart, handling NumPy serialization issues.
    
    Args:
        chart: An Altair chart object
        use_container_width: Whether to use the full container width
        
    Returns:
        The Streamlit chart component
    """
    import streamlit as st
    import json
    import altair as alt
    
    # Custom JSON serializer to handle NumPy types
    def serialize_numpy_data(obj):
        import numpy as np
        from datetime import datetime
        import pandas as pd
        
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