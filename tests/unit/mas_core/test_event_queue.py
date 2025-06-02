#!/usr/bin/env python3
"""
Unit tests for EventQueue implementation.
Tests webhook payload processing and retry logic.
"""

import pytest
import asyncio
from datetime import datetime
from scripts.event_queue import EventQueue, WebhookPayload, RetryHandler

@pytest.fixture
def config():
    """Test configuration fixture."""
    return {
        "queue": {
            "max_size": 100,
            "timeout": 5,
            "retry_policy": {
                "base_delay": 0.1,
                "max_retries": 2
            }
        }
    }

@pytest.fixture
def sample_payload():
    """Sample webhook payload fixture."""
    return {
        "event_type": "push",
        "repo": "test/repo",
        "user": "test_user",
        "message": "Test commit",
        "files": ["file1.py", "file2.py"]
    }

@pytest.fixture
async def event_queue(config):
    """EventQueue instance fixture."""
    queue = EventQueue(config)
    yield queue
    await queue.stop()

@pytest.mark.asyncio
async def test_enqueue_valid_payload(event_queue, sample_payload):
    """Test enqueueing valid webhook payload."""
    success = await event_queue.enqueue(sample_payload)
    assert success
    assert event_queue.get_queue_depth() == 1

@pytest.mark.asyncio
async def test_enqueue_invalid_payload(event_queue):
    """Test enqueueing invalid webhook payload."""
    invalid_payload = {
        "event_type": "push",
        # Missing required 'repo' field
        "user": "test_user"
    }
    success = await event_queue.enqueue(invalid_payload)
    assert not success
    assert event_queue.get_queue_depth() == 0

@pytest.mark.asyncio
async def test_dequeue_payload(event_queue, sample_payload):
    """Test dequeuing and processing webhook payload."""
    await event_queue.enqueue(sample_payload)
    
    payload = await event_queue.dequeue()
    assert payload is not None
    assert isinstance(payload, WebhookPayload)
    assert payload.event_type == sample_payload["event_type"]
    assert payload.repo == sample_payload["repo"]
    assert payload.user == sample_payload["user"]
    assert payload.message == sample_payload["message"]
    assert payload.files == sample_payload["files"]

@pytest.mark.asyncio
async def test_queue_depth(event_queue, sample_payload):
    """Test queue depth tracking."""
    assert event_queue.get_queue_depth() == 0
    
    # Add multiple payloads
    for i in range(3):
        payload = sample_payload.copy()
        payload["message"] = f"Test commit {i}"
        await event_queue.enqueue(payload)
        
    assert event_queue.get_queue_depth() == 3
    
    # Dequeue one payload
    await event_queue.dequeue()
    assert event_queue.get_queue_depth() == 2

@pytest.mark.asyncio
async def test_queue_max_size(event_queue, sample_payload):
    """Test queue max size enforcement."""
    max_size = event_queue.max_size
    
    # Fill queue to max size
    for i in range(max_size):
        payload = sample_payload.copy()
        payload["message"] = f"Test commit {i}"
        success = await event_queue.enqueue(payload)
        assert success
        
    # Attempt to add one more
    success = await event_queue.enqueue(sample_payload)
    assert not success
    assert event_queue.get_queue_depth() == max_size

@pytest.mark.asyncio
async def test_retry_handler():
    """Test retry logic with exponential backoff."""
    retry_handler = RetryHandler(base_delay=0.1, max_retries=2)
    
    # Test successful execution
    async def success_func():
        return "success"
        
    result = await retry_handler.retry_with_backoff(success_func)
    assert result == "success"
    
    # Test failed execution with retries
    attempt = 0
    async def fail_func():
        nonlocal attempt
        attempt += 1
        if attempt <= 2:
            raise ValueError("Test error")
        return "success"
        
    result = await retry_handler.retry_with_backoff(fail_func)
    assert result == "success"
    assert attempt == 3
    
    # Test max retries exceeded
    async def always_fail():
        raise ValueError("Always fails")
        
    with pytest.raises(ValueError):
        await retry_handler.retry_with_backoff(always_fail)

@pytest.mark.asyncio
async def test_queue_context_manager(config, sample_payload):
    """Test queue context manager functionality."""
    async with EventQueue(config) as queue:
        assert queue._running
        await queue.enqueue(sample_payload)
        payload = await queue.dequeue()
        assert payload is not None
        
    assert not queue._running
    assert len(queue._tasks) == 0

@pytest.mark.asyncio
async def test_concurrent_operations(event_queue, sample_payload):
    """Test concurrent enqueue and dequeue operations."""
    # Create multiple producers and consumers
    async def producer(count):
        for i in range(count):
            payload = sample_payload.copy()
            payload["message"] = f"Test commit {i}"
            await event_queue.enqueue(payload)
            await asyncio.sleep(0.1)
            
    async def consumer(count):
        payloads = []
        for _ in range(count):
            payload = await event_queue.dequeue()
            if payload:
                payloads.append(payload)
            await asyncio.sleep(0.1)
        return payloads
        
    # Run concurrent operations
    producer_task = asyncio.create_task(producer(5))
    consumer_tasks = [
        asyncio.create_task(consumer(3))
        for _ in range(2)
    ]
    
    await producer_task
    results = await asyncio.gather(*consumer_tasks)
    
    # Verify results
    all_payloads = [p for sublist in results for p in sublist]
    assert len(all_payloads) == 5
    assert all(isinstance(p, WebhookPayload) for p in all_payloads) 