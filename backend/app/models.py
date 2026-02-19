from sqlalchemy import Column, BigInteger, DateTime, Float, String, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime, timezone


class Base(DeclarativeBase):
    pass


class Host(Base):
    __tablename__ = "hosts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    host_key = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    samples = relationship("MetricsSample", back_populates="host")


class MetricsSample(Base):
    __tablename__ = "metrics_samples"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    host_id = Column(BigInteger, ForeignKey("hosts.id"), nullable=True)  # nullable for V1 backward compat
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

    host = relationship("Host", back_populates="samples")

    __table_args__ = (
        Index("ix_metrics_samples_ts_utc", "ts_utc"),
        Index("ix_metrics_samples_host_ts", "host_id", "ts_utc"),
    )
