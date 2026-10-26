"""Add provider payment fields to recovery_cases.

Revision ID: 0003_provider_payment_fields
Revises: 0002_webhook_receipts
Create Date: 2026-09-05
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0003_provider_payment_fields"
down_revision: str | None = "0002_webhook_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add provider payment fields to recovery_cases
    op.add_column(
        "recovery_cases",
        sa.Column("razorpay_order_id", sa.String(128), nullable=True, unique=True),
    )
    op.add_column(
        "recovery_cases",
        sa.Column("razorpay_payment_id", sa.String(128), nullable=True, unique=True),
    )
    op.add_column(
        "recovery_cases",
        sa.Column("provider_payment_status", sa.String(50), nullable=True),
    )
    op.add_column(
        "recovery_cases",
        sa.Column("provider_payment_timestamp", sa.DateTime(timezone=True), nullable=True),
    )

    # Create indexes for the new unique fields
    op.create_index("ix_recovery_cases_razorpay_order_id", "recovery_cases", ["razorpay_order_id"])
    op.create_index(
        "ix_recovery_cases_razorpay_payment_id", "recovery_cases", ["razorpay_payment_id"]
    )


def downgrade() -> None:
    # Remove indexes
    op.drop_index("ix_recovery_cases_razorpay_payment_id", table_name="recovery_cases")
    op.drop_index("ix_recovery_cases_razorpay_order_id", table_name="recovery_cases")

    # Remove columns
    op.drop_column("recovery_cases", "provider_payment_timestamp")
    op.drop_column("recovery_cases", "provider_payment_status")
    op.drop_column("recovery_cases", "razorpay_payment_id")
    op.drop_column("recovery_cases", "razorpay_order_id")
