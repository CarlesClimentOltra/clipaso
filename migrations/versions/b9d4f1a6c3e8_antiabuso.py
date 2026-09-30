"""protección contra abusos: límites diarios por plan y red de alta de cada cuenta

Revision ID: b9d4f1a6c3e8
Revises: a7c3e9f2d1b5
Create Date: 2026-10-01 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'b9d4f1a6c3e8'
down_revision = 'a7c3e9f2d1b5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('plans', schema=None) as batch_op:
        batch_op.add_column(sa.Column('daily_renders', sa.Integer(), nullable=False, server_default='10'))
        batch_op.add_column(sa.Column('daily_more_clips', sa.Integer(), nullable=False, server_default='2'))
        batch_op.add_column(sa.Column('daily_exports', sa.Integer(), nullable=False, server_default='5'))
        batch_op.add_column(sa.Column('daily_covers', sa.Integer(), nullable=False, server_default='5'))
    with op.batch_alter_table('users', schema=None) as batch_op:
        # Huella (HMAC) de la IP desde la que se creó la cuenta: nunca la IP en claro.
        batch_op.add_column(sa.Column('signup_ip', sa.String(64), nullable=True))
        batch_op.create_index('ix_users_signup_ip', ['signup_ip'])


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index('ix_users_signup_ip')
        batch_op.drop_column('signup_ip')
    with op.batch_alter_table('plans', schema=None) as batch_op:
        batch_op.drop_column('daily_covers')
        batch_op.drop_column('daily_exports')
        batch_op.drop_column('daily_more_clips')
        batch_op.drop_column('daily_renders')
