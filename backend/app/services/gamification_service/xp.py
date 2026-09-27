"""游戏化服务 · XP 流水。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.models.gamification import XPTransaction
from app.models.user import User

from .common import count


def list_xp_transactions(
    db: Session, user: User, params: PageParams
) -> tuple[list[XPTransaction], int]:
    """分页返回经验流水。"""
    total = count(db, select(func.count()).select_from(XPTransaction).where(XPTransaction.user_id == user.id))
    rows = list(
        db.scalars(
            select(XPTransaction)
            .where(XPTransaction.user_id == user.id)
            .order_by(XPTransaction.created_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        ).all()
    )
    return rows, total
