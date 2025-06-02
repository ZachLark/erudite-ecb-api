#!/usr/bin/env python3
"""
Event Queue System for GitBridge Webhook Processing.
Handles async queuing of webhook payloads with retry logic.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

# Configure logging
logger = logging.getLogger(__name__)

class WebhookPayload(BaseModel):
    """Webhook payload model with validation."""
    event_type: str
    repo: str
    user: Optional[str] = None
    message: Optional[str] = None
    files: list = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = 0

class RetryHandler:
    """Handles retry logic with exponential backoff."""
    
    def __init__(self, base_delay: float = 1.0, max_retries: int = 3):
        """
        Initialize RetryHandler.
        
        Args:
            base_delay: Base delay in seconds
            max_retries: Maximum number of retry attempts
        """
        self.base_delay = base_delay
        self.max_retries = max_retries
        
    async def retry_with_backoff(self, func, *args, **kwargs) -> Optional[Any]:
        """
        Execute function with retry and exponential backoff.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Optional[Any]: Function result if successful
        """
        retry_count = 0
        last_error = None
        
        while retry_count <= self.max_retries:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                retry_count += 1
                
                if retry_count > self.max_retries:
                    logger.error(
                        f"Max retries ({self.max_retries}) exceeded: {str(e)}"
                    )
                    break
                    
                delay = self.base_delay * (2 ** (retry_count - 1))
                logger.warning(
                    f"Retry {retry_count}/{self.max_retries} after {delay}s: {str(e)}"
                )
                await asyncio.sleep(delay)
                
        raise last_error

class EventQueue:
    """Manages async queue of webhook events."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize EventQueue.
        
        Args:
            config: Configuration dictionary from webhook_config.yaml
        """
        queue_config = config.get("queue", {})
        self.max_size = queue_config.get("max_size", 10000)
        self.timeout = queue_config.get("timeout", 30)
        
        retry_config = queue_config.get("retry_policy", {})
        self.retry_handler = RetryHandler(
            base_delay=retry_config.get("base_delay", 1),
            max_retries=retry_config.get("max_retries", 3)
        )
        
        self.queue = asyncio.Queue(maxsize=self.max_size)
        self._running = False
        self._tasks = set()
        
    async def enqueue(self, payload: Dict[str, Any]) -> bool:
        """
        Validate and enqueue webhook payload.
        
        Args:
            payload: Webhook payload dictionary
            
        Returns:
            bool: True if enqueued successfully
        """
        try:
            # Validate payload
            webhook_payload = WebhookPayload(**payload)
            
            # Add to queue
            await self.queue.put(webhook_payload)
            logger.info(
                f"Enqueued {webhook_payload.event_type} event for {webhook_payload.repo}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to enqueue payload: {str(e)}")
            return False
            
    async def dequeue(self) -> Optional[WebhookPayload]:
        """
        Dequeue and process next webhook payload.
        
        Returns:
            Optional[WebhookPayload]: Processed payload if successful
        """
        try:
            # Get next payload with timeout
            payload = await asyncio.wait_for(
                self.queue.get(),
                timeout=self.timeout
            )
            
            # Process with retry logic
            result = await self.retry_handler.retry_with_backoff(
                self._process_payload,
                payload
            )
            
            self.queue.task_done()
            return result
            
        except asyncio.TimeoutError:
            logger.debug("Queue dequeue timeout")
            return None
        except Exception as e:
            logger.error(f"Error processing payload: {str(e)}")
            return None
            
    async def _process_payload(self, payload: WebhookPayload) -> WebhookPayload:
        """
        Process webhook payload.
        
        Args:
            payload: WebhookPayload instance
            
        Returns:
            WebhookPayload: Processed payload
        """
        # Add processing logic here
        # This will be integrated with task_generator.py and task_chain.py
        return payload
        
    def get_queue_depth(self) -> int:
        """
        Get current queue size.
        
        Returns:
            int: Current queue size
        """
        return self.queue.qsize()
        
    async def start(self):
        """Start queue processing."""
        self._running = True
        while self._running:
            task = asyncio.create_task(self.dequeue())
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            
    async def stop(self):
        """Stop queue processing."""
        self._running = False
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            
    async def __aenter__(self):
        """Context manager entry."""
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.stop() 