"""Unit tests for GitHub webhook listener."""

import pytest
import json
from unittest.mock import patch, MagicMock
from flask import Response
from integrations.webhook_listener import app, receive_webhook

@pytest.fixture
def client():
    """Provide a test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def sample_push_event():
    """Provide sample push event data."""
    return {
        "ref": "refs/heads/main",
        "repository": {
            "full_name": "test/repo"
        },
        "commits": [
            {
                "id": "abc123",
                "message": "Test commit",
                "author": {"name": "Test Author"},
                "url": "https://github.com/test/repo/commit/abc123"
            }
        ],
        "pusher": {"name": "testuser"}
    }

@pytest.fixture
def sample_pr_event():
    """Provide sample pull request event data."""
    return {
        "action": "opened",
        "pull_request": {
            "number": 123,
            "title": "Test PR",
            "body": "Test description",
            "user": {"login": "testuser"},
            "html_url": "https://github.com/test/repo/pull/123",
            "head": {"ref": "feature-branch"},
            "commits": 1,
            "changed_files": 2
        },
        "repository": {
            "full_name": "test/repo"
        }
    }

def test_webhook_without_signature(client):
    """Test webhook call without signature header."""
    response = client.post("/webhook", json={})
    assert response.status_code == 401
    assert json.loads(response.data)["error"] == "Invalid signature"

def test_webhook_with_invalid_signature(client):
    """Test webhook call with invalid signature."""
    response = client.post(
        "/webhook",
        json={},
        headers={
            "X-Hub-Signature-256": "sha256=invalid",
            "X-GitHub-Event": "push"
        }
    )
    assert response.status_code == 401
    assert json.loads(response.data)["error"] == "Invalid signature"

def test_webhook_with_invalid_json(client):
    """Test webhook call with invalid JSON payload."""
    with patch("integrations.webhook_listener.signature_validator.validate_signature", return_value=True):
        response = client.post(
            "/webhook",
            data="invalid json",
            headers={
                "X-Hub-Signature-256": "sha256=valid",
                "X-GitHub-Event": "push"
            }
        )
        assert response.status_code == 400
        assert json.loads(response.data)["error"] == "Invalid JSON"

def test_push_event_handling(client, sample_push_event):
    """Test handling of push event."""
    with patch("integrations.webhook_listener.signature_validator.validate_signature", return_value=True), \
         patch("integrations.webhook_listener.commit_router.handle_push_event", return_value=["task_123"]):
        
        response = client.post(
            "/webhook",
            json=sample_push_event,
            headers={
                "X-Hub-Signature-256": "sha256=valid",
                "X-GitHub-Event": "push"
            }
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["task_ids"] == ["task_123"]

def test_pr_event_handling(client, sample_pr_event):
    """Test handling of pull request event."""
    with patch("integrations.webhook_listener.signature_validator.validate_signature", return_value=True), \
         patch("integrations.webhook_listener.commit_router.handle_pr_event", return_value=["task_456"]):
        
        response = client.post(
            "/webhook",
            json=sample_pr_event,
            headers={
                "X-Hub-Signature-256": "sha256=valid",
                "X-GitHub-Event": "pull_request"
            }
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["task_ids"] == ["task_456"]

def test_unsupported_event_type(client):
    """Test handling of unsupported event type."""
    with patch("integrations.webhook_listener.signature_validator.validate_signature", return_value=True):
        response = client.post(
            "/webhook",
            json={},
            headers={
                "X-Hub-Signature-256": "sha256=valid",
                "X-GitHub-Event": "unsupported"
            }
        )
        assert response.status_code == 202
        data = json.loads(response.data)
        assert data["status"] == "ignored"
        assert data["reason"] == "Unsupported event type"

def test_event_handler_error(client, sample_push_event):
    """Test handling of event handler errors."""
    with patch("integrations.webhook_listener.signature_validator.validate_signature", return_value=True), \
         patch("integrations.webhook_listener.commit_router.handle_push_event", side_effect=Exception("Test error")):
        
        response = client.post(
            "/webhook",
            json=sample_push_event,
            headers={
                "X-Hub-Signature-256": "sha256=valid",
                "X-GitHub-Event": "push"
            }
        )
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data["error"] == "Internal error processing webhook"

def test_missing_event_type(client):
    """Test webhook call without event type header."""
    with patch("integrations.webhook_listener.signature_validator.validate_signature", return_value=True):
        response = client.post(
            "/webhook",
            json={},
            headers={
                "X-Hub-Signature-256": "sha256=valid"
            }
        )
        assert response.status_code == 202
        data = json.loads(response.data)
        assert data["status"] == "ignored" 