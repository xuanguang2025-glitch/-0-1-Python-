"""考试服务（`docs/API.md` §2.20）。

- 开始考试：按试卷定义生成试卷（选择 + 代码 + Debug + 编程题），服务端计时；
- 中途可保存作答（`answers_json`）；
- 交卷自动判分：客观题直接判，代码题调用判题能力（同事提供的
  `app/services/judge_service.py`，不可用时回退本机执行器按测试用例判分）。

本包按职责拆分，`__init__` 统一重导出公共 API（`from app.services import exam_service`）。
"""

from __future__ import annotations

from .common import (
    DIFFICULTY_BY_LEVEL,
    OBJECTIVE_TYPES,
    PAPER_KEY,
    is_expired as _is_expired,
    remaining_seconds as _remaining_seconds,
)
from .grading import (
    check_objective as _check_objective,
    external_judge as _external_judge,
    grade_problem,
    local_judge as _local_judge,
    normalize as _normalize,
    to_bool as _to_bool,
)
from .papers import (
    assemble_specs as _assemble_specs,
    load_questions as _load_questions,
    paper_specs as _paper_specs,
    question_out as _question_out,
)
from .attempts import (
    get_attempt as _get_attempt,
    get_exam as _get_exam,
    get_exam_detail,
    list_exams,
    paper_from_attempt as _paper_from_attempt,
    save_answers,
    start_exam,
    submit_exam,
)
from .history import get_attempt_report, list_attempts, problem_briefs

__all__ = [
    "OBJECTIVE_TYPES",
    "DIFFICULTY_BY_LEVEL",
    "PAPER_KEY",
    "grade_problem",
    "list_exams",
    "get_exam_detail",
    "start_exam",
    "save_answers",
    "submit_exam",
    "list_attempts",
    "get_attempt_report",
    "problem_briefs",
]
