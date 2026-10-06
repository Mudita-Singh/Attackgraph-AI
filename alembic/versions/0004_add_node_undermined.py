"""Add undermined column to nodes table

Revision ID: 0004_add_node_undermined
Revises: 0003_add_node_is_critical
Create Date: 2026-09-26
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0004_add_node_undermined'
down_revision: Union[str, None] = '0003_add_node_is_critical'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('nodes', sa.Column('undermined', sa.Boolean(), nullable=False, server_default='false'))

def downgrade() -> None:
    op.drop_column('nodes', 'undermined')
