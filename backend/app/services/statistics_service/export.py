"""统计报表服务 · 导出（json / csv / md）。"""

from __future__ import annotations

import csv
import io
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.learning import CodeHistory
from app.models.submission import Submission
from app.models.user import User

from .report import report


def export(db: Session, user: User, export_type: str = "report", fmt: str = "json") -> tuple[str, str, bytes]:
    """`GET /statistics/export`：返回 `(文件名, MIME, 内容字节)`。"""
    export_type = export_type if export_type in ("report", "submissions", "code") else "report"
    fmt = fmt if fmt in ("md", "csv", "json") else "json"

    if export_type == "submissions":
        rows = list(
            db.scalars(
                select(Submission).where(Submission.user_id == user.id).order_by(Submission.created_at.desc())
            ).all()
        )
        records = [
            {
                "id": r.id,
                "problem_id": r.problem_id,
                "status": r.status,
                "score": r.score,
                "passed_cases": r.passed_cases,
                "total_cases": r.total_cases,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
        return dump("submissions", records, fmt, user.username)

    if export_type == "code":
        rows = list(
            db.scalars(
                select(CodeHistory).where(CodeHistory.user_id == user.id).order_by(CodeHistory.created_at.desc())
            ).all()
        )
        records = [
            {
                "id": r.id,
                "context_type": r.context_type,
                "context_id": r.context_id,
                "file_path": r.file_path,
                "version_no": r.version_no,
                "code": r.code,
            }
            for r in rows
        ]
        return dump("code_history", records, fmt, user.username)

    report_data = report(db, user, period="month").model_dump(mode="json")
    if fmt == "md":
        body = report_markdown(report_data)
        return f"pythonlab-report-{user.username}.md", "text/markdown; charset=utf-8", body.encode("utf-8")
    payload = json.dumps(report_data, ensure_ascii=False, indent=2)
    return f"pythonlab-report-{user.username}.json", "application/json", payload.encode("utf-8")


def dump(name: str, records: list[dict], fmt: str, username: str) -> tuple[str, str, bytes]:
    """把记录列表序列化为 csv / json。"""
    if fmt == "csv":
        buffer = io.StringIO()
        if records:
            writer = csv.DictWriter(buffer, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)
        return f"pythonlab-{name}-{username}.csv", "text/csv; charset=utf-8", buffer.getvalue().encode("utf-8")
    payload = json.dumps(records, ensure_ascii=False, indent=2)
    return f"pythonlab-{name}-{username}.json", "application/json", payload.encode("utf-8")


def report_markdown(data: dict) -> str:
    """把报告字典渲染为 Markdown。"""
    lines = [
        f"# 学习报告（{data.get('period')}）",
        "",
        f"- 周期：{data.get('start_date')} ~ {data.get('end_date')}",
        "",
        str(data.get("summary_md") or ""),
        "",
        "## 亮点",
    ]
    lines += [f"- {item}" for item in (data.get("highlights") or [])] or ["- 暂无"]
    lines += ["", "## 薄弱知识点"]
    lines += [f"- {item['name']}（{item['score']}）" for item in (data.get("weak_topics") or [])] or ["- 暂无"]
    return "\n".join(lines) + "\n"
