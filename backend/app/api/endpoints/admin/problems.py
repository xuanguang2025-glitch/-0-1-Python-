"""管理端端点 · 题目 / 测试用例。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Body, File, Query, Request, UploadFile

from app.core.deps import AdminUser, DbSession, Pagination
from app.core.pagination import build_page
from app.core.response import PageModel, ResponseModel, success_response
from app.schemas.problem import AdminProblemIn, AdminTestCaseIn, ProblemBrief
from app.services import admin_service

from ._common import meta

router = APIRouter()


@router.get("/problems", response_model=ResponseModel[PageModel[ProblemBrief]], summary="题目列表")
def list_problems(
    db: DbSession,
    admin: AdminUser,
    pagination: Pagination,
    q: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    category: str | None = Query(default=None),
) -> dict:
    """题目列表。"""
    items, total = admin_service.list_problems(db, pagination, q=q, difficulty=difficulty, category=category)
    return success_response(build_page([ProblemBrief.model_validate(p) for p in items], total, pagination))


@router.post("/problems", response_model=ResponseModel[ProblemBrief], summary="新建题目")
def create_problem(payload: AdminProblemIn, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """新建题目（含测试用例）。"""
    problem = admin_service.create_problem(db, admin, payload.model_dump(), meta(request))
    return success_response(ProblemBrief.model_validate(problem), message="题目已创建")


@router.patch("/problems/{problem_id}", response_model=ResponseModel[ProblemBrief], summary="更新题目")
def update_problem(
    problem_id: str, request: Request, db: DbSession, admin: AdminUser, payload: dict[str, Any] = Body(...)
) -> dict:
    """更新题目。"""
    problem = admin_service.update_problem(db, admin, problem_id, payload, meta(request))
    return success_response(ProblemBrief.model_validate(problem), message="题目已更新")


@router.delete("/problems/{problem_id}", response_model=ResponseModel[None], summary="删除题目")
def delete_problem(problem_id: str, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """删除题目。"""
    admin_service.delete_problem(db, admin, problem_id, meta(request))
    return success_response(None, message="题目已删除")


@router.post("/problems/import", response_model=ResponseModel[dict], summary="批量导入题目")
async def import_problems(
    request: Request,
    db: DbSession,
    admin: AdminUser,
    file: UploadFile = File(..., description="JSON 文件（数组或 {items: []}）"),
) -> dict:
    """批量导入题目（multipart JSON），返回 `{created, updated, failed}`。"""
    payload = json.loads((await file.read()).decode("utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else payload
    result = admin_service.import_problems(db, admin, list(items or []), meta(request))
    return success_response(result)


@router.post("/test-cases", response_model=ResponseModel[dict], summary="新建测试用例")
def create_test_case(payload: AdminTestCaseIn, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """新建测试用例。"""
    case = admin_service.create_test_case(db, admin, payload.model_dump(), meta(request))
    return success_response({"id": case.id}, message="测试用例已创建")


@router.patch("/test-cases/{case_id}", response_model=ResponseModel[dict], summary="更新测试用例")
def update_test_case(
    case_id: str, request: Request, db: DbSession, admin: AdminUser, payload: dict[str, Any] = Body(...)
) -> dict:
    """更新测试用例。"""
    case = admin_service.update_test_case(db, admin, case_id, payload, meta(request))
    return success_response({"id": case.id}, message="测试用例已更新")


@router.delete("/test-cases/{case_id}", response_model=ResponseModel[None], summary="删除测试用例")
def delete_test_case(case_id: str, request: Request, db: DbSession, admin: AdminUser) -> dict:
    """删除测试用例。"""
    admin_service.delete_test_case(db, admin, case_id, meta(request))
    return success_response(None, message="测试用例已删除")
