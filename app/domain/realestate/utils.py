from __future__ import annotations
from typing import Optional
from urllib.parse import urlparse


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
        if not pr.netloc or "." not in pr.netloc:
            return None
        return u
    except Exception:
        return None
