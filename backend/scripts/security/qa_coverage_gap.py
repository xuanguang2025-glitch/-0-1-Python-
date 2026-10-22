"""QA：后端 API 路径覆盖盲区分析（快照式，静态提取 + 模板通配匹配）。

注意：仓库中有其他工程师在并行新增测试文件，本脚本结果为**某一时刻的快照**。
"""

from __future__ import annotations

import collections
import glob
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.main import app

METHODS = {"get", "post", "put", "patch", "delete"}


def clean(path: str) -> str:
    """去掉查询串与末尾斜杠，并把 {API} 变量前缀还原成 /api。"""
    path = path.split("?", 1)[0]
    path = re.sub(r"^\{API\}", "/api", path)
    path = re.sub(r"^API", "/api", path)
    path = re.sub(r"/+", "/", path)
    return path.rstrip("/") or "/"


def template_matches(template: str, actual: str) -> bool:
    """OpenAPI 模板按段匹配：模板里的 {x} 段可匹配实际路径的任意单段。"""
    t = clean(template).split("/")
    a = clean(actual).split("/")
    if len(t) != len(a):
        return False
    for seg_t, seg_a in zip(t, a, strict=False):
        if seg_t.startswith("{") and seg_t.endswith("}"):
            continue
        if seg_t != seg_a:
            return False
    return True


def main() -> None:
    spec = app.openapi()
    called: list[tuple[str, str]] = []  # (verb, path)
    for name in sorted(glob.glob("tests/test_*.py")):
        if "qa_" in name:
            continue  # 排除 QA 自己的探测脚本
        src = Path(name).read_text(encoding="utf-8")
        for match in re.finditer(r"""\.(get|post|put|patch|delete)\(\s*f?["']([^"']*)["']""", src):
            called.append((match.group(1), clean(match.group(2))))

    zero: list[tuple[str, list[str]]] = []
    for path in sorted(spec["paths"]):
        verbs = [v for v in spec["paths"][path] if v.lower() in METHODS]
        hit = [v for v in verbs if any(cv == v and template_matches(path, cp) for cv, cp in called)]
        if not hit:
            zero.append((path, verbs))

    total = len(spec["paths"])
    print(f"总路径 {total} | 零覆盖 {len(zero)} | 路径覆盖率 {(1 - len(zero) / total) * 100:.1f}%")
    dom = collections.Counter("/".join(p.split("/")[:3]) for p, _ in zero)
    print("\n=== 零覆盖按域 ===")
    for key, val in dom.most_common():
        print(f"  {val:3d}  {key}")
    print("\n=== 零覆盖明细 ===")
    for path, verbs in zero:
        print(f"  {','.join(v.upper() for v in verbs):18s} {path}")


if __name__ == "__main__":
    main()
