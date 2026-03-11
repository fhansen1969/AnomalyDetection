"""
Microsoft Teams Alert Channel for Anomaly Detection System

Sends alerts to Microsoft Teams channels via webhooks.
"""

import json
import logging
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime

from anomaly_detection.alerts.alert_manager import AlertManager


class TeamsAlertChannel:
    """
    Microsoft Teams alert channel for sending notifications to Teams channels.

    Supports adaptive cards, rich formatting, and different severity levels.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Teams alert channel.

        Args:
            config: Teams configuration containing webhook URLs and settings
        """
        self.config = config
        self.enabled = config.get("enabled", True)
        self.webhook_url = config.get("webhook_url", "")
        self.team_name = config.get("team_name", "Security Team")
        self.channel_name = config.get("channel_name", "Anomaly Alerts")

        # Severity-specific settings
        self.severity_settings = config.get("severity_settings", self._get_default_severity_settings())

        # Message templates
        self.templates = config.get("templates", self._get_default_templates())

        # Adaptive card configuration
        self.use_adaptive_cards = config.get("use_adaptive_cards", True)
        self.include_actions = config.get("include_actions", True)
        self.action_buttons = config.get("action_buttons", self._get_default_action_buttons())

        self.logger = logging.getLogger("teams_alert")

        if not self.webhook_url:
            self.logger.warning("No Teams webhook URL configured")
            self.enabled = False

    def _get_default_severity_settings(self) -> Dict[str, Dict[str, Any]]:
        """Get default severity settings for Teams."""
        return {
            "Critical": {
                "color": "attention",  # Red
                "icon": "🚨",
                "mention": True,
                "priority": "high"
            },
            "High": {
                "color": "warning",  # Orange
                "icon": "⚠️",
                "mention": False,
                "priority": "normal"
            },
            "Medium": {
                "color": "accent",  # Blue
                "icon": "ℹ️",
                "mention": False,
                "priority": "normal"
            },
            "Low": {
                "color": "good",  # Green
                "icon": "📊",
                "mention": False,
                "priority": "low"
            }
        }

    def _get_default_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get default message templates."""
        return {
            "single_anomaly": {
                "title": "🚨 Anomaly Detected",
                "text": "**Model:** {model}\n**Score:** {score:.3f}\n**Severity:** {severity}\n**Time:** {timestamp}",
                "facts": [
                    {"name": "Model", "value": "{model}"},
                    {"name": "Score", "value": "{score:.3f}"},
                    {"name": "Severity", "value": "{severity}"},
                    {"name": "Timestamp", "value": "{timestamp}"}
                ]
            },
            "multiple_anomalies": {
                "title": "🚨 Multiple Anomalies Detected",
                "text": "**Total Anomalies:** {count}\n**Time Range:** {time_range}",
                "facts": [
                    {"name": "Total Anomalies", "value": "{count}"},
                    {"name": "Critical", "value": "{critical_count}"},
                    {"name": "High", "value": "{high_count}"},
                    {"name": "Medium", "value": "{medium_count}"},
                    {"name": "Low", "value": "{low_count}"}
                ]
            }
        }

    def _get_default_action_buttons(self) -> List[Dict[str, Any]]:
        """Get default action buttons for adaptive cards."""
        return [
            {
                "type": "Action.OpenUrl",
                "title": "View Dashboard",
                "url": "https://your-monitoring-system.com/dashboard"
            },
            {
                "type": "Action.OpenUrl",
                "title": "View Details",
                "url": "https://your-anomaly-system.com/anomalies/{anomaly_id}"
            },
            {
                "type": "Action.Submit",
                "title": "Acknowledge",
                "data": {"action": "acknowledge", "anomaly_id": "{anomaly_id}"}
            }
        ]

    def send_alert(self, subject: str, anomalies: List[Dict[str, Any]],
                   alert_type: str = "single_anomaly") -> bool:
        """
        Send alert to Microsoft Teams.

        Args:
            subject: Alert subject/title
            anomalies: List of anomaly objects
            alert_type: Type of alert template to use

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled or not self.webhook_url:
            return False

        if not anomalies:
            return True

        try:
            # Create message payload
            if self.use_adaptive_cards:
                payload = self._create_adaptive_card(subject, anomalies, alert_type)
            else:
                payload = self._create_simple_message(subject, anomalies, alert_type)

            # Send to Teams
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            if response.status_code == 200:
                self.logger.info(f"Teams alert sent successfully for {len(anomalies)} anomalies")
                return True
            else:
                self.logger.error(f"Teams alert failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"Error sending Teams alert: {e}")
            return False

    def _create_adaptive_card(self, subject: str, anomalies: List[Dict[str, Any]],
                            alert_type: str) -> Dict[str, Any]:
        """Create an adaptive card payload for Teams."""
        # Get severity and template
        severity = self._get_highest_severity(anomalies)
        severity_config = self.severity_settings.get(severity, self.severity_settings["Medium"])
        template = self.templates.get(alert_type, self.templates["single_anomaly"])

        # Format content based on alert type
        if alert_type == "multiple_anomalies" or len(anomalies) > 1:
            card_content = self._format_multiple_anomalies_adaptive(anomalies, template, severity_config)
        else:
            card_content = self._format_single_anomaly_adaptive(anomalies[0], template, severity_config)

        # Create adaptive card
        adaptive_card = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": card_content["body"],
                    "actions": card_content.get("actions", [])
                }
            }]
        }

        # Add @mention for critical/high severity
        if severity_config.get("mention", False):
            adaptive_card["text"] = f"@{self.team_name} {subject}"

        return adaptive_card

    def _format_single_anomaly_adaptive(self, anomaly: Dict[str, Any],
                                      template: Dict[str, Any],
                                      severity_config: Dict[str, Any]) -> Dict[str, Any]:
        """Format single anomaly as adaptive card."""
        # Create card body
        body = [
            {
                "type": "TextBlock",
                "size": "Medium",
                "weight": "Bolder",
                "text": f"{severity_config['icon']} {template['title']}",
                "color": severity_config["color"]
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": fact["name"], "value": fact["value"].format(**anomaly)}
                    for fact in template["facts"]
                ]
            }
        ]

        # Add details section
        if anomaly.get("details"):
            details = anomaly["details"]
            if isinstance(details, dict):
                body.append({
                    "type": "TextBlock",
                    "text": "**Details:**",
                    "weight": "Bolder"
                })

                for key, value in list(details.items())[:5]:  # Limit to 5 details
                    body.append({
                        "type": "TextBlock",
                        "text": f"• **{key}:** {str(value)[:100]}",
                        "wrap": True
                    })

        # Add actions
        actions = []
        if self.include_actions:
            for button in self.action_buttons:
                action = button.copy()
                # Replace placeholders
                if "url" in action:
                    action["url"] = action["url"].format(anomaly_id=anomaly.get("id", ""))
                if "data" in action and isinstance(action["data"], dict):
                    action["data"]["anomaly_id"] = anomaly.get("id", "")
                actions.append(action)

        return {"body": body, "actions": actions}

    def _format_multiple_anomalies_adaptive(self, anomalies: List[Dict[str, Any]],
                                          template: Dict[str, Any],
                                          severity_config: Dict[str, Any]) -> Dict[str, Any]:
        """Format multiple anomalies as adaptive card."""
        # Calculate statistics
        severity_counts = self._count_by_severity(anomalies)

        # Get time range
        timestamps = [a.get("timestamp") for a in anomalies if a.get("timestamp")]
        time_range = "Unknown"
        if timestamps:
            time_range = f"{min(timestamps)} to {max(timestamps)}"

        # Create card body
        body = [
            {
                "type": "TextBlock",
                "size": "Medium",
                "weight": "Bolder",
                "text": f"{severity_config['icon']} {template['title']}",
                "color": severity_config["color"]
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": fact["name"], "value": fact["value"].format(
                        count=len(anomalies),
                        time_range=time_range,
                        critical_count=severity_counts.get("Critical", 0),
                        high_count=severity_counts.get("High", 0),
                        medium_count=severity_counts.get("Medium", 0),
                        low_count=severity_counts.get("Low", 0)
                    )}
                    for fact in template["facts"]
                ]
            }
        ]

        # Add top anomalies
        body.append({
            "type": "TextBlock",
            "text": "**Top Anomalies:**",
            "weight": "Bolder"
        })

        sorted_anomalies = sorted(anomalies, key=lambda x: x.get("score", 0), reverse=True)
        for i, anomaly in enumerate(sorted_anomalies[:3]):  # Top 3
            body.append({
                "type": "TextBlock",
                "text": f"{i+1}. {anomaly.get('model', 'Unknown')}: {anomaly.get('score', 0):.3f}",
                "wrap": True
            })

        # Add actions
        actions = []
        if self.include_actions:
            actions.append({
                "type": "Action.OpenUrl",
                "title": "View All Anomalies",
                "url": "https://your-anomaly-system.com/anomalies"
            })

        return {"body": body, "actions": actions}

    def _create_simple_message(self, subject: str, anomalies: List[Dict[str, Any]],
                             alert_type: str) -> Dict[str, Any]:
        """Create a simple message payload (fallback)."""
        severity = self._get_highest_severity(anomalies)
        severity_config = self.severity_settings.get(severity, self.severity_settings["Medium"])

        if len(anomalies) > 1:
            text = f"{severity_config['icon']} **{subject}**\n\n"
            text += f"**Total Anomalies:** {len(anomalies)}\n"

            severity_counts = self._count_by_severity(anomalies)
            text += f"**Breakdown:** Critical: {severity_counts.get('Critical', 0)}, "
            text += f"High: {severity_counts.get('High', 0)}, "
            text += f"Medium: {severity_counts.get('Medium', 0)}, "
            text += f"Low: {severity_counts.get('Low', 0)}\n\n"

            # Top anomalies
            sorted_anomalies = sorted(anomalies, key=lambda x: x.get("score", 0), reverse=True)
            text += "**Top Anomalies:**\n"
            for i, anomaly in enumerate(sorted_anomalies[:3]):
                text += f"{i+1}. {anomaly.get('model', 'Unknown')}: {anomaly.get('score', 0):.3f}\n"
        else:
            anomaly = anomalies[0]
            text = f"{severity_config['icon']} **{subject}**\n\n"
            text += f"**Model:** {anomaly.get('model', 'Unknown')}\n"
            text += f"**Score:** {anomaly.get('score', 0):.3f}\n"
            text += f"**Severity:** {anomaly.get('severity', 'Unknown')}\n"
            text += f"**Time:** {anomaly.get('timestamp', 'Unknown')}"

        return {
            "title": subject,
            "text": text,
            "themeColor": self._get_theme_color(severity_config["color"])
        }

    def _get_highest_severity(self, anomalies: List[Dict[str, Any]]) -> str:
        """Get the highest severity level from anomalies."""
        severity_order = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}

        highest_severity = "Low"
        highest_score = 0

        for anomaly in anomalies:
            severity = anomaly.get("severity", "Low")
            score = severity_order.get(severity, 0)
            if score > highest_score:
                highest_severity = severity
                highest_score = score

        return highest_severity

    def _count_by_severity(self, anomalies: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count anomalies by severity level."""
        counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}

        for anomaly in anomalies:
            severity = anomaly.get("severity", "Low")
            if severity in counts:
                counts[severity] += 1

        return counts

    def _get_theme_color(self, color_name: str) -> str:
        """Convert color name to Teams theme color hex."""
        color_map = {
            "attention": "FF0000",  # Red
            "warning": "FFA500",   # Orange
            "accent": "0078D4",    # Blue
            "good": "00CC44"       # Green
        }
        return color_map.get(color_name, "0078D4")

    def test_connection(self) -> bool:
        """
        Test Teams webhook connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self.webhook_url:
            return False

        try:
            test_payload = {
                "title": "🧪 Teams Alert Test",
                "text": "Connection test from Anomaly Detection System",
                "themeColor": "0078D4"
            }

            response = requests.post(
                self.webhook_url,
                json=test_payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            return response.status_code == 200

        except Exception as e:
            self.logger.error(f"Teams connection test failed: {e}")
            return False
