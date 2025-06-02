"""Unit tests for MAS validation utilities."""

import pytest
from datetime import datetime, timezone
from mas_core.utils.validation import (
    validate_task_id,
    validate_timestamp,
    validate_task,
    validate_agent_assignment,
    validate_consensus_vote,
    generate_task_id,
    ValidationError
)

def test_validate_task_id():
    """Test task ID validation."""
    assert validate_task_id("task_123")
    assert validate_task_id("task-123_abc")
    assert not validate_task_id("task@123")
    assert not validate_task_id("task 123")
    assert not validate_task_id("")

def test_validate_timestamp():
    """Test timestamp validation."""
    now = datetime.now(timezone.utc).isoformat()
    assert validate_timestamp(now)
    assert not validate_timestamp("2025-13-01T00:00:00")
    assert not validate_timestamp("invalid")

def test_validate_task():
    """Test task structure validation."""
    valid_task = {
        "task_id": "task_123",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "description": "Test task",
        "priority_level": "medium",
        "consensus": "pending",
        "agent_assignment": {
            "agent1": "generate_draft",
            "agent2": "review_draft"
        }
    }

    # Test valid task
    validate_task(valid_task)

    # Test missing field
    invalid_task = valid_task.copy()
    del invalid_task["description"]
    with pytest.raises(ValidationError, match="Missing required field"):
        validate_task(invalid_task)

    # Test invalid priority
    invalid_task = valid_task.copy()
    invalid_task["priority_level"] = "invalid"
    with pytest.raises(ValidationError, match="Invalid priority_level"):
        validate_task(invalid_task)

def test_validate_agent_assignment():
    """Test agent assignment validation."""
    valid_assignment = {
        "agent1": "generate_draft",
        "agent2": "review_draft"
    }

    # Test valid assignment
    validate_agent_assignment(valid_assignment)

    # Test empty assignment
    with pytest.raises(ValidationError, match="Empty agent assignment"):
        validate_agent_assignment({})

    # Test invalid role
    invalid_assignment = {"agent1": "invalid_role"}
    with pytest.raises(ValidationError, match="Invalid agent role"):
        validate_agent_assignment(invalid_assignment)

def test_validate_consensus_vote():
    """Test consensus vote validation."""
    valid_vote = {
        "task_id": "task_123",
        "agent_id": "agent1",
        "vote": "approve",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Test valid vote
    validate_consensus_vote(valid_vote)

    # Test invalid vote value
    invalid_vote = valid_vote.copy()
    invalid_vote["vote"] = "maybe"
    with pytest.raises(ValidationError, match="Invalid vote value"):
        validate_consensus_vote(invalid_vote)

def test_generate_task_id():
    """Test task ID generation."""
    task_id = generate_task_id()
    assert validate_task_id(task_id)
    assert task_id.startswith("task_")
    assert len(task_id) == 21  # "task_" + 16 hex chars 