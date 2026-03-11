"""
Slack Alert Channel for Anomaly Detection System

Sends alerts to Slack channels via webhooks.
"""

import json
import logging
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime

from anomaly_detection.alerts.alert_manager import AlertManager


class SlackAlertChannel:
    """
    Slack alert channel for sending notifications to Slack workspaces.

    Supports rich formatting, threading, and different severity levels.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Slack alert channel.

        Args:
            config: Slack configuration containing webhook URLs and settings
        """
        self.config = config
        self.enabled = config.get("enabled", True)
        self.webhook_url = config.get("webhook_url", "")
        self.channel = config.get("channel", "#alerts")
        self.username = config.get("username", "Anomaly Detection Bot")
        self.icon_emoji = config.get("icon_emoji", ":warning:")

        # Severity-specific settings
        self.severity_settings = config.get("severity_settings", {
            "Critical": {
                "color": "danger",
                "icon": ":fire:",
                "mention": True,
                "channels": ["#alerts", "#security"]
            },
            "High": {
                "color": "warning",
                "icon": ":warning:",
                "mention": False,
                "channels": ["#alerts"]
            },
            "Medium": {
                "color": "good",
                "icon": ":bell:",
                "mention": False,
                "channels": ["#alerts"]
            },
            "Low": {
                "color": "#808080",
                "icon": ":information_source:",
                "mention": False,
                "channels": ["#alerts"]
            }
        })

        # Templates
        self.templates = config.get("templates", self._get_default_templates())

        self.logger = logging.getLogger("slack_alert")

        if not self.webhook_url:
            self.logger.warning("No Slack webhook URL configured")
            self.enabled = False

    def _get_default_templates(self) -> Dict[str, str]:
        """Get default Slack message templates."""
        return {
            "single_anomaly": """
🚨 *Anomaly Detected*

*Model:* {model}
*Score:* {score:.3f}
*Severity:* {severity}
*Time:* {timestamp}

*Details:*
{details}

*Original Data:*
```json
{original_data}
```
            """.strip(),

            "multiple_anomalies": """
🚨 *Multiple Anomalies Detected*

*Total Anomalies:* {count}
*Time Range:* {time_range}

*Breakdown by Severity:*
• Critical: {critical_count}
• High: {high_count}
• Medium: {medium_count}
• Low: {low_count}

*Top Anomalies:*
{top_anomalies}

*View full details:* `{command}`
            """.strip(),

            "summary": """
📊 *Anomaly Detection Summary*

*Period:* {period}
*Total Processed:* {total_processed}
*Anomalies Found:* {anomaly_count}
*False Positive Rate:* {false_positive_rate:.2%}

*Model Performance:*
{performance_metrics}

*Next Steps:*
{next_steps}
            """.strip()
        }

    def send_alert(self, subject: str, anomalies: List[Dict[str, Any]],
                   alert_type: str = "single_anomaly") -> bool:
        """
        Send alert to Slack.

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
            # Prepare message based on alert type
            if alert_type == "multiple_anomalies" or len(anomalies) > 1:
                message = self._format_multiple_anomalies(anomalies)
            else:
                message = self._format_single_anomaly(anomalies[0])

            # Get severity settings
            severity = self._get_highest_severity(anomalies)
            severity_config = self.severity_settings.get(severity, self.severity_settings["Medium"])

            # Prepare Slack payload
            payload = {
                "channel": self.channel,
                "username": self.username,
                "icon_emoji": severity_config["icon"],
                "attachments": [{
                    "color": severity_config["color"],
                    "title": subject,
                    "text": message,
                    "footer": "Anomaly Detection System",
                    "ts": datetime.utcnow().timestamp()
                }]
            }

            # Add mentions for critical/high severity
            if severity_config.get("mention", False):
                payload["text"] = "@channel " + subject

            # Send to Slack
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            if response.status_code == 200:
                self.logger.info(f"Slack alert sent successfully for {len(anomalies)} anomalies")
                return True
            else:
                self.logger.error(f"Slack alert failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"Error sending Slack alert: {e}")
            return False

    def _format_single_anomaly(self, anomaly: Dict[str, Any]) -> str:
        """Format a single anomaly for Slack."""
        template = self.templates["single_anomaly"]

        # Format original data (truncate if too long)
        original_data = json.dumps(anomaly.get("original_data", {}), indent=2)
        if len(original_data) > 2000:
            original_data = original_data[:1997] + "..."

        return template.format(
            model=anomaly.get("model", "Unknown"),
            score=anomaly.get("score", 0.0),
            severity=anomaly.get("severity", "Unknown"),
            timestamp=anomaly.get("timestamp", "Unknown"),
            details=self._format_anomaly_details(anomaly),
            original_data=original_data
        )

    def _format_multiple_anomalies(self, anomalies: List[Dict[str, Any]]) -> str:
        """Format multiple anomalies for Slack."""
        template = self.templates["multiple_anomalies"]

        # Calculate statistics
        severity_counts = self._count_by_severity(anomalies)

        # Get time range
        timestamps = [a.get("timestamp") for a in anomalies if a.get("timestamp")]
        if timestamps:
            time_range = f"{min(timestamps)} to {max(timestamps)}"
        else:
            time_range = "Unknown"

        # Format top anomalies
        top_anomalies = []
        sorted_anomalies = sorted(anomalies, key=lambda x: x.get("score", 0), reverse=True)
        for i, anomaly in enumerate(sorted_anomalies[:3]):  # Top 3
            top_anomalies.append(f"{i+1}. {anomaly.get('model', 'Unknown')}: {anomaly.get('score', 0):.3f}")

        top_anomalies_text = "\n".join(top_anomalies)

        return template.format(
            count=len(anomalies),
            time_range=time_range,
            critical_count=severity_counts.get("Critical", 0),
            high_count=severity_counts.get("High", 0),
            medium_count=severity_counts.get("Medium", 0),
            low_count=severity_counts.get("Low", 0),
            top_anomalies=top_anomalies_text,
            command="/anomaly list --limit 10"
        )

    def _format_anomaly_details(self, anomaly: Dict[str, Any]) -> str:
        """Format anomaly details for display."""
        details = anomaly.get("details", {})

        if not details:
            return "No additional details available"

        formatted_details = []
        for key, value in details.items():
            if isinstance(value, (int, float)):
                formatted_details.append(f"• {key}: {value:.3f}")
            else:
                formatted_details.append(f"• {key}: {str(value)[:100]}")

        return "\n".join(formatted_details)

    def _get_highest_severity(self, anomalies: List[Dict[str, Any]]) -> str:
        """Get the highest severity level from a list of anomalies."""
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

    def test_connection(self) -> bool:
        """
        Test Slack webhook connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self.webhook_url:
            return False

        try:
            payload = {
                "channel": self.channel,
                "username": self.username,
                "icon_emoji": ":test_tube:",
                "text": "🧪 *Slack Alert Test*\n\nConnection test from Anomaly Detection System",
                "attachments": [{
                    "color": "good",
                    "text": "If you can see this message, Slack integration is working correctly.",
                    "footer": f"Test sent at {datetime.utcnow().isoformat()}",
                    "ts": datetime.utcnow().timestamp()
                }]
            }

            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            return response.status_code == 200

        except Exception as e:
            self.logger.error(f"Slack connection test failed: {e}")
            return False
