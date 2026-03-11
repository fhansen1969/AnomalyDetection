"""
Metrics components for the Anomaly Detection Dashboard.
Provides functions for displaying system and model metrics.
"""

from typing import Dict, Any, List, Optional, Tuple
import streamlit as st
import plotly.graph_objects as go
from config.theme import get_current_theme

def display_system_metrics(status: Dict[str, Any]) -> None:
    """Display system metrics in a grid layout."""
    current_theme = get_current_theme()
    
    # Get system load data with defaults
    system_load = status.get("system_load", {})
    cpu_usage = system_load.get("cpu", 0)
    memory_usage = system_load.get("memory", 0)
    disk_usage = system_load.get("disk", 0)
    network_usage = system_load.get("network", 0)
    
    # Create 4 columns for metrics
    col1, col2, col3, col4 = st.columns(4)
    
    # Helper function to get color based on usage
    def get_usage_color(usage):
        if usage < 50:
            return current_theme['success_color']
        elif usage < 80:
            return current_theme['warning_color']
        else:
            return current_theme['error_color']
    
    # CPU Usage
    with col1:
        cpu_color = get_usage_color(cpu_usage)
        st.markdown(f"""
        <div style="background: {current_theme['card_bg']}; padding: 20px; border-radius: 10px; 
                    box-shadow: 0 4px 8px rgba(0,0,0,0.08); text-align: center;">
            <div style="font-size: 2rem; color: {cpu_color};">💻</div>
            <h4 style="margin: 10px 0; color: {current_theme['text_color']};">CPU Usage</h4>
            <h2 style="margin: 0; color: {cpu_color};">{cpu_usage:.1f}%</h2>
            <div style="margin-top: 10px;">
                <div style="background: rgba(0,0,0,0.1); border-radius: 10px; height: 8px; overflow: hidden;">
                    <div style="background: {cpu_color}; height: 100%; width: {cpu_usage}%; transition: width 0.3s;"></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Memory Usage
    with col2:
        memory_color = get_usage_color(memory_usage)
        st.markdown(f"""
        <div style="background: {current_theme['card_bg']}; padding: 20px; border-radius: 10px; 
                    box-shadow: 0 4px 8px rgba(0,0,0,0.08); text-align: center;">
            <div style="font-size: 2rem; color: {memory_color};">🧠</div>
            <h4 style="margin: 10px 0; color: {current_theme['text_color']};">Memory Usage</h4>
            <h2 style="margin: 0; color: {memory_color};">{memory_usage:.1f}%</h2>
            <div style="margin-top: 10px;">
                <div style="background: rgba(0,0,0,0.1); border-radius: 10px; height: 8px; overflow: hidden;">
                    <div style="background: {memory_color}; height: 100%; width: {memory_usage}%; transition: width 0.3s;"></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Disk Usage
    with col3:
        disk_color = get_usage_color(disk_usage)
        st.markdown(f"""
        <div style="background: {current_theme['card_bg']}; padding: 20px; border-radius: 10px; 
                    box-shadow: 0 4px 8px rgba(0,0,0,0.08); text-align: center;">
            <div style="font-size: 2rem; color: {disk_color};">💾</div>
            <h4 style="margin: 10px 0; color: {current_theme['text_color']};">Disk Usage</h4>
            <h2 style="margin: 0; color: {disk_color};">{disk_usage:.1f}%</h2>
            <div style="margin-top: 10px;">
                <div style="background: rgba(0,0,0,0.1); border-radius: 10px; height: 8px; overflow: hidden;">
                    <div style="background: {disk_color}; height: 100%; width: {disk_usage}%; transition: width 0.3s;"></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Network Usage
    with col4:
        network_color = get_usage_color(network_usage)
        st.markdown(f"""
        <div style="background: {current_theme['card_bg']}; padding: 20px; border-radius: 10px; 
                    box-shadow: 0 4px 8px rgba(0,0,0,0.08); text-align: center;">
            <div style="font-size: 2rem; color: {network_color};">🌐</div>
            <h4 style="margin: 10px 0; color: {current_theme['text_color']};">Network Usage</h4>
            <h2 style="margin: 0; color: {network_color};">{network_usage:.1f}%</h2>
            <div style="margin-top: 10px;">
                <div style="background: rgba(0,0,0,0.1); border-radius: 10px; height: 8px; overflow: hidden;">
                    <div style="background: {network_color}; height: 100%; width: {network_usage}%; transition: width 0.3s;"></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Add some spacing
    st.markdown("<br>", unsafe_allow_html=True)
    
    # System Information
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div style="background: {current_theme['card_bg']}; padding: 15px; border-radius: 8px; 
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <div style="font-size: 0.9rem; color: {current_theme.get('text_muted', '#888')};">Hostname</div>
            <div style="font-size: 1.1rem; font-weight: 500; color: {current_theme['text_color']};">
                {status.get('hostname', 'Unknown')}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style="background: {current_theme['card_bg']}; padding: 15px; border-radius: 8px; 
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <div style="font-size: 0.9rem; color: {current_theme.get('text_muted', '#888')};">Platform</div>
            <div style="font-size: 1.1rem; font-weight: 500; color: {current_theme['text_color']};">
                {status.get('platform', 'Unknown')}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div style="background: {current_theme['card_bg']}; padding: 15px; border-radius: 8px; 
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <div style="font-size: 0.9rem; color: {current_theme.get('text_muted', '#888')};">Uptime</div>
            <div style="font-size: 1.1rem; font-weight: 500; color: {current_theme['text_color']};">
                {status.get('uptime', 'Unknown')}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div style="background: {current_theme['card_bg']}; padding: 15px; border-radius: 8px; 
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <div style="font-size: 0.9rem; color: {current_theme.get('text_muted', '#888')};">Last Update</div>
            <div style="font-size: 1.1rem; font-weight: 500; color: {current_theme['text_color']};">
                {status.get('last_update', 'Unknown')}
            </div>
        </div>
        """, unsafe_allow_html=True)
def display_model_metrics(model_id=None):
    """
    Display metrics for a specific model or all models.
    
    Args:
        model_id (str, optional): Model ID to display metrics for. If None, shows metrics for all models.
    """
    # Get models
    models = get_models()
    
    if not models:
        st.info("No models available.")
        return
    
    # Filter to specific model if requested
    if model_id:
        models = [model for model in models if model.get('id') == model_id]
        
        if not models:
            st.warning(f"Model with ID '{model_id}' not found.")
            return
    
    # Get theme for styling
    theme = get_current_theme()
    
    # Create layout
    if model_id:
        # Single model view - detailed metrics
        model = models[0]
        
        # Header with model info
        st.markdown(f"## {model.get('name', 'Unknown Model')}")
        st.markdown(f"**Type**: {model.get('type', 'Unknown')}")
        st.markdown(f"**Status**: {model.get('status', 'Unknown')}")
        
        # Performance metrics
        st.markdown("### Performance Metrics")
        
        # Get metrics
        metrics = model.get('metrics', {})
        performance = model.get('performance', {})
        
        # Create columns for metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            create_metric_card(
                label="Accuracy",
                value=performance.get('accuracy', 0) * 100,
                suffix="%",
                precision=1
            )
        
        with col2:
            create_metric_card(
                label="Precision",
                value=performance.get('precision', 0) * 100,
                suffix="%",
                precision=1
            )
        
        with col3:
            create_metric_card(
                label="Recall",
                value=performance.get('recall', 0) * 100,
                suffix="%",
                precision=1
            )
        
        with col4:
            create_metric_card(
                label="F1 Score",
                value=performance.get('f1_score', 0) * 100,
                suffix="%",
                precision=1
            )
        
        # ROC curve if available
        if 'roc_curve' in metrics:
            st.markdown("### ROC Curve")
            
            # Extract ROC curve data
            roc_data = metrics['roc_curve']
            
            # Create ROC curve plot
            fig = go.Figure()
            
            # Add ROC curve
            fig.add_trace(
                go.Scatter(
                    x=roc_data.get('fpr', [0, 1]),
                    y=roc_data.get('tpr', [0, 1]),
                    mode='lines',
                    name='ROC Curve',
                    line=dict(color=theme.get('primary_color', '#4361ee'), width=2)
                )
            )
            
            # Add diagonal line (random classifier)
            fig.add_trace(
                go.Scatter(
                    x=[0, 1],
                    y=[0, 1],
                    mode='lines',
                    name='Random',
                    line=dict(color='gray', width=2, dash='dash')
                )
            )
            
            # Update layout
            fig.update_layout(
                title=f"ROC Curve (AUC: {metrics.get('auc', 0):.3f})",
                xaxis=dict(title='False Positive Rate'),
                yaxis=dict(title='True Positive Rate'),
                legend=dict(x=0.6, y=0.1),
                margin=dict(l=0, r=0, t=30, b=0),
                height=400,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Model configuration
        st.markdown("### Model Configuration")
        
        # Get configuration
        config = model.get('config', {})
        
        if config:
            # Display configuration parameters
            config_df = pd.DataFrame({
                'Parameter': list(config.keys()),
                'Value': list(config.values())
            })
            
            st.dataframe(config_df, hide_index=True)
        else:
            st.info("No configuration data available.")
        
    else:
        # Multiple models view - comparison metrics
        st.markdown("## Model Comparison")
        
        # Create a DataFrame for model metrics
        model_data = []
        
        for model in models:
            # Get performance metrics
            performance = model.get('performance', {})
            
            # Add to data
            model_data.append({
                'model': model.get('name', 'Unknown'),
                'type': model.get('type', 'Unknown'),
                'status': model.get('status', 'Unknown'),
                'accuracy': performance.get('accuracy', 0),
                'precision': performance.get('precision', 0),
                'recall': performance.get('recall', 0),
                'f1_score': performance.get('f1_score', 0)
            })
        
        # Convert to DataFrame
        model_df = pd.DataFrame(model_data)
        
        # Create model comparison chart
        from components.charts import create_model_comparison_chart
        fig = create_model_comparison_chart(model_df, height=500)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Model details table
        st.markdown("### Model Details")
        
        # Create a more detailed table
        model_details = []
        
        for model in models:
            # Add to data
            model_details.append({
                'Name': model.get('name', 'Unknown'),
                'Type': model.get('type', 'Unknown'),
                'Status': model.get('status', 'Unknown'),
                'Training Time': model.get('training_time', 'N/A'),
                'Created': model.get('created_at', 'N/A')
            })
        
        # Convert to DataFrame
        details_df = pd.DataFrame(model_details)
        
        # Display table
        st.dataframe(details_df, hide_index=True)

def display_anomaly_metrics(anomaly_id=None):
    """
    Display metrics for a specific anomaly or summary metrics for all anomalies.
    
    Args:
        anomaly_id (str, optional): Anomaly ID to display metrics for. If None, shows summary metrics.
    """
    # Get anomalies
    anomalies = get_anomalies(limit=1000)
    
    if not anomalies:
        st.info("No anomalies available.")
        return
    
    # Get theme for styling
    theme = get_current_theme()
    
    # Filter to specific anomaly if requested
    if anomaly_id:
        filtered_anomalies = [anomaly for anomaly in anomalies if anomaly.get('id') == anomaly_id]
        
        if not filtered_anomalies:
            st.warning(f"Anomaly with ID '{anomaly_id}' not found.")
            return
        
        anomaly = filtered_anomalies[0]
        
        # Header with anomaly info
        st.markdown(f"## Anomaly Details: {anomaly_id[:8]}...")
        
        # Create columns for basic info
        col1, col2, col3 = st.columns(3)
        
        with col1:
            create_metric_card(
                label="Anomaly Score",
                value=anomaly.get('score', 0) * 100,
                suffix="%",
                precision=1
            )
        
        with col2:
            # Get severity from analysis if available
            severity = "Unknown"
            if anomaly.get('analysis') and isinstance(anomaly['analysis'], dict):
                severity = anomaly['analysis'].get('severity', "Unknown")
                
            st.markdown(f"**Severity**: {severity}")
            st.markdown(f"**Status**: {anomaly.get('status', 'Unknown')}")
        
        with col3:
            # Format timestamp
            timestamp = anomaly.get('timestamp', '')
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    formatted_time = timestamp
            else:
                formatted_time = str(timestamp)
                
            st.markdown(f"**Detected**: {formatted_time}")
            st.markdown(f"**Model**: {anomaly.get('model', 'Unknown')}")
        
        # Anomaly details
        st.markdown("### Anomaly Features")
        
        # Get features
        features = anomaly.get('features', {})
        
        if features and isinstance(features, dict):
            # Display feature values
            feature_df = pd.DataFrame({
                'Feature': list(features.keys()),
                'Value': list(features.values())
            })
            
            st.dataframe(feature_df, hide_index=True)
            
            # Feature visualization if there are numeric features
            numeric_features = {}
            for key, value in features.items():
                if isinstance(value, (int, float)):
                    numeric_features[key] = value
            
            if numeric_features:
                st.markdown("#### Feature Visualization")
                
                # Create radar chart for features
                fig = go.Figure()
                
                # Add radar chart
                fig.add_trace(
                    go.Scatterpolar(
                        r=list(numeric_features.values()),
                        theta=list(numeric_features.keys()),
                        fill='toself',
                        name='Feature Values',
                        line=dict(color=theme.get('primary_color', '#4361ee'))
                    )
                )
                
                # Update layout
                fig.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True,
                            range=[0, max(numeric_features.values()) * 1.2]
                        )
                    ),
                    showlegend=False,
                    margin=dict(l=0, r=0, t=0, b=0),
                    height=300,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No feature data available.")
            
        # Anomaly analysis
        st.markdown("### Analysis Results")
        
        # Get analysis
        analysis = anomaly.get('analysis', {})
        
        if analysis and isinstance(analysis, dict):
            # Display analysis details
            st.markdown(f"**Severity**: {analysis.get('severity', 'Unknown')}")
            
            if 'description' in analysis:
                st.markdown(f"**Description**: {analysis['description']}")
            
            # Additional analysis fields
            additional_fields = {}
            for key, value in analysis.items():
                if key not in ['severity', 'description']:
                    additional_fields[key] = value
            
            if additional_fields:
                st.markdown("#### Additional Analysis")
                
                # Display as a table
                analysis_df = pd.DataFrame({
                    'Field': list(additional_fields.keys()),
                    'Value': [str(v) for v in additional_fields.values()]
                })
                
                st.dataframe(analysis_df, hide_index=True)
        else:
            st.info("No analysis data available.")
    
    else:
        # Summary metrics for all anomalies
        st.markdown("## Anomaly Metrics Summary")
        
        # Count anomalies by severity
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
        
        # Create columns for summary metrics
        col1, col2 = st.columns(2)
        
        with col1:
            # Total anomalies
            create_metric_card(
                label="Total Anomalies",
                value=len(anomalies)
            )
            
            # High severity anomalies
            high_count = severity_counts.get("High", 0) + severity_counts.get("Critical", 0)
            create_metric_card(
                label="High Severity",
                value=high_count,
                color="danger" if high_count > 0 else "primary"
            )
            
            # Create time series chart
            from components.charts import create_time_series_chart
            time_fig = create_time_series_chart(height=300)
            
            st.plotly_chart(time_fig, use_container_width=True)
        
        with col2:
            # Severity distribution
            st.markdown("### Severity Distribution")
            
            # Create data for pie chart
            severity_data = pd.DataFrame({
                'severity': list(severity_counts.keys()),
                'count': list(severity_counts.values())
            })
            
            # Create severity distribution chart
            from components.charts import create_severity_distribution_chart
            severity_fig = create_severity_distribution_chart(severity_data, height=350)
            
            st.plotly_chart(severity_fig, use_container_width=True)
        
        # Recent anomalies
        st.markdown("### Recent Anomalies")
        
        # Create a DataFrame for display
        recent_data = []
        
        for anomaly in anomalies[:10]:  # Show only the 10 most recent
            # Extract severity from analysis if available
            severity = "Unknown"
            if anomaly.get('analysis') and isinstance(anomaly['analysis'], dict):
                severity = anomaly['analysis'].get('severity', "Unknown")
            
            # Format timestamp
            timestamp = anomaly.get('timestamp', '')
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    formatted_time = timestamp
            else:
                formatted_time = str(timestamp)
            
            # Add to data
            recent_data.append({
                'ID': anomaly.get('id', 'Unknown')[:8] + '...',
                'Timestamp': formatted_time,
                'Score': f"{anomaly.get('score', 0):.2f}",
                'Severity': severity,
                'Model': anomaly.get('model', 'Unknown'),
                'Status': anomaly.get('status', 'Unknown')
            })
        
        # Convert to DataFrame
        recent_df = pd.DataFrame(recent_data)
        
        # Display table
        st.dataframe(recent_df, hide_index=True)

def create_metric_dashboard(metrics_dict, title=None):
    """
    Create a dashboard of metrics from a dictionary.
    
    Args:
        metrics_dict (dict): Dictionary of metrics to display
        title (str, optional): Dashboard title. Defaults to None.
    """
    if title:
        st.markdown(f"## {title}")
    
    # Create a grid of metrics
    num_metrics = len(metrics_dict)
    cols_per_row = 3
    
    # Calculate number of rows needed
    num_rows = (num_metrics + cols_per_row - 1) // cols_per_row
    
    # Create metrics in a grid layout
    for row in range(num_rows):
        cols = st.columns(cols_per_row)
        
        for col_idx in range(cols_per_row):
            metric_idx = row * cols_per_row + col_idx
            
            if metric_idx < num_metrics:
                # Get metric key and value
                metric_key = list(metrics_dict.keys())[metric_idx]
                metric_value = metrics_dict[metric_key]
                
                # Display metric
                with cols[col_idx]:
                    create_metric_card(
                        label=metric_key,
                        value=metric_value,
                        suffix="" if isinstance(metric_value, str) else "",
                        precision=2 if isinstance(metric_value, float) else 0
                    )

def display_performance_metrics(data=None, title="Performance Metrics"):
    """
    Display performance metrics in a dashboard layout.
    
    Args:
        data (dict, optional): Performance metrics data. If None, creates demo data.
        title (str, optional): Dashboard title. Defaults to "Performance Metrics".
    """
    # Create demo data if not provided
    if data is None:
        data = create_demo_performance_metrics()
    
    # Display title
    st.markdown(f"## {title}")
    
    # Create layout with columns
    col1, col2 = st.columns(2)
    
    # Get theme for styling
    theme = get_current_theme()
    
    # Display overall performance metrics
    with col1:
        st.markdown("### Overall Performance")
        
        # Extract metrics
        accuracy = data.get('accuracy', 0.85)
        precision = data.get('precision', 0.82)
        recall = data.get('recall', 0.87)
        f1_score = data.get('f1_score', 0.84)
        
        # Create gauge charts for each metric
        fig = make_subplots(
            rows=2, cols=2,
            specs=[[{'type': 'indicator'}, {'type': 'indicator'}],
                   [{'type': 'indicator'}, {'type': 'indicator'}]],
            subplot_titles=("Accuracy", "Precision", "Recall", "F1 Score")
        )
        
        # Add gauges
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=accuracy * 100,
                number={"suffix": "%", "font": {"size": 24}},
                gauge={
                    'axis': {'range': [0, 100], 'tickwidth': 1},
                    'bar': {'color': theme.get('primary_color', '#4361ee')},
                    'steps': [
                        {'range': [0, 60], 'color': 'rgba(255, 0, 0, 0.2)'},
                        {'range': [60, 80], 'color': 'rgba(255, 165, 0, 0.2)'},
                        {'range': [80, 100], 'color': 'rgba(0, 128, 0, 0.2)'}
                    ],
                    'threshold': {
                        'line': {'color': theme.get('primary_color', '#4361ee'), 'width': 4},
                        'thickness': 0.75,
                        'value': accuracy * 100
                    }
                }
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=precision * 100,
                number={"suffix": "%", "font": {"size": 24}},
                gauge={
                    'axis': {'range': [0, 100], 'tickwidth': 1},
                    'bar': {'color': theme.get('primary_color', '#4361ee')},
                    'steps': [
                        {'range': [0, 60], 'color': 'rgba(255, 0, 0, 0.2)'},
                        {'range': [60, 80], 'color': 'rgba(255, 165, 0, 0.2)'},
                        {'range': [80, 100], 'color': 'rgba(0, 128, 0, 0.2)'}
                    ],
                    'threshold': {
                        'line': {'color': theme.get('primary_color', '#4361ee'), 'width': 4},
                        'thickness': 0.75,
                        'value': precision * 100
                    }
                }
            ),
            row=1, col=2
        )
        
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=recall * 100,
                number={"suffix": "%", "font": {"size": 24}},
                gauge={
                    'axis': {'range': [0, 100], 'tickwidth': 1},
                    'bar': {'color': theme.get('primary_color', '#4361ee')},
                    'steps': [
                        {'range': [0, 60], 'color': 'rgba(255, 0, 0, 0.2)'},
                        {'range': [60, 80], 'color': 'rgba(255, 165, 0, 0.2)'},
                        {'range': [80, 100], 'color': 'rgba(0, 128, 0, 0.2)'}
                    ],
                    'threshold': {
                        'line': {'color': theme.get('primary_color', '#4361ee'), 'width': 4},
                        'thickness': 0.75,
                        'value': recall * 100
                    }
                }
            ),
            row=2, col=1
        )
        
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=f1_score * 100,
                number={"suffix": "%", "font": {"size": 24}},
                gauge={
                    'axis': {'range': [0, 100], 'tickwidth': 1},
                    'bar': {'color': theme.get('primary_color', '#4361ee')},
                    'steps': [
                        {'range': [0, 60], 'color': 'rgba(255, 0, 0, 0.2)'},
                        {'range': [60, 80], 'color': 'rgba(255, 165, 0, 0.2)'},
                        {'range': [80, 100], 'color': 'rgba(0, 128, 0, 0.2)'}
                    ],
                    'threshold': {
                        'line': {'color': theme.get('primary_color', '#4361ee'), 'width': 4},
                        'thickness': 0.75,
                        'value': f1_score * 100
                    }
                }
            ),
            row=2, col=2
        )
        
        # Update layout
        fig.update_layout(
            height=500,
            margin=dict(l=30, r=30, t=70, b=30),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Display confusion matrix
    with col2:
        st.markdown("### Confusion Matrix")
        
        # Extract confusion matrix
        confusion_matrix = data.get('confusion_matrix', [
            [85, 15],
            [10, 90]
        ])
        
        # Create heatmap
        labels = ['Normal', 'Anomaly']
        
        # Convert to percentage if the values are large
        if np.sum(confusion_matrix) > 100:
            # Calculate percentages for each row
            row_sums = np.sum(confusion_matrix, axis=1, keepdims=True)
            confusion_pct = np.divide(confusion_matrix, row_sums) * 100
            z_text = [[f"{val:.1f}%" for val in row] for row in confusion_pct]
        else:
            z_text = [[str(val) for val in row] for row in confusion_matrix]
        
        # Create figure
        fig = go.Figure(data=go.Heatmap(
            z=confusion_matrix,
            x=labels,
            y=labels,
            colorscale=[
                [0, 'rgba(255,255,255,0.8)'],
                [0.5, theme.get('primary_color', '#4361ee') + '80'],
                [1, theme.get('primary_color', '#4361ee')]
            ],
            showscale=False,
            text=z_text,
            texttemplate="%{text}",
            textfont={"size": 20}
        ))
        
        # Update layout
        fig.update_layout(
            title="Confusion Matrix",
            xaxis=dict(title="Predicted", tickfont={"size": 14}),
            yaxis=dict(title="Actual", tickfont={"size": 14}),
            height=500,
            margin=dict(l=60, r=30, t=70, b=60),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Display additional metrics
    st.markdown("### Additional Metrics")
    
    # Extract additional metrics
    additional_metrics = data.get('additional_metrics', {})
    
    if additional_metrics:
        # Create columns
        col1, col2, col3 = st.columns(3)
        
        # Create metric cards
        for i, (key, value) in enumerate(additional_metrics.items()):
            with [col1, col2, col3][i % 3]:
                create_metric_card(
                    label=key,
                    value=value,
                    precision=3 if isinstance(value, float) else 0
                )
    else:
        st.info("No additional metrics available.")

# Helper function for creating demo data
def create_demo_performance_metrics():
    """
    Create demo performance metrics data.
    
    Returns:
        dict: Dictionary with demo performance metrics
    """
    # Create data
    data = {
        'accuracy': 0.92,
        'precision': 0.88,
        'recall': 0.87,
        'f1_score': 0.875,
        'confusion_matrix': [
            [85, 15],
            [10, 90]
        ],
        'additional_metrics': {
            'AUC': 0.94,
            'False Positive Rate': 0.08,
            'False Negative Rate': 0.12,
            'Average Precision': 0.91,
            'Training Time (s)': 245,
            'Inference Time (ms)': 12.5
        }
    }
    
    return data

def create_model_performance_radar(model_data, height=400, width=None, metrics=None):
    """
    Create a radar chart for model performance metrics.
    
    Args:
        model_data (dict, pd.DataFrame, or list): Model performance data
        height (int, optional): Chart height. Defaults to 400.
        width (int, optional): Chart width. Defaults to None (auto).
        metrics (list, optional): List of metrics to include. Defaults to None.
        
    Returns:
        plotly.graph_objects.Figure: The radar chart figure
    """
    # Get current theme
    theme = get_current_theme()
    
    # Handle different input types
    import pandas as pd
    
    # Convert list to DataFrame if necessary
    if isinstance(model_data, list):
        # Check if list contains dictionaries with model info
        if model_data and isinstance(model_data[0], dict):
            # Extract model data
            models_list = []
            for model in model_data:
                # Get performance metrics
                performance = model.get('performance', {})
                if not performance:
                    # If no performance key, try to extract metrics directly
                    performance = {k: v for k, v in model.items() 
                                  if k not in ['id', 'name', 'type', 'status', 'created_at', 'updated_at']
                                  and isinstance(v, (int, float))}
                
                # Create model entry with name and metrics
                model_entry = {
                    'model': model.get('name', f"Model {len(models_list)+1}")
                }
                
                # Add performance metrics
                for k, v in performance.items():
                    if isinstance(v, (int, float)):
                        model_entry[k] = v
                
                models_list.append(model_entry)
            
            # Convert to DataFrame
            df = pd.DataFrame(models_list)
        else:
            # Not a valid format, create an empty DataFrame
            df = pd.DataFrame(columns=['model'])
    # Convert dict to DataFrame if necessary
    elif isinstance(model_data, dict):
        # Extract model name and metrics
        if 'name' in model_data:
            model_name = model_data.get('name', 'Model')
        else:
            model_name = 'Model'
        
        # Get performance metrics
        performance = model_data.get('performance', model_data)
        
        # Create DataFrame with a single row
        df = pd.DataFrame([{
            'model': model_name,
            **{k: v for k, v in performance.items() if isinstance(v, (int, float))}
        }])
    else:
        # Assume it's already a DataFrame
        df = model_data
    
    # Check if DataFrame is valid
    if not isinstance(df, pd.DataFrame) or df.empty:
        # Create figure with error message
        fig = go.Figure()
        
        fig.add_annotation(
            text="No valid model data available for radar chart",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14)
        )
        
        fig.update_layout(
            height=height,
            width=width,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        return fig
    
    # If no metrics specified, use common performance metrics
    if metrics is None:
        default_metrics = ['accuracy', 'precision', 'recall', 'f1_score', 'auc', 'specificity']
        # Check if the columns actually exist in the DataFrame
        if hasattr(df, 'columns'):
            metrics = [col for col in default_metrics if col in df.columns]
            
            # If none of the default metrics are found, use all numeric columns except 'model'
            if not metrics:
                metrics = [col for col in df.columns if col != 'model' and 
                          pd.api.types.is_numeric_dtype(df[col])]
        else:
            # If df doesn't have columns attribute, use empty list
            metrics = []
    
    # Ensure we have metrics
    if not metrics:
        # Create figure with error message
        fig = go.Figure()
        
        fig.add_annotation(
            text="No metrics available for radar chart",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14)
        )
        
        fig.update_layout(
            height=height,
            width=width,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        return fig
    
    # Create radar chart
    fig = go.Figure()
    
    # Add trace for each model
    if 'model' in df.columns:
        for model_name in df['model'].unique():
            model_df = df[df['model'] == model_name]
            
            # Extract metric values
            r_values = [model_df.iloc[0][metric] for metric in metrics]
            
            # Add radar trace
            fig.add_trace(
                go.Scatterpolar(
                    r=r_values,
                    theta=metrics,
                    fill='toself',
                    name=model_name,
                    line=dict(color=theme.get('primary_color', '#4361ee'))
                )
            )
    else:
        # If no model column, just use the first row
        r_values = [df.iloc[0][metric] if metric in df.columns else 0 for metric in metrics]
        
        # Add radar trace
        fig.add_trace(
            go.Scatterpolar(
                r=r_values,
                theta=metrics,
                fill='toself',
                name='Model',
                line=dict(color=theme.get('primary_color', '#4361ee'))
            )
        )
    
    # Add radar chart for perfect model (1.0 for all metrics)
    if len(df) <= 1 or ('model' in df.columns and len(df['model'].unique()) == 1):
        fig.add_trace(
            go.Scatterpolar(
                r=[1.0] * len(metrics),
                theta=metrics,
                fill='none',
                name='Perfect Model',
                line=dict(
                    color='rgba(150, 150, 150, 0.8)',
                    dash='dash',
                    width=1
                )
            )
        )
    
    # Update layout
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                tickformat='.0%'
            )
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=80, r=80, t=20, b=20),
        height=height,
        width=width,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig

def create_storage_usage_gauge(usage_percent, storage_type="Local Storage", used_space=None, total_space=None, height=300, width=None):
    """
    Create a gauge chart showing storage usage.
    
    Args:
        usage_percent (float): Percentage of storage used
        storage_type (str, optional): Type of storage. Defaults to "Local Storage".
        used_space (str, optional): Amount of used space (e.g., "500 GB"). Defaults to None.
        total_space (str, optional): Total available space (e.g., "1 TB"). Defaults to None.
        height (int, optional): Chart height. Defaults to 300.
        width (int, optional): Chart width. Defaults to None (auto).
        
    Returns:
        plotly.graph_objects.Figure: The gauge chart figure
    """
    # Get current theme
    theme = get_current_theme()
    
    # Ensure usage_percent is within 0-100
    usage_percent = max(0, min(100, usage_percent))
    
    # Determine color based on usage
    if usage_percent >= 80:
        color = theme.get('error_color', '#f44336')  # Red for high usage
    elif usage_percent >= 60:
        color = theme.get('warning_color', '#ff9100')  # Orange for medium usage
    else:
        color = theme.get('success_color', '#4CAF50')  # Green for low usage
    
    # Determine subtitle text
    if used_space and total_space:
        subtitle = f"{used_space} of {total_space} used"
    else:
        subtitle = f"{usage_percent:.1f}% used"
    
    # Create gauge chart
    fig = go.Figure()
    
    # Add gauge trace
    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=usage_percent,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={
                'text': storage_type,
                'font': {'size': 18, 'color': theme.get('text_color', '#333333')}
            },
            gauge={
                'axis': {
                    'range': [0, 100],
                    'tickwidth': 1,
                    'tickcolor': theme.get('text_color', '#333333'),
                    'ticksuffix': '%'
                },
                'bar': {'color': color},
                'bgcolor': 'rgba(0, 0, 0, 0.05)',
                'borderwidth': 0,
                'steps': [
                    {'range': [0, 60], 'color': 'rgba(76, 175, 80, 0.1)'},  # Green zone
                    {'range': [60, 80], 'color': 'rgba(255, 145, 0, 0.1)'},  # Orange zone
                    {'range': [80, 100], 'color': 'rgba(244, 67, 54, 0.1)'}  # Red zone
                ],
                'threshold': {
                    'line': {'color': color, 'width': 4},
                    'thickness': 0.75,
                    'value': usage_percent
                }
            },
            number={
                'suffix': '%',
                'font': {'size': 26, 'color': color}
            }
        )
    )
    
    # Add subtitle annotation
    fig.add_annotation(
        text=subtitle,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.3,
        showarrow=False,
        font={
            'size': 14,
            'color': theme.get('text_color', '#333333')
        }
    )
    
    # Update layout
    fig.update_layout(
        height=height,
        width=width,
        margin=dict(l=30, r=30, t=30, b=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig