"""Atomic database-backed rate limits that work across application instances."""
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from fastapi import HTTPException, Request
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import RateLimitBucket


def enforce_rate_limit(
    db: Session, request: Request, *, action: str, identity: str, limit: int, window_seconds: int
) -> None:
    """Count an action in a fixed UTC window and reject requests beyond the configured limit."""
    client_ip = request.client.host if request.client else "unknown"
    key_hash = sha256(f"{action}|{client_ip}|{identity.strip().lower()}".encode()).hexdigest()
    now = datetime.now(UTC)
    window_epoch = int(now.timestamp()) // window_seconds * window_seconds
    window_start = datetime.fromtimestamp(window_epoch, UTC)
    table = RateLimitBucket.__table__
    values = {"key_hash": key_hash, "window_start": window_start, "hits": 1}
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = pg_insert(table).values(**values).on_conflict_do_update(
            index_elements=[table.c.key_hash, table.c.window_start],
            set_={"hits": table.c.hits + 1},
        ).returning(table.c.hits)
    elif dialect == "sqlite":
        statement = sqlite_insert(table).values(**values).on_conflict_do_update(
            index_elements=[table.c.key_hash, table.c.window_start],
            set_={"hits": table.c.hits + 1},
        ).returning(table.c.hits)
    else:
        bucket = db.get(RateLimitBucket, (key_hash, window_start))
        if bucket is None:
            bucket = RateLimitBucket(key_hash=key_hash, window_start=window_start, hits=1)
            db.add(bucket)
            db.flush()
        else:
            bucket.hits += 1
        hits = bucket.hits
        db.commit()
        if hits > limit:
            retry_after = max(1, window_seconds - int((now - window_start).total_seconds()))
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.", headers={"Retry-After": str(retry_after)})
        return
    hits = int(db.scalar(statement) or 1)
    # Expired hashed buckets are periodically removed so the table stays bounded.
    db.execute(delete(RateLimitBucket).where(
        RateLimitBucket.window_start < now - timedelta(days=2)
    ))
    db.commit()
    if hits > limit:
        retry_after = max(1, window_seconds - int((now - window_start).total_seconds()))
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )
