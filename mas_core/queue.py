"""
Event queue implementation for GitBridge.

This module provides the base event queue implementation using asyncio.Queue.
It serves as the default queue implementation and as a fallback for Redis queue.

MAS Lite Protocol v2.1 References:
- Section 4.2: Event Queue Requirements
- Section 4.3: Queue Operations
- Section 4.4: Error Handling
"""

import asyncio
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class EventQueue:
    """Asyncio-based event queue implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize asyncio queue.
        
        Args:
            config: Configuration dictionary containing queue settings
                   Required keys:
                   - queue.max_size: Maximum queue size
                   - queue.timeout: Operation timeout in seconds
        """
        self.queue = asyncio.Queue(maxsize=config["queue"]["max_size"])
        self.timeout = config["queue"]["timeout"]
        
    async def enqueue(self, payload: Dict[str, Any]) -> bool:
        """Enqueue webhook payload.
        
        Args:
            payload: Dictionary containing webhook event data
            
        Returns:
            bool: True if enqueue successful, False if queue full
        """
        try:
            await asyncio.wait_for(
                self.queue.put(payload),
                timeout=self.timeout
            )
            logger.debug("Successfully enqueued payload")
            return True
            
        except asyncio.TimeoutError:
            logger.warning("Queue full, rejecting payload")
            return False
            
        except Exception as e:
            logger.error(f"Queue enqueue error: {str(e)}")
            return False
            
    async def dequeue(self) -> Optional[Dict[str, Any]]:
        """Dequeue webhook payload.
        
        Returns:
            Optional[Dict[str, Any]]: Dequeued payload or None if timeout/error
        """
        try:
            payload = await asyncio.wait_for(
                self.queue.get(),
                timeout=self.timeout
            )
            self.queue.task_done()
            return payload
            
        except asyncio.TimeoutError:
            return None
            
        except Exception as e:
            logger.error(f"Queue dequeue error: {str(e)}")
            return None
            
    async def get_queue_depth(self) -> int:
        """Get current queue depth.
        
        Returns:
            int: Number of items in queue
        """
        return self.queue.qsize()
        
    async def check_health(self) -> Dict[str, Any]:
        """Check queue health.
        
        Returns:
            Dict[str, Any]: Health check results
        """
        try:
            return {
                "status": "healthy",
                "queue_depth": self.queue.qsize(),
                "processing": 0  # Asyncio queue doesn't track processing items
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
            
    async def cleanup(self) -> None:
        """Clean up queue resources."""
        # No cleanup needed for asyncio queue
        pass 