from typing import Optional

def _normalize_image_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        u = str(url).strip()
        if not u:
            return None
        # esquema ausente, mas começa com //host/path
        if u.startswith("//"):
            u = "https:" + u
        # somente aceita http/https
        if not (u.startswith("http://") or u.startswith("https://")):
            return None
        # valida host simples (deve conter ponto)
        from urllib.parse import urlparse
        pr = urlparse(u)
        if not pr.netloc or "." not in pr.netloc:
            return None
        return u
    except Exception:
        return None

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, exists
import httpx
from app.repositories.db import SessionLocal
from app.core.config import settings
from app.domain.realestate.models import (
    Property,
    PropertyPurpose,
    PropertyType,
    Lead,
    PropertyImage,
)

router = APIRouter()


# Dependency: DB session por request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Schemas (simples para MVP)
class ImovelCriar(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    tipo: PropertyType
    finalidade: PropertyPurpose
    preco: float
    condominio: Optional[float] = None
    iptu: Optional[float] = None
    cidade: str
    estado: str
    bairro: Optional[str] = None
    endereco_json: Optional[dict] = None
    dormitorios: Optional[int] = None
    banheiros: Optional[int] = None
    suites: Optional[int] = None
    vagas: Optional[int] = None
    area_total: Optional[float] = None
    area_util: Optional[float] = None
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
                    "ano_construcao": 2012
                }
            ]
        }
    }


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
    preco: Optional[float] = None
    condominio: Optional[float] = None
    iptu: Optional[float] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    bairro: Optional[str] = None
    endereco_json: Optional[dict] = None
    dormitorios: Optional[int] = None
    banheiros: Optional[int] = None
    suites: Optional[int] = None
    vagas: Optional[int] = None
    area_total: Optional[float] = None
    area_util: Optional[float] = None
    ano_construcao: Optional[int] = None
    ativo: Optional[bool] = None
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {"preco": 3200, "ativo": True, "descricao": "Atualizado: com armários planejados."}
            ]
        }
    }


@router.post(
    "/imoveis",
    response_model=ImovelSaida,
    summary="Cadastrar imóvel",
    description="Cria um novo imóvel com os atributos básicos (tipo, finalidade, preço e localização)",
)
def create_property(payload: ImovelCriar, db: Session = Depends(get_db)):
    if settings.RE_READ_ONLY:
        raise HTTPException(status_code=403, detail="read_only_mode")
    tenant_id = int(1) if settings.DEFAULT_TENANT_ID == "default" else 1
    prop = Property(
        tenant_id=tenant_id,
        title=payload.titulo,
        description=payload.descricao,
        type=payload.tipo,
        purpose=payload.finalidade,
        price=payload.preco,
        condo_fee=payload.condominio,
        iptu=payload.iptu,
        address_city=payload.cidade,
        address_state=payload.estado,
        address_neighborhood=payload.bairro,
        address_json=payload.endereco_json,
        bedrooms=payload.dormitorios,
        bathrooms=payload.banheiros,
        suites=payload.suites,
        parking_spots=payload.vagas,
        area_total=payload.area_total,
        area_usable=payload.area_util,
        year_built=payload.ano_construcao,
        is_active=True,
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return _to_imovel_saida(prop)


@router.get(
    "/imoveis",
    response_model=List[ImovelSaida],
    summary="Listar imóveis",
    description="Lista imóveis com filtros comuns: finalidade (compra/locação), tipo, cidade/estado, faixa de preço e dormitórios.",
)
def list_properties(
    db: Session = Depends(get_db),
    finalidade: Optional[PropertyPurpose] = Query(None),
    tipo: Optional[PropertyType] = Query(None),
    cidade: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    preco_min: Optional[float] = Query(None),
    preco_max: Optional[float] = Query(None),
    dormitorios_min: Optional[int] = Query(None),
    only_with_cover: bool = Query(False, description="Retorna apenas imóveis que possuam ao menos 1 imagem"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    stmt = select(Property).where(Property.is_active == True)  # noqa: E712
    if finalidade:
        stmt = stmt.where(Property.purpose == finalidade)
    if tipo:
        stmt = stmt.where(Property.type == tipo)
    if cidade:
        c = (cidade or "").strip()
        if c:
            stmt = stmt.where(Property.address_city.ilike(f"%{c}%"))
    if estado:
        uf = (estado or "").strip().upper()
        if uf:
            stmt = stmt.where(Property.address_state == uf)
    if preco_min is not None:
        stmt = stmt.where(Property.price >= preco_min)
    if preco_max is not None:
        stmt = stmt.where(Property.price <= preco_max)
    if dormitorios_min is not None:
        stmt = stmt.where(Property.bedrooms >= dormitorios_min)
    # Filtrar apenas imóveis que possuam imagens quando solicitado
    if only_with_cover:
        # Abordagem robusta: inner join + distinct evita armadilhas de correlação
        from sqlalchemy import distinct
        stmt = (
            stmt.join(PropertyImage, PropertyImage.property_id == Property.id)
                .distinct()
        )
    # Ordenação por mais recentes primeiro (melhor UX)
    try:
        stmt = stmt.order_by(Property.updated_at.desc(), Property.id.desc())
    except Exception:
        # Fallback caso o campo não exista em algum ambiente
        stmt = stmt.order_by(Property.id.desc())

    stmt = stmt.limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()
    # N+1 simples para obter a imagem de capa (MVP)
    out: list[ImovelSaida] = []
    for r in rows:
        cover_url: Optional[str] = None
        try:
            img_stmt = (
                select(PropertyImage)
                .where(PropertyImage.property_id == r.id)
                .order_by(PropertyImage.is_cover.desc(), PropertyImage.sort_order.asc(), PropertyImage.id.asc())
                .limit(1)
            )
            img = db.execute(img_stmt).scalars().first()
            if img:
                cover_url = _normalize_image_url(img.url)
        except Exception:
            cover_url = None
        item = _to_imovel_saida(r)
        item.cover_image_url = cover_url
        out.append(item)
    return out


@router.get(
    "/imoveis/{property_id}",
    response_model=ImovelSaida,
    summary="Obter imóvel",
    description="Retorna um imóvel pelo seu ID.",
)
def get_property(property_id: int, db: Session = Depends(get_db)):
    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="property_not_found")
    return _to_imovel_saida(prop)


@router.patch(
    "/imoveis/{property_id}",
    response_model=ImovelSaida,
    summary="Atualizar imóvel (parcial)",
    description="Atualiza parcialmente campos do imóvel, incluindo ativação/desativação.",
)
def update_property(property_id: int, payload: ImovelAtualizar, db: Session = Depends(get_db)):
    if settings.RE_READ_ONLY:
        raise HTTPException(status_code=403, detail="read_only_mode")
    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="property_not_found")
    data = payload.model_dump(exclude_unset=True)
    mapping = {
        "titulo": "title",
        "descricao": "description",
        "preco": "price",
        "condominio": "condo_fee",
        "iptu": "iptu",
        "cidade": "address_city",
        "estado": "address_state",
        "bairro": "address_neighborhood",
        "endereco_json": "address_json",
        "dormitorios": "bedrooms",
        "banheiros": "bathrooms",
        "suites": "suites",
        "vagas": "parking_spots",
        "area_total": "area_total",
        "area_util": "area_usable",
        "ano_construcao": "year_built",
        "ativo": "is_active",
    }
    for k, v in data.items():
        setattr(prop, mapping.get(k, k), v)
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return _to_imovel_saida(prop)


# Leads
class LeadCreate(BaseModel):
    nome: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None
    origem: Optional[str] = Field(default="whatsapp")
    preferencias: Optional[dict] = None
    consentimento_lgpd: bool = Field(default=False)
    
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
                        "preco_max": 400000
                    },
                    "consentimento_lgpd": True
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

    class Config:
        from_attributes = True


@router.post(
    "/leads",
    response_model=LeadOut,
    summary="Cadastrar lead",
    description="Cria um lead com preferências de busca e consentimento LGPD.",
)
def create_lead(payload: LeadCreate, db: Session = Depends(get_db)):
    tenant_id = int(1) if settings.DEFAULT_TENANT_ID == "default" else 1
    data = payload.model_dump()
    lead = Lead(
        tenant_id=tenant_id,
        name=data.get("nome"),
        phone=data.get("telefone"),
        email=data.get("email"),
        source=data.get("origem"),
        preferences=data.get("preferencias"),
        consent_lgpd=data.get("consentimento_lgpd", False),
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return LeadOut(
        id=lead.id,
        nome=lead.name,
        telefone=lead.phone,
        email=lead.email,
        origem=lead.source,
        preferencias=lead.preferences,
    )

@router.get(
    "/leads",
    response_model=List[LeadOut],
    summary="Listar leads",
    description="Lista leads.",
)
def list_leads(db: Session = Depends(get_db)):
    rows = db.query(Lead).all()
    return [
        LeadOut(
            id=r.id,
            nome=r.name,
            telefone=r.phone,
            email=r.email,
            origem=r.source,
            preferencias=r.preferences,
        )
        for r in rows
    ]


# --- Staging de Leads (MVP sem tabela dedicada) ---
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


@router.post(
    "/leads/staging",
    response_model=LeadStagingOut,
    summary="Staging/Upsert de leads a partir de integra\u00E7\u00F5es (MVP)",
    description=(
        "Upsert de Lead utilizando phone/email como chaves principais.\n"
        "Armazena external_lead_id e updated_at_source dentro de preferences para rastreabilidade."
    ),
)
def upsert_lead_from_staging(payload: LeadStagingIn, db: Session = Depends(get_db)):
    tenant_id = int(1) if settings.DEFAULT_TENANT_ID == "default" else 1
    data = payload.model_dump(exclude_unset=True)

    # Estratégia de deduplicação (MVP): phone > email
    lead: Lead | None = None
    if data.get("phone"):
        lead = (
            db.query(Lead)
            .filter(Lead.tenant_id == tenant_id, Lead.phone == data["phone"])  # type: ignore
            .first()
        )
    if not lead and data.get("email"):
        lead = (
            db.query(Lead)
            .filter(Lead.tenant_id == tenant_id, Lead.email == data["email"])  # type: ignore
            .first()
        )

    created = False
    updated = False

    if not lead:
        # cria
        lead = Lead(
            tenant_id=tenant_id,
            name=data.get("name"),
            phone=data.get("phone"),
            email=data.get("email"),
            source=data.get("source"),
            preferences=data.get("preferences") or {},
            consent_lgpd=False,
        )
        # rastreabilidade da origem
        prefs = dict(lead.preferences or {})
        if data.get("external_lead_id"):
            prefs["external_lead_id"] = data["external_lead_id"]
        if data.get("updated_at_source"):
            prefs["updated_at_source"] = data["updated_at_source"]
        lead.preferences = prefs
        db.add(lead)
        db.commit()
        db.refresh(lead)
        created = True
    else:
        # update simples: atualiza campos se vierem preenchidos
        before = lead.preferences or {}
        lead.name = data.get("name") or lead.name
        lead.phone = data.get("phone") or lead.phone
        lead.email = data.get("email") or lead.email
        lead.source = data.get("source") or lead.source
        # merge de preferences
        prefs = dict(before)
        for k, v in (data.get("preferences") or {}).items():
            prefs[k] = v
        if data.get("external_lead_id"):
            prefs["external_lead_id"] = data["external_lead_id"]
        if data.get("updated_at_source"):
            # se houver timestamp anterior, sobrescreve; regra detalhada pode ser adicionada depois
            prefs["updated_at_source"] = data["updated_at_source"]
        lead.preferences = prefs
        db.add(lead)
        db.commit()
        db.refresh(lead)
        updated = True

    return LeadStagingOut(
        created=created,
        updated=updated,
        lead=LeadOut(
            id=lead.id,
            nome=lead.name,
            telefone=lead.phone,
            email=lead.email,
            origem=lead.source,
            preferencias=lead.preferences,
        ),
    )


# --- Imagens do imóvel ---
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
                    "storage_key": "imoveis/1/capa.jpg"
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


@router.post(
    "/imoveis/{property_id}/imagens",
    response_model=ImagemSaida,
    summary="Adicionar imagem ao imóvel",
)
def add_imagem(property_id: int, payload: ImagemCriar, db: Session = Depends(get_db)):
    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="property_not_found")
    img = PropertyImage(
        property_id=property_id,
        url=payload.url,
        storage_key=payload.storage_key,
        is_cover=bool(payload.is_capa),
        sort_order=int(payload.ordem or 0),
    )
    db.add(img)
    db.commit()
    db.refresh(img)
    return ImagemSaida(id=img.id, url=img.url, is_capa=img.is_cover, ordem=img.sort_order)


@router.get(
    "/imoveis/{property_id}/imagens",
    response_model=List[ImagemSaida],
    summary="Listar imagens do imóvel",
)
def list_imagens(property_id: int, db: Session = Depends(get_db)):
    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="property_not_found")
    stmt = (
        select(PropertyImage)
        .where(PropertyImage.property_id == property_id)
        .order_by(PropertyImage.is_cover.desc(), PropertyImage.sort_order.asc(), PropertyImage.id.asc())
    )
    rows = db.execute(stmt).scalars().all()
    out: list[ImagemSaida] = []
    for r in rows:
        nurl = _normalize_image_url(r.url)
        if not nurl:
            continue
        out.append(ImagemSaida(id=r.id, url=nurl, is_capa=r.is_cover, ordem=r.sort_order))
    return out


 # [REMOVIDO] Duplicidade do endpoint de proxy de imagens.
 # Mantida apenas a versão assíncrona definida mais abaixo em "/images/proxy".

# --- Detalhes do imóvel (consolidado) ---
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


@router.get(
    "/imoveis/{property_id}/detalhes",
    response_model=ImovelDetalhes,
    summary="Detalhes do imóvel (com imagens)",
)
def get_imovel_detalhes(property_id: int, db: Session = Depends(get_db)):
    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="property_not_found")
    stmt = (
        select(PropertyImage)
        .where(PropertyImage.property_id == property_id)
        .order_by(PropertyImage.is_cover.desc(), PropertyImage.sort_order.asc(), PropertyImage.id.asc())
    )
    imgs = db.execute(stmt).scalars().all()
    norm_imgs: list[ImagemSaida] = []
    for i in imgs:
        nurl = _normalize_image_url(i.url)
        if not nurl:
            continue
        norm_imgs.append(ImagemSaida(id=i.id, url=nurl, is_capa=i.is_cover, ordem=i.sort_order))
    return ImovelDetalhes(
        id=prop.id,
        titulo=prop.title,
        descricao=prop.description,
        tipo=prop.type,
        finalidade=prop.purpose,
        preco=prop.price,
        cidade=prop.address_city,
        estado=prop.address_state,
        bairro=prop.address_neighborhood,
        dormitorios=prop.bedrooms,
        banheiros=prop.bathrooms,
        suites=prop.suites,
        vagas=prop.parking_spots,
        area_total=prop.area_total,
        area_util=prop.area_usable,
        imagens=norm_imgs,
    )


# --- helpers ---
def _to_imovel_saida(p: Property) -> ImovelSaida:
    return ImovelSaida(
        id=p.id,
        titulo=p.title,
        tipo=p.type,
        finalidade=p.purpose,
        preco=p.price,
        cidade=p.address_city,
        estado=p.address_state,
        bairro=p.address_neighborhood,
        dormitorios=p.bedrooms,
        banheiros=p.bathrooms,
        suites=p.suites,
        vagas=p.parking_spots,
        ativo=p.is_active,
    )


@router.get("/images/proxy")
async def proxy_image(url: str = Query(..., description="URL da imagem para fazer proxy")):
    """
    Proxy de imagens para contornar CORS.
    Aceita uma URL de imagem e retorna o conteúdo com headers apropriados.
    """
    print(f"[PROXY] Requisição para: {url}")
    if not url:
        raise HTTPException(status_code=400, detail="URL é obrigatória")
    
    # Validar URL
    normalized = _normalize_image_url(url)
    if not normalized:
        raise HTTPException(status_code=400, detail="URL inválida")
    
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(
                normalized,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.ndimoveis.com.br/",
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Erro ao buscar imagem: {response.status_code}"
                )
            
            # Determinar content-type
            content_type = response.headers.get("content-type", "image/jpeg")
            
            return Response(
                content=response.content,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",  # 24 horas
                    "Access-Control-Allow-Origin": "*",
                }
            )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Erro ao buscar imagem: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
