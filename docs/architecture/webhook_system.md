# GitBridge Webhook System

## Overview
The GitBridge webhook system processes GitHub events through a Redis-backed queue system, ensuring reliable event handling and task execution.

## Authentication
### GITBRIDGE_TOKEN
The system uses a GitHub Personal Access Token (PAT) with the following required scopes:
- `repo`: Full control of private repositories
- `workflow`: Access to GitHub Actions workflows
- `write:packages`: Write access to packages

To configure the token:
1. Generate a PAT in GitHub Settings > Developer Settings > Personal Access Tokens
2. Add the token to your repository's secrets as `GITBRIDGE_TOKEN`
3. Update GitHub Actions workflows to use `${{ secrets.GITBRIDGE_TOKEN }}`

## Event Flow
1. GitHub webhook sends event to GitBridge endpoint
2. Event is validated and enqueued in Redis
3. Task Chain processes event based on type
4. Results are sent back to GitHub via API

## Redis Queue Integration
The Redis queue system (`redis.asyncio`) provides:
- Atomic operations for event handling
- Automatic failover to asyncio queue
- Health monitoring and metrics
- 89.23% test coverage

## Configuration
### webhook_config.yaml
```yaml
queue:
  type: redis
  redis_url: redis://localhost:6379/0
  max_size: 1000
  timeout: 5.0
  retry_policy:
    max_retries: 3
    base_delay: 0.1

github:
  token: ${GITBRIDGE_TOKEN}
  api_version: 2022-11-28
  webhook_secret: ${WEBHOOK_SECRET}

metrics:
  latency_target: 500  # ms
  queue_depth_warning: 100
  health_check_interval: 60  # seconds
```

## Performance
- Current latency: 312.8ms (target: <500ms)
- Queue depth monitoring
- Automatic health checks
- Error rate tracking

## Integration Tests
See `/tests/integration/test_redis_queue_integration.py` for:
- Rollback scenarios
- Fault handling
- Concurrent load testing
- Redis failover verification

## UI Integration
The Redis dashboard (see `/docs/figma/gbp13_redis_dashboard.fig`) provides:
- Real-time queue status
- Event processing metrics
- Health monitoring
- Manual queue management

## Error Handling
1. Connection failures: Automatic retry with exponential backoff
2. Queue full: Event rejection with notification
3. Invalid events: Logging and quarantine
4. Redis unavailable: Failover to asyncio queue

## Monitoring
- Queue depth alerts
- Latency tracking
- Error rate monitoring
- Health check dashboard

## Security
- Webhook secret validation
- Token scope restrictions
- Rate limiting
- Event validation

## References
- [GitHub Webhooks Guide](https://docs.github.com/webhooks)
- [Redis Documentation](https://redis.io/docs)
- [MAS Lite Protocol v2.1](https://maslite.dev/docs) 