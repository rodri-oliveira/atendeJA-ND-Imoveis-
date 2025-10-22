"""remove_unused_tables

Revision ID: 529d4d52fce0
Revises: b2c3d4e5f6a7
Create Date: 2025-10-22 10:40:39.691559

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '529d4d52fce0'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove tabelas não implementadas e não utilizadas."""
    # Remover tabelas de amenidades (não implementado)
    op.drop_table('re_property_amenities')
    op.drop_table('re_amenities')
    
    # Remover tabela de referências externas (não implementado)
    op.drop_table('re_property_external_refs')
    
    # Remover tabela de agendamento de visitas (não implementado)
    op.drop_table('re_visit_schedules')


def downgrade() -> None:
    """Recriar tabelas removidas (caso necessário reverter)."""
    # Recriar re_visit_schedules
    op.create_table(
        're_visit_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('property_id', sa.Integer(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['re_leads.id']),
        sa.ForeignKeyConstraint(['property_id'], ['re_properties.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Recriar re_property_external_refs
    op.create_table(
        're_property_external_refs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('property_id', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('external_id', sa.String(), nullable=True),
        sa.Column('url', sa.String(), nullable=True),
        sa.Column('synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['property_id'], ['re_properties.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Recriar re_amenities
    op.create_table(
        're_amenities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('icon', sa.String(), nullable=True),
        sa.Column('category', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Recriar re_property_amenities
    op.create_table(
        're_property_amenities',
        sa.Column('property_id', sa.Integer(), nullable=False),
        sa.Column('amenity_id', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['amenity_id'], ['re_amenities.id']),
        sa.ForeignKeyConstraint(['property_id'], ['re_properties.id']),
        sa.PrimaryKeyConstraint('property_id', 'amenity_id')
    )
