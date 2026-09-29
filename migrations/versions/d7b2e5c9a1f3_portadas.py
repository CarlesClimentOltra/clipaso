"""portadas de los clips (miniaturas 9:16 y 16:9)

Revision ID: d7b2e5c9a1f3
Revises: c4e7a9d2b8f1
Create Date: 2026-09-29 13:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'd7b2e5c9a1f3'
down_revision = 'c4e7a9d2b8f1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('clips', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cover', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('clips', schema=None) as batch_op:
        batch_op.drop_column('cover')
