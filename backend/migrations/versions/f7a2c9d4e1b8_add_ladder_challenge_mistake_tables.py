"""add challenge runs and mistake cards (度衡/回澜)

Revision ID: f7a2c9d4e1b8
Revises: e5b6c7d8f9a0
Create Date: 2026-10-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7a2c9d4e1b8'
down_revision: Union[str, Sequence[str], None] = 'e5b6c7d8f9a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'challenge_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(),
                  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('position', sa.String(length=120), nullable=False),
        sa.Column('difficulty', sa.String(length=20), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('question_count', sa.Integer(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('questions', sa.JSON(), nullable=False),
        sa.Column('answers', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('deadline_at', sa.DateTime(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('overtime', sa.Boolean(), nullable=False),
        sa.Column('overall_score', sa.Float(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('model_name', sa.String(length=120), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_challenge_runs_user_id', 'challenge_runs', ['user_id'])

    op.create_table(
        'mistake_cards',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(),
                  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('question_id', sa.Integer(),
                  sa.ForeignKey('interview_questions.id'), nullable=False),
        sa.Column('position', sa.String(length=120), nullable=False),
        sa.Column('question_content', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=30), nullable=True),
        sa.Column('dimension', sa.String(length=60), nullable=True),
        sa.Column('goal', sa.Text(), nullable=True),
        sa.Column('rubric', sa.JSON(), nullable=True),
        sa.Column('my_answer', sa.Text(), nullable=False),
        sa.Column('repetitions', sa.Integer(), nullable=False),
        sa.Column('ease_factor', sa.Float(), nullable=False),
        sa.Column('interval_days', sa.Integer(), nullable=False),
        sa.Column('due_at', sa.DateTime(), nullable=False),
        sa.Column('last_grade', sa.Integer(), nullable=True),
        sa.Column('last_reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('review_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_mistake_cards_user_id', 'mistake_cards', ['user_id'])
    op.create_index('ix_mistake_cards_question_id', 'mistake_cards', ['question_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_mistake_cards_question_id', table_name='mistake_cards')
    op.drop_index('ix_mistake_cards_user_id', table_name='mistake_cards')
    op.drop_table('mistake_cards')
    op.drop_index('ix_challenge_runs_user_id', table_name='challenge_runs')
    op.drop_table('challenge_runs')
