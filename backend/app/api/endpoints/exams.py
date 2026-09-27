"""考试端点（`docs/API.md` §2.20，6 条路由 + 中途保存）。

- `GET  /exams`                        试卷列表（含我的最好成绩）
- `GET  /exams/attempts`               作答历史（分页）
- `GET  /exams/attempts/{id}`          成绩单
- `GET  /exams/{id}`                   试卷详情（不含答案）
- `POST /exams/{id}/start`             开始考试（生成试卷）
- `PUT  /exams/attempts/{id}/answers`  中途保存作答
- `POST /exams/{id}/submit`            交卷自动判分
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession, Pagination
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.exam import (
    ExamAttemptBrief,
    ExamAttemptOut,
    ExamBrief,
    ExamDetail,
    ExamReportOut,
    ExamSaveOut,
    ExamSubmitRequest,
)
from app.services import exam_service

router = APIRouter(prefix="/exams", tags=["exams"])


@router.get("", response_model=ResponseModel[list[ExamBrief]], summary="试卷列表")
def list_exams(
    db: DbSession,
    current_user: CurrentUser,
    level: str | None = Query(default=None, pattern="^(basic|intermediate|advanced)$"),
) -> dict:
    """试卷列表（基础 / 中级 / 高级），含我的最好成绩。"""
    return success_response(exam_service.list_exams(db, current_user, level=level))


@router.get("/attempts", response_model=ResponseModel[PageModel[ExamAttemptBrief]], summary="作答历史")
def list_attempts(db: DbSession, current_user: CurrentUser, pagination: Pagination) -> dict:
    """分页返回我的考试作答历史。"""
    items, total = exam_service.list_attempts(db, current_user, pagination)
    return success_response(build_page(items, total, pagination))


@router.get("/attempts/{attempt_id}", response_model=ResponseModel[ExamReportOut], summary="成绩单")
def get_attempt(attempt_id: str, db: DbSession, current_user: CurrentUser) -> dict:
    """按作答记录返回成绩单（得分 / 逐题结果 / 薄弱知识点）。"""
    return success_response(exam_service.get_attempt_report(db, current_user, attempt_id))


@router.get("/{exam_id}", response_model=ResponseModel[ExamDetail], summary="试卷详情")
def get_exam(exam_id: str, db: DbSession, current_user: CurrentUser) -> dict:
    """试卷详情（题目**不含答案**）。"""
    return success_response(exam_service.get_exam_detail(db, current_user, exam_id))


@router.post("/{exam_id}/start", response_model=ResponseModel[ExamAttemptOut], summary="开始考试")
def start_exam(exam_id: str, db: DbSession, current_user: CurrentUser) -> dict:
    """开始考试（生成试卷并服务端计时；已有未超时作答则续答）。"""
    return success_response(exam_service.start_exam(db, current_user, exam_id), message="考试已开始")


@router.put("/attempts/{attempt_id}/answers", response_model=ResponseModel[ExamSaveOut], summary="保存作答")
def save_answers(
    attempt_id: str,
    payload: ExamSubmitRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """中途保存作答（保留试卷定义）。"""
    return success_response(exam_service.save_answers(db, current_user, attempt_id, payload.answers))


@router.post("/{exam_id}/submit", response_model=ResponseModel[ExamReportOut], summary="交卷")
def submit_exam(
    exam_id: str,
    payload: ExamSubmitRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """交卷自动判分，返回成绩单（得分 / 正确率 / 薄弱知识点）。"""
    data = exam_service.submit_exam(db, current_user, exam_id, payload.model_dump())
    return success_response(data, message="已交卷")
