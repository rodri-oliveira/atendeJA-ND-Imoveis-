"""
Serviço LLM para extração de intenção e entidades no chatbot imobiliário.
Usa Ollama (Llama local) com prompts estruturados para substituir regex/hardcode.
"""
from typing import Any, Dict, List, Optional
import json
import httpx
from app.core.config import settings


class LLMService:
    """Cliente para Ollama com prompts especializados para chatbot imobiliário."""
    
    def __init__(self):
        self.base_urls = self._get_candidate_urls()
        self.model = settings.OLLAMA_DEFAULT_MODEL
        self.timeout = 30
    
    def _get_candidate_urls(self) -> List[str]:
        """Retorna URLs candidatas para Ollama (config, docker, localhost)."""
        base = (settings.OLLAMA_BASE_URL or "").strip().rstrip("/")
        urls = []
        if base:
            urls.append(base)
        urls.append("http://host.docker.internal:11434")
        urls.append("http://localhost:11434")
        # Remove duplicatas mantendo ordem
        seen = set()
        out: List[str] = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out
    
    async def _chat(self, messages: List[Dict[str, str]]) -> str:
        """Chama Ollama /api/chat e retorna o conteúdo da resposta."""
        payload = {"model": self.model, "messages": messages, "stream": False}
        async with httpx.AsyncClient() as client:
            last_err: Optional[Exception] = None
            for url in self.base_urls:
                try:
                    r = await client.post(f"{url}/api/chat", json=payload, timeout=self.timeout)
                    r.raise_for_status()
                    js = r.json()
                    return js.get("message", {}).get("content", "")
                except Exception as e:
                    last_err = e
                    continue
            raise Exception(f"LLM unavailable: {last_err}")

    def _chat_sync(self, messages: List[Dict[str, str]]) -> str:
        """Versão síncrona de chat: usa httpx.Client."""
        payload = {"model": self.model, "messages": messages, "stream": False}
        last_err: Optional[Exception] = None
        with httpx.Client() as client:
            for url in self.base_urls:
                try:
                    r = client.post(f"{url}/api/chat", json=payload, timeout=self.timeout)
                    r.raise_for_status()
                    js = r.json()
                    return js.get("message", {}).get("content", "")
                except Exception as e:
                    last_err = e
                    continue
        raise Exception(f"LLM unavailable: {last_err}")
    
    async def extract_intent_and_entities(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extrai intenção e entidades estruturadas do input do usuário.
        
        Returns:
            {
                "intent": "buscar_imovel" | "responder_lgpd" | "outro",
                "entities": {
                    "finalidade": "rent" | "sale" | null,
                    "tipo": "house" | "apartment" | "commercial" | "land" | null,
                    "cidade": str | null,
                    "estado": str | null,
                    "preco_min": float | null,
                    "preco_max": float | null,
                    "dormitorios": int | null,
                    "nome_usuario": str | null
                }
            }
        """
        system_prompt = """Você é um assistente especializado em imóveis. Sua tarefa é extrair informações estruturadas de mensagens de usuários.

Retorne APENAS um JSON válido no formato:
{
  "intent": "buscar_imovel" ou "responder_lgpd" ou "proximo_imovel" ou "ajustar_criterios" ou "outro",
  "entities": {
    "finalidade": "rent" (alugar/locação/aluguel) ou "sale" (comprar/venda/compra) ou null,
    "tipo": "house" (casa) ou "apartment" (apartamento/ap/apto) ou "commercial" (comercial) ou "land" (terreno) ou null,
    "cidade": nome da cidade ou null,
    "estado": sigla UF (2 letras) ou null,
    "preco_min": número ou null,
    "preco_max": número ou null,
    "dormitorios": número ou null,
    "nome_usuario": primeiro nome do usuário se ele se apresentar (ex: "me chamo João", "sou Maria", "meu nome é Pedro") ou null
  }
}

Regras:
- Se o usuário responder "sim", "autorizo", "aceito", "ok", "concordo" → intent: "responder_lgpd"
- Se mencionar "próximo", "outro", "mais", "outras opções", "próximo imóvel" → intent: "proximo_imovel"
- Se mencionar "ajustar", "mudar", "refazer", "nova busca", "outros critérios" → intent: "ajustar_criterios"
- Se mencionar busca de imóvel → intent: "buscar_imovel"
- Caso contrário → intent: "outro"

Normalização de finalidade:
- "locação", "alugar", "aluguel", "locar", "alugo" → "rent"
- "comprar", "venda", "compra", "vender", "compro" → "sale"

Normalização de tipo:
- "casa", "sobrado" → "house"
- "apartamento", "ap", "apto", "flat" → "apartment"
- "comercial", "loja", "sala comercial", "ponto comercial" → "commercial"
- "terreno", "lote", "área" → "land"

Conversão de valores por extenso:
- "cem mil", "100 mil", "100k" → 100000
- "duzentos mil", "200 mil", "200k" → 200000
- "quinhentos mil", "500 mil", "500k" → 500000
- "um milhão", "1 milhão", "1mi" → 1000000
- "dois mil", "2 mil", "2k" → 2000
- "três mil", "3 mil", "3k" → 3000

Exemplos:
Input: "quero alugar casa em Mogi das Cruzes 3 quartos até 2000"
Output: {"intent":"buscar_imovel","entities":{"finalidade":"rent","tipo":"house","cidade":"Mogi Das Cruzes","estado":null,"preco_min":null,"preco_max":2000,"dormitorios":3}}

Input: "sim"
Output: {"intent":"responder_lgpd","entities":{"finalidade":null,"tipo":null,"cidade":null,"estado":null,"preco_min":null,"preco_max":null,"dormitorios":null}}

Input: "próximo"
Output: {"intent":"proximo_imovel","entities":{"finalidade":null,"tipo":null,"cidade":null,"estado":null,"preco_min":null,"preco_max":null,"dormitorios":null}}

Input: "outras opções"
Output: {"intent":"proximo_imovel","entities":{"finalidade":null,"tipo":null,"cidade":null,"estado":null,"preco_min":null,"preco_max":null,"dormitorios":null}}

Input: "vamos ajustar os critérios"
Output: {"intent":"ajustar_criterios","entities":{"finalidade":null,"tipo":null,"cidade":null,"estado":null,"preco_min":null,"preco_max":null,"dormitorios":null}}

Input: "ap"
Output: {"intent":"buscar_imovel","entities":{"finalidade":null,"tipo":"apartment","cidade":null,"estado":null,"preco_min":null,"preco_max":null,"dormitorios":null}}

Input: "cem mil"
Output: {"intent":"buscar_imovel","entities":{"finalidade":null,"tipo":null,"cidade":null,"estado":null,"preco_min":null,"preco_max":100000,"dormitorios":null}}

Input: "locação"
Output: {"intent":"buscar_imovel","entities":{"finalidade":"rent","tipo":null,"cidade":null,"estado":null,"preco_min":null,"preco_max":null,"dormitorios":null,"nome_usuario":null}}

Input: "Olá, me chamo Georgia e tenho interesse nesse imóvel"
Output: {"intent":"buscar_imovel","entities":{"finalidade":null,"tipo":null,"cidade":null,"estado":null,"preco_min":null,"preco_max":null,"dormitorios":null,"nome_usuario":"Georgia"}}

Input: "Meu nome é Thiago, quero alugar casa"
Output: {"intent":"buscar_imovel","entities":{"finalidade":"rent","tipo":"house","cidade":null,"estado":null,"preco_min":null,"preco_max":null,"dormitorios":null,"nome_usuario":"Thiago"}}

Agora processe a mensagem do usuário e retorne APENAS o JSON."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
        
        response = await self._chat(messages)
        
        # Parse JSON da resposta
        try:
            # Remove markdown code blocks se presentes
            response_clean = response.strip()
            if response_clean.startswith("```"):
                lines = response_clean.split("\n")
                response_clean = "\n".join(lines[1:-1]) if len(lines) > 2 else response_clean
            
            result = json.loads(response_clean)
            return result
        except json.JSONDecodeError:
            # Fallback: retornar estrutura vazia
            return {
                "intent": "outro",
                "entities": {
                    "finalidade": None,
                    "tipo": None,
                    "cidade": None,
                    "estado": None,
                    "preco_min": None,
                    "preco_max": None,
                    "dormitorios": None,
                    "nome_usuario": None
                }
            }

    def extract_intent_and_entities_sync(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Versão síncrona para uso em contextos não-async (ex.: handlers sync)."""
        system_prompt = """Você é um assistente especializado em imóveis. Sua tarefa é extrair informações estruturadas de mensagens de usuários.

Retorne APENAS um JSON válido no formato:
{
  "intent": "buscar_imovel" ou "responder_lgpd" ou "proximo_imovel" ou "ajustar_criterios" ou "outro",
  "entities": {
    "finalidade": "rent" (alugar/locação/aluguel) ou "sale" (comprar/venda/compra) ou null,
    "tipo": "house" (casa) ou "apartment" (apartamento/ap/apto) ou "commercial" (comercial) ou "land" (terreno) ou null,
    "cidade": nome da cidade ou null,
    "estado": sigla UF (2 letras) ou null,
    "preco_min": número ou null,
    "preco_max": número ou null,
    "dormitorios": número ou null,
    "nome_usuario": primeiro nome do usuário se ele se apresentar (ex: "me chamo João", "sou Maria", "meu nome é Pedro") ou null
  }
}

Agora processe a mensagem do usuário e retorne APENAS o JSON."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]

        response = self._chat_sync(messages)

        try:
            response_clean = response.strip()
            if response_clean.startswith("```"):
                lines = response_clean.split("\n")
                response_clean = "\n".join(lines[1:-1]) if len(lines) > 2 else response_clean
            result = json.loads(response_clean)
            return result
        except json.JSONDecodeError:
            return {
                "intent": "outro",
                "entities": {
                    "finalidade": None,
                    "tipo": None,
                    "cidade": None,
                    "estado": None,
                    "preco_min": None,
                    "preco_max": None,
                    "dormitorios": None,
                    "nome_usuario": None
                }
            }


# Singleton global
_llm_service: Optional[LLMService] = None

def get_llm_service() -> LLMService:
    """Retorna instância singleton do LLMService."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
