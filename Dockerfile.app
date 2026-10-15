# 观澜 AUREL 整站单容器镜像（前端构建产物由 FastAPI 托管，一个容器即可运行整站）
# 构建上下文为仓库根目录：docker build -f Dockerfile.app -t aurel-app .
# 适用于 Render / Fly.io / HF Spaces 等单容器免费托管平台（PORT 环境变量自动适配）
FROM node:24-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim AS runtime

WORKDIR /app/backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./alembic.ini
# 前端产物：后端检测到 /app/frontend/dist 后自动托管静态文件并对 SPA 路由回退 index.html
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

EXPOSE 8000
# 启动前先执行数据库迁移；PORT 由托管平台注入，默认 8000
CMD ["sh", "-c", "alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
