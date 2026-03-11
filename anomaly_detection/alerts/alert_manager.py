"""
Alert manager for the anomaly detection system.

This module provides functionality to generate and send alerts for detected anomalies.
"""

import logging
import json
import datetime
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Any, Optional


class AlertManager:
    """
    Alert manager for the anomaly detection system.
    
    This class provides methods to generate and send alerts for detected anomalies
    through various channels (email, Slack, webhook, etc.).
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize alert manager with configuration.
        
        Args:
            config: Alert configuration
        """
        self.config = config
        self.enabled = config.get("enabled", True)
        self.threshold = config.get("threshold", 0.75)
        self.logger = logging.getLogger("alert_manager")
        
        # Configure alert types
        self.alert_types = {}
        
        for alert_config in config.get("types", []):
            alert_type = alert_config.get("name")
            
            if alert_type and alert_config.get("enabled", False):
                self.alert_types[alert_type] = alert_config
        
        self.logger.info(f"Initialized alert manager with {len(self.alert_types)} alert types")
    
    def generate_alerts(self, anomalies: List[Dict[str, Any]]) -> None:
        """
        Generate and send alerts for detected anomalies.
        
        Args:
            anomalies: List of anomaly objects
        """
        if not self.enabled:
            self.logger.info("Alert manager is disabled")
            return
        
        if not anomalies:
            return
        
        # Filter anomalies by score threshold
        high_score_anomalies = [a for a in anomalies if a.get("score", 0) >= self.threshold]
        
        if not high_score_anomalies:
            self.logger.info(f"No anomalies with score >= {self.threshold}")
            return
        
        self.logger.info(f"Generating alerts for {len(high_score_anomalies)} high-score anomalies")
        
        # Generate alert content
        alert_subject = f"Security Alert: {len(high_score_anomalies)} High-Score Anomalies Detected"
        
        alert_text = self._generate_alert_text(high_score_anomalies)
        alert_html = self._generate_alert_html(high_score_anomalies)
        alert_json = self._generate_alert_json(high_score_anomalies)
        
        # Send alerts via all configured channels
        for alert_type, alert_config in self.alert_types.items():
            try:
                if alert_type == "email":
                    self._send_email_alert(alert_config, alert_subject, alert_text, alert_html)
                elif alert_type == "slack":
                    self._send_slack_alert(alert_config, alert_subject, alert_text, alert_json)
                elif alert_type == "webhook":
                    self._send_webhook_alert(alert_config, alert_subject, alert_json)
                elif alert_type == "console":
                    self._send_console_alert(alert_config, alert_subject, alert_text)
                else:
                    self.logger.warning(f"Unknown alert type: {alert_type}")
            except Exception as e:
                self.logger.error(f"Error sending {alert_type} alert: {str(e)}")
    
    def _generate_alert_text(self, anomalies: List[Dict[str, Any]]) -> str:
        """
        Generate plain text alert content.
        
        Args:
            anomalies: List of anomaly objects
            
        Returns:
            Plain text alert content
        """
        text = f"Security Alert: {len(anomalies)} High-Score Anomalies Detected\n\n"
        text += f"Time: {datetime.datetime.utcnow().isoformat()}\n\n"
        
        for i, anomaly in enumerate(anomalies[:10]):  # Limit to top 10
            text += f"Anomaly {i+1}:\n"
            text += f"  ID: {anomaly.get('id')}\n"
            text += f"  Score: {anomaly.get('score', 0):.2f}\n"
            text += f"  Model: {anomaly.get('model', 'unknown')}\n"
            text += f"  Timestamp: {anomaly.get('timestamp', '')}\n"
            
            # Add analysis info if available
            if "analysis" in anomaly:
                analysis = anomaly["analysis"]
                text += f"  Analysis:\n"
                text += f"    Severity: {analysis.get('severity', 'unknown')}\n"
                text += f"    Description: {analysis.get('description', 'No description')}\n"
            
            text += "\n"
        
        if len(anomalies) > 10:
            text += f"... and {len(anomalies) - 10} more anomalies\n"
        
        return text
    
    def _generate_alert_html(self, anomalies: List[Dict[str, Any]]) -> str:
        """
        Generate HTML alert content.
        
        Args:
            anomalies: List of anomaly objects
            
        Returns:
            HTML alert content
        """
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: #f8d7da; padding: 10px; border-radius: 5px; }}
                .anomaly {{ border: 1px solid #ddd; padding: 10px; margin: 10px 0; border-radius: 5px; }}
                .high {{ background-color: #f8d7da; }}
                .medium {{ background-color: #fff3cd; }}
                .low {{ background-color: #d1ecf1; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>Security Alert: {len(anomalies)} High-Score Anomalies Detected</h2>
                <p>Time: {datetime.datetime.utcnow().isoformat()}</p>
            </div>
        """
        
        for i, anomaly in enumerate(anomalies[:10]):  # Limit to top 10
            score = anomaly.get('score', 0)
            severity_class = "high" if score >= 0.8 else "medium" if score >= 0.6 else "low"
            
            html += f"""
            <div class="anomaly {severity_class}">
                <h3>Anomaly {i+1}</h3>
                <p><strong>ID:</strong> {anomaly.get('id')}</p>
                <p><strong>Score:</strong> {score:.2f}</p>
                <p><strong>Model:</strong> {anomaly.get('model', 'unknown')}</p>
                <p><strong>Timestamp:</strong> {anomaly.get('timestamp', '')}</p>
            """
            
            # Add analysis info if available
            if "analysis" in anomaly:
                analysis = anomaly["analysis"]
                html += f"""
                <div>
                    <h4>Analysis</h4>
                    <p><strong>Severity:</strong> {analysis.get('severity', 'unknown')}</p>
                    <p><strong>Description:</strong> {analysis.get('description', 'No description')}</p>
                    <p><strong>Recommendation:</strong> {analysis.get('recommendation', 'No recommendation')}</p>
                </div>
                """
            
            html += "</div>"
        
        if len(anomalies) > 10:
            html += f"<p>... and {len(anomalies) - 10} more anomalies</p>"
        
        html += """
        </body>
        </html>
        """
        
        return html
    
    def _generate_alert_json(self, anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate JSON alert content.
        
        Args:
            anomalies: List of anomaly objects
            
        Returns:
            JSON alert content
        """
        return {
            "alert_type": "security_anomaly",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "count": len(anomalies),
            "anomalies": anomalies[:10],  # Limit to top 10
            "has_more": len(anomalies) > 10
        }
    
    def _send_email_alert(self, config: Dict[str, Any], subject: str, 
                         text_content: str, html_content: str) -> None:
        """
        Send email alert.
        
        Args:
            config: Email alert configuration
            subject: Alert subject
            text_content: Plain text alert content
            html_content: HTML alert content
        """
        recipients = config.get("recipients", [])
        
        if not recipients:
            self.logger.warning("No email recipients configured")
            return
        
        smtp_server = config.get("smtp_server")
        smtp_port = config.get("smtp_port", 587)
        smtp_user = config.get("smtp_user")
        smtp_password = config.get("smtp_password")
        
        if not smtp_server or not smtp_user:
            self.logger.warning("Incomplete SMTP configuration")
            return
        
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = ", ".join(recipients)
        
        # Attach text and HTML parts
        part1 = MIMEText(text_content, "plain")
        part2 = MIMEText(html_content, "html")
        
        msg.attach(part1)
        msg.attach(part2)
        
        # Send email
        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            
            if smtp_password:
                server.login(smtp_user, smtp_password)
            
            server.sendmail(smtp_user, recipients, msg.as_string())
            server.quit()
            
            self.logger.info(f"Sent email alert to {len(recipients)} recipients")
        except Exception as e:
            self.logger.error(f"Error sending email: {str(e)}")
            raise
    
    def _send_slack_alert(self, config: Dict[str, Any], subject: str, 
                         text_content: str, json_content: Dict[str, Any]) -> None:
        """
        Send Slack alert.
        
        Args:
            config: Slack alert configuration
            subject: Alert subject
            text_content: Plain text alert content
            json_content: JSON alert content
        """
        webhook_url = config.get("webhook_url")
        channel = config.get("channel")
        
        if not webhook_url:
            self.logger.warning("No Slack webhook URL configured")
            return
        
        # Create Slack message
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": subject
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Time:* {datetime.datetime.utcnow().isoformat()}"
                }
            },
            {
                "type": "divider"
            }
        ]
        
        # Add anomalies
        for i, anomaly in enumerate(json_content.get("anomalies", [])[:5]):  # Limit to top 5 for Slack
            score = anomaly.get('score', 0)
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Anomaly {i+1}*\n"
                        f"*Score:* {score:.2f}\n"
                        f"*Model:* {anomaly.get('model', 'unknown')}\n"
                        f"*ID:* {anomaly.get('id')}"
                    )
                }
            })
        
        # Add footer
        if json_content.get("has_more", False):
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"... and {json_content.get('count', 0) - 5} more anomalies"
                    }
                ]
            })
        
        # Create payload
        payload = {
            "blocks": blocks,
            "text": subject  # Fallback text
        }
        
        if channel:
            payload["channel"] = channel
        
        # Send to Slack
        try:
            response = requests.post(
                webhook_url,
                json=payload
            )
            
            if response.status_code != 200:
                self.logger.error(f"Error sending Slack alert: {response.text}")
                raise ValueError(f"Slack API error: {response.text}")
            
            self.logger.info("Sent Slack alert")
        except Exception as e:
            self.logger.error(f"Error sending Slack alert: {str(e)}")
            raise
    
    def _send_webhook_alert(self, config: Dict[str, Any], subject: str, 
                           json_content: Dict[str, Any]) -> None:
        """
        Send webhook alert.
        
        Args:
            config: Webhook alert configuration
            subject: Alert subject
            json_content: JSON alert content
        """
        webhook_url = config.get("url")
        method = config.get("method", "POST")
        headers = config.get("headers", {})
        
        if not webhook_url:
            self.logger.warning("No webhook URL configured")
            return
        
        # Add alert subject to JSON payload
        payload = json_content.copy()
        payload["subject"] = subject
        
        # Send to webhook
        try:
            response = requests.request(
                method,
                webhook_url,
                json=payload,
                headers=headers
            )
            
            if response.status_code not in [200, 201, 202, 204]:
                self.logger.error(f"Error sending webhook alert: {response.text}")
                raise ValueError(f"Webhook API error: {response.text}")
            
            self.logger.info(f"Sent webhook alert to {webhook_url}")
        except Exception as e:
            self.logger.error(f"Error sending webhook alert: {str(e)}")
            raise
    
    def _send_console_alert(self, config: Dict[str, Any], subject: str, 
                           text_content: str) -> None:
        """
        Send console alert.
        
        Args:
            config: Console alert configuration
            subject: Alert subject
            text_content: Plain text alert content
        """
        print("\n" + "="*80)
        print(f"SECURITY ALERT: {subject}")
        print("="*80)
        print(text_content)
        print("="*80 + "\n")
        
        self.logger.info("Sent console alert")