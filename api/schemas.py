from pydantic import BaseModel, Field, field_validator
from datetime import datetime, date
from typing import Optional, List
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# ─── Orders ─────────────────────────────────────────────────────────────────


class OrderCreate(BaseModel):
    patient_first_name: str = Field(..., min_length=1, max_length=100)
    patient_last_name: str = Field(..., min_length=1, max_length=100)
    patient_dob: date
    status: OrderStatus = OrderStatus.PENDING
    notes: Optional[str] = Field(None, max_length=2000)
    created_by: Optional[str] = Field(None, max_length=100)


class OrderUpdate(BaseModel):
    patient_first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    patient_last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    patient_dob: Optional[date] = None
    status: Optional[OrderStatus] = None
    notes: Optional[str] = Field(None, max_length=2000)


class OrderResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    patient_first_name: str
    patient_last_name: str
    patient_dob: date
    status: OrderStatus
    notes: Optional[str]
    document_filename: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime


class OrderListResponse(BaseModel):
    items: List[OrderResponse]
    total: int
    page: int
    per_page: int
    pages: int


# ─── Upload / Extraction ────────────────────────────────────────────────────


class ExtractedPatientInfo(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class UploadResponse(BaseModel):
    extracted_info: ExtractedPatientInfo
    order: OrderResponse
    message: str


# ─── Activity Logs ──────────────────────────────────────────────────────────


class ActivityLogResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    ip_address: Optional[str]
    request_path: str
    request_method: str
    status_code: Optional[int]
    duration_ms: Optional[float]
    extra_data: Optional[dict]
    timestamp: datetime


class ActivityLogListResponse(BaseModel):
    items: List[ActivityLogResponse]
    total: int
    page: int
    per_page: int
    pages: int


# ─── Stats ──────────────────────────────────────────────────────────────────


class OrderStats(BaseModel):
    total: int
    pending: int
    processing: int
    completed: int
    cancelled: int
