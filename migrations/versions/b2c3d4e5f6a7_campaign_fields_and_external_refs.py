"""campanhas e refs externas: leads.campaign_* + properties.ref_code + property_external_refs

Revision ID: b2c3d4e5f6a7
Revises: a1e2b3c4d5e6
Create Date: 2025-10-14 12:34:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1e2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_existing_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    try:
        rows = bind.exec_driver_sql(f"PRAGMA table_info('{table_name}')").fetchall()
        return {row[1] for row in rows}
    except Exception:
        insp = sa.inspect(bind)
        return {c["name"] for c in insp.get_columns(table_name)}


def upgrade() -> None:
    # 1) re_properties.ref_code (String(16)) e índice único por tenant
    props_cols = _get_existing_columns("re_properties")
    if "ref_code" not in props_cols:
        with op.batch_alter_table("re_properties", schema=None) as batch_op:
            batch_op.add_column(sa.Column("ref_code", sa.String(length=16), nullable=True))
    # Criar índice único (tenant_id, ref_code) se não existir
    insp = sa.inspect(op.get_bind())
    existing_idxs = {ix.get("name") for ix in insp.get_indexes("re_properties")}
    if "uix_re_prop_tenant_refcode" not in existing_idxs:
        op.create_index("uix_re_prop_tenant_refcode", "re_properties", ["tenant_id", "ref_code"], unique=True)

    # 2) Tabela re_property_external_refs
    bind = op.get_bind()
    has_ext_refs = False
    try:
        bind.exec_driver_sql("SELECT 1 FROM re_property_external_refs LIMIT 1")
        has_ext_refs = True
    except Exception:
        has_ext_refs = False
    if not has_ext_refs:
        op.create_table(
            "re_property_external_refs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("provider", sa.String(length=32), nullable=False, index=True),
            sa.Column("external_id", sa.String(length=160), nullable=False),
            sa.Column("url", sa.String(length=500), nullable=True),
            sa.Column("property_id", sa.Integer(), sa.ForeignKey("re_properties.id"), nullable=False, index=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index(
            "uix_re_prop_extref",
            "re_property_external_refs",
            ["tenant_id", "provider", "external_id"],
            unique=True,
        )

    # 3) re_leads: campos de campanha
    leads_cols = _get_existing_columns("re_leads")
    with op.batch_alter_table("re_leads", schema=None) as batch_op:
        if "campaign_source" not in leads_cols:
            batch_op.add_column(sa.Column("campaign_source", sa.String(length=32), nullable=True))
        if "campaign_medium" not in leads_cols:
            batch_op.add_column(sa.Column("campaign_medium", sa.String(length=32), nullable=True))
        if "campaign_name" not in leads_cols:
            batch_op.add_column(sa.Column("campaign_name", sa.String(length=120), nullable=True))
        if "campaign_content" not in leads_cols:
            batch_op.add_column(sa.Column("campaign_content", sa.String(length=120), nullable=True))
        if "landing_url" not in leads_cols:
            batch_op.add_column(sa.Column("landing_url", sa.String(length=500), nullable=True))
        if "external_property_id" not in leads_cols:
            batch_op.add_column(sa.Column("external_property_id", sa.String(length=160), nullable=True))
    insp = sa.inspect(op.get_bind())
    existing_lead_idxs = {ix.get("name") for ix in insp.get_indexes("re_leads")}
    if "idx_re_leads_campaign_source" not in existing_lead_idxs:
        op.create_index("idx_re_leads_campaign_source", "re_leads", ["campaign_source"], unique=False)
    if "idx_re_leads_tenant_campaign_source" not in existing_lead_idxs:
        op.create_index("idx_re_leads_tenant_campaign_source", "re_leads", ["tenant_id", "campaign_source"], unique=False)


def downgrade() -> None:
    # 3) Remover índices e colunas de campanha
    op.drop_index("idx_re_leads_tenant_campaign_source", table_name="re_leads")
    op.drop_index("idx_re_leads_campaign_source", table_name="re_leads")
    with op.batch_alter_table("re_leads", schema=None) as batch_op:
        for col in [
            "external_property_id",
            "landing_url",
            "campaign_content",
            "campaign_name",
            "campaign_medium",
            "campaign_source",
        ]:
            try:
                batch_op.drop_column(col)
            except Exception:
                pass

    # 2) Dropar re_property_external_refs
    try:
        op.drop_index("uix_re_prop_extref", table_name="re_property_external_refs")
    except Exception:
        pass
    try:
        op.drop_table("re_property_external_refs")
    except Exception:
        pass

    # 1) Remover índice único e coluna ref_code de re_properties
    try:
        op.drop_index("uix_re_prop_tenant_refcode", table_name="re_properties")
    except Exception:
        pass
    try:
        with op.batch_alter_table("re_properties", schema=None) as batch_op:
            batch_op.drop_column("ref_code")
    except Exception:
        pass
