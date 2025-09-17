"""mensageria: logs de envio e lista de supressão

Revision ID: 7f2d3a1c9b2a
Revises: 46ca38c65133
Create Date: 2025-09-16 19:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "7f2d3a1c9b2a"
down_revision: Union[str, Sequence[str], None] = "46ca38c65133"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "suppressed_contacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("wa_id", sa.String(length=32), nullable=False, index=True),
        sa.Column("reason", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("uix_suppressed_tenant_wa", "suppressed_contacts", ["tenant_id", "wa_id"], unique=True)

    op.create_table(
        "message_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("to", sa.String(length=32), nullable=False, index=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("body", sa.JSON(), nullable=True),
        sa.Column("template_name", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("provider_message_id", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_msglog_tenant_to", "message_logs", ["tenant_id", "to"], unique=False)
    op.create_index("idx_msglog_created", "message_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_msglog_created", table_name="message_logs")
    op.drop_index("idx_msglog_tenant_to", table_name="message_logs")
    op.drop_table("message_logs")

    op.drop_index("uix_suppressed_tenant_wa", table_name="suppressed_contacts")
    op.drop_table("suppressed_contacts")
