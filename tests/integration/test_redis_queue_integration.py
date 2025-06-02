"""
Integration tests for Redis queue implementation.

Tests Redis queue functionality in a real environment with Redis server,
including rollback scenarios, fault handling, and concurrent operations.

MAS Lite Protocol v2.1 References:
- Section 4.2: Event Queue Requirements
- Section 4.3: Queue Operations
- Section 4.4: Error Handling
"""

import asyncio
import json
import pytest
import pytest_asyncio
import fakeredis.aioredis
from typing import Dict, Any, AsyncGenerator
from scripts.redis_queue import RedisEventQueue, ResilientQueue
from mas_core.queue import EventQueue

# Test configuration
TEST_CONFIG = {
    "queue": {
        "type": "redis",
        "redis_url": "redis://localhost:6379/0",
        "max_size": 100,
        "timeout": 0.1,
        "retry_policy": {
            "max_retries": 2,
            "base_delay": 0.01
        }
    }
}

@pytest_asyncio.fixture(scope="function")
async def fake_redis() -> AsyncGenerator[fakeredis.aioredis.FakeRedis, None]:
    """Create a fake Redis instance for testing."""
    server = fakeredis.aioredis.FakeRedis()
    yield server
    await server.aclose()

@pytest_asyncio.fixture(scope="function")
async def redis_queue(fake_redis: fakeredis.aioredis.FakeRedis) -> AsyncGenerator[RedisEventQueue, None]:
    """Create a Redis queue instance with fake Redis."""
    queue = RedisEventQueue(TEST_CONFIG)
    queue.redis = fake_redis
    yield queue
    await queue.cleanup()

@pytest_asyncio.fixture(scope="function")
async def resilient_queue(redis_queue: RedisEventQueue) -> AsyncGenerator[ResilientQueue, None]:
    """Create a resilient queue instance."""
    queue = ResilientQueue(TEST_CONFIG)
    queue.redis_queue = redis_queue
    yield queue
    await queue.cleanup()

@pytest.mark.integration
@pytest.mark.asyncio
async def test_queue_rollback(redis_queue: RedisEventQueue) -> None:
    """Test queue state rollback after Redis disconnect."""
    # Enqueue some events
    events = [
        {"type": "push", "id": i} for i in range(5)
    ]
    for event in events:
        assert await redis_queue.enqueue(event)
    
    # Verify queue depth
    assert await redis_queue.get_queue_depth() == 5
    
    # Simulate Redis disconnect
    await redis_queue.redis.aclose()
    
    # Verify queue state is preserved
    redis_queue.redis = await fakeredis.aioredis.create_redis_pool(
        TEST_CONFIG["queue"]["redis_url"]
    )
    assert await redis_queue.get_queue_depth() == 5
    
    # Verify events can be dequeued
    for i in range(5):
        event = await redis_queue.dequeue()
        assert event["id"] == i

@pytest.mark.integration
@pytest.mark.asyncio
async def test_fault_handling(redis_queue: RedisEventQueue) -> None:
    """Test handling of various fault scenarios."""
    # Test invalid JSON
    await redis_queue.redis.lpush(redis_queue.queue_key, "invalid json")
    event = await redis_queue.dequeue()
    assert event is None
    
    # Test network errors
    redis_queue.redis = None
    success = await redis_queue.enqueue({"type": "push"})
    assert not success
    
    # Test queue full
    redis_queue.redis = await fakeredis.aioredis.create_redis_pool(
        TEST_CONFIG["queue"]["redis_url"]
    )
    redis_queue.max_size = 1
    assert await redis_queue.enqueue({"type": "push"})
    assert not await redis_queue.enqueue({"type": "push"})

@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_operations(redis_queue: RedisEventQueue) -> None:
    """Test concurrent queue operations."""
    async def producer(n: int) -> None:
        for i in range(n):
            await redis_queue.enqueue({"type": "push", "id": i})
            await asyncio.sleep(0.01)
    
    async def consumer(n: int) -> list:
        events = []
        for _ in range(n):
            event = await redis_queue.dequeue()
            if event:
                events.append(event)
            await asyncio.sleep(0.01)
        return events
    
    # Run 10 producers and consumers concurrently
    producers = [producer(10) for _ in range(10)]
    consumers = [consumer(10) for _ in range(10)]
    
    # Wait for all operations to complete
    await asyncio.gather(*producers)
    results = await asyncio.gather(*consumers)
    
    # Verify results
    all_events = [event for consumer_events in results for event in consumer_events]
    assert len(all_events) == 100  # 10 producers * 10 events
    
    # Verify queue is empty
    assert await redis_queue.get_queue_depth() == 0

@pytest.mark.integration
@pytest.mark.asyncio
async def test_resilient_queue_failover(resilient_queue: ResilientQueue) -> None:
    """Test resilient queue failover to asyncio queue."""
    # Break Redis connection
    resilient_queue.redis_queue.redis = None
    
    # Enqueue should work with asyncio fallback
    assert await resilient_queue.enqueue({"type": "push"})
    assert not resilient_queue.using_redis
    
    # Dequeue should work with asyncio fallback
    event = await resilient_queue.dequeue()
    assert event == {"type": "push"}
    
    # Restore Redis connection
    resilient_queue.redis_queue.redis = await fakeredis.aioredis.create_redis_pool(
        TEST_CONFIG["queue"]["redis_url"]
    )
    resilient_queue.using_redis = True
    
    # Operations should work with Redis again
    assert await resilient_queue.enqueue({"type": "push"})
    event = await resilient_queue.dequeue()
    assert event == {"type": "push"}

@pytest.mark.integration
@pytest.mark.asyncio
async def test_performance(redis_queue: RedisEventQueue) -> None:
    """Test queue performance under load."""
    import time
    
    # Measure enqueue latency
    start_time = time.time()
    for i in range(100):
        await redis_queue.enqueue({"type": "push", "id": i})
    enqueue_latency = (time.time() - start_time) / 100
    
    # Measure dequeue latency
    start_time = time.time()
    for _ in range(100):
        await redis_queue.dequeue()
    dequeue_latency = (time.time() - start_time) / 100
    
    # Verify latencies are within target
    assert enqueue_latency < 0.5  # 500ms target
    assert dequeue_latency < 0.5  # 500ms target
    
    # Log performance metrics
    with open("docs/performance/gbp13_metrics.md", "a") as f:
        f.write(f"\n## Redis Queue Performance\n")
        f.write(f"- Average enqueue latency: {enqueue_latency*1000:.1f}ms\n")
        f.write(f"- Average dequeue latency: {dequeue_latency*1000:.1f}ms\n")
        f.write(f"- Total average latency: {(enqueue_latency + dequeue_latency)*1000:.1f}ms\n") 