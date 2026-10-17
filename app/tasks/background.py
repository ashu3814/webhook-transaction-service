import time
from sqlalchemy.orm import Session
from app.tasks.celery_app import celery_app
from app.database import SessionLocal
from app.services.transaction import TransactionService
from app.utils.logger import logger


@celery_app.task(bind=True, name="process_transaction")
def process_transaction_task(self, transaction_id: str):
    db: Session | None = None
    start_time = time.time()
    
    logger.info(f"⏳ TASK started | txn_id={transaction_id} | task_id={self.request.id}")

    try:
        # This is the only intentional processing delay.
        logger.info(f"⏳ PROCESSING | txn_id={transaction_id} | waiting=30s")
        time.sleep(30)

        # Open the database session only when the transaction is ready to update.
        db = SessionLocal()
        TransactionService.mark_as_processed(db, transaction_id)
        
        elapsed = round((time.time() - start_time), 2)
        logger.info(
            f"✅ TASK completed | txn_id={transaction_id} | "
            f"duration={elapsed}s | status=PROCESSED"
        )
        return {"status": "processed", "transaction_id": transaction_id}

    except Exception as e:
        elapsed = round((time.time() - start_time), 2)
        logger.error(
            f"❌ TASK failed | txn_id={transaction_id} | "
            f"duration={elapsed}s | error={str(e)}"
        )
        # Roll back only if database work had started, then preserve the traceback.
        if db is not None:
            db.rollback()
        raise

    finally:
        # Return the connection to the pool regardless of task success or failure.
        if db is not None:
            db.close()