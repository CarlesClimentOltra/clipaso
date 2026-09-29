"""envío a worker remoto

Revision ID: 5c2d8e1f0a7b
Revises: 3f693a7c9801
Create Date: 2026-09-27 21:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

import clipaso.saas.models

revision = '5c2d8e1f0a7b'
down_revision = '3f693a7c9801'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dispatched_at', clipaso.saas.models.UTCDateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_column('dispatched_at')
