# 安全验证脚本（QA 攻击面回归资产）

本目录存放 QA 在渗透测试中沉淀的**攻击面回归脚本**。它们不是 pytest 用例
（文件名不以 `test_` 开头，`pytest tests/` 不会收集），而是可重复执行的
「攻击输入 → 实际响应」证据生成器：每次改安全相关代码后跑一遍，用输出对比
确认防线没有被无意削弱。

## 运行方式

统一在 `backend/` 目录下执行（脚本内部自行处理 `sys.path`）：

```bash
cd backend

# 沙箱 AST 白名单：47 种绕过手法 + 反向误杀检查（只读，不改任何源码）
.venv/Scripts/python.exe scripts/security/qa_ast_verify.py

# 逃逸影响证明：chdir / pathlib / makedirs / 保留名，用「工作目录外是否出现
# 证明文件」验证是否真逃逸；结尾附 3 条真实误杀最小复现
.venv/Scripts/python.exe scripts/security/qa_ast_confirm.py

# 保留名 P0 的决定性对比：同一载荷放 main.py / _plab_guard.py /
# __plab_boot__.py，验证唯一差别（文件名）不再导致免检执行
.venv/Scripts/python.exe scripts/security/qa_reserved_name.py

# 认证与越权面验证
.venv/Scripts/python.exe scripts/security/qa_auth_verify.py

# 测试覆盖缺口检查
.venv/Scripts/python.exe scripts/security/qa_coverage_gap.py

# kill-the-test：对 conftest.py 做 5 种定向破坏，验证守护用例真的在守护，
# 结束后按字节还原并复跑确认回绿（会临时改动 conftest.py，勿在运行时中断）
.venv/Scripts/python.exe scripts/security/qa_killtest.py
```

退出码：`0` = 全部通过；非 0 = 存在 FAIL（脚本内以 `[PASS]` / `[FAIL]` 标注）。

## 与 pytest 套件的关系

- 这些脚本覆盖的攻击面**同时**有对应的 pytest 回归用例（`tests/test_sandbox_security.py`、
  `tests/test_sandbox_reserved_name.py`、`tests/test_jwt_secret_policy.py`、
  `tests/test_client_ip_trust.py`）——CI 跑 pytest 即可守住底线；
- 本目录脚本的价值在于**人工复核时的可读证据**（每个攻击输入打印实际响应），
  以及 pytest 不便表达的破坏性验证（如 kill-the-test 需要临时改夹具）。

## 安全注意

- 所有写操作都写到系统 TEMP 目录，脚本结束前自行清理；不触碰真实数据库
  （`data/pythonlab.db`）与项目文件；
- `qa_killtest.py` 会临时修改 `tests/conftest.py`，运行期间不要中断；
- 需要先启动服务的是 `qa_live_probe.py` / `qa_sandbox_deep.py`（仍在
  `backend/tests/` 下，面向已部署实例的 HTTP 探测）。
