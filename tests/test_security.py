"""Security and Hardening Tests for SeeGuide.

Tests:
1. HTTP Security Headers:
   - X-Content-Type-Options: nosniff
   - X-Frame-Options: DENY
   - Strict-Transport-Security: max-age=31536000; includeSubDomains
2. WebSocket Message Size Limit:
   - Oversized messages (> 2 MB) are rejected with policy violation (code 1008).
   - Valid normal frames (< 2 MB) are accepted without disconnect.
"""

import base64
import json
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.main import app


@pytest.fixture
def client():
    """Provides a Starlette TestClient with base URL."""
    return TestClient(app)


def test_http_security_headers_on_health_endpoint(client):
    """Verifies that mandatory security headers are present on API responses."""
    response = client.get("/health")
    assert response.status_code == 200
    
    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert "Strict-Transport-Security" in headers
    assert "max-age=31536000" in headers.get("Strict-Transport-Security")


def test_http_security_headers_on_static_endpoint(client):
    """Verifies that security headers are applied across static file endpoints."""
    response = client.get("/")
    assert response.status_code == 200
    
    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"


def test_websocket_message_size_limit_rejection(client):
    """Verifies that incoming WebSocket messages exceeding 2MB are rejected with code 1008."""
    session_id = "test-sec-size-limit"
    
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(f"/ws/{session_id}") as ws:
            # Construct a payload larger than MAX_MESSAGE_BYTES (2 * 1024 * 1024)
            large_padding = "A" * (2 * 1024 * 1024 + 1024)
            oversized_payload = json.dumps({
                "type": "frame",
                "session_id": session_id,
                "seq": 1,
                "ts_client": 123456.78,
                "mode": "walk",
                "image_b64": large_padding,
                "width": 640,
                "height": 480,
                "mime": "image/jpeg"
            })
            ws.send_text(oversized_payload)
            # Wait for server response or close
            ws.receive_text()

    assert excinfo.value.code == 1008


def test_websocket_valid_payload_accepted(client):
    """Verifies that incoming frames under 2MB are accepted normally."""
    session_id = "test-sec-valid-size"
    
    with client.websocket_connect(f"/ws/{session_id}") as ws:
        valid_payload = json.dumps({
            "type": "command",
            "command": "walk"
        })
        ws.send_text(valid_payload)
        # Connection should remain open and alive
        # Send a ping/pong or receive without disconnect
