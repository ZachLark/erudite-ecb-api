#!/usr/bin/env python3
"""
Unit tests for TaskChain implementation.
Tests task lifecycle management and state transitions.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from mas_core.task_chain import TaskChain, TaskState, TaskMetadata

@pytest.fixture
def config():
    """Test configuration fixture."""
    return {
        "task_chain": {
            "max_concurrent": 5,
            "states": ["Created", "Queued", "ConsensusPending", "Resolved", "Failed"]
        }
    }

@pytest.fixture
def consensus_manager():
    """Mock consensus manager fixture."""
    manager = AsyncMock()
    manager.process_task = AsyncMock(return_value={"status": "approved"})
    return manager

@pytest.fixture
def mas_logger():
    """Mock MAS logger fixture."""
    logger = AsyncMock()
    logger.log_event = AsyncMock()
    logger.get_events = AsyncMock(return_value=[])
    return logger

@pytest.fixture
async def task_chain(config, consensus_manager, mas_logger):
    """TaskChain instance fixture."""
    chain = TaskChain(consensus_manager, mas_logger, config)
    yield chain

@pytest.mark.asyncio
async def test_create_task(task_chain, mas_logger):
    """Test task creation and initialization."""
    task_id = "test_task_1"
    agent = "test_agent"
    parent_task_id = "parent_task_1"
    
    metadata = await task_chain.create_task(task_id, agent, parent_task_id)
    
    assert metadata.task_id == task_id
    assert metadata.agent == agent
    assert metadata.parent_task_id == parent_task_id
    assert metadata.status == TaskState.CREATED
    assert metadata.retry_count == 0
    assert metadata.error_message is None
    
    # Verify logging
    mas_logger.log_event.assert_called_once()
    call_args = mas_logger.log_event.call_args[0]
    assert call_args[0] == "task_created"
    assert call_args[1]["task_id"] == task_id
    assert call_args[1]["agent"] == agent
    assert call_args[1]["parent_task_id"] == parent_task_id

@pytest.mark.asyncio
async def test_transition_state(task_chain, mas_logger):
    """Test task state transitions."""
    task_id = "test_task_2"
    await task_chain.create_task(task_id)
    
    # Test successful transition
    success = await task_chain.transition_state(task_id, TaskState.QUEUED)
    assert success
    assert task_chain.tasks[task_id].status == TaskState.QUEUED
    
    # Test transition to failed state with error message
    error_msg = "Test error"
    success = await task_chain.transition_state(
        task_id,
        TaskState.FAILED,
        error_message=error_msg
    )
    assert success
    assert task_chain.tasks[task_id].status == TaskState.FAILED
    assert task_chain.tasks[task_id].error_message == error_msg
    
    # Test invalid task ID
    success = await task_chain.transition_state("invalid_task", TaskState.QUEUED)
    assert not success

@pytest.mark.asyncio
async def test_process_consensus_result(task_chain, mas_logger):
    """Test consensus result processing."""
    task_id = "test_task_3"
    await task_chain.create_task(task_id)
    
    # Test approved consensus
    result = {"status": "approved"}
    success = await task_chain.process_consensus_result(task_id, result)
    assert success
    assert task_chain.tasks[task_id].status == TaskState.RESOLVED
    
    # Test rejected consensus
    task_id = "test_task_4"
    await task_chain.create_task(task_id)
    result = {"status": "rejected", "reason": "Test rejection"}
    success = await task_chain.process_consensus_result(task_id, result)
    assert success
    assert task_chain.tasks[task_id].status == TaskState.FAILED
    assert task_chain.tasks[task_id].error_message == "Test rejection"

@pytest.mark.asyncio
async def test_get_task_history(task_chain, mas_logger):
    """Test task history retrieval."""
    task_id = "test_task_5"
    await task_chain.create_task(task_id)
    
    # Mock history events
    events = [
        {"event": "task_created", "task_id": task_id},
        {"event": "state_change", "task_id": task_id}
    ]
    mas_logger.get_events.return_value = events
    
    history = await task_chain.get_task_history(task_id)
    assert history == events
    mas_logger.get_events.assert_called_once_with(
        event_filter={"task_id": task_id}
    )

@pytest.mark.asyncio
async def test_cleanup_task(task_chain, mas_logger):
    """Test task cleanup."""
    task_id = "test_task_6"
    await task_chain.create_task(task_id)
    
    assert task_id in task_chain.tasks
    await task_chain.cleanup_task(task_id)
    assert task_id not in task_chain.tasks
    
    # Verify cleanup logging
    cleanup_call = [
        call for call in mas_logger.log_event.call_args_list
        if call[0][0] == "task_cleanup"
    ][0]
    assert cleanup_call[0][1]["task_id"] == task_id

@pytest.mark.asyncio
async def test_concurrent_task_limit(task_chain):
    """Test concurrent task limit enforcement."""
    tasks = []
    max_concurrent = task_chain.max_concurrent
    
    # Create more tasks than the concurrent limit
    for i in range(max_concurrent + 2):
        task_id = f"concurrent_task_{i}"
        tasks.append(task_chain.create_task(task_id))
    
    # Verify all tasks are created but semaphore limits concurrency
    completed_tasks = await asyncio.gather(*tasks)
    assert len(completed_tasks) == max_concurrent + 2
    assert all(isinstance(task, TaskMetadata) for task in completed_tasks) 