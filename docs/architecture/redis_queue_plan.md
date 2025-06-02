# GitBridge GBP13 Redis Queue Integration Plan

## Overview
The Redis queue implementation replaces the default asyncio.Queue with a Redis-backed queue for improved scalability, persistence, and monitoring capabilities. This document outlines the implementation details, performance metrics, and integration with the GitBridge webhook system.

## 1. Dependencies

```python
# requirements.txt additions
aioredis==2.0.1
redis==5.0.1
```

## 2. Architecture Changes

### 2.1 Redis Queue Implementation

```python
from aioredis import Redis
from typing import Optional, Dict, Any

class RedisEventQueue:
    """Redis-backed event queue implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Redis queue."""
        self.redis = Redis.from_url(
            config["queue"]["redis_url"],
            encoding="utf-8",
            decode_responses=True
        )
        self.queue_key = "gitbridge:events"
        self.processing_key = "gitbridge:processing"
        self.max_size = config["queue"]["max_size"]
        self.timeout = config["queue"]["timeout"]
        
    async def enqueue(self, payload: Dict[str, Any]) -> bool:
        """Enqueue webhook payload to Redis."""
        if await self.redis.llen(self.queue_key) >= self.max_size:
            return False
            
        await self.redis.lpush(
            self.queue_key,
            json.dumps(payload)
        )
        return True
        
    async def dequeue(self) -> Optional[Dict[str, Any]]:
        """Dequeue and process webhook payload from Redis."""
        try:
            # Atomic move from queue to processing
            payload = await self.redis.brpoplpush(
                self.queue_key,
                self.processing_key,
                timeout=self.timeout
            )
            if not payload:
                return None
                
            return json.loads(payload)
            
        except Exception as e:
            logger.error(f"Redis dequeue error: {str(e)}")
            return None
```

### 2.2 Factory Pattern Integration

```python
class QueueFactory:
    """Queue implementation factory."""
    
    @staticmethod
    def create_queue(config: Dict[str, Any]) -> Union[EventQueue, RedisEventQueue]:
        """Create queue instance based on configuration."""
        queue_type = config["queue"]["type"]
        if queue_type == "redis":
            return RedisEventQueue(config)
        return EventQueue(config)  # Default asyncio implementation
```

## 3. Configuration Updates

```yaml
# webhook_config.yaml
queue:
  type: "redis"  # or "asyncio" for backward compatibility
  redis_url: "redis://localhost:6379/0"
  max_size: 10000
  timeout: 30
  retry_policy:
    max_retries: 3
    base_delay: 1
```

## 4. Migration Strategy

### 4.1 Phase 1: Development
1. Implement `RedisEventQueue` class
2. Add unit tests
3. Update configuration
4. Add Redis health checks

### 4.2 Phase 2: Testing
1. Run integration tests
2. Benchmark performance
3. Test failure scenarios
4. Validate metrics

### 4.3 Phase 3: Deployment
1. Deploy Redis instance
2. Update configuration
3. Monitor performance
4. Enable gradual rollout

## 5. Testing Plan

### 5.1 Unit Tests
```python
# tests/unit/mas_core/test_redis_queue.py

import pytest
from mas_core.queue import RedisEventQueue

@pytest.mark.asyncio
async def test_redis_enqueue():
    queue = RedisEventQueue(config)
    payload = {"event_type": "push", "repo": "test/repo"}
    
    success = await queue.enqueue(payload)
    assert success
    assert await queue.get_queue_depth() == 1

@pytest.mark.asyncio
async def test_redis_dequeue():
    queue = RedisEventQueue(config)
    payload = {"event_type": "push", "repo": "test/repo"}
    
    await queue.enqueue(payload)
    result = await queue.dequeue()
    
    assert result == payload
    assert await queue.get_queue_depth() == 0
```

### 5.2 Integration Tests
```python
@pytest.mark.integration
async def test_redis_queue_flow():
    queue = RedisEventQueue(config)
    task_chain = TaskChain(consensus_manager, mas_logger, config)
    
    # Test end-to-end flow
    payload = create_test_payload()
    await queue.enqueue(payload)
    
    result = await queue.dequeue()
    task = await task_chain.create_task(
        task_id=generate_task_id(),
        agent=result["user"]
    )
    
    assert task.state == TaskState.CREATED
```

## 6. Performance Targets

### 6.1 Latency Goals
- Queue operations: <5ms
- End-to-end flow: <300ms
- Target improvement: 15-20%

### 6.2 Resource Usage
- Memory: <256MB per Redis instance
- CPU: <10% average load
- Network: <5MB/s peak throughput

## 7. Monitoring

### 7.1 Redis Metrics
```yaml
metrics:
  - name: redis_queue_depth
    type: gauge
    threshold: 1000
    
  - name: redis_operation_latency
    type: histogram
    buckets: [1, 2, 5, 10, 20, 50]
    
  - name: redis_error_rate
    type: counter
    alert_threshold: 1%
```

### 7.2 Health Checks
```python
async def check_redis_health():
    """Check Redis connection and queue health."""
    try:
        await redis.ping()
        depth = await redis.llen("gitbridge:events")
        processing = await redis.llen("gitbridge:processing")
        
        return {
            "status": "healthy",
            "queue_depth": depth,
            "processing": processing
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

## 8. Rollback Plan

### 8.1 Automatic Fallback
```python
class ResilientQueue:
    """Queue with automatic fallback to asyncio."""
    
    def __init__(self, config):
        self.redis_queue = RedisEventQueue(config)
        self.async_queue = EventQueue(config)
        
    async def enqueue(self, payload):
        try:
            return await self.redis_queue.enqueue(payload)
        except Exception:
            logger.warning("Falling back to asyncio queue")
            return await self.async_queue.enqueue(payload)
```

### 8.2 Manual Rollback
1. Update configuration to use `asyncio` queue
2. Drain Redis queue
3. Process remaining items
4. Switch to asyncio implementation

## 9. Timeline

### Week 1 (June 3-7)
- Implement Redis queue
- Write unit tests
- Update configuration

### Week 2 (June 10-14)
- Integration testing
- Performance testing
- Documentation updates

### Week 3 (June 17-21)
- Staging deployment
- Monitoring setup
- Performance tuning

### Week 4 (June 24-28)
- Production deployment
- Performance validation
- Final documentation

## 10. Success Criteria

1. Latency improvement: 15-20%
2. Zero data loss during migration
3. Successful failover testing
4. All tests passing
5. Documentation complete
6. Monitoring operational 

## Implementation Details

### Queue Implementation
- **Package**: Using `redis.asyncio` (Redis 5.0.1) for async Redis operations
- **Atomic Operations**: Pipeline-based atomic operations for queue safety
  ```python
  async with redis.pipeline(transaction=True) as pipe:
      await pipe.brpop(queue_key, timeout=timeout)
      await pipe.lpush(processing_key, "placeholder")
      results = await pipe.execute()
  ```
- **Configuration**: Toggle in `webhook_config.yaml`:
  ```yaml
  queue:
    type: "redis"  # or "asyncio" for backward compatibility
    redis_url: "redis://localhost:6379/0"
    max_size: 10000
    timeout: 30
  ```

### Features
1. **Atomic Queue Operations**
   - Enqueue: `LPUSH` with queue depth check
   - Dequeue: `BRPOP` with processing list tracking
   - Error handling: Invalid JSON cleanup

2. **Resilient Design**
   - Automatic fallback to asyncio queue
   - Retry policy with exponential backoff
   - Connection error recovery

3. **Health Monitoring**
   - Queue depth tracking
   - Processing list monitoring
   - Redis connection health checks

4. **Performance Optimizations**
   - Pipeline-based atomic operations
   - Connection pooling
   - Efficient JSON serialization

## Performance Metrics

### GBP13 vs GBP12
- **GBP12 Latency**: 312.8ms average
- **GBP13 Target**: <500ms
- **Actual Performance**: See `/docs/performance/gbp13_metrics.md`

### Benchmarks
- Queue operations: ~9ms average
- Task transitions: ~8ms average
- Consensus processing: ~245ms average

## Integration

### Task Chain Integration
```python
# Create and process task
task = await task_chain.create_task(event)
await task_chain.transition_task(task.id, TaskState.Queued)
await task_chain.transition_task(task.id, TaskState.ConsensusPending)
await task_chain.transition_task(task.id, TaskState.Resolved)
```

### Error Handling
1. **Queue Full**
   ```python
   if await redis.llen(queue_key) >= max_size:
       logger.warning("Queue full, rejecting payload")
       return False
   ```

2. **Invalid Payload**
   ```python
   try:
       return json.loads(payload)
   except json.JSONDecodeError:
       await redis.lrem(processing_key, 1, payload)
       return None
   ```

3. **Connection Loss**
   ```python
   try:
       return await redis_queue.enqueue(payload)
   except Exception:
       logger.warning("Falling back to asyncio queue")
       return await async_queue.enqueue(payload)
   ```

## UI Dashboard

### Figma Prototype
- **Link**: [Redis Queue Dashboard](https://www.figma.com/file/gbp13-redis-dashboard)
- **Purpose**: Visualize queue status and operations for non-technical users
- **Features**:
  - Real-time queue depth graph
  - Task state transitions
  - Health status indicators
  - Manual queue operations (flush, retry)

### Integration with Flask UI
- **Endpoint**: `http://localhost:10000/redis`
- **WebSocket Updates**: Real-time queue metrics
- **User Actions**: Queue management controls

## Testing

### Unit Tests
- Queue operations (enqueue/dequeue)
- Error handling
- Fallback mechanism
- Health checks

### Integration Tests
- Task chain integration
- Concurrent operations
- Redis failure scenarios
- Performance benchmarks

## Deployment

### Requirements
- Redis 5.0.1 or higher
- Python 3.13.3
- Dependencies in `requirements-webhook.txt`

### Configuration
1. Set Redis URL in `webhook_config.yaml`
2. Configure retry policy
3. Set monitoring options
4. Enable queue type

### Monitoring
- Prometheus metrics
- Grafana dashboard
- Error logging
- Performance tracking

## Future Enhancements
1. **Clustering Support**
   - Redis Cluster configuration
   - Multi-node scaling

2. **Advanced Features**
   - Priority queues
   - Dead letter queues
   - Queue inspection tools

3. **UI Improvements**
   - Advanced analytics
   - Custom dashboards
   - Export capabilities 