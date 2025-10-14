"""re_leads: status, timestamps, filtros e integrações

Revision ID: a1e2b3c4d5e6
Revises: 7f2d3a1c9b2a
Create Date: 2025-10-13 23:52:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1e2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "7f2d3a1c9b2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # Usar PRAGMA para detectar colunas no SQLite de forma confiável
    try:
        rows = bind.exec_driver_sql("PRAGMA table_info('re_leads')").fetchall()
        existing_cols = {row[1] for row in rows}  # (cid, name, type, notnull, dflt_value, pk)
    except Exception:
        # Fallback para outros dialetos
        insp = sa.inspect(bind)
        existing_cols = {c["name"] for c in insp.get_columns("re_leads")}

    # 1) Adicionar colunas (sem FKs/índices)
    with op.batch_alter_table("re_leads", schema=None) as batch_op:
        if "status" not in existing_cols:
            batch_op.add_column(sa.Column("status", sa.String(length=32), nullable=False, server_default="novo"))
        if "last_inbound_at" not in existing_cols:
            batch_op.add_column(sa.Column("last_inbound_at", sa.DateTime(), nullable=True))
        if "last_outbound_at" not in existing_cols:
            batch_op.add_column(sa.Column("last_outbound_at", sa.DateTime(), nullable=True))
        if "status_updated_at" not in existing_cols:
            batch_op.add_column(sa.Column("status_updated_at", sa.DateTime(), nullable=True))

        if "property_interest_id" not in existing_cols:
            batch_op.add_column(sa.Column("property_interest_id", sa.Integer(), nullable=True))
        if "contact_id" not in existing_cols:
            batch_op.add_column(sa.Column("contact_id", sa.Integer(), nullable=True))

        if "finalidade" not in existing_cols:
            batch_op.add_column(sa.Column("finalidade", sa.String(length=16), nullable=True))
        if "tipo" not in existing_cols:
            batch_op.add_column(sa.Column("tipo", sa.String(length=32), nullable=True))
        if "cidade" not in existing_cols:
            batch_op.add_column(sa.Column("cidade", sa.String(length=120), nullable=True))
        if "estado" not in existing_cols:
            batch_op.add_column(sa.Column("estado", sa.String(length=2), nullable=True))
        if "bairro" not in existing_cols:
            batch_op.add_column(sa.Column("bairro", sa.String(length=120), nullable=True))
        if "dormitorios" not in existing_cols:
            batch_op.add_column(sa.Column("dormitorios", sa.Integer(), nullable=True))
        if "preco_min" not in existing_cols:
            batch_op.add_column(sa.Column("preco_min", sa.Float(), nullable=True))
        if "preco_max" not in existing_cols:
            batch_op.add_column(sa.Column("preco_max", sa.Float(), nullable=True))

    # Recarregar metadados após recriação
    insp = sa.inspect(op.get_bind())
    existing_fks = {fk.get("name") for fk in insp.get_foreign_keys("re_leads")}
    existing_idxs = {ix.get("name") for ix in insp.get_indexes("re_leads")}

    # 2) Criar FKs em batch separado (evita reordenação circular)
    with op.batch_alter_table("re_leads", schema=None) as batch_op:
        if "fk_re_leads_property_interest" not in existing_fks:
            batch_op.create_foreign_key(
                "fk_re_leads_property_interest",
                "re_properties",
                ["property_interest_id"],
                ["id"],
            )
        if "fk_re_leads_contact" not in existing_fks:
            batch_op.create_foreign_key(
                "fk_re_leads_contact",
                "contacts",
                ["contact_id"],
                ["id"],
            )

    # 3) Criar índices fora do batch (CREATE INDEX é suportado)
    if "idx_re_leads_tenant_status" not in existing_idxs:
        op.create_index("idx_re_leads_tenant_status", "re_leads", ["tenant_id", "status"], unique=False)
    if "idx_re_leads_city" not in existing_idxs:
        op.create_index("idx_re_leads_city", "re_leads", ["cidade"], unique=False)
    if "idx_re_leads_state" not in existing_idxs:
        op.create_index("idx_re_leads_state", "re_leads", ["estado"], unique=False)
    if "idx_re_leads_bairro" not in existing_idxs:
        op.create_index("idx_re_leads_bairro", "re_leads", ["bairro"], unique=False)
    if "idx_re_leads_purpose_type" not in existing_idxs:
        op.create_index("idx_re_leads_purpose_type", "re_leads", ["finalidade", "tipo"], unique=False)
    if "idx_re_leads_dormitorios" not in existing_idxs:
        op.create_index("idx_re_leads_dormitorios", "re_leads", ["dormitorios"], unique=False)
    if "idx_re_leads_preco_min" not in existing_idxs:
        op.create_index("idx_re_leads_preco_min", "re_leads", ["preco_min"], unique=False)
    if "idx_re_leads_preco_max" not in existing_idxs:
        op.create_index("idx_re_leads_preco_max", "re_leads", ["preco_max"], unique=False)
    if "idx_re_leads_property_interest" not in existing_idxs:
        op.create_index("idx_re_leads_property_interest", "re_leads", ["property_interest_id"], unique=False)


def downgrade() -> None:
    # 1) Dropar índices
    op.drop_index("idx_re_leads_property_interest", table_name="re_leads")
    op.drop_index("idx_re_leads_preco_max", table_name="re_leads")
    op.drop_index("idx_re_leads_preco_min", table_name="re_leads")
    op.drop_index("idx_re_leads_dormitorios", table_name="re_leads")
    op.drop_index("idx_re_leads_purpose_type", table_name="re_leads")
    op.drop_index("idx_re_leads_bairro", table_name="re_leads")
    op.drop_index("idx_re_leads_state", table_name="re_leads")
    op.drop_index("idx_re_leads_city", table_name="re_leads")
    op.drop_index("idx_re_leads_tenant_status", table_name="re_leads")

    # 2) Dropar FKs
    with op.batch_alter_table("re_leads", schema=None) as batch_op:
        batch_op.drop_constraint("fk_re_leads_contact", type_="foreignkey")
        batch_op.drop_constraint("fk_re_leads_property_interest", type_="foreignkey")

    # 3) Remover colunas
    with op.batch_alter_table("re_leads", schema=None) as batch_op:
        batch_op.drop_column("contact_id")
        batch_op.drop_column("property_interest_id")
        batch_op.drop_column("preco_max")
        batch_op.drop_column("preco_min")
        batch_op.drop_column("dormitorios")
        batch_op.drop_column("bairro")
        batch_op.drop_column("estado")
        batch_op.drop_column("cidade")
        batch_op.drop_column("tipo")
        batch_op.drop_column("finalidade")
        batch_op.drop_column("status_updated_at")
        batch_op.drop_column("last_outbound_at")
        batch_op.drop_column("last_inbound_at")
        batch_op.drop_column("status")
