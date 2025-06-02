"""
Integration tests for UI and routing components.

Tests the integration between Flask UI, Redis queue, and AI routing system.

MAS Lite Protocol v2.1 References:
- Section 4.2: Event Queue Requirements
- Section 4.3: Queue Operations
- Section 4.4: Error Handling
"""

import pytest
import pytest_asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch
from flask import Flask
from flask.testing import FlaskClient
from scripts.redis_queue import RedisEventQueue
from scripts.event_router import EventRouter
from scripts.ai_router import AIRouter

@pytest.fixture
def app() -> Flask:
    """Create Flask app for testing."""
    from app import create_app
    app = create_app({
        "TESTING": True,
        "REDIS_URL": "redis://localhost:6379/0"
    })
    return app

@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Create test client."""
    return app.test_client()

@pytest_asyncio.fixture
async def redis_queue() -> AsyncGenerator[RedisEventQueue, None]:
    """Create Redis queue for testing."""
    with patch("redis.asyncio.Redis.from_url") as mock_redis:
        queue = RedisEventQueue({
            "queue": {
                "type": "redis",
                "redis_url": "redis://localhost:6379/0",
                "max_size": 100,
                "timeout": 0.1
            }
        })
        yield queue
        await queue.cleanup()

@pytest_asyncio.fixture
async def event_router(redis_queue: RedisEventQueue) -> EventRouter:
    """Create event router for testing."""
    router = EventRouter({
        "providers": {
            "claude": {"enabled": True},
            "grok": {"enabled": True},
            "chatgpt": {"enabled": True}
        }
    })
    router.redis_queue = redis_queue
    return router

@pytest.mark.integration
def test_redis_dashboard_view(client: FlaskClient) -> None:
    """Test Redis dashboard view."""
    response = client.get("/redis")
    assert response.status_code == 200
    assert b"Redis Dashboard" in response.data

@pytest.mark.integration
def test_oauth_login(client: FlaskClient) -> None:
    """Test OAuth login flow."""
    response = client.get("/auth/login")
    assert response.status_code == 302  # Redirect to GitHub
    assert "github.com/login/oauth" in response.location

@pytest.mark.integration
@pytest.mark.asyncio
async def test_event_routing(
    client: FlaskClient,
    event_router: EventRouter
) -> None:
    """Test event routing through UI."""
    # Create test event
    event = {
        "type": "code_review",
        "repo": "test/repo",
        "commit": "abc123"
    }
    
    # Submit through UI
    response = client.post("/events", json=event)
    assert response.status_code == 202
    
    # Verify routing
    routed_event = await event_router.redis_queue.dequeue()
    assert routed_event == event
    
    # Check provider selection
    providers = event_router.ai_router.select_providers(event["type"])
    assert "claude" in providers
    assert "grok" in providers

@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_check(
    client: FlaskClient,
    redis_queue: RedisEventQueue
) -> None:
    """Test system health check."""
    # Mock Redis health
    redis_queue.redis.ping = AsyncMock(return_value=True)
    
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["redis_connected"] is True

@pytest.mark.integration
@pytest.mark.asyncio
async def test_provider_failover(
    client: FlaskClient,
    event_router: EventRouter
) -> None:
    """Test AI provider failover."""
    # Disable Claude
    event_router.ai_router.providers["claude"].enabled = False
    
    # Create test event
    event = {
        "type": "code_review",
        "repo": "test/repo",
        "commit": "abc123"
    }
    
    # Submit through UI
    response = client.post("/events", json=event)
    assert response.status_code == 202
    
    # Verify fallback to Grok
    providers = event_router.ai_router.select_providers(event["type"])
    assert "claude" not in providers
    assert "grok" in providers

@pytest.mark.integration
def test_metrics_view(client: FlaskClient) -> None:
    """Test metrics view."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"Queue Depth" in response.data
    assert b"Processing Time" in response.data

@pytest.mark.integration
def test_config_view(client: FlaskClient) -> None:
    """Test configuration view."""
    response = client.get("/config")
    assert response.status_code == 200
    assert b"Redis Settings" in response.data
    assert b"Provider Configuration" in response.data 