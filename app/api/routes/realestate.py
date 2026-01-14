from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sqlalchemy import select, func, text
import structlog
import httpx
from app.domain.realestate.services.image_service import upload_property_images
from app.domain.realestate.services.property_service import (
    create_property as svc_create_property,
    list_properties as svc_list_properties,
    get_property as svc_get_property,
    update_property as svc_update_property,
    get_property_details as svc_get_property_details,
    soft_delete_property as svc_soft_delete_property,
    hard_delete_property as svc_hard_delete_property,
    _resolve_tenant_id as svc_resolve_tenant_id,
)
from app.domain.realestate.mappers import to_imovel_dict
from app.domain.realestate.utils import normalize_image_url
from app.domain.realestate.schemas import (
    ImovelCriar,
    ImovelSaida,
    ImovelAtualizar,
    ImagemCriar,
    ImagemSaida,
    ImovelDetalhes,
    LeadCreate,
    LeadOut,
    LeadStagingIn,
    LeadStagingOut,
)
from app.api.deps import get_db
from app.core.config import settings
from app.domain.realestate.models import (
    Property,
    PropertyPurpose,
    PropertyType,
    Lead,
    PropertyImage,
    LeadStatus,
)
from app.domain.realestate.services.chatbot_flow_service import ChatbotFlowService
from app.services.tenant_resolver import resolve_chatbot_domain_for_tenant
from pydantic import BaseModel
from app.api.deps import RequestContext, require_active_tenant_context

router = APIRouter()
log = structlog.get_logger()


# Schemas (simples para MVP)
# Schemas movidos para app/domain/realestate/schemas.py


 # --


 # --


 # --


@router.post(
    "/imoveis",
    response_model=ImovelSaida,
    summary="Cadastrar imóvel",
    description="Cria um novo imóvel com os atributos básicos (tipo, finalidade, preço e localização)",
)
def create_property(
    payload: ImovelCriar,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_active_tenant_context),
):
    if settings.RE_READ_ONLY:
        raise HTTPException(status_code=403, detail="read_only_mode")
    data = payload.model_dump()
    data["tenant_id"] = int(ctx.tenant_id)
    prop = svc_create_property(db, data)
    return ImovelSaida(**to_imovel_dict(prop))


@router.get(
    "/imoveis",
    response_model=List[ImovelSaida],
    summary="Listar imóveis",
    description="Lista imóveis com filtros comuns: finalidade (compra/locação), tipo, cidade/estado, faixa de preço e dormitórios.",
)
def list_properties(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_active_tenant_context),
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
    items, total = svc_list_properties(
        db,
        tenant_id=int(ctx.tenant_id),
        finalidade=finalidade,
        tipo=tipo,
        cidade=cidade,
        estado=estado,
        preco_min=preco_min,
        preco_max=preco_max,
        dormitorios_min=dormitorios_min,
        only_with_cover=only_with_cover,
        limit=limit,
        offset=offset,
    )
    try:
        log.info(
            "re_list_total",
            query=str(getattr(request.url, "query", "")),
            finalidade=(finalidade.value if finalidade else None),
            tipo=(tipo.value if tipo else None),
            cidade=cidade,
            estado=estado,
            only_with_cover=only_with_cover,
            limit=limit,
            offset=offset,
            total=int(total),
        )
    except Exception:
        pass
    response.headers["X-Total-Count"] = str(total)
    return [ImovelSaida(**it) for it in items]


@router.get(
    "/imoveis/type-counts",
    summary="Contagem de imóveis por tipo",
    description="Retorna contagem de imóveis ativos por tipo (apartment/house/land/commercial) para o tenant atual.",
)
def list_property_type_counts(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_active_tenant_context),
):
    rows = db.execute(
        text(
            """
            select type::text as tipo, count(1) as count
            from re_properties
            where tenant_id = :tenant_id and is_active = true
            group by 1
            order by 2 desc
            """
        ),
        {"tenant_id": int(ctx.tenant_id)},
    ).fetchall()
    return {"tenant_id": int(ctx.tenant_id), "type_counts": [dict(r._mapping) for r in rows]}


@router.post(
    "/imoveis/{property_id}/imagens/upload",
    response_model=List[ImagemSaida],
    summary="Upload de imagens para o imóvel (multipart)",
    description=(
        "Aceita múltiplos arquivos de imagem (jpeg/png/webp). "
        "Salva em disco local e associa ao imóvel como PropertyImage."
    ),
)
def upload_imagens(
    property_id: int,
    request: Request,
    files: List[UploadFile] = File(..., description="Arquivos de imagem"),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_active_tenant_context),
):
    """Upload local (MVP). Encaminha para o service e retorna DTOs de imagem."""
    if settings.RE_READ_ONLY:
        raise HTTPException(status_code=403, detail="read_only_mode")

    base_url = str(request.base_url).rstrip("/")
    try:
        # Ensure property belongs to tenant (service validates by tenant_id via header)
        _ = svc_get_property(db, property_id, tenant_id=int(ctx.tenant_id))
        created = upload_property_images(db, property_id, files, base_url)
        return [ImagemSaida(id=i["id"], url=i["url"], is_capa=bool(i["is_capa"]), ordem=int(i["ordem"])) for i in created]
    except ValueError as e:
        # Erros de regra do domínio traduzidos para HTTP 400
        raise HTTPException(status_code=400, detail={"code": "re_rule_error", "message": str(e)})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "upload_internal_error", "message": str(e)})

@router.delete(
    "/admin/re/imoveis/{property_id}",
    summary="Soft delete de imóvel",
)
def admin_soft_delete_property(
    property_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_active_tenant_context),
):
    if settings.RE_READ_ONLY:
        raise HTTPException(status_code=403, detail="read_only_mode")
    try:
        res = svc_soft_delete_property(db, property_id, tenant_id=int(ctx.tenant_id))
        return res
    except ValueError:
        raise HTTPException(status_code=404, detail="property_not_found")


@router.delete(
    "/admin/re/imoveis/{property_id}/hard",
    summary="Hard delete de imóvel",
)
def admin_hard_delete_property(
    property_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_active_tenant_context),
):
    if settings.RE_READ_ONLY:
        raise HTTPException(status_code=403, detail="read_only_mode")
    try:
        res = svc_hard_delete_property(db, property_id, tenant_id=int(ctx.tenant_id))
        return res
    except ValueError:
        raise HTTPException(status_code=404, detail="property_not_found")


class BulkDeleteIn(BaseModel):
    title_contains: Optional[str] = None
    description_contains: Optional[str] = None
    mode: str = "soft"


@router.post(
    "/admin/re/imoveis/bulk-delete",
    summary="Exclusão em lote por filtros",
)
def admin_bulk_delete_properties(
    payload: BulkDeleteIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_active_tenant_context),
):
    if settings.RE_READ_ONLY:
        raise HTTPException(status_code=403, detail="read_only_mode")
    term_title = (payload.title_contains or "").strip()
    term_desc = (payload.description_contains or "").strip()
    if not term_title and not term_desc:
        raise HTTPException(status_code=400, detail="missing_filters")
    q = db.query(Property).filter(Property.tenant_id == ctx.tenant_id)
    if term_title:
        q = q.filter(Property.title.ilike(f"%{term_title}%"))
    if term_desc:
        q = q.filter(Property.description.ilike(f"%{term_desc}%"))
    rows: List[Property] = q.all()
    count = 0
    for r in rows:
        try:
            if (payload.mode or "soft").lower() == "hard":
                svc_hard_delete_property(db, int(r.id), tenant_id=int(ctx.tenant_id))
            else:
                svc_soft_delete_property(db, int(r.id), tenant_id=int(ctx.tenant_id))
            count += 1
        except Exception:
            continue
    return {"ok": True, "matched": len(rows), "deleted": count, "mode": (payload.mode or "soft").lower()}

@router.get(
    "/imoveis/{property_id}",
    response_model=ImovelSaida,
    summary="Obter imóvel",
    description="Retorna um imóvel pelo seu ID.",
)
def get_property(
    property_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_active_tenant_context),
):
    try:
        prop = svc_get_property(db, property_id, tenant_id=int(ctx.tenant_id))
        return ImovelSaida(**to_imovel_dict(prop))
    except ValueError:
        raise HTTPException(status_code=404, detail="property_not_found")


@router.patch(
    "/imoveis/{property_id}",
    response_model=ImovelSaida,
    summary="Atualizar imóvel (parcial)",
    description="Atualiza parcialmente campos do imóvel, incluindo ativação/desativação.",
)
def update_property(
    property_id: int,
    payload: ImovelAtualizar,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_active_tenant_context),
):
    if settings.RE_READ_ONLY:
        raise HTTPException(status_code=403, detail="read_only_mode")
    try:
        prop = svc_update_property(db, property_id, payload.model_dump(exclude_unset=True), tenant_id=int(ctx.tenant_id))
        return ImovelSaida(**to_imovel_dict(prop))
    except ValueError:
        raise HTTPException(status_code=404, detail="property_not_found")


# Leads
 # --


@router.post(
    "/leads",
    response_model=LeadOut,
    summary="Cadastrar lead",
    description="Cria um lead com preferências de busca e consentimento LGPD.",
)
def create_lead(
    payload: LeadCreate,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_active_tenant_context),
):
    data = payload.model_dump(exclude_unset=True)
    lead = Lead(
        tenant_id=ctx.tenant_id,
        name=data.get("nome"),
        phone=data.get("telefone"),
        email=data.get("email"),
        source=data.get("origem"),
        preferences=data.get("preferencias"),
        consent_lgpd=data.get("consentimento_lgpd", False),
        # direcionado/integrações
        property_interest_id=data.get("property_interest_id"),
        contact_id=data.get("contact_id"),
        # filtros denormalizados
        finalidade=(data.get("finalidade").value if data.get("finalidade") is not None else None),
        tipo=(data.get("tipo").value if data.get("tipo") is not None else None),
        cidade=data.get("cidade"),
        estado=(data.get("estado").upper() if data.get("estado") else None),
        bairro=data.get("bairro"),
        dormitorios=data.get("dormitorios"),
        preco_min=data.get("preco_min"),
        preco_max=data.get("preco_max"),
        # campanha
        campaign_source=data.get("campaign_source"),
        campaign_medium=data.get("campaign_medium"),
        campaign_name=data.get("campaign_name"),
        campaign_content=data.get("campaign_content"),
        landing_url=data.get("landing_url"),
        external_property_id=data.get("external_property_id"),
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
        consentimento_lgpd=lead.consent_lgpd,
        status=lead.status,
        last_inbound_at=lead.last_inbound_at,
        last_outbound_at=lead.last_outbound_at,
        status_updated_at=lead.status_updated_at,
        property_interest_id=lead.property_interest_id,
        contact_id=lead.contact_id,
        finalidade=lead.finalidade,
        tipo=lead.tipo,
        cidade=lead.cidade,
        estado=lead.estado,
        bairro=lead.bairro,
        dormitorios=lead.dormitorios,
        preco_min=lead.preco_min,
        preco_max=lead.preco_max,
        campaign_source=lead.campaign_source,
        campaign_medium=lead.campaign_medium,
        campaign_name=lead.campaign_name,
        campaign_content=lead.campaign_content,
        landing_url=lead.landing_url,
        external_property_id=lead.external_property_id,
    )

@router.get(
    "/leads",
    response_model=List[LeadOut],
    summary="Listar leads",
    description="Lista leads com filtros básicos.",
)
def list_leads(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_active_tenant_context),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    finalidade: Optional[PropertyPurpose] = Query(None),
    tipo: Optional[PropertyType] = Query(None),
    cidade: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    bairro: Optional[str] = Query(None),
    dormitorios: Optional[int] = Query(None),
    preco_min: Optional[float] = Query(None),
    preco_max: Optional[float] = Query(None),
    direcionado: Optional[bool] = Query(None, description="Se True, apenas leads com property_interest_id"),
    campaign_source: Optional[str] = Query(None, description="Origem de campanha (ex.: facebook, chavesnamao)"),
):
    def _get_by_path(obj: object, path: str):
        raw = (path or '').strip()
        if not raw:
            return None
        cur: object = obj
        for part in raw.split('.'):
            if cur is None:
                return None
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                return None
        return cur

    def _extract_summary_value(*, preferences: dict, source: str):
        src = (source or '').strip()
        if not src:
            return None
        if src.startswith('preferences.'):
            return _get_by_path({'preferences': preferences or {}}, src)
        return _get_by_path(preferences or {}, src)

    domain = resolve_chatbot_domain_for_tenant(db, int(ctx.tenant_id))
    flow_svc = ChatbotFlowService(db)
    flow_row = flow_svc.get_published_flow(tenant_id=int(ctx.tenant_id), domain=domain)
    lead_summary_fields: list[dict] = []
    lead_kanban: dict | None = None
    if flow_row and isinstance(getattr(flow_row, 'flow_definition', None), dict):
        try:
            flow = flow_svc.validate_definition(flow_row.flow_definition)
            if getattr(flow, 'lead_summary', None) and getattr(flow.lead_summary, 'fields', None):
                lead_summary_fields = [f.model_dump() for f in flow.lead_summary.fields]
            if getattr(flow, 'lead_kanban', None) and getattr(flow.lead_kanban, 'stages', None):
                lead_kanban = {'stages': [s.model_dump() for s in flow.lead_kanban.stages]}
        except Exception:
            lead_summary_fields = []
            lead_kanban = None

    q = db.query(Lead).filter(Lead.tenant_id == int(ctx.tenant_id))
    if status:
        q = q.filter(Lead.status == status)
    if finalidade:
        q = q.filter(Lead.finalidade == finalidade.value)
    if tipo:
        q = q.filter(Lead.tipo == tipo.value)
    if cidade:
        c = (cidade or "").strip()
        if c:
            q = q.filter(Lead.cidade.ilike(f"%{c}%"))
    if estado:
        uf = (estado or "").strip().upper()
        if uf:
            q = q.filter(Lead.estado == uf)
    if bairro:
        b = (bairro or "").strip()
        if b:
            q = q.filter(Lead.bairro.ilike(f"%{b}%"))
    if dormitorios is not None:
        q = q.filter(Lead.dormitorios == dormitorios)
    if preco_min is not None:
        q = q.filter(Lead.preco_min >= preco_min)
    if preco_max is not None:
        q = q.filter(Lead.preco_max <= preco_max)
    if direcionado is True:
        q = q.filter(Lead.property_interest_id.isnot(None))
    if direcionado is False:
        q = q.filter(Lead.property_interest_id.is_(None))
    if campaign_source:
        q = q.filter(Lead.campaign_source == campaign_source)

    # Ordenar por atividade recente para refletir atualizações (ex.: agendamento) no topo da lista
    rows = q.order_by(Lead.last_inbound_at.desc(), Lead.id.desc()).limit(limit).offset(offset).all()
    return [
        LeadOut(
            id=r.id,
            nome=r.name,
            telefone=r.phone,
            email=r.email,
            origem=r.source,
            preferencias=r.preferences,
            consentimento_lgpd=r.consent_lgpd,
            status=r.status,
            last_inbound_at=r.last_inbound_at,
            last_outbound_at=r.last_outbound_at,
            status_updated_at=r.status_updated_at,
            property_interest_id=r.property_interest_id,
            contact_id=r.contact_id,
            external_property_id=r.external_property_id,
            finalidade=r.finalidade,
            tipo=r.tipo,
            cidade=r.cidade,
            estado=r.estado,
            bairro=r.bairro,
            dormitorios=r.dormitorios,
            preco_min=r.preco_min,
            preco_max=r.preco_max,
            campaign_source=r.campaign_source,
            campaign_medium=r.campaign_medium,
            campaign_name=r.campaign_name,
            campaign_content=r.campaign_content,
            landing_url=r.landing_url,
            lead_kanban=lead_kanban,
            lead_summary=(
                [
                    {
                        'key': f.get('key'),
                        'label': f.get('label'),
                        'value': (
                            _extract_summary_value(preferences=(r.preferences or {}), source=str(f.get('source') or ''))
                            if _extract_summary_value(preferences=(r.preferences or {}), source=str(f.get('source') or '')) not in (None, '', [])
                            else (f.get('empty_value') if f.get('empty_value') is not None else _extract_summary_value(preferences=(r.preferences or {}), source=str(f.get('source') or '')))
                        ),
                    }
                    for f in (lead_summary_fields or [])
                ]
                if lead_summary_fields
                else None
            ),
        )
        for r in rows
    ]

class LeadStatusUpdate(BaseModel):
    status: LeadStatus


class LeadConfigOut(BaseModel):
    domain: str
    has_published_flow: bool
    lead_summary_fields: list[dict]
    lead_kanban: dict | None = None


@router.get("/leads/config", response_model=LeadConfigOut, summary="Config de Leads (Flow/Kanban)")
def get_leads_config(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_active_tenant_context),
):
    domain = resolve_chatbot_domain_for_tenant(db, int(ctx.tenant_id))
    flow_svc = ChatbotFlowService(db)
    flow_row = flow_svc.get_published_flow(tenant_id=int(ctx.tenant_id), domain=domain)

    lead_summary_fields: list[dict] = []
    lead_kanban: dict | None = None

    if flow_row and isinstance(getattr(flow_row, 'flow_definition', None), dict):
        try:
            flow = flow_svc.validate_definition(flow_row.flow_definition)
            if getattr(flow, 'lead_summary', None) and getattr(flow.lead_summary, 'fields', None):
                lead_summary_fields = [f.model_dump() for f in flow.lead_summary.fields]
            if getattr(flow, 'lead_kanban', None) and getattr(flow.lead_kanban, 'stages', None):
                lead_kanban = {'stages': [s.model_dump() for s in flow.lead_kanban.stages]}
        except Exception:
            lead_summary_fields = []
            lead_kanban = None

    return LeadConfigOut(
        domain=domain,
        has_published_flow=bool(flow_row),
        lead_summary_fields=lead_summary_fields,
        lead_kanban=lead_kanban,
    )

@router.patch("/leads/{lead_id}/status", response_model=LeadOut, summary="Atualizar status do lead")
def update_lead_status(
    lead_id: int,
    payload: LeadStatusUpdate,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_active_tenant_context),
):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == ctx.tenant_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="lead_not_found")

    try:
        lead.change_status(payload.status)
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": str(e)})

# --- Staging de Leads (MVP sem tabela dedicada) ---
 # --


@router.post(
    "/leads/staging",
    response_model=LeadStagingOut,
    summary="Staging/Upsert de leads a partir de integrações (MVP)",
    description=(
        "Upsert de Lead utilizando phone/email como chaves principais.\n"
        "Armazena external_lead_id e updated_at_source dentro de preferences para rastreabilidade."
    ),
)
def upsert_lead_from_staging(
    payload: LeadStagingIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_active_tenant_context),
):
    data = payload.model_dump(exclude_unset=True)

    # Estratégia de deduplicação (MVP): phone > email
    lead: Lead | None = None
    if data.get("phone"):
        lead = (
            db.query(Lead)
            .filter(Lead.tenant_id == ctx.tenant_id, Lead.phone == data["phone"])  # type: ignore
            .first()
        )
    if not lead and data.get("email"):
        lead = (
            db.query(Lead)
            .filter(Lead.tenant_id == ctx.tenant_id, Lead.email == data["email"])  # type: ignore
            .first()
        )

    created = False
    updated = False

    if not lead:
        # cria
        lead = Lead(
            tenant_id=ctx.tenant_id,
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
            consentimento_lgpd=lead.consent_lgpd,
        ),
    )


# --- Imagens do imóvel --- (definitions moved above)


@router.post(
    "/imoveis/{property_id}/imagens",
    response_model=ImagemSaida,
    summary="Adicionar imagem ao imóvel",
)
def add_imagem(
    property_id: int,
    payload: ImagemCriar,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_active_tenant_context),
):
    prop = svc_get_property(db, property_id, tenant_id=int(ctx.tenant_id))
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
def list_imagens(
    property_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_active_tenant_context),
):
    prop = svc_get_property(db, property_id, tenant_id=int(ctx.tenant_id))
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
        nurl = normalize_image_url(r.url)
        if not nurl:
            continue
        out.append(ImagemSaida(id=r.id, url=nurl, is_capa=r.is_cover, ordem=r.sort_order))
    return out


 # [REMOVIDO] Duplicidade do endpoint de proxy de imagens.
 # Mantida apenas a versão assíncrona definida mais abaixo em "/images/proxy".

@router.get(
    "/imoveis/{property_id}/detalhes",
    response_model=ImovelDetalhes,
    summary="Detalhes do imóvel (com imagens)",
)
def get_imovel_detalhes(
    property_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(require_active_tenant_context),
):
    try:
        d = svc_get_property_details(db, property_id, tenant_id=int(ctx.tenant_id))
        d_out = ImovelDetalhes(
            id=d["id"],
            titulo=d["titulo"],
            descricao=d.get("descricao"),
            tipo=d["tipo"],
            finalidade=d["finalidade"],
            preco=d["preco"],
            cidade=d["cidade"],
            estado=d["estado"],
            bairro=d.get("bairro"),
            dormitorios=d.get("dormitorios"),
            banheiros=d.get("banheiros"),
            suites=d.get("suites"),
            vagas=d.get("vagas"),
            area_total=d.get("area_total"),
            area_util=d.get("area_util"),
            imagens=[ImagemSaida(**img) for img in d.get("imagens", [])],
        )
        return d_out
    except ValueError:
        raise HTTPException(status_code=404, detail="property_not_found")



@router.get("/images/proxy")
async def proxy_image(url: str = Query(..., description="URL da imagem para fazer proxy")):
    """
    Proxy de imagens para contornar CORS.
    Aceita uma URL de imagem e retorna o conteúdo com headers apropriados.
    """
    # Log estruturado da requisição de proxy
    log.info("img_proxy_enter", url=url)
    if not url:
        raise HTTPException(status_code=400, detail={"code": "url_required", "message": "URL é obrigatória"})
    
    # Validar URL
    normalized = normalize_image_url(url)
    if not normalized:
        raise HTTPException(status_code=400, detail={"code": "invalid_url", "message": "URL inválida"})
    # Allowlist de hosts para mitigar SSRF
    try:
        from urllib.parse import urlparse
        host = urlparse(normalized).hostname or ""
        allowed = {"cdn-imobibrasil.com.br", "imgs2.cdn-imobibrasil.com.br", "imgs.cdn-imobibrasil.com.br"}
        def is_allowed(h: str) -> bool:
            return any(h == a or h.endswith("." + a) for a in allowed)
        if not is_allowed(host):
            log.warning("img_proxy_blocked_host", host=host)
            raise HTTPException(status_code=403, detail="host_not_allowed")
    except HTTPException:
        raise
    except Exception as _e:
        log.warning("img_proxy_host_parse_error", error=str(_e))
        raise HTTPException(status_code=400, detail="invalid_url")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.ndimoveis.com.br/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    try:
        # Tentativa padrão (verify=True)
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(normalized, headers=headers)
    except httpx.HTTPError as e:
        # Retry tolerante a SSL em ambientes dev/Windows
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False) as client2:
                response = await client2.get(normalized, headers=headers)
                log.warning("img_proxy_retry_verify_false", reason=repr(e))
        except httpx.HTTPError as e2:
            log.warning("img_proxy_http_error", error=repr(e2))
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "image_fetch_error",
                    "message": "Erro ao buscar imagem.",
                    "details": {"error": e2.__class__.__name__},
                },
            )

    if response.status_code != 200:
        log.warning("img_proxy_upstream_non_200", status=response.status_code)
        raise HTTPException(
            status_code=response.status_code,
            detail={
                "code": "image_upstream_error",
                "message": "Erro ao buscar imagem.",
                "details": {"status_code": int(response.status_code)},
            },
        )

    # Determinar content-type
    content_type = response.headers.get("content-type", "image/jpeg")

    return Response(
        content=response.content,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",  # 24 horas
            "Access-Control-Allow-Origin": "*",
        },
    )
