"""add user tenant and invites

Revision ID: d7c1f4f9e2a0
Revises: b2c3d4e5f6a7
Create Date: 2026-01-02 22:22:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "d7c1f4f9e2a0"
down_revision = "529d4d52fce0"
branch_labels = None
depends_on = None


user_role_enum = postgresql.ENUM("admin", "collaborator", name="userrole", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # users.tenant_id
    user_cols = {c["name"] for c in insp.get_columns("users")}
    if "tenant_id" not in user_cols:
        op.add_column("users", sa.Column("tenant_id", sa.Integer(), nullable=True))

    user_indexes = {ix["name"] for ix in insp.get_indexes("users")}
    if "ix_users_tenant_id" not in user_indexes:
        op.create_index("ix_users_tenant_id", "users", ["tenant_id"], unique=False)

    user_fks = {fk["name"] for fk in insp.get_foreign_keys("users") if fk.get("name")}
    if "fk_users_tenant" not in user_fks:
        op.create_foreign_key(
            "fk_users_tenant",
            "users",
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # user_invites table
    if not insp.has_table("user_invites"):
        op.create_table(
            "user_invites",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(length=180), nullable=False),
            sa.Column("role", user_role_enum, nullable=False, server_default="collaborator"),
            sa.Column("token", sa.String(length=255), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.Index("idx_invite_tenant_email", "tenant_id", "email"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("user_invites"):
        op.drop_table("user_invites")

    user_fks = {fk["name"] for fk in insp.get_foreign_keys("users") if fk.get("name")}
    if "fk_users_tenant" in user_fks:
        op.drop_constraint("fk_users_tenant", "users", type_="foreignkey")

    user_indexes = {ix["name"] for ix in insp.get_indexes("users")}
    if "ix_users_tenant_id" in user_indexes:
        op.drop_index("ix_users_tenant_id", table_name="users")

    user_cols = {c["name"] for c in insp.get_columns("users")}
    if "tenant_id" in user_cols:
        op.drop_column("users", "tenant_id")
