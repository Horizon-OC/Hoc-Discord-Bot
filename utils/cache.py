"""
Simple in-memory cache without Redis
"""
from typing import Any, Optional
from datetime import datetime, timedelta
from utils.logger import bot_logger

class Cache:
    """Simple in-memory cache"""
    
    def __init__(self):
        self.cache = {}
        self.expiry = {}
        self.connected = True  # Always "connected" for in-memory cache
    
    async def connect(self):
        """No-op for compatibility"""
        bot_logger.info("Using in-memory cache")
    
    async def disconnect(self):
        """No-op for compatibility"""
        pass
    
    def _is_expired(self, key: str) -> bool:
        """Check if cache entry is expired"""
        if key not in self.expiry:
            return True
        return datetime.now() > self.expiry[key]
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache"""
        if key not in self.cache or self._is_expired(key):
            return None
        return self.cache[key]
    
    async def set(self, key: str, value: Any, ttl: int = 3600):
        """Set a value in cache"""
        self.cache[key] = value
        self.expiry[key] = datetime.now() + timedelta(seconds=ttl)
    
    async def delete(self, key: str):
        """Delete a key from cache"""
        self.cache.pop(key, None)
        self.expiry.pop(key, None)
    
    async def clear_pattern(self, pattern: str):
        """Clear all keys matching a pattern"""
        keys_to_delete = [k for k in self.cache.keys() if pattern.replace('*', '') in k]
        for key in keys_to_delete:
            await self.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache"""
        return key in self.cache and not self._is_expired(key)
    
    # Guild-specific cache helpers
    async def get_guild_config(self, guild_id: int) -> Optional[dict]:
        """Get guild config from cache"""
        return await self.get(f"guild_config:{guild_id}")
    
    async def set_guild_config(self, guild_id: int, config: dict):
        """Set guild config in cache"""
        await self.set(f"guild_config:{guild_id}", config)
    
    async def invalidate_guild_config(self, guild_id: int):
        """Invalidate guild config cache"""
        await self.delete(f"guild_config:{guild_id}")
    
    async def get_user_warnings(self, guild_id: int, user_id: int) -> Optional[list]:
        """Get user warnings from cache"""
        return await self.get(f"warnings:{guild_id}:{user_id}")
    
    async def set_user_warnings(self, guild_id: int, user_id: int, warnings: list):
        """Set user warnings in cache"""
        await self.set(f"warnings:{guild_id}:{user_id}", warnings, ttl=300)
    
    async def invalidate_user_warnings(self, guild_id: int, user_id: int):
        """Invalidate user warnings cache"""
        await self.delete(f"warnings:{guild_id}:{user_id}")