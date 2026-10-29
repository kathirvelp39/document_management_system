import os

import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=3,
    socket_timeout=3,
)


def check_redis_connection() -> bool:
    """Check whether Redis is reachable."""
    try:
        return bool(redis_client.ping())
    except redis.RedisError:
        return False