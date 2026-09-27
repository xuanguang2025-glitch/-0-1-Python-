"""判题服务 · 学习副作用（题目统计 / XP / 掌握度 / 错题本 / 课时进度 / 连续天数）。

全部函数幂等或可重复调用：XP 仅首次 AC 发放；错题条目复用未解决记录累加；
`rejudge` 路径不会进入本模块（不重复发放奖励）。
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import (
    MAX_STDOUT_CHARS,
    XP_REASON_AC,
    level_of_xp,
    mastery_level_of,
)
from app.db.base import utc_now
from app.models.course import LessonTopic, Topic
from app.models.enums import MasteryLevel, MistakeErrorType
from app.models.gamification import XPTransaction
from app.models.learning import KnowledgeMastery, LearningProgress, Mistake
from app.models.problem import Problem, ProblemTag, Tag
from app.models.submission import Submission
from app.models.user import User
from app.utils.text import truncate
from app.utils.time import to_utc

from app.services.judge_types import (
    ACCEPTED,
    COMPILE_ERROR,
    MEMORY_LIMIT,
    RUNTIME_ERROR,
    SECURITY_ERROR,
    TIME_LIMIT,
    WRONG_ANSWER,
    JudgeOutcome,
)


def _post_judge_effects(
    db: Session, user: User, problem: Problem, submission: Submission, outcome: JudgeOutcome
) -> None:
    """更新题目统计、掌握度、XP、连续学习天数与错题本。"""
    _update_problem_stats(problem, submission)
    topics = _topics_for(db, problem, submission.lesson_id)
    accepted = submission.status == ACCEPTED

    if accepted:
        _award_ac_xp(db, user, problem, submission)
        _resolve_mistakes(db, user, problem)
    for topic_id, _weight in topics:
        _update_mastery(db, user, topic_id, accepted)
    if not accepted:
        primary_topic = topics[0][0] if topics else None
        _record_mistake(db, user, problem, submission, primary_topic)
    if submission.lesson_id:
        _update_lesson_progress(db, user, submission)
    _touch_streak(db, user)
    db.flush()


def _update_problem_stats(problem: Problem, submission: Submission) -> None:
    """更新题目提交 / 通过计数与通过率。"""
    problem.submission_count = int(problem.submission_count or 0) + 1
    if submission.status == ACCEPTED:
        problem.accepted_count = int(problem.accepted_count or 0) + 1
    problem.refresh_acceptance_rate()
    if submission.time_ms:
        problem.avg_time_ms = int(submission.time_ms or 0)


def _award_ac_xp(db: Session, user: User, problem: Problem, submission: Submission) -> None:
    """首次通过该题时发放 XP 并写流水。"""
    prior = db.scalar(
        select(func.count())
        .select_from(Submission)
        .where(
            Submission.user_id == user.id,
            Submission.problem_id == problem.id,
            Submission.status == ACCEPTED,
            Submission.id != submission.id,
        )
    )
    if prior:
        return
    amount = int(problem.xp_reward or 0)
    if amount <= 0:
        return
    user.xp = int(user.xp or 0) + amount
    user.level = level_of_xp(int(user.xp), get_settings().level_threshold_list)
    db.add(
        XPTransaction(
            user_id=user.id,
            amount=amount,
            reason=XP_REASON_AC,
            ref_type="problem",
            ref_id=problem.id,
            balance_after=int(user.xp),
        )
    )


def _topics_for(db: Session, problem: Problem, lesson_id: str | None) -> list[tuple[str, float]]:
    """汇总题目关联知识点：课时主/次知识点 + 标签同名知识点。"""
    weights: dict[str, float] = {}
    if lesson_id:
        for link in db.scalars(select(LessonTopic).where(LessonTopic.lesson_id == lesson_id)).all():
            weights[link.topic_id] = 1.0 if link.is_primary else 0.5
    tag_slugs = list(
        db.scalars(
            select(Tag.slug).join(ProblemTag, ProblemTag.tag_id == Tag.id).where(ProblemTag.problem_id == problem.id)
        ).all()
    )
    if tag_slugs:
        for topic in db.scalars(select(Topic).where(Topic.slug.in_(tag_slugs))).all():
            weights.setdefault(topic.id, 1.0)
    return list(weights.items())


def _update_mastery(db: Session, user: User, topic_id: str, correct: bool) -> None:
    """更新单个知识点掌握度；通过时标记为已掌握。"""
    mastery = db.scalars(
        select(KnowledgeMastery).where(
            KnowledgeMastery.user_id == user.id, KnowledgeMastery.topic_id == topic_id
        )
    ).one_or_none()
    if mastery is None:
        mastery = KnowledgeMastery(
            user_id=user.id, topic_id=topic_id, mastery_score=0.0, mastery_level=MasteryLevel.NONE.value
        )
        db.add(mastery)
    mastery.apply_result(correct)
    if correct:
        mastery.mastery_score = max(float(mastery.mastery_score or 0.0), 90.0)
        mastery.mastery_level = mastery_level_of(mastery.mastery_score)
    db.flush()


def _resolve_mistakes(db: Session, user: User, problem: Problem) -> None:
    """答对该题后，把该用户该题所有未解决的错题条目标记为已掌握（幂等）。

    仅修改 `resolved` 状态，保留 `review_count` 与 `user_answer` 等学习记录；
    重复 AC 不会报错，也不会触碰已解决的条目。
    """
    unresolved = db.scalars(
        select(Mistake).where(
            Mistake.user_id == user.id,
            Mistake.problem_id == problem.id,
            Mistake.resolved.is_(False),
        )
    ).all()
    for mistake in unresolved:
        mistake.resolve(True)
    if unresolved:
        db.flush()


def _record_mistake(
    db: Session, user: User, problem: Problem, submission: Submission, topic_id: str | None
) -> None:
    """写入 / 更新错题本条目（同一题未掌握时累加错误次数）。"""
    error_type = _mistake_error_type(submission.status)
    existing = db.scalars(
        select(Mistake)
        .where(
            Mistake.user_id == user.id,
            Mistake.problem_id == problem.id,
            Mistake.resolved.is_(False),
        )
        .order_by(Mistake.updated_at.desc())
    ).first()
    answer = truncate(submission.code or "", MAX_STDOUT_CHARS)
    if existing is not None:
        existing.review_count = int(existing.review_count or 0) + 1
        existing.user_answer = answer
        existing.error_type = error_type
        existing.error_message = submission.error_message
        existing.submission_id = submission.id
        if topic_id:
            existing.topic_id = topic_id
        existing.schedule_review(1)
        return
    mistake = Mistake(
        user_id=user.id,
        problem_id=problem.id,
        submission_id=submission.id,
        lesson_id=submission.lesson_id,
        topic_id=topic_id,
        title=problem.title or "错题",
        question_snapshot_md=problem.statement_md,
        user_answer=answer,
        correct_answer=None,
        error_type=error_type,
        error_message=submission.error_message,
        review_count=1,
    )
    mistake.schedule_review(1)
    db.add(mistake)


def _mistake_error_type(status: str) -> str:
    """提交状态 → 错题错误类型。"""
    return {
        WRONG_ANSWER: MistakeErrorType.OUTPUT.value,
        RUNTIME_ERROR: MistakeErrorType.RUNTIME.value,
        COMPILE_ERROR: MistakeErrorType.SYNTAX.value,
        TIME_LIMIT: MistakeErrorType.TIMEOUT.value,
        MEMORY_LIMIT: MistakeErrorType.RUNTIME.value,
        SECURITY_ERROR: MistakeErrorType.CONCEPT.value,
    }.get(status, MistakeErrorType.LOGIC.value)


def _update_lesson_progress(db: Session, user: User, submission: Submission) -> None:
    """更新随堂练习课时进度（次数 + 代码快照）。"""
    progress = db.scalars(
        select(LearningProgress).where(
            LearningProgress.user_id == user.id, LearningProgress.lesson_id == submission.lesson_id
        )
    ).one_or_none()
    if progress is None:
        progress = LearningProgress(user_id=user.id, lesson_id=str(submission.lesson_id))
        db.add(progress)
    progress.attempt_count = int(progress.attempt_count or 0) + 1
    progress.code_snapshot = truncate(submission.code or "", MAX_STDOUT_CHARS)
    if progress.started_at is None:
        progress.started_at = utc_now()


def _touch_streak(db: Session, user: User) -> None:
    """按 UTC 日期维护连续学习天数。"""
    now = utc_now()
    today = now.date()
    last = user.last_active_at
    if last is None:
        user.streak_days = 1
    else:
        delta = (today - to_utc(last).date()).days
        if delta == 0:
            user.streak_days = int(user.streak_days or 0) or 1
        elif delta == 1:
            user.streak_days = int(user.streak_days or 0) + 1
        else:
            user.streak_days = 1
    if int(user.streak_days or 0) > int(user.max_streak_days or 0):
        user.max_streak_days = int(user.streak_days)
    user.last_active_at = now
