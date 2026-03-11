"""
Views module for the Anomaly Detection Dashboard.
"""

from .dashboard import render as dashboard_render
from .anomalies import render as anomalies_render
from .models import render as models_render
from .agent_viz import render as agent_viz_render, render_animation_controls
from .system_status import render as system_status_render
from .settings_view import render as settings_view_render

# Re-export for convenience
dashboard = dashboard_render
anomalies = anomalies_render
models = models_render
agent_viz = agent_viz_render
system_status = system_status_render
settings_view = settings_view_render

__all__ = [
    'dashboard',
    'anomalies',
    'models',
    'agent_viz',
    'system_status',
    'settings_view',
    'render_animation_controls'
]