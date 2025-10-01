from __future__ import annotations

from typing import Tuple
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from app.domain.realestate import models as re_models


def upsert_property(db: Session, tenant_id: int, dto) -> Tuple[str, int]:
    """
    Faz UPSERT de um imóvel e substitui as imagens.
    Retorna (status, images_created) onde status in {"created", "updated"}.
    """
    # Garantir external_id para chave única com tenant
    external_id = dto.external_id or dto.url

    # Buscar existente
    stmt = select(re_models.Property).where(
        re_models.Property.tenant_id == tenant_id,
        re_models.Property.external_id == external_id,
    )
    prop = db.execute(stmt).scalar_one_or_none()

    # Mapear enums
    ptype_map = {
        "apartment": re_models.PropertyType.apartment,
        "house": re_models.PropertyType.house,
        "commercial": re_models.PropertyType.commercial,
        "land": re_models.PropertyType.land,
    }
    purpose_map = {
        "sale": re_models.PropertyPurpose.sale,
        "rent": re_models.PropertyPurpose.rent,
    }

    tipo_enum = ptype_map.get((dto.ptype or "apartment").lower(), re_models.PropertyType.apartment)
    purpose_enum = purpose_map.get((dto.purpose or "sale").lower(), re_models.PropertyPurpose.sale)

    images_created = 0

    if prop is None:
        prop = re_models.Property(
            tenant_id=tenant_id,
            title=(dto.title or "Sem título"),
            description=None,
            type=tipo_enum,
            purpose=purpose_enum,
            price=float(dto.price or 0.0),
            condo_fee=dto.condo_fee,
            iptu=dto.iptu,
            external_id=external_id,
            source="ndimoveis",
            updated_at_source=None,
            address_city=(dto.city or ""),
            address_state=(dto.state or ""),
            address_neighborhood=(dto.neighborhood or None),
            bedrooms=dto.bedrooms,
            bathrooms=dto.bathrooms,
            suites=dto.suites,
            parking_spots=dto.parking,
            area_total=dto.area_total,
            area_usable=None,
            is_active=True,
        )
        db.add(prop)
        db.flush()
        status = "created"
    else:
        prop.title = dto.title or prop.title
        prop.type = tipo_enum
        prop.purpose = purpose_enum
        prop.price = float(dto.price or prop.price)
        prop.condo_fee = dto.condo_fee
        prop.iptu = dto.iptu
        prop.address_city = (dto.city or prop.address_city)
        prop.address_state = (dto.state or prop.address_state)
        prop.address_neighborhood = (dto.neighborhood or prop.address_neighborhood)
        prop.bedrooms = dto.bedrooms
        prop.bathrooms = dto.bathrooms
        prop.suites = dto.suites
        prop.parking_spots = dto.parking
        prop.area_total = dto.area_total
        status = "updated"

    # Substituir imagens (se houver)
    imgs = dto.images or []
    if imgs:
        db.execute(delete(re_models.PropertyImage).where(re_models.PropertyImage.property_id == prop.id))
        order = 0
        for idx, url in enumerate(imgs):
            db.add(
                re_models.PropertyImage(
                    property_id=prop.id,
                    url=url,
                    is_cover=(idx == 0),
                    sort_order=order,
                )
            )
            order += 1
            images_created += 1

    return status, images_created
