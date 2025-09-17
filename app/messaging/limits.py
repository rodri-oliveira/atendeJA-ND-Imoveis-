from __future__ import annotations
import time
from typing import Optional

import redis  # type: ignore

from app.core.config import settings


class RateLimiter:
    """Rate limit por contato e global usando Redis; fallback em memória.

    - por_contato_interval_s: limite de 1 mensagem por intervalo por contato
    - global_per_minute: limite global por minuto (tenant)
    """

    def __init__(self, tenant_id: int | str, por_contato_interval_s: int = 2, global_per_minute: int = 60):
        self.tenant_id = str(tenant_id)
        self.por_contato_interval_s = por_contato_interval_s
        self.global_per_minute = global_per_minute
        self._r = None
        try:
            self._r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
            # teste de conexão light
            self._r.ping()
        except Exception:
            self._r = None
        # fallback memória
        self._mem_last: dict[str, float] = {}
        self._mem_minute: dict[int, int] = {}

    def _key_contact(self, wa_id: str) -> str:
        return f"rl:{self.tenant_id}:{wa_id}"

    def _key_global(self) -> str:
        return f"rlg:{self.tenant_id}"

    def allow(self, wa_id: str) -> bool:
        now = time.time()
        # por contato
        if self._r:
            k = self._key_contact(wa_id)
            # set if not exists with TTL acting as interval guard
            ok = self._r.set(k, "1", nx=True, ex=self.por_contato_interval_s)
            if not ok:
                return False
        else:
            last = self._mem_last.get(wa_id, 0.0)
            if now - last < self.por_contato_interval_s:
                return False
            self._mem_last[wa_id] = now
        # global per minute
        minute_bucket = int(now // 60)
        if self._r:
            kg = f"{self._key_global()}:{minute_bucket}"
            cnt = self._r.incr(kg)
            if cnt == 1:
                self._r.expire(kg, 60)
            if cnt > self.global_per_minute:
                return False
        else:
            cnt = self._mem_minute.get(minute_bucket, 0) + 1
            self._mem_minute[minute_bucket] = cnt
            # limpeza simples
            for bucket in list(self._mem_minute.keys()):
                if bucket < minute_bucket:
                    del self._mem_minute[bucket]
            if cnt > self.global_per_minute:
                return False
        return True
