"""cobros con Paddle: precio anual de cada plan y suscripción de cada usuario

Revision ID: c1d5e8a2f4b7
Revises: b9d4f1a6c3e8
Create Date: 2026-10-02 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'c1d5e8a2f4b7'
down_revision = 'b9d4f1a6c3e8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('plans', schema=None) as batch_op:
        batch_op.add_column(sa.Column('price_eur_cents_yearly', sa.Integer(), nullable=False, server_default='0'))
        batch_op.drop_column('stripe_price_id')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('stripe_customer_id')
        batch_op.add_column(sa.Column('billing_customer_id', sa.String(64), nullable=True))
        batch_op.add_column(sa.Column('billing_subscription_id', sa.String(64), nullable=True))
        batch_op.add_column(sa.Column('billing_status', sa.String(32), nullable=True))
        batch_op.add_column(sa.Column('billing_interval', sa.String(8), nullable=True))
        batch_op.add_column(sa.Column('billing_renews_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('billing_cancels_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('billing_event_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index('ix_users_billing_customer_id', ['billing_customer_id'])
        batch_op.create_index('ix_users_billing_subscription_id', ['billing_subscription_id'])


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index('ix_users_billing_subscription_id')
        batch_op.drop_index('ix_users_billing_customer_id')
        for col in ('billing_event_at', 'billing_cancels_at', 'billing_renews_at', 'billing_interval', 'billing_status',
                    'billing_subscription_id', 'billing_customer_id'):
            batch_op.drop_column(col)
        batch_op.add_column(sa.Column('stripe_customer_id', sa.String(128), nullable=True))
    with op.batch_alter_table('plans', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stripe_price_id', sa.String(128), nullable=True))
        batch_op.drop_column('price_eur_cents_yearly')
