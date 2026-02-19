"""create metrics_samples table

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "metrics_samples",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ts_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cpu_percent", sa.Float(), nullable=False),
        sa.Column("load_avg_1", sa.Float(), nullable=True),
        sa.Column("mem_used_bytes", sa.Float(), nullable=False),
        sa.Column("mem_total_bytes", sa.Float(), nullable=False),
        sa.Column("mem_percent", sa.Float(), nullable=False),
        sa.Column("disk_used_bytes", sa.Float(), nullable=False),
        sa.Column("disk_total_bytes", sa.Float(), nullable=False),
        sa.Column("disk_percent", sa.Float(), nullable=False),
        sa.Column("net_rx_bps", sa.Float(), nullable=False, server_default="0"),
        sa.Column("net_tx_bps", sa.Float(), nullable=False, server_default="0"),
        sa.Column("uptime_seconds", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_metrics_samples_ts_utc", "metrics_samples", ["ts_utc"])


def downgrade() -> None:
    op.drop_index("ix_metrics_samples_ts_utc", table_name="metrics_samples")
    op.drop_table("metrics_samples")
