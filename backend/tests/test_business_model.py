from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import Business


def test_business_model_persists_foundation_fields() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        business = Business(name="My Side Hustle")
        session.add(business)
        session.commit()
        session.refresh(business)

        assert business.id is not None
        assert business.name == "My Side Hustle"
        assert business.currency_code == "NGN"
        assert business.timezone == "Africa/Lagos"
        assert business.created_at is not None
        assert business.updated_at is not None

    engine.dispose()
