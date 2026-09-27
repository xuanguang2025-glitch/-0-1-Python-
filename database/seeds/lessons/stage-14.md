# 阶段 14 · 自动化

## os-automation

### 理论

用 Python 替代重复的系统操作：目录管理、文件复制/移动/删除、调用外部命令（`subprocess`）、读取系统信息。核心是把「手工步骤」写成可复用脚本。

### 代码

```python
import shutil
import subprocess
from pathlib import Path

# 目录与文件操作
Path("backup").mkdir(exist_ok=True)
shutil.copy("config.json", "backup/config.json")
shutil.make_archive("backup/archive", "zip", "backup")

# 调用外部命令（安全：列表传参，避免 shell 注入）
result = subprocess.run(["ls", "-la"], capture_output=True, text=True, check=False)
print(result.stdout[:100])
```

### 示例

```python
from pathlib import Path
import shutil

def archive_folder(folder: str, out: str) -> str:
    """把目录打包为 zip，返回压缩包路径。"""
    return shutil.make_archive(out, "zip", folder)
```

### 练习

1. 写脚本把某目录下所有 `.log` 归档到 `archive/`。
2. 用 `subprocess` 执行命令并解析输出。

### 注意事项

- 用列表传参而非 `shell=True`，防命令注入。
- 删除/移动前先确认目标，避免误删。

### 常见错误

- `shell=True` 拼接用户输入，命令注入。
- 硬编码绝对路径，换机器即失效。

## file-batch

### 理论

批量文件处理：遍历 → 过滤 → 处理 → 输出。常配合 `glob`/`rglob`、`Path`、进度提示与异常容错（单个失败不中断整体）。

### 代码

```python
from pathlib import Path

def batch_process(folder: str, ext: str = ".txt") -> dict[str, int]:
    """递归处理指定后缀文件，返回统计。"""
    stats = {"ok": 0, "failed": 0}
    for path in Path(folder).rglob(f"*{ext}"):
        try:
            content = path.read_text(encoding="utf-8")
            path.with_suffix(".bak").write_text(content, encoding="utf-8")
            stats["ok"] += 1
        except Exception:      # noqa: BLE001
            stats["failed"] += 1
    return stats
```

### 示例

```python
from pathlib import Path

def merge_txt(folder: str, output: str) -> int:
    """把目录下所有 txt 合并到一个文件。"""
    files = sorted(Path(folder).glob("*.txt"))
    with open(output, "w", encoding="utf-8") as out:
        for path in files:
            out.write(path.read_text(encoding="utf-8"))
            out.write("\n")
    return len(files)
```

### 练习

1. 批量把 CSV 转成 JSON。
2. 统计目录下各类型文件数量与总大小。

### 注意事项

- 单文件异常要捕获，避免整体中断。
- 处理前先备份或用 `--dry-run`。

### 常见错误

- 覆盖源文件导致不可恢复。
- 遍历顺序不稳定，输出难以复现。

## scheduling-task

### 理论

定时任务按周期执行脚本：系统级用 cron（Linux）/任务计划程序（Windows），Python 内用 `schedule` 或 APScheduler，也可用 `while + sleep` 简易实现。

### 代码

```python
import time
from datetime import datetime

def run_task() -> None:
    """示例任务。"""
    print(f"[{datetime.now():%H:%M:%S}] 执行任务")

def simple_scheduler(interval: int = 60) -> None:
    """简易周期调度（阻塞式）。"""
    while True:
        run_task()
        time.sleep(interval)
```

```bash
# Linux cron：每天 02:00 执行
# 0 2 * * * /usr/bin/python3 /path/to/job.py >> /var/log/job.log 2>&1
```

### 示例

```python
try:
    import schedule
except ImportError:
    schedule = None

if schedule:
    schedule.every().day.at("02:00").do(run_task)
    # while True: schedule.run_pending(); time.sleep(1)
```

### 练习

1. 用 `schedule` 写一个每 10 秒执行的任务。
2. 把脚本配置为系统定时任务。

### 注意事项

- 长任务加日志与异常捕获，避免静默失败。
- 注意时区与夏令时（优先 UTC）。

### 常见错误

- 任务抛异常导致调度器退出。
- 多实例重复执行同一任务。

## excel-automation

### 理论

用 `openpyxl` 读写 Excel：创建工作簿、读写单元格、公式、样式。`pandas` 也可批量处理表格并导出。适合报表、数据汇总自动化。

### 代码

```python
from openpyxl import Workbook

wb = Workbook()
ws = wb.active
ws.title = "成绩"
ws.append(["姓名", "成绩"])
for name, score in [("张三", 95), ("李四", 88)]:
    ws.append([name, score])

ws["C1"] = "是否及格"
ws["C2"] = "=IF(B2>=60,\"是\",\"否\")"
wb.save("scores.xlsx")
```

### 示例

```python
from openpyxl import load_workbook

def read_column(path: str, column: str = "A") -> list:
    """读取某列全部非空值。"""
    wb = load_workbook(path, read_only=True)
    ws = wb.active
    return [cell.value for cell in ws[column] if cell.value is not None]
```

### 练习

1. 生成一个含公式的统计表。
2. 读取 Excel 并做汇总计算后写回。

### 注意事项

- 大文件用 `read_only=True` 省内存。
- 公式写入字符串，由 Excel 计算。

### 常见错误

- 未安装 `openpyxl` 直接 `import`。
- 写入中文未注意编码（xlsx 一般无此问题）。

## email-automation

### 理论

用 `smtplib` + `email` 标准库发送邮件：构造 `MIMEText`/`MIMEMultipart`，用 SMTP 服务器发送。支持纯文本、HTML、附件。

### 代码

```python
import smtplib
from email.mime.text import MIMEText
from email.header import Header

def send_mail(host: str, user: str, password: str, to: str, subject: str, body: str) -> None:
    """发送纯文本邮件。"""
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = user
    msg["To"] = to
    msg["Subject"] = Header(subject, "utf-8")
    with smtplib.SMTP_SSL(host, 465, timeout=10) as server:
        server.login(user, password)
        server.sendmail(user, [to], msg.as_string())
```

### 示例

```python
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

msg = MIMEMultipart()
# msg.attach(...) 添加正文
# part = MIMEApplication(open("report.pdf", "rb").read()); msg.attach(part) 添加附件
```

### 练习

1. 发送一封含 HTML 正文的邮件。
2. 给邮件添加附件。

### 注意事项

- 邮箱密码用「授权码」或环境变量。
- 加超时，避免阻塞。

### 常见错误

- 明文写入邮箱密码。
- 未设超时导致连接挂起。

## log-parsing

### 理论

日志解析进阶：批量解析多文件、按时间/等级聚合、生成日报/报表。结合正则、`datetime` 与 `collections.Counter`/`defaultdict`。

### 代码

```python
import re
from collections import Counter
from pathlib import Path

LINE_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2}).*\[(?P<level>\w+)\]")

def summarize(folder: str) -> dict[str, Counter]:
    """按日期统计各等级日志条数。"""
    result: dict[str, Counter] = {}
    for path in Path(folder).glob("*.log"):
        for line in path.read_text(encoding="utf-8").splitlines():
            m = LINE_RE.match(line)
            if m:
                result.setdefault(m["date"], Counter())[m["level"]] += 1
    return result
```

### 示例

```python
def top_errors(lines: list[str], n: int = 5) -> list[tuple[str, int]]:
    """统计出现最多的错误消息。"""
    counter: Counter = Counter()
    for line in lines:
        if "[ERROR]" in line:
            counter[line.split("] ", 1)[-1].strip()] += 1
    return counter.most_common(n)
```

### 练习

1. 生成「每日错误数」报表。
2. 找出错误率突增的日期。

### 注意事项

- 大文件逐行处理，避免内存问题。
- 时间字段统一格式便于排序。

### 常见错误

- 正则未锚定，误匹配多行。
- 忽略时区导致时间聚合错误。

## web-scraping

### 理论

网页抓取获取公开数据：`requests` 取页面，`BeautifulSoup`/`lxml` 解析 HTML，`css` 选择器提取字段。务必遵守 robots、限速、仅抓公开数据。

### 代码

```python
import requests
from bs4 import BeautifulSoup

def fetch_titles(url: str) -> list[str]:
    """抓取页面所有 h2 标题文本。"""
    resp = requests.get(url, timeout=10, headers={"User-Agent": "pythonlab/1.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return [h.get_text(strip=True) for h in soup.select("h2")]
```

### 示例

```python
import requests
from bs4 import BeautifulSoup

def parse_table(html: str) -> list[dict]:
    """把表格解析为字典列表。"""
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table tr")
    header = [th.get_text(strip=True) for th in rows[0].select("th")]
    return [dict(zip(header, (td.get_text(strip=True) for td in r.select("td")))) for r in rows[1:]]
```

### 练习

1. 抓取一个列表页的标题与链接。
2. 解析 HTML 表格转为结构化数据。

### 注意事项

- 遵守 robots.txt 与频率限制。
- 加 `User-Agent`，礼貌抓取。

### 常见错误

- 高频抓取被封禁。
- 硬编码易变的 CSS 选择器。

## report-generation

### 理论

报表生成把数据转成可交付结果：文本/CSV/Excel/HTML/PDF。流程：取数 → 计算 → 渲染模板 → 导出。适合日报、周报自动化。

### 代码

```python
from datetime import datetime
from pathlib import Path

TEMPLATE = """# 数据日报 {date}

- 新增用户：{new_users}
- 活跃用户：{active}
- 错误数：{errors}
"""

def render_report(date: str, stats: dict[str, int]) -> str:
    """渲染 Markdown 报表。"""
    return TEMPLATE.format(date=date, **stats)

report = render_report(datetime.now().strftime("%Y-%m-%d"),
                       {"new_users": 12, "active": 340, "errors": 2})
Path("report.md").write_text(report, encoding="utf-8")
print(report)
```

### 示例

```python
import csv

def export_csv(rows: list[dict], path: str, fields: list[str]) -> None:
    """导出字典列表为 CSV。"""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
```

### 练习

1. 生成一份含表格的 HTML 报表。
2. 把统计结果导出为 Excel。

### 注意事项

- 模板与数据分离，便于调整格式。
- 报表加入生成时间与数据来源。

### 常见错误

- 直接在代码里拼大段 HTML 字符串。
- 数字未格式化（小数位、千分位）。

## workflow-orchestration

### 理论

流程编排把多个自动化步骤串成流水线：取数 → 清洗 → 分析 → 导出 → 通知，并处理依赖、失败重试、日志。可用简单函数串联，也可用 Airflow/Prefect 等。

### 代码

```python
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

def run_pipeline(steps: list[tuple[str, Callable[[dict], dict]]]) -> dict:
    """按顺序执行步骤，任一步失败即中止并记录。"""
    context: dict = {}
    for name, step in steps:
        try:
            context = step(context)
            logger.info("步骤完成: %s", name)
        except Exception:
            logger.exception("步骤失败: %s", name)
            raise
    return context

steps = [
    ("取数", lambda ctx: {**ctx, "raw": [1, 2, 3]}),
    ("清洗", lambda ctx: {**ctx, "clean": [x for x in ctx["raw"] if x > 0]}),
    ("统计", lambda ctx: {**ctx, "total": sum(ctx["clean"])}),
]
print(run_pipeline(steps))
```

### 示例

```python
# 步骤可插拔：新增「通知」步骤只需加一个函数
def notify(ctx: dict) -> dict:
    print(f"完成，合计 {ctx.get('total')}")
    return ctx

# run_pipeline([... , ("通知", notify)])
```

### 注意事项

- 每步职责单一、输入输出明确。
- 失败要可观测（日志 + 中止）。

### 常见错误

- 步骤间隐式依赖全局变量。
- 出错后静默继续，脏数据向下传。
