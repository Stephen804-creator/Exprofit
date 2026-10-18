from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import Business, Transaction
from app.schemas.transactions import TransactionCreate, TransactionUpdate
from app.services.transactions import (
    BusinessNotFoundError,
    CurrencyMismatchError,
    InvalidTransactionStateError,
    TransactionNotFoundError,
    create_transaction,
    get_transaction,
    list_transactions,
    update_transaction,
    void_transaction,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def make_business(db: Session, *, currency_code: str = "NGN") -> Business:
    business = Business(name="Market Stall", currency_code=currency_code)
    db.add(business)
    db.commit()
    db.refresh(business)
    return business


def make_payload(business_id, **overrides) -> TransactionCreate:
    data = {
        "business_id": business_id,
        "direction": "income",
        "amount": Decimal("1250.50"),
        "currency_code": "NGN",
        "transaction_date": date(2026, 10, 18),
        "description": "Daily sales",
        "category": "Sales",
        "status": "posted",
    }
    data.update(overrides)
    return TransactionCreate(**data)


def test_create_and_list_transaction(db_session: Session) -> None:
    business = make_business(db_session)
    saved = create_transaction(db_session, make_payload(business.id))

    assert saved.amount == Decimal("1250.50")
    assert saved.direction == "income"
    assert saved.status == "posted"
    assert saved.currency_code == "NGN"
    assert list_transactions(db_session, business.id) == [saved]


def test_rejects_missing_business(db_session: Session) -> None:
    with pytest.raises(BusinessNotFoundError):
        create_transaction(db_session, make_payload(uuid4()))


def test_rejects_currency_mismatch(db_session: Session) -> None:
    business = make_business(db_session, currency_code="NGN")
    payload = make_payload(business.id, currency_code="USD")

    with pytest.raises(CurrencyMismatchError):
        create_transaction(db_session, payload)


def test_get_is_scoped_to_business(db_session: Session) -> None:
    business = make_business(db_session)
    saved = create_transaction(db_session, make_payload(business.id))

    with pytest.raises(TransactionNotFoundError):
        get_transaction(db_session, uuid4(), saved.id)


def test_update_and_void_preserve_entry(db_session: Session) -> None:
    business = make_business(db_session)
    saved = create_transaction(db_session, make_payload(business.id))
    updated = update_transaction(
        db_session,
        business.id,
        saved.id,
        TransactionUpdate(description="Corrected sales note"),
    )
    assert updated.description == "Corrected sales note"

    voided = void_transaction(db_session, business.id, saved.id)
    assert voided.status == "void"
    assert db_session.get(Transaction, saved.id) is not None

    with pytest.raises(InvalidTransactionStateError):
        update_transaction(
            db_session,
            business.id,
            saved.id,
            TransactionUpdate(description="Cannot change void entry"),
        )


def test_amount_must_be_positive() -> None:
    with pytest.raises(ValueError):
        make_payload(uuid4(), amount=Decimal("0.00"))


def test_currency_is_normalized() -> None:
    payload = make_payload(uuid4(), currency_code="ngn")
    assert payload.currency_code == "NGN"



def test_duplicate_idempotency_key_is_rejected(db_session: Session) -> None:
    from app.services.transactions import DuplicateTransactionRequestError

    business = make_business(db_session)
    payload = make_payload(business.id, idempotency_key="request-001")
    create_transaction(db_session, payload)

    with pytest.raises(DuplicateTransactionRequestError):
        create_transaction(db_session, payload)


def test_blank_description_is_rejected() -> None:
    with pytest.raises(ValueError):
        make_payload(uuid4(), description="   ")


def test_invalid_currency_code_is_rejected() -> None:
    with pytest.raises(ValueError):
        make_payload(uuid4(), currency_code="12$")
