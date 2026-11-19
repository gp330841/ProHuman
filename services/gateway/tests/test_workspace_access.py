"""Exercise authentication before touching databases or providers."""

import hashlib
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import create_app


@pytest.fixture
def credentials(monkeypatch):
    token = "A" * 43
    workspace = uuid4()
    monkeypatch.setenv("PROHUMAN_CREDENTIALS", json.dumps({
        hashlib.sha256(token.encode()).hexdigest(): {
            "user_id": "member", "workspace_id": str(workspace)
        }
    }))
    return {"Authorization": "Bearer " + token}, workspace


def test_verified_identity_and_member_admin_boundary(credentials):
    headers, workspace = credentials
    client = TestClient(create_app())
    response = client.get("/api/v1/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["workspace_id"] == str(workspace)
    assert client.get("/api/v1/system/status", headers=headers).status_code == 403
    assert client.post("/api/v1/system/flush-test-data", headers=headers).status_code == 403


def test_sensitive_routes_reject_anonymous_access():
    client = TestClient(create_app())
    session_id = uuid4()
    for path in (
        "/api/v1/sessions",
        f"/api/v1/sessions/{session_id}",
        f"/api/v1/export/{session_id}/mom",
        f"/api/v1/audio/{session_id}/playback",
    ):
        assert client.get(path).status_code == 401
    assert client.post("/api/v1/search", json={"query": "budget"}).status_code == 401
    assert client.post("/api/v1/agent/query", json={"query": "budget"}).status_code == 401
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(f"/api/v1/audio/stream/{session_id}"):
            pytest.fail("Unauthenticated recording connection accepted")
    assert error.value.code == 1008
