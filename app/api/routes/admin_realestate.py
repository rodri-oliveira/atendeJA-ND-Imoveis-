
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Literal
from app.api.deps import require_role_admin
from app.repositories.db import SessionLocal
from sqlalchemy import select, func, delete
from app.domain.realestate import models as re_models
from app.domain.realestate.sources import ndimoveis as nd
from app.domain.realestate.importer import upsert_property
import httpx
import re
import time
from urllib.parse import urljoin


router = APIRouter(dependencies=[Depends(require_role_admin)])

# Registro simples em memória para tarefas assíncronas (MVP)
TASKS: dict[str, dict] = {}


@router.get("/ping")
def ping():
    return {"status": "ok"}


# Em desenvolvimento, usamos http para evitar problemas de cadeia SSL no Windows.
# Em produção, prefira https.
ND_BASE = "http://www.ndimoveis.com.br"


class NDCheckIn(BaseModel):
    finalidade: Literal["venda", "locacao", "both"] = Field(default="both")
    page_start: int = Field(default=1, ge=1)
    max_pages: int = Field(default=1, ge=1, le=50)
    per_detail: bool = True
    throttle_ms: int = Field(default=400, ge=0)


class NDCheckOut(BaseModel):
    discovered: int
    new: int
    existing: int
    new_items: list[dict]
    existing_items: list[dict]


def _nd_list_url_candidates(finalidade: str, page: int) -> list[str]:
    # Delega ao adapter centralizado
    return nd.list_url_candidates(finalidade, page)


def _extract_detail_links(html: str) -> list[str]:
    # Usa BeautifulSoup via adapter para maior robustez
    return nd.discover_list_links(html)


def _extract_external_id_from_detail(html: str) -> str | None:
    # Mantemos como fallback: o adapter já tenta extrair no parse_detail
    m = re.search(r"Código:\s*([A-Za-z]\d{2,})", html, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"#([A-Za-z]\d{2,})", html)
    if m2:
        return m2.group(1).strip()
    return None


@router.post("/import/ndimoveis/check", response_model=NDCheckOut)
def re_nd_check(payload: NDCheckIn):
    try:
        fins = ["venda", "locacao"] if payload.finalidade == "both" else [payload.finalidade]
        discovered_urls: list[str] = []
        # Nota: em alguns ambientes Windows, a cadeia de certificados pode não estar instalada
        # corretamente, causando CERTIFICATE_VERIFY_FAILED. Para fins de desenvolvimento,
        # desativamos a verificação SSL aqui. Em produção, habilite verify=True.
        with httpx.Client(timeout=20.0, headers={"User-Agent": "AtendeJA-Bot/1.0"}, verify=False) as client:
            for fin in fins:
                for page in range(payload.page_start, payload.page_start + payload.max_pages):
                    candidates = _nd_list_url_candidates(fin, page)
                    page_links: list[str] = []
                    for url in candidates:
                        try:
                            r = client.get(url)
                            if r.status_code != 200:
                                continue
                            links = _extract_detail_links(r.text)
                            page_links.extend(links)
                            if links:
                                # Achou links nesta variação, segue
                                break
                        except Exception:
                            continue
                        finally:
                            time.sleep(payload.throttle_ms / 1000.0)
                    if not page_links and page == payload.page_start:
                        # Fallback: tentar homepage capturar destaques
                        try:
                            hr = client.get(f"{ND_BASE}/")
                            if hr.status_code == 200:
                                page_links = _extract_detail_links(hr.text)
                        except Exception:
                            pass
                    if not page_links:
                        break
                    discovered_urls.extend(page_links)

            discovered_urls = sorted(list({u for u in discovered_urls}))
            new_items: list[dict] = []
            existing_items: list[dict] = []

            with SessionLocal() as db:
                # garante tenant default via nome em settings (já usado no admin.py)
                from app.api.routes.admin import _get_or_create_default_tenant  # evitar duplicação

                tenant = _get_or_create_default_tenant(db)
                for url in discovered_urls:
                    ext_id: str | None = None
                    if payload.per_detail:
                        try:
                            dr = client.get(url)
                            if dr.status_code == 200:
                                dto = nd.parse_detail(dr.text, url)
                                ext_id = dto.external_id
                        except Exception:
                            ext_id = None
                        time.sleep(payload.throttle_ms / 1000.0)

                    item = {"url": url}
                    if ext_id:
                        item["external_id"] = ext_id
                        stmt = select(re_models.Property.id).where(
                            re_models.Property.tenant_id == tenant.id,
                            re_models.Property.source == "ndimoveis",
                            re_models.Property.external_id == ext_id,
                        )
                        exists = db.execute(stmt).scalar_one_or_none()
                        (existing_items if exists else new_items).append(item)
                    else:
                        new_items.append(item)

        return NDCheckOut(
            discovered=len(discovered_urls),
            new=len(new_items),
            existing=len(existing_items),
            new_items=new_items[:200],
            existing_items=existing_items[:200],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "nd_check_error", "message": str(e)})


class NDRunIn(BaseModel):
    finalidade: Literal["venda", "locacao", "both"] = Field(default="both")
    page_start: int = Field(default=1, ge=1)
    max_pages: int = Field(default=2, ge=1, le=50)
    limit_properties: int | None = Field(default=10, ge=1, le=200)
    throttle_ms: int = Field(default=400, ge=0)


class NDRunOut(BaseModel):
    created: int
    images_created: int
    processed: int
    sampled_external_ids: list[str]


@router.post("/import/ndimoveis/run", response_model=NDRunOut)
def re_nd_run(payload: NDRunIn):
    try:
        fins = ["venda", "locacao"] if payload.finalidade == "both" else [payload.finalidade]
        discovered_urls: list[str] = []
        with httpx.Client(timeout=25.0, headers={"User-Agent": "AtendeJA-Bot/1.0"}, verify=False) as client:
            for fin in fins:
                for page in range(payload.page_start, payload.page_start + payload.max_pages):
                    candidates = _nd_list_url_candidates(fin, page)
                    page_links: list[str] = []
                    for url in candidates:
                        try:
                            r = client.get(url)
                            if r.status_code != 200:
                                continue
                            links = _extract_detail_links(r.text)
                            page_links.extend(links)
                            if links:
                                break
                        except Exception:
                            continue
                        finally:
                            time.sleep(payload.throttle_ms / 1000.0)
                    if not page_links and page == payload.page_start:
                        try:
                            hr = client.get(f"{ND_BASE}/")
                            if hr.status_code == 200:
                                page_links = _extract_detail_links(hr.text)
                        except Exception:
                            pass
                    if not page_links:
                        break
                    discovered_urls.extend(page_links)

            # Limitar quantos processar
            unique_urls = sorted(list({u for u in discovered_urls}))
            if payload.limit_properties:
                unique_urls = unique_urls[: payload.limit_properties]

            from app.api.routes.admin import _get_or_create_default_tenant  # reuse
            created = updated = images_created = processed = 0
            sample_ids: list[str] = []

            with SessionLocal() as db:
                tenant = _get_or_create_default_tenant(db)
                for url in unique_urls:
                    # Detalhe
                    try:
                        dr = client.get(url)
                        if dr.status_code != 200:
                            continue
                        html = dr.text
                    except Exception:
                        continue
                    time.sleep(payload.throttle_ms / 1000.0)

                    dto = nd.parse_detail(html, url)
                    if dto.external_id:
                        sample_ids.append(dto.external_id)

                    status, imgs_created = upsert_property(db, tenant.id, dto)
                    if status == "created":
                        created += 1
                    else:
                        updated += 1
                    images_created += imgs_created
                    processed += 1

                db.commit()

        return NDRunOut(
            created=created,
            updated=updated,
            images_created=images_created,
            processed=processed,
            sampled_external_ids=sample_ids[:20],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "nd_run_error", "message": str(e)})


# ====== Enfileiramento assíncrono (MVP) ======
class EnqueueIn(NDRunIn):
    pass


class EnqueueOut(BaseModel):
    task_id: str
    status: Literal["queued", "running", "done", "error"]


class TaskStatusOut(BaseModel):
    task_id: str
    status: Literal["queued", "running", "done", "error"]
    result: dict | None = None
    error: str | None = None


def _background_run(task_id: str, payload: NDRunIn):
    TASKS[task_id] = {"status": "running", "result": None, "error": None}
    try:
        res = re_nd_run(payload)  # reutiliza a lógica síncrona
        TASKS[task_id] = {"status": "done", "result": res.model_dump(), "error": None}
    except HTTPException as he:
        TASKS[task_id] = {"status": "error", "result": None, "error": str(he.detail)}
    except Exception as e:
        TASKS[task_id] = {"status": "error", "result": None, "error": str(e)}


@router.post("/import/ndimoveis/enqueue", response_model=EnqueueOut)
def re_nd_enqueue(payload: EnqueueIn, bg: BackgroundTasks):
    import uuid
    task_id = str(uuid.uuid4())
    TASKS[task_id] = {"status": "queued", "result": None, "error": None}
    bg.add_task(_background_run, task_id, payload)
    return EnqueueOut(task_id=task_id, status="queued")


@router.get("/import/status", response_model=TaskStatusOut)
def re_import_status(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="task_not_found")
    t = TASKS[task_id]
    return TaskStatusOut(task_id=task_id, status=t["status"], result=t.get("result"), error=t.get("error"))


# ====== Endpoints de auditoria ======
class RECountOut(BaseModel):
    total: int


@router.get("/properties/count", response_model=RECountOut)
def re_properties_count(source: str = "ndimoveis"):
    try:
        from app.api.routes.admin import _get_or_create_default_tenant
        with SessionLocal() as db:
            tenant = _get_or_create_default_tenant(db)
            stmt = select(re_models.Property).where(re_models.Property.tenant_id == tenant.id)
            if source:
                stmt = stmt.where(re_models.Property.source == source)
            # count(*) com SQLAlchemy 2.x
            from sqlalchemy import func
            total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
            return RECountOut(total=int(total))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "re_count_error", "message": str(e)})


class RESampleItem(BaseModel):
    id: int
    external_id: str | None
    title: str
    price: float


class RESampleOut(BaseModel):
    items: list[RESampleItem]


@router.get("/properties/sample", response_model=RESampleOut)
def re_properties_sample(source: str = "ndimoveis", limit: int = 10, order: Literal["created", "updated"] = "created"):
    try:
        from app.api.routes.admin import _get_or_create_default_tenant
        with SessionLocal() as db:
            tenant = _get_or_create_default_tenant(db)
            stmt = (
                select(
                    re_models.Property.id,
                    re_models.Property.external_id,
                    re_models.Property.title,
                    re_models.Property.price,
                )
                .where(re_models.Property.tenant_id == tenant.id)
            )
            if source:
                stmt = stmt.where(re_models.Property.source == source)
            order_col = re_models.Property.created_at if order == "created" else re_models.Property.updated_at
            stmt = stmt.order_by(order_col.desc()).limit(max(1, min(limit, 50)))
            rows = db.execute(stmt).all()
            items = [
                RESampleItem(
                    id=row[0],
                    external_id=row[1],
                    title=row[2],
                    price=float(row[3] or 0.0),
                )
                for row in rows
            ]
            return RESampleOut(items=items)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "re_sample_error", "message": str(e)})


# ====== Repair de preços (corrige apenas o campo price) ======
class RepairPricesIn(BaseModel):
    source: str = Field(default="ndimoveis")
    limit: int = Field(default=50, ge=1, le=200)
    max_pages_per_finalidade: int = Field(default=5, ge=1, le=20)
    throttle_ms: int = Field(default=300, ge=0)


class RepairPricesOut(BaseModel):
    targeted: int
    updated_prices: int
    not_found: list[str]


@router.post("/repair/prices", response_model=RepairPricesOut)
def re_repair_prices(payload: RepairPricesIn):
    try:
        from app.api.routes.admin import _get_or_create_default_tenant
        with SessionLocal() as db:
            tenant = _get_or_create_default_tenant(db)
            # Seleciona últimos N imóveis pela data de atualização (prioridade) do source
            stmt = (
                select(
                    re_models.Property.id,
                    re_models.Property.external_id,
                )
                .where(
                    re_models.Property.tenant_id == tenant.id,
                    re_models.Property.source == payload.source,
                )
                .order_by(re_models.Property.updated_at.desc())
                .limit(payload.limit)
            )
            rows = db.execute(stmt).all()
            target_ext_ids = [r[1] for r in rows if r[1]]

        # Descobrir URLs nas primeiras páginas e montar mapa ext_id -> dto
        fins = ["venda", "locacao"]
        found_map: dict[str, dict] = {}
        with httpx.Client(timeout=25.0, headers={"User-Agent": "AtendeJA-Bot/1.0"}, verify=False) as client:
            for fin in fins:
                for page in range(1, payload.max_pages_per_finalidade + 1):
                    for url in _nd_list_url_candidates(fin, page):
                        try:
                            r = client.get(url)
                            if r.status_code != 200:
                                continue
                            links = _extract_detail_links(r.text)
                        except Exception:
                            links = []
                        finally:
                            time.sleep(payload.throttle_ms / 1000.0)
                        for durl in links:
                            try:
                                dr = client.get(durl)
                                if dr.status_code != 200:
                                    continue
                                dto = nd.parse_detail(dr.text, durl)
                                if dto.external_id:
                                    if dto.external_id in target_ext_ids:
                                        found_map[dto.external_id] = {
                                            "price": dto.price,
                                            "purpose": dto.purpose,
                                        }
                            except Exception:
                                continue
                            finally:
                                time.sleep(payload.throttle_ms / 1000.0)

        # Atualizar apenas o campo price
        updated = 0
        not_found: list[str] = []
        with SessionLocal() as db:
            for eid in target_ext_ids:
                info = found_map.get(eid)
                if not info:
                    not_found.append(eid)
                    continue
                new_price = float(info.get("price") or 0.0)
                new_purpose = info.get("purpose")
                if new_price <= 0:
                    # Mesmo sem preço válido, ainda podemos corrigir finalidade
                    pass
                stmt = select(re_models.Property).where(
                    re_models.Property.tenant_id == tenant.id,  # type: ignore
                    re_models.Property.source == payload.source,  # type: ignore
                    re_models.Property.external_id == eid,
                )
                prop = db.execute(stmt).scalar_one_or_none()
                if not prop:
                    continue
                changed = False
                if new_price > 0 and prop.price != new_price:
                    prop.price = new_price
                    changed = True
                if isinstance(new_purpose, str) and new_purpose in ("sale", "rent"):
                    # Atualiza finalidade se divergente
                    try:
                        from app.domain.realestate.models import PropertyPurpose as _PP
                        new_pp = _PP(new_purpose)
                        if getattr(prop, "purpose", None) != new_pp:
                            prop.purpose = new_pp
                            changed = True
                    except Exception:
                        pass
                if changed:
                    db.add(prop)
                    updated += 1
            if updated:
                db.commit()

        return RepairPricesOut(targeted=len(target_ext_ids), updated_prices=updated, not_found=not_found[:50])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "re_repair_prices_error", "message": str(e)})


# ====== Repair de finalidade (purpose) a partir do título ======
class RepairPurposeIn(BaseModel):
    source: str = Field(default="ndimoveis")
    cidade: str | None = None
    estado: str | None = None
    limit: int = Field(default=200, ge=1, le=1000)
    dry_run: bool = Field(default=False)


class RepairPurposeOut(BaseModel):
    targeted: int
    updated: int
    unchanged: int
    examples: list[dict] = []


@router.post("/repair/purpose_from_title", response_model=RepairPurposeOut)
def re_repair_purpose_from_title(payload: RepairPurposeIn):
    try:
        from app.api.routes.admin import _get_or_create_default_tenant
        with SessionLocal() as db:
            tenant = _get_or_create_default_tenant(db)
            stmt = (
                select(
                    re_models.Property.id,
                    re_models.Property.title,
                    re_models.Property.purpose,
                    re_models.Property.address_city,
                    re_models.Property.address_state,
                )
                .where(
                    re_models.Property.tenant_id == tenant.id,  # type: ignore
                    re_models.Property.source == payload.source,  # type: ignore
                )
                .order_by(re_models.Property.updated_at.desc())
                .limit(payload.limit)
            )
            if payload.cidade:
                stmt = stmt.where(re_models.Property.address_city.ilike(f"%{payload.cidade.strip()}%"))
            if payload.estado:
                stmt = stmt.where(re_models.Property.address_state == payload.estado.strip().upper())

            rows = db.execute(stmt).all()
            targeted = len(rows)
            updated = 0
            unchanged = 0
            examples: list[dict] = []

            # Função simples para inferir finalidade com base no título
            import re as _re
            def infer_purpose(title: str | None) -> str | None:
                if not title:
                    return None
                t = title.lower()
                if _re.search(r"loca[cç][aã]o|alug", t):
                    return "rent"
                if _re.search(r"venda", t):
                    return "sale"
                return None

            if not payload.dry_run:
                for rid, title, purpose, city, state in rows:
                    new_p = infer_purpose(title)
                    if new_p is None:
                        unchanged += 1
                        continue
                    try:
                        from app.domain.realestate.models import PropertyPurpose as _PP
                        new_pp = _PP(new_p)
                    except Exception:
                        unchanged += 1
                        continue
                    prop = db.get(re_models.Property, rid)
                    if not prop:
                        unchanged += 1
                        continue
                    if getattr(prop, "purpose", None) != new_pp:
                        prop.purpose = new_pp
                        db.add(prop)
                        updated += 1
                        if len(examples) < 10:
                            examples.append({
                                "id": rid,
                                "title": title,
                                "from": str(purpose),
                                "to": new_p,
                                "cidade": city,
                                "estado": state,
                            })
                    else:
                        unchanged += 1
                if updated:
                    db.commit()
            else:
                # Apenas simula (dry run)
                for rid, title, purpose, city, state in rows:
                    new_p = infer_purpose(title)
                    if new_p and len(examples) < 10:
                        examples.append({
                            "id": rid,
                            "title": title,
                            "from": str(purpose),
                            "to": new_p,
                            "cidade": city,
                            "estado": state,
                        })

            return RepairPurposeOut(targeted=targeted, updated=updated, unchanged=unchanged, examples=examples)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "re_repair_purpose_error", "message": str(e)})


# ====== Repair de imagens inválidas ======
class RepairImagesIn(BaseModel):
    source: str = Field(default="ndimoveis")
    cidade: str | None = None
    estado: str | None = None
    limit: int = Field(default=200, ge=1, le=1000)
    dry_run: bool = Field(default=False)


class RepairImagesOut(BaseModel):
    properties_checked: int
    images_removed: int
    properties_updated: int
    examples: list[dict] = []


def _is_valid_image_url(url: str | None) -> bool:
    """Valida se a URL da imagem tem domínio válido."""
    if not url:
        return False
    try:
        u = str(url).strip()
        if not (u.startswith('http://') or u.startswith('https://')):
            return False
        from urllib.parse import urlparse
        parsed = urlparse(u)
        # Verifica se tem hostname e se contém pelo menos um ponto (domínio válido)
        return bool(parsed.hostname and '.' in parsed.hostname)
    except Exception:
        return False


@router.post("/images/repair_invalid", response_model=RepairImagesOut)
def re_repair_invalid_images(payload: RepairImagesIn):
    """
    Remove imagens com URLs inválidas (sem domínio válido) e promove 
    uma imagem válida como capa quando necessário.
    """
    try:
        from app.api.routes.admin import _get_or_create_default_tenant
        with SessionLocal() as db:
            tenant = _get_or_create_default_tenant(db)
            
            # Buscar imóveis
            stmt = (
                select(re_models.Property.id)
                .where(
                    re_models.Property.tenant_id == tenant.id,  # type: ignore
                    re_models.Property.source == payload.source,  # type: ignore
                )
                .order_by(re_models.Property.updated_at.desc())
                .limit(payload.limit)
            )
            if payload.cidade:
                stmt = stmt.where(re_models.Property.address_city.ilike(f"%{payload.cidade.strip()}%"))
            if payload.estado:
                stmt = stmt.where(re_models.Property.address_state == payload.estado.strip().upper())
            
            property_ids = [row[0] for row in db.execute(stmt).all()]
            
            properties_checked = len(property_ids)
            images_removed = 0
            properties_updated = 0
            examples: list[dict] = []
            
            for prop_id in property_ids:
                # Buscar imagens do imóvel
                img_stmt = (
                    select(re_models.PropertyImage)
                    .where(re_models.PropertyImage.property_id == prop_id)
                    .order_by(re_models.PropertyImage.order)
                )
                images = db.execute(img_stmt).scalars().all()
                
                if not images:
                    continue
                
                # Separar válidas e inválidas
                invalid_images = [img for img in images if not _is_valid_image_url(img.url)]
                valid_images = [img for img in images if _is_valid_image_url(img.url)]
                
                if not invalid_images:
                    continue
                
                property_changed = False
                
                if not payload.dry_run:
                    # Remover imagens inválidas
                    for img in invalid_images:
                        db.delete(img)
                        images_removed += 1
                        property_changed = True
                    
                    # Se havia capa inválida e existem imagens válidas, promover a primeira válida
                    had_invalid_cover = any(img.is_cover for img in invalid_images)
                    if had_invalid_cover and valid_images:
                        # Remover flag de capa de todas
                        for img in valid_images:
                            img.is_cover = False
                        # Promover primeira válida
                        valid_images[0].is_cover = True
                        db.add(valid_images[0])
                        property_changed = True
                
                if property_changed or payload.dry_run:
                    properties_updated += 1
                    if len(examples) < 10:
                        prop = db.get(re_models.Property, prop_id)
                        examples.append({
                            "property_id": prop_id,
                            "title": prop.title if prop else None,
                            "invalid_urls": [img.url for img in invalid_images[:3]],
                            "invalid_count": len(invalid_images),
                            "valid_count": len(valid_images),
                        })
            
            if not payload.dry_run and images_removed > 0:
                db.commit()
            
            return RepairImagesOut(
                properties_checked=properties_checked,
                images_removed=images_removed if not payload.dry_run else 0,
                properties_updated=properties_updated,
                examples=examples,
            )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "re_repair_images_error", "message": str(e)})


# ====== Reset (limpeza) de imóveis e imagens por fonte ======
class REResetIn(BaseModel):
    source: str = Field(default="ndimoveis")
    dry_run: bool = Field(default=True)
    confirm: str | None = Field(default=None, description="Use 'CONFIRM' para executar sem dry_run")


class REResetOut(BaseModel):
    source: str
    dry_run: bool
    properties_total: int
    images_total: int
    deleted_properties: int
    deleted_images: int


@router.post("/properties/reset", response_model=REResetOut)
def re_properties_reset(payload: REResetIn):
    """
    Remove TODOS os imóveis e imagens da fonte informada apenas para o tenant padrão.
    - dry_run=True: apenas retorna as contagens (não deleta nada)
    - Para executar a exclusão, envie confirm="CONFIRM" e dry_run=False
    """
    try:
        from app.api.routes.admin import _get_or_create_default_tenant
        with SessionLocal() as db:
            tenant = _get_or_create_default_tenant(db)

            # Coletar IDs de imóveis por tenant+source
            p_stmt = (
                select(re_models.Property.id)
                .where(re_models.Property.tenant_id == tenant.id)
            )
            if payload.source:
                p_stmt = p_stmt.where(re_models.Property.source == payload.source)
            prop_ids = [row[0] for row in db.execute(p_stmt).all()]

            if not prop_ids:
                return REResetOut(
                    source=payload.source,
                    dry_run=bool(payload.dry_run),
                    properties_total=0,
                    images_total=0,
                    deleted_properties=0,
                    deleted_images=0,
                )

            # Contar imagens relacionadas
            img_total = db.execute(
                select(func.count()).where(re_models.PropertyImage.property_id.in_(prop_ids))
            ).scalar_one()

            if payload.dry_run:
                return REResetOut(
                    source=payload.source,
                    dry_run=True,
                    properties_total=len(prop_ids),
                    images_total=int(img_total),
                    deleted_properties=0,
                    deleted_images=0,
                )

            if payload.confirm != "CONFIRM":
                raise HTTPException(status_code=400, detail={"code": "confirm_required", "message": "Envie confirm='CONFIRM' para executar sem dry_run"})

            # Executar deleção em transação
            del_imgs_stmt = delete(re_models.PropertyImage).where(re_models.PropertyImage.property_id.in_(prop_ids))
            del_props_stmt = delete(re_models.Property).where(re_models.Property.id.in_(prop_ids))
            
            deleted_images_count = db.execute(del_imgs_stmt).rowcount
            deleted_properties_count = db.execute(del_props_stmt).rowcount

            db.commit()

            return REResetOut(
                source=payload.source,
                dry_run=False,
                properties_total=len(prop_ids),
                images_total=int(img_total),
                deleted_properties=deleted_properties_count,
                deleted_images=deleted_images_count,
            )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "re_reset_error", "message": str(e)})


# ====== Importar por URLs explícitas (ND Imóveis) ======

class NDFromUrlsIn(BaseModel):
    urls: list[str]
    throttle_ms: int = 250


class NDFromUrlsOut(BaseModel):
    created: int
    updated: int
    images_created: int
    processed: int
    sampled_external_ids: list[str]
    errors: list[dict] = []


@router.post("/import/ndimoveis/from_urls", response_model=NDFromUrlsOut)
def re_nd_import_from_urls(payload: NDFromUrlsIn):
    try:
        if not payload.urls:
            return NDFromUrlsOut(created=0, updated=0, images_created=0, processed=0, sampled_external_ids=[], errors=[])
        from app.api.routes.admin import _get_or_create_default_tenant  # reuse
        created = updated = images_created = processed = 0
        sample_ids: list[str] = []
        errs: list[dict] = []
        with httpx.Client(timeout=25.0, headers={"User-Agent": "AtendeJA-Bot/1.0"}, verify=False) as client:
            with SessionLocal() as db:
                tenant = _get_or_create_default_tenant(db)
                for url in payload.urls:
                    try:
                        r = client.get(url)
                        if r.status_code != 200:
                            errs.append({"url": url, "status": r.status_code})
                            continue
                        dto = nd.parse_detail(r.text, url)
                        if dto.external_id:
                            sample_ids.append(dto.external_id)
                        st, imgs = upsert_property(db, tenant.id, dto)
                        if st == "created":
                            created += 1
                        else:
                            updated += 1
                        images_created += imgs
                        processed += 1
                    except Exception as e:  # noqa: BLE001
                        errs.append({"url": url, "error": str(e)})
                    finally:
                        time.sleep(max(0, payload.throttle_ms) / 1000.0)
                db.commit()
        return NDFromUrlsOut(
            created=created,
            updated=updated,
            images_created=images_created,
            processed=processed,
            sampled_external_ids=sample_ids[:20],
            errors=errs[:20],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "nd_from_urls_error", "message": str(e)})