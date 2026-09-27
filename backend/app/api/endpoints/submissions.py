"""提交与判题端点（`docs/API.md` §2.6，6 条路由）。

- `POST /submissions` 同步判题并返回结果；
- 提交详情 / 用例结果对**非样例测试点**做脱敏（不返回 expected_output，仅保留「第 N 个测试点未通过」）。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import client_ip, rate_limit_user
from app.core.deps import AdminUser, CurrentUser, DbSession, Pagination
from app.core.errors import AppError, ErrorCode, forbidden, not_found
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.models.problem import Problem, TestCase
from app.models.submission import Submission
from app.models.user import User
from app.schemas.submission import (
    SubmissionBrief,
    SubmissionCreateRequest,
    SubmissionOut,
    SubmissionResultOut,
    SubmissionStatusOut,
)
from app.services import judge_service
from app.utils.validators import validate_code_size

router = APIRouter(prefix="/submissions", tags=["submissions"])

#: 单次提交代码大小上限（256KB）
MAX_CODE_BYTES: int = 256 * 1024

SubmitLimit = Annotated[None, Depends(rate_limit_user("submit"))]


@router.post("", response_model=ResponseModel[SubmissionOut], summary="提交代码并判题")
def create_submission(
    payload: SubmissionCreateRequest,
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
    _limit: SubmitLimit,
) -> dict:
    """提交代码 / 答案，同步判题并返回结果。"""
    if not payload.problem_id:
        raise AppError(code=ErrorCode.BAD_REQUEST, message="problem_id 不能为空")
    problem = db.get(Problem, payload.problem_id)
    if problem is None or not problem.is_published:
        raise not_found(ErrorCode.PROBLEM_NOT_FOUND, "题目不存在")
    validate_code_size(payload.code or "", limit=MAX_CODE_BYTES)

    submission = judge_service.judge_submission(
        db,
        current_user,
        problem=problem,
        code=payload.code or "",
        language=payload.language or "python",
        lesson_id=payload.lesson_id,
        answer=_effective_answer(payload),
        ip=client_ip(request),
    )
    return success_response(_build_out(db, submission, current_user, include_results=True))


@router.get("", response_model=ResponseModel[PageModel[SubmissionBrief]], summary="我的提交列表")
def list_submissions(
    current_user: CurrentUser,
    db: DbSession,
    pagination: Pagination,
    problem_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict:
    """分页返回当前用户的提交记录。"""
    stmt = select(Submission).where(Submission.user_id == current_user.id)
    if problem_id:
        stmt = stmt.where(Submission.problem_id == problem_id)
    if status:
        stmt = stmt.where(Submission.status == status)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    items = db.scalars(
        stmt.order_by(Submission.created_at.desc()).offset(pagination.offset).limit(pagination.limit)
    ).all()
    title_map = _problem_titles(db, [item.problem_id for item in items if item.problem_id])
    briefs = [
        SubmissionBrief(
            id=item.id,
            problem_id=item.problem_id,
            problem_title=title_map.get(item.problem_id or ""),
            lesson_id=item.lesson_id,
            status=item.status,
            score=int(item.score or 0),
            passed_cases=int(item.passed_cases or 0),
            total_cases=int(item.total_cases or 0),
            time_ms=int(item.time_ms or 0),
            memory_kb=int(item.memory_kb or 0),
            language=item.language,
            created_at=item.created_at,
        )
        for item in items
    ]
    return success_response(build_page(briefs, total, pagination))


@router.get("/{submission_id}", response_model=ResponseModel[SubmissionOut], summary="提交详情")
def get_submission(
    submission_id: str,
    current_user: CurrentUser,
    db: DbSession,
    include_results: bool = Query(default=True),
) -> dict:
    """返回提交详情（含脱敏后的逐用例结果）。"""
    submission = _get_owned(db, submission_id, current_user)
    return success_response(_build_out(db, submission, current_user, include_results=include_results))


@router.get(
    "/{submission_id}/results",
    response_model=ResponseModel[list[SubmissionResultOut]],
    summary="用例判题结果",
)
def get_submission_results(submission_id: str, current_user: CurrentUser, db: DbSession) -> dict:
    """返回逐用例结果（隐藏用例脱敏）。"""
    submission = _get_owned(db, submission_id, current_user)
    return success_response(_build_out(db, submission, current_user, include_results=True).results)


@router.get("/{submission_id}/status", response_model=ResponseModel[SubmissionStatusOut], summary="判题状态")
def get_submission_status(submission_id: str, current_user: CurrentUser, db: DbSession) -> dict:
    """轮询判题状态（同步判题下通常直接返回终态）。"""
    submission = _get_owned(db, submission_id, current_user, allow_admin=False)
    return success_response(
        SubmissionStatusOut(
            status=submission.status,
            passed_cases=int(submission.passed_cases or 0),
            total_cases=int(submission.total_cases or 0),
            finished=bool(submission.is_finished),
        )
    )


@router.post("/{submission_id}/rejudge", response_model=ResponseModel[SubmissionOut], summary="重判（管理员）")
def rejudge_submission(submission_id: str, admin: AdminUser, db: DbSession) -> dict:
    """重新判题（仅管理员）。"""
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise not_found(ErrorCode.SUBMISSION_NOT_FOUND, "提交不存在")
    submission = judge_service.rejudge(db, submission)
    return success_response(_build_out(db, submission, admin, include_results=True), message="已重新判题")


# ------------------------------------------------------------------ 内部工具
def _effective_answer(payload: SubmissionCreateRequest) -> object | None:
    """客观题答案优先取 `answer` 字段，否则退回 `code`。"""
    if payload.answer is not None:
        return payload.answer
    return payload.code


def _get_owned(db: Session, submission_id: str, user: User, *, allow_admin: bool = True) -> Submission:
    """获取提交并校验归属（本人或管理员）。"""
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise not_found(ErrorCode.SUBMISSION_NOT_FOUND, "提交不存在")
    if submission.user_id == user.id:
        return submission
    if allow_admin and user.is_admin:
        return submission
    raise forbidden("无权访问该提交")


def _build_out(
    db: Session, submission: Submission, user: User, *, include_results: bool
) -> SubmissionOut:
    """构造提交详情，对隐藏用例的期望/实际输出脱敏。"""
    results: list[SubmissionResultOut] = []
    if include_results:
        cases = _test_case_map(db, submission.problem_id)
        ordered = sorted(
            submission.results or [],
            key=lambda row: (cases.get(row.test_case_id).order_index if cases.get(row.test_case_id) else 10**6, row.id),
        )
        for index, row in enumerate(ordered, start=1):
            case = cases.get(row.test_case_id) if row.test_case_id else None
            hidden = case is not None and not bool(case.is_sample)
            if hidden:
                results.append(
                    SubmissionResultOut(
                        id=row.id,
                        test_case_id=None,
                        passed=bool(row.passed),
                        time_ms=int(row.time_ms or 0),
                        memory_kb=int(row.memory_kb or 0),
                        actual_output=None,
                        expected_output=None,
                        diff=None,
                        stderr=None,
                        message=None if row.passed else f"第 {index} 个测试点未通过",
                    )
                )
            else:
                results.append(
                    SubmissionResultOut(
                        id=row.id,
                        test_case_id=row.test_case_id,
                        passed=bool(row.passed),
                        time_ms=int(row.time_ms or 0),
                        memory_kb=int(row.memory_kb or 0),
                        actual_output=row.actual_output,
                        expected_output=row.expected_output,
                        diff=row.diff,
                        stderr=row.stderr,
                        message=row.message,
                    )
                )
    return SubmissionOut(
        id=submission.id,
        user_id=submission.user_id,
        problem_id=submission.problem_id,
        lesson_id=submission.lesson_id,
        challenge_id=submission.challenge_id,
        language=submission.language,
        code=submission.code or "",
        status=submission.status,
        score=int(submission.score or 0),
        passed_cases=int(submission.passed_cases or 0),
        total_cases=int(submission.total_cases or 0),
        time_ms=int(submission.time_ms or 0),
        memory_kb=int(submission.memory_kb or 0),
        error_type=submission.error_type,
        error_message=submission.error_message,
        runner=submission.runner,
        judged_by=submission.judged_by,
        created_at=submission.created_at,
        finished_at=submission.finished_at,
        results=results,
    )


def _test_case_map(db: Session, problem_id: str | None) -> dict[str, TestCase]:
    """题目的测试用例字典 `{id: TestCase}`。"""
    if not problem_id:
        return {}
    rows = db.scalars(select(TestCase).where(TestCase.problem_id == problem_id)).all()
    return {row.id: row for row in rows}


def _problem_titles(db: Session, problem_ids: list[str]) -> dict[str, str]:
    """批量查询题目标题 `{id: title}`。"""
    if not problem_ids:
        return {}
    rows = db.execute(select(Problem.id, Problem.title).where(Problem.id.in_(problem_ids))).all()
    return {str(row[0]): str(row[1]) for row in rows}


__all__ = ["router"]
