"""Business-scoped transaction endpoints with server-side domain permission checks."""

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
from app.permissions import (
    allowed_transaction_directions,
    require_permission,
    transaction_domain,
)
from app.schemas.transactions import TransactionCreate, TransactionRead, TransactionUpdate
from app.services.audit import record_audit_event
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
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> Transaction:
    if payload.business_id != business_id:
        raise HTTPException(status_code=400, detail="business_id in body must match URL")
    require_permission(membership, transaction_domain(payload.direction), "write")
    try:
        transaction = create_transaction(db, payload)
        record_audit_event(
            db, business_id=business_id, actor_user_id=membership.user_id,
            event_type="transaction.created", target_type="transaction", target_id=transaction.id,
            metadata={"direction": transaction.direction, "status": transaction.status,
                      "amount": str(transaction.amount), "currency_code": transaction.currency_code},
        )
        db.commit()
        return transaction
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
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
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
    directions = allowed_transaction_directions(membership, "read")
    query = select(Transaction).where(
        Transaction.business_id == business_id,
        Transaction.direction.in_(directions),
    )
    if status_filter is not None:
        query = query.where(Transaction.status == status_filter)
    if start_date is not None:
        query = query.where(Transaction.transaction_date >= start_date)
    if end_date is not None:
        query = query.where(Transaction.transaction_date <= end_date)
    query = (
        query.order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(query).all())


@router.get("/{transaction_id}", response_model=TransactionRead)
def read_entry(
    business_id: UUID,
    transaction_id: UUID,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> Transaction:
    try:
        transaction = get_transaction(db, business_id, transaction_id)
        require_permission(membership, transaction_domain(transaction.direction), "read")
        return transaction
    except TransactionNotFoundError as exc:
        _raise_service_error(exc)


@router.patch("/{transaction_id}", response_model=TransactionRead)
def update_entry(
    business_id: UUID,
    transaction_id: UUID,
    payload: TransactionUpdate,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> Transaction:
    try:
        existing = get_transaction(db, business_id, transaction_id)
        require_permission(membership, transaction_domain(existing.direction), "write")
        if payload.direction is not None:
            require_permission(membership, transaction_domain(payload.direction), "write")
        transaction = update_transaction(db, business_id, transaction_id, payload)
        record_audit_event(
            db, business_id=business_id, actor_user_id=membership.user_id,
            event_type="transaction.updated", target_type="transaction", target_id=transaction.id,
            metadata={"updated_fields": sorted(payload.model_dump(exclude_unset=True).keys()),
                      "status": transaction.status},
        )
        db.commit()
        return transaction
    except (TransactionNotFoundError, InvalidTransactionStateError) as exc:
        _raise_service_error(exc)


@router.post("/{transaction_id}/void", response_model=TransactionRead)
def void_entry(
    business_id: UUID,
    transaction_id: UUID,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> Transaction:
    try:
        existing = get_transaction(db, business_id, transaction_id)
        require_permission(membership, transaction_domain(existing.direction), "write")
        transaction = void_transaction(db, business_id, transaction_id)
        record_audit_event(
            db, business_id=business_id, actor_user_id=membership.user_id,
            event_type="transaction.voided", target_type="transaction", target_id=transaction.id,
            metadata={"direction": transaction.direction, "amount": str(transaction.amount),
                      "currency_code": transaction.currency_code},
        )
        db.commit()
        return transaction
    except (TransactionNotFoundError, InvalidTransactionStateError) as exc:
        _raise_service_error(exc)
