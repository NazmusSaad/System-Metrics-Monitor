from sqlalchemy import Column, BigInteger, DateTime, Float, Index
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone


class Base(DeclarativeBase):
    pass


class MetricsSample(Base):
    __tablename__ = "metrics_samples"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts_utc = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    cpu_percent = Column(Float, nullable=False)
    load_avg_1 = Column(Float, nullable=True)  # None on Windows
    mem_used_bytes = Column(Float, nullable=False)
    mem_total_bytes = Column(Float, nullable=False)
    mem_percent = Column(Float, nullable=False)
    disk_used_bytes = Column(Float, nullable=False)
    disk_total_bytes = Column(Float, nullable=False)
    disk_percent = Column(Float, nullable=False)
    net_rx_bps = Column(Float, nullable=False, default=0)
    net_tx_bps = Column(Float, nullable=False, default=0)
    uptime_seconds = Column(Float, nullable=True)

    __table_args__ = (
        Index("ix_metrics_samples_ts_utc", "ts_utc"),
    )
