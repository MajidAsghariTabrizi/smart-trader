# -*- coding: utf-8 -*-
"""
SmartTrader Plans Module
- Plan management (FREE/PRO/PROFESSIONAL)
- Plan assignment and validation
- FastAPI dependencies for plan checks
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, status

from database_setup import get_db_connection, USER_PLANS_TABLE
from auth import get_current_user

# =====================================================================
# Plan Hierarchy
# =====================================================================

PLAN_LEVELS = {
    "FREE": 0,
    "PRO": 1,
    "PROFESSIONAL": 2,
}

# =====================================================================
# Plan Management
# =====================================================================


def get_user_plan(user_id: int) -> Optional[Dict[str, Any]]:
    """Get active plan for user."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        row = conn.execute(
            f"""
            SELECT id, user_id, plan, starts_at, ends_at, is_active, created_at
            FROM {USER_PLANS_TABLE}
            WHERE user_id = ? AND is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if row:
            plan = dict(row)
            # Check if plan has expired
            if plan.get("ends_at"):
                ends_at = datetime.fromisoformat(plan["ends_at"].replace("Z", "+00:00"))
                if ends_at < datetime.now(timezone.utc):
                    # Plan expired, return FREE
                    return {"plan": "FREE", "is_active": True}
            return plan
        return None
    finally:
        conn.close()


def assign_default_plan(user_id: int) -> bool:
    """Assign FREE plan to new user."""
    return set_user_plan(user_id, "FREE", duration_days=None)


def set_user_plan(user_id: int, plan: str, duration_days: Optional[int] = None) -> bool:
    """
    Set user plan. If duration_days is None, plan is permanent (for FREE).
    For PRO/PROFESSIONAL, duration_days should be provided.
    """
    if plan not in PLAN_LEVELS:
        return False

    conn = get_db_connection()
    if not conn:
        return False

    try:
        # Deactivate existing active plans
        conn.execute(
            f"UPDATE {USER_PLANS_TABLE} SET is_active = 0 WHERE user_id = ? AND is_active = 1",
            (user_id,),
        )

        # Calculate ends_at
        starts_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        ends_at = None
        if duration_days is not None:
            ends_at = (datetime.now(timezone.utc) + timedelta(days=duration_days)).isoformat().replace("+00:00", "Z")

        # Insert new plan
        conn.execute(
            f"""
            INSERT INTO {USER_PLANS_TABLE} (user_id, plan, starts_at, ends_at, is_active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (user_id, plan, starts_at, ends_at),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error setting user plan: {e}")
        return False
    finally:
        conn.close()


def has_plan_access(user_plan: Optional[Dict[str, Any]], required_plan: str) -> bool:
    """Check if user plan has access to required plan level."""
    if not user_plan:
        return required_plan == "FREE"

    user_plan_name = user_plan.get("plan", "FREE")
    user_level = PLAN_LEVELS.get(user_plan_name, 0)
    required_level = PLAN_LEVELS.get(required_plan, 0)

    return user_level >= required_level


# =====================================================================
# FastAPI Dependencies
# =====================================================================


def require_plan(plan: str):
    """
    FastAPI dependency to require a specific plan level.
    Usage: @app.get("/api/pro/feature", dependencies=[Depends(require_plan("PRO"))])
    """

    def _check_plan(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_plan = get_user_plan(current_user["id"])
        if not has_plan_access(user_plan, plan):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{plan} plan required",
            )
        return current_user

    return Depends(_check_plan)

