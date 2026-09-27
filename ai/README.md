# PYTHON LAB —— AI 接入说明

本目录存放 AI 子系统的**可读配置与提示词文档**（运行期实际提示词集中在
`backend/app/services/ai/prompts.py`，二者保持同步，即使本目录缺失也不影响服务运行）。

## 目录

```
ai/
├── README.md                      # 本文件
├── config/models.yaml             # 模型清单（能力的声明式目录）
└── prompts/
    ├── tutor_system.md            # 导师身份与总则
    ├── hint_ladder.md             # 五级提示阶梯
    ├── code_review.md             # Code Review 九维度与 JSON schema
    ├── error_analysis.md          # 报错分析模板
    ├── exam_generator.md          # 组卷与解析
    ├── mode_beginner.md           # 初学者模式
    ├── mode_standard.md           # 标准模式
    └── mode_advanced.md           # 进阶模式
```

## 接入方式

所有厂商统一通过环境变量配置（**Key 只存在于服务端环境变量**）：

```ini
AI_PROVIDER=deepseek            # deepseek/openai/qwen/zhipu/anthropic/gemini/custom
AI_MODEL=deepseek-chat
AI_BASE_URL=https://api.deepseek.com/v1
AI_API_KEY=                     # 留空 → 自动降级本地规则助手
AI_TEMPERATURE=0.3
AI_MAX_TOKENS=2048
AI_TIMEOUT_MS=30000
AI_OFFLINE=false                # true = 强制离线
AI_RATE_LIMIT_PER_HOUR=60
AI_DEFAULT_MODE=standard
AI_ALLOW_FULL_ANSWER_IN_DRILL=false
```

厂商专用 Key（`AI_API_KEY` 为空时读取）：`DEEPSEEK_API_KEY` / `OPENAI_API_KEY` /
`QWEN_API_KEY` / `ZHIPU_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY`。

## 无 Key 时（离线降级）

`AI_API_KEY` 为空、`AI_OFFLINE=true`，或远程调用超时/失败 → 自动切到
`RuleBasedProvider`，响应携带 `degraded=true`，前端显示「离线助手」徽章：

- 报错分析：识别 ≥12 种异常 + traceback 定位 + 知识点映射 + 修复步骤；
- 代码评审：九维度启发式静态检查（可变默认参数 / 裸 except / 未使用导入等）；
- 学习建议：练习生成 / 学习计划 / 测试模板 / 代码解释。

**密钥纪律**：`sk-*` 密钥绝不出现在数据库、日志、错误信息或前端响应中。
