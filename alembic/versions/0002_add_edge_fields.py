"""Add confidence, status, verification_outcome, reasoning, step to edges table

Revision ID: 0002_add_edge_fields
Revises: 0001_initial_schema
Create Date: 2026-09-06
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002_add_edge_fields'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('edges', sa.Column('confidence', sa.Float(), nullable=True))
    op.add_column('edges', sa.Column('status', sa.String(length=50), nullable=False, server_default='unverified'))
    op.add_column('edges', sa.Column('verification_outcome', sa.String(length=100), nullable=True))
    op.add_column('edges', sa.Column('reasoning', sa.Text(), nullable=True))
    op.add_column('edges', sa.Column('step', sa.Integer(), nullable=True))

def downgrade() -> None:
    op.drop_column('edges', 'step')
    op.drop_column('edges', 'reasoning')
    op.drop_column('edges', 'verification_outcome')
    op.drop_column('edges', 'status')
    op.drop_column('edges', 'confidence')
