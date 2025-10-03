from __future__ import annotations
from typing import Optional, Dict, Any
from app.domain.realestate.models import Property


def to_imovel_dict(p: Property, cover_image_url: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": p.id,
        "titulo": p.title,
        "tipo": p.type,
        "finalidade": p.purpose,
        "preco": p.price,
        "cidade": p.address_city,
        "estado": p.address_state,
        "bairro": p.address_neighborhood,
        "dormitorios": p.bedrooms,
        "banheiros": p.bathrooms,
        "suites": p.suites,
        "vagas": p.parking_spots,
        "ativo": p.is_active,
        "cover_image_url": cover_image_url,
    }
