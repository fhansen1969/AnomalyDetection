"""WebSocket endpoint and streaming status routes."""
import json
import logging
import traceback
import uuid
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.state import app_state

logger = logging.getLogger("api_services")
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.
    """
    await websocket.accept()

    # Generate a client ID
    client_id = str(uuid.uuid4())
    app_state.websocket_connections[client_id] = websocket

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connection",
            "client_id": client_id,
            "status": "connected",
            "message": "Connected to anomaly detection service",
            "timestamp": datetime.utcnow().isoformat()
        })

        # Keep the connection open and handle incoming messages
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)

                # Handle message based on type
                if message.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                elif message.get("type") == "subscribe":
                    topics = message.get("topics", [])
                    if not isinstance(topics, list):
                        topics = []
                    await websocket.send_json({
                        "type": "subscription",
                        "status": "subscribed",
                        "topics": topics,
                        "timestamp": datetime.utcnow().isoformat()
                    })
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as e:
                logging.error(f"Error processing WebSocket message: {str(e)}")
                logging.error(traceback.format_exc())
                await websocket.send_json({
                    "type": "error",
                    "message": "Internal server error",
                    "timestamp": datetime.utcnow().isoformat()
                })
    except WebSocketDisconnect:
        if client_id in app_state.websocket_connections:
            del app_state.websocket_connections[client_id]
    except Exception as e:
        logging.error(f"Unexpected WebSocket error: {str(e)}")
        logging.error(traceback.format_exc())
        if client_id in app_state.websocket_connections:
            del app_state.websocket_connections[client_id]


@router.get("/stream/status")
async def get_stream_status():
    """Get the status of real-time data streams."""

    streams = {
        "anomaly_stream": {
            "name": "Anomaly Detection Stream",
            "status": "active",
            "last_message": datetime.now().isoformat(),
            "connected_clients": len(app_state.websocket_connections)
        },
        "log_stream": {
            "name": "System Log Stream",
            "status": "active",
            "last_message": datetime.now().isoformat(),
            "connected_clients": len(app_state.websocket_connections)
        },
        "metric_stream": {
            "name": "Metrics Stream",
            "status": "active",
            "last_message": datetime.now().isoformat(),
            "connected_clients": len(app_state.websocket_connections)
        }
    }

    total_clients = sum(s["connected_clients"] for s in streams.values())

    return {
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_streams": len(streams),
            "active_streams": len([s for s in streams.values() if s["status"] == "active"]),
            "total_connected_clients": total_clients
        },
        "streams": streams
    }
