import uuid
import enum
from datetime import datetime, date

from sqlalchemy import String, DateTime, Date, Text, JSON, Float, Integer, Enum, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    patient_first_name: Mapped[str] = mapped_column(String(100))
    patient_last_name: Mapped[str] = mapped_column(String(100))
    patient_dob: Mapped[date] = mapped_column(Date)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, values_callable=lambda e: [m.value for m in e]),
        default=OrderStatus.PENDING,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    action: Mapped[str] = mapped_column(String(150))
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    request_path: Mapped[str] = mapped_column(String(512))
    request_method: Mapped[str] = mapped_column(String(10))
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
