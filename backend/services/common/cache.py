"""Redis caching module for frequently accessed data"""
import os
import json
import logging
from typing import Optional, Any
from datetime import timedelta

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger("cache")

# Redis configuration — prefer REDIS_URL (Docker), fall back to host/port
_REDIS_URL = os.getenv("REDIS_URL", "")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_TTL = int(os.getenv("REDIS_TTL", 3600))  # Default 1 hour

# Cache key prefixes
CACHE_PREFIX_RAG = "rag:"
CACHE_PREFIX_CLASSIFIER = "classifier:"
CACHE_PREFIX_OCR = "ocr:"
CACHE_PREFIX_USER = "user:"
CACHE_PREFIX_SESSION = "session:"


class RedisCache:
    """Redis cache wrapper with error handling"""
    
    def __init__(self):
        self.client = None
        self.enabled = False
        
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available. Install redis-py to enable caching.")
            return
        
        try:
            # Prefer REDIS_URL (full URL) over individual host/port
            if _REDIS_URL:
                self.client = redis.from_url(
                    _REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
            else:
                self.client = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    db=REDIS_DB,
                    password=REDIS_PASSWORD,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            # Test connection
            self.client.ping()
            self.enabled = True
            logger.info(f"Redis cache enabled: {_REDIS_URL or f'{REDIS_HOST}:{REDIS_PORT}'}")
        except Exception as e:
            logger.warning(f"Redis connection failed: {str(e)}. Caching disabled.")
            self.enabled = False
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.enabled:
            return None
        
        try:
            value = self.client.get(key)
            if value is not None:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except Exception as e:
            logger.error(f"Cache get error: {str(e)}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache with optional TTL"""
        if not self.enabled:
            return False
        
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            ttl = ttl or REDIS_TTL
            return self.client.setex(key, ttl, value)
        except Exception as e:
            logger.error(f"Cache set error: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.enabled:
            return False
        
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            logger.error(f"Cache delete error: {str(e)}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self.enabled:
            return False
        
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            logger.error(f"Cache exists error: {str(e)}")
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        if not self.enabled:
            return 0
        
        try:
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache clear pattern error: {str(e)}")
            return 0
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        if not self.enabled:
            return {"enabled": False}
        
        try:
            info = self.client.info()
            return {
                "enabled": True,
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "total_keys": info.get("db0", {}).get("keys", 0),
            }
        except Exception as e:
            logger.error(f"Cache stats error: {str(e)}")
            return {"enabled": True, "error": str(e)}


# Global cache instance
cache = RedisCache()


def cache_key(prefix: str, *parts) -> str:
    """Generate cache key from prefix and parts"""
    return f"{prefix}{':'.join(str(p) for p in parts)}"


def get_cached(key: str, default: Any = None) -> Any:
    """Get value from cache with default"""
    value = cache.get(key)
    return value if value is not None else default


def set_cached(key: str, value: Any, ttl: int = None) -> bool:
    """Set value in cache"""
    return cache.set(key, value, ttl)


def invalidate_cache(prefix: str) -> int:
    """Invalidate all cache keys with prefix"""
    return cache.clear_pattern(f"{prefix}*")
