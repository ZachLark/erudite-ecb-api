# GBP15 Routing Plan

## Overview
The GitBridge routing system will handle task distribution between multiple AI services (Claude/Grok/ChatGPT) through the Redis queue system.

## Components

### Redis Queue Integration
- Queue structure for task distribution
- Priority-based routing
- Load balancing between AI services
- Error handling and retries

### AI Router (`/scripts/ai_router.py`)
- Service discovery and health checks
- Task type classification
- AI service selection logic
- Response aggregation
- Fallback handling

## Implementation Details
1. Task Classification
   - Analyze incoming tasks
   - Determine optimal AI service
   - Set task priority

2. Load Balancing
   - Monitor AI service health
   - Track response times
   - Adjust routing based on performance

3. Error Handling
   - Retry logic
   - Service failover
   - Error reporting

## Metrics
- Response times per AI service
- Error rates
- Queue latency
- Service availability

## Components

### 1. Event Router
- Redis queue consumer
- Event type classification
- Task distribution
- Error handling

### 2. AI Router
- Multi-AI support:
  * Claude
  * Grok
  * ChatGPT
- Provider selection
- Load balancing
- Failover handling

### 3. Task Processor
- Task state management
- AI request formatting
- Response processing
- Result validation

### 4. Consensus Manager
- Multi-AI consensus
- Result comparison
- Conflict resolution
- Decision logging

## Implementation

### Event Router (`event_router.py`)
```python
class EventRouter:
    def __init__(self, config):
        self.redis_queue = RedisEventQueue(config)
        self.ai_router = AIRouter(config)
        self.task_processor = TaskProcessor(config)
        
    async def route_event(self, event):
        # Classify event
        event_type = self.classify_event(event)
        
        # Select AI providers
        providers = self.ai_router.select_providers(event_type)
        
        # Create and process tasks
        tasks = [
            self.task_processor.create_task(event, provider)
            for provider in providers
        ]
        
        # Get results and consensus
        results = await asyncio.gather(*tasks)
        consensus = await self.get_consensus(results)
        
        return consensus
```

### AI Router (`ai_router.py`)
```python
class AIRouter:
    def __init__(self, config):
        self.providers = {
            "claude": ClaudeProvider(config),
            "grok": GrokProvider(config),
            "chatgpt": ChatGPTProvider(config)
        }
        
    def select_providers(self, event_type):
        # Select providers based on event type
        if event_type == "code_review":
            return ["claude", "grok"]
        elif event_type == "documentation":
            return ["chatgpt", "claude"]
        else:
            return ["grok"]  # Default
```

### Task Processor (`task_processor.py`)
```python
class TaskProcessor:
    def __init__(self, config):
        self.config = config
        
    async def create_task(self, event, provider):
        # Format request for provider
        request = self.format_request(event, provider)
        
        # Send to AI provider
        response = await self.providers[provider].process(request)
        
        # Validate response
        if self.validate_response(response):
            return response
        else:
            raise TaskError("Invalid response")
```

## Routing Logic

### 1. Event Classification
- Webhook event types
- Code changes
- Documentation updates
- Issue management

### 2. Provider Selection
- Event type matching
- Provider capabilities
- Load balancing
- Health status

### 3. Task Distribution
- Parallel processing
- Resource allocation
- Priority handling
- Rate limiting

### 4. Result Handling
- Response validation
- Consensus building
- Action execution
- Status updates

## Error Handling

### 1. Provider Errors
- Connection failures
- Timeout handling
- Rate limit errors
- Invalid responses

### 2. Task Errors
- State transitions
- Data validation
- Resource limits
- Cleanup procedures

### 3. Recovery
- Automatic retries
- Provider failover
- Task rescheduling
- Error reporting

## Performance

### 1. Metrics
- Routing latency
- Provider response times
- Task completion rates
- Error frequencies

### 2. Optimization
- Connection pooling
- Request batching
- Response caching
- Load shedding

## Testing

### 1. Unit Tests
- Router logic
- Provider selection
- Task processing
- Error handling

### 2. Integration Tests
- Multi-provider scenarios
- Consensus building
- Failover handling
- Performance testing

## Deployment

### 1. Configuration
- Provider settings
- Routing rules
- Rate limits
- Monitoring

### 2. Scaling
- Horizontal scaling
- Load balancing
- Cache distribution
- Task partitioning

## Documentation
- Architecture overview
- Provider integration
- Configuration guide
- Troubleshooting 