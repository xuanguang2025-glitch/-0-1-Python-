"""通用工具包：ID、时间、文本、校验、文件、差异。

所有函数均为纯函数（不访问数据库 / 网络），便于单测与复用。
"""

from app.utils.diff import build_hunks, first_difference_line, similarity_ratio, unified_diff_text
from app.utils.files import build_zip, cleanup_dir, make_temp_dir, read_text, safe_join, write_files
from app.utils.ids import is_uuid, new_uuid, short_id
from app.utils.text import (
    collapse_blank_lines,
    excerpt,
    highlight,
    mask_email,
    normalize_output,
    slugify,
    truncate,
    truncate_bytes,
)
from app.utils.time import (
    day_range,
    format_duration,
    format_minutes,
    iso_utc,
    last_n_days,
    now_utc,
    seconds_between,
    to_utc,
    today_utc,
)
from app.utils.validators import (
    clamp_int,
    is_safe_filename,
    validate_code_size,
    validate_file_extension,
    validate_relative_path,
    validate_upload,
)

__all__ = [
    "build_hunks",
    "build_zip",
    "clamp_int",
    "cleanup_dir",
    "collapse_blank_lines",
    "day_range",
    "excerpt",
    "first_difference_line",
    "format_duration",
    "format_minutes",
    "highlight",
    "is_safe_filename",
    "is_uuid",
    "iso_utc",
    "last_n_days",
    "make_temp_dir",
    "mask_email",
    "new_uuid",
    "normalize_output",
    "now_utc",
    "read_text",
    "safe_join",
    "seconds_between",
    "short_id",
    "similarity_ratio",
    "slugify",
    "to_utc",
    "today_utc",
    "truncate",
    "truncate_bytes",
    "unified_diff_text",
    "validate_code_size",
    "validate_file_extension",
    "validate_relative_path",
    "validate_upload",
    "write_files",
]
