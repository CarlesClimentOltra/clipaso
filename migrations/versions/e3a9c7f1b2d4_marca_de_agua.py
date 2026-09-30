"""marca de agua de Clipaso según el plan

Revision ID: e3a9c7f1b2d4
Revises: d7b2e5c9a1f3
Create Date: 2026-09-30 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'e3a9c7f1b2d4'
down_revision = 'd7b2e5c9a1f3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('plans', schema=None) as batch_op:
        batch_op.add_column(sa.Column('watermark', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table('plans', schema=None) as batch_op:
        batch_op.drop_column('watermark')
