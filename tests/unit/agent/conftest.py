"""Shared test fixtures for Agent framework unit tests."""

import pytest
from typing import Dict, Any, List
from datetime import datetime, timezone
import asyncio
from dataclasses import dataclass
from pathlib import Path

@dataclass
class MockCapability:
    """Mock capability for testing."""
    name: str
    version: str
    requirements: List[str]

@pytest.fixture
def mock_agent_config() -> Dict[str, Any]:
    """Provide mock agent configuration for testing."""
    return {
        "agent_id": "test_agent_001",
        "capabilities": [
            {
                "name": "code_review",
                "version": "1.0.0",
                "requirements": ["python", "git"]
            },
            {
                "name": "documentation",
                "version": "1.0.0",
                "requirements": ["markdown"]
            }
        ],
        "max_tasks": 10,
        "task_timeout": 300,
        "heartbeat_interval": 30
    }

@pytest.fixture
def mock_message() -> Dict[str, Any]:
    """Provide a mock agent message for testing."""
    return {
        "message_id": "msg_001",
        "sender_id": "agent_001",
        "recipient_id": "agent_002",
        "message_type": "task_assignment",
        "content": {
            "task_id": "test_task_001",
            "action": "review",
            "priority": "high"
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "requires_response": True
    }

@pytest.fixture
def mock_capability() -> MockCapability:
    """Provide a mock capability instance for testing."""
    return MockCapability(
        name="code_review",
        version="1.0.0",
        requirements=["python", "git"]
    )

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_agent_state() -> Dict[str, Any]:
    """Provide mock agent state data for testing."""
    return {
        "status": "active",
        "current_task": "test_task_001",
        "task_queue": ["test_task_002", "test_task_003"],
        "completed_tasks": ["test_task_000"],
        "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        "performance_metrics": {
            "tasks_completed": 10,
            "avg_task_time": 45.2,
            "success_rate": 0.95
        }
    } 