import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_bank_detail_repo
from app.repositories.bank_detail_repo import BankDetailRepository
from app.schemas.bank_detail import BankDetailResponse, BankDetailUpdate

router = APIRouter()


@router.put("/bank-details/{bank_id}", response_model=BankDetailResponse)
async def update_bank_detail(
    bank_id: uuid.UUID,
    data: BankDetailUpdate,
    repo: BankDetailRepository = Depends(get_bank_detail_repo),
):
    updated = await repo.update(bank_id, data.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Bank detail not found")
    return updated


@router.delete("/bank-details/{bank_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bank_detail(
    bank_id: uuid.UUID,
    repo: BankDetailRepository = Depends(get_bank_detail_repo),
):
    bd = await repo.get_by_id(bank_id)
    if not bd:
        raise HTTPException(status_code=404, detail="Bank detail not found")
    await repo.delete(bank_id)
