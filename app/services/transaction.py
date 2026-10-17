from sqlalchemy.orm import Session
from app.repositories.transaction import TransactionRepository
from app.enums.transaction import TransactionStatus
from app.schemas.transaction import TransactionCreate


class TransactionService:
    
    @staticmethod
    def receive_webhook(db: Session, transaction_data: TransactionCreate) -> bool:
        txn_id = transaction_data.transaction_id

        return TransactionRepository.create(
            db=db,
            transaction_id=txn_id,
            source_account=transaction_data.source_account,
            destination_account=transaction_data.destination_account,
            amount=transaction_data.amount,
            currency=transaction_data.currency.value
        )
    
    @staticmethod
    def get_transaction(db: Session, transaction_id: str):
        return TransactionRepository.get_by_id(db, transaction_id)
    
    @staticmethod
    def mark_as_processed(db: Session, transaction_id: str):
        return TransactionRepository.update_status(db, transaction_id, TransactionStatus.PROCESSED)