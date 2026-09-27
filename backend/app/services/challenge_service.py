"""挑战赛服务（`docs/API.md` §2.14）。

排行榜**只返回昵称与成绩**（`display_name` + `score` + `total_time_ms`），
绝不包含 email / 真实姓名 / user_id 等隐私字段。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.core.pagination import PageParams
from app.models.challenge import Challenge, UserChallenge
from app.models.enums import ChallengeStatus, NotificationType, SubmissionStatus
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.user import Profile, User
from app.schemas.challenge import (
    ChallengeBrief,
    ChallengeDetail,
    ChallengeSubmitOut,
    LeaderboardEntry,
    LeaderboardOut,
    UserChallengeOut,
)
from app.schemas.problem import ProblemBrief
from app.services import exam_service, gamification_service, notification_service
from app.utils.time import now_utc, to_utc

logger = logging.getLogger("pythonlab.challenge")


def _is_open(challenge: Challenge) -> bool:
    """安全判断挑战是否进行中（归一化时区，避免 naive/aware 比较异常）。"""
    if challenge.end_at is None:
        return False
    return to_utc(challenge.end_at) > now_utc()


def _my_status(db: Session, user: User | None, challenge_id: str) -> UserChallenge | None:
    """返回当前用户在某挑战中的记录（未登录返回 None）。"""
    if user is None:
        return None
    return db.scalars(
        select(UserChallenge).where(UserChallenge.user_id == user.id, UserChallenge.challenge_id == challenge_id)
    ).one_or_none()


def _brief(challenge: Challenge, my: UserChallenge | None) -> ChallengeBrief:
    """构造挑战列表项。"""
    return ChallengeBrief(
        id=challenge.id,
        slug=challenge.slug,
        title=challenge.title,
        challenge_type=challenge.challenge_type,
        difficulty=challenge.difficulty,
        start_at=challenge.start_at,
        end_at=challenge.end_at,
        duration_minutes=challenge.duration_minutes,
        xp_reward=challenge.xp_reward,
        participant_count=challenge.participant_count,
        problem_count=len(challenge.problem_ids),
        is_open=_is_open(challenge),
        my_status=my.status if my else None,
    )


def _user_challenge_out(record: UserChallenge) -> UserChallengeOut:
    """构造用户挑战记录响应体。"""
    return UserChallengeOut(
        id=record.id,
        challenge_id=record.challenge_id,
        status=record.status,
        score=int(record.score or 0),
        passed_cases=int(record.passed_cases or 0),
        total_time_ms=int(record.total_time_ms or 0),
        rank=record.rank,
        submitted_at=record.submitted_at,
    )


def list_challenges(
    db: Session,
    user: User | None,
    params: PageParams,
    *,
    challenge_type: str | None = None,
    status: str | None = None,
) -> tuple[list[ChallengeBrief], int]:
    """挑战列表（可按类型 / 进行状态筛选）。"""
    conditions: list[Any] = [Challenge.is_published.is_(True)]
    if challenge_type:
        conditions.append(Challenge.challenge_type == challenge_type)
    now = now_utc()
    if status == "active":
        conditions.append(Challenge.end_at > now)
    elif status == "ended":
        conditions.append(Challenge.end_at <= now)

    total = int(db.scalar(select(func.count()).select_from(Challenge).where(*conditions)) or 0)
    rows = list(
        db.scalars(
            select(Challenge)
            .where(*conditions)
            .order_by(Challenge.start_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        ).all()
    )
    items = [_brief(challenge, _my_status(db, user, challenge.id)) for challenge in rows]
    return items, total


def get_challenge(db: Session, user: User | None, challenge_id: str) -> ChallengeDetail:
    """挑战详情（含题目列表与我的参与记录）。"""
    challenge = _get_challenge(db, challenge_id)
    my = _my_status(db, user, challenge.id)
    problems = exam_service.problem_briefs(db, challenge.problem_ids)
    return ChallengeDetail(
        challenge=_brief(challenge, my),
        description_md=challenge.description_md,
        rules_md=challenge.rules_md,
        problems=problems,
        my=_user_challenge_out(my) if my else None,
    )


def _get_challenge(db: Session, challenge_id: str) -> Challenge:
    """按 id 获取挑战（不存在抛 404）。"""
    challenge = db.get(Challenge, challenge_id)
    if challenge is None:
        raise AppError(code=ErrorCode.CHALLENGE_NOT_FOUND, message="挑战不存在", status_code=404)
    return challenge


def challenge_problems(db: Session, user: User, challenge_id: str) -> list[ProblemBrief]:
    """`GET /challenges/{id}/problems`：挑战题目列表。"""
    challenge = _get_challenge(db, challenge_id)
    return exam_service.problem_briefs(db, challenge.problem_ids)


def join_challenge(db: Session, user: User, challenge_id: str) -> UserChallengeOut:
    """`POST /challenges/{id}/join`：报名（已结束抛 CHALLENGE_CLOSED，重复报名抛 ALREADY_JOINED）。"""
    challenge = _get_challenge(db, challenge_id)
    if not _is_open(challenge):
        raise AppError(code=ErrorCode.CHALLENGE_CLOSED, message="挑战已结束", status_code=400)
    existing = _my_status(db, user, challenge.id)
    if existing is not None:
        raise AppError(code=ErrorCode.ALREADY_JOINED, message="你已报名该挑战", status_code=409)

    record = UserChallenge(
        user_id=user.id, challenge_id=challenge.id, status=ChallengeStatus.JOINED.value
    )
    db.add(record)
    challenge.participant_count = int(challenge.participant_count or 0) + 1
    notification_service.create(
        db,
        user,
        NotificationType.CHALLENGE.value,
        f"挑战开始：{challenge.title}",
        challenge.description_md or "",
        link=f"/challenges/{challenge.id}",
    )
    db.commit()
    db.refresh(record)
    return _user_challenge_out(record)


def submit_challenge(db: Session, user: User, challenge_id: str, solutions: dict[str, str]) -> ChallengeSubmitOut:
    """`POST /challenges/{id}/submit`：判题计分并更新排行榜数据。"""
    challenge = _get_challenge(db, challenge_id)
    record = _my_status(db, user, challenge.id)
    if record is None:
        raise AppError(code=ErrorCode.BAD_REQUEST, message="请先报名该挑战", status_code=400)
    if not _is_open(challenge):
        raise AppError(code=ErrorCode.CHALLENGE_CLOSED, message="挑战已结束", status_code=400)

    problem_ids = challenge.problem_ids
    problems = {p.id: p for p in db.scalars(select(Problem).where(Problem.id.in_(problem_ids))).all()}
    total_score = 0
    passed_cases = 0
    total_time_ms = 0
    details: list[dict[str, Any]] = []

    for pid in problem_ids:
        problem = problems.get(pid)
        if problem is None:
            continue
        code = solutions.get(pid, "") or ""
        result = exam_service.grade_problem(db, problem, code)
        total_score += int(result["score"])
        passed_cases += int(result["passed_cases"])
        total_time_ms += int(problem.avg_time_ms or 0) or 200
        details.append(
            {
                "problem_id": pid,
                "correct": bool(result["correct"]),
                "score": int(result["score"]),
                "passed_cases": int(result["passed_cases"]),
                "total_cases": int(result["total_cases"]),
            }
        )
        _record_submission(db, user, challenge, problem, code, result)

    record.apply_result(total_score, passed_cases, total_time_ms)
    gamification_service.award_xp(db, user, max(0, total_score // 2), "challenge", "challenge", challenge.id)
    gamification_service.check_and_unlock(db, user, {"metric": "challenges_completed"})
    db.commit()
    db.refresh(record)
    return ChallengeSubmitOut(
        user_challenge=_user_challenge_out(record),
        passed_cases=passed_cases,
        details=details,
    )


def _record_submission(
    db: Session,
    user: User,
    challenge: Challenge,
    problem: Problem,
    code: str,
    result: dict[str, Any],
) -> None:
    """写入一次挑战提交记录并刷新题目冗余计数。"""
    accepted = bool(result["correct"])
    db.add(
        Submission(
            user_id=user.id,
            problem_id=problem.id,
            challenge_id=challenge.id,
            code=code,
            status=SubmissionStatus.ACCEPTED.value if accepted else SubmissionStatus.WRONG_ANSWER.value,
            score=int(result["score"]),
            passed_cases=int(result["passed_cases"]),
            total_cases=int(result["total_cases"]),
            finished_at=now_utc(),
        )
    )
    problem.submission_count = int(problem.submission_count or 0) + 1
    if accepted:
        problem.accepted_count = int(problem.accepted_count or 0) + 1
    problem.refresh_acceptance_rate()


def leaderboard(db: Session, challenge_id: str, limit: int = 100) -> LeaderboardOut:
    """`GET /challenges/{id}/leaderboard`：**仅昵称与成绩**。"""
    challenge = _get_challenge(db, challenge_id)
    limit = max(1, min(100, int(limit or 100)))
    rows = db.execute(
        select(UserChallenge.score, UserChallenge.total_time_ms, Profile.display_name, User.username)
        .join(User, User.id == UserChallenge.user_id)
        .outerjoin(Profile, Profile.user_id == User.id)
        .where(UserChallenge.challenge_id == challenge.id)
        .order_by(UserChallenge.score.desc(), UserChallenge.total_time_ms.asc())
        .limit(limit)
    ).all()
    entries = [
        LeaderboardEntry(
            rank=index,
            display_name=(row.display_name or row.username or "学习者"),
            score=int(row.score or 0),
            total_time_ms=int(row.total_time_ms or 0),
        )
        for index, row in enumerate(rows, start=1)
    ]
    return LeaderboardOut(entries=entries, total=len(entries), updated_at=now_utc())


def my_challenges(db: Session, user: User, params: PageParams) -> tuple[list[UserChallengeOut], int]:
    """`GET /challenges/my`：我的挑战记录。"""
    total = int(
        db.scalar(select(func.count()).select_from(UserChallenge).where(UserChallenge.user_id == user.id)) or 0
    )
    rows = list(
        db.scalars(
            select(UserChallenge)
            .where(UserChallenge.user_id == user.id)
            .order_by(UserChallenge.created_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        ).all()
    )
    return [_user_challenge_out(row) for row in rows], total
