"""add expression_analyses table

Revision ID: 7c4f2a91d8e3
Revises: 6b9e946e385c
Create Date: 2026-10-11 06:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c4f2a91d8e3'
down_revision: Union[str, Sequence[str], None] = '6b9e946e385c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('expression_analyses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('filename', sa.String(length=300), nullable=True),
    sa.Column('transcript', sa.Text(), nullable=True),
    sa.Column('asr_status', sa.String(length=30), nullable=False),
    sa.Column('asr_provider', sa.String(length=50), nullable=True),
    sa.Column('asr_error', sa.Text(), nullable=True),
    sa.Column('audio_duration_ms', sa.Integer(), nullable=True),
    sa.Column('metrics', sa.JSON(), nullable=False),
    sa.Column('workflow', sa.JSON(), nullable=True),
    sa.Column('model_name', sa.String(length=120), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('expression_analyses')
