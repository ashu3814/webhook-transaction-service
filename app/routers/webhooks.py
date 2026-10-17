from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
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
    db: Session = Depends(get_db)
) -> WebhookResponse:
    # Skip known duplicates before creating a row or enqueueing work.
    if TransactionRepository.exists(db, transaction.transaction_id):
        logger.info("Duplicate webhook skipped transaction_id=%s", transaction.transaction_id)
        return WebhookResponse(status="received")

    # Commit the transaction before queueing so the worker can find its row.
    created = TransactionService.receive_webhook(db, transaction)
    if not created:
        # Another request may have inserted this ID after the initial existence check.
        logger.info("Duplicate webhook skipped transaction_id=%s", transaction.transaction_id)
        return WebhookResponse(status="received")

    # Publish immediately; queue congestion is managed by the worker prefetch setting.
    process_transaction_task.delay(transaction.transaction_id)

    return WebhookResponse(status="received")