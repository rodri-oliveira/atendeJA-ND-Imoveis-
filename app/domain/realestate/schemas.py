from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, AliasChoices
from pydantic.functional_validators import field_validator
from datetime import datetime
from app.domain.realestate.models import PropertyType, PropertyPurpose


# ===== Imóvel =====
class ImovelCriar(BaseModel):
    titulo: str = Field(validation_alias=AliasChoices("titulo", "title"))
    descricao: Optional[str] = Field(default=None, validation_alias=AliasChoices("descricao", "description"))
    tipo: PropertyType = Field(validation_alias=AliasChoices("tipo", "type"))
    finalidade: PropertyPurpose = Field(validation_alias=AliasChoices("finalidade", "purpose"))
    preco: float = Field(gt=0, validation_alias=AliasChoices("preco", "price"))
    condominio: Optional[float] = Field(default=None, ge=0, validation_alias=AliasChoices("condominio", "condominium"))
    iptu: Optional[float] = Field(default=None, ge=0)
    cidade: str = Field(validation_alias=AliasChoices("cidade", "city"))
    estado: str = Field(validation_alias=AliasChoices("estado", "state"))
    bairro: Optional[str] = Field(default=None, validation_alias=AliasChoices("bairro", "neighborhood"))
    endereco_json: Optional[dict] = Field(default=None, validation_alias=AliasChoices("endereco_json", "address_json"))
    dormitorios: Optional[int] = Field(default=None, ge=0, validation_alias=AliasChoices("dormitorios", "bedrooms"))
    banheiros: Optional[int] = Field(default=None, ge=0, validation_alias=AliasChoices("banheiros", "bathrooms"))
    suites: Optional[int] = Field(default=None, ge=0)
    vagas: Optional[int] = Field(default=None, ge=0, validation_alias=AliasChoices("vagas", "parking_spots"))
    area_total: Optional[float] = Field(default=None, ge=0, validation_alias=AliasChoices("area_total", "area_total"))
    area_util: Optional[float] = Field(default=None, ge=0, validation_alias=AliasChoices("area_util", "area_usable"))
    ano_construcao: Optional[int] = Field(default=None, validation_alias=AliasChoices("ano_construcao", "year_built"))

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
    ref_code: Optional[str] = None
    external_id: Optional[str] = None
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
    cover_image_url: Optional[str] = Field(default=None, serialization_alias="url_capa")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ImovelAtualizar(BaseModel):
    titulo: Optional[str] = Field(default=None, validation_alias=AliasChoices("titulo", "title"))
    descricao: Optional[str] = Field(default=None, validation_alias=AliasChoices("descricao", "description"))
    preco: Optional[float] = Field(default=None, gt=0, validation_alias=AliasChoices("preco", "price"))
    condominio: Optional[float] = Field(default=None, ge=0, validation_alias=AliasChoices("condominio", "condominium"))
    iptu: Optional[float] = Field(default=None, ge=0)
    cidade: Optional[str] = Field(default=None, validation_alias=AliasChoices("cidade", "city"))
    estado: Optional[str] = Field(default=None, validation_alias=AliasChoices("estado", "state"))
    bairro: Optional[str] = Field(default=None, validation_alias=AliasChoices("bairro", "neighborhood"))
    endereco_json: Optional[dict] = Field(default=None, validation_alias=AliasChoices("endereco_json", "address_json"))
    dormitorios: Optional[int] = Field(default=None, ge=0, validation_alias=AliasChoices("dormitorios", "bedrooms"))
    banheiros: Optional[int] = Field(default=None, ge=0, validation_alias=AliasChoices("banheiros", "bathrooms"))
    suites: Optional[int] = Field(default=None, ge=0)
    vagas: Optional[int] = Field(default=None, ge=0, validation_alias=AliasChoices("vagas", "parking_spots"))
    area_total: Optional[float] = Field(default=None, ge=0, validation_alias=AliasChoices("area_total", "area_total"))
    area_util: Optional[float] = Field(default=None, ge=0, validation_alias=AliasChoices("area_util", "area_usable"))
    ano_construcao: Optional[int] = Field(default=None, validation_alias=AliasChoices("ano_construcao", "year_built"))
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
    is_capa: Optional[bool] = Field(default=False, validation_alias=AliasChoices("is_capa", "is_cover"))
    ordem: Optional[int] = Field(default=0, validation_alias=AliasChoices("ordem", "sort_order"))
    storage_key: Optional[str] = Field(default=None, validation_alias=AliasChoices("storage_key", "storageKey"))

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "url": "https://exemplo-cdn.com/imoveis/1/capa.jpg",
                    "is_capa": True,
                    "ordem": 0,
                    "storage_key": "imoveis/1/capa.jpg",
                }
            ]
        },
    )


class ImagemSaida(BaseModel):
    id: int
    url: str
    is_capa: bool
    ordem: int

    model_config = ConfigDict(from_attributes=True)


class ImovelDetalhes(BaseModel):
    id: int
    ref_code: Optional[str] = None
    external_id: Optional[str] = None
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
    # Campanha (opcional)
    campaign_source: Optional[str] = None
    campaign_medium: Optional[str] = None
    campaign_name: Optional[str] = None
    campaign_content: Optional[str] = None
    landing_url: Optional[str] = None
    external_property_id: Optional[str] = None

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
    nome: Optional[str] = Field(default=None, validation_alias=AliasChoices("nome", "name"))
    telefone: Optional[str] = Field(default=None, validation_alias=AliasChoices("telefone", "phone"))
    email: Optional[str] = None
    origem: Optional[str] = Field(default=None, validation_alias=AliasChoices("origem", "source"))
    preferencias: Optional[dict] = Field(default=None, validation_alias=AliasChoices("preferencias", "preferences"))
    consentimento_lgpd: Optional[bool] = Field(default=None, validation_alias=AliasChoices("consentimento_lgpd", "consent_lgpd"))
    # Status e timestamps
    status: Optional[str] = None
    last_inbound_at: Optional[datetime] = None
    last_outbound_at: Optional[datetime] = None
    status_updated_at: Optional[datetime] = None

    # Resumo dinâmico baseado no Flow (schema-driven)
    lead_summary: Optional[list[dict]] = None

    # Config do Kanban por etapa (Flow), repetida por compatibilidade no payload
    lead_kanban: Optional[dict] = None

    @field_validator('last_inbound_at', 'last_outbound_at', 'status_updated_at', mode='before')
    @classmethod
    def _ensure_utc_timezone(cls, v):
        """Garante que datetime seja serializado com timezone UTC (sufixo Z)"""
        if v and isinstance(v, datetime):
            # Se não tem timezone, assume UTC
            if v.tzinfo is None:
                from datetime import timezone
                return v.replace(tzinfo=timezone.utc)
        return v

    # Direcionamento/integração
    property_interest_id: Optional[int] = None
    contact_id: Optional[int] = None
    external_property_id: Optional[str] = None
    # Filtros denormalizados (segmentação)
    finalidade: Optional[PropertyPurpose] = None
    tipo: Optional[PropertyType] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    bairro: Optional[str] = None
    dormitorios: Optional[int] = None
    preco_min: Optional[float] = None
    preco_max: Optional[float] = None
    # Campanha (atribuição)
    campaign_source: Optional[str] = None
    campaign_medium: Optional[str] = None
    campaign_name: Optional[str] = None
    campaign_content: Optional[str] = None
    landing_url: Optional[str] = None
    external_property_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class LeadStagingIn(BaseModel):
    external_lead_id: Optional[str] = Field(default=None, validation_alias=AliasChoices("external_lead_id", "id_lead_externo"))
    source: Optional[str] = Field(default=None, validation_alias=AliasChoices("source", "origem"))
    name: Optional[str] = Field(default=None, validation_alias=AliasChoices("name", "nome"))
    phone: Optional[str] = Field(default=None, validation_alias=AliasChoices("phone", "telefone"))
    email: Optional[str] = None
    preferences: Optional[dict] = Field(default=None, validation_alias=AliasChoices("preferences", "preferencias"))
    updated_at_source: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("updated_at_source", "atualizado_em_origem"),
    )  # ISO-8601 string


class LeadStagingOut(BaseModel):
    created: bool
    updated: bool
    lead: LeadOut
