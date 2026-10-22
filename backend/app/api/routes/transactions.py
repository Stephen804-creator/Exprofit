"""Business-scoped transaction endpoints with server-side domain permission checks."""

import csv
import io
from datetime import date
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_business_membership
from app.db.session import get_db
from app.models import Business, BusinessMembership, Transaction
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
            metadata={
                "direction": transaction.direction,
                "status": transaction.status,
                "amount": str(transaction.amount),
                "currency_code": transaction.currency_code,
            },
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


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_csv(
    business_id: UUID,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File(...)],
) -> dict:
    """Import a bounded CSV batch atomically; all rows must validate before any are saved."""
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Upload a .csv transaction file.")
    content = await file.read(2 * 1024 * 1024 + 1)
    if not content or len(content) > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail="CSV must be non-empty and no larger than 2 MB."
        )
    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise HTTPException(status_code=422, detail="CSV must be valid UTF-8 text.") from exc
    headers = {str(name).strip().lower() for name in (reader.fieldnames or []) if name}
    required = {"direction", "amount", "transaction_date", "description"}
    if not required.issubset(headers):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "CSV is missing required columns.",
                "required_columns": sorted(required),
            },
        )
    business = db.get(Business, business_id)
    if business is None or business.workspace_type != "business":
        raise HTTPException(status_code=404, detail="Business workspace not found.")

    rows: list[Transaction] = []
    errors: list[dict[str, object]] = []
    for row_number, raw_row in enumerate(reader, start=2):
        if row_number > 502:
            raise HTTPException(
                status_code=413, detail="CSV may contain at most 500 transaction rows."
            )
        row = {(key or "").strip().lower(): (value or "").strip()
               for key, value in raw_row.items() if key is not None}
        if not any(row.values()):
            continue
        try:
            payload = TransactionCreate.model_validate({
                "business_id": business_id,
                "direction": row.get("direction", "").lower(),
                "amount": row.get("amount", ""),
                "currency_code": row.get("currency_code") or business.currency_code,
                "transaction_date": row.get("transaction_date", ""),
                "description": row.get("description", ""),
                "category": row.get("category") or None,
                "status": (row.get("status") or "draft").lower(),
            })
            if payload.currency_code != business.currency_code:
                raise ValueError(
                    f"Currency must match this workspace ({business.currency_code}); "
                    "conversion is not supported."
                )
            require_permission(membership, transaction_domain(payload.direction), "write")
        except (ValidationError, ValueError, HTTPException) as exc:
            if isinstance(exc, HTTPException):
                message = str(exc.detail)
            elif isinstance(exc, ValidationError):
                message = "; ".join(
                    f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
                    for item in exc.errors()
                )
            else:
                message = str(exc)
            errors.append({"row": row_number, "error": message})
            continue
        rows.append(Transaction(**payload.model_dump()))

    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "No rows were imported. Correct the listed CSV errors and retry.",
                    "errors": errors[:100], "error_count": len(errors)},
        )
    if not rows:
        raise HTTPException(status_code=422, detail="CSV contains no transaction rows.")
    import_id = uuid4()
    db.add_all(rows)
    db.flush()
    record_audit_event(
        db, business_id=business_id, actor_user_id=membership.user_id,
        event_type="transactions.imported", target_type="transaction_import", target_id=import_id,
        metadata={
            "row_count": len(rows),
            "source_filename": (file.filename or "transactions.csv")[:255],
            "transaction_ids": [str(item.id) for item in rows],
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="CSV import conflicted with existing records."
        ) from exc
    return {"import_id": str(import_id), "created_count": len(rows),
            "transaction_ids": [str(item.id) for item in rows],
            "message": "Transactions imported. Review draft rows before posting them."}


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
