import type { NextConfig } from 'next';

/** 后端 API 基址（服务端变量，仅用于 rewrites 代理）。 */
const BACKEND_URL: string = process.env.BACKEND_URL ?? 'http://127.0.0.1:8000';

/** 构建输出目录（默认 .next，可通过环境变量覆盖，便于隔离验证构建）。 */
const DIST_DIR: string = process.env.NEXT_DIST_DIR ?? '.next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  distDir: DIST_DIR,
  eslint: {
    // 本机未安装 eslint 配置，构建时不强依赖，避免装包失败阻塞编译
    ignoreDuringBuilds: true,
  },
  async rewrites() {
    // 同源代理：/api/** -> {BACKEND_URL}/api/**，规避 CORS
    return [
      {
        source: '/api/:path*',
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
  webpack: (config) => {
    // Monaco worker 走 CDN 体积太大且离线不可用，这里交由 @monaco-editor/react 内部 loader 处理，
    // 仅关闭 webpack 对 monaco-editor 的 ESM 警告。
    config.resolve = config.resolve ?? {};
    config.resolve.fallback = { ...config.resolve.fallback, fs: false, path: false };
    return config;
  },
};

export default nextConfig;
