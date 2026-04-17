import uuid

import logfire
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_account_repo
from app.repositories.account_repo import AccountRepository
from app.schemas.account import AccountCreate, AccountResponse, AccountUpdate, OwnershipResponse

router = APIRouter()


def _build_response(acc, ownerships_override=None) -> AccountResponse:
    ownerships = ownerships_override
    if ownerships is None:
        ownerships = [
            OwnershipResponse(
                id=o.id,
                member_id=o.member_id,
                ownership_percentage=o.ownership_percentage,
                member_name=o.member.name if o.member else None,
            )
            for o in acc.ownerships
        ]
    return AccountResponse(
        id=acc.id,
        household_id=acc.household_id,
        account_number=acc.account_number,
        custodian=acc.custodian,
        account_type=acc.account_type,
        account_value=acc.account_value,
        ownerships=ownerships,
    )


@router.get("/households/{household_id}/accounts", response_model=list[AccountResponse])
async def list_accounts(household_id: uuid.UUID, repo: AccountRepository = Depends(get_account_repo)):
    accounts = await repo.list_by_household(household_id)
    logfire.info("account.list_returned", household_id=str(household_id), count=len(accounts))
    return [_build_response(acc) for acc in accounts]


@router.post("/households/{household_id}/accounts", response_model=AccountResponse, status_code=201)
async def create_account(
    household_id: uuid.UUID,
    data: AccountCreate,
    repo: AccountRepository = Depends(get_account_repo),
):
    account = await repo.create(household_id, data)
    logfire.info("account.created", household_id=str(household_id), account_id=str(account.id))
    ownerships = [
        OwnershipResponse(
            id=o.id,
            member_id=o.member_id,
            ownership_percentage=o.ownership_percentage,
            member_name=None,
        )
        for o in account.ownerships
    ]
    return _build_response(account, ownerships)


@router.put("/accounts/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: uuid.UUID,
    data: AccountUpdate,
    repo: AccountRepository = Depends(get_account_repo),
):
    updated = await repo.update(account_id, data.model_dump(exclude_unset=True))
    if not updated:
        logfire.warning("account.not_found_on_update", account_id=str(account_id))
        raise HTTPException(status_code=404, detail="Account not found")
    logfire.info("account.updated", account_id=str(account_id))
    return _build_response(updated)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: uuid.UUID,
    repo: AccountRepository = Depends(get_account_repo),
):
    account = await repo.get_by_id(account_id)
    if not account:
        logfire.warning("account.not_found_on_delete", account_id=str(account_id))
        raise HTTPException(status_code=404, detail="Account not found")
    await repo.delete(account_id)
    logfire.info("account.deleted", account_id=str(account_id))
