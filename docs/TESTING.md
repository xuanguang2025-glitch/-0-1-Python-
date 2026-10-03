# PYTHON LAB —— 前端测试基座设计（增量）

> 版本：v1.0 ｜ 架构师：高见远（Gao） ｜ 状态：可直接执行
> 适用版本：Next.js 15.1 + React 19 + TypeScript 5.7 + Tailwind 3.4（见 `frontend/package.json`）
> 现状：31 个页面、0 个测试。本设计目标是用**最小依赖、零外部服务**的方式覆盖高风险逻辑。

---

## 0. 结论先行（TL;DR）

| 项 | 决断 |
|---|---|
| 框架 | **Vitest 3.x**（不用 Jest，不用 Playwright） |
| 组件测试 | **@testing-library/react 16.x**（React 19 兼容） |
| 网络 mock | **手写 `fetch` stub**，**不引入 msw**（第 1–3 步完全够用） |
| 环境 | `jsdom`（仅需 DOM 的测试）+ `node`（纯函数测试）双环境 |
| 第 1 步产出 | **4 个测试文件、约 46 条断言**，覆盖 XSS 转义与 401 单飞刷新两条安全红线 |
| 不做 | Playwright e2e、视觉回归、性能测试、覆盖率门槛（理由见 §1.4） |
| 新增依赖 | 6 个 devDependency，全部走 npmmirror |

---

## 1. 测试分层策略

### 1.1 分层与优先级

| 层 | 目标 | 优先级 | 文件数 | 断言数（估） |
|---|---|---|---|---|
| **L1 纯函数** | 无 DOM、无网络，秒级 | **P0** | 4 | ~46 |
| **L2 网络契约** | `lib/api.ts` 单飞刷新 / 错误解包 / blob | **P0** | 1 | ~14 |
| **L3 Hook 状态机** | `usePythonRunner` 等状态流转 | P1 | 2 | ~10 |
| **L4 组件渲染** | 安全渲染与关键交互 | P1 | 2 | ~8 |
| **L5 页面级** | 31 个页面的集成 | **P2（暂不做）** | 0 | 0 |

### 1.2 L1 纯函数（P0，先做）

| 目标 | 理由 |
|---|---|
| `lib/highlight.ts` | **全站唯一 `dangerouslySetInnerHTML` 的数据源**（`SECURITY.md` §2.1）。转义一旦回退就是可直接利用的 XSS。**必须第一个写测试。** |
| `lib/api.ts`（`ApiRequestError` / `buildUrl` 行为） | 错误码是前后端契约，回归成本高 |
| `lib/format.ts` | `extractErrorLine` 直接影响判题错误定位；`formatPython` 影响用户看到的代码 |
| `lib/utils.ts` | `formatDuration` / `formatMemory` / `parseFilename` 等纯展示函数，边际收益高、无 flaky 风险 |

### 1.3 L2/L3/L4（P0/P1）

| 层 | 目标 | 理由 |
|---|---|---|
| L2 | `lib/api.ts` 的 **401 单飞刷新**：并发 401 只触发一次 `/auth/refresh`、重试仅一次、刷新失败清理登录态 | 这是全站最复杂的并发逻辑，文档 `API.md` §5.2 明确承诺「单飞」，一旦破坏会导致 refresh 风暴与登态错乱。**bug 概率高、后果严重、测试成本低** → 必测 |
| L3 | `usePythonRunner`（running 态、错误态、reset）、`useDebounce`（防抖时序） | 状态机逻辑，renderHook 可测，成本低 |
| L4 | `code-block.tsx`（渲染结果不含可执行 `<script>`）、`markdown.tsx`（原始 HTML 不渲染） | 与 §1.2 呼应：验证「转义 + 不启用 rehype-raw」在**组件层**同样成立，形成纵深防御 |

### 1.4 明确「不测什么」（重要）

| 不测 | 理由 |
|---|---|
| **31 个页面的整体渲染** | 页面多为 `<PageHeader>` + 列表 + 分页的同构壳。为它们写 RTL 断言只会产出 31 个「能渲染且不崩溃」的无价值测试，重构即碎。**页面正确性改由类型系统 + 后端契约 + 人工冒烟保证。** |
| **视觉样式 / 响应式断点** | 需要视觉回归基建（Playwright snapshot），收益低、波动大（Tailwind 类名变动即误报）。**明确推到第二阶段。** |
| **`@monaco-editor/react` 集成** | Monaco 依赖 Web Worker + WASM + 真实布局，jsdom 下无法渲染（会抛错）。测试价值为零。**用 mock 把它整个替换掉。** |
| **Recharts 图表** | 断言 SVG path 的 d 属性是脆的。应改为断言「传入了正确的 data 数组」——但那实际上是在测 recharts，故**跳过**。 |
| **覆盖率数字门槛** | 不设 `coverage.thresholds`。31 页项目强行卡 80% 会催生大量「断言调用次数」的水测试。**用下面的「红线清单」代替覆盖率指标。** |
| **后端已覆盖的逻辑** | 判题、掌握度算法等在后端有 97 个 pytest 用例，前端重复测是浪费。 |
| **Playwright e2e** | 需要起 dev server（Next 15 冷启动 30s+）且本机无 Docker、需后端在线才能跑通登录流。**第二阶段再做**，且只覆盖 3 条主干（见 §8）。 |

### 1.5 替代覆盖率的红线清单

CI 只需保证：**下面 6 条断言永远存在且通过**。这是本项目的「不可回归清单」。

1. `highlightCode('<script>alert(1)</script>')` 输出**不含裸 `<`**
2. `highlightCode("s = '<img onerror=x>'")` 输出**不含裸 `<`**
3. `highlightCode('x = "a" and 1 < 2')` 中 `<` 被转义为 `&lt;`（运算符识别不破坏转义）
4. 3 个并发 401 → `/auth/refresh` **只被调用 1 次**
5. 刷新成功后原请求**只重试 1 次**并成功
6. `code-block.tsx` 渲染 `<script>` 源码后，`container.querySelector('script')` 为 `null`

---

## 2. 框架选型与理由

### 2.1 Vitest vs Jest

| 维度 | **Vitest** | Jest |
|---|---|---|
| 与 Vite/Next 15 的关系 | 与 `next.config.ts` 同源，共享 TS 转换管线，**零额外 babel/ts-jest 配置** | 需 `next/jest` + SWC 额外配置，多一层 |
| ESM 支持 | 原生一等公民。本项目 `tsconfig` 是 `"module": "esnext"` + `"moduleResolution": "bundler"` | ESM 支持仍需实验开关 |
| `jsdom` 环境 | `environment: 'jsdom'` 一行配置 | 需额外装 `jest-environment-jsdom` |
| 速度 | 并行 worker，启动快 | 慢 |
| React 19 兼容 | `@testing-library/react@16` 官方支持；Vitest 对 React 无特殊耦合 | 同（问题不在 Jest 本身） |
| 结论 | ✅ **选它** | ❌ |

> 关键理由一句话：**Vitest 不需要新增任何转译配置**。Jest 需要 `next/jest` 包装器 + SWC 转换，遇到 `next.config.ts` 里的自定义 webpack 逻辑容易出摩擦。

### 2.2 msw vs 手写 fetch stub

| 方案 | 结论 |
|---|---|
| msw@2 | ❌ 本阶段不引入。理由：本项目 API 层已高度封装（**所有请求都收敛到 `lib/api.ts` 的 `rawRequest`**，组件内禁止直接 fetch，见该文件头注释 §1）。既然只有一个调用点，直接 `vi.stubGlobal('fetch', mockFn)` 即可断言「URL、方法、Header、Body、重试次数」。msw 的价值在于「就近拦截任意组件的请求」，本项目不存在这个场景。 |
| 手写 stub | ✅ 采用。`tests/helpers/fetch-mock.ts` 提供 `mockFetchOnce` / `mockFetchSequence` / `jsonResponse` 三个小工具。 |

> **决策留口**：若将来出现绕过 `lib/api.ts` 的第三方请求（如 SDK 直连），再引入 msw，届时只需改 L2 一处。

### 2.3 依赖清单（精确版本区间）

```jsonc
// frontend/package.json → devDependencies 新增
{
  "vitest":                 "^3.2.4",     // 与 Vite 6 兼容；4.x 尚需评估
  "@vitest/coverage-v8":    "^3.2.4",     // 可选，第 3 步再装
  "jsdom":                  "^26.0.0",    // Node 18+ 对应版本线
  "@testing-library/react": "^16.3.0",    // ★ 必须是 16.x：15.x 不支持 React 19
  "@testing-library/dom":    "^10.4.0",    // 16.x 的 peer
  "@testing-library/user-event": "^14.6.1",
  "@testing-library/jest-dom": "^6.6.3"   // 断言扩展（toBeInTheDocument 等）
}
```

> ⚠️ **版本陷阱（必须注意）**：`@testing-library/react@14/15` 的 peerDependencies 是 `react ^18`，在 React 19 下会 **ERESOLVE 装不上**。必须用 `^16.3.0`。
> ⚠️ 本机当前 Node 为 **v22.22.2**（满足要求），`engines.node` 现为 `>=18.18.0` 保持不变。

### 2.4 安装命令（Windows + npmmirror）

```powershell
cd D:\徐浩然\2026-09-26-21-55-08\python-learning-platform\frontend

# 1) 一次性写入国内镜像（当前无 .npmrc，必须先建）
#    注意：路径是 .npmrc（不是 npmrc），npm 才会识别
npm config set registry https://registry.npmmirror.com
#    等价于在 frontend/ 下创建 .npmrc，内容：registry=https://registry.npmmirror.com

# 2) 安装
npm install -D vitest@^3.2.4 jsdom@^26.0.0 `
  @testing-library/react@^16.3.0 @testing-library/dom@^10.4.0 `
  @testing-library/user-event@^14.6.1 @testing-library/jest-dom@^6.6.3

# 3) 可选（第 3 步再装）
# npm install -D @vitest/coverage-v8@^3.2.4

# 4) 验证
npx vitest --version
```

> 网络慢时的兜底：`npm install --prefer-offline --no-audit --no-fund`。若仍超时，先只装 `vitest + jsdom`（L1/L2 不需要 RTL），跑通后再补 RTL。

---

## 3. 配置文件清单

### 3.1 新增文件（共 5 个）

| 文件 | 作用 |
|---|---|
| `frontend/vitest.config.mts` | Vitest 主配置（**注意用 `.mts`**，与 `next.config.ts` 不冲突） |
| `frontend/tests/setup.ts` | 全局 setup：jest-dom 扩展、清理函数、固定时区 |
| `frontend/tests/helpers/fetch-mock.ts` | fetch stub 工具 + 统一响应构造 |
| `frontend/tests/helpers/factories.ts` | 测试数据工厂（`makeTokenPair` / `makeRunResponse` / `makeProblem`） |
| `frontend/.npmrc` | `registry=https://registry.npmmirror.com` |

### 3.2 `vitest.config.mts` 完整内容（可直接复制）

```ts
/// <reference types="vitest/config" />
import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  test: {
    // ---- 环境 ----
    // 默认 node（纯函数测试零开销），需要 DOM 的测试在文件顶部用
    // @vitest-environment jsdom 单独声明，避免为纯函数付出 jsdom 启动代价
    environment: 'node',
    globals: true,                 // 提供 describe/it/expect 全局，免去每个文件 import
    setupFiles: ['./tests/setup.ts'],

    // ---- 路径别名：必须与 tsconfig.json 的 "@/*": ["./src/*"] 保持一致 ----
    // 两种写法都写上：alias 供 Vite 解析，tsconfigPaths 供编辑器/类型
    alias: [{ find: /^@\//, replacement: fileURLToPath(new URL('./src/', import.meta.url)) }],

    // ---- 包含 / 排除 ----
    include: ['tests/**/*.test.{ts,tsx}'],   // 只收 tests/ 目录，不侵入 src/
    exclude: [
      'node_modules/**',
      '.next/**',            // next build 产物
      '.next-dev/**',        // next dev 产物（本项目自定义 distDir）
      '.next-verify/**',     // 隔离验证构建产物
      'out/**',
      'coverage/**',
      '**/*.d.ts',
    ],

    // ---- 行为 ----
    css: false,                // 不处理 CSS import，Tailwind 相关 import 直接忽略
    restoreMocks: true,        // 每个用例后自动 restoreMocks，避免 spy 泄漏
    clearMocks: true,
    mockReset: true,
    unstubEnvs: true,
    unstubGlobals: true,       // ★ 关键：自动还原 vi.stubGlobal('fetch', ...)
    environmentOptions: {
      jsdom: { url: 'http://localhost:3000' },   // 固定 origin，便于断言相对 URL
    },

    // ---- 性能 ----
    testTimeout: 5000,
    hookTimeout: 10000,
    pool: 'threads',           // 默认；避免 forks 在 Windows 上更慢
    reporters: ['default'],
  },
});
```

> **要点说明**
> - **别名双保险**：`alias` 让 Vite 在运行期正确解析 `@/lib/api`；`tsconfig.json` 里已有 `paths`，编辑器与 `tsc --noEmit` 不受影响。**不要**用 `vite-tsconfig-paths` 插件（多一个依赖，本项目别名只有一个 `@/*`，手写足够）。
> - **`unstubGlobals: true`**：这是本设计能不做手工 teardown 的关键。开启后 `vi.stubGlobal` 会在每个用例后自动还原。
> - **`exclude` 必须含 `.next-verify`**：`tsconfig.json` 里已有这个自定义 distDir，容易遗漏。
> - **环境按需声明**：`highlight.test.ts` / `format.test.ts` / `utils.test.ts` 用默认 `node`；`api.test.ts`、`code-block.test.tsx` 加 `// @vitest-environment jsdom` 首行注释。

### 3.3 `tests/setup.ts` 完整内容

```ts
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, beforeAll, vi } from 'vitest';

/** 固定时区与基准时刻，避免 formatRelativeTime 断言随时钟漂移。 */
const FIXED_NOW = new Date('2026-09-27T10:00:00Z');

beforeAll(() => {
  // 固定为 UTC：CI 与本机时区不同会导致日期格式化断言飘红
  process.env.TZ = 'UTC';
  // 统一「现在」：所有依赖当前时间的函数都读它
  vi.useFakeTimers({ toFake: ['Date', 'performance'] });
  vi.setSystemTime(FIXED_NOW);
});

afterEach(() => {
  cleanup();                 // 卸载 React 树
  vi.clearAllTimers();
  vi.useRealTimers();
});
```

> ⚠️ **不要用 `vi.useFakeTimers()` 全量开**：`@testing-library` 与 user-event 依赖 `queueMicrotask`/定时器，全量 fake 会让 `waitFor` 挂死。上例只 fake 了 `Date` 与 `performance`，是经过验证的折中。
> ⚠️ 若某个测试需要真实定时器（如防抖），在该测试内用 `vi.useFakeTimers()` 局部开启，`finally` 里 `useRealTimers()`。

### 3.4 `tests/helpers/fetch-mock.ts` 完整内容

```ts
import { vi } from 'vitest';

/** 构造统一响应结构的 Response 替身。 */
export function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: new Headers({ 'Content-Type': 'application/json' }),
    text: async () => JSON.stringify(body),
    json: async () => body,
    blob: async () => new Blob([JSON.stringify(body)]),
    clone() { return this; },
  } as unknown as Response;
}

/** 统一成功信封。 */
export const ok = <T>(data: T, message = '') =>
  jsonResponse({ success: true, data, message, error: null });

/** 统一失败信封（对齐 docs/API.md §4）。 */
export const err = (code: string, message = '失败', status = 400, details: unknown = null) =>
  jsonResponse({ success: false, data: null, message, error: { code, details } }, status);

/** 按调用顺序返回预设响应；用完则抛错以暴露「多发/少发请求」。 */
export function mockFetchSequence(responses: Response[]) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const fn = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    const next = responses[calls.length - 1];
    if (!next) throw new Error(`fetch 调用次数超出预期：第 ${calls.length + 1} 次`);
    return next;
  });
  vi.stubGlobal('fetch', fn);
  return { fn, calls };
}

/** 永远 401 + 可刷新错误码，用于测单飞刷新。 */
export const unauthorized = () => err('TOKEN_EXPIRED', '登录已过期', 401);
```

### 3.5 `frontend/package.json` 需追加的 scripts

```jsonc
{
  "scripts": {
    // ...已有保持不动
    "test": "vitest run",
    "test:watch": "vitest",
    "test:ui": "vitest --ui",
    "test:coverage": "vitest run --coverage"
  }
}
```

### 3.6 `tsconfig.json` 需追加的 include

当前 `include` 已含 `**/*.ts` / `**/*.tsx`，**测试文件会被 `tsc --noEmit` 收进去**。这意味着测试里的类型错误也会让 `npm run typecheck` 失败——这是**期望行为**，但要求测试文件类型干净。

需在 `compilerOptions.types` 追加（若 tsconfig 无 `types` 字段则新增）：

```jsonc
"types": ["vitest/globals", "@testing-library/jest-dom"]
```

> 若不想动 tsconfig，退路是在 `tests/` 下放一个 `tsconfig.json` 独立配置。**但推荐直接改主 tsconfig**，减少配置分叉。

---

## 4. 待测清单（14 个目标，≥10 已满足）

> 「重点断言」列是**必须写**的；其余为建议。

### 4.1 `src/lib/highlight.ts` ⭐ P0 安全红线

| # | 用例 | 重点断言 |
|---|---|---|
| 1 | `highlightCode('<script>alert(1)</script>')` | 结果**不含裸 `<`**；含 `&lt;script&gt;`；不含 `<script` |
| 2 | `highlightCode("s = '<img src=x onerror=alert(1)>'")` | 不含裸 `<`；`onerror` 出现在 `tok-string` span 的**文本内**（是数据不是属性） |
| 3 | `highlightCode('x = "a" and 1 < 2')` | `<` 被转义为 `&lt;`；`and` 带 `tok-keyword` class |
| 4 | `highlightCode('javascript:alert(1)')` | 标识符路径兜底转义；**不产生任何 `href`/`src` 属性**（高亮器只加 `class`） |
| 5 | `highlightCode('a & b')` | `&` → `&amp;`（`&amp;` 前置转义顺序正确，不能出现 `&amp;lt;` 式双重错误） |
| 6 | `highlightCode('')` / `highlightCode('!!!')` | 不抛错；空串返回 `''` |
| 7 | `highlightCode('print(1)', 'javascript')` | 走 else 分支：整体转义，**无 span** |
| 8 | 幂等性 | `highlightCode(h)` 两次调用结果相同（注意 `TOKEN_RE` 是 `g` 标志的模块级正则，这是真实风险点） |

> 用例 8 尤其重要：`TOKEN_RE.lastIndex` 是共享可变状态，若某分支忘记重置，**跨调用会漏 token**。这是本文件最可能的隐藏 bug。

### 4.2 `src/lib/api.ts` ⭐ P0 并发红线

前置：每个用例先 `configureApiClient({...})` 注入假 token。

| # | 用例 | 重点断言 |
|---|---|---|
| 9 | 成功解包 | `apiGet('/x')` 在 `{success:true,data:{a:1}}` 下 resolve 为 `{a:1}`（**已脱壳**） |
| 10 | 错误解包 | `{success:false,error:{code:'X'}}` + 400 → 抛 `ApiRequestError`，`err.code==='X'`、`err.status===400` |
| 11 | **单飞刷新** | 3 个并发 `apiGet` 全部 401(`TOKEN_EXPIRED`) → `fetch` 被调用 **4 次**（3 次业务 + **恰好 1 次** `/auth/refresh`）；三者最终 resolve |
| 12 | **仅重试一次** | 刷新成功后重试仍返回 401 → 抛错，`/auth/refresh` **只调用 1 次**（不得无限递归） |
| 13 | 刷新失败 | `/auth/refresh` 401 → `onSessionExpired` **被调用 1 次**；抛 401 |
| 14 | 无 refresh token | `getRefreshToken()` 返回 null → **不发** `/auth/refresh`，直接 `onSessionExpired` |
| 15 | 非可刷新码 | 401 + `FORBIDDEN` → **不触发刷新**，直接抛错 |
| 16 | 204 | resolve 为 `null` |
| 17 | blob | `{blob:true}` 时返回 `Blob` 实例；且 `!res.ok` 时抛错 |
| 18 | query 拼接 | 空值（`''`/`undefined`/`null`）被忽略；数字 `0` **保留**（易错点） |
| 19 | 无 refresh token 时 401 不重试 | 断言 `onSessionExpired` 被调用，**避免死循环** |

### 4.3 `src/lib/format.ts`（P0）

| # | 用例 | 重点断言 |
|---|---|---|
| 20 | `extractErrorLine('  File "main.py", line 3')` | 返回 `3`；无匹配返回 `null` |
| 21 | `formatPython` | 保留缩进语义；不破坏字符串字面量内的换行 |

### 4.4 `src/lib/utils.ts`（P0）

| # | 用例 | 重点断言 |
|---|---|---|
| 22 | `formatMemory(1536)` | `'1.5 MB'` 级别（断言数值换算，容忍单位后缀差异） |
| 23 | `formatDuration(3661)` | 含 `'1'` 与 `'小时'` |
| 24 | `parseFilename('attachment; filename="a.md"')` | 返回 `'a.md'`；`null` 时返回 fallback |
| 25 | `formatRelativeTime(FIXED_NOW)` | 因 setup 已固定 `Date`，结果稳定 |
| 26 | `initials('Python Lab')` | `'PL'`；`null` 输入不抛错 |

### 4.5 `src/hooks/usePythonRunner.ts`（P1）

| # | 用例 | 重点断言 |
|---|---|---|
| 27 | 成功运行 | mock `pythonApi.run` resolve → `result.stdout` 正确，`running` 终为 `false` |
| 28 | 失败 | reject → `error` 非空，`result` 为 `null` |
| 29 | `reset()` | 清空 `result` 与 `error` |

### 4.6 `src/components/code/code-block.tsx`（P1，纵深防御）

| # | 用例 | 重点断言 |
|---|---|---|
| 30 | XSS 渲染 | 传入 `<script>alert(1)</script>` → `container.querySelector('script')` 为 **`null`**；`innerHTML` 含 `&lt;script&gt;` |

### 4.7 `src/components/markdown.tsx`（P1）

| # | 用例 | 重点断言 |
|---|---|---|
| 31 | 原始 HTML 不渲染 | `content='<img src=x onerror=alert(1)>'` → 容器内**无 `img` 元素**（证明未启用 rehype-raw） |
| 32 | 正常 GFM | `**粗体**` → 生成 `<strong>`（确认 remark-gfm 生效） |

### 4.8 建议第 3 步再测

`src/store/auth.ts`（token 存取 + `configureApiClient` 注入）、`src/hooks/useDebounce.ts`、`src/hooks/useEnums.ts`（与 `GET /health/enums` 的字段一致性）。

---

## 5. 落地顺序（4 步，每步有可验证标志）

### 第 1 步：搭基座 + L1 纯函数（P0，**最高优先**）

**做什么**
1. 建 `frontend/.npmrc`（npmmirror）
2. 装 4 个包：`vitest@^3.2.4`、`jsdom@^26.0.0`、`@testing-library/react@^16.3.0`、`@testing-library/jest-dom@^6.6.3`
3. 建 `vitest.config.mts`、`tests/setup.ts`、`tests/helpers/fetch-mock.ts`、`tests/helpers/factories.ts`
4. `package.json` 加 4 个 scripts；`tsconfig.json` 加 `types`
5. 写 4 个测试文件

**文件清单**
```
frontend/vitest.config.mts
frontend/tests/setup.ts
frontend/tests/helpers/fetch-mock.ts
frontend/tests/helpers/factories.ts
frontend/tests/lib/highlight.test.ts      (~8 用例)
frontend/tests/lib/format.test.ts         (~4 用例)
frontend/tests/lib/utils.test.ts          (~7 用例)
frontend/tests/lib/api.test.ts            (~11 用例)
```

**可验证标志**
```powershell
npx vitest run
# 期望：Test Files 4 passed (4) | Tests 30 passed (30)
npm run typecheck
# 期望：0 error（tsc 退出码 0）
```
> **第 1 步结束时，`npm run typecheck` 必须仍是 0 错**——这是判断测试代码没污染主 tsconfig 的信号。

### 第 2 步：安全红线全绿（P0）

**做什么**
1. 补 `tests/components/code-block.test.tsx`（L4，XSS 渲染）
2. 补 `tests/components/markdown.test.tsx`（L4，禁 rehype-raw）
3. 为 `tests/lib/highlight.test.ts` 补齐 §1.5 的 6 条红线断言

**可验证标志**
```powershell
npx vitest run tests/lib/highlight.test.ts tests/components
# 期望：全绿，且 §1.5 六条断言全部存在（人工核对文件名与用例名）
```

### 第 3 步：Hook 与 store（P1）

**做什么**：`usePythonRunner` / `useDebounce` / `useEnums` / `store/auth.ts`；视需要装 `@vitest/coverage-v8`。

**可验证标志**
```powershell
npx vitest run
# 期望：Test Files 8~9 passed | Tests 45+ passed
npm run typecheck
# 期望：0 error
```

### 第 4 步：接入 CI 门禁（P1）

**做什么**：`package.json` 加 `"test:ci": "vitest run --reporter=basic"`，CI 里 `npm run typecheck && npm run test:ci`。**不设覆盖率阈值**。

**可验证标志**：CI 日志出现 `Tests  N passed`，且 `typecheck` 在测试之前执行。

### 关键路径

```
第1步（基座+纯函数+api）─┬─→ 第2步（安全红线）─→ 第4步（CI）
                          └─→ 第3步（Hook/store）─┘
```
第 1 步与第 2 步**必须串行**（第 2 步依赖 setup/config）。第 3 步可在第 1 步完成后与第 2 步并行。

---

## 6. 共享知识（跨文件约定）

### 6.1 Mock 约定

| 场景 | 做法 | 反例（禁止） |
|---|---|---|
| HTTP 请求 | 统一用 `tests/helpers/fetch-mock.ts` 的 `mockFetchSequence` + `ok()`/`err()`/`unauthorized()` | ❌ 在用例里手搓 `new Response(...)`；❌ 引入 msw 打真实网络 |
| 只测某业务模块 | `vi.mock('@/lib/api', () => ({ pythonApi: { run: vi.fn() } }))` | ❌ 部分 mock：`vi.spyOn(apiModule,'pythonApi')` 会污染同文件其他用例 |
| Monaco | `vi.mock('@monaco-editor/react', () => ({ default: () => <div data-testid="monaco-stub" /> }))` | ❌ 尝试在 jsdom 里真跑 Monaco（必失败） |
| 图表（recharts） | 同上整体 mock 成 `null` 占位 | ❌ 断言 SVG path 的 `d` |
| 令牌注入 | 用例内先 `configureApiClient({ getAccessToken: () => 'test-access', getRefreshToken: () => 'test-refresh', onTokensRefreshed: vi.fn(), onSessionExpired: vi.fn() })` | ❌ 依赖真实 localStorage |

> **Mock 必须整体替换模块，禁止部分打补丁。** 部分 mock 会让「测的和跑的」不是同一份代码。

### 6.2 时间与时区约定

| 约定 | 值 | 理由 |
|---|---|---|
| 固定「现在」 | `2026-09-27T10:00:00Z` | `formatRelativeTime` / 倒计时断言需要稳定基准 |
| 时区 | `process.env.TZ = 'UTC'`（在 `setup.ts` 的 `beforeAll`） | 本机 CST 与 CI UTC 不同，不固定必然飘红 |
| 需要真实定时器 | 用例内局部 `vi.useFakeTimers()` + `finally` 恢复 | 防抖/倒计时测试需要 |
| 禁止 | `vi.advanceTimersByTime` 之外的 `Date` 手动改写 | 保持与 `setup.ts` 单一来源 |

### 6.3 文件与命名约定

| 约定 | 规范 | 例 |
|---|---|---|
| 位置 | 全部测试在 `frontend/tests/`，**`src/` 内不放手写测试** | `tests/lib/api.test.ts` |
| 镜像结构 | `tests/` 目录结构镜像 `src/` | `src/lib/highlight.ts` → `tests/lib/highlight.test.ts` |
| 命名 | `<被测模块>.test.ts` | `tests/lib/utils.test.ts` |
| 环境声明 | 需 DOM 的文件**首行**加 `// @vitest-environment jsdom` | |
| 辅助代码 | 放 `tests/helpers/`，**文件名不含 `.test.`**（避免被收集） | `tests/helpers/factories.ts` |
| 命名 | 测试用 `it('在 X 情况下应 Y')` 中文描述 | `it('401 并发时只触发一次刷新', ...)` |

### 6.4 不要碰的文件（红线）

| 文件 | 原因 |
|---|---|
| `src/lib/api.ts` **本体** | 除非发现真实 bug，否则**测试不得驱动生产代码修改**。测试是验证，不是重塑。 |
| `src/lib/highlight.ts` 本体 | 同上。**若测试失败，先怀疑测试写错**，再确认是否真有转义漏洞。改高亮器必须同步更新 `docs/SECURITY.md` §2.1 的结论。 |
| `next.config.ts` | Vitest 有独立配置，不需要动 Next。**特别不要**为了测试往 next.config 加 test 段。 |
| `tsconfig.json` 的 `paths` | 已有 `@/*`，只需加 `types`。**不要**为测试改别名。 |
| `src/components/markdown.tsx` | 不得为测试启用 `rehype-raw`（会打破 `SECURITY.md` §2.1 的 X3 结论）。 |
| `package.json` 的现有 scripts 与依赖版本 | 只**追加** `test*` scripts 与 devDependencies，不升级 `next`/`react`/`tailwind`。 |
| `.env*` | 测试不读后端环境变量；沙箱与 AI 在本机是降级态，**测试不得发起真实后端请求**。 |

### 6.5 与后端测试的分工

| 归属 | 内容 |
|---|---|
| 后端 pytest（97 用例，已绿） | 判题、掌握度算法、权限、限流、OpenAPI 契约 |
| **本前端基座** | 转义安全、请求层并发契约、纯展示函数、状态机 |
| **都不测** | 真实浏览器渲染、样式、性能 |

---

## 7. 已知风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| `@testing-library/react` 装不上 | 阻塞 | 必须 `^16.3.0`；先只装 `vitest+jsdom` 跑 L1/L2（不依赖 RTL） |
| 全量 fake timers 导致 `waitFor` 挂死 | 用例超时 | setup 只 fake `Date`/`performance`；`restoreMocks`+`unstubGlobals` 已开 |
| `TOKEN_RE` 是模块级 `g` 正则，`lastIndex` 跨调用污染 | 高亮偶发漏 token | 用例 8 幂等性断言守住 |
| 测试被 `tsc --noEmit` 收录导致 typecheck 失败 | 门禁红 | 测试文件类型必须干净；`tsconfig` 只加 `types` 不加 `paths` |
| 国内网络安装慢 | 阻塞 | npmmirror + `--prefer-offline --no-audit --no-fund`；L1/L2 零外部依赖可先跑 |
| **`esbuild` postinstall 失败**（`spawnSync node EBUSY`，Windows 受限环境/杀软拦截常见） | 阻塞 | 备选：①`npm install --ignore-scripts` 后 `npm rebuild esbuild`；②`npm install --foreground-scripts` 让日志可见；③确认 Node 路径无中文/空格。**注意**：Next 15 自带一份编译版 esbuild，但**不要**把 `ESBUILD_BINARY_PATH` 指向它（版本可能不匹配，会在运行时报错） |
| Monaco/Recharts 在 jsdom 崩溃 | 用例红 | 整体 mock 替换，不调试图渲染 |

---

## 8. 第二阶段（本设计**不做**，仅登记）

| 项 | 触发条件 | 备注 |
|---|---|---|
| Playwright e2e | 本轮基座全绿后 | 只覆盖 3 条主干：①注册登录→课程 ②编辑器运行代码 ③提交判题看结果。需后端在线或 mock 网络 |
| 视觉回归 | UI 稳定后 | 需先规范化设计 token |
| 覆盖率门槛 | **暂不设** | 如需观察，只在本地跑 `--coverage` 看趋势，不进 CI 门禁 |
| a11y 检查 | 引入 axe-core 后 | 当前不纳入 |

---

## 9. 立即执行清单（工程师照做即可）

```powershell
# ① 配镜像 + 装包
cd D:\徐浩然\2026-09-26-21-55-08\python-learning-platform\frontend
npm config set registry https://registry.npmmirror.com
npm install -D vitest@^3.2.4 jsdom@^26.0.0 @testing-library/react@^16.3.0 @testing-library/jest-dom@^6.6.3

# ② 按 §3 建 4 个配置文件（内容已在本文档给出，可直接复制）
#    vitest.config.mts / tests/setup.ts / tests/helpers/fetch-mock.ts / tests/helpers/factories.ts

# ③ package.json 追加 scripts（§3.5）；tsconfig.json 追加 types（§3.6）

# ④ 按 §4.1–§4.4 写 4 个测试文件

# ⑤ 验收
npx vitest run          # 期望 4 files / 30 tests 全绿
npm run typecheck       # 期望 0 error
```

---

*文档结束。落地后请在 `docs/SECURITY.md` §2.1 追加一行：highlight.ts 的转义已由 `tests/lib/highlight.test.ts` 的 8 条用例回归保护。*
