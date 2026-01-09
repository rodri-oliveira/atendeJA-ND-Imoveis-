"""add re_chatbot_flows

Revision ID: 9c1d2e3f4a5b
Revises: 878dda9ee4a9
Create Date: 2026-01-05

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c1d2e3f4a5b"
down_revision: Union[str, Sequence[str], None] = "878dda9ee4a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "re_chatbot_flows" in insp.get_table_names():
        return

    op.create_table(
        "re_chatbot_flows",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("domain", sa.String(length=64), nullable=False, server_default="real_estate", index=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("flow_definition", sa.JSON(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false"), index=True),
        sa.Column("published_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("published_by", sa.String(length=180), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("tenant_id", "name", name="uix_re_chatbot_flow_tenant_name"),
    )

    op.create_index(
        "idx_re_chatbot_flow_tenant_domain_published",
        "re_chatbot_flows",
        ["tenant_id", "domain", "is_published"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "re_chatbot_flows" not in insp.get_table_names():
        return

    op.drop_index("idx_re_chatbot_flow_tenant_domain_published", table_name="re_chatbot_flows")
    op.drop_table("re_chatbot_flows")
