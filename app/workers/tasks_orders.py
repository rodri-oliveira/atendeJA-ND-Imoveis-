from __future__ import annotations
from celery import Task
from app.workers.celery_app import celery
import structlog
from app.repositories.db import db_session
from app.repositories import models
from app.workers.tasks_outbound import send_text as task_send_text
from app.workers.tasks_outbound import send_template as task_send_template
from datetime import datetime, timedelta

log = structlog.get_logger()


@celery.task(name="orders.set_status", bind=True, max_retries=3)
def set_status_task(self: Task, order_id: int, target_status: str):
    """Altera status de pedido de forma assíncrona e envia notificação.
    Usa a mesma matriz de transição da API e respeita allow_direct_paid quando relevante.
    """
    with db_session() as db:
        order = db.get(models.Order, order_id)
        if not order:
            log.error("order_not_found", order_id=order_id)
            return {"ok": False, "error": "order_not_found"}

        tenant = db.get(models.Tenant, order.tenant_id)
        allow_direct_paid = bool((tenant.settings_json or {}).get("allow_direct_paid")) if tenant else False
        current = order.status
        target = models.OrderStatus(target_status)

        allowed: dict[models.OrderStatus, set[models.OrderStatus]] = {
            models.OrderStatus.draft: {models.OrderStatus.canceled},
            models.OrderStatus.pending_payment: {models.OrderStatus.paid, models.OrderStatus.canceled},
            models.OrderStatus.paid: {models.OrderStatus.in_kitchen, models.OrderStatus.canceled},
            models.OrderStatus.in_kitchen: {models.OrderStatus.out_for_delivery, models.OrderStatus.canceled},
            models.OrderStatus.out_for_delivery: {models.OrderStatus.delivered, models.OrderStatus.canceled},
            models.OrderStatus.delivered: set(),
            models.OrderStatus.canceled: set(),
        }
        if allow_direct_paid:
            allowed.setdefault(models.OrderStatus.draft, set()).add(models.OrderStatus.paid)
            allowed.setdefault(models.OrderStatus.in_kitchen, set()).add(models.OrderStatus.paid)
            allowed.setdefault(models.OrderStatus.out_for_delivery, set()).add(models.OrderStatus.paid)

        if target not in allowed.get(current, set()):
            log.warning("invalid_transition", current=current.value, target=target.value, order_id=order_id)
            return {"ok": False, "error": f"invalid_transition:{current.value}->{target.value}"}

        # Guardas mínimas para paid direto
        if target is models.OrderStatus.paid and allow_direct_paid:
            if not order.delivery_address:
                log.warning("address_required_for_paid", order_id=order_id)
                return {"ok": False, "error": "address_required"}

        order.status = target
        db.add(order)
        db.commit()
        db.refresh(order)

        # Notificação via template (fallback para texto)
        try:
            customer = db.get(models.Customer, order.customer_id)
            tenant = db.get(models.Tenant, order.tenant_id)
            if customer and customer.wa_id:
                cfg = (tenant.settings_json if tenant else {}) or {}
                lang = cfg.get("template_lang", "pt_BR")
                map_tpl = {
                    models.OrderStatus.paid: cfg.get("template_paid"),
                    models.OrderStatus.in_kitchen: cfg.get("template_in_kitchen"),
                    models.OrderStatus.out_for_delivery: cfg.get("template_out_for_delivery"),
                    models.OrderStatus.delivered: cfg.get("template_delivered"),
                    # confirm pode ser tratado na API quando aplicável
                }
                tpl = map_tpl.get(order.status)
                idem = f"order-status-{order.id}-{order.status.value}"
                if tpl:
                    task_send_template.delay(
                        tenant_id=str(int(tenant.id)) if tenant else "0",
                        to_wa_id=customer.wa_id,
                        template_name=tpl,
                        language_code=lang,
                        components=[],
                        idempotency_key=idem,
                    )
                else:
                    msg = {
                        models.OrderStatus.paid: "Pagamento confirmado! Seu pedido será preparado.",
                        models.OrderStatus.in_kitchen: "Seu pedido entrou em preparo.",
                        models.OrderStatus.out_for_delivery: "Seu pedido saiu para entrega.",
                        models.OrderStatus.delivered: "Pedido entregue. Bom apetite!",
                        models.OrderStatus.canceled: "Seu pedido foi cancelado.",
                    }.get(order.status, f"Status do pedido atualizado: {order.status.value}")
                    task_send_text.delay(
                        tenant_id=str(int(order.tenant_id)),
                        to_wa_id=customer.wa_id,
                        text=msg,
                        idempotency_key=idem,
                    )
        except Exception:
            pass

    return {"ok": True, "order_id": order_id, "status": target.value}


@celery.task(name="orders.check_sla_alerts", bind=True, max_retries=0)
def check_sla_alerts(self: Task):
    """Verifica pedidos que estouraram SLAs e notifica operação.
    Nota: usa created_at como base (aproximação) por não termos timestamp por status.
    """
    now = datetime.utcnow()
    alerted = []
    with db_session() as db:
        tenants = db.query(models.Tenant).all()
        for t in tenants:
            cfg = (t.settings_json or {})
            if not cfg.get("alerts_enabled"):
                continue
            channel = (cfg.get("alerts_channel") or "log").lower()
            ops_wa = cfg.get("alerts_ops_wa_id")

            def minutes(n):
                try:
                    return int(n)
                except Exception:
                    return 0

            sla_prep = max(0, minutes(cfg.get("sla_preparo_min", 0)))
            sla_ent = max(0, minutes(cfg.get("sla_entrega_min", 0)))
            sla_fin = max(0, minutes(cfg.get("sla_finalizacao_min", 0)))

            q = db.query(models.Order).filter(models.Order.tenant_id == t.id)
            rows = q.all()
            for o in rows:
                # Base de tempo: último evento do status atual (preciso); fallback para created_at
                base = None
                try:
                    ev = (
                        db.query(models.OrderStatusEvent)
                        .filter(
                            models.OrderStatusEvent.order_id == o.id,
                            models.OrderStatusEvent.to_status == o.status.value,
                        )
                        .order_by(models.OrderStatusEvent.id.desc())
                        .first()
                    )
                    if ev:
                        base = ev.created_at
                except Exception:
                    base = None
                if not base:
                    base = getattr(o, "created_at", None)
                if not base:
                    continue
                elapsed_min = (now - base).total_seconds() / 60.0
                over = None
                if o.status == models.OrderStatus.paid and sla_prep:
                    over = elapsed_min - sla_prep
                elif o.status == models.OrderStatus.in_kitchen and sla_ent:
                    over = elapsed_min - (sla_prep + sla_ent)
                elif o.status == models.OrderStatus.out_for_delivery and sla_fin:
                    over = elapsed_min - (sla_prep + sla_ent + sla_fin)
                if over is not None and over > 0:
                    msg = (
                        f"[ALERTA SLA] Pedido #{o.id} em '{o.status.value}' há {int(elapsed_min)} min; "
                        f"ultrapassou SLA em {int(over)} min."
                    )
                    if channel == "whatsapp" and ops_wa:
                        try:
                            task_send_text.delay(
                                tenant_id=str(int(t.id)),
                                to_wa_id=ops_wa,
                                text=msg,
                                idempotency_key=f"sla-alert-{o.id}-{o.status.value}",
                            )
                        except Exception:
                            log.warning("sla_alert_send_failed", order_id=o.id)
                    else:
                        log.warning("sla_alert", tenant=t.name, order_id=o.id, status=o.status.value, over_minutes=int(over))
                    alerted.append(o.id)

    return {"ok": True, "alerted_orders": alerted}
