"""mensajes de contacto (dudas, sugerencias, errores) con su captura opcional

Revision ID: e3f7a1b4c6d9
Revises: d2e6f9a3b5c8
Create Date: 2026-10-02 20:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'e3f7a1b4c6d9'
down_revision = 'd2e6f9a3b5c8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'contact_messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(128), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('email', sa.String(320), nullable=False),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('context', sa.JSON(), nullable=False),
        sa.Column('attachment_key', sa.String(512), nullable=True),
        sa.Column('status', sa.String(16), nullable=False, server_default='new'),
        sa.Column('ip_hash', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_contact_messages_created_at', 'contact_messages', ['created_at'])
    op.create_index('ix_contact_messages_ip_hash', 'contact_messages', ['ip_hash'])
    op.create_index('ix_contact_messages_user_id', 'contact_messages', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_contact_messages_user_id', 'contact_messages')
    op.drop_index('ix_contact_messages_ip_hash', 'contact_messages')
    op.drop_index('ix_contact_messages_created_at', 'contact_messages')
    op.drop_table('contact_messages')
