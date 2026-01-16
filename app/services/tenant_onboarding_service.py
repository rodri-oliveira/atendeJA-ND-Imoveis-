from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.api.schemas.chatbot_templates import ChatbotFlowTemplateApplyIn
from app.repositories.models import Tenant, WhatsAppAccount, UserRole, OnboardingRun, UserInvite
from app.services.chatbot_template_service import apply_chatbot_flow_template
from app.core.config import settings
from app.domain.catalog.models import CatalogIngestionRun
from app.services.vehicle_ingestion_jobs import run_vehicle_ingestion_job


@dataclass(frozen=True)
class OnboardTenantByUrlResult:
    tenant_id: int
    tenant_name: str
    chatbot_domain: str
    flow_id: int
    published: bool
    published_version: int | None
    ingestion: dict | None
    whatsapp_account_id: int | None
    invite_token: str | None
    invite_email: str | None


class TenantOnboardingService:
    def __init__(self, *, db: Session):
        self.db = db

    def ensure_tenant(
        self,
        *,
        name: str,
        timezone: str,
        chatbot_domain: str,
        allow_existing: bool,
    ) -> Tenant:
        tenant_name = (name or "").strip()
        if not tenant_name:
            raise HTTPException(status_code=400, detail="name_required")

        domain = (chatbot_domain or "").strip() or "real_estate"

        exists = self.db.query(Tenant).filter(Tenant.name == tenant_name).first()
        if exists and not allow_existing:
            raise HTTPException(status_code=400, detail="tenant_name_already_exists")

        if exists:
            t = exists
            settings_json = dict(getattr(t, "settings_json", {}) or {})
            changed = False

            if (settings_json.get("chatbot_domain") or "").strip() != domain:
                settings_json["chatbot_domain"] = domain
                changed = True

            raw_enabled = settings_json.get("enabled_domains")
            if isinstance(raw_enabled, list):
                enabled_domains = [str(x).strip() for x in raw_enabled if str(x).strip()]
            else:
                enabled_domains = []
            if not enabled_domains:
                enabled_domains = [domain]
                changed = True
            if domain not in enabled_domains:
                enabled_domains = [domain, *[d for d in enabled_domains if d != domain]]
                changed = True
            settings_json["enabled_domains"] = enabled_domains

            if changed:
                t.settings_json = settings_json
                self.db.add(t)
                self.db.flush()
            return t

        t = Tenant(name=tenant_name, timezone=(timezone or "America/Sao_Paulo"))
        settings_json = dict(getattr(t, "settings_json", {}) or {})
        settings_json["chatbot_domain"] = domain
        settings_json["enabled_domains"] = [domain]
        t.settings_json = settings_json

        self.db.add(t)
        self.db.flush()
        return t

    def apply_flow_template(
        self,
        *,
        tenant_id: int,
        chatbot_domain: str,
        template: str,
        flow_name: str,
        overwrite_flow: bool,
        publish_flow: bool,
    ):
        domain = (chatbot_domain or "").strip() or "real_estate"
        tpl_payload = ChatbotFlowTemplateApplyIn(
            domain=domain,
            template=(template or "default"),
            name=(flow_name or "default"),
            overwrite=bool(overwrite_flow),
            publish=bool(publish_flow),
        )
        return apply_chatbot_flow_template(db=self.db, tenant_id=int(tenant_id), payload=tpl_payload, commit=False)

    def create_whatsapp_account(
        self,
        *,
        tenant_id: int,
        phone_number_id: str | None,
        waba_id: str | None,
        token: str | None,
    ) -> int:
        pnid = (phone_number_id or "").strip()
        if not pnid:
            raise HTTPException(status_code=400, detail="phone_number_id_required")

        existing_wa = self.db.query(WhatsAppAccount).filter(WhatsAppAccount.phone_number_id == pnid).first()
        if existing_wa:
            raise HTTPException(status_code=400, detail="phone_number_id_already_exists")

        wa = WhatsAppAccount(
            tenant_id=int(tenant_id),
            phone_number_id=pnid,
            waba_id=((waba_id or "").strip() or None),
            token=((token or "").strip() or None),
            is_active=True,
        )
        self.db.add(wa)
        self.db.flush()
        return int(wa.id)

    def invite_admin(
        self,
        *,
        tenant_id: int,
        invite_admin_email: str,
        invite_expires_hours: int | None,
    ) -> tuple[str, str]:
        from app.api.routes.admin import _issue_invite

        email = (invite_admin_email or "").strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="email_required")
        expires_hours = int(invite_expires_hours or 72)
        out = _issue_invite(
            self.db,
            email=email,
            role=UserRole.admin,
            tenant_id=int(tenant_id),
            expires_hours=expires_hours,
            commit=False,
        )
        return str(out.token), str(out.email)

    def enqueue_ingestion(
        self,
        *,
        tenant_id: int,
        base_url: str,
        max_listings: int,
        timeout_seconds: float,
        max_listing_pages: int,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict:
        base = (base_url or "").strip()
        if not base:
            raise HTTPException(status_code=400, detail="base_url_required")

        run = CatalogIngestionRun(tenant_id=int(tenant_id), source_base_url=base, status="queued")
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        if background_tasks is not None and (settings.APP_ENV or "").lower() != "test":
            background_tasks.add_task(
                run_vehicle_ingestion_job,
                tenant_id=int(tenant_id),
                run_id=int(run.id),
                base_url=base,
                max_listings=int(max_listings),
                timeout_seconds=float(timeout_seconds),
                max_listing_pages=int(max_listing_pages),
            )

        return {
            "run_id": int(run.id),
            "status": str(run.status),
        }

    async def onboard_by_url(
        self,
        *,
        idempotency_key: str | None,
        name: str,
        timezone: str,
        chatbot_domain: str,
        allow_existing: bool,
        template: str,
        flow_name: str,
        overwrite_flow: bool,
        publish_flow: bool,
        base_url: str | None,
        run_ingestion: bool,
        max_listings: int,
        timeout_seconds: float,
        max_listing_pages: int,
        create_whatsapp_account: bool,
        phone_number_id: str | None,
        waba_id: str | None,
        token: str | None,
        invite_admin_email: str | None,
        invite_expires_hours: int | None,
        background_tasks: BackgroundTasks | None = None,
    ) -> OnboardTenantByUrlResult:
        tenant_name = (name or "").strip()
        if not tenant_name:
            raise HTTPException(status_code=400, detail="name_required")

        domain = (chatbot_domain or "").strip() or "real_estate"

        t: Tenant | None = None
        tpl_out = None
        wa_account_id: int | None = None
        invite_token: str | None = None
        invite_email: str | None = None

        key = (idempotency_key or "").strip() or None
        req_payload = {
            "name": tenant_name,
            "timezone": (timezone or "America/Sao_Paulo"),
            "chatbot_domain": domain,
            "allow_existing": bool(allow_existing),
            "template": (template or "default"),
            "flow_name": (flow_name or "default"),
            "overwrite_flow": bool(overwrite_flow),
            "publish_flow": bool(publish_flow),
            "create_whatsapp_account": bool(create_whatsapp_account),
            "phone_number_id": (phone_number_id or None),
            "waba_id": (waba_id or None),
            "invite_admin_email": (invite_admin_email or None),
            "invite_expires_hours": int(invite_expires_hours or 72),
        }

        run: OnboardingRun | None = None
        if key:
            run = self.db.query(OnboardingRun).filter(OnboardingRun.idempotency_key == key).first()
            if run:
                if (run.request_json or {}) != req_payload:
                    if run is not None:
                        try:
                            run.status = "failed"
                            run.error_code = "idempotency_key_conflict"
                            self.db.add(run)
                            self.db.commit()
                        except Exception:
                            self.db.rollback()
                    raise HTTPException(status_code=409, detail="idempotency_key_conflict")
                if run.status == "completed" and run.response_json:
                    js = run.response_json
                    replay_invite_token: str | None = None
                    replay_invite_email: str | None = None
                    if js.get("invite_email") and js.get("tenant_id"):
                        replay_invite_email = str(js.get("invite_email"))
                        try:
                            tenant_id = int(js.get("tenant_id") or 0)
                            invite = (
                                self.db.query(UserInvite)
                                .filter(
                                    UserInvite.tenant_id == tenant_id,
                                    UserInvite.email == replay_invite_email,
                                    UserInvite.used_at.is_(None),
                                    UserInvite.expires_at > datetime.utcnow(),
                                )
                                .order_by(UserInvite.id.desc())
                                .first()
                            )
                            if invite:
                                replay_invite_token = str(invite.token)
                        except Exception:
                            replay_invite_token = None
                    return OnboardTenantByUrlResult(
                        tenant_id=int(js.get("tenant_id") or 0),
                        tenant_name=str(js.get("tenant_name") or ""),
                        chatbot_domain=str(js.get("chatbot_domain") or domain),
                        flow_id=int(js.get("flow_id") or 0),
                        published=bool(js.get("published")),
                        published_version=(int(js.get("published_version")) if js.get("published_version") is not None else None),
                        ingestion=(js.get("ingestion") if isinstance(js.get("ingestion"), dict) else None),
                        whatsapp_account_id=(int(js.get("whatsapp_account_id")) if js.get("whatsapp_account_id") is not None else None),
                        invite_token=replay_invite_token,
                        invite_email=replay_invite_email,
                    )
                if run.status == "in_progress":
                    if run is not None:
                        try:
                            run.error_code = "onboarding_in_progress"
                            self.db.add(run)
                            self.db.commit()
                        except Exception:
                            self.db.rollback()
                    raise HTTPException(status_code=409, detail="onboarding_in_progress")

            if not run:
                run = OnboardingRun(idempotency_key=key, status="in_progress", request_json=req_payload)
                try:
                    self.db.add(run)
                    self.db.commit()
                    self.db.refresh(run)
                except Exception:
                    self.db.rollback()
                    run = self.db.query(OnboardingRun).filter(OnboardingRun.idempotency_key == key).first()
                    if run and (run.request_json or {}) != req_payload:
                        raise HTTPException(status_code=409, detail="idempotency_key_conflict")
                    if run and run.status == "completed" and run.response_json:
                        js = run.response_json
                        replay_invite_token: str | None = None
                        replay_invite_email: str | None = None
                        if js.get("invite_email") and js.get("tenant_id"):
                            replay_invite_email = str(js.get("invite_email"))
                            try:
                                tenant_id = int(js.get("tenant_id") or 0)
                                invite = (
                                    self.db.query(UserInvite)
                                    .filter(
                                        UserInvite.tenant_id == tenant_id,
                                        UserInvite.email == replay_invite_email,
                                        UserInvite.used_at.is_(None),
                                        UserInvite.expires_at > datetime.utcnow(),
                                    )
                                    .order_by(UserInvite.id.desc())
                                    .first()
                                )
                                if invite:
                                    replay_invite_token = str(invite.token)
                            except Exception:
                                replay_invite_token = None
                        return OnboardTenantByUrlResult(
                            tenant_id=int(js.get("tenant_id") or 0),
                            tenant_name=str(js.get("tenant_name") or ""),
                            chatbot_domain=str(js.get("chatbot_domain") or domain),
                            flow_id=int(js.get("flow_id") or 0),
                            published=bool(js.get("published")),
                            published_version=(int(js.get("published_version")) if js.get("published_version") is not None else None),
                            ingestion=(js.get("ingestion") if isinstance(js.get("ingestion"), dict) else None),
                            whatsapp_account_id=(int(js.get("whatsapp_account_id")) if js.get("whatsapp_account_id") is not None else None),
                            invite_token=replay_invite_token,
                            invite_email=replay_invite_email,
                        )
                    if run and run.status == "in_progress":
                        raise HTTPException(status_code=409, detail="onboarding_in_progress")
                    raise

        try:
            t = self.ensure_tenant(
                name=tenant_name,
                timezone=timezone,
                chatbot_domain=domain,
                allow_existing=bool(allow_existing),
            )

            tpl_out = self.apply_flow_template(
                tenant_id=int(t.id),
                chatbot_domain=domain,
                template=template,
                flow_name=flow_name,
                overwrite_flow=bool(overwrite_flow),
                publish_flow=bool(publish_flow),
            )

            if create_whatsapp_account:
                wa_account_id = self.create_whatsapp_account(
                    tenant_id=int(t.id),
                    phone_number_id=phone_number_id,
                    waba_id=waba_id,
                    token=token,
                )

            if invite_admin_email:
                invite_token, invite_email = self.invite_admin(
                    tenant_id=int(t.id),
                    invite_admin_email=invite_admin_email,
                    invite_expires_hours=invite_expires_hours,
                )

            self.db.commit()
        except HTTPException as e:
            self.db.rollback()
            if run is not None:
                try:
                    run.status = "failed"
                    run.error_code = str(getattr(e, "detail", None) or "http_error")
                    self.db.add(run)
                    self.db.commit()
                except Exception:
                    self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            if run is not None:
                try:
                    run.status = "failed"
                    run.error_code = "unexpected_error"
                    self.db.add(run)
                    self.db.commit()
                except Exception:
                    self.db.rollback()
            raise

        # Importante: ingestão faz I/O externo. Não deve ocorrer dentro de transação.
        ingestion_out: dict | None = None
        if run_ingestion:
            assert t is not None
            ingestion_out = self.enqueue_ingestion(
                tenant_id=int(t.id),
                base_url=str(base_url or ""),
                max_listings=int(max_listings),
                timeout_seconds=float(timeout_seconds),
                max_listing_pages=int(max_listing_pages),
                background_tasks=background_tasks,
            )

        assert t is not None
        assert tpl_out is not None

        resp_payload = {
            "tenant_id": int(t.id),
            "tenant_name": str(t.name),
            "chatbot_domain": domain,
            "flow_id": int(tpl_out.flow_id),
            "published": bool(tpl_out.published),
            "published_version": (int(tpl_out.published_version) if tpl_out.published_version is not None else None),
            "ingestion": ingestion_out,
            "whatsapp_account_id": wa_account_id,
            "invite_email": invite_email,
        }

        if run is not None:
            try:
                run.status = "completed"
                run.tenant_id = int(t.id)
                run.response_json = resp_payload
                run.error_code = None
                self.db.add(run)
                self.db.commit()
            except Exception:
                self.db.rollback()

        return OnboardTenantByUrlResult(
            tenant_id=int(t.id),
            tenant_name=str(t.name),
            chatbot_domain=domain,
            flow_id=int(tpl_out.flow_id),
            published=bool(tpl_out.published),
            published_version=(int(tpl_out.published_version) if tpl_out.published_version is not None else None),
            ingestion=ingestion_out,
            whatsapp_account_id=wa_account_id,
            invite_token=invite_token,
            invite_email=invite_email,
        )
