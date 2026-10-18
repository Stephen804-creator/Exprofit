"""Transaction lifecycle operations, kept separate from HTTP routes."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Business, Transaction
from app.schemas.transactions import TransactionCreate, TransactionUpdate


class TransactionServiceError(Exception):
    """Base exception for expected transaction-service failures."""


class BusinessNotFoundError(TransactionServiceError):
    """Raised when the requested business does not exist."""


class TransactionNotFoundError(TransactionServiceError):
    """Raised when the requested transaction does not exist in the business."""


class CurrencyMismatchError(TransactionServiceError):
    """Raised when a transaction currency differs from the business currency."""


class DuplicateTransactionRequestError(TransactionServiceError):
    """Raised when an idempotency key has already been used for a business."""


class InvalidTransactionStateError(TransactionServiceError):
    """Raised when an operation is not allowed for the current transaction state."""


def create_transaction(db: Session, payload: TransactionCreate) -> Transaction:
    """Create a transaction after checking business and currency consistency."""
    business = db.get(Business, payload.business_id)
    if business is None:
        raise BusinessNotFoundError("Business not found")

    if payload.currency_code != business.currency_code:
        raise CurrencyMismatchError(
            "Transaction currency must match the business currency; conversion is not supported"
        )

    if payload.idempotency_key:
        existing = db.scalar(
            select(Transaction).where(
                Transaction.business_id == payload.business_id,
                Transaction.idempotency_key == payload.idempotency_key,
            )
        )
        if existing is not None:
            raise DuplicateTransactionRequestError(
                "This idempotency key has already been used for this business"
            )

    transaction = Transaction(**payload.model_dump())
    db.add(transaction)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(transaction)
    return transaction


def list_transactions(
    db: Session,
    business_id: UUID,
    *,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Transaction]:
    """List entries for one business, newest transaction date first."""
    query = select(Transaction).where(Transaction.business_id == business_id)
    if status is not None:
        query = query.where(Transaction.status == status)
    query = (
        query.order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(query).all())


def get_transaction(db: Session, business_id: UUID, transaction_id: UUID) -> Transaction:
    """Fetch an entry by both business and transaction ID."""
    transaction = db.scalar(
        select(Transaction).where(
            Transaction.business_id == business_id,
            Transaction.id == transaction_id,
        )
    )
    if transaction is None:
        raise TransactionNotFoundError("Transaction not found")
    return transaction


def update_transaction(
    db: Session,
    business_id: UUID,
    transaction_id: UUID,
    payload: TransactionUpdate,
) -> Transaction:
    """Update editable fields on a draft or posted entry."""
    transaction = get_transaction(db, business_id, transaction_id)
    if transaction.status == "void":
        raise InvalidTransactionStateError("Voided transactions cannot be edited")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(transaction, field, value)

    db.commit()
    db.refresh(transaction)
    return transaction


def void_transaction(db: Session, business_id: UUID, transaction_id: UUID) -> Transaction:
    """Mark an entry void instead of deleting its financial history."""
    transaction = get_transaction(db, business_id, transaction_id)
    if transaction.status == "void":
        raise InvalidTransactionStateError("Transaction is already void")
    transaction.status = "void"
    db.commit()
    db.refresh(transaction)
    return transaction
