from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Literal
from app.api.deps import require_role_admin
from app.repositories.db import SessionLocal
from sqlalchemy import select
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
                                if dto.external_id and dto.price:
                                    if dto.external_id in target_ext_ids:
                                        found_map[dto.external_id] = {"price": dto.price}
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
                new_price = float(info["price"] or 0.0)
                if new_price <= 0:
                    continue
                stmt = select(re_models.Property).where(
                    re_models.Property.tenant_id == tenant.id,  # type: ignore
                    re_models.Property.source == payload.source,  # type: ignore
                    re_models.Property.external_id == eid,
                )
                prop = db.execute(stmt).scalar_one_or_none()
                if not prop:
                    continue
                if prop.price != new_price:
                    prop.price = new_price
                    db.add(prop)
                    updated += 1
            if updated:
                db.commit()

        return RepairPricesOut(targeted=len(target_ext_ids), updated_prices=updated, not_found=not_found[:50])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "re_repair_prices_error", "message": str(e)})
