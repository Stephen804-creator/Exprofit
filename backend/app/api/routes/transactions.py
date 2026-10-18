"""Business-scoped transaction endpoints; every operation checks membership."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
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
    update_transaction,
    void_transaction,
)

router = APIRouter(prefix="/businesses/{business_id}/transactions", tags=["transactions"])


def _raise_service_error(exc: Exception) -> None:
    if isinstance(exc, (BusinessNotFoundError, TransactionNotFoundError)):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, (CurrencyMismatchError, DuplicateTransactionRequestError)):
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
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Transaction conflicts with an existing record",
        ) from exc


@router.get("", response_model=list[TransactionRead])
def list_entries(
    business_id: UUID,
    _: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[
        str | None, Query(alias="status", pattern="^(draft|posted|void)$")
    ] = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Transaction]:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")
    query = select(Transaction).where(Transaction.business_id == business_id)
    if status_filter is not None:
        query = query.where(Transaction.status == status_filter)
    if start_date is not None:
        query = query.where(Transaction.transaction_date >= start_date)
    if end_date is not None:
        query = query.where(Transaction.transaction_date <= end_date)
    query = query.order_by(
        Transaction.transaction_date.desc(), Transaction.created_at.desc()
    ).offset(offset).limit(limit)
    return list(db.scalars(query).all())


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
