"""chatbot flows: archive fields

Revision ID: f1a2b3c4d5e8
Revises: f1a2b3c4d5e7
Create Date: 2026-01-09

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e8"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(insp: sa.Inspector, table: str, col: str) -> bool:
    return any(c.get("name") == col for c in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "re_chatbot_flows" not in insp.get_table_names():
        return

    if not _has_column(insp, "re_chatbot_flows", "is_archived"):
        op.add_column(
            "re_chatbot_flows",
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )

    if not _has_column(insp, "re_chatbot_flows", "archived_at"):
        op.add_column(
            "re_chatbot_flows",
            sa.Column("archived_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "re_chatbot_flows" not in insp.get_table_names():
        return

    # Downgrade conservador: evita drop em produção para não perder dados.
