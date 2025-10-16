"""
Testes de detecção via LLM (requer Ollama rodando localmente).
"""
import pytest
from app.domain.realestate import detection_utils_llm as detect


def test_detect_consent():
    """Testa detecção de consentimento LGPD."""
    assert detect.detect_consent("sim") is True
    assert detect.detect_consent("autorizo") is True
    assert detect.detect_consent("não") is False


def test_detect_purpose():
    """Testa detecção de finalidade."""
    assert detect.detect_purpose("quero alugar") == "rent"
    assert detect.detect_purpose("locação") == "rent"
    assert detect.detect_purpose("quero comprar") == "sale"
    assert detect.detect_purpose("venda") == "sale"


def test_detect_property_type():
    """Testa detecção de tipo de imóvel."""
    assert detect.detect_property_type("casa") == "house"
    assert detect.detect_property_type("apartamento") == "apartment"
    assert detect.detect_property_type("comercial") == "commercial"


def test_extract_price():
    """Testa extração de preço."""
    price = detect.extract_price("até 2000")
    assert price is not None
    assert 1900 <= price <= 2100  # Margem para variação do LLM


def test_extract_bedrooms():
    """Testa extração de dormitórios."""
    assert detect.extract_bedrooms("2 quartos") == 2
    assert detect.extract_bedrooms("3 dormitórios") == 3
    assert detect.extract_bedrooms("tanto faz") is None


def test_is_greeting():
    """Testa detecção de saudação."""
    assert detect.is_greeting("olá") is True
    assert detect.is_greeting("bom dia") is True
    assert detect.is_greeting("quero alugar") is False
