"""Update pattern_stats table and add evidence_only_confidence to edges

Revision ID: 0005_pattern_stats
Revises: 0004_add_node_undermined
Create Date: 2026-10-06
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0005_pattern_stats'
down_revision: Union[str, None] = '0004_add_node_undermined'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Add evidence_only_confidence column to edges
    op.add_column('edges', sa.Column('evidence_only_confidence', sa.Float(), nullable=True))
    
    # 2. Recreate pattern_stats table with Section 34 schema
    # Drop index and table if existing
    op.execute("DROP TABLE IF EXISTS pattern_stats CASCADE;")
    
    op.create_table(
        'pattern_stats',
        sa.Column('pattern_key', sa.String(length=255), nullable=False),
        sa.Column('times_verified', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('times_refuted', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('pattern_key')
    )

def downgrade() -> None:
    op.drop_table('pattern_stats')
    op.drop_column('edges', 'evidence_only_confidence')
