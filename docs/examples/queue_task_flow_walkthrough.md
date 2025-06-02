# GitBridge Queue and Task Chain Flow Walkthrough

This document walks through the complete flow of a GitHub webhook event through the GitBridge queue system and task chain, demonstrating the integration between `event_queue.py` and `task_chain.py`.

## 1. Webhook Event Reception

When a webhook event is received from GitHub (e.g., a push event), it is first validated and then transformed into a `WebhookPayload`:

```json
{
    "event_type": "push",
    "repo": "octocat/Hello-World",
    "user": "octocat",
    "message": "Fix all the bugs",
    "files": ["src/app.py", "tests/test_app.py"]
}
```

## 2. Event Queue Processing

### 2.1 Enqueue Operation
The webhook payload is enqueued in `event_queue.py`:

```python
success = await event_queue.enqueue(payload)
# Queue depth is tracked for monitoring
current_depth = event_queue.get_queue_depth()
```

### 2.2 Retry Logic
If processing fails, the RetryHandler implements exponential backoff:

```python
# Base delay: 1s, Max retries: 3
# Retry delays: 1s -> 2s -> 4s
retry_handler = RetryHandler(base_delay=1.0, max_retries=3)
result = await retry_handler.retry_with_backoff(process_func)
```

### 2.3 Dequeue Operation
Events are dequeued asynchronously:

```python
webhook_payload = await event_queue.dequeue()
if webhook_payload:
    # Process the payload
    await process_webhook_event(webhook_payload)
```

## 3. Task Chain Lifecycle

### 3.1 Task Creation
A task is created from the webhook payload:

```python
task_id = f"task_{webhook_payload.event_type}_{int(datetime.utcnow().timestamp())}"
task = await task_chain.create_task(
    task_id=task_id,
    agent=webhook_payload.user
)
```

### 3.2 State Transitions
The task moves through various states:

1. **Created** → Initial state
2. **Queued** → Ready for processing
3. **ConsensusPending** → Awaiting agent consensus
4. **Resolved** → Task completed successfully
   
```python
# Example state transition
await task_chain.transition_state(task_id, TaskState.QUEUED)
```

### 3.3 Consensus Processing
When consensus is required:

```python
# Submit for consensus
consensus_result = await consensus_manager.process_task(task_id)

# Handle result
await task_chain.process_consensus_result(task_id, consensus_result)
```

## 4. Performance Monitoring

Performance metrics are collected throughout the flow:

```json
{
    "queue_metrics": {
        "depth": 42,
        "enqueue_latency_ms": 5,
        "dequeue_latency_ms": 8
    },
    "task_metrics": {
        "state_transition_latency_ms": 12,
        "consensus_latency_ms": 250,
        "total_processing_time_ms": 275
    }
}
```

## 5. Error Handling

### 5.1 Queue Errors
- Queue full
- Invalid payload
- Processing timeout

```python
try:
    await event_queue.enqueue(payload)
except asyncio.QueueFull:
    logger.error("Queue capacity reached")
```

### 5.2 Task Errors
- Invalid state transitions
- Consensus failures
- Timeout errors

```python
try:
    await task_chain.transition_state(task_id, new_state)
except ValidationError as e:
    logger.error(f"Invalid state transition: {e}")
```

## 6. Cleanup and Maintenance

### 6.1 Task Cleanup
Tasks are cleaned up after completion:

```python
await task_chain.cleanup_task(task_id)
```

### 6.2 Queue Maintenance
The queue can be stopped gracefully:

```python
await event_queue.stop()
```

## 7. Integration Example

Complete flow from webhook to resolved task:

```python
async def process_webhook_to_task():
    # 1. Receive webhook and enqueue
    await event_queue.enqueue(webhook_payload)
    
    # 2. Dequeue and process
    payload = await event_queue.dequeue()
    
    # 3. Create task
    task = await task_chain.create_task(
        task_id=generate_task_id(),
        agent=payload.user
    )
    
    # 4. Move through states
    await task_chain.transition_state(task.task_id, TaskState.QUEUED)
    await task_chain.transition_state(task.task_id, TaskState.CONSENSUS_PENDING)
    
    # 5. Process consensus
    consensus_result = await consensus_manager.process_task(task.task_id)
    await task_chain.process_consensus_result(task.task_id, consensus_result)
    
    # 6. Cleanup
    await task_chain.cleanup_task(task.task_id)
```

## 8. Configuration

The flow is configured via `webhook_config.yaml`:

```yaml
queue:
  type: "asyncio"
  max_size: 10000
  timeout: 30
  retry_policy:
    max_retries: 3
    base_delay: 1

task_chain:
  states:
    - Created
    - Queued
    - ConsensusPending
    - Resolved
    - Failed
  max_concurrent: 10
  consensus_required: true
```

## 9. Monitoring and Logging

### 9.1 Metrics
- Queue depth
- Processing latencies
- State transition times
- Error rates

### 9.2 Logs
- Event logs
- Task state changes
- Error conditions
- Performance data

## 10. Forward Compatibility

This implementation is designed to support:
- Redis queue backend (GBP13)
- Enhanced task metadata (GBP14)
- Rate limiting hooks (GBP17)
- Sub-350ms latency target (GBP24) 