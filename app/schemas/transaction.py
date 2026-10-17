from pydantic import BaseModel, Field, field_serializer
from datetime import datetime
from typing import Optional
from app.enums.transaction import TransactionStatus, Currency
from app.utils.time import to_ist


class TransactionCreate(BaseModel):
    transaction_id: str = Field(..., min_length=1, max_length=50)
    source_account: str = Field(..., min_length=1, max_length=100)
    destination_account: str = Field(..., min_length=1, max_length=100)
    amount: int = Field(..., gt=0)
    currency: Currency


class TransactionResponse(BaseModel):
    transaction_id: str
    source_account: str
    destination_account: str
    amount: int
    currency: Currency
    status: TransactionStatus
    created_at: datetime
    processed_at: Optional[datetime] = None

    @field_serializer("created_at", "processed_at")
    def serialize_timestamps(self, value: Optional[datetime]) -> Optional[datetime]:
        return to_ist(value) if value is not None else None
    
    class Config:
        from_attributes = True


class WebhookResponse(BaseModel):
    status: str


class HealthResponse(BaseModel):
    status: str
    current_time: str