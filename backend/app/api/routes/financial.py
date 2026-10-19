"""Private receipt workflow, financial summaries and MarginGuard API."""

import hashlib
import io
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import PurePath
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_business_membership
from app.db.session import get_db
from app.models import Business, BusinessMembership, Receipt, Transaction
from app.permissions import require_permission
from app.services.financial_analysis import compare_periods, profitability, summarize_transactions

router = APIRouter(prefix="/businesses/{business_id}", tags=["financial"])
MAX_RECEIPT_BYTES = 5 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


class ReceiptConfirm(BaseModel):
    direction: str = Field(pattern="^(income|expense)$")
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    transaction_date: date
    description: str = Field(min_length=1, max_length=500)
    category: str | None = Field(default="Uncategorised", max_length=80)


def _require_write(membership: BusinessMembership) -> None:
    require_permission(membership, "expenses", "write")


def _receipt_payload(receipt: Receipt) -> dict:
    return {
        "id": str(receipt.id), "business_id": str(receipt.business_id),
        "original_filename": receipt.original_filename, "content_type": receipt.content_type,
        "candidate_merchant": receipt.candidate_merchant,
        "candidate_date": receipt.candidate_date.isoformat() if receipt.candidate_date else None,
        "candidate_amount": str(receipt.candidate_amount) if receipt.candidate_amount is not None else None,
        "candidate_currency": receipt.candidate_currency,
        "extracted_text": receipt.extracted_text[:6000],
        "review_status": receipt.review_status,
        "linked_transaction_id": str(receipt.linked_transaction_id) if receipt.linked_transaction_id else None,
        "created_at": receipt.created_at.isoformat() if receipt.created_at else None,
    }


def _extract_text(content: bytes, content_type: str) -> str:
    """Use optional local OCR/PDF packages; never fail upload solely because OCR is unavailable."""
    try:
        if content_type == "application/pdf":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content), strict=False)
            return "\n".join((page.extract_text() or "") for page in reader.pages)[:12000]
        from PIL import Image
        import pytesseract
        with Image.open(io.BytesIO(content)) as image:
            return pytesseract.image_to_string(image.convert("RGB"))[:12000]
    except Exception:
        return ""


def _extract_candidates(text: str) -> tuple[str | None, date | None, Decimal | None, str | None]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    merchant = lines[0][:160] if lines else None
    parsed_date = None
    for pattern, fmt in ((r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", "%Y-%m-%d"),
                         (r"\b(\d{1,2})[-/](\d{1,2})[-/](20\d{2})\b", "%d-%m-%Y")):
        match = re.search(pattern, text)
        if match:
            try:
                parsed_date = date.fromisoformat(
                    f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
                ) if fmt == "%Y-%m-%d" else date(
                    int(match.group(3)), int(match.group(2)), int(match.group(1))
                )
                break
            except ValueError:
                continue
    currency = None
    for token, code in (("₦", "NGN"), ("NGN", "NGN"), ("$", "USD"), ("USD", "USD"),
                        ("£", "GBP"), ("GBP", "GBP"), ("€", "EUR"), ("EUR", "EUR")):
        if token.lower() in text.lower():
            currency = code
            break
    amounts = re.findall(r"(?<!\w)(?:₦|NGN|USD|GBP|EUR|\$|£|€)?\s*(\d{1,9}(?:,\d{3})*(?:\.\d{2})|\d+(?:\.\d{2}))(?!\w)", text, re.I)
    parsed_amount = None
    if amounts:
        try:
            parsed_amount = Decimal(amounts[-1].replace(",", "")).quantize(Decimal("0.01"))
        except InvalidOperation:
            pass
    return merchant, parsed_date, parsed_amount, currency


@router.get("/financial-summary")
def financial_summary(
    business_id: UUID,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")
    require_permission(membership, "sales", "read")
    require_permission(membership, "expenses", "read")
    query = select(Transaction).where(
        Transaction.business_id == business_id, Transaction.status == "posted"
    )
    if start_date:
        query = query.where(Transaction.transaction_date >= start_date)
    if end_date:
        query = query.where(Transaction.transaction_date <= end_date)
    items = list(db.scalars(query.order_by(Transaction.transaction_date.desc())).all())
    return {"start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            **summarize_transactions(items), "profitability": profitability(items)}


@router.get("/margin-guard")
def margin_guard(
    business_id: UUID,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
    end_date: date = Query(default_factory=date.today),
    period_days: Annotated[int, Query(ge=7, le=180)] = 30,
) -> dict:
    require_permission(membership, "sales", "read")
    require_permission(membership, "expenses", "read")
    current_start = end_date - timedelta(days=period_days - 1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=period_days - 1)
    query = select(Transaction).where(
        Transaction.business_id == business_id, Transaction.status == "posted",
        Transaction.transaction_date >= previous_start, Transaction.transaction_date <= end_date,
    )
    items = list(db.scalars(query.order_by(Transaction.transaction_date.desc())).all())
    current = [x for x in items if current_start <= x.transaction_date <= end_date]
    previous = [x for x in items if previous_start <= x.transaction_date <= previous_end]
    return compare_periods(current, previous, current_start, end_date, previous_start, previous_end)


@router.get("/receipts")
def list_receipts(
    business_id: UUID,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    require_permission(membership, "expenses", "read")
    receipts = db.scalars(select(Receipt).where(
        Receipt.business_id == business_id
    ).order_by(Receipt.created_at.desc()).limit(50)).all()
    return [_receipt_payload(item) for item in receipts]


@router.post("/receipts", status_code=status.HTTP_201_CREATED)
async def upload_receipt(
    business_id: UUID,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File(...)],
) -> dict:
    _require_write(membership)
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, WebP image, or PDF.")
    content = await file.read(MAX_RECEIPT_BYTES + 1)
    if not content or len(content) > MAX_RECEIPT_BYTES:
        raise HTTPException(status_code=413, detail="Receipt must be non-empty and no larger than 5 MB.")
    # Check file signatures instead of trusting the browser-provided MIME type alone.
    valid = (
        (content_type == "image/jpeg" and content.startswith(b"\xff\xd8\xff"))
        or (content_type == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n"))
        or (content_type == "image/webp" and content[:4] == b"RIFF" and content[8:12] == b"WEBP")
        or (content_type == "application/pdf" and content.startswith(b"%PDF-"))
    )
    if not valid:
        raise HTTPException(status_code=415, detail="The file content does not match its declared type.")
    text = _extract_text(content, content_type)
    merchant, parsed_date, amount, currency = _extract_candidates(text)
    receipt = Receipt(
        business_id=business_id, uploaded_by_user_id=membership.user_id,
        original_filename=PurePath(file.filename or "receipt").name[:255],
        content_type=content_type, sha256_hex=hashlib.sha256(content).hexdigest(),
        file_bytes=content, extracted_text=text, candidate_merchant=merchant,
        candidate_date=parsed_date, candidate_amount=amount, candidate_currency=currency,
        review_status="pending",
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return _receipt_payload(receipt)


@router.get("/receipts/{receipt_id}/file")
def download_receipt_file(
    business_id: UUID, receipt_id: UUID,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    require_permission(membership, "expenses", "read")
    receipt = db.scalar(select(Receipt).where(
        Receipt.id == receipt_id, Receipt.business_id == business_id
    ))
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    return Response(content=receipt.file_bytes, media_type=receipt.content_type,
                    headers={"Content-Disposition": 'inline; filename="receipt"',
                             "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/receipts/{receipt_id}/confirm")
def confirm_receipt(
    business_id: UUID, receipt_id: UUID, payload: ReceiptConfirm,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    require_permission(membership, "sales" if payload.direction == "income" else "expenses", "write")
    receipt = db.scalar(select(Receipt).where(
        Receipt.id == receipt_id, Receipt.business_id == business_id
    ))
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    if receipt.review_status != "pending":
        raise HTTPException(status_code=409, detail="This receipt has already been reviewed.")
    business = db.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found.")
    transaction = Transaction(
        business_id=business_id,
        direction=payload.direction,
        amount=payload.amount,
        currency_code=business.currency_code,
        transaction_date=payload.transaction_date,
        description=payload.description.strip(),
        category=payload.category,
        status="posted",
    )
    # One transaction ensures a receipt cannot be marked confirmed without its ledger entry.
    db.add(transaction)
    receipt.review_status = "confirmed"
    db.flush()
    receipt.linked_transaction_id = transaction.id
    db.commit()
    db.refresh(receipt)
    return {"receipt": _receipt_payload(receipt), "transaction_id": str(transaction.id)}


@router.post("/receipts/{receipt_id}/reject")
def reject_receipt(
    business_id: UUID, receipt_id: UUID,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    _require_write(membership)
    receipt = db.scalar(select(Receipt).where(
        Receipt.id == receipt_id, Receipt.business_id == business_id
    ))
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    if receipt.review_status != "pending":
        raise HTTPException(status_code=409, detail="This receipt has already been reviewed.")
    receipt.review_status = "rejected"
    receipt.file_bytes = b""
    receipt.extracted_text = ""
    db.commit()
    return _receipt_payload(receipt)
