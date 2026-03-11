"""
Models management page for the Anomaly Detection Dashboard.
Allows viewing and managing anomaly detection models using real PostgreSQL data.
"""

import streamlit as st
import json
import pandas as pd
from typing import Dict, List, Any, Optional

from config.theme import get_current_theme
from components.metrics import create_model_performance_radar
from utils.ui_components import loading_animation
from config.settings import add_notification
from services.data_service import get_models
from services.database import execute_query


def render() -> None:
    """Render the models management page."""
    st.markdown('<h1 class="main-header">Models Management</h1>', unsafe_allow_html=True)
    
    # Get model data from database
    models = get_models()
    
    if not models:
        st.warning("No models found in the database. Please initialize your database with sample data or add models manually.")
        return
    
    # Model performance overview
    st.markdown('<h2 class="sub-header">Performance Overview</h2>', unsafe_allow_html=True)
    
    # Create radar chart for model performance
    radar_fig = create_model_performance_radar(models)
    if radar_fig:
        st.plotly_chart(radar_fig, use_container_width=True)
    else:
        st.info("Performance radar chart could not be generated. Make sure there are trained models with performance metrics.")
    
    # Model cards with enhanced styling
    st.markdown('<h2 class="sub-header">Available Models</h2>', unsafe_allow_html=True)
    
    # Calculate overall stats and display them
    render_overall_stats(models)
    
    # Create a model filter
    render_model_filter(models)
    

def render_overall_stats(models: List[Dict[str, Any]]) -> None:
    """Render overall statistics about models."""
    current_theme = get_current_theme()
    
    # Calculate overall stats
    trained_models = [m for m in models if m.get('status') == 'trained']
    
    # Parse performance data if it's stored as JSON string
    total_accuracy = 0
    count = 0
    
    for model in trained_models:
        perf = model.get('performance', {})
        # Handle case where performance is stored as JSON string
        if isinstance(perf, str):
            try:
                perf = json.loads(perf)
            except:
                perf = {}
        
        if isinstance(perf, dict) and 'accuracy' in perf:
            total_accuracy += perf.get('accuracy', 0)
            count += 1
    
    avg_accuracy = total_accuracy / count if count > 0 else 0
    
    # Display overall stats
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {current_theme['primary_color']}20, {current_theme['secondary_color']}10);
              padding: 15px; border-radius: 10px; margin-bottom: 20px; text-align: center;">
        <div style="font-size: 1rem; margin-bottom: 5px;">Overall System Performance</div>
        <div style="font-size: 2rem; font-weight: 700; color: {current_theme['primary_color']};">{avg_accuracy:.1%}</div>
        <div style="font-size: 0.9rem; color: {current_theme['text_color']}cc;">
            Average Accuracy across {len(trained_models)} trained models
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_model_filter(models: List[Dict[str, Any]]) -> None:
    """Render model filtering options and model cards."""
    # Get unique statuses from actual model data
    unique_statuses = set()
    unique_types = set()
    
    for model in models:
        status = model.get('status', 'unknown')
        model_type = model.get('type', 'unknown')
        
        if status:
            unique_statuses.add(status)
        if model_type:
            unique_types.add(model_type)
    
    # Create filter columns
    col1, col2 = st.columns(2)
    
    with col1:
        # Status filter
        status_filter = st.multiselect(
            "Filter by Status",
            list(unique_statuses),
            default=list(unique_statuses)  # Show all by default
        )
    
    with col2:
        # Type filter
        type_filter = st.multiselect(
            "Filter by Type",
            list(unique_types),
            default=list(unique_types)  # Show all by default
        )
    
    # Apply filters
    filtered_models = []
    for model in models:
        model_status = model.get('status', 'unknown')
        model_type = model.get('type', 'unknown')
        
        # Check if model matches filters
        if (not status_filter or model_status in status_filter) and \
           (not type_filter or model_type in type_filter):
            filtered_models.append(model)
    
    # Display count
    st.info(f"Showing {len(filtered_models)} of {len(models)} models")
    
    render_model_cards(filtered_models)


def render_model_cards(models: List[Dict[str, Any]]) -> None:
    """Render cards for each model."""
    current_theme = get_current_theme()
    
    if not models:
        st.info("No models match the current filter criteria.")
        return
    
    # Create columns for layout
    columns = st.columns(3)
    
    # Iterate through models
    for i, model in enumerate(models):
        # Get the appropriate column
        col = columns[i % 3]
        
        with col:
            # Create a styled container for each model
            with st.container():
                # Extract model information
                model_name = model.get("name", "Unknown")
                model_type = model.get("type", "Unknown")
                model_status = model.get("status", "Unknown")
                
                # Parse performance data if it's stored as JSON string
                performance = model.get("performance", {})
                if isinstance(performance, str):
                    try:
                        performance = json.loads(performance)
                    except:
                        performance = {}
                
                # Extract metrics with defaults
                accuracy = performance.get("accuracy", 0) if isinstance(performance, dict) else 0
                precision = performance.get("precision", 0) if isinstance(performance, dict) else 0
                recall = performance.get("recall", 0) if isinstance(performance, dict) else 0
                f1_score = performance.get("f1", 0) if isinstance(performance, dict) else 0
                
                # Training time
                training_time = model.get("training_time", "N/A")
                
                # Determine status styling
                if model_status == "trained":
                    status_icon = "✓"
                    badge_color = current_theme['success_color']
                elif model_status == "training":
                    status_icon = "⟳"
                    badge_color = current_theme['warning_color']
                else:
                    status_icon = "✗"
                    badge_color = current_theme['error_color']
                
                # Model card styling
                st.markdown(f"""
                <div style="background: {current_theme['card_bg']}; 
                           border-radius: 10px; 
                           padding: 20px; 
                           margin-bottom: 10px; 
                           border-left: 4px solid {current_theme['primary_color']}; 
                           box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
                    <h3 style="color: {current_theme['primary_color']}; margin: 0 0 10px 0; font-size: 1.3rem;">
                        {model_name.replace('_', ' ').title()}
                    </h3>
                    <span style="background-color: {badge_color}20; 
                                color: {badge_color}; 
                                padding: 5px 12px; 
                                border-radius: 20px; 
                                font-size: 0.85rem; 
                                font-weight: 500;">
                        {status_icon} {model_status.title()}
                    </span>
                </div>
                """, unsafe_allow_html=True)
                
                # Model details in the container
                st.write(f"**Type:** {model_type.replace('_', ' ').title()}")
                
                # Show metrics for trained models
                if model_status == "trained" and any([accuracy > 0, precision > 0, recall > 0, f1_score > 0]):
                    st.markdown("**Performance Metrics:**")
                    
                    # Use metric display for clean formatting
                    if accuracy > 0:
                        st.metric("Accuracy", f"{accuracy:.1%}", label_visibility="visible")
                    if precision > 0:
                        st.metric("Precision", f"{precision:.1%}", label_visibility="visible")
                    if recall > 0:
                        st.metric("Recall", f"{recall:.1%}", label_visibility="visible")
                    if f1_score > 0:
                        st.metric("F1 Score", f"{f1_score:.1%}", label_visibility="visible")
                
                st.write(f"**Training Time:** {training_time}")
                
                # Progress bar for trained models
                if model_status == "trained" and accuracy > 0:
                    st.progress(accuracy, text=f"Overall Performance: {accuracy:.1%}")
                
                # Action buttons
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.button("📊 Details", key=f"details_{model_name}_{i}"):
                        st.session_state[f'show_details_{model_name}'] = True
                
                with col_btn2:
                    if model_status == "trained":
                        if st.button("🔄 Retrain", key=f"retrain_{model_name}_{i}"):
                            st.info(f"Retraining {model_name}... (Feature coming soon)")
                    else:
                        if st.button("▶️ Train", key=f"train_{model_name}_{i}"):
                            st.info(f"Training {model_name}... (Feature coming soon)")
                
                st.markdown("---")
    
    # Show model details outside of the columns
    for model in models:
        model_name = model.get("name", "Unknown")
        if st.session_state.get(f'show_details_{model_name}', False):
            view_model_details(model)
            if st.button(f"Close {model_name} Details", key=f"close_{model_name}"):
                st.session_state[f'show_details_{model_name}'] = False
                st.rerun()


def view_model_details(model: Dict[str, Any]) -> None:
    """Display detailed information about a model in a modal-like container."""
    st.markdown("---")
    st.markdown(f"### 📋 {model.get('name', 'Model')} Details")
    
    # Basic Information and Configuration side by side
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Basic Information")
        st.write(f"**Name:** {model.get('name', 'Unknown')}")
        st.write(f"**Type:** {model.get('type', 'Unknown')}")
        st.write(f"**Status:** {model.get('status', 'Unknown')}")
        st.write(f"**Training Time:** {model.get('training_time', 'N/A')}")
    
    with col2:
        st.markdown("#### Configuration")
        config = model.get('config', {})
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except:
                config = {}
        
        if config:
            st.json(config)
        else:
            st.write("No configuration available")
    
    # Performance Metrics
    st.markdown("#### Performance Metrics")
    performance = model.get('performance', {})
    if isinstance(performance, str):
        try:
            performance = json.loads(performance)
        except:
            performance = {}
    
    if performance and isinstance(performance, dict):
        # Create a nice table
        metrics_data = []
        for metric, value in performance.items():
            if isinstance(value, (int, float)):
                metrics_data.append({
                    'Metric': metric.replace('_', ' ').title(),
                    'Value': f"{value:.4f}",
                    'Percentage': f"{value:.1%}"
                })
        
        if metrics_data:
            df = pd.DataFrame(metrics_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.write("No valid performance metrics available")
    else:
        st.write("No performance metrics available")
    
    # Additional details
    if 'created_at' in model:
        st.write(f"**Created:** {model['created_at']}")
    if 'updated_at' in model:
        st.write(f"**Last Updated:** {model['updated_at']}")
    
    st.markdown("---")


if __name__ == "__main__":
    render()