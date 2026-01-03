from __future__ import annotations
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.domain.realestate.models import Property, PropertyImage, PropertyPurpose, PropertyType
from app.domain.realestate.mappers import to_imovel_dict
from app.domain.realestate.utils import normalize_image_url
from app.services.image_storage import delete_file
from app.core.config import settings
from app.repositories.models import Tenant


def _resolve_tenant_id(db: Session) -> int:
    """Resolve o tenant ativo para operações de imóveis.

    - Em ambiente de teste, usa/garante um tenant chamado 'test' para isolar dados.
    - Caso DEFAULT_TENANT_ID seja um número, usa diretamente esse ID.
    - Caso contrário, procura/cria o tenant pelo nome informado em DEFAULT_TENANT_ID.
    """
    try:
        tenant_name = settings.DEFAULT_TENANT_ID
        if (settings.APP_ENV or "").lower() == "test":
            tenant_name = "test"
        # Se for numérico, usar diretamente
        try:
            return int(tenant_name)
        except Exception:
            pass
        # Resolver por nome
        t = db.query(Tenant).filter(Tenant.name == tenant_name).first()
        if not t:
            t = Tenant(name=tenant_name)
            db.add(t)
            db.flush()
        return int(t.id)
    except Exception:
        return 1


def create_property(db: Session, data: Dict[str, Any]) -> Property:
    tenant_id = int(data.get("tenant_id") or 0) if isinstance(data, dict) else 0
    if not tenant_id:
        tenant_id = _resolve_tenant_id(db)
    prop = Property(
        tenant_id=tenant_id,
        title=data["titulo"],
        description=data.get("descricao"),
        type=data["tipo"],
        purpose=data["finalidade"],
        price=data["preco"],
        condo_fee=data.get("condominio"),
        iptu=data.get("iptu"),
        address_city=data["cidade"],
        address_state=data["estado"],
        address_neighborhood=data.get("bairro"),
        address_json=data.get("endereco_json"),
        bedrooms=data.get("dormitorios"),
        bathrooms=data.get("banheiros"),
        suites=data.get("suites"),
        parking_spots=data.get("vagas"),
        area_total=data.get("area_total"),
        area_usable=data.get("area_util"),
        year_built=data.get("ano_construcao"),
        is_active=True,
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop


def list_properties(
    db: Session,
    tenant_id: int | None = None,
    finalidade: Optional[PropertyPurpose] = None,
    tipo: Optional[PropertyType] = None,
    cidade: Optional[str] = None,
    estado: Optional[str] = None,
    preco_min: Optional[float] = None,
    preco_max: Optional[float] = None,
    dormitorios_min: Optional[int] = None,
    only_with_cover: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    # Monta condições base (evita duplicação entre consulta e contagem)
    tenant_id = int(tenant_id) if tenant_id is not None else _resolve_tenant_id(db)
    conds = [
        Property.is_active == True,  # noqa: E712
        Property.tenant_id == tenant_id,
    ]
    if finalidade:
        conds.append(Property.purpose == finalidade)
    if tipo:
        conds.append(Property.type == tipo)
    if cidade:
        c = (cidade or "").strip()
        if c:
            # Filtro por cidade tolerante (substring), conforme plano
            conds.append(Property.address_city.ilike(f"%{c}%"))
    if estado:
        uf = (estado or "").strip().upper()
        if uf:
            conds.append(Property.address_state == uf)
    if preco_min is not None:
        conds.append(Property.price >= preco_min)
    if preco_max is not None:
        conds.append(Property.price <= preco_max)
    if dormitorios_min is not None:
        conds.append(Property.bedrooms >= dormitorios_min)

    # Consulta principal
    stmt = select(Property).where(*conds)
    if only_with_cover:
        # Garante que apenas imóveis com ao menos uma imagem entrem no resultado
        stmt = stmt.join(PropertyImage, PropertyImage.property_id == Property.id).distinct()

    try:
        stmt = stmt.order_by(Property.updated_at.desc(), Property.id.desc())
    except Exception:
        stmt = stmt.order_by(Property.id.desc())

    # Contagem robusta baseada na mesma consulta/joins do resultado (IDs distintos)
    ids_stmt = select(Property.id).where(*conds)
    if only_with_cover:
        ids_stmt = ids_stmt.join(PropertyImage, PropertyImage.property_id == Property.id).distinct()
    else:
        ids_stmt = ids_stmt.distinct()
    total = db.execute(select(func.count()).select_from(ids_stmt.subquery())).scalar_one()

    rows = db.execute(stmt.limit(limit).offset(offset)).scalars().all()

    out: List[Dict[str, Any]] = []
    for r in rows:
        cover_url: Optional[str] = None
        try:
            img_stmt = (
                select(PropertyImage)
                .where(PropertyImage.property_id == r.id)
                .order_by(
                    PropertyImage.is_cover.desc(),
                    PropertyImage.sort_order.asc(),
                    PropertyImage.id.asc(),
                )
                .limit(1)
            )
            img = db.execute(img_stmt).scalars().first()
            if img:
                cover_url = normalize_image_url(img.url)
        except Exception:
            cover_url = None
        out.append(to_imovel_dict(r, cover_url))

    try:
        import structlog
        log = structlog.get_logger()
        log.info(
            "re_list_service_total",
            tenant_id=int(tenant_id),
            only_with_cover=bool(only_with_cover),
            total=int(total),
        )
    except Exception:
        pass
    return out, int(total)


def get_property(db: Session, property_id: int, tenant_id: int | None = None) -> Property:
    tenant_id = int(tenant_id) if tenant_id is not None else _resolve_tenant_id(db)
    prop = db.get(Property, property_id)
    if not prop:
        raise ValueError("property_not_found")
    if int(getattr(prop, "tenant_id", 0) or 0) != int(tenant_id):
        raise ValueError("property_not_found")
    return prop


def update_property(db: Session, property_id: int, data: Dict[str, Any], tenant_id: int | None = None) -> Property:
    prop = get_property(db, property_id, tenant_id=tenant_id)
    if not prop:
        raise ValueError("property_not_found")

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
    return prop


def get_property_details(db: Session, property_id: int, tenant_id: int | None = None) -> Dict[str, Any]:
    prop = get_property(db, property_id, tenant_id=tenant_id)
    if not prop:
        raise ValueError("property_not_found")

    stmt = (
        select(PropertyImage)
        .where(PropertyImage.property_id == property_id)
        .order_by(PropertyImage.is_cover.desc(), PropertyImage.sort_order.asc(), PropertyImage.id.asc())
    )
    imgs = db.execute(stmt).scalars().all()
    norm_imgs: List[Dict[str, Any]] = []
    for i in imgs:
        nurl = normalize_image_url(i.url)
        if not nurl:
            continue
        norm_imgs.append({
            "id": i.id,
            "url": nurl,
            "is_capa": bool(i.is_cover),
            "ordem": int(i.sort_order),
        })
    return {
        "id": prop.id,
        "titulo": prop.title,
        "descricao": prop.description,
        "tipo": prop.type,
        "finalidade": prop.purpose,
        "preco": prop.price,
        "condominio": prop.condo_fee,
        "iptu": prop.iptu,
        "cidade": prop.address_city,
        "estado": prop.address_state,
        "bairro": prop.address_neighborhood,
        "dormitorios": prop.bedrooms,
        "banheiros": prop.bathrooms,
        "suites": prop.suites,
        "vagas": prop.parking_spots,
        "area_total": prop.area_total,
        "area_util": prop.area_usable,
        "ano_construcao": prop.year_built,
        "imagens": norm_imgs,
    }

def hard_delete_property(db: Session, property_id: int, tenant_id: int | None = None) -> Dict[str, Any]:
    prop = get_property(db, property_id, tenant_id=tenant_id)
    if not prop:
        raise ValueError("property_not_found")
    imgs = db.execute(select(PropertyImage).where(PropertyImage.property_id == property_id)).scalars().all()
    removed_files = 0
    for img in imgs:
        try:
            if delete_file(img.storage_key or ""):
                removed_files += 1
        except Exception:
            pass
        db.delete(img)
    db.delete(prop)
    db.commit()
    return {"ok": True, "images_deleted": removed_files}


def set_active_property(db: Session, property_id: int, active: bool, tenant_id: int | None = None) -> Property:
    prop = get_property(db, property_id, tenant_id=tenant_id)
    if not prop:
        raise ValueError("property_not_found")
    prop.is_active = bool(active)
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop


def soft_delete_property(db: Session, property_id: int, tenant_id: int | None = None) -> Dict[str, Any]:
    # Sem remover arquivos/imagens; apenas marca como inativo
    prop = get_property(db, property_id, tenant_id=tenant_id)
    if not prop:
        raise ValueError("property_not_found")
    if not prop.is_active:
        return {"ok": True, "already_inactive": True}
    prop.is_active = False
    db.add(prop)
    db.commit()
    return {"ok": True}
