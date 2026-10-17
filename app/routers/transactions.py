from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.transaction import TransactionResponse
from app.services.transaction import TransactionService

router = APIRouter(prefix="/v1", tags=["transactions"])


@router.get("/transactions/{transaction_id}", response_model=list[TransactionResponse])
async def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db)
) -> list[TransactionResponse]:
    
    transaction = TransactionService.get_transaction(db, transaction_id)
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_id} not found"
        )
    
    return [transaction]