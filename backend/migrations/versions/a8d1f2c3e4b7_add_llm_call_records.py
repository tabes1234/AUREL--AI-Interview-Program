"""add llm_call_records table (T10 调用观测)

Revision ID: a8d1f2c3e4b7
Revises: 7c4f2a91d8e3
Create Date: 2026-10-12 04:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8d1f2c3e4b7'
down_revision: Union[str, Sequence[str], None] = '7c4f2a91d8e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('llm_call_records',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('service', sa.String(length=50), nullable=False),
    sa.Column('model', sa.String(length=120), nullable=False),
    sa.Column('prompt_version', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('latency_ms', sa.Integer(), nullable=False),
    sa.Column('experiment', sa.Boolean(), nullable=False),
    sa.Column('error_type', sa.String(length=80), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('usage', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_llm_call_records_service', 'llm_call_records', ['service'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_llm_call_records_service', table_name='llm_call_records')
    op.drop_table('llm_call_records')
