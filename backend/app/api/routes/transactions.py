"""Business-scoped transaction endpoints; every operation checks membership."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_business_membership
from app.db.session import get_db
from app.models import BusinessMembership, Transaction
from app.schemas.transactions import TransactionCreate, TransactionRead, TransactionUpdate
from app.services.transactions import (
    BusinessNotFoundError,
    CurrencyMismatchError,
    DuplicateTransactionRequestError,
    InvalidTransactionStateError,
    TransactionNotFoundError,
    create_transaction,
    get_transaction,
    list_transactions,
    update_transaction,
    void_transaction,
)

router = APIRouter(prefix="/businesses/{business_id}/transactions", tags=["transactions"])


def _raise_service_error(exc: Exception) -> None:
    if isinstance(exc, BusinessNotFoundError | TransactionNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, CurrencyMismatchError | DuplicateTransactionRequestError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, InvalidTransactionStateError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise exc


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def create(
    business_id: UUID,
    payload: TransactionCreate,
    _: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> Transaction:
    if payload.business_id != business_id:
        raise HTTPException(status_code=400, detail="business_id in body must match URL")
    try:
        return create_transaction(db, payload)
    except (BusinessNotFoundError, CurrencyMismatchError, DuplicateTransactionRequestError) as exc:
        _raise_service_error(exc)


@router.get("", response_model=list[TransactionRead])
def list_entries(
    business_id: UUID,
    _: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status", pattern="^(draft|posted|void)$")] = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Transaction]:
    # Date filters are intentionally applied here only when provided.
    entries = list_transactions(db, business_id, status=status_filter, limit=100, offset=0)
    if start_date is not None:
        entries = [entry for entry in entries if entry.transaction_date >= start_date]
    if end_date is not None:
        entries = [entry for entry in entries if entry.transaction_date <= end_date]
    return entries[offset : offset + limit]


@router.get("/{transaction_id}", response_model=TransactionRead)
def read_entry(
    business_id: UUID,
    transaction_id: UUID,
    _: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> Transaction:
    try:
        return get_transaction(db, business_id, transaction_id)
    except TransactionNotFoundError as exc:
        _raise_service_error(exc)


@router.patch("/{transaction_id}", response_model=TransactionRead)
def update_entry(
    business_id: UUID,
    transaction_id: UUID,
    payload: TransactionUpdate,
    _: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> Transaction:
    try:
        return update_transaction(db, business_id, transaction_id, payload)
    except (TransactionNotFoundError, InvalidTransactionStateError) as exc:
        _raise_service_error(exc)


@router.post("/{transaction_id}/void", response_model=TransactionRead)
def void_entry(
    business_id: UUID,
    transaction_id: UUID,
    _: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> Transaction:
    try:
        return void_transaction(db, business_id, transaction_id)
    except (TransactionNotFoundError, InvalidTransactionStateError) as exc:
        _raise_service_error(exc)
