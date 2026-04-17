import uuid

import logfire
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
        logfire.warning("bank_detail.not_found_on_update", bank_id=str(bank_id))
        raise HTTPException(status_code=404, detail="Bank detail not found")
    logfire.info("bank_detail.updated", bank_id=str(bank_id))
    return updated


@router.delete("/bank-details/{bank_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bank_detail(
    bank_id: uuid.UUID,
    repo: BankDetailRepository = Depends(get_bank_detail_repo),
):
    bd = await repo.get_by_id(bank_id)
    if not bd:
        logfire.warning("bank_detail.not_found_on_delete", bank_id=str(bank_id))
        raise HTTPException(status_code=404, detail="Bank detail not found")
    await repo.delete(bank_id)
    logfire.info("bank_detail.deleted", bank_id=str(bank_id))
