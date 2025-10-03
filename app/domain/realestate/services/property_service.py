from __future__ import annotations
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.domain.realestate.models import Property, PropertyImage, PropertyPurpose, PropertyType
from app.domain.realestate.mappers import to_imovel_dict
from app.domain.realestate.utils import normalize_image_url


def create_property(db: Session, data: Dict[str, Any]) -> Property:
    tenant_id = int(1)
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

    if only_with_cover:
        stmt = stmt.join(PropertyImage, PropertyImage.property_id == Property.id).distinct()

    try:
        stmt = stmt.order_by(Property.updated_at.desc(), Property.id.desc())
    except Exception:
        stmt = stmt.order_by(Property.id.desc())

    # total filtrado
    stmt_count = stmt.order_by(None)
    total = db.execute(select(func.count()).select_from(stmt_count.subquery())).scalar_one()

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

    return out, int(total)


def get_property(db: Session, property_id: int) -> Property:
    prop = db.get(Property, property_id)
    if not prop:
        raise ValueError("property_not_found")
    return prop


def update_property(db: Session, property_id: int, data: Dict[str, Any]) -> Property:
    prop = db.get(Property, property_id)
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


def get_property_details(db: Session, property_id: int) -> Dict[str, Any]:
    prop = db.get(Property, property_id)
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

    base = to_imovel_dict(prop, cover_image_url=None)
    base.update({
        "descricao": prop.description,
        "area_total": prop.area_total,
        "area_util": prop.area_usable,
        "imagens": norm_imgs,
    })
    return base
