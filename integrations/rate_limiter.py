"""
Rate Limiter for GitHub Webhooks.

This module implements rate limiting using Redis as a backend store
to support distributed deployments.
"""

import time
from typing import Tuple, Optional
import redis
from mas_core.utils.logging import MASLogger

class RateLimiter:
    """Rate limiter implementation using Redis."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        default_limit: int = 5000,
        window_seconds: int = 3600
    ) -> None:
        """
        Initialize rate limiter.

        Args:
            redis_url: Redis connection URL
            default_limit: Default hourly limit
            window_seconds: Time window in seconds
        """
        self.redis = redis.from_url(redis_url)
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.logger = MASLogger("rate_limiter")

    def is_allowed(self, key: str) -> Tuple[bool, Optional[int]]:
        """
        Check if request is allowed under rate limit.

        Args:
            key: Identifier for rate limit (e.g. IP or API key)

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        current = int(time.time())
        window_key = f"{key}:{current // self.window_seconds}"

        try:
            # Increment counter for current window
            count = self.redis.incr(window_key)
            
            # Set expiry if first request in window
            if count == 1:
                self.redis.expire(window_key, self.window_seconds)

            if count > self.default_limit:
                retry_after = self.window_seconds - (current % self.window_seconds)
                self.logger.log_event(
                    source="rate_limiter",
                    event_type="rate_limit_exceeded",
                    payload={
                        "key": key,
                        "count": count,
                        "limit": self.default_limit,
                        "retry_after": retry_after
                    }
                )
                return False, retry_after

            return True, None

        except redis.RedisError as e:
            self.logger.log_error(
                error_type="rate_limiter_error",
                message=str(e),
                context={"key": key}
            )
            # Fail open if Redis is down
            return True, None

    def get_limit_info(self, key: str) -> dict:
        """
        Get current rate limit information.

        Args:
            key: Identifier for rate limit

        Returns:
            Dict with limit information
        """
        current = int(time.time())
        window_key = f"{key}:{current // self.window_seconds}"

        try:
            count = int(self.redis.get(window_key) or 0)
            ttl = self.redis.ttl(window_key)
            
            return {
                "total": self.default_limit,
                "remaining": max(0, self.default_limit - count),
                "reset": current + (ttl if ttl > 0 else self.window_seconds),
                "used": count
            }
        except redis.RedisError as e:
            self.logger.log_error(
                error_type="rate_limiter_error",
                message=str(e),
                context={"key": key}
            )
            return {
                "total": self.default_limit,
                "remaining": self.default_limit,
                "reset": current + self.window_seconds,
                "used": 0
            } 