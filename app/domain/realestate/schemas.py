from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator
from datetime import datetime
from app.domain.realestate.models import PropertyType, PropertyPurpose


# ===== Imóvel =====
class ImovelCriar(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    tipo: PropertyType
    finalidade: PropertyPurpose
    preco: float = Field(gt=0)
    condominio: Optional[float] = Field(default=None, ge=0)
    iptu: Optional[float] = Field(default=None, ge=0)
    cidade: str
    estado: str
    bairro: Optional[str] = None
    endereco_json: Optional[dict] = None
    dormitorios: Optional[int] = Field(default=None, ge=0)
    banheiros: Optional[int] = Field(default=None, ge=0)
    suites: Optional[int] = Field(default=None, ge=0)
    vagas: Optional[int] = Field(default=None, ge=0)
    area_total: Optional[float] = Field(default=None, ge=0)
    area_util: Optional[float] = Field(default=None, ge=0)
    ano_construcao: Optional[int] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "titulo": "Apto 2 dorm SP - metrô",
                    "descricao": "Andar alto, 1 vaga, perto do metrô.",
                    "tipo": "apartment",
                    "finalidade": "rent",
                    "preco": 3000,
                    "condominio": 550,
                    "iptu": 120,
                    "cidade": "São Paulo",
                    "estado": "SP",
                    "bairro": "Centro",
                    "endereco_json": {"rua": "Rua Exemplo", "numero": "123", "cep": "01000-000"},
                    "dormitorios": 2,
                    "banheiros": 1,
                    "suites": 0,
                    "vagas": 1,
                    "area_total": 65,
                    "area_util": 60,
                    "ano_construcao": 2012,
                }
            ]
        }
    }

    @field_validator('titulo')
    @classmethod
    def _vl_titulo(cls, v: str) -> str:
        v2 = (v or '').strip()
        if not v2:
            raise ValueError('titulo_obrigatorio')
        return v2

    @field_validator('cidade')
    @classmethod
    def _vl_cidade(cls, v: str) -> str:
        v2 = (v or '').strip()
        if not v2:
            raise ValueError('cidade_obrigatoria')
        return v2

    @field_validator('estado')
    @classmethod
    def _vl_estado(cls, v: str) -> str:
        uf = (v or '').strip().upper()
        if len(uf) != 2:
            raise ValueError('estado_uf_invalido')
        return uf

    @field_validator('ano_construcao')
    @classmethod
    def _vl_ano(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        current = datetime.now().year + 1
        if not (1800 <= int(v) <= current):
            raise ValueError('ano_construcao_range')
        return int(v)


class ImovelSaida(BaseModel):
    id: int
    titulo: str
    tipo: PropertyType
    finalidade: PropertyPurpose
    preco: float
    cidade: str
    estado: str
    bairro: Optional[str] = None
    dormitorios: Optional[int] = None
    banheiros: Optional[int] = None
    suites: Optional[int] = None
    vagas: Optional[int] = None
    ativo: bool
    cover_image_url: Optional[str] = None

    class Config:
        from_attributes = True


class ImovelAtualizar(BaseModel):
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    preco: Optional[float] = Field(default=None, gt=0)
    condominio: Optional[float] = Field(default=None, ge=0)
    iptu: Optional[float] = Field(default=None, ge=0)
    cidade: Optional[str] = None
    estado: Optional[str] = None
    bairro: Optional[str] = None
    endereco_json: Optional[dict] = None
    dormitorios: Optional[int] = Field(default=None, ge=0)
    banheiros: Optional[int] = Field(default=None, ge=0)
    suites: Optional[int] = Field(default=None, ge=0)
    vagas: Optional[int] = Field(default=None, ge=0)
    area_total: Optional[float] = Field(default=None, ge=0)
    area_util: Optional[float] = Field(default=None, ge=0)
    ano_construcao: Optional[int] = None
    ativo: Optional[bool] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"preco": 3200, "ativo": True, "descricao": "Atualizado: com armários planejados."}
            ]
        }
    }


# ===== Imagem =====
class ImagemCriar(BaseModel):
    url: str
    is_capa: Optional[bool] = False
    ordem: Optional[int] = 0
    storage_key: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "url": "https://exemplo-cdn.com/imoveis/1/capa.jpg",
                    "is_capa": True,
                    "ordem": 0,
                    "storage_key": "imoveis/1/capa.jpg",
                }
            ]
        }
    }


class ImagemSaida(BaseModel):
    id: int
    url: str
    is_capa: bool
    ordem: int

    class Config:
        from_attributes = True


class ImovelDetalhes(BaseModel):
    id: int
    titulo: str
    descricao: Optional[str] = None
    tipo: PropertyType
    finalidade: PropertyPurpose
    preco: float
    cidade: str
    estado: str
    bairro: Optional[str] = None
    dormitorios: Optional[int] = None
    banheiros: Optional[int] = None
    suites: Optional[int] = None
    vagas: Optional[int] = None
    area_total: Optional[float] = None
    area_util: Optional[float] = None
    imagens: List[ImagemSaida] = []


# ===== Lead =====
class LeadCreate(BaseModel):
    nome: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None
    origem: Optional[str] = Field(default="whatsapp")
    preferencias: Optional[dict] = None
    consentimento_lgpd: bool = Field(default=False)
    # Direcionamento/integração
    property_interest_id: Optional[int] = None
    contact_id: Optional[int] = None
    # Filtros denormalizados (segmentação)
    finalidade: Optional[PropertyPurpose] = None
    tipo: Optional[PropertyType] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    bairro: Optional[str] = None
    dormitorios: Optional[int] = None
    preco_min: Optional[float] = None
    preco_max: Optional[float] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "nome": "Fulano",
                    "telefone": "+5511999990000",
                    "email": "fulano@exemplo.com",
                    "origem": "whatsapp",
                    "preferencias": {
                        "finalidade": "sale",
                        "cidade": "São Paulo",
                        "tipo": "apartment",
                        "dormitorios": 2,
                        "preco_max": 400000,
                    },
                    "consentimento_lgpd": True,
                }
            ]
        }
    }


class LeadOut(BaseModel):
    id: int
    nome: Optional[str]
    telefone: Optional[str]
    email: Optional[str]
    origem: Optional[str]
    preferencias: Optional[dict]
    consentimento_lgpd: Optional[bool] = None
    # Status e timestamps
    status: Optional[str] = None
    last_inbound_at: Optional[datetime] = None
    last_outbound_at: Optional[datetime] = None
    status_updated_at: Optional[datetime] = None
    # Direcionamento/integração
    property_interest_id: Optional[int] = None
    contact_id: Optional[int] = None
    # Filtros denormalizados (segmentação)
    finalidade: Optional[PropertyPurpose] = None
    tipo: Optional[PropertyType] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    bairro: Optional[str] = None
    dormitorios: Optional[int] = None
    preco_min: Optional[float] = None
    preco_max: Optional[float] = None

    class Config:
        from_attributes = True


class LeadStagingIn(BaseModel):
    external_lead_id: Optional[str] = None
    source: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    preferences: Optional[dict] = None
    updated_at_source: Optional[str] = None  # ISO-8601 string


class LeadStagingOut(BaseModel):
    created: bool
    updated: bool
    lead: LeadOut
