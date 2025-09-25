from __future__ import annotations
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings

router = APIRouter()


def _candidate_urls() -> List[str]:
    base = (settings.OLLAMA_BASE_URL or "").strip().rstrip("/")
    urls = []
    if base:
        urls.append(base)
    urls.append("http://host.docker.internal:11434")
    urls.append("http://localhost:11434")
    # keep order, remove dups
    seen = set()
    out: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


async def _try_get(client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
    r = await client.get(url, timeout=5)
    r.raise_for_status()
    return r.json()


class GenerateIn(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    stream: Optional[bool] = False


@router.get("/ping")
async def llm_ping():
    attempts: List[Dict[str, Any]] = []
    async with httpx.AsyncClient() as client:
        for u in _candidate_urls():
            try:
                js = await _try_get(client, f"{u}/api/tags")
                attempts.append({"url": u, "status": 200, "models": [m.get("name") for m in js.get("models", [])]})
                return {"ok": True, "used_url": u, "attempts": attempts}
            except Exception as e:
                attempts.append({"url": u, "error": str(e)})
    return {"ok": False, "used_url": None, "attempts": attempts}


@router.post("/generate")
async def llm_generate(body: GenerateIn):
    model = body.model or settings.OLLAMA_DEFAULT_MODEL
    payload = {"model": model, "prompt": body.prompt, "stream": False, "options": {"temperature": body.temperature or 0.7}}
    async with httpx.AsyncClient() as client:
        last_err: Optional[Exception] = None
        for u in _candidate_urls():
            try:
                r = await client.post(f"{u}/api/generate", json=payload, timeout=60)
                r.raise_for_status()
                js = r.json()
                return {"model": model, "response": js.get("response"), "raw": js, "used_url": u}
            except Exception as e:
                last_err = e
                continue
    raise HTTPException(status_code=502, detail={"code": "llm_unavailable", "message": str(last_err) if last_err else "no_provider"})


@router.post("/chat")
async def llm_chat(body: ChatIn):
    model = body.model or settings.OLLAMA_DEFAULT_MODEL
    payload = {"model": model, "messages": [m.model_dump() for m in body.messages], "stream": False}
    async with httpx.AsyncClient() as client:
        last_err: Optional[Exception] = None
        for u in _candidate_urls():
            try:
                r = await client.post(f"{u}/api/chat", json=payload, timeout=60)
                r.raise_for_status()
                js = r.json()
                return {"used_url": u, **js}
            except Exception as e:
                last_err = e
                continue
    raise HTTPException(status_code=502, detail={"code": "llm_unavailable", "message": str(last_err) if last_err else "no_provider"})
