"""
Chart components for the Anomaly Detection Dashboard.
Provides functions for creating various charts and visualizations.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
import calendar
import random

from services.data_service import get_time_series_data, get_anomalies
from config.theme import get_current_theme

def create_time_series_chart(data=None, days=30, height=400, show_legend=True):
    """
    Create a time series chart for anomaly detection data.
    
    Args:
        data (pd.DataFrame, optional): Time series data. If None, fetches from data service.
        days (int, optional): Number of days to include if fetching data. Defaults to 30.
        height (int, optional): Chart height. Defaults to 400.
        show_legend (bool, optional): Whether to show the legend. Defaults to True.
        
    Returns:
        plotly.graph_objects.Figure: The time series chart
    """
    # Get current theme
    theme = get_current_theme()
    
    # Get data if not provided
    if data is None:
        time_series_data = get_time_series_data(days=days)
        if isinstance(time_series_data, dict) and 'data' in time_series_data:
            data = pd.DataFrame(time_series_data['data'])
        else:
            # Create demo data if no data is available
            data = create_demo_time_series_data(days)
    
    if data.empty:
        # Create demo data if data is empty
        data = create_demo_time_series_data(days)
    
    # Ensure expected columns exist
    expected_columns = ['date', 'high_severity', 'medium_severity', 'low_severity']
    for col in expected_columns:
        if col not in data.columns:
            if col == 'date':
                # Create date column if missing
                data['date'] = pd.date_range(end=datetime.now(), periods=len(data))
            else:
                # Create severity columns with random values if missing
                data[col] = np.random.randint(0, 10, size=len(data))
    
    # Convert date to datetime if it's not already
    if not pd.api.types.is_datetime64_any_dtype(data['date']):
        data['date'] = pd.to_datetime(data['date'])
    
    # Sort by date
    data = data.sort_values('date')
    
    # Create figure
    fig = go.Figure()
    
    # Add traces for each severity level
    fig.add_trace(
        go.Bar(
            x=data['date'],
            y=data['high_severity'],
            name='High Severity',
            marker_color=theme.get('error_color', '#f44336'),
            hovertemplate='%{y} high severity anomalies<extra></extra>'
        )
    )
    
    fig.add_trace(
        go.Bar(
            x=data['date'],
            y=data['medium_severity'],
            name='Medium Severity',
            marker_color=theme.get('warning_color', '#ff9100'),
            hovertemplate='%{y} medium severity anomalies<extra></extra>'
        )
    )
    
    fig.add_trace(
        go.Bar(
            x=data['date'],
            y=data['low_severity'],
            name='Low Severity',
            marker_color=theme.get('primary_color', '#4361ee'),
            hovertemplate='%{y} low severity anomalies<extra></extra>'
        )
    )
    
    # Update layout
    fig.update_layout(
        title='Anomalies Over Time',
        barmode='stack',
        xaxis=dict(
            title='Date',
            gridcolor='rgba(0,0,0,0.1)',
            tickformat='%b %d'
        ),
        yaxis=dict(
            title='Count',
            gridcolor='rgba(0,0,0,0.1)'
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=height,
        hovermode='x unified',
        showlegend=show_legend,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        )
    )
    
    # Add range selector
    fig.update_xaxes(
        rangeslider_visible=False,
        rangeselector=dict(
            buttons=list([
                dict(count=7, label='1w', step='day', stepmode='backward'),
                dict(count=1, label='1m', step='month', stepmode='backward'),
                dict(count=3, label='3m', step='month', stepmode='backward'),
                dict(step='all')
            ]),
            bgcolor='rgba(0,0,0,0.1)',
            activecolor=theme.get('primary_color', '#4361ee')
        )
    )
    
    return fig

def create_severity_distribution_chart(data=None, height=400):
    """
    Create a chart showing the distribution of anomalies by severity.
    
    Args:
        data (pd.DataFrame, optional): Anomaly data. If None, fetches from data service.
        height (int, optional): Chart height. Defaults to 400.
        
    Returns:
        plotly.graph_objects.Figure: The severity distribution chart
    """
    # Get current theme
    theme = get_current_theme()
    
    # Get data if not provided
    if data is None:
        anomalies = get_anomalies(limit=1000)
        if anomalies:
            # Create a list to hold severity data
            severity_data = []
            
            # Count occurrences of each severity
            severity_counts = {}
            
            for anomaly in anomalies:
                # Extract severity from analysis if available
                severity = "Unknown"
                if anomaly.get('analysis') and isinstance(anomaly['analysis'], dict):
                    severity = anomaly['analysis'].get('severity', "Unknown")
                
                # Increment count
                if severity in severity_counts:
                    severity_counts[severity] += 1
                else:
                    severity_counts[severity] = 1
            
            # Create data for the chart
            for severity, count in severity_counts.items():
                severity_data.append({
                    "severity": severity,
                    "count": count
                })
            
            # Convert to DataFrame
            data = pd.DataFrame(severity_data)
        else:
            # Create demo data if no data is available
            data = create_demo_severity_data()
    
    if data is None or data.empty:
        # Create demo data if data is empty
        data = create_demo_severity_data()
    
    # Ensure expected columns exist
    if 'severity' not in data.columns or 'count' not in data.columns:
        # Create demo data if columns are missing
        data = create_demo_severity_data()
    
    # Map severity levels to colors
    severity_colors = {
        "Critical": theme.get('error_color', '#f44336'),
        "High": theme.get('warning_color', '#ff9100'),
        "Medium": "#ffb74d",
        "Low": theme.get('primary_color', '#4361ee'),
        "Unknown": "#9e9e9e"
    }
    
    # Create color list in the order of the data
    colors = [severity_colors.get(severity, "#9e9e9e") for severity in data['severity']]
    
    # Create figure - first try a pie chart
    fig = go.Figure()
    
    fig.add_trace(
        go.Pie(
            labels=data['severity'],
            values=data['count'],
            hole=0.6,
            marker=dict(colors=colors),
            textinfo='label+percent',
            hoverinfo='label+value',
            hovertemplate='%{label}: %{value} anomalies<extra></extra>'
        )
    )
    
    # Update layout
    fig.update_layout(
        title='Anomalies by Severity',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=height,
        showlegend=False
    )
    
    # Add total count in the center
    total_count = data['count'].sum()
    
    fig.add_annotation(
        x=0.5, y=0.5,
        text=f"{total_count}<br>Total",
        font=dict(size=16, color=theme.get('text_color', '#333333')),
        showarrow=False
    )
    
    return fig

def create_model_comparison_chart(data=None, height=400):
    """
    Create a chart comparing the performance of different anomaly detection models.
    
    Args:
        data (pd.DataFrame, optional): Model performance data. If None, creates demo data.
        height (int, optional): Chart height. Defaults to 400.
        
    Returns:
        plotly.graph_objects.Figure: The model comparison chart
    """
    # Get current theme
    theme = get_current_theme()
    
    # Create demo data if not provided
    if data is None:
        data = create_demo_model_comparison_data()
    
    # Ensure expected columns exist
    expected_columns = ['model', 'accuracy', 'precision', 'recall', 'f1_score']
    for col in expected_columns:
        if col not in data.columns:
            # Create demo data if columns are missing
            data = create_demo_model_comparison_data()
            break
    
    # Create figure with subplots
    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "bar"}, {"type": "radar"}]],
        column_widths=[0.6, 0.4],
        subplot_titles=("Model Performance Metrics", "Model Comparison")
    )
    
    # Color for each model
    colors = px.colors.qualitative.Plotly[:len(data)]
    
    # Add bar chart for each metric
    metrics = ['accuracy', 'precision', 'recall', 'f1_score']
    
    for i, metric in enumerate(metrics):
        fig.add_trace(
            go.Bar(
                x=data['model'],
                y=data[metric],
                name=metric.capitalize(),
                marker_color=theme.get('chart_palette', [theme.get('primary_color', '#4361ee')])[i % len(theme.get('chart_palette', [theme.get('primary_color', '#4361ee')]))],
                hovertemplate='%{y:.2f}<extra></extra>'
            ),
            row=1, col=1
        )
    
    # Add radar chart for model comparison
    for i, model in enumerate(data['model']):
        model_data = data[data['model'] == model]
        
        fig.add_trace(
            go.Scatterpolar(
                r=[model_data[metric].values[0] for metric in metrics],
                theta=[metric.capitalize() for metric in metrics],
                fill='toself',
                name=model,
                marker_color=colors[i],
                hovertemplate='%{r:.2f}<extra>%{theta}</extra>'
            ),
            row=1, col=2
        )
    
    # Update layout
    fig.update_layout(
        barmode='group',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=height,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        hovermode='closest'
    )
    
    # Update polar axes
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1]
            )
        )
    )
    
    # Update axes
    fig.update_xaxes(
        showgrid=True,
        gridcolor='rgba(0,0,0,0.1)',
        row=1, col=1
    )
    
    fig.update_yaxes(
        title='Score',
        showgrid=True,
        gridcolor='rgba(0,0,0,0.1)',
        range=[0, 1],
        row=1, col=1
    )
    
    return fig

def create_anomaly_heatmap(data=None, height=400):
    """
    Create a heatmap showing anomaly distribution by time of day and day of week.
    
    Args:
        data (pd.DataFrame, optional): Anomaly data. If None, fetches from data service.
        height (int, optional): Chart height. Defaults to 400.
        
    Returns:
        plotly.graph_objects.Figure: The anomaly heatmap
    """
    # Get current theme
    theme = get_current_theme()
    
    # Get data if not provided
    if data is None:
        anomalies = get_anomalies(limit=1000)
        
        if anomalies:
            # Extract timestamp and create DataFrame
            data = []
            
            for anomaly in anomalies:
                timestamp = anomaly.get('timestamp')
                
                # Parse timestamp if it's a string
                if isinstance(timestamp, str):
                    try:
                        timestamp = pd.to_datetime(timestamp)
                    except:
                        continue
                
                # Extract day of week and hour
                if timestamp:
                    data.append({
                        'day_of_week': timestamp.day_name(),
                        'hour': timestamp.hour
                    })
            
            # Convert to DataFrame
            data = pd.DataFrame(data)
        else:
            # Create demo data if no data is available
            data = create_demo_heatmap_data()
    
    if data is None or data.empty:
        # Create demo data if data is empty
        data = create_demo_heatmap_data()
    
    # Ensure expected columns exist
    if 'day_of_week' not in data.columns or 'hour' not in data.columns:
        # Create demo data if columns are missing
        data = create_demo_heatmap_data()
    
    # Count occurrences of each day-hour combination
    heatmap_data = data.groupby(['day_of_week', 'hour']).size().reset_index(name='count')
    
    # Create a pivot table for the heatmap
    pivot_data = heatmap_data.pivot_table(
        index='day_of_week',
        columns='hour',
        values='count',
        fill_value=0
    )
    
    # Reindex to ensure days are in correct order
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    pivot_data = pivot_data.reindex(days_order)
    
    # Create figure
    fig = go.Figure(
        data=go.Heatmap(
            z=pivot_data.values,
            x=[f"{hour}:00" for hour in range(24)],
            y=pivot_data.index,
            colorscale=[
                [0, 'rgba(255,255,255,0.8)'],
                [0.2, theme.get('primary_color', '#4361ee') + '40'],
                [0.4, theme.get('primary_color', '#4361ee') + '80'],
                [0.6, theme.get('secondary_color', '#3a0ca3') + '60'],
                [0.8, theme.get('secondary_color', '#3a0ca3') + 'A0'],
                [1, theme.get('error_color', '#f44336')]
            ],
            hovertemplate='%{y} at %{x}<br>Anomalies: %{z}<extra></extra>'
        )
    )
    
    # Update layout
    fig.update_layout(
        title='Anomaly Distribution by Time',
        xaxis=dict(
            title='Hour of Day',
            tickvals=list(range(0, 24, 3)),
            ticktext=[f"{h}:00" for h in range(0, 24, 3)]
        ),
        yaxis=dict(
            title='Day of Week',
            categoryorder='array',
            categoryarray=days_order
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=height
    )
    
    return fig

def create_feature_importance_chart(data=None, height=400):
    """
    Create a chart showing feature importance for anomaly detection.
    
    Args:
        data (pd.DataFrame, optional): Feature importance data. If None, creates demo data.
        height (int, optional): Chart height. Defaults to 400.
        
    Returns:
        plotly.graph_objects.Figure: The feature importance chart
    """
    # Get current theme
    theme = get_current_theme()
    
    # Create demo data if not provided
    if data is None:
        data = create_demo_feature_importance_data()
    
    # Ensure expected columns exist
    if 'feature' not in data.columns or 'importance' not in data.columns:
        # Create demo data if columns are missing
        data = create_demo_feature_importance_data()
    
    # Sort by importance
    data = data.sort_values('importance', ascending=True)
    
    # Create color gradient based on importance
    n_features = len(data)
    color_scale = np.linspace(0, 1, n_features)
    colors = [
        f"rgba({int(99 + 156 * i)}, {int(94 + 107 * i)}, {int(238 - 198 * i)}, 0.8)"
        for i in color_scale
    ]
    
    # Create figure
    fig = go.Figure()
    
    fig.add_trace(
        go.Bar(
            y=data['feature'],
            x=data['importance'],
            orientation='h',
            marker_color=colors,
            hovertemplate='%{x:.3f}<extra>%{y}</extra>'
        )
    )
    
    # Update layout
    fig.update_layout(
        title='Feature Importance',
        xaxis=dict(
            title='Importance Score',
            showgrid=True,
            gridcolor='rgba(0,0,0,0.1)'
        ),
        yaxis=dict(
            title='Feature',
            showgrid=True,
            gridcolor='rgba(0,0,0,0.1)'
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=height
    )
    
    return fig

# Helper functions for creating demo data

def create_demo_time_series_data(days=30):
    """
    Create demo time series data for development.
    
    Args:
        days (int): Number of days to include
        
    Returns:
        pd.DataFrame: DataFrame with demo data
    """
    # Generate dates
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days-1)
    dates = pd.date_range(start=start_date, end=end_date)
    
    # Generate random counts with a trend
    np.random.seed(42)  # For reproducibility
    
    # Base trend - higher on weekdays, lower on weekends
    trend = [5 if d.weekday() < 5 else 2 for d in dates]
    
    # Add some randomness
    high_severity = [max(0, int(t * 0.4 + np.random.normal(0, 1))) for t in trend]
    medium_severity = [max(0, int(t * 0.7 + np.random.normal(0, 2))) for t in trend]
    low_severity = [max(0, int(t * 1.2 + np.random.normal(0, 3))) for t in trend]
    
    # Create DataFrame
    data = pd.DataFrame({
        'date': dates,
        'high_severity': high_severity,
        'medium_severity': medium_severity,
        'low_severity': low_severity
    })
    
    return data

def create_demo_severity_data():
    """
    Create demo severity distribution data.
    
    Returns:
        pd.DataFrame: DataFrame with demo data
    """
    # Create data
    data = pd.DataFrame({
        'severity': ['Critical', 'High', 'Medium', 'Low', 'Unknown'],
        'count': [5, 15, 25, 40, 5]
    })
    
    return data

def create_demo_model_comparison_data():
    """
    Create demo model comparison data.
    
    Returns:
        pd.DataFrame: DataFrame with demo data
    """
    # Create data
    data = pd.DataFrame({
        'model': ['Isolation Forest', 'Autoencoder', 'One-Class SVM', 'LOF', 'DBSCAN'],
        'accuracy': [0.92, 0.88, 0.85, 0.82, 0.78],
        'precision': [0.88, 0.85, 0.83, 0.80, 0.75],
        'recall': [0.90, 0.87, 0.84, 0.81, 0.77],
        'f1_score': [0.89, 0.86, 0.83, 0.80, 0.76]
    })
    
    return data

def create_demo_heatmap_data():
    """
    Create demo heatmap data for anomaly distribution.
    
    Returns:
        pd.DataFrame: DataFrame with demo data
    """
    # Day and hour combinations
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    hours = range(24)
    
    # Create empty DataFrame
    data = []
    
    # Generate random counts with patterns
    np.random.seed(42)  # For reproducibility
    
    # Business hours have more anomalies (9 AM - 6 PM on weekdays)
    for day in days:
        is_weekend = day in ['Saturday', 'Sunday']
        
        for hour in hours:
            is_business_hour = 9 <= hour <= 18
            
            # Base count
            if is_weekend:
                base_count = 1  # Lower on weekends
            elif is_business_hour:
                base_count = 5  # Higher during business hours
            else:
                base_count = 2  # Medium outside business hours
            
            # Add randomness
            count = max(0, np.random.poisson(base_count))
            
            # Add multiple entries to simulate individual anomalies
            for _ in range(count):
                data.append({
                    'day_of_week': day,
                    'hour': hour
                })
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    return df

def create_demo_feature_importance_data():
    """
    Create demo feature importance data.
    
    Returns:
        pd.DataFrame: DataFrame with demo data
    """
    # Create data
    data = pd.DataFrame({
        'feature': [
            'Request Frequency',
            'Time of Day',
            'Source IP Reputation',
            'Data Transfer Volume',
            'Authentication Method',
            'Session Duration',
            'User Role',
            'Resource Access Pattern',
            'Error Rate',
            'Geographic Location'
        ],
        'importance': [
            0.92, 0.85, 0.78, 0.75, 0.68, 0.65, 0.62, 0.58, 0.55, 0.45
        ]
    })
    
    return data

def create_static_severity_chart():
    """Create a static severity distribution chart and return as an image."""
    import plotly.express as px
    import pandas as pd
    import numpy as np
    from io import BytesIO
    
    # Generate sample data if needed for development/testing
    # In production, you would use actual data from your database
    dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
    
    # Create sample data
    data = []
    for date in dates:
        # Add random number of anomalies for each severity level
        high = np.random.randint(0, 5)
        medium = np.random.randint(1, 10)
        low = np.random.randint(3, 15)
        
        # Add high severity anomalies
        for _ in range(high):
            data.append({
                'date': date,
                'severity': 'High',
                'count': 1
            })
        
        # Add medium severity anomalies
        for _ in range(medium):
            data.append({
                'date': date,
                'severity': 'Medium',
                'count': 1
            })
        
        # Add low severity anomalies
        for _ in range(low):
            data.append({
                'date': date,
                'severity': 'Low',
                'count': 1
            })
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    # Aggregate by date and severity
    agg_df = df.groupby(['date', 'severity'])['count'].sum().reset_index()
    
    # Create chart with Plotly
    fig = px.bar(
        agg_df, 
        x='date', 
        y='count', 
        color='severity',
        color_discrete_map={
            'High': '#FF4560',
            'Medium': '#FEB019',
            'Low': '#00E396'
        },
        title='Anomaly Severity Distribution Over Time'
    )
    
    # Update layout
    fig.update_layout(
        xaxis_title='Date',
        yaxis_title='Number of Anomalies',
        legend_title='Severity',
        barmode='stack'
    )
    
    # Convert Plotly figure to image bytes
    try:
        img_bytes = fig.to_image(format="png")
        
        # Create a BytesIO object for Streamlit to use
        return BytesIO(img_bytes)
    except Exception as e:
        import streamlit as st
        st.error(f"Failed to create chart image: {str(e)}")
        
        # Return None on error, let the calling code handle this case
        return None

def visualize_anomaly_timeline(anomaly_id=None, data=None, height=400, days_back=30):
    """
    Create a timeline visualization for an anomaly or all anomalies.
    
    Args:
        anomaly_id (str, optional): Specific anomaly ID to visualize. Defaults to None.
        data (pd.DataFrame, optional): Anomaly data. If None, fetches from data service.
        height (int, optional): Chart height. Defaults to 400.
        days_back (int, optional): Number of days to look back. Defaults to 30.
        
    Returns:
        plotly.graph_objects.Figure: The timeline visualization
    """
    # Get current theme
    theme = get_current_theme()
    
    # Get data if not provided
    if data is None:
        if anomaly_id:
            # Get specific anomaly and related events
            from services.data_service import get_anomaly_by_id, get_agent_activities
            
            anomaly = get_anomaly_by_id(anomaly_id)
            activities = get_agent_activities(anomaly_id)
            
            if anomaly:
                # Create timeline data
                timeline_data = []
                
                # Add the main anomaly
                main_timestamp = None
                if anomaly.get('timestamp'):
                    if isinstance(anomaly['timestamp'], str):
                        try:
                            main_timestamp = pd.to_datetime(anomaly['timestamp'])
                        except:
                            main_timestamp = pd.Timestamp.now() - pd.Timedelta(days=1)
                    else:
                        main_timestamp = anomaly['timestamp']
                else:
                    main_timestamp = pd.Timestamp.now() - pd.Timedelta(days=1)
                
                # Get severity from analysis if available
                severity = "Unknown"
                if anomaly.get('analysis') and isinstance(anomaly['analysis'], dict):
                    severity = anomaly['analysis'].get('severity', "Unknown")
                
                # Add to timeline data
                timeline_data.append({
                    'id': anomaly_id,
                    'type': 'anomaly',
                    'timestamp': main_timestamp,
                    'description': f"Anomaly detected (Score: {anomaly.get('score', 0):.2f})",
                    'severity': severity,
                    'status': anomaly.get('status', 'new')
                })
                
                # Add agent activities
                for activity in activities:
                    activity_timestamp = None
                    
                    if activity.get('timestamp'):
                        if isinstance(activity['timestamp'], str):
                            try:
                                activity_timestamp = pd.to_datetime(activity['timestamp'])
                            except:
                                activity_timestamp = main_timestamp + pd.Timedelta(minutes=random.randint(5, 60))
                        else:
                            activity_timestamp = activity['timestamp']
                    else:
                        activity_timestamp = main_timestamp + pd.Timedelta(minutes=random.randint(5, 60))
                    
                    # Add to timeline data
                    timeline_data.append({
                        'id': activity.get('id', str(random.randint(1000, 9999))),
                        'type': 'activity',
                        'timestamp': activity_timestamp,
                        'description': activity.get('description', activity.get('action', 'Agent activity')),
                        'severity': 'N/A',
                        'status': activity.get('status', 'completed'),
                        'agent': activity.get('agent', activity.get('agent_id', 'unknown'))
                    })
                
                # Convert to DataFrame
                data = pd.DataFrame(timeline_data)
            else:
                # Create demo data if anomaly not found
                data = create_demo_timeline_data(anomaly_id)
        else:
            # Get all anomalies from data service
            anomalies = get_anomalies(limit=100)
            
            if anomalies:
                # Create timeline data
                timeline_data = []
                
                for anomaly in anomalies:
                    # Parse timestamp
                    if anomaly.get('timestamp'):
                        if isinstance(anomaly['timestamp'], str):
                            try:
                                timestamp = pd.to_datetime(anomaly['timestamp'])
                            except:
                                timestamp = pd.Timestamp.now() - pd.Timedelta(days=random.randint(1, days_back))
                        else:
                            timestamp = anomaly['timestamp']
                    else:
                        timestamp = pd.Timestamp.now() - pd.Timedelta(days=random.randint(1, days_back))
                    
                    # Get severity from analysis if available
                    severity = "Unknown"
                    if anomaly.get('analysis') and isinstance(anomaly['analysis'], dict):
                        severity = anomaly['analysis'].get('severity', "Unknown")
                    
                    # Add to timeline data
                    timeline_data.append({
                        'id': anomaly.get('id', str(random.randint(1000, 9999))),
                        'type': 'anomaly',
                        'timestamp': timestamp,
                        'description': f"Anomaly detected (Score: {anomaly.get('score', 0):.2f})",
                        'severity': severity,
                        'status': anomaly.get('status', 'new'),
                        'model': anomaly.get('model', 'unknown')
                    })
                
                # Convert to DataFrame
                data = pd.DataFrame(timeline_data)
            else:
                # Create demo data if no anomalies found
                data = create_demo_timeline_data()
    
    # Create demo data if data is empty or None
    if data is None or len(data) == 0:
        data = create_demo_timeline_data(anomaly_id)
    
    # Ensure timestamp column is datetime
    if 'timestamp' in data.columns:
        data['timestamp'] = pd.to_datetime(data['timestamp'])
    
    # Sort by timestamp
    data = data.sort_values('timestamp')
    
    # Filter to relevant time period
    start_date = pd.Timestamp.now() - pd.Timedelta(days=days_back)
    data = data[data['timestamp'] >= start_date]
    
    # Create figure
    fig = go.Figure()
    
    # Color mapping
    severity_colors = {
        "Critical": theme.get('error_color', '#f44336'),
        "High": theme.get('warning_color', '#ff9100'),
        "Medium": "#ffb74d",
        "Low": theme.get('primary_color', '#4361ee'),
        "Unknown": "#9e9e9e",
        "N/A": "#9e9e9e"
    }
    
    status_shapes = {
        "new": "circle",
        "investigating": "diamond",
        "resolved": "square",
        "false_positive": "x",
        "completed": "star",
        "in_progress": "triangle-up",
        "failed": "x"
    }
    
    # Check if we're visualizing a specific anomaly
    if anomaly_id:
        # Create a scatter plot for each event type
        for event_type in data['type'].unique():
            type_data = data[data['type'] == event_type]
            
            marker_symbol = "circle" if event_type == "anomaly" else "diamond"
            marker_size = 16 if event_type == "anomaly" else 12
            
            # For activities, use status to determine shape
            if event_type == "activity":
                # Create a separate trace for each status
                for status in type_data['status'].unique():
                    status_data = type_data[type_data['status'] == status]
                    
                    fig.add_trace(
                        go.Scatter(
                            x=status_data['timestamp'],
                            y=[0] * len(status_data),  # All on same line
                            mode="markers+text",
                            marker=dict(
                                symbol=status_shapes.get(status, "circle"),
                                size=marker_size,
                                color=theme.get('secondary_color', '#3a0ca3'),
                                line=dict(width=1, color="white")
                            ),
                            text=[desc[:20] + "..." if len(desc) > 20 else desc for desc in status_data['description']],
                            textposition="top center",
                            hovertext=[
                                f"<b>{desc}</b><br>Status: {status}<br>Agent: {agent}<br>{ts.strftime('%Y-%m-%d %H:%M:%S')}"
                                for desc, status, agent, ts in zip(
                                    status_data['description'],
                                    status_data['status'],
                                    status_data['agent'],
                                    status_data['timestamp']
                                )
                            ],
                            hoverinfo="text",
                            name=f"{status.capitalize()} Activity"
                        )
                    )
            else:
                # For anomalies, use severity to determine color
                for severity in type_data['severity'].unique():
                    severity_data = type_data[type_data['severity'] == severity]
                    
                    fig.add_trace(
                        go.Scatter(
                            x=severity_data['timestamp'],
                            y=[0] * len(severity_data),  # All on same line
                            mode="markers+text",
                            marker=dict(
                                symbol=marker_symbol,
                                size=marker_size,
                                color=severity_colors.get(severity, "#9e9e9e"),
                                line=dict(width=1, color="white")
                            ),
                            text=["Anomaly Detected"] * len(severity_data),
                            textposition="top center",
                            hovertext=[
                                f"<b>Anomaly Detected</b><br>Severity: {severity}<br>Status: {status}<br>{desc}<br>{ts.strftime('%Y-%m-%d %H:%M:%S')}"
                                for severity, status, desc, ts in zip(
                                    severity_data['severity'],
                                    severity_data['status'],
                                    severity_data['description'],
                                    severity_data['timestamp']
                                )
                            ],
                            hoverinfo="text",
                            name=f"{severity} Anomaly"
                        )
                    )
        
        # Add a line connecting events in chronological order
        fig.add_trace(
            go.Scatter(
                x=data['timestamp'],
                y=[0] * len(data),
                mode="lines",
                line=dict(color="#dddddd", width=1, dash="dot"),
                hoverinfo="none",
                showlegend=False
            )
        )
        
        # Update layout
        fig.update_layout(
            title="Anomaly Timeline",
            xaxis=dict(
                title="Time",
                showgrid=True,
                gridcolor="#eeeeee"
            ),
            yaxis=dict(
                showticklabels=False,
                showgrid=False,
                zeroline=False
            ),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            hovermode="closest",
            height=height,
            margin=dict(l=20, r=20, t=60, b=20),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
    else:
        # For multiple anomalies, create a timeline with multiple tracks
        # Group by model
        models = data['model'].unique() if 'model' in data.columns else ["Unknown"]
        
        for i, model in enumerate(models):
            if 'model' in data.columns:
                model_data = data[data['model'] == model]
            else:
                model_data = data
            
            # Create a separate trace for each severity
            for severity in model_data['severity'].unique():
                severity_data = model_data[model_data['severity'] == severity]
                
                fig.add_trace(
                    go.Scatter(
                        x=severity_data['timestamp'],
                        y=[i] * len(severity_data),  # Separate line for each model
                        mode="markers",
                        marker=dict(
                            symbol="circle",
                            size=12,
                            color=severity_colors.get(severity, "#9e9e9e"),
                            line=dict(width=1, color="white")
                        ),
                        hovertext=[
                            f"<b>{desc}</b><br>Model: {model}<br>Severity: {severity}<br>Status: {status}<br>{ts.strftime('%Y-%m-%d %H:%M:%S')}"
                            for desc, severity, status, ts in zip(
                                severity_data['description'],
                                severity_data['severity'],
                                severity_data['status'],
                                severity_data['timestamp']
                            )
                        ],
                        hoverinfo="text",
                        name=f"{model} - {severity}"
                    )
                )
            
            # Add a line for each model
            fig.add_trace(
                go.Scatter(
                    x=[start_date, pd.Timestamp.now()],
                    y=[i, i],
                    mode="lines",
                    line=dict(color="#dddddd", width=1),
                    hoverinfo="none",
                    showlegend=False
                )
            )
        
        # Update layout
        fig.update_layout(
            title="Anomaly Timeline",
            xaxis=dict(
                title="Time",
                showgrid=True,
                gridcolor="#eeeeee"
            ),
            yaxis=dict(
                title="Model",
                tickvals=list(range(len(models))),
                ticktext=models,
                showgrid=True,
                gridcolor="#eeeeee"
            ),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            hovermode="closest",
            height=height,
            margin=dict(l=100, r=20, t=60, b=20),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
    
    # Add range selector
    fig.update_xaxes(
        rangeslider_visible=False,
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1d", step="day", stepmode="backward"),
                dict(count=7, label="1w", step="day", stepmode="backward"),
                dict(count=1, label="1m", step="month", stepmode="backward"),
                dict(step="all")
            ]),
            bgcolor="rgba(0,0,0,0.1)",
            activecolor=theme.get('primary_color', '#4361ee')
        )
    )
    
    return fig

def create_demo_timeline_data(anomaly_id=None):
    """
    Create demo timeline data for development.
    
    Args:
        anomaly_id (str, optional): Specific anomaly ID to create data for. Defaults to None.
        
    Returns:
        pd.DataFrame: DataFrame with demo timeline data
    """
    # Current time
    now = pd.Timestamp.now()
    
    if anomaly_id:
        # Create a timeline for a specific anomaly
        # Main anomaly detection event
        anomaly_time = now - pd.Timedelta(days=1, hours=random.randint(0, 12))
        
        # Create events in a sequence
        events = [
            {
                'id': anomaly_id,
                'type': 'anomaly',
                'timestamp': anomaly_time,
                'description': f"Anomaly detected (Score: {random.uniform(0.7, 0.95):.2f})",
                'severity': random.choice(['Critical', 'High', 'Medium']),
                'status': 'new'
            },
            {
                'id': f"act_{random.randint(1000, 9999)}",
                'type': 'activity',
                'timestamp': anomaly_time + pd.Timedelta(minutes=15),
                'description': "Initial analysis started",
                'severity': 'N/A',
                'status': 'completed',
                'agent': 'analyzer_agent'
            },
            {
                'id': f"act_{random.randint(1000, 9999)}",
                'type': 'activity',
                'timestamp': anomaly_time + pd.Timedelta(minutes=25),
                'description': "Pattern recognition completed",
                'severity': 'N/A',
                'status': 'completed',
                'agent': 'analyzer_agent'
            },
            {
                'id': f"act_{random.randint(1000, 9999)}",
                'type': 'activity',
                'timestamp': anomaly_time + pd.Timedelta(minutes=35),
                'description': "Investigation initiated",
                'severity': 'N/A',
                'status': 'completed',
                'agent': 'investigator_agent'
            },
            {
                'id': f"act_{random.randint(1000, 9999)}",
                'type': 'activity',
                'timestamp': anomaly_time + pd.Timedelta(minutes=50),
                'description': "Correlation analysis completed",
                'severity': 'N/A',
                'status': 'completed',
                'agent': 'investigator_agent'
            },
            {
                'id': f"act_{random.randint(1000, 9999)}",
                'type': 'activity',
                'timestamp': anomaly_time + pd.Timedelta(minutes=65),
                'description': "Remediation actions initiated",
                'severity': 'N/A',
                'status': 'in_progress',
                'agent': 'responder_agent'
            },
            {
                'id': f"act_{random.randint(1000, 9999)}",
                'type': 'activity',
                'timestamp': anomaly_time + pd.Timedelta(minutes=75),
                'description': "Security team notified",
                'severity': 'N/A',
                'status': 'completed',
                'agent': 'responder_agent'
            }
        ]
        
        # Create DataFrame
        df = pd.DataFrame(events)
    else:
        # Create a timeline for multiple anomalies
        events = []
        
        # Generate several anomalies over the past month
        models = ['isolation_forest', 'autoencoder', 'one_class_svm', 'dbscan']
        severities = ['Critical', 'High', 'Medium', 'Low']
        statuses = ['new', 'investigating', 'resolved', 'false_positive']
        
        # Weights for severity (less critical anomalies are more common)
        severity_weights = [0.1, 0.2, 0.3, 0.4]
        
        # Generate 20-40 anomalies
        for i in range(random.randint(20, 40)):
            # Random timestamp in the past month
            timestamp = now - pd.Timedelta(days=random.randint(1, 30), 
                                          hours=random.randint(0, 23),
                                          minutes=random.randint(0, 59))
            
            # Select model, severity and status
            model = random.choice(models)
            severity = random.choices(severities, weights=severity_weights)[0]
            status = random.choice(statuses)
            
            # Create anomaly event
            events.append({
                'id': f"ano_{random.randint(1000, 9999)}",
                'type': 'anomaly',
                'timestamp': timestamp,
                'description': f"Anomaly detected (Score: {random.uniform(0.6, 0.95):.2f})",
                'severity': severity,
                'status': status,
                'model': model
            })
        
        # Create DataFrame
        df = pd.DataFrame(events)
    
    return df