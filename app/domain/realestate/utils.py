from __future__ import annotations
from typing import Optional
from urllib.parse import urlparse
import re


def normalize_image_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        u = str(url).strip()
        if not u:
            return None
        if u.startswith("//"):
            u = "https:" + u
        if not (u.startswith("http://") or u.startswith("https://")):
            return None
        pr = urlparse(u)
        if not pr.netloc:
            return None
        host = pr.hostname or ""
        # aceita localhost
        if host == "localhost":
            return u
        # aceita IPv4/IPv6
        if re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", host) or host == "::1":
            return u
        # aceita domínios com ponto
        if "." in host:
            return u
        return None
    except Exception:
        return None
