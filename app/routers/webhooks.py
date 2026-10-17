from fastapi import APIRouter, Depends, status, Request
from sqlalchemy.orm import Session
import time
from app.database import get_db
from app.schemas.transaction import TransactionCreate, WebhookResponse
from app.services.transaction import TransactionService
from app.tasks.background import process_transaction_task
from app.repositories.transaction import TransactionRepository
from app.utils.logger import logger

router = APIRouter(prefix="/v1", tags=["webhooks"])


@router.post("/webhooks/transactions", response_model=WebhookResponse, status_code=status.HTTP_202_ACCEPTED)
async def receive_webhook(
    transaction: TransactionCreate,
    db: Session = Depends(get_db),
    request: Request = None
) -> WebhookResponse:
    start_time = time.time()
    
    # Skip known duplicates before creating a row or enqueueing work.
    if TransactionRepository.exists(db, transaction.transaction_id):
        elapsed = round((time.time() - start_time) * 1000, 2)
        logger.info(
            f"🔄 DUPLICATE webhook | txn_id={transaction.transaction_id} | "
            f"response_time={elapsed}ms | status=202"
        )
        return WebhookResponse(status="received")

    # Commit the transaction before queueing so the worker can find its row.
    created = TransactionService.receive_webhook(db, transaction)
    if not created:
        elapsed = round((time.time() - start_time) * 1000, 2)
        logger.info(
            f"🔄 DUPLICATE webhook | txn_id={transaction.transaction_id} | "
            f"response_time={elapsed}ms | status=202"
        )
        return WebhookResponse(status="received")

    # Publish immediately; queue congestion is managed by the worker prefetch setting.
    task = process_transaction_task.delay(transaction.transaction_id)
    elapsed = round((time.time() - start_time) * 1000, 2)
    
    logger.info(
        f"📨 WEBHOOK received | txn_id={transaction.transaction_id} | "
        f"task_id={task.id} | response_time={elapsed}ms | status=202"
    )

    return WebhookResponse(status="received")