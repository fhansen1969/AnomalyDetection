"""
Shared utility functions used across routers.
Extracted from api_services.py.
"""
import json
import logging
import traceback
import yaml
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from fastapi import HTTPException

from api.state import app_state

logger = logging.getLogger("api_services")


def get_default_agent_workflow():
    """Get the default agent workflow structure."""
    return {
        "nodes": [
            "security_analyst",
            "threat_intel",
            "remediation",
            "code_generator",
            "security_review",
            "data_collector"
        ],
        "edges": [
            {"from": "security_analyst", "to": "threat_intel"},
            {"from": "threat_intel", "to": "remediation"},
            {"from": "remediation", "to": "code_generator"},
            {"from": "code_generator", "to": "security_review"},
            {"from": "security_review", "to": "data_collector"}
        ],
        "description": "Multi-agent workflow for comprehensive anomaly analysis"
    }


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from a YAML file."""
    try:
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f)

        if 'config' in config_dict:
            return config_dict['config']
        return config_dict
    except Exception as e:
        logging.error(f"Error loading configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error loading configuration: {str(e)}")


def parse_timestamp(timestamp):
    """Parse timestamp from various formats."""
    if not timestamp:
        return None

    if isinstance(timestamp, datetime):
        return timestamp

    if isinstance(timestamp, str):
        try:
            return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except Exception:
            try:
                return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return None

    return None


def get_anomaly_severity(anomaly):
    """Extract severity from anomaly."""
    if 'severity' in anomaly and anomaly['severity']:
        return anomaly['severity']

    analysis = anomaly.get('analysis', {})

    if isinstance(analysis, str):
        try:
            analysis = json.loads(analysis)
        except Exception:
            analysis = {}

    if isinstance(analysis, dict):
        return analysis.get('severity', 'Unknown')

    score = float(anomaly.get('score', 0))
    if score >= 0.9:
        return "Critical"
    elif score >= 0.8:
        return "High"
    elif score >= 0.6:
        return "Medium"
    else:
        return "Low"


def get_agent_description(agent_name: str) -> str:
    """Get a description for an agent based on its name."""
    descriptions = {
        "security_analyst": "Analyzes anomalies to determine severity, threat identification, and false positive evaluation.",
        "remediation_expert": "Provides actionable steps to address security anomalies including containment, investigation, remediation, and prevention.",
        "reflection_expert": "Critically evaluates security analyses and remediation plans to identify gaps and suggest improvements.",
        "security_critic": "Identifies potential false positives, missing context, or incomplete analyses.",
        "code_generator": "Creates secure, efficient code for remediation actions based on remediation plans.",
        "data_collector": "Identifies additional data needed for thorough investigation of anomalies."
    }
    return descriptions.get(agent_name, "No description available")


def find_correlations(target_anomaly: Dict[str, Any], anomalies: List[Dict[str, Any]],
                      time_window_hours: int = 24, min_score: float = 0.3) -> List[Dict[str, Any]]:
    """Find correlations between a target anomaly and other anomalies."""
    anomaly_id = target_anomaly.get('id')
    anomaly_score = float(target_anomaly.get('score', 0))
    anomaly_model = target_anomaly.get('model')
    anomaly_location = target_anomaly.get('location')
    anomaly_src_ip = target_anomaly.get('src_ip')
    anomaly_dst_ip = target_anomaly.get('dst_ip')
    anomaly_time = parse_timestamp(target_anomaly.get('timestamp'))

    related_anomalies = []

    for a in anomalies:
        if a.get('id') == anomaly_id:
            continue

        correlation_score = 0
        correlation_reasons = []

        if a.get('src_ip') == anomaly_src_ip and anomaly_src_ip:
            correlation_score += 0.4
            correlation_reasons.append("Same source IP")

        if a.get('dst_ip') == anomaly_dst_ip and anomaly_dst_ip:
            correlation_score += 0.3
            correlation_reasons.append("Same destination IP")

        if a.get('location') == anomaly_location:
            correlation_score += 0.2
            correlation_reasons.append("Same location")

        if abs(float(a.get('score', 0)) - anomaly_score) < 0.1:
            correlation_score += 0.2
            correlation_reasons.append("Similar anomaly score")

        if a.get('model') == anomaly_model:
            correlation_score += 0.1
            correlation_reasons.append("Detected by same model")

        if anomaly_time:
            try:
                a_time = parse_timestamp(a.get('timestamp'))
                if a_time:
                    time_diff = abs((a_time - anomaly_time).total_seconds())
                    time_window_seconds = time_window_hours * 3600

                    if time_diff < time_window_seconds:
                        time_correlation = 0.3 * (1 - time_diff / time_window_seconds)
                        correlation_score += time_correlation

                        if time_diff < 3600:
                            correlation_reasons.append("Time proximity (within 1 hour)")
                        elif time_diff < 21600:
                            correlation_reasons.append("Time proximity (within 6 hours)")
                        else:
                            correlation_reasons.append(f"Time proximity (within {int(time_diff/3600)} hours)")
            except Exception:
                pass

        if 'features' in target_anomaly and 'features' in a:
            target_features = target_anomaly.get('features', [])
            a_features = a.get('features', [])

            if target_features and a_features:
                target_set = set(str(f) for f in target_features if f)
                a_set = set(str(f) for f in a_features if f)

                if target_set and a_set:
                    similarity = len(target_set.intersection(a_set)) / len(target_set.union(a_set))
                    if similarity > 0.5:
                        correlation_score += 0.2 * similarity
                        correlation_reasons.append(f"Feature similarity ({similarity:.1%})")

        if correlation_score >= min_score:
            related_anomalies.append({
                'anomaly': a,
                'score': min(correlation_score, 1.0),
                'reasons': correlation_reasons
            })

    related_anomalies.sort(key=lambda x: x['score'], reverse=True)
    return related_anomalies


def calculate_pairwise_correlation(a1: Dict[str, Any], a2: Dict[str, Any]) -> float:
    """Calculate correlation score between two anomalies."""
    try:
        if not a1 or not a2:
            return 0.0

        if not isinstance(a1, dict) or not isinstance(a2, dict):
            logger.warning(f"Invalid anomaly types: {type(a1)}, {type(a2)}")
            return 0.0

        score = 0.0

        try:
            if a1.get('src_ip') == a2.get('src_ip') and a1.get('src_ip'):
                score += 0.4
        except Exception as e:
            logger.debug(f"Error comparing src_ip: {e}")

        try:
            if a1.get('dst_ip') == a2.get('dst_ip') and a1.get('dst_ip'):
                score += 0.3
        except Exception as e:
            logger.debug(f"Error comparing dst_ip: {e}")

        try:
            if a1.get('location') == a2.get('location'):
                score += 0.2
        except Exception as e:
            logger.debug(f"Error comparing location: {e}")

        try:
            score1 = float(a1.get('score', 0))
            score2 = float(a2.get('score', 0))
            if abs(score1 - score2) < 0.1:
                score += 0.2
        except Exception as e:
            logger.debug(f"Error comparing scores: {e}")

        try:
            if a1.get('model') == a2.get('model'):
                score += 0.1
        except Exception as e:
            logger.debug(f"Error comparing models: {e}")

        try:
            t1 = parse_timestamp(a1.get('timestamp'))
            t2 = parse_timestamp(a2.get('timestamp'))
            if t1 and t2:
                time_diff = abs((t1 - t2).total_seconds())
                if time_diff < 3600:
                    score += 0.3
                elif time_diff < 21600:
                    score += 0.2
                elif time_diff < 86400:
                    score += 0.1
        except Exception as e:
            logger.debug(f"Error calculating time proximity: {e}")

        return min(float(score), 1.0)
    except Exception as e:
        logger.error(f"Error in calculate_pairwise_correlation: {e}")
        return 0.0


def build_correlation_matrix(anomalies: List[Dict[str, Any]]) -> Tuple[List[List[float]], List[str]]:
    """Build a correlation matrix for a list of anomalies."""
    try:
        if not anomalies or not isinstance(anomalies, list):
            logger.error(f"Invalid anomalies input: {type(anomalies)}")
            return [[]], []

        n = len(anomalies)
        if n < 2:
            logger.warning(f"Too few anomalies for correlation matrix: {n}")
            return [[]], []

        matrix = [[0.0 for _ in range(n)] for _ in range(n)]
        labels = []

        for i in range(n):
            try:
                anomaly_id = anomalies[i].get('id', f'anomaly_{i}')
                if isinstance(anomaly_id, str):
                    labels.append(anomaly_id[:10])
                else:
                    labels.append(str(anomaly_id)[:10])
            except Exception as e:
                logger.warning(f"Error getting label for anomaly {i}: {e}")
                labels.append(f'anomaly_{i}')

            for j in range(n):
                try:
                    if i == j:
                        matrix[i][j] = 1.0
                    else:
                        correlation = calculate_pairwise_correlation(anomalies[i], anomalies[j])
                        matrix[i][j] = float(correlation)
                except Exception as e:
                    logger.warning(f"Error calculating correlation for ({i},{j}): {e}")
                    matrix[i][j] = 0.0

        return matrix, labels
    except Exception as e:
        logger.error(f"Error in build_correlation_matrix: {e}")
        logger.error(traceback.format_exc())
        return [[]], []


async def store_detection_results(job_id: str, result: Dict[str, Any]):
    """Store detection results in the database."""
    import asyncio
    if app_state.storage_manager:
        try:
            await asyncio.to_thread(
                lambda: _store_detection_results_sync(job_id, result)
            )
        except Exception as e:
            logger.error(f"Error storing detection results: {e}")


def _store_detection_results_sync(job_id: str, result: Dict[str, Any]):
    """Synchronous helper to store detection results."""
    if not app_state.storage_manager:
        return

    try:
        if hasattr(app_state.storage_manager, 'update_job'):
            app_state.storage_manager.update_job(job_id, {
                'status': 'completed',
                'result': result,
                'updated_at': datetime.utcnow().isoformat()
            })
    except Exception as e:
        logger.error(f"Error in _store_detection_results_sync: {e}")
        logger.error(traceback.format_exc())
