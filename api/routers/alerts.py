"""Alert management routes and AlertManager class."""
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

from api.state import app_state
from api.schemas import AlertConfig

logger = logging.getLogger("api_services")
router = APIRouter()


class AlertManager:
    """
    Manager for handling and sending alerts based on detected anomalies.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize alert manager with configuration.

        Args:
            config: Alert configuration
        """
        self.config = config
        self.logger = logging.getLogger("alert_manager")
        self.enabled = config.get("enabled", False)
        self.threshold_score = config.get("threshold_score", 0.8)
        self.channels = config.get("channels", ["console"])

    async def send_alert(self, anomaly: Dict[str, Any]) -> bool:
        """
        Send an alert for a detected anomaly.

        Args:
            anomaly: Detected anomaly

        Returns:
            Success flag
        """
        if not self.enabled:
            return False

        score = anomaly.get("score", 0)
        if score < self.threshold_score:
            return False

        # Format alert message
        alert_message = self._format_alert_message(anomaly)

        # Send to all configured channels
        results = []

        if "console" in self.channels:
            self.logger.warning(f"ALERT: {alert_message}")
            results.append(True)

        if "email" in self.channels and "email" in self.config:
            email_result = await self._send_email_alert(anomaly, alert_message)
            results.append(email_result)

        if "webhook" in self.channels and "webhook" in self.config:
            webhook_result = await self._send_webhook_alert(anomaly, alert_message)
            results.append(webhook_result)

        if "file" in self.channels and "file" in self.config:
            file_result = await self._send_file_alert(anomaly, alert_message)
            results.append(file_result)

        # Broadcast to WebSocket clients
        await self._broadcast_alert(anomaly, alert_message)

        return all(results)

    def _format_alert_message(self, anomaly: Dict[str, Any]) -> str:
        """
        Format an alert message for an anomaly.

        Args:
            anomaly: Detected anomaly

        Returns:
            Formatted alert message
        """
        model = anomaly.get("model", "unknown")
        score = anomaly.get("score", 0)
        timestamp = anomaly.get("timestamp", "unknown")
        details = anomaly.get("details", {})

        if score >= 0.9:
            severity = "CRITICAL"
        elif score >= 0.8:
            severity = "HIGH"
        elif score >= 0.6:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        return f"{severity} anomaly detected by {model} at {timestamp} with score {score:.2f}: {details}"

    async def _send_email_alert(self, anomaly: Dict[str, Any], message: str) -> bool:
        """
        Send an email alert.

        Args:
            anomaly: Detected anomaly
            message: Alert message

        Returns:
            Success flag
        """
        self.logger.info(f"Would send email alert: {message}")
        return True

    async def _send_webhook_alert(self, anomaly: Dict[str, Any], message: str) -> bool:
        """
        Send a webhook alert to a REST API endpoint.

        Args:
            anomaly: Detected anomaly
            message: Alert message

        Returns:
            Success flag
        """
        webhook_config = self.config.get("webhook", {})
        url = webhook_config.get("url")
        if not url:
            self.logger.error("Webhook URL not configured")
            return False

        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
            "anomaly": anomaly,
        }
        if webhook_config.get("include_full_analysis"):
            payload["full_analysis"] = True
        if webhook_config.get("include_evidence_chain"):
            payload["evidence_chain"] = True

        headers = {"Content-Type": "application/json"}
        auth_token = webhook_config.get("auth_token")
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code < 300:
                    self.logger.info(f"Webhook alert sent to {url} (HTTP {response.status_code})")
                    return True
                else:
                    self.logger.error(f"Webhook alert failed: HTTP {response.status_code} from {url}")
                    return False
        except Exception as e:
            self.logger.error(f"Webhook alert error: {e}")
            return False

    async def _send_file_alert(self, anomaly: Dict[str, Any], message: str) -> bool:
        """
        Append an alert as a JSON line to a file.

        Args:
            anomaly: Detected anomaly
            message: Alert message

        Returns:
            Success flag
        """
        file_config = self.config.get("file", {})
        path = file_config.get("path", "logs/alerts.json")
        fmt = file_config.get("format", "jsonl")

        alert_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
            "anomaly": anomaly,
        }

        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "a") as f:
                if fmt == "jsonl":
                    f.write(json.dumps(alert_record, default=str) + "\n")
                else:
                    f.write(f"[{alert_record['timestamp']}] {message}\n")
            self.logger.info(f"Alert written to {path}")
            return True
        except Exception as e:
            self.logger.error(f"File alert error: {e}")
            return False

    async def _broadcast_alert(self, anomaly: Dict[str, Any], message: str) -> None:
        """
        Broadcast an alert to all connected WebSocket clients.

        Args:
            anomaly: Detected anomaly
            message: Alert message
        """
        alert_data = {
            "type": "alert",
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
            "anomaly": anomaly
        }

        for client_id, websocket in app_state.websocket_connections.items():
            try:
                await websocket.send_json(alert_data)
            except Exception as e:
                self.logger.error(f"Error sending alert to WebSocket client {client_id}: {str(e)}")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/alerts/test", tags=["Alerts"], response_model=Dict[str, Any])
async def test_alert(
    alert_type: str = Query("email", description="Type of alert to test (email, webhook, etc.)"),
    recipient: Optional[str] = Query(None, description="Optional recipient for the test alert")
):
    """
    Send a test alert to verify alert configuration.

    Args:
        alert_type: Type of alert to test (email, webhook, etc.)
        recipient: Optional recipient for the test alert

    Returns:
        Alert test status
    """
    if not app_state.alert_manager:
        raise HTTPException(status_code=404, detail="Alert manager not initialized")

    try:
        test_anomaly = {
            "id": f"test-{uuid.uuid4()}",
            "timestamp": datetime.utcnow().isoformat(),
            "detection_time": datetime.utcnow().isoformat(),
            "model": "test_model",
            "score": 0.95,
            "threshold": 0.7,
            "original_data": {"test": True, "message": "This is a test alert"},
            "details": {"test": True, "alert_type": alert_type, "recipient": recipient}
        }

        success = await app_state.alert_manager.send_alert(test_anomaly)

        return {
            "status": "success" if success else "failure",
            "alert_type": alert_type,
            "recipient": recipient,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Test alert sent successfully" if success else "Failed to send test alert"
        }
    except Exception as e:
        logging.error(f"Error sending test alert: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending test alert: {str(e)}")


@router.post("/alerts/config", tags=["Alerts"], response_model=Dict[str, Any])
async def update_alert_config(
    alert_config: AlertConfig
):
    """
    Update the alert configuration.

    Args:
        alert_config: New alert configuration

    Returns:
        Updated alert configuration
    """
    if app_state.config is None:
        raise HTTPException(status_code=404, detail="System not initialized")

    # Update alert configuration
    if "alerts" not in app_state.config:
        app_state.config["alerts"] = {}

    app_state.config["alerts"]["enabled"] = alert_config.enabled
    app_state.config["alerts"]["threshold_score"] = alert_config.threshold_score
    app_state.config["alerts"]["channels"] = alert_config.channels

    if alert_config.email:
        app_state.config["alerts"]["email"] = alert_config.email

    if alert_config.webhook:
        app_state.config["alerts"]["webhook"] = alert_config.webhook

    if alert_config.file:
        app_state.config["alerts"]["file"] = alert_config.file

    # Re-initialize alert manager
    try:
        app_state.alert_manager = AlertManager(app_state.config["alerts"])
        return {
            "status": "success",
            "alerts_enabled": alert_config.enabled,
            "threshold_score": alert_config.threshold_score,
            "channels": alert_config.channels,
            "updated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logging.error(f"Error updating alert configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating alert configuration: {str(e)}")
