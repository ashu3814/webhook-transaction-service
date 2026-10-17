from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.transaction import Transaction
from app.enums.transaction import TransactionStatus
from app.utils.time import now_ist


class TransactionRepository:
    
    @staticmethod
    def create(db: Session, transaction_id: str, source_account: str, 
               destination_account: str, amount: int, currency: str) -> bool:
        db_transaction = Transaction(
            transaction_id=transaction_id,
            source_account=source_account,
            destination_account=destination_account,
            amount=amount,
            currency=currency,
            status=TransactionStatus.PROCESSING
        )
        db.add(db_transaction)
        try:
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            # Treat only a transaction-ID collision as an idempotent duplicate.
            if TransactionRepository.exists(db, transaction_id):
                return False
            raise
    
    @staticmethod
    def get_by_id(db: Session, transaction_id: str) -> Transaction:
        return db.query(Transaction).filter(
            Transaction.transaction_id == transaction_id
        ).first()
    
    @staticmethod
    def update_status(db: Session, transaction_id: str, status: TransactionStatus) -> bool:
        # Update by primary key in one statement instead of SELECT, UPDATE, and refresh.
        values = {Transaction.status: status}
        if status == TransactionStatus.PROCESSED:
            values[Transaction.processed_at] = now_ist()

        result = db.execute(
            update(Transaction)
            .where(Transaction.transaction_id == transaction_id)
            .values(values)
        )
        db.commit()
        return result.rowcount > 0
    
    @staticmethod
    def exists(db: Session, transaction_id: str) -> bool:
        return db.query(Transaction).filter(
            Transaction.transaction_id == transaction_id
        ).first() is not None