from __future__ import annotations

from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.domain.realestate.models import Property, PropertyImage
from app.services.image_storage import save_property_images, ensure_base_dirs, delete_file

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


def delete_property_image(
    db: Session,
    property_id: int,
    image_id: int,
    remove_file: bool = True,
) -> dict:
    """Remove a imagem do imóvel. Se era capa, promove a próxima pela ordem.
    Reorganiza sort_order para manter sequência contígua iniciando em 0.
    """
    img = db.get(PropertyImage, image_id)
    if not img or int(img.property_id) != int(property_id):
        raise ValueError("image_not_found")

    storage_key = img.storage_key
    was_cover = bool(img.is_cover)

    db.delete(img)
    db.flush()

    promoted_id = None
    if was_cover:
        next_img = db.execute(
            select(PropertyImage)
            .where(PropertyImage.property_id == property_id)
            .order_by(PropertyImage.sort_order.asc(), PropertyImage.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        if next_img:
            next_img.is_cover = True
            db.add(next_img)
            promoted_id = next_img.id

    # Renumerar sort_order
    remaining = db.execute(
        select(PropertyImage)
        .where(PropertyImage.property_id == property_id)
        .order_by(PropertyImage.sort_order.asc(), PropertyImage.id.asc())
    ).scalars().all()
    for idx, r in enumerate(remaining):
        if int(r.sort_order or -1) != idx:
            r.sort_order = idx
            db.add(r)

    db.commit()

    if remove_file and storage_key:
        try:
            delete_file(storage_key)
        except Exception:
            pass

    return {"deleted": True, "promoted_cover_id": promoted_id}


def set_property_cover(db: Session, property_id: int, image_id: int) -> dict:
    """Define imagem como capa e remove flag das demais."""
    img = db.get(PropertyImage, image_id)
    if not img or int(img.property_id) != int(property_id):
        raise ValueError("image_not_found")

    imgs = db.execute(
        select(PropertyImage).where(PropertyImage.property_id == property_id)
    ).scalars().all()
    for r in imgs:
        r.is_cover = (r.id == img.id)
        db.add(r)
    db.commit()
    return {"ok": True}


def reorder_property_images(db: Session, property_id: int, items: list[dict]) -> dict:
    """Reordena imagens. items: [{"id": int, "ordem": int}]. Normaliza sequência ao final."""
    if not isinstance(items, list) or not items:
        raise ValueError("empty_items")

    # Mapear ordens desejadas
    desired = {int(i.get("id")): int(i.get("ordem")) for i in items if "id" in i and "ordem" in i}
    if not desired:
        raise ValueError("invalid_items")

    imgs = db.execute(
        select(PropertyImage)
        .where(PropertyImage.property_id == property_id)
        .order_by(PropertyImage.sort_order.asc(), PropertyImage.id.asc())
    ).scalars().all()
    img_by_id = {r.id: r for r in imgs}

    # Aplicar ordens informadas apenas para imagens do imóvel
    for iid, ordem in desired.items():
        r = img_by_id.get(iid)
        if r is None:
            continue
        try:
            ordem_int = int(ordem)
            if ordem_int < 0:
                ordem_int = 0
        except Exception:
            ordem_int = 0
        r.sort_order = ordem_int
        db.add(r)

    # Normalizar sequência final
    final = sorted(imgs, key=lambda x: (int(x.sort_order or 0), int(x.id)))
    for idx, r in enumerate(final):
        if int(r.sort_order or -1) != idx:
            r.sort_order = idx
            db.add(r)
    db.commit()
    return {"ok": True, "count": len(final)}
