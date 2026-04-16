from datetime import date
from typing import Any, Dict, List, Optional

import redis


class RedisCache:

    def __init__(self, client: redis.Redis):
        self.client = client

    @staticmethod
    def _decode(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode()
        return str(value) if value is not None else ""

    @staticmethod
    def _parse_int(value: Any, default: int = 0) -> int:
        try:
            return int(RedisCache._decode(value))
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _parse_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(RedisCache._decode(value))
        except (ValueError, TypeError):
            return default

    def get_hash_str(self, data: Dict, key: str, default: str = "") -> str:
        val = data.get(key.encode() if isinstance(key, str) else key, b'')
        return self._decode(val) or default

    def get_hash_int(self, data: Dict, key: str, default: int = 0) -> int:
        return self._parse_int(data.get(key.encode() if isinstance(key, str) else key), default)

    def get_hash_float(self, data: Dict, key: str, default: float = 0.0) -> float:
        return self._parse_float(data.get(key.encode() if isinstance(key, str) else key), default)

    def hgetall(self, key: str) -> Optional[Dict]:
        result = self.client.hgetall(key)
        return result if result else None

    def hset(self, key: str, mapping: Dict[str, Any], ttl: Optional[int] = None) -> None:
        pipe = self.client.pipeline()
        pipe.hset(key, mapping={k: str(v) for k, v in mapping.items()})
        if ttl:
            pipe.expire(key, ttl)
        pipe.execute()

    def smembers(self, key: str) -> List[str]:
        return [self._decode(m) for m in self.client.smembers(key)]

    def exists(self, key: str) -> bool:
        return bool(self.client.exists(key))


class CampaignKeys:

    @staticmethod
    def state(campaign_id: str) -> str:
        return f"campaign:{campaign_id}:state"

    @staticmethod
    def metrics(campaign_id: str) -> str:
        return f"campaign:{campaign_id}:metrics"


    @staticmethod
    def pi_config(campaign_id: str) -> str:
        return f"campaign:{campaign_id}:pi_config"

    @staticmethod
    def daily(campaign_id: str, dt: Optional[date] = None) -> str:
        dt = dt or date.today()
        return f"campaign:{campaign_id}:daily:{dt.strftime('%Y-%m-%d')}"

    @staticmethod
    def daily_today(campaign_id: str) -> str:
        return CampaignKeys.daily(campaign_id, date.today())
