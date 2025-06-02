"""Unit tests for MAS error handler."""

import pytest
from datetime import datetime, timezone
from mas_core.error_handler import ErrorHandler, MASError, ErrorCategory

@pytest.fixture
def error_handler():
    """Provide a fresh error handler instance."""
    return ErrorHandler()

@pytest.fixture
def sample_error():
    """Provide a sample error instance."""
    return MASError(
        error_id="err_001",
        error_type=ErrorCategory.TASK,
        message="Test error",
        timestamp=datetime.now(timezone.utc).isoformat(),
        context={"test": "context"},
        task_id="task_001"
    )

def test_error_handler_initialization(error_handler):
    """Test error handler initialization."""
    assert error_handler.error_log == []
    assert len(error_handler.recovery_handlers) == 6

def test_handle_validation_error(error_handler):
    """Test handling of validation errors."""
    error = MASError(
        error_id="err_001",
        error_type=ErrorCategory.VALIDATION,
        message="Invalid task format",
        timestamp=datetime.now(timezone.utc).isoformat(),
        context={"field": "task_id"},
    )
    
    success = error_handler.handle_error(error)
    assert not success
    assert len(error_handler.error_log) == 1
    assert error_handler.error_log[0].recovery_attempted
    assert not error_handler.error_log[0].recovery_successful

def test_handle_task_error(error_handler):
    """Test handling of task errors."""
    error = MASError(
        error_id="err_002",
        error_type=ErrorCategory.TASK,
        message="Task execution failed",
        timestamp=datetime.now(timezone.utc).isoformat(),
        context={"task_id": "task_001"},
        task_id="task_001"
    )
    
    success = error_handler.handle_error(error)
    assert success
    assert len(error_handler.error_log) == 1
    assert error_handler.error_log[0].recovery_attempted
    assert error_handler.error_log[0].recovery_successful

def test_handle_agent_error(error_handler):
    """Test handling of agent errors."""
    error = MASError(
        error_id="err_003",
        error_type=ErrorCategory.AGENT,
        message="Agent disconnected",
        timestamp=datetime.now(timezone.utc).isoformat(),
        context={"agent_id": "agent_001"},
        agent_id="agent_001"
    )
    
    success = error_handler.handle_error(error)
    assert success
    assert len(error_handler.error_log) == 1
    assert error_handler.error_log[0].recovery_attempted
    assert error_handler.error_log[0].recovery_successful

def test_handle_system_error(error_handler):
    """Test handling of system errors."""
    error = MASError(
        error_id="err_004",
        error_type=ErrorCategory.SYSTEM,
        message="System resource exhausted",
        timestamp=datetime.now(timezone.utc).isoformat(),
        context={"resource": "memory"},
    )
    
    success = error_handler.handle_error(error)
    assert not success
    assert len(error_handler.error_log) == 1

def test_error_summary(error_handler, sample_error):
    """Test error summary generation."""
    # Add multiple errors
    error_handler.handle_error(sample_error)
    error_handler.handle_error(MASError(
        error_id="err_002",
        error_type=ErrorCategory.VALIDATION,
        message="Test error 2",
        timestamp=datetime.now(timezone.utc).isoformat(),
        context={}
    ))
    
    summary = error_handler.get_error_summary()
    assert summary["total_errors"] == 2
    assert len(summary["categories"]) == 2
    assert summary["recovery_stats"]["attempted"] == 2
    assert "timestamp" in summary

def test_recovery_failure_handling(error_handler):
    """Test handling of recovery failures."""
    error = MASError(
        error_id="err_005",
        error_type=ErrorCategory.CONSENSUS,
        message="Consensus failed",
        timestamp=datetime.now(timezone.utc).isoformat(),
        context={},
        task_id=None  # This will cause recovery to fail
    )
    
    success = error_handler.handle_error(error)
    assert not success
    assert len(error_handler.error_log) == 1
    assert error_handler.error_log[0].recovery_attempted
    assert not error_handler.error_log[0].recovery_successful

def test_error_handler_init():
    """Test ErrorHandler initialization"""
    handler = ErrorHandler()
    assert handler is not None

def test_error_handler_basic_flow():
    """Test basic error handling flow"""
    handler = ErrorHandler()
    error = Exception("Test error")
    handler.handle_error(error)
    assert handler.get_last_error() == error 