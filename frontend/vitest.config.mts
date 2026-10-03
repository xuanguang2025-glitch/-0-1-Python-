/// <reference types="vitest/config" />
import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  test: {
    // ---- 环境 ----
    // 默认 node（纯函数测试零开销），需要 DOM 的测试在文件顶部用
    // @vitest-environment jsdom 单独声明，避免为纯函数付出 jsdom 启动代价
    environment: 'node',
    globals: true, // 提供 describe/it/expect 全局，免去每个文件 import
    setupFiles: ['./tests/setup.ts'],

    // ---- 路径别名：必须与 tsconfig.json 的 "@/*": ["./src/*"] 保持一致 ----
    alias: [{ find: /^@\//, replacement: fileURLToPath(new URL('./src/', import.meta.url)) }],

    // ---- 包含 / 排除 ----
    include: ['tests/**/*.test.{ts,tsx}'], // 只收 tests/ 目录，不侵入 src/
    exclude: [
      'node_modules/**',
      '.next/**', // next build 产物
      '.next-dev/**', // next dev 产物（本项目自定义 distDir）
      '.next-dev-3001/**', // 本机 3001 端口 dev 产物
      '.next-verify/**', // 隔离验证构建产物
      '.next-prod/**', // 生产模式产物
      'out/**',
      'coverage/**',
      '**/*.d.ts',
    ],

    // ---- 行为 ----
    css: false, // 不处理 CSS import，Tailwind 相关 import 直接忽略
    restoreMocks: true, // 每个用例后自动 restoreMocks，避免 spy 泄漏
    clearMocks: true,
    mockReset: true,
    unstubEnvs: true,
    unstubGlobals: true, // ★ 关键：自动还原 vi.stubGlobal('fetch', ...)
    environmentOptions: {
      jsdom: { url: 'http://localhost:3000' }, // 固定 origin，便于断言相对 URL
    },

    // ---- 性能 ----
    testTimeout: 5000,
    hookTimeout: 10000,
    pool: 'threads', // 默认；避免 forks 在 Windows 上更慢
    reporters: ['default'],
  },
});
