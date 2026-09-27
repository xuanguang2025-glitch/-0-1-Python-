"""用户端点（`docs/API.md` §2.2，8 条路由）。"""

from __future__ import annotations

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import Response

from app.core.deps import CurrentUser, DbSession, OptionalUser
from app.core.response import ResponseModel, success_response
from app.schemas.common import MessageOut
from app.schemas.user import (
    AvatarOut,
    DeleteAccountRequest,
    PreferencesUpdateRequest,
    ProfileOut,
    ProfileUpdateRequest,
    PublicUserOut,
    UserOverviewOut,
)
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/profile", response_model=ResponseModel[ProfileOut], summary="我的资料")
def get_my_profile(db: DbSession, current_user: CurrentUser) -> dict:
    """获取当前用户资料（缺失时自动补建）。"""
    profile = user_service.get_profile(db, current_user)
    return success_response(ProfileOut.model_validate(profile))


@router.patch("/me/profile", response_model=ResponseModel[ProfileOut], summary="更新我的资料")
def update_my_profile(
    payload: ProfileUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """更新昵称 / 头像链接 / 简介 / 时区。"""
    return success_response(user_service.update_profile(db, current_user, payload), message="资料已更新")


@router.post("/me/avatar", response_model=ResponseModel[AvatarOut], summary="上传头像")
async def upload_avatar(
    db: DbSession,
    current_user: CurrentUser,
    file: UploadFile = File(..., description="jpg/png/webp，≤2MB"),
) -> dict:
    """上传头像（MIME 与大小严格校验），返回可访问路径。"""
    url = await user_service.save_avatar(db, current_user, file)
    return success_response(AvatarOut(avatar_url=url), message="头像已更新")


@router.patch("/me/preferences", response_model=ResponseModel[ProfileOut], summary="更新偏好")
def update_preferences(
    payload: PreferencesUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """更新 AI 模式 / 学习模式 / 主题 / 每周目标。"""
    return success_response(user_service.update_preferences(db, current_user, payload), message="偏好已更新")


@router.get("/me/overview", response_model=ResponseModel[UserOverviewOut], summary="学习概览")
def get_overview(db: DbSession, current_user: CurrentUser) -> dict:
    """首页仪表盘数据（经验 / 等级 / 连续天数 / 完成课时 / 解题数 / 今日时长）。"""
    return success_response(user_service.get_overview(db, current_user))


@router.get("/me/export", summary="导出学习数据")
def export_me(
    db: DbSession,
    current_user: CurrentUser,
    format: str = Query(default="json", pattern="^(json|zip)$"),
) -> Response:
    """导出学习数据（json / zip），通过 `Content-Disposition` 返回文件名。"""
    filename, content_type, payload = user_service.export_learning_data(db, current_user, format)
    return Response(
        content=payload,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/me", response_model=ResponseModel[MessageOut], summary="注销账号（软删除）")
def delete_me(payload: DeleteAccountRequest, db: DbSession, current_user: CurrentUser) -> dict:
    """软删除当前账号（需再次输入密码确认）。"""
    user_service.delete_account(db, current_user, payload.password)
    return success_response(MessageOut(message="账号已注销"), message="账号已注销")


@router.get("/{user_id}/public", response_model=ResponseModel[PublicUserOut], summary="公开资料")
def get_public_profile(user_id: str, db: DbSession, _viewer: OptionalUser = None) -> dict:
    """公开资料：**仅昵称与等级**，不暴露任何联系方式。"""
    return success_response(user_service.get_public_user(db, user_id))
