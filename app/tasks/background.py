import time
from sqlalchemy.orm import Session
from app.tasks.celery_app import celery_app
from app.database import SessionLocal
from app.services.transaction import TransactionService
from app.utils.logger import logger


@celery_app.task(bind=True, name="process_transaction")
def process_transaction_task(self, transaction_id: str):
    db: Session | None = None
    logger.info("Transaction task received transaction_id=%s", transaction_id)

    try:
        # This is the only intentional processing delay.
        time.sleep(30)

        # Open the database session only when the transaction is ready to update.
        db = SessionLocal()
        TransactionService.mark_as_processed(db, transaction_id)

        logger.info("Transaction task succeeded transaction_id=%s", transaction_id)
        return {"status": "processed", "transaction_id": transaction_id}

    except Exception:
        # Roll back only if database work had started, then preserve the traceback.
        if db is not None:
            db.rollback()
        raise

    finally:
        # Return the connection to the pool regardless of task success or failure.
        if db is not None:
            db.close()