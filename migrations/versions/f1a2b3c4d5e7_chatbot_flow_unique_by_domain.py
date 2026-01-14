"""chatbot flow unique by domain

Revision ID: f1a2b3c4d5e7
Revises: c3f1a2b4c5d6
Create Date: 2026-01-09

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e7"
down_revision: Union[str, Sequence[str], None] = "c3f1a2b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_unique_constraint(insp: sa.Inspector, table: str, name: str) -> bool:
    return any(c.get("name") == name for c in insp.get_unique_constraints(table))


def _has_index(insp: sa.Inspector, table: str, name: str) -> bool:
    return any(i.get("name") == name for i in insp.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "re_chatbot_flows" not in insp.get_table_names():
        return

    # Old: (tenant_id, name)
    old_name = "uix_re_chatbot_flow_tenant_name"
    # New: (tenant_id, domain, name)
    new_name = "uix_re_chatbot_flow_tenant_domain_name"

    # For SQLite tests, migrations are usually not applied; keep migration resilient anyway.
    dialect = bind.dialect.name

    if _has_unique_constraint(insp, "re_chatbot_flows", old_name):
        if dialect != "sqlite":
            op.drop_constraint(old_name, "re_chatbot_flows", type_="unique")
        # On SQLite, dropping constraints is limited; we skip to avoid breaking migration runs.

    if _has_index(insp, "re_chatbot_flows", old_name):
        op.drop_index(old_name, table_name="re_chatbot_flows")

    # Create new unique constraint/index if missing
    if not _has_unique_constraint(insp, "re_chatbot_flows", new_name) and not _has_index(insp, "re_chatbot_flows", new_name):
        if dialect != "sqlite":
            op.create_unique_constraint(new_name, "re_chatbot_flows", ["tenant_id", "domain", "name"])
        else:
            op.create_index(new_name, "re_chatbot_flows", ["tenant_id", "domain", "name"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "re_chatbot_flows" not in insp.get_table_names():
        return

    old_name = "uix_re_chatbot_flow_tenant_name"
    new_name = "uix_re_chatbot_flow_tenant_domain_name"

    dialect = bind.dialect.name

    if _has_unique_constraint(insp, "re_chatbot_flows", new_name):
        if dialect != "sqlite":
            op.drop_constraint(new_name, "re_chatbot_flows", type_="unique")

    if _has_index(insp, "re_chatbot_flows", new_name):
        op.drop_index(new_name, table_name="re_chatbot_flows")

    if not _has_unique_constraint(insp, "re_chatbot_flows", old_name) and not _has_index(insp, "re_chatbot_flows", old_name):
        if dialect != "sqlite":
            op.create_unique_constraint(old_name, "re_chatbot_flows", ["tenant_id", "name"])
        else:
            op.create_index(old_name, "re_chatbot_flows", ["tenant_id", "name"], unique=True)
