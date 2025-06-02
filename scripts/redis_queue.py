"""
Redis queue implementation for GitBridge.

This module provides Redis-backed queue implementation for GitBridge's event processing
system, with automatic failover to asyncio queue.

MAS Lite Protocol v2.1 References:
- Section 4.2: Event Queue Requirements
- Section 4.3: Queue Operations
- Section 4.4: Error Handling
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, Union
import redis.asyncio
from mas_core.queue import EventQueue
from mas_core.utils.logging import MASLogger

logger = MASLogger(__name__)

class QueueError(Exception):
    """Base class for queue errors."""
    pass

class QueueFullError(QueueError):
    """Raised when queue is full."""
    pass

class QueueConnectionError(QueueError):
    """Raised when Redis connection fails."""
    pass

class QueueFactory:
    """Factory for creating queue instances."""
    
    @staticmethod
    def create_queue(config: Dict[str, Any]) -> Union[EventQueue, 'RedisEventQueue']:
        """Create queue instance based on configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Union[EventQueue, RedisEventQueue]: Queue instance
            
        Raises:
            ValueError: If configuration is invalid
        """
        if "queue" not in config:
            raise ValueError("Missing queue configuration")
            
        queue_config = config["queue"]
        required_fields = ["type", "max_size", "timeout", "retry_policy"]
        missing_fields = [f for f in required_fields if f not in queue_config]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            
        queue_type = queue_config["type"]
        if queue_type == "redis":
            if "redis_url" not in queue_config:
                raise ValueError("Missing redis_url in configuration")
            return RedisEventQueue(config)
        return EventQueue(config)

class RedisEventQueue(EventQueue):
    """Redis-backed event queue."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Redis queue.
        
        Args:
            config: Configuration dictionary containing queue settings
                   Required keys:
                   - queue.redis_url: Redis connection URL
                   - queue.max_size: Maximum queue size
                   - queue.timeout: Operation timeout in seconds
                   - queue.retry_policy: Retry policy settings
                   
        Raises:
            ValueError: If configuration is invalid
        """
        if not isinstance(config.get("queue", {}).get("max_size"), int):
            raise ValueError("max_size must be an integer")
        if config["queue"]["max_size"] < 0:
            raise ValueError("max_size must be non-negative")
            
        self.redis_url = config["queue"]["redis_url"]
        self.max_size = config["queue"]["max_size"]
        self.timeout = config["queue"]["timeout"]
        self.retry_policy = config["queue"]["retry_policy"]
        
        try:
            self.redis = redis.asyncio.Redis.from_url(self.redis_url)
        except Exception as e:
            raise ValueError(f"Invalid Redis URL: {str(e)}")
            
        self.queue_key = "gitbridge:events"
        self.processing_key = "gitbridge:processing"
        
    async def enqueue(self, event: Dict[str, Any]) -> bool:
        """Enqueue an event.
        
        Args:
            event: Event to enqueue
            
        Returns:
            bool: True if enqueued successfully
            
        Raises:
            QueueFullError: If queue is full
            QueueConnectionError: If Redis connection fails
        """
        try:
            # Validate event
            if not isinstance(event, dict):
                raise ValueError("Event must be a dictionary")
                
            # Convert event to JSON string
            event_json = json.dumps(event)
            
            # Check queue size with retry
            for attempt in range(self.retry_policy["max_retries"]):
                try:
                    size = await self.redis.llen(self.queue_key)
                    if size >= self.max_size:
                        logger.error("Queue is full")
                        raise QueueFullError("Queue is full")
                        
                    # Add event to queue
                    await self.redis.lpush(self.queue_key, event_json)
                    return True
                    
                except redis.asyncio.ConnectionError as e:
                    if attempt == self.retry_policy["max_retries"] - 1:
                        raise QueueConnectionError(f"Redis connection failed: {str(e)}")
                    await asyncio.sleep(self.retry_policy["base_delay"] * (2 ** attempt))
                    
        except (QueueFullError, QueueConnectionError) as e:
            logger.error(str(e))
            return False
        except Exception as e:
            logger.error(f"Redis enqueue error: {str(e)}")
            return False
            
    async def dequeue(self) -> Optional[Dict[str, Any]]:
        """Dequeue an event.
        
        Returns:
            Optional[Dict[str, Any]]: Event if available, None otherwise
            
        Raises:
            QueueConnectionError: If Redis connection fails
        """
        try:
            # Use pipeline for atomic operations with retry
            for attempt in range(self.retry_policy["max_retries"]):
                try:
                    async with self.redis.pipeline(transaction=True) as pipe:
                        # Get event from queue with timeout
                        await pipe.brpop(self.queue_key, timeout=self.timeout)
                        # Add placeholder to processing list
                        await pipe.lpush(self.processing_key, "placeholder")
                        results = await pipe.execute()
                        
                        if not results[0]:  # Timeout
                            await self.redis.lpop(self.processing_key)  # Remove placeholder
                            return None
                            
                        # Parse JSON string
                        _, event_json = results[0]  # brpop returns (key, value)
                        try:
                            return json.loads(event_json)
                        except json.JSONDecodeError:
                            # Remove invalid JSON from processing
                            await self.redis.lrem(self.processing_key, 1, event_json)
                            return None
                            
                except redis.asyncio.ConnectionError as e:
                    if attempt == self.retry_policy["max_retries"] - 1:
                        raise QueueConnectionError(f"Redis connection failed: {str(e)}")
                    await asyncio.sleep(self.retry_policy["base_delay"] * (2 ** attempt))
                    
        except QueueConnectionError as e:
            logger.error(str(e))
            return None
        except Exception as e:
            logger.error(f"Redis dequeue error: {str(e)}")
            return None
            
    async def get_queue_depth(self) -> int:
        """Get current queue depth.
        
        Returns:
            int: Current queue depth
        """
        try:
            return await self.redis.llen(self.queue_key)
            
        except Exception as e:
            logger.error(f"Redis queue depth error: {str(e)}")
            return 0
            
    async def check_health(self) -> Dict[str, Any]:
        """Check queue health.
        
        Returns:
            Dict[str, Any]: Health status
        """
        try:
            await self.redis.ping()
            queue_depth = await self.redis.llen(self.queue_key)
            processing = await self.redis.llen(self.processing_key)
            
            return {
                "status": "healthy",
                "queue_depth": queue_depth,
                "processing": processing,
                "redis_connected": True
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "redis_connected": False
            }
            
    async def cleanup(self) -> None:
        """Clean up queue resources."""
        try:
            await self.redis.aclose()
        except Exception as e:
            logger.error(f"Redis cleanup error: {str(e)}")

class ResilientQueue(EventQueue):
    """Resilient queue with Redis and asyncio fallback."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize resilient queue.
        
        Args:
            config: Configuration dictionary containing queue settings
                   Required keys:
                   - queue.redis_url: Redis connection URL
                   - queue.max_size: Maximum queue size
                   - queue.timeout: Operation timeout in seconds
                   - queue.retry_policy: Retry policy settings
        """
        self.redis_queue = RedisEventQueue(config)
        self.asyncio_queue = EventQueue(config)  # Pass config
        self.retry_policy = config["queue"]["retry_policy"]
        self.using_redis = True
        
    async def enqueue(self, event: Dict[str, Any]) -> bool:
        """Enqueue an event.
        
        Args:
            event: Event to enqueue
            
        Returns:
            bool: True if enqueued successfully
        """
        if self.using_redis:
            try:
                success = await self.redis_queue.enqueue(event)
                if success:
                    return True
                    
            except Exception as e:
                logger.error(f"Redis enqueue error: {str(e)}")
                self.using_redis = False
                
        # Redis failed or not using Redis, try asyncio queue
        try:
            await self.asyncio_queue.enqueue(event)
            return True
            
        except Exception as e:
            logger.error(f"Asyncio enqueue error: {str(e)}")
            return False
            
    async def dequeue(self) -> Optional[Dict[str, Any]]:
        """Dequeue an event.
        
        Returns:
            Optional[Dict[str, Any]]: Event if available, None otherwise
        """
        if self.using_redis:
            try:
                event = await self.redis_queue.dequeue()
                if event is not None:
                    return event
                    
            except Exception as e:
                logger.error(f"Redis dequeue error: {str(e)}")
                self.using_redis = False
                
        # Redis failed or not using Redis, try asyncio queue
        try:
            return await self.asyncio_queue.dequeue()
            
        except Exception as e:
            logger.error(f"Asyncio dequeue error: {str(e)}")
            return None
            
    async def get_queue_depth(self) -> int:
        """Get current queue depth.
        
        Returns:
            int: Current queue depth
        """
        if self.using_redis:
            try:
                return await self.redis_queue.get_queue_depth()
                
            except Exception:
                self.using_redis = False
                
        return self.asyncio_queue.qsize()
        
    async def cleanup(self) -> None:
        """Clean up queue resources."""
        await self.redis_queue.cleanup() 