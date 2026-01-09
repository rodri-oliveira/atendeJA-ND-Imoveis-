"""fix re_chatbot_flows missing columns

Revision ID: c3f1a2b4c5d6
Revises: 9c1d2e3f4a5b
Create Date: 2026-01-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3f1a2b4c5d6"
down_revision: Union[str, Sequence[str], None] = "9c1d2e3f4a5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(insp: sa.Inspector, table: str, col: str) -> bool:
    return any(c.get("name") == col for c in insp.get_columns(table))


def _has_index(insp: sa.Inspector, table: str, index_name: str) -> bool:
    return any(i.get("name") == index_name for i in insp.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "re_chatbot_flows" not in insp.get_table_names():
        return

    # Columns expected by the SQLAlchemy model
    if not _has_column(insp, "re_chatbot_flows", "domain"):
        op.add_column(
            "re_chatbot_flows",
            sa.Column("domain", sa.String(length=64), nullable=False, server_default="real_estate"),
        )

    if not _has_column(insp, "re_chatbot_flows", "flow_definition"):
        op.add_column("re_chatbot_flows", sa.Column("flow_definition", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))

    if not _has_column(insp, "re_chatbot_flows", "is_published"):
        op.add_column(
            "re_chatbot_flows",
            sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )

    if not _has_column(insp, "re_chatbot_flows", "published_version"):
        op.add_column(
            "re_chatbot_flows",
            sa.Column("published_version", sa.Integer(), nullable=False, server_default="0"),
        )

    if not _has_column(insp, "re_chatbot_flows", "published_at"):
        op.add_column("re_chatbot_flows", sa.Column("published_at", sa.DateTime(), nullable=True))

    if not _has_column(insp, "re_chatbot_flows", "published_by"):
        op.add_column("re_chatbot_flows", sa.Column("published_by", sa.String(length=180), nullable=True))

    if not _has_column(insp, "re_chatbot_flows", "created_at"):
        op.add_column(
            "re_chatbot_flows",
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if not _has_column(insp, "re_chatbot_flows", "updated_at"):
        op.add_column(
            "re_chatbot_flows",
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    # Index used by lookups for published flow
    if not _has_index(insp, "re_chatbot_flows", "idx_re_chatbot_flow_tenant_domain_published"):
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

    if _has_index(insp, "re_chatbot_flows", "idx_re_chatbot_flow_tenant_domain_published"):
        op.drop_index("idx_re_chatbot_flow_tenant_domain_published", table_name="re_chatbot_flows")

    # Downgrade is intentionally conservative: we avoid dropping columns to prevent data loss.
