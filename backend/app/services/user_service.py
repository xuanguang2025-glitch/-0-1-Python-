"""用户服务：资料、偏好、头像、概览、导出、注销（`docs/API.md` §2.2）。"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import level_of_xp, next_level_xp
from app.core.errors import AppError, ErrorCode
from app.core.security import verify_password
from app.models.course import CourseEnrollment
from app.models.enums import ProgressStatus, SubmissionStatus
from app.models.learning import LearningProgress, LearningSession
from app.models.submission import Submission
from app.models.user import Profile, User
from app.schemas.user import (
    ProfileOut,
    ProfileUpdateRequest,
    PreferencesUpdateRequest,
    UserOverviewOut,
    PublicUserOut,
)
from app.utils.files import build_zip
from app.utils.text import mask_email
from app.utils.time import now_utc, seconds_between, today_utc

logger = logging.getLogger("pythonlab.user")

#: 头像允许的图片类型与大小
AVATAR_TYPES: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp")
AVATAR_MAX_BYTES: int = 2 * 1024 * 1024


def get_profile(db: Session, user: User) -> Profile:
    """获取用户资料，缺失时自动补建（保证 1:1 不变式）。"""
    profile = db.scalars(select(Profile).where(Profile.user_id == user.id)).one_or_none()
    if profile is None:
        profile = Profile(user_id=user.id, display_name=user.username)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def update_profile(db: Session, user: User, payload: ProfileUpdateRequest) -> ProfileOut:
    """更新资料（仅允许白名单字段）。"""
    profile = get_profile(db, user)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if value is not None:
            setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return ProfileOut.model_validate(profile)


def update_preferences(db: Session, user: User, payload: PreferencesUpdateRequest) -> ProfileOut:
    """更新偏好（AI 模式 / 学习模式 / 主题 / 每周目标）。"""
    profile = get_profile(db, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return ProfileOut.model_validate(profile)


async def save_avatar(db: Session, user: User, file: UploadFile) -> str:
    """校验并保存头像文件，返回可访问的 `/uploads/...` 路径。"""
    settings = get_settings()
    content_type = (file.content_type or "").lower()
    if content_type not in AVATAR_TYPES:
        raise AppError(
            code=ErrorCode.INVALID_FILE_TYPE,
            message=f"头像仅支持 jpg/png/webp（收到 {content_type or '未知'}）",
            details={"allowed": list(AVATAR_TYPES)},
        )
    content = await file.read()
    if len(content) > AVATAR_MAX_BYTES:
        raise AppError(
            code=ErrorCode.FILE_TOO_LARGE,
            message=f"头像大小超出限制（{len(content)} / {AVATAR_MAX_BYTES} 字节）",
        )

    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[content_type]
    avatars_dir = settings.upload_dir_path / "avatars"
    avatars_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{user.id}{suffix}"
    (avatars_dir / filename).write_bytes(content)

    profile = get_profile(db, user)
    profile.avatar_url = f"/uploads/avatars/{filename}"
    db.commit()
    return profile.avatar_url


def get_overview(db: Session, user: User) -> UserOverviewOut:
    """首页学习概览（经验 / 等级 / 连续天数 / 完成课时 / 解题数 / 今日时长 / 今日任务）。"""
    settings = get_settings()
    thresholds = settings.level_threshold_list

    completed_lessons = int(
        db.scalar(
            select(func.count())
            .select_from(LearningProgress)
            .where(LearningProgress.user_id == user.id, LearningProgress.status == ProgressStatus.COMPLETED.value)
        )
        or 0
    )
    solved_problems = int(
        db.scalar(
            select(func.count(func.distinct(Submission.problem_id))).where(
                Submission.user_id == user.id,
                Submission.status == SubmissionStatus.ACCEPTED.value,
                Submission.problem_id.is_not(None),
            )
        )
        or 0
    )

    day_start = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sessions = db.scalars(
        select(LearningSession).where(
            LearningSession.user_id == user.id,
            LearningSession.started_at >= day_start,
        )
    ).all()
    today_seconds = sum(
        item.duration_seconds
        or (seconds_between(item.started_at, item.ended_at) if item.ended_at else 0)
        for item in today_sessions
    )

    # 今日任务完成数（表可能尚未落数据，缺失时按 0 处理）
    daily_done = 0
    try:
        from app.models.gamification import UserDailyTask

        daily_done = int(
            db.scalar(
                select(func.count()).where(
                    UserDailyTask.user_id == user.id,
                    UserDailyTask.date == today_utc(),
                    UserDailyTask.completed.is_(True),
                )
            )
            or 0
        )
    except Exception:  # noqa: BLE001 - 统计失败不影响主流程
        daily_done = 0

    return UserOverviewOut(
        xp=int(user.xp or 0),
        level=int(user.level or 1),
        next_level_xp=next_level_xp(int(user.xp or 0), thresholds),
        streak_days=int(user.streak_days or 0),
        completed_lessons=completed_lessons,
        solved_problems=solved_problems,
        today_minutes=int(today_seconds // 60),
        daily_tasks_done=daily_done,
    )


def export_learning_data(db: Session, user: User, fmt: str = "json") -> tuple[str, str, bytes]:
    """导出学习数据，返回 `(文件名, MIME, 内容字节)`。"""
    from app.models.learning import Bookmark, CodeHistory, Mistake
    from app.models.submission import Submission as _Submission

    lessons = db.scalars(select(LearningProgress).where(LearningProgress.user_id == user.id)).all()
    submissions = db.scalars(select(_Submission).where(_Submission.user_id == user.id)).all()
    mistakes = db.scalars(select(Mistake).where(Mistake.user_id == user.id)).all()
    bookmarks = db.scalars(select(Bookmark).where(Bookmark.user_id == user.id)).all()
    history = db.scalars(select(CodeHistory).where(CodeHistory.user_id == user.id)).all()

    payload: dict[str, Any] = {
        "user": {
            "id": user.id,
            "email": mask_email(user.email),
            "username": user.username,
            "xp": user.xp,
            "level": user.level,
            "streak_days": user.streak_days,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "progress": [item.to_dict() for item in lessons],
        "submissions": [item.to_dict() for item in submissions],
        "mistakes": [item.to_dict() for item in mistakes],
        "bookmarks": [item.to_dict() for item in bookmarks],
        "code_history": [item.to_dict() for item in history],
    }

    if fmt == "zip":
        files = {
            "user.json": _to_json(payload["user"]),
            "progress.json": _to_json(payload["progress"]),
            "submissions.json": _to_json(payload["submissions"]),
            "mistakes.json": _to_json(payload["mistakes"]),
            "bookmarks.json": _to_json(payload["bookmarks"]),
        }
        for item in history:
            safe_name = item.file_path.replace("/", "_")
            files[f"code/{item.context_type}-{item.version_no}-{safe_name}"] = item.code
        return f"pythonlab-export-{user.username}.zip", "application/zip", build_zip(files)

    return f"pythonlab-export-{user.username}.json", "application/json", _to_json(payload).encode("utf-8")


def _to_json(value: Any) -> str:
    """把任意结构序列化为带缩进的 JSON 文本（中文不转义）。"""
    import json

    def _default(obj: Any) -> str:
        if hasattr(obj, "isoformat"):
            return str(obj.isoformat())
        return str(obj)

    return json.dumps(value, ensure_ascii=False, indent=2, default=_default)


def delete_account(db: Session, user: User, password: str) -> None:
    """软删除账号（保留数据便于审计，标记 status=deleted）。"""
    if not verify_password(password, user.hashed_password):
        raise AppError(code=ErrorCode.INVALID_CREDENTIALS, message="密码不正确", status_code=401)
    user.soft_delete()
    user.status = "deleted"
    db.commit()
    logger.info("用户已软删除 user_id=%s", user.id)


def get_public_user(db: Session, user_id: str) -> PublicUserOut:
    """公开资料：**仅昵称与等级**，不暴露邮箱等任何联系方式。"""
    row = db.execute(
        select(User, Profile)
        .outerjoin(Profile, Profile.user_id == User.id)
        .where(User.id == user_id, User.deleted_at.is_(None))
    ).first()
    if row is None:
        raise AppError(code=ErrorCode.USER_NOT_FOUND, message="用户不存在", status_code=404)
    target, profile = row
    return PublicUserOut(
        id=target.id,
        display_name=(profile.display_name if profile and profile.display_name else target.username),
        avatar_url=profile.avatar_url if profile else None,
        level=int(target.level or 1),
        xp=int(target.xp or 0),
    )


def recent_activity_days(db: Session, user: User, days: int = 7) -> int:
    """返回最近 N 天中有学习记录的活跃天数（连续天数计算的基础）。"""
    since = now_utc() - timedelta(days=days)
    rows = db.scalars(
        select(LearningSession.started_at).where(
            LearningSession.user_id == user.id,
            LearningSession.started_at >= since,
        )
    ).all()
    return len({moment.date() for moment in rows})


def current_stage_no(db: Session, user: User) -> int | None:
    """返回用户最近学习的阶段序号（进度总览用）。"""
    row = db.execute(
        select(CourseEnrollment.course_id, CourseEnrollment.updated_at)
        .where(CourseEnrollment.user_id == user.id)
        .order_by(CourseEnrollment.updated_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    from app.models.course import Course

    course = db.get(Course, row[0])
    return int(course.stage_no) if course else None
