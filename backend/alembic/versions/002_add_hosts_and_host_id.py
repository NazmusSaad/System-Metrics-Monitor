"""v2 add hosts table and host_id to metrics_samples

Revision ID: 002
Revises: 001
Create Date: 2025-01-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create hosts table
    op.create_table(
        "hosts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("host_key", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("host_key"),
    )
    op.create_index("ix_hosts_host_key", "hosts", ["host_key"])

    # Add host_id column to metrics_samples (nullable for backward compat with existing data)
    op.add_column("metrics_samples", sa.Column("host_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_metrics_samples_host_id", "metrics_samples", "hosts", ["host_id"], ["id"])
    op.create_index("ix_metrics_samples_host_ts", "metrics_samples", ["host_id", "ts_utc"])


def downgrade() -> None:
    op.drop_index("ix_metrics_samples_host_ts", table_name="metrics_samples")
    op.drop_constraint("fk_metrics_samples_host_id", "metrics_samples", type_="foreignkey")
    op.drop_column("metrics_samples", "host_id")
    op.drop_index("ix_hosts_host_key", table_name="hosts")
    op.drop_table("hosts")
