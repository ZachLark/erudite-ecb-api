"""
Unit tests for Redis queue implementation.

Tests Redis-backed event queue functionality, including enqueue/dequeue operations,
health checks, and automatic failover capabilities.

MAS Lite Protocol v2.1 References:
- Section 4.2: Event Queue Requirements
- Section 4.3: Queue Operations
- Section 4.4: Error Handling
"""

import json
import pytest
import pytest_asyncio
import asyncio
import redis.asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from scripts.redis_queue import (
    RedisEventQueue, QueueFactory, ResilientQueue,
    QueueError, QueueFullError, QueueConnectionError
)
from mas_core.queue import EventQueue

# Use shorter timeout for tests
TEST_TIMEOUT = 0.1

# Add test markers
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.timeout(2),
    pytest.mark.filterwarnings("ignore::DeprecationWarning")
]

@pytest.fixture(scope="function")
def test_event():
    """Test event fixture."""
    return {
        "event_type": "push",
        "repo": "test/repo",
        "user": "test_user",
        "timestamp": "2025-06-02T12:00:00Z"
    }

@pytest.fixture(scope="function")
def config():
    """Test configuration fixture."""
    return {
        "queue": {
            "type": "redis",
            "redis_url": "redis://localhost:6379/0",
            "max_size": 100,
            "timeout": TEST_TIMEOUT,  # Use shorter timeout
            "retry_policy": {
                "max_retries": 2,
                "base_delay": 0.01  # Shorter delay
            }
        }
    }

@pytest.fixture(scope="function")
def mock_redis():
    """Mock Redis client fixture."""
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.llen = AsyncMock(return_value=0)
    redis.lpush = AsyncMock(return_value=True)
    redis.lpop = AsyncMock(return_value=None)
    redis.lrem = AsyncMock(return_value=1)
    redis.close = AsyncMock()
    redis.aclose = AsyncMock()  # Add aclose method
    
    # Mock pipeline with proper async context management
    pipeline = AsyncMock()
    pipeline.brpop = AsyncMock()
    pipeline.lpush = AsyncMock()
    pipeline.execute = AsyncMock(return_value=[None])
    pipeline.__aenter__ = AsyncMock(return_value=pipeline)
    pipeline.__aexit__ = AsyncMock()
    redis.pipeline = MagicMock(return_value=pipeline)
    
    return redis

@pytest_asyncio.fixture(scope="function")
async def redis_queue(config, mock_redis):
    """RedisEventQueue instance fixture."""
    with patch("redis.asyncio.Redis.from_url", return_value=mock_redis):
        queue = RedisEventQueue(config)
        yield queue
        await queue.cleanup()  # Ensure cleanup

@pytest.mark.asyncio
async def test_redis_queue_init(redis_queue):
    """Test queue initialization."""
    assert redis_queue.queue_key == "gitbridge:events"
    assert redis_queue.processing_key == "gitbridge:processing"
    assert redis_queue.max_size == 100
    assert redis_queue.timeout == TEST_TIMEOUT
    assert redis_queue.retry_policy == {"max_retries": 2, "base_delay": 0.01}

@pytest.mark.asyncio
async def test_redis_enqueue_success(redis_queue, mock_redis):
    """Test successful payload enqueue."""
    payload = {
        "event_type": "push",
        "repo": "test/repo",
        "user": "test_user"
    }
    
    success = await redis_queue.enqueue(payload)
    assert success
    
    mock_redis.lpush.assert_called_once_with(
        "gitbridge:events",
        json.dumps(payload)
    )

@pytest.mark.asyncio
async def test_redis_enqueue_queue_full(redis_queue, mock_redis):
    """Test enqueue when queue is full."""
    mock_redis.llen.return_value = 100
    
    success = await redis_queue.enqueue({"event_type": "push"})
    assert not success
    mock_redis.lpush.assert_not_called()

@pytest.mark.asyncio
async def test_redis_dequeue_success(redis_queue, mock_redis):
    """Test successful payload dequeue."""
    payload = {
        "event_type": "push",
        "repo": "test/repo"
    }
    
    # Mock successful dequeue
    pipeline = mock_redis.pipeline.return_value
    pipeline.execute.return_value = [("gitbridge:events", json.dumps(payload))]
    
    result = await redis_queue.dequeue()
    assert result == payload
    
    # Verify pipeline operations
    pipeline.brpop.assert_called_once_with("gitbridge:events", timeout=TEST_TIMEOUT)
    pipeline.lpush.assert_called_once_with("gitbridge:processing", "placeholder")

@pytest.mark.asyncio
async def test_redis_dequeue_timeout(redis_queue, mock_redis):
    """Test dequeue timeout."""
    pipeline = mock_redis.pipeline.return_value
    pipeline.execute.return_value = [None]  # Simulate timeout
    
    # Use shorter timeout for test
    async with asyncio.timeout(TEST_TIMEOUT * 2):
        result = await redis_queue.dequeue()
        
    assert result is None
    mock_redis.lpop.assert_called_once_with("gitbridge:processing")

@pytest.mark.asyncio
async def test_redis_dequeue_invalid_json(redis_queue, mock_redis):
    """Test dequeue with invalid JSON payload."""
    pipeline = mock_redis.pipeline.return_value
    pipeline.execute.return_value = [("gitbridge:events", "invalid json")]
    
    result = await redis_queue.dequeue()
    assert result is None
    mock_redis.lrem.assert_called_once_with(
        "gitbridge:processing",
        1,
        "invalid json"
    )

@pytest.mark.asyncio
async def test_redis_dequeue_error(redis_queue, mock_redis):
    """Test dequeue error handling."""
    pipeline = mock_redis.pipeline.return_value
    pipeline.execute.side_effect = Exception("Redis error")
    
    result = await redis_queue.dequeue()
    assert result is None

@pytest.mark.asyncio
async def test_queue_factory_redis(config):
    """Test queue factory creates Redis queue."""
    with patch("redis.asyncio.Redis.from_url"):
        queue = QueueFactory.create_queue(config)
        assert isinstance(queue, RedisEventQueue)

@pytest.mark.asyncio
async def test_queue_factory_asyncio(config):
    """Test queue factory creates asyncio queue."""
    config["queue"]["type"] = "asyncio"
    queue = QueueFactory.create_queue(config)
    assert isinstance(queue, EventQueue)

@pytest.mark.asyncio
async def test_redis_health_check_healthy(redis_queue, mock_redis):
    """Test Redis health check when healthy."""
    mock_redis.llen.side_effect = [5, 2]  # queue_depth, processing
    
    health = await redis_queue.check_health()
    assert health["status"] == "healthy"
    assert health["queue_depth"] == 5
    assert health["processing"] == 2

@pytest.mark.asyncio
async def test_redis_health_check_unhealthy(redis_queue, mock_redis):
    """Test Redis health check when unhealthy."""
    mock_redis.ping.side_effect = Exception("Connection error")
    
    health = await redis_queue.check_health()
    assert health["status"] == "unhealthy"
    assert "error" in health

@pytest.mark.asyncio
async def test_resilient_queue_enqueue_success(config):
    """Test resilient queue successful enqueue."""
    with patch("scripts.redis_queue.RedisEventQueue") as mock_redis_queue, \
         patch("scripts.redis_queue.EventQueue") as mock_async_queue:
        
        mock_redis_queue.return_value.enqueue = AsyncMock(return_value=True)
        queue = ResilientQueue(config)
        
        success = await queue.enqueue({"event_type": "push"})
        assert success
        mock_redis_queue.return_value.enqueue.assert_called_once()
        mock_async_queue.return_value.enqueue.assert_not_called()

@pytest.mark.asyncio
async def test_resilient_queue_fallback(config):
    """Test resilient queue fallback to asyncio."""
    with patch("scripts.redis_queue.RedisEventQueue") as mock_redis_queue, \
         patch("scripts.redis_queue.EventQueue") as mock_async_queue:
        
        mock_redis_queue.return_value.enqueue = AsyncMock(side_effect=Exception)
        mock_async_queue.return_value.enqueue = AsyncMock(return_value=True)
        queue = ResilientQueue(config)
        
        success = await queue.enqueue({"event_type": "push"})
        assert success
        mock_redis_queue.return_value.enqueue.assert_called_once()
        mock_async_queue.return_value.enqueue.assert_called_once()

@pytest.mark.asyncio
async def test_cleanup(redis_queue, mock_redis):
    """Test queue cleanup."""
    await redis_queue.cleanup()
    mock_redis.aclose.assert_called_once()

@pytest.mark.asyncio
async def test_redis_enqueue_connection_error(redis_queue, mock_redis):
    """Test enqueue with Redis connection error."""
    mock_redis.lpush.side_effect = redis.asyncio.ConnectionError("Connection refused")
    
    success = await redis_queue.enqueue({"event_type": "push"})
    assert not success

@pytest.mark.asyncio
async def test_redis_dequeue_connection_error(redis_queue, mock_redis):
    """Test dequeue with Redis connection error."""
    pipeline = mock_redis.pipeline.return_value
    pipeline.execute.side_effect = redis.asyncio.ConnectionError("Connection refused")
    
    result = await redis_queue.dequeue()
    assert result is None

@pytest.mark.asyncio
async def test_redis_queue_max_size_zero(config):
    """Test queue with max_size of 0."""
    config["queue"]["max_size"] = 0
    queue = RedisEventQueue(config)
    
    success = await queue.enqueue({"event_type": "push"})
    assert not success

@pytest.mark.asyncio
async def test_redis_queue_invalid_url(config):
    """Test queue with invalid Redis URL."""
    config["queue"]["redis_url"] = "invalid://url"
    with pytest.raises(ValueError):
        RedisEventQueue(config)

@pytest.mark.asyncio
async def test_resilient_queue_redis_recovery(config):
    """Test resilient queue recovery after Redis becomes available."""
    with patch("scripts.redis_queue.RedisEventQueue") as mock_redis_queue, \
         patch("scripts.redis_queue.EventQueue") as mock_async_queue:
        
        # First enqueue fails with Redis
        mock_redis_queue.return_value.enqueue = AsyncMock(side_effect=Exception)
        mock_async_queue.return_value.enqueue = AsyncMock(return_value=True)
        queue = ResilientQueue(config)
        
        # Should fall back to asyncio
        success = await queue.enqueue({"event_type": "push"})
        assert success
        assert not queue.using_redis
        
        # Redis becomes available
        mock_redis_queue.return_value.enqueue = AsyncMock(return_value=True)
        queue.using_redis = True
        
        # Should use Redis again
        success = await queue.enqueue({"event_type": "push"})
        assert success
        assert queue.using_redis

@pytest.mark.asyncio
async def test_resilient_queue_both_queues_fail(config):
    """Test resilient queue when both Redis and asyncio queues fail."""
    with patch("scripts.redis_queue.RedisEventQueue") as mock_redis_queue, \
         patch("scripts.redis_queue.EventQueue") as mock_async_queue:
        
        mock_redis_queue.return_value.enqueue = AsyncMock(side_effect=Exception)
        mock_async_queue.return_value.enqueue = AsyncMock(side_effect=Exception)
        queue = ResilientQueue(config)
        
        success = await queue.enqueue({"event_type": "push"})
        assert not success

@pytest.mark.asyncio
async def test_redis_queue_large_payload(redis_queue, mock_redis, test_event):
    """Test queue with large payload."""
    # Create a large payload
    large_payload = test_event.copy()
    large_payload["data"] = "x" * 1024 * 1024  # 1MB of data
    
    success = await redis_queue.enqueue(large_payload)
    assert success
    mock_redis.lpush.assert_called_once()

@pytest.mark.asyncio
async def test_redis_queue_concurrent_operations(redis_queue, mock_redis):
    """Test concurrent queue operations."""
    async def producer():
        for i in range(5):
            await redis_queue.enqueue({"event": f"event_{i}"})
            
    async def consumer():
        results = []
        for _ in range(5):
            result = await redis_queue.dequeue()
            if result:
                results.append(result)
        return results
    
    # Run producer and consumer concurrently
    producer_task = asyncio.create_task(producer())
    consumer_task = asyncio.create_task(consumer())
    
    await asyncio.gather(producer_task, consumer_task)
    
    # Verify pipeline usage
    pipeline = mock_redis.pipeline.return_value
    assert pipeline.execute.call_count == 5  # One for each dequeue 

@pytest.mark.asyncio
async def test_queue_factory_missing_config():
    """Test queue factory with missing configuration."""
    with pytest.raises(ValueError, match="Missing queue configuration"):
        QueueFactory.create_queue({})

@pytest.mark.asyncio
async def test_queue_factory_missing_fields():
    """Test queue factory with missing required fields."""
    config = {"queue": {"type": "redis"}}
    with pytest.raises(ValueError, match="Missing required fields"):
        QueueFactory.create_queue(config)

@pytest.mark.asyncio
async def test_queue_factory_missing_redis_url():
    """Test queue factory with missing Redis URL."""
    config = {
        "queue": {
            "type": "redis",
            "max_size": 100,
            "timeout": 1,
            "retry_policy": {"max_retries": 3, "base_delay": 0.1}
        }
    }
    with pytest.raises(ValueError, match="Missing redis_url"):
        QueueFactory.create_queue(config)

@pytest.mark.asyncio
async def test_redis_queue_invalid_max_size():
    """Test Redis queue with invalid max_size."""
    config = {
        "queue": {
            "type": "redis",
            "redis_url": "redis://localhost:6379/0",
            "max_size": "not a number",
            "timeout": 1,
            "retry_policy": {"max_retries": 3, "base_delay": 0.1}
        }
    }
    with pytest.raises(ValueError, match="max_size must be an integer"):
        RedisEventQueue(config)

@pytest.mark.asyncio
async def test_redis_queue_negative_max_size():
    """Test Redis queue with negative max_size."""
    config = {
        "queue": {
            "type": "redis",
            "redis_url": "redis://localhost:6379/0",
            "max_size": -1,
            "timeout": 1,
            "retry_policy": {"max_retries": 3, "base_delay": 0.1}
        }
    }
    with pytest.raises(ValueError, match="max_size must be non-negative"):
        RedisEventQueue(config)

@pytest.mark.asyncio
async def test_redis_enqueue_invalid_event(redis_queue):
    """Test enqueue with invalid event type."""
    success = await redis_queue.enqueue("not a dictionary")
    assert not success

@pytest.mark.asyncio
async def test_redis_enqueue_retry_success(redis_queue, mock_redis):
    """Test enqueue with successful retry."""
    # First attempt fails, second succeeds
    mock_redis.llen.side_effect = [
        redis.asyncio.ConnectionError("First attempt"),
        0  # Queue size on second attempt
    ]
    mock_redis.lpush.side_effect = [True]
    
    success = await redis_queue.enqueue({"event_type": "push"})
    assert success
    assert mock_redis.llen.call_count == 2
    assert mock_redis.lpush.call_count == 1

@pytest.mark.asyncio
async def test_redis_dequeue_retry_success(redis_queue, mock_redis):
    """Test dequeue with successful retry."""
    pipeline = mock_redis.pipeline.return_value
    # First attempt fails, second succeeds
    pipeline.execute.side_effect = [
        redis.asyncio.ConnectionError("First attempt"),
        [("gitbridge:events", json.dumps({"event_type": "push"}))]
    ]
    
    result = await redis_queue.dequeue()
    assert result == {"event_type": "push"}
    assert pipeline.execute.call_count == 2

@pytest.mark.asyncio
async def test_resilient_queue_cleanup(config):
    """Test resilient queue cleanup."""
    with patch("scripts.redis_queue.RedisEventQueue") as mock_redis_queue:
        # Make cleanup method async
        mock_redis_queue.return_value.cleanup = AsyncMock()
        queue = ResilientQueue(config)
        await queue.cleanup()
        mock_redis_queue.return_value.cleanup.assert_awaited_once()

@pytest.mark.asyncio
async def test_resilient_queue_dequeue_retry(config):
    """Test resilient queue dequeue with retry."""
    with patch("scripts.redis_queue.RedisEventQueue") as mock_redis_queue, \
         patch("scripts.redis_queue.EventQueue") as mock_async_queue:
        
        # First Redis dequeue fails, second succeeds
        mock_redis_queue.return_value.dequeue = AsyncMock(side_effect=Exception)
        mock_async_queue.return_value.dequeue = AsyncMock(return_value={"event_type": "push"})
        queue = ResilientQueue(config)
        
        # First dequeue should fail Redis and succeed with asyncio
        result = await queue.dequeue()
        assert result == {"event_type": "push"}
        assert not queue.using_redis
        mock_redis_queue.return_value.dequeue.assert_called_once()
        mock_async_queue.return_value.dequeue.assert_called_once()

@pytest.mark.asyncio
async def test_resilient_queue_get_queue_depth_retry(config):
    """Test resilient queue get_queue_depth with retry."""
    with patch("scripts.redis_queue.RedisEventQueue") as mock_redis_queue, \
         patch("scripts.redis_queue.EventQueue") as mock_async_queue:
        
        # Redis get_queue_depth fails
        mock_redis_queue.return_value.get_queue_depth = AsyncMock(side_effect=Exception)
        mock_async_queue.return_value.qsize = MagicMock(return_value=5)
        queue = ResilientQueue(config)
        
        depth = await queue.get_queue_depth()
        assert depth == 5
        assert not queue.using_redis
        mock_redis_queue.return_value.get_queue_depth.assert_called_once()

@pytest.mark.asyncio
async def test_redis_queue_get_queue_depth_error(redis_queue, mock_redis):
    """Test Redis queue get_queue_depth with error."""
    mock_redis.llen.side_effect = Exception("Redis error")
    
    depth = await redis_queue.get_queue_depth()
    assert depth == 0
    mock_redis.llen.assert_called_once()

@pytest.mark.asyncio
async def test_redis_queue_check_health_error(redis_queue, mock_redis):
    """Test Redis queue health check with error."""
    mock_redis.ping.side_effect = Exception("Redis error")
    
    health = await redis_queue.check_health()
    assert health["status"] == "unhealthy"
    assert "error" in health
    assert not health["redis_connected"]
    mock_redis.ping.assert_called_once()

@pytest.mark.asyncio
async def test_resilient_queue_dequeue_both_fail(config):
    """Test resilient queue dequeue when both queues fail."""
    with patch("scripts.redis_queue.RedisEventQueue") as mock_redis_queue, \
         patch("scripts.redis_queue.EventQueue") as mock_async_queue:
        
        mock_redis_queue.return_value.dequeue = AsyncMock(side_effect=Exception)
        mock_async_queue.return_value.dequeue = AsyncMock(side_effect=Exception)
        queue = ResilientQueue(config)
        
        result = await queue.dequeue()
        assert result is None
        assert not queue.using_redis
        mock_redis_queue.return_value.dequeue.assert_called_once()
        mock_async_queue.return_value.dequeue.assert_called_once()

@pytest.mark.asyncio
async def test_redis_queue_cleanup_error(redis_queue, mock_redis):
    """Test Redis queue cleanup with error."""
    mock_redis.aclose.side_effect = Exception("Cleanup error")
    await redis_queue.cleanup()  # Should not raise
    mock_redis.aclose.assert_called_once() 