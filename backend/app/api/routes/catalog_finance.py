"""Workspace product/customer attribution and category budget endpoints."""
from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_business_membership
from app.db.session import get_db
from app.models import Budget, Business, BusinessMembership, Customer, FinancialGoal, Product, Transaction
from app.permissions import require_permission
from app.schemas.catalog import (
    BudgetCreate,
    BudgetRead,
    FinancialGoalCreate,
    FinancialGoalRead,
    CustomerCreate,
    CustomerRead,
    ProductCreate,
    ProductRead,
)
from app.services.financial_analysis import DIRECT_COST_CATEGORIES

router = APIRouter(prefix="/businesses/{business_id}", tags=["catalog and budgets"])


def _business(db: Session, business_id: UUID) -> Business:
    business = db.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return business


@router.get("/products", response_model=list[ProductRead])
def list_products(
    business_id: UUID,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Product]:
    require_permission(membership, "sales", "read")
    query = (
        select(Product)
        .where(Product.business_id == business_id, Product.is_active.is_(True))
        .order_by(Product.name.asc())
        .limit(500)
    )
    return list(db.scalars(query).all())


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    business_id: UUID,
    payload: ProductCreate,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> Product:
    require_permission(membership, "sales", "write")
    business = _business(db, business_id)
    product = Product(
        business_id=business_id,
        currency_code=business.currency_code,
        **payload.model_dump(),
    )
    db.add(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A product with this name or SKU already exists.",
        ) from exc
    db.refresh(product)
    return product


@router.get("/customers", response_model=list[CustomerRead])
def list_customers(
    business_id: UUID,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Customer]:
    require_permission(membership, "sales", "read")
    query = (
        select(Customer)
        .where(Customer.business_id == business_id, Customer.is_active.is_(True))
        .order_by(Customer.name.asc())
        .limit(500)
    )
    return list(db.scalars(query).all())


@router.post("/customers", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(
    business_id: UUID,
    payload: CustomerCreate,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> Customer:
    require_permission(membership, "sales", "write")
    _business(db, business_id)
    customer = Customer(business_id=business_id, **payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def _attributed_profitability(
    db: Session,
    business_id: UUID,
    dimension: str,
    start_date: date | None,
    end_date: date | None,
) -> list[dict]:
    model = Product if dimension == "product" else Customer
    link_column = (
        Transaction.product_id if dimension == "product" else Transaction.customer_id
    )
    entries = list(
        db.scalars(
            select(model)
            .where(model.business_id == business_id, model.is_active.is_(True))
            .order_by(model.name.asc())
            .limit(500)
        ).all()
    )
    if not entries:
        return []

    direct_cost = (
        (Transaction.direction == "expense")
        & func.lower(func.coalesce(Transaction.category, "")).in_(DIRECT_COST_CATEGORIES)
    )
    query = select(
        link_column.label("entry_id"),
        func.coalesce(
            func.sum(case((Transaction.direction == "income", Transaction.amount), else_=0)),
            0,
        ).label("revenue"),
        func.coalesce(
            func.sum(case((direct_cost, Transaction.amount), else_=0)), 0
        ).label("direct_costs"),
        func.count(Transaction.id).label("transaction_count"),
        func.sum(case((direct_cost, 1), else_=0)).label("direct_cost_count"),
    ).where(
        Transaction.business_id == business_id,
        Transaction.status == "posted",
        link_column.in_([entry.id for entry in entries]),
    )
    if start_date:
        query = query.where(Transaction.transaction_date >= start_date)
    if end_date:
        query = query.where(Transaction.transaction_date <= end_date)
    totals = {row.entry_id: row for row in db.execute(query.group_by(link_column)).all()}
    workspace_currency = _business(db, business_id).currency_code
    result = []

    for entry in entries:
        row = totals.get(entry.id)
        revenue = Decimal(row.revenue or 0) if row else Decimal("0.00")
        direct_costs = Decimal(row.direct_costs or 0) if row else Decimal("0.00")
        has_direct_costs = bool(row and row.direct_cost_count)
        gross_profit = revenue - direct_costs if has_direct_costs else None
        margin = None
        if gross_profit is not None and revenue > 0:
            margin = (gross_profit / revenue * Decimal("100")).quantize(Decimal("0.01"))
        result.append(
            {
                "id": str(entry.id),
                "name": entry.name,
                "currency_code": (
                    entry.currency_code if dimension == "product" else workspace_currency
                ),
                "revenue": str(revenue.quantize(Decimal("0.01"))),
                "direct_costs": str(direct_costs.quantize(Decimal("0.01"))),
                "gross_profit": (
                    str(gross_profit.quantize(Decimal("0.01")))
                    if gross_profit is not None
                    else None
                ),
                "gross_margin_percent": str(margin) if margin is not None else None,
                "transaction_count": int(row.transaction_count) if row else 0,
                "note": (
                    "Uses posted transactions explicitly linked to this record. Direct costs "
                    "include only configured direct-cost categories; missing direct-cost "
                    "records make gross profit unavailable."
                ),
            }
        )
    return result


def _validate_date_range(start_date: date | None, end_date: date | None) -> None:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date must be on or before end_date",
        )


@router.get("/product-profitability")
def product_profitability(
    business_id: UUID,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    require_permission(membership, "sales", "read")
    require_permission(membership, "expenses", "read")
    _validate_date_range(start_date, end_date)
    return {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "items": _attributed_profitability(
            db, business_id, "product", start_date, end_date
        ),
    }


@router.get("/customer-profitability")
def customer_profitability(
    business_id: UUID,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    require_permission(membership, "sales", "read")
    require_permission(membership, "expenses", "read")
    _validate_date_range(start_date, end_date)
    return {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "items": _attributed_profitability(
            db, business_id, "customer", start_date, end_date
        ),
    }


@router.get("/budgets", response_model=list[BudgetRead])
def list_budgets(
    business_id: UUID,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Budget]:
    require_permission(membership, "expenses", "read")
    query = (
        select(Budget)
        .where(Budget.business_id == business_id)
        .order_by(Budget.period_start.desc(), Budget.category.asc())
        .limit(500)
    )
    return list(db.scalars(query).all())


@router.post("/budgets", response_model=BudgetRead, status_code=status.HTTP_201_CREATED)
def create_budget(
    business_id: UUID,
    payload: BudgetCreate,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> Budget:
    require_permission(membership, "expenses", "write")
    if payload.period_start > payload.period_end:
        raise HTTPException(
            status_code=422,
            detail="period_start must be on or before period_end",
        )
    business = _business(db, business_id)
    budget = Budget(
        business_id=business_id,
        currency_code=business.currency_code,
        **payload.model_dump(),
    )
    db.add(budget)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A budget already exists for this category and period.",
        ) from exc
    db.refresh(budget)
    return budget


@router.get("/goals", response_model=list[FinancialGoalRead])
def list_financial_goals(
    business_id: UUID,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> list[FinancialGoal]:
    require_permission(membership, "sales", "read")
    require_permission(membership, "expenses", "read")
    return list(db.scalars(
        select(FinancialGoal).where(
            FinancialGoal.business_id == business_id, FinancialGoal.is_active.is_(True)
        ).order_by(FinancialGoal.period_end.asc(), FinancialGoal.name.asc()).limit(200)
    ).all())


@router.post("/goals", response_model=FinancialGoalRead, status_code=status.HTTP_201_CREATED)
def create_financial_goal(
    business_id: UUID,
    payload: FinancialGoalCreate,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> FinancialGoal:
    if payload.period_start > payload.period_end:
        raise HTTPException(status_code=422, detail="period_start must be on or before period_end")
    require_permission(membership, "sales", "write")
    if payload.goal_kind == "gross_profit":
        require_permission(membership, "expenses", "write")
    business = _business(db, business_id)
    goal = FinancialGoal(
        business_id=business_id, currency_code=business.currency_code, **payload.model_dump()
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.get("/goal-progress")
def financial_goal_progress(
    business_id: UUID,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    require_permission(membership, "sales", "read")
    require_permission(membership, "expenses", "read")
    goals = db.scalars(select(FinancialGoal).where(
        FinancialGoal.business_id == business_id, FinancialGoal.is_active.is_(True)
    ).order_by(FinancialGoal.period_end.asc()).limit(200)).all()
    output = []
    for goal in goals:
        records = db.scalars(select(Transaction).where(
            Transaction.business_id == business_id,
            Transaction.status == "posted",
            Transaction.currency_code == goal.currency_code,
            Transaction.transaction_date >= goal.period_start,
            Transaction.transaction_date <= goal.period_end,
        )).all()
        revenue = sum((row.amount for row in records if row.direction == "income"), Decimal("0.00"))
        direct_costs = sum((row.amount for row in records if row.direction == "expense" and (row.category or "").strip().casefold() in {category.casefold() for category in DIRECT_COST_CATEGORIES}), Decimal("0.00"))
        actual = revenue if goal.goal_kind == "revenue" else revenue - direct_costs
        target = Decimal(goal.target_amount)
        percent = (actual / target * Decimal("100")).quantize(Decimal("0.01"))
        output.append({
            "id": str(goal.id), "name": goal.name, "goal_kind": goal.goal_kind,
            "currency_code": goal.currency_code, "period_start": goal.period_start.isoformat(),
            "period_end": goal.period_end.isoformat(), "target_amount": str(target),
            "actual_amount": str(actual.quantize(Decimal("0.01"))),
            "remaining_amount": str((target - actual).quantize(Decimal("0.01"))),
            "progress_percent": str(percent), "status": "achieved" if actual >= target else "in_progress",
            "basis": "Revenue is the sum of posted income. Gross profit is posted income minus posted expenses in recognised direct-cost categories; overhead and missing costs are not inferred.",
        })
    return {"items": output}


@router.get("/budget-vs-actual")
def budget_vs_actual(
    business_id: UUID,
    membership: Annotated[BusinessMembership, Depends(require_business_membership)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    require_permission(membership, "expenses", "read")
    budgets = db.scalars(
        select(Budget)
        .where(Budget.business_id == business_id)
        .order_by(Budget.period_start.desc(), Budget.category.asc())
        .limit(500)
    ).all()
    rows = []
    for budget in budgets:
        actual = db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.business_id == business_id,
                Transaction.status == "posted",
                Transaction.direction == "expense",
                Transaction.currency_code == budget.currency_code,
                Transaction.category == budget.category,
                Transaction.transaction_date >= budget.period_start,
                Transaction.transaction_date <= budget.period_end,
            )
        ) or Decimal("0.00")
        actual = Decimal(actual)
        percent = actual / Decimal(budget.amount) * Decimal("100")
        state = (
            "over_budget"
            if percent >= 100
            else "warning"
            if percent >= budget.warning_threshold_percent
            else "on_track"
        )
        rows.append(
            {
                "id": str(budget.id),
                "category": budget.category,
                "currency_code": budget.currency_code,
                "period_start": budget.period_start.isoformat(),
                "period_end": budget.period_end.isoformat(),
                "budget_amount": str(budget.amount),
                "actual_spend": str(actual.quantize(Decimal("0.01"))),
                "remaining": str((Decimal(budget.amount) - actual).quantize(Decimal("0.01"))),
                "used_percent": str(percent.quantize(Decimal("0.01"))),
                "warning_threshold_percent": budget.warning_threshold_percent,
                "status": state,
            }
        )
    return {
        "items": rows,
        "disclaimer": (
            "Actuals include posted expense transactions whose category exactly matches the "
            "budget category and whose dates fall inside the budget period."
        ),
    }
