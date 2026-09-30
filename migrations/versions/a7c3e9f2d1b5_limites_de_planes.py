"""límites nuevos de los planes: calidad máxima de descarga, miniaturas por día y sin límites (desarrollo)

Revision ID: a7c3e9f2d1b5
Revises: f5b8d2c4e6a1
Create Date: 2026-09-30 22:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'a7c3e9f2d1b5'
down_revision = 'f5b8d2c4e6a1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('plans', schema=None) as batch_op:
        batch_op.add_column(sa.Column('max_export_quality', sa.String(8), nullable=False, server_default='1080p'))
        batch_op.add_column(sa.Column('daily_thumbnails', sa.Integer(), nullable=False, server_default='10'))
        batch_op.add_column(sa.Column('unlimited', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table('plans', schema=None) as batch_op:
        batch_op.drop_column('unlimited')
        batch_op.drop_column('daily_thumbnails')
        batch_op.drop_column('max_export_quality')
