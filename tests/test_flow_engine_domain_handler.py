from __future__ import annotations

from app.domain.realestate.models import ChatbotFlow
from app.services.flow_engine import FlowEngine


def test_flow_engine_uses_domain_handler(db_session):
    flow_definition = {
        "version": 1,
        "start": "start",
        "nodes": [
            {"id": "start", "type": "handler", "handler": "start", "transitions": []},
        ],
    }

    db_session.add(
        ChatbotFlow(
            tenant_id=1,
            domain="car_dealer",
            name="default-test-domain-handler",
            flow_definition=flow_definition,
            is_published=True,
            published_version=1,
            published_by="test",
        )
    )
    db_session.commit()

    engine = FlowEngine(db_session)
    out = engine.try_process_message(
        sender_id="tester-domain-handler",
        tenant_id=1,
        domain="car_dealer",
        text_raw="oi",
        text_normalized="oi",
        state={"stage": "start"},
    )

    assert out.handled is True
    assert "Car Dealer handler" in (out.message or "")
