"""
Theme configuration and styling for the Anomaly Detection Dashboard.
Provides functions for handling color themes, CSS generation, and theme-related utilities.
"""

import streamlit as st

# Theme configuration
THEME = {
    'light': {
        'bg_color': '#ffffff',
        'text_color': '#333333',
        'primary_color': '#4361ee',
        'secondary_color': '#3a0ca3',
        'accent_color': '#4cc9f0',
        'success_color': '#4CAF50',
        'warning_color': '#ff9100',
        'error_color': '#f44336',
        'card_bg': '#f8f9fa',
        'sidebar_bg': '#f8f9fa',
        'chart_palette': ['#4361ee', '#3a0ca3', '#4cc9f0', '#f72585', '#7209b7']
    },
    'dark': {
        'bg_color': '#1a1a2e',
        'text_color': '#e6e6e6',
        'primary_color': '#4361ee',
        'secondary_color': '#3a0ca3',
        'accent_color': '#4cc9f0',
        'success_color': '#4CAF50',
        'warning_color': '#ff9100',
        'error_color': '#f44336',
        'card_bg': '#16213e',
        'sidebar_bg': '#0f3460',
        'chart_palette': ['#4361ee', '#3a0ca3', '#4cc9f0', '#f72585', '#7209b7']
    }
}

def get_current_theme():
    """Get the current theme settings based on session state."""
    return THEME[st.session_state.theme]

def hex_to_rgba(hex_color, alpha=1.0):
    """Convert hex color to rgba format that Plotly accepts."""
    # Remove '#' if present
    hex_color = hex_color.lstrip('#')
    
    # Parse the hex values
    if len(hex_color) == 6:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    elif len(hex_color) == 3:
        r, g, b = int(hex_color[0] * 2, 16), int(hex_color[1] * 2, 16), int(hex_color[2] * 2, 16)
    else:
        # Default to light gray if invalid format
        r, g, b = 200, 200, 200
    
    # Return rgba string
    return f"rgba({r}, {g}, {b}, {alpha})"

def get_custom_css():
    """Generate the custom CSS based on the current theme."""
    current_theme = get_current_theme()
    
    return f"""
    <style>
        /* Base styles */
        body {{
            color: {current_theme['text_color']};
            background-color: {current_theme['bg_color']};
            transition: all 0.5s ease;
        }}
        
        /* Headers */
        .main-header {{
            font-size: 2.8rem !important;
            font-weight: 700 !important;
            color: {current_theme['primary_color']} !important;
            text-align: center !important;
            margin-bottom: 1.5rem !important;
            text-shadow: 0px 2px 4px rgba(0,0,0,0.1);
            background: linear-gradient(90deg, {current_theme['primary_color']}, {current_theme['secondary_color']});
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: glow 2s ease-in-out infinite alternate;
        }}
        
        @keyframes glow {{
            from {{
                text-shadow: 0 0 5px rgba(67, 97, 238, 0.3);
            }}
            to {{
                text-shadow: 0 0 15px rgba(67, 97, 238, 0.5);
            }}
        }}
        
        .sub-header {{
            font-size: 1.8rem !important;
            font-weight: 600 !important;
            color: {current_theme['secondary_color']} !important;
            margin-top: 1.5rem !important;
            margin-bottom: 1rem !important;
            border-left: 4px solid {current_theme['primary_color']};
            padding-left: 10px;
        }}
        
        /* Cards */
        .metric-card {{
            background-color: {current_theme['card_bg']};
            border-radius: 1rem;
            padding: 1.5rem;
            box-shadow: 0 10px 20px rgba(0,0,0,0.08);
            margin: 0.8rem 0;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            border-top: 4px solid {current_theme['primary_color']};
            animation: fadeIn 0.5s ease-out;
            height: 100%;
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .metric-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 15px 30px rgba(0,0,0,0.12);
        }}
        
        .metric-label {{
            font-size: 1rem;
            font-weight: 700;
            color: {current_theme['text_color']}aa;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .metric-value {{
            font-size: 2.5rem;
            font-weight: 700;
            color: {current_theme['primary_color']};
            display: flex;
            align-items: center;
            justify-content: center;
            margin-top: 0.5rem;
        }}
        
        .metric-icon {{
            margin-right: 0.5rem;
            font-size: 1.8rem;
        }}
        
        /* Anomaly cards */
        .anomaly-high {{
            background-color: {current_theme['error_color']}22;
            border-left: 4px solid {current_theme['error_color']};
            padding: 16px;
            border-radius: 8px;
            margin: 8px 0;
            transition: all 0.3s ease;
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0% {{ box-shadow: 0 0 0 0 {current_theme['error_color']}60; }}
            70% {{ box-shadow: 0 0 0 10px {current_theme['error_color']}00; }}
            100% {{ box-shadow: 0 0 0 0 {current_theme['error_color']}00; }}
        }}
        
        .anomaly-medium {{
            background-color: {current_theme['warning_color']}22;
            border-left: 4px solid {current_theme['warning_color']};
            padding: 16px;
            border-radius: 8px;
            margin: 8px 0;
            transition: all 0.3s ease;
        }}
        
        .anomaly-low {{
            background-color: {current_theme['success_color']}22;
            border-left: 4px solid {current_theme['success_color']};
            padding: 16px;
            border-radius: 8px;
            margin: 8px 0;
            transition: all 0.3s ease;
        }}
        
        /* Agent cards */
        .agent-active {{
            background-color: {current_theme['accent_color']}22;
            border: 2px solid {current_theme['accent_color']};
            border-radius: 1rem;
            padding: 1rem;
            transition: all 0.3s ease;
            box-shadow: 0 0 15px {current_theme['accent_color']}50;
            animation: pulseAgent 1.5s infinite;
        }}
        
        @keyframes pulseAgent {{
            0% {{ box-shadow: 0 0 0 0 {current_theme['accent_color']}60; }}
            70% {{ box-shadow: 0 0 10px 5px {current_theme['accent_color']}30; }}
            100% {{ box-shadow: 0 0 0 0 {current_theme['accent_color']}00; }}
        }}
        
        /* Tabs styling */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 3px;
            padding: 0 10px;
            background-color: {current_theme['card_bg']};
            border-radius: 10px 10px 0 0;
            border-bottom: 2px solid {current_theme['primary_color']}30;
        }}
        
        .stTabs [data-baseweb="tab"] {{
            height: 50px;
            white-space: pre-wrap;
            background-color: {current_theme['card_bg']};
            border-radius: 10px 10px 0 0;
            gap: 1px;
            padding: 10px 20px;
            transition: all 0.3s ease;
        }}
        
        .stTabs [aria-selected="true"] {{
            background-color: {current_theme['primary_color']}20;
            border-bottom: 4px solid {current_theme['primary_color']};
            color: {current_theme['primary_color']};
            font-weight: bold;
        }}
        
        /* Models */
        .model-card {{
            padding: 1.5rem; 
            border-radius: 1rem; 
            margin: 1rem 0; 
            border: 1px solid {current_theme['primary_color']}30; 
            box-shadow: 0 10px 20px rgba(0,0,0,0.08);
            background-color: {current_theme['card_bg']};
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            height: 100%;
        }}
        
        .model-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 15px 30px rgba(0,0,0,0.12);
        }}
        
        /* Agent messages */
        .agent-message {{
            padding: 15px;
            border-radius: 10px;
            margin: 10px 0;
            background-color: {current_theme['card_bg']};
            border-left: 4px solid {current_theme['primary_color']};
            box-shadow: 0 4px 8px rgba(0,0,0,0.05);
            animation: slideIn 0.3s ease-out;
        }}
        
        @keyframes slideIn {{
            from {{ opacity: 0; transform: translateX(-20px); }}
            to {{ opacity: 1; transform: translateX(0); }}
        }}
        
        /* Sidebar */
        .sidebar .sidebar-content {{
            background-color: {current_theme['sidebar_bg']};
            background-image: linear-gradient(135deg, {current_theme['primary_color']}20, {current_theme['secondary_color']}10);
        }}
        
        /* Animations */
        @keyframes float {{
            0% {{ transform: translateY(0px); }}
            50% {{ transform: translateY(-10px); }}
            100% {{ transform: translateY(0px); }}
        }}
        
        .float-animation {{
            animation: float 3s ease-in-out infinite;
        }}
        
        /* Progress bars */
        .progress-container {{
            width: 100%;
            background-color: {current_theme['card_bg']};
            border-radius: 10px;
            padding: 3px;
            box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);
            margin: 10px 0;
        }}
        
        .progress-bar {{
            height: 20px;
            border-radius: 8px;
            background-image: linear-gradient(to right, {current_theme['primary_color']}, {current_theme['secondary_color']});
            text-align: center;
            line-height: 20px;
            color: white;
            font-weight: bold;
            transition: width 0.5s ease;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            animation: progressAnimation 1s ease-out;
        }}
        
        @keyframes progressAnimation {{
            0% {{ width: 5%; }}
            100% {{ width: var(--width); }}
        }}
        
        /* Buttons */
        div.stButton > button:first-child {{
            background-color: {current_theme['primary_color']};
            color: white;
            border: none;
            border-radius: 5px;
            padding: 10px 20px;
            font-weight: bold;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            transition: all 0.3s ease;
        }}
        
        div.stButton > button:hover {{
            background-color: {current_theme['secondary_color']};
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
            transform: translateY(-2px);
        }}
        
        /* Notification */
        .notification {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background-color: {current_theme['primary_color']};
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
            z-index: 9999;
            animation: slideInRight 0.5s ease-out, fadeOut 0.5s ease-in 2.5s forwards;
            display: flex;
            align-items: center;
        }}
        
        @keyframes slideInRight {{
            from {{ transform: translateX(300px); opacity: 0; }}
            to {{ transform: translateX(0); opacity: 1; }}
        }}
        
        @keyframes fadeOut {{
            from {{ opacity: 1; }}
            to {{ opacity: 0; visibility: hidden; }}
        }}
        
        /* Loading animation */
        .loading-animation {{
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100px;
        }}
        
        .loading-dot {{
            width: 20px;
            height: 20px;
            background-color: {current_theme['primary_color']};
            border-radius: 50%;
            margin: 0 10px;
            animation: loadingAnimation 1.5s infinite ease-in-out;
        }}
        
        .loading-dot:nth-child(1) {{
            animation-delay: 0s;
        }}
        
        .loading-dot:nth-child(2) {{
            animation-delay: 0.3s;
        }}
        
        .loading-dot:nth-child(3) {{
            animation-delay: 0.6s;
        }}
        
        @keyframes loadingAnimation {{
            0%, 100% {{ transform: scale(1); opacity: 1; }}
            50% {{ transform: scale(1.5); opacity: 0.5; }}
        }}
        
        /* Dashboard specific styles */
        .data-card {{
            background-color: {current_theme['card_bg']};
            border-radius: 1rem;
            padding: 1.5rem;
            box-shadow: 0 10px 20px rgba(0,0,0,0.08);
            margin: 0.8rem 0;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            border-left: 4px solid {current_theme['primary_color']};
            height: 100%;
        }}
        
        /* Custom scrollbar */
        ::-webkit-scrollbar {{
            width: 10px;
            height: 10px;
        }}
        
        ::-webkit-scrollbar-track {{
            background: {current_theme['bg_color']}; 
            border-radius: 10px;
        }}
        
        ::-webkit-scrollbar-thumb {{
            background: {current_theme['primary_color']}80;
            border-radius: 10px;
        }}
        
        ::-webkit-scrollbar-thumb:hover {{
            background: {current_theme['primary_color']};
        }}
        
        /* Tooltip */
        .tooltip {{
            position: relative;
            display: inline-block;
        }}
        
        .tooltip .tooltiptext {{
            visibility: hidden;
            width: 200px;
            background-color: {current_theme['primary_color']};
            color: white;
            text-align: center;
            border-radius: 6px;
            padding: 10px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            margin-left: -100px;
            opacity: 0;
            transition: opacity 0.3s;
            font-size: 0.9rem;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }}
        
        .tooltip:hover .tooltiptext {{
            visibility: visible;
            opacity: 1;
        }}
    </style>
    """

def inject_custom_css():
    """Inject the custom CSS into the Streamlit app."""
    st.markdown(get_custom_css(), unsafe_allow_html=True)

def load_material_icons():
    """Load Material Icons font."""
    st.markdown("""
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    """, unsafe_allow_html=True)