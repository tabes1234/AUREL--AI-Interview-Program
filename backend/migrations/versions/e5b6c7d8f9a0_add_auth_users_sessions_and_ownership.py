"""add auth users, email codes, sessions and data ownership (真实邮箱验证码认证)

Revision ID: e5b6c7d8f9a0
Revises: c9f3b7d2e6a5
Create Date: 2026-10-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5b6c7d8f9a0'
down_revision: Union[str, Sequence[str], None] = 'c9f3b7d2e6a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('nickname', sa.String(length=40), nullable=False),
        sa.Column('email_verified_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    op.create_table(
        'email_verification_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('purpose', sa.String(length=20), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_email_verification_codes_email', 'email_verification_codes', ['email'])

    op.create_table(
        'user_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_user_sessions_user_id', 'user_sessions', ['user_id'])
    op.create_index('ix_user_sessions_token_hash', 'user_sessions', ['token_hash'])

    # 业务数据归属用户（NULL = 历史遗留数据，登录用户不可见）
    op.add_column('interview_tasks', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_index('ix_interview_tasks_user_id', 'interview_tasks', ['user_id'])
    op.add_column('knowledge_documents', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_index('ix_knowledge_documents_user_id', 'knowledge_documents', ['user_id'])
    op.add_column('resume_match_records', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_index('ix_resume_match_records_user_id', 'resume_match_records', ['user_id'])
    op.add_column('expression_analyses', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_index('ix_expression_analyses_user_id', 'expression_analyses', ['user_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_expression_analyses_user_id', table_name='expression_analyses')
    op.drop_column('expression_analyses', 'user_id')
    op.drop_index('ix_resume_match_records_user_id', table_name='resume_match_records')
    op.drop_column('resume_match_records', 'user_id')
    op.drop_index('ix_knowledge_documents_user_id', table_name='knowledge_documents')
    op.drop_column('knowledge_documents', 'user_id')
    op.drop_index('ix_interview_tasks_user_id', table_name='interview_tasks')
    op.drop_column('interview_tasks', 'user_id')
    op.drop_index('ix_user_sessions_token_hash', table_name='user_sessions')
    op.drop_index('ix_user_sessions_user_id', table_name='user_sessions')
    op.drop_table('user_sessions')
    op.drop_index('ix_email_verification_codes_email', table_name='email_verification_codes')
    op.drop_table('email_verification_codes')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
