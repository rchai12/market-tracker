import time

import redis


class RateLimiter:
    """Redis-backed sliding window rate limiter."""

    def __init__(self, redis_client: redis.Redis, source: str, max_requests: int, window_seconds: int):
        self.redis = redis_client
        self.key = f"rate_limit:{source}"
        self.max_requests = max_requests
        self.window = window_seconds

    def acquire(self) -> bool:
        """Returns True if request is allowed, False if rate limited."""
        now = time.time()
        pipe = self.redis.pipeline()

        # Remove expired entries
        pipe.zremrangebyscore(self.key, 0, now - self.window)
        # Count current entries
        pipe.zcard(self.key)
        # Add current request
        pipe.zadd(self.key, {str(now): now})
        # Set expiry on the key
        pipe.expire(self.key, self.window)

        results = pipe.execute()
        current_count = results[1]

        if current_count >= self.max_requests:
            # Remove the entry we just added
            self.redis.zrem(self.key, str(now))
            return False

        return True

    def wait_and_acquire(self) -> None:
        """Block until a request slot is available."""
        while not self.acquire():
            time.sleep(0.1)
