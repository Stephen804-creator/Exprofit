"""Central server-side permission policy for workspace financial data.

Permission keys use the form "<domain>:<action>" with boolean values.
Examples: "sales:read": true and "expenses:write": true.
"""
from collections.abc import Iterable

from fastapi import HTTPException, status

from app.models import BusinessMembership

FINANCIAL_DOMAINS = ("sales", "purchases", "expenses", "inventory")
ACTIONS = ("read", "write")
TRANSACTION_DIRECTION_DOMAIN = {"income": "sales", "expense": "expenses"}


def has_permission(membership: BusinessMembership, domain: str, action: str) -> bool:
    """Owners have full workspace financial access; others need explicit grants."""
    if membership.status != "active":
        return False
    if domain not in (*FINANCIAL_DOMAINS, "staff_administration") or action not in ACTIONS:
        return False
    if membership.role == "owner":
        return True
    if membership.role not in {"admin", "worker"}:
        return False
    permissions = membership.permissions or {}
    return permissions.get(f"{domain}:{action}") is True


def require_permission(membership: BusinessMembership, domain: str, action: str) -> None:
    """Raise a consistent authorization error when an action is not granted."""
    if not has_permission(membership, domain, action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission required: {domain}:{action}",
        )


def allowed_transaction_directions(
    membership: BusinessMembership, action: str
) -> tuple[str, ...]:
    """Return directions the member may access without leaking other domains."""
    allowed: Iterable[str] = (
        direction
        for direction, domain in TRANSACTION_DIRECTION_DOMAIN.items()
        if has_permission(membership, domain, action)
    )
    result = tuple(allowed)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No transaction {action} permission is assigned",
        )
    return result


def transaction_domain(direction: str) -> str:
    """Map the current transaction model to its financial permission domain."""
    try:
        return TRANSACTION_DIRECTION_DOMAIN[direction]
    except KeyError as exc:
        raise HTTPException(status_code=403, detail="Unsupported transaction domain") from exc
