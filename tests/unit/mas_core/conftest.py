"""Shared test fixtures for MAS core unit tests."""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any, Generator
from pathlib import Path
import tempfile
import json

@pytest.fixture
def mock_task() -> Dict[str, Any]:
    """Provide a mock task for testing."""
    return {
        "task_id": "test_task_001",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase_id": "P1",
        "description": "Test task for unit testing",
        "priority_level": "medium",
        "consensus": "pending",
        "sections_reviewed": ["1.1", "1.2"],
        "agent_assignment": {
            "grok": "generate_draft",
            "chatgpt": "review_draft"
        }
    }

@pytest.fixture
def temp_log_file() -> Generator[Path, None, None]:
    """Provide a temporary log file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tf:
        temp_path = Path(tf.name)
        json.dump([], tf)
    yield temp_path
    temp_path.unlink()

@pytest.fixture
def mock_metrics() -> Dict[str, Any]:
    """Provide mock metrics data for testing."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_metrics": {
            "total": 100,
            "completed": 75,
            "pending": 20,
            "failed": 5
        },
        "performance_metrics": {
            "avg_task_completion_time": 120.5,
            "consensus_rounds_avg": 2.3,
            "routing_latency_ms": 85.2
        }
    }

@pytest.fixture
def mock_consensus_data() -> Dict[str, Any]:
    """Provide mock consensus data for testing."""
    return {
        "task_id": "test_task_001",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "votes": {
            "grok": "approve",
            "chatgpt": "approve"
        },
        "comments": {
            "grok": "Code review passed",
            "chatgpt": "Documentation complete"
        },
        "status": "approved",
        "round": 1
    } 