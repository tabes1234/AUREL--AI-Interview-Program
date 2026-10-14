"""add catalog context and question meta (问澜行业职业题集)

Revision ID: c9f3b7d2e6a5
Revises: a8d1f2c3e4b7
Create Date: 2026-10-12 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9f3b7d2e6a5'
down_revision: Union[str, Sequence[str], None] = 'a8d1f2c3e4b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('interview_tasks', sa.Column('industry_id', sa.String(length=60), nullable=True))
    op.add_column('interview_tasks', sa.Column('occupation_id', sa.String(length=60), nullable=True))
    op.add_column('interview_tasks', sa.Column('experience_level', sa.String(length=30), nullable=True))
    op.add_column('interview_tasks', sa.Column('interview_type', sa.String(length=30), nullable=True))
    op.add_column('interview_tasks', sa.Column('focus_areas', sa.JSON(), nullable=True))
    op.add_column('interview_questions', sa.Column('category', sa.String(length=30), nullable=True))
    op.add_column('interview_questions', sa.Column('dimension', sa.String(length=60), nullable=True))
    op.add_column('interview_questions', sa.Column('goal', sa.Text(), nullable=True))
    op.add_column('interview_questions', sa.Column('rubric', sa.JSON(), nullable=True))
    op.add_column('interview_questions', sa.Column('suggested_follow_up', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('interview_questions', 'suggested_follow_up')
    op.drop_column('interview_questions', 'rubric')
    op.drop_column('interview_questions', 'goal')
    op.drop_column('interview_questions', 'dimension')
    op.drop_column('interview_questions', 'category')
    op.drop_column('interview_tasks', 'focus_areas')
    op.drop_column('interview_tasks', 'interview_type')
    op.drop_column('interview_tasks', 'experience_level')
    op.drop_column('interview_tasks', 'occupation_id')
    op.drop_column('interview_tasks', 'industry_id')
