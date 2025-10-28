"""
Serviço LLM para extração de intenção e entidades no chatbot imobiliário.
Usa Ollama (Llama local) com prompts estruturados para substituir regex/hardcode.
"""
from typing import Any, Dict, List, Optional
import json
import httpx
from app.core.config import settings
import structlog

log = structlog.get_logger()


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
        """Faz chamada async para Ollama."""
        log.debug("llm_chat_start", model=self.model, message_count=len(messages))
        
        for i, url in enumerate(self.base_urls):
            try:
                log.debug("llm_trying_url", url=url, attempt=i+1, total_urls=len(self.base_urls))
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{url}/api/chat",
                        json={"model": self.model, "messages": messages, "stream": False}
                    )
                    response.raise_for_status()
                    result = response.json()["message"]["content"]
                    
                    log.info("llm_chat_success", 
                            url=url, 
                            response_length=len(result),
                            response_preview=result[:100] + "..." if len(result) > 100 else result)
                    return result
                    
            except Exception as e:
                log.warning("llm_url_failed", url=url, error=str(e), attempt=i+1)
                continue
                
        log.error("llm_all_urls_failed", urls=self.base_urls)
        raise Exception("Nenhuma URL do Ollama disponível")

    def _chat_sync(self, messages: List[Dict[str, str]]) -> str:
        """Faz chamada síncrona para Ollama."""
        log.debug("llm_chat_sync_start", model=self.model, message_count=len(messages))
        
        for i, url in enumerate(self.base_urls):
            try:
                log.debug("llm_sync_trying_url", url=url, attempt=i+1, total_urls=len(self.base_urls))
                
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        f"{url}/api/chat",
                        json={"model": self.model, "messages": messages, "stream": False}
                    )
                    response.raise_for_status()
                    result = response.json()["message"]["content"]
                    
                    log.info("llm_chat_sync_success", 
                            url=url, 
                            response_length=len(result),
                            response_preview=result[:100] + "..." if len(result) > 100 else result)
                    return result
                    
            except Exception as e:
                log.warning("llm_sync_url_failed", url=url, error=str(e), attempt=i+1)
                continue
                
        log.error("llm_sync_all_urls_failed", urls=self.base_urls)
        raise Exception("Nenhuma URL do Ollama disponível")

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
        log.info("llm_extract_start", user_input=user_input, input_length=len(user_input))
        
        system_prompt = """Você é um assistente especializado em imóveis. Sua tarefa é extrair informações estruturadas de mensagens de usuários.

REGRAS CRÍTICAS PARA EVITAR ALUCINAÇÕES:
1. Se o usuário disse apenas "sim", "não", "ok", "oi" ou palavras muito simples (≤3 caracteres), retorne TODAS as entidades como null
2. NUNCA invente informações que não estão EXPLICITAMENTE na mensagem do usuário
3. Se não tem CERTEZA ABSOLUTA sobre uma informação, use null
4. Não faça suposições ou inferências - seja literal
5. Use null (não "null" como string) para valores ausentes

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
    "nome_usuario": primeiro nome do usuário se ele se apresentar ou null
  }
}

EXEMPLOS CORRETOS:

Input: "quero alugar casa em São Paulo"
Output: {"intent":"buscar_imovel","entities":{"finalidade":"rent","tipo":"house","cidade":"São Paulo","estado":null,"preco_min":null,"preco_max":null,"dormitorios":null,"nome_usuario":null}}

Input: "apartamento para comprar até 500 mil"
Output: {"intent":"buscar_imovel","entities":{"finalidade":"sale","tipo":"apartment","cidade":null,"estado":null,"preco_min":null,"preco_max":500000,"dormitorios":null,"nome_usuario":null}}

Input: "casa para alugar em Mogi das Cruzes com 3 quartos até 2000"
Output: {"intent":"buscar_imovel","entities":{"finalidade":"rent","tipo":"house","cidade":"Mogi Das Cruzes","estado":null,"preco_min":null,"preco_max":2000,"dormitorios":3,"nome_usuario":null}}

Input: "sim"
Output: {"intent":"responder_lgpd","entities":{"finalidade":null,"tipo":null,"cidade":null,"estado":null,"preco_min":null,"preco_max":null,"dormitorios":null,"nome_usuario":null}}

Input: "próximo"
Output: {"intent":"proximo_imovel","entities":{"finalidade":null,"tipo":null,"cidade":null,"estado":null,"preco_min":null,"preco_max":null,"dormitorios":null,"nome_usuario":null}}

Input: "ok"
Output: {"intent":"responder_lgpd","entities":{"finalidade":null,"tipo":null,"cidade":null,"estado":null,"preco_min":null,"preco_max":null,"dormitorios":null,"nome_usuario":null}}

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
        
        # Parse e sanitiza JSON da resposta
        try:
            # Remove markdown code blocks se presentes
            response_clean = response.strip()
            if response_clean.startswith("```"):
                lines = response_clean.split("\n")
                response_clean = "\n".join(lines[1:-1]) if len(lines) > 2 else response_clean
                log.debug("llm_removed_markdown", original_length=len(response), cleaned_length=len(response_clean))
            
            result = json.loads(response_clean)
            log.info("llm_json_parse_success", result=result)
            
            # Sanitizar resultado para evitar alucinações
            sanitized_result = self._sanitize_result(result, user_input)
            
            if result != sanitized_result:
                log.warning("llm_result_sanitized", 
                           original=result, 
                           sanitized=sanitized_result,
                           user_input=user_input)
            
            return sanitized_result
            
        except json.JSONDecodeError as e:
            log.error("llm_json_parse_failed", 
                     error=str(e), 
                     response=response, 
                     response_clean=response_clean if 'response_clean' in locals() else None)
            
            # Fallback: retornar estrutura vazia
            fallback_result = {
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
            log.info("llm_using_fallback", fallback=fallback_result)
            return fallback_result

    def extract_intent_and_entities_sync(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Versão síncrona para uso em contextos não-async (ex.: handlers sync)."""
        log.info("llm_extract_sync_start", user_input=user_input, input_length=len(user_input), context=context)
        
        system_prompt = """Você é um assistente especializado em imóveis. Sua tarefa é extrair informações estruturadas de mensagens de usuários.

REGRAS CRÍTICAS PARA EVITAR ALUCINAÇÕES:
1. Se o usuário disse apenas "sim", "não", "ok", "oi" ou palavras muito simples (≤3 caracteres), retorne TODAS as entidades como null
2. NUNCA invente informações que não estão EXPLICITAMENTE na mensagem do usuário
3. Se não tem CERTEZA ABSOLUTA sobre uma informação, use null
4. Não faça suposições ou inferências - seja literal
5. Use null (não "null" como string) para valores ausentes

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

        log.info("llm_sync_sending_request", messages=messages, user_input=user_input)

        response = self._chat_sync(messages)
        
        log.info("llm_sync_raw_response", response=response, user_input=user_input, response_length=len(response))

        try:
            response_clean = response.strip()
            if response_clean.startswith("```"):
                lines = response_clean.split("\n")
                response_clean = "\n".join(lines[1:-1]) if len(lines) > 2 else response_clean
                log.debug("llm_sync_removed_markdown", original_length=len(response), cleaned_length=len(response_clean))
            
            log.info("llm_sync_parsing_json", response_clean=response_clean, user_input=user_input)
            
            result = json.loads(response_clean)
            log.info("llm_sync_json_parse_success", result=result, user_input=user_input)
            
            # Sanitizar resultado para evitar alucinações
            log.info("llm_sync_sanitizing_result", original_result=result, user_input=user_input)
            sanitized_result = self._sanitize_result(result, user_input)
            
            if result != sanitized_result:
                log.warning("llm_sync_result_sanitized", 
                           original=result, 
                           sanitized=sanitized_result,
                           user_input=user_input)
            else:
                log.info("llm_sync_no_sanitization_needed", result=result, user_input=user_input)
            
            log.info("llm_sync_final_result", final_result=sanitized_result, user_input=user_input)
            return sanitized_result
            
        except json.JSONDecodeError as e:
            log.error("llm_sync_json_parse_failed", 
                     error=str(e), 
                     response=response, 
                     response_clean=response_clean if 'response_clean' in locals() else None,
                     user_input=user_input)
            
            fallback_result = {
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
            log.info("llm_sync_using_fallback", fallback=fallback_result, user_input=user_input)
            return fallback_result

    def _sanitize_result(self, result: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        """Sanitiza resultado do LLM para evitar alucinações."""
        # Importar aqui para evitar dependência circular
        from app.domain.realestate.validation_utils import sanitize_llm_result
        return sanitize_llm_result(result, user_input)


# Singleton global
_llm_service: Optional[LLMService] = None

def get_llm_service() -> LLMService:
    """Retorna instância singleton do LLMService."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
