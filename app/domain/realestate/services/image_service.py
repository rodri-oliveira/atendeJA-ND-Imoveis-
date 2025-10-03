from __future__ import annotations

from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.domain.realestate.models import Property, PropertyImage
from app.services.image_storage import save_property_images, ensure_base_dirs

# Políticas de limite (mantidas centralizadas no service)
MAX_FILES_PER_REQUEST = 10
MAX_IMAGES_PER_PROPERTY = 30


def upload_property_images(
    db: Session,
    property_id: int,
    files: List[any],      # UploadFile-like
    base_url: str,
) -> List[Dict]:
    """Salva imagens localmente e cria PropertyImage relacionados.
    Retorna lista de dicts: {id, url, is_capa, ordem}.
    Levanta ValueError para erros de domínio/regra (traduzidos em HTTP pelo router).
    """
    ensure_base_dirs()

    prop = db.get(Property, property_id)
    if not prop:
        raise ValueError("property_not_found")

    # Contagem atual
    current_count = db.execute(
        select(func.count()).select_from(PropertyImage).where(PropertyImage.property_id == property_id)
    ).scalar_one()

    if not files:
        raise ValueError("no_files")
    if len(files) > MAX_FILES_PER_REQUEST:
        raise ValueError(f"max_files_per_request={MAX_FILES_PER_REQUEST}")
    if current_count >= MAX_IMAGES_PER_PROPERTY:
        raise ValueError("max_images_per_property_reached")

    # Slots disponíveis
    remaining_slots = MAX_IMAGES_PER_PROPERTY - int(current_count)
    to_process = files[: max(0, min(len(files), remaining_slots))]
    if not to_process:
        raise ValueError("no_slots_available")

    # Próxima ordem e capa existente
    last_order = db.execute(
        select(PropertyImage.sort_order)
        .where(PropertyImage.property_id == property_id)
        .order_by(PropertyImage.sort_order.desc())
        .limit(1)
    ).scalar_one_or_none()
    next_order = int((last_order or -1) + 1)

    has_cover = bool(
        db.execute(
            select(func.count()).select_from(PropertyImage).where(
                PropertyImage.property_id == property_id, PropertyImage.is_cover == True  # noqa: E712
            )
        ).scalar_one()
    )

    # Persistir arquivos
    saved = save_property_images(property_id, to_process)

    created: List[Dict] = []
    for idx, (filename, full_path) in enumerate(saved):
        public_url = f"{base_url}/static/imoveis/{property_id}/{filename}"
        img = PropertyImage(
            property_id=property_id,
            url=public_url,
            storage_key=str(full_path),
            is_cover=(not has_cover and idx == 0),
            sort_order=next_order,
        )
        next_order += 1
        db.add(img)
        db.flush()
        created.append({
            "id": img.id,
            "url": public_url,
            "is_capa": bool(img.is_cover),
            "ordem": int(img.sort_order),
        })

    if created:
        db.commit()

    return created
