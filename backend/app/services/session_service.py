"""学习会话服务：开始 / 心跳 / 结束（`docs/API.md` §2.11 学习会话记录）。

独立于 `progress_service`：会话是「时长与热力图」的数据源，生命周期与进度读写解耦，
所有操作均校验会话归属（仅本人，越权返回 403）。
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.models.learning import LearningSession
from app.models.user import User
from app.schemas.progress import (
    LearningSessionEndRequest,
    LearningSessionHeartbeatRequest,
    LearningSessionOut,
    LearningSessionStartRequest,
)
from app.utils.time import now_utc, seconds_between

logger = logging.getLogger("pythonlab.session")


def start_session(db: Session, user: User, payload: LearningSessionStartRequest) -> LearningSessionOut:
    """开始一次学习会话。"""
    session = LearningSession(
        user_id=user.id,
        session_type=payload.session_type,
        learning_mode=payload.learning_mode,
        ref_id=payload.ref_id,
        started_at=now_utc(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return to_out(session)


def heartbeat(
    db: Session, user: User, session_id: str, payload: LearningSessionHeartbeatRequest
) -> LearningSessionOut:
    """会话心跳：累加时长 / 行为数 / 经验。仅本人可操作。"""
    session = owned_session(db, user, session_id)
    session.duration_seconds = int(session.duration_seconds or 0) + payload.seconds
    session.actions_count = int(session.actions_count or 0) + payload.actions
    session.xp_earned = int(session.xp_earned or 0) + payload.xp_earned
    db.commit()
    db.refresh(session)
    return to_out(session)


def end_session(db: Session, user: User, session_id: str, payload: LearningSessionEndRequest) -> LearningSessionOut:
    """结束会话并结算时长。仅本人可操作。"""
    session = owned_session(db, user, session_id)
    session.close(duration_seconds=payload.duration_seconds)
    if payload.actions_count is not None:
        session.actions_count = payload.actions_count
    db.commit()
    db.refresh(session)
    return to_out(session)


def session_seconds(session: LearningSession) -> int:
    """会话有效时长（秒）：优先取已结算时长，否则按起止时间推算。"""
    if session.duration_seconds:
        return int(session.duration_seconds)
    if session.ended_at:
        return seconds_between(session.started_at, session.ended_at)
    return seconds_between(session.started_at, now_utc())


def owned_session(db: Session, user: User, session_id: str) -> LearningSession:
    """取会话并校验归属，非本人抛 403，不存在抛 404。"""
    session = db.get(LearningSession, session_id)
    if session is None:
        raise AppError(code=ErrorCode.NOT_FOUND, message="学习会话不存在", status_code=404, details=f"id={session_id}")
    if session.user_id != user.id:
        raise AppError(code=ErrorCode.FORBIDDEN, message="无权操作他人的学习会话", status_code=403)
    return session


def to_out(session: LearningSession) -> LearningSessionOut:
    """ORM 学习会话 → Schema。"""
    return LearningSessionOut(
        id=session.id,
        session_type=session.session_type,
        learning_mode=session.learning_mode,
        ref_id=session.ref_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        duration_seconds=int(session.duration_seconds or 0),
        xp_earned=int(session.xp_earned or 0),
        actions_count=int(session.actions_count or 0),
    )
