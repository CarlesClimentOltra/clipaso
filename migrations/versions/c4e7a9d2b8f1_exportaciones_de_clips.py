"""exportaciones de clips (otras calidades y MP3)

Revision ID: c4e7a9d2b8f1
Revises: 8d4f2a6b1c3e
Create Date: 2026-09-28 22:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'c4e7a9d2b8f1'
down_revision = '8d4f2a6b1c3e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('clips', schema=None) as batch_op:
        batch_op.add_column(sa.Column('exports', sa.JSON(), nullable=False, server_default='{}'))


def downgrade() -> None:
    with op.batch_alter_table('clips', schema=None) as batch_op:
        batch_op.drop_column('exports')
