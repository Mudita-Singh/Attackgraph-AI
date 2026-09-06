"""Add is_critical column to nodes table

Revision ID: 0003_add_node_is_critical
Revises: 0002_add_edge_fields
Create Date: 2026-09-06
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0003_add_node_is_critical'
down_revision: Union[str, None] = '0002_add_edge_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('nodes', sa.Column('is_critical', sa.Boolean(), nullable=False, server_default='false'))

def downgrade() -> None:
    op.drop_column('nodes', 'is_critical')
