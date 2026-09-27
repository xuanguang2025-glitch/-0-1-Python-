"""代码历史服务：快照 / 列表 / 查看 / 恢复 / 对比 / 删除（`docs/API.md` §2.9、§2.19）。

同一 `(user_id, context_type, context_id, file_path)` 的版本号递增；保留最近
`CODE_HISTORY_KEEP`（30）版，超出部分优先清理 `source=auto` 的更早记录。
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import CODE_HISTORY_KEEP
from app.core.errors import AppError, ErrorCode
from app.core.pagination import PageParams, paginate
from app.models.enums import CodeContextType, CodeSource
from app.models.learning import CodeHistory
from app.models.user import User
from app.schemas.editor import CodeHistoryBrief, CodeHistoryOut, CompareOut
from app.utils.diff import build_hunks, unified_diff_text
from app.utils.validators import validate_code_size, validate_relative_path

logger = logging.getLogger("pythonlab.code_history")


def save_snapshot(
    db: Session,
    user: User,
    *,
    context_type: str,
    context_id: str | None,
    file_path: str,
    code: str,
    label: str | None = None,
    source: str = CodeSource.MANUAL.value,
) -> CodeHistory:
    """写入一条代码历史快照（自动分配版本号并清理过期版本）。"""
    safe_path = validate_relative_path(file_path)
    validate_code_size(code or "")
    if context_type not in CodeContextType.values():
        context_type = CodeContextType.PLAYGROUND.value
    if source not in CodeSource.values():
        source = CodeSource.MANUAL.value

    version_no, parent_id = _next_version(db, user.id, context_type, context_id, safe_path)
    record = CodeHistory(
        user_id=user.id,
        context_type=context_type,
        context_id=context_id,
        file_path=safe_path,
        code=code or "",
        label=label,
        version_no=version_no,
        parent_id=parent_id,
        source=source,
        size_bytes=len((code or "").encode("utf-8")),
    )
    db.add(record)
    db.flush()
    _prune(db, user.id, context_type, context_id, safe_path)
    db.commit()
    db.refresh(record)
    return record


def list_history(
    db: Session,
    user: User,
    *,
    context_type: str | None,
    context_id: str | None,
    params: PageParams,
) -> tuple[list[CodeHistory], int]:
    """按上下文分页列出代码历史（不含完整代码）。"""
    stmt = select(CodeHistory).where(CodeHistory.user_id == user.id)
    if context_type:
        stmt = stmt.where(CodeHistory.context_type == context_type)
    if context_id:
        stmt = stmt.where(CodeHistory.context_id == context_id)
    stmt = stmt.order_by(CodeHistory.created_at.desc(), CodeHistory.version_no.desc())
    return paginate(db, stmt, params)


def get_history(db: Session, user: User, history_id: str) -> CodeHistory:
    """按 id 获取历史版本（校验归属）。"""
    record = db.get(CodeHistory, history_id)
    if record is None:
        raise AppError(code=ErrorCode.HISTORY_NOT_FOUND, message="代码历史不存在", status_code=404)
    if record.user_id != user.id:
        raise AppError(code=ErrorCode.FORBIDDEN, message="无权访问他人的代码历史", status_code=403)
    return record


def restore_snapshot(db: Session, user: User, history_id: str) -> CodeHistory:
    """把某个历史版本复制为新版本并返回（不修改原记录）。"""
    original = get_history(db, user, history_id)
    return save_snapshot(
        db,
        user,
        context_type=original.context_type,
        context_id=original.context_id,
        file_path=original.file_path,
        code=original.code,
        label=f"恢复自 v{original.version_no}",
        source=CodeSource.MANUAL.value,
    )


def delete_history(db: Session, user: User, history_id: str) -> None:
    """删除某个历史版本。"""
    record = get_history(db, user, history_id)
    db.delete(record)
    db.commit()


def compare_versions(db: Session, user: User, left_id: str, right_id: str) -> CompareOut:
    """对比两个历史版本，返回统一 diff 文本与结构化 hunks。"""
    left = get_history(db, user, left_id)
    right = get_history(db, user, right_id)
    diff_text = unified_diff_text(
        left.code,
        right.code,
        left_label=f"v{left.version_no}:{left.file_path}",
        right_label=f"v{right.version_no}:{right.file_path}",
    )
    hunks = build_hunks(left.code, right.code)
    return CompareOut(diff_text=diff_text, hunks=hunks)


def to_brief(record: CodeHistory) -> CodeHistoryBrief:
    """ORM → 列表项 Schema。"""
    return CodeHistoryBrief.model_validate(record)


def to_out(record: CodeHistory) -> CodeHistoryOut:
    """ORM → 详情 Schema。"""
    return CodeHistoryOut.model_validate(record)


def _next_version(
    db: Session, user_id: str, context_type: str, context_id: str | None, file_path: str
) -> tuple[int, str | None]:
    """计算下一个版本号与父版本 id。"""
    conditions = [
        CodeHistory.user_id == user_id,
        CodeHistory.context_type == context_type,
        CodeHistory.file_path == file_path,
    ]
    conditions.append(
        CodeHistory.context_id.is_(None) if context_id is None else CodeHistory.context_id == context_id
    )
    row = db.execute(
        select(CodeHistory.version_no, CodeHistory.id)
        .where(*conditions)
        .order_by(CodeHistory.version_no.desc())
        .limit(1)
    ).first()
    if row is None:
        return 1, None
    return int(row[0]) + 1, str(row[1])


def _prune(db: Session, user_id: str, context_type: str, context_id: str | None, file_path: str) -> None:
    """保留最近 `CODE_HISTORY_KEEP` 版，超出部分清理 source=auto 的更早记录。"""
    conditions = [
        CodeHistory.user_id == user_id,
        CodeHistory.context_type == context_type,
        CodeHistory.file_path == file_path,
    ]
    conditions.append(
        CodeHistory.context_id.is_(None) if context_id is None else CodeHistory.context_id == context_id
    )
    total = int(db.scalar(select(func.count()).select_from(CodeHistory).where(*conditions)) or 0)
    overflow = total - CODE_HISTORY_KEEP
    if overflow <= 0:
        return
    stale = db.scalars(
        select(CodeHistory)
        .where(*conditions, CodeHistory.source == CodeSource.AUTO.value)
        .order_by(CodeHistory.version_no.asc())
        .limit(overflow)
    ).all()
    for item in stale:
        db.delete(item)
    db.flush()


__all__ = [
    "compare_versions",
    "delete_history",
    "get_history",
    "list_history",
    "restore_snapshot",
    "save_snapshot",
    "to_brief",
    "to_out",
]
