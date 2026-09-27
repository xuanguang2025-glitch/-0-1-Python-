# PYTHON LAB —— 备用前端镜像（若 frontend/ 内未提供 Dockerfile 时使用）
#
# 用法（在仓库根）：
#   docker build -f docker/frontend.Dockerfile -t pythonlab/frontend:1.0.0 ./frontend
# 并在 .env 中设置 FRONTEND_DOCKERFILE=../docker/frontend.Dockerfile
#
# 注意：frontend 未开启 next.config `output: 'standalone'` 时，用 deps+builder+runner
# 三阶段中的 `npm start` 方式启动亦可；此处按 standalone 产物优先，找不到则回退 npm start。

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm config set registry https://registry.npmmirror.com \
    && (npm ci --omit=dev || npm install --omit=dev)

FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm config set registry https://registry.npmmirror.com && (npm ci || npm install)
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000
RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001
COPY --from=deps /app/node_modules ./node_modules
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/next.config.* ./
USER nextjs
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=5 \
    CMD wget -qO- http://127.0.0.1:3000 >/dev/null 2>&1 || exit 1
CMD ["npm", "run", "start"]
