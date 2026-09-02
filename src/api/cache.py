"""Upstash Redis client for caching predictions and anomalies."""

from __future__ import annotations

import structlog
import httpx
from config import settings

logger = structlog.get_logger(__name__)


class RedisClient:
    """Thin wrapper around Upstash Redis REST API."""

    def __init__(self) -> None:
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            # Ensure URL has no trailing slash
            base_url = settings.upstash_redis_url.rstrip("/")
            self._client = httpx.Client(
                base_url=base_url,
                timeout=30.0,
                headers={
                    "Authorization": f"Bearer {settings.upstash_redis_token}",
                },
            )
        return self._client

    def get(self, key: str) -> str | None:
        """Get a value from cache."""
        try:
            # The REST API endpoint is: GET /get/{key}
            resp = self._get_client().get(f"/get/{key}")
            if resp.status_code == 200:
                # Upstash returns {"result": "value"} or {"result": null} if not found
                data = resp.json()
                return data.get("result")
            elif resp.status_code == 404:
                logger.debug("Redis cache miss", key=key)
                return None
            else:
                logger.warning("Redis GET failed", key=key, status=resp.status_code)
        except Exception as exc:
            logger.error("Redis GET error", key=key, error=str(exc))
        return None

    def set(self, key: str, value: str, ttl: int) -> None:
        """
        Store a value in cache with TTL in seconds.
        Upstash endpoint: POST /set/{key} with body and ?EX={ttl}
        """
        try:
            resp = self._get_client().post(
                f"/set/{key}",
                content=value,
                params={"EX": ttl},
            )
            if resp.status_code != 200:
                logger.warning(
                    "Redis SET failed",
                    key=key,
                    status=resp.status_code,
                    response=resp.text,
                )
            else:
                logger.debug("Redis cache set", key=key, ttl=ttl)
        except Exception as exc:
            logger.error("Redis SET error", key=key, error=str(exc))

    def delete(self, key: str) -> None:
        """Delete a key from cache."""
        try:
            resp = self._get_client().delete(f"/del/{key}")
            if resp.status_code != 200:
                logger.warning(
                    "Redis DELETE failed",
                    key=key,
                    status=resp.status_code,
                )
        except Exception as exc:
            logger.error("Redis DELETE error", key=key, error=str(exc))


def get_redis_client() -> RedisClient:
    """Return a RedisClient instance (lazy-init)."""
    return RedisClient()
