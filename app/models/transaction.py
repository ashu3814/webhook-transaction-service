from sqlalchemy import Column, String, Integer, DateTime, Enum
from app.database import Base
from app.enums.transaction import TransactionStatus, Currency
from app.utils.time import now_ist


class Transaction(Base):
    __tablename__ = "transactions"
    
    # The primary key already provides uniqueness and an index for task lookups.
    transaction_id = Column(String(50), primary_key=True)
    source_account = Column(String(100), nullable=False)
    destination_account = Column(String(100), nullable=False)
    amount = Column(Integer, nullable=False)
    currency = Column(Enum(Currency), nullable=False)
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PROCESSING, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_ist, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<Transaction(id={self.transaction_id}, status={self.status})>"