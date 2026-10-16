# 观澜 AUREL

> 见微知远，向新而行。

面向大学生与求职者的 AI 职业成长平台：以真实模型驱动的模拟面试、职业规划对话、岗位解析、简历编辑与岗位匹配为核心，帮助用户看清自己、练好表达、走好下一步。

## 功能特性

- **问澜 · AI 模拟面试**：结合行业与岗位真实生成面试题，追问决策推进，完成后产出可解释的四维评分报告（总分、维度、证据、建议）
- **知途 · AI 职业规划**：分层记忆的对话式规划，长期记忆区分「你说过的事实 / AI 归纳 / AI 推断」，产出阶段化行动计划并保留版本快照
- **知岗 · 岗位解析**：JD 结构化解析，所有结论可回溯原文片段，无法定位的证据如实标注「模型推断」
- **合契 · 岗位匹配**：简历与岗位逐项对照，命中与缺失均附双侧原文证据
- **履历成章 · 简历工坊**：七节结构化编辑、七款差异化模板、版本管理、AI 润色仅生成建议文本（确认后才应用），真实导出 PDF / DOCX
- **知藏 · 知识库 / 观己 · 技能图谱 / 度衡 · 限时挑战 / 回澜 · 错题本 / 知潮 · 岗位库 / 协奏 · 多角色工作流**
- **行舟 · 工作台 / 小鸥 · 悬浮助手 / 引航 · 新手引导**

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React 19、TypeScript、Vite、Tailwind CSS、React Router、Motion、Lucide |
| 后端 | Python、FastAPI、Pydantic v2、SQLAlchemy 2.0、Alembic、httpx、Uvicorn |
| AI | 火山方舟 Chat Completions（OpenAI 兼容接口，模型由 `ARK_MODEL` 环境变量配置）：连接池复用、自动重试、SSE 流式、调用观测入库 |
| 数据库 | SQLite（WAL）+ Alembic 迁移，全部业务数据按用户隔离 |
| 认证 | 用户名 + 密码注册登录（PBKDF2-SHA256 哈希）、HttpOnly Cookie 会话、登出真实撤销服务端会话 |

## 快速开始

### 后端（端口 8000）

```bash
cd backend
pip install -r requirements.txt
```

在 `backend/` 下创建 `.env`：

```
ARK_API_KEY=你的火山方舟 API Key
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_MODEL=你的模型名
AUREL_DATABASE_URL=sqlite:///./aurel.db
```

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

未配置 `ARK_API_KEY` 时，AI 功能的调用会明确返回配置错误，不会伪造任何 AI 结果。

### 前端（端口 5173）

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 即可访问。开发服务器已配置代理，`/api` 请求自动转发到后端。

## 测试与检查

```bash
# 后端测试（backend/ 目录）
python -m pytest

# 前端检查（frontend/ 目录）
npm run lint        # ESLint
npm run typecheck   # TypeScript
npm run build       # 生产构建
```

## 在线部署（Docker Compose）

```bash
# 1. 在仓库根目录创建 .env（与 backend/.env 变量一致）
# 2. 构建并启动
docker compose up -d --build
# 3. 访问 http://localhost:8080（Nginx 托管前端并反代 /api，SSE 已关闭缓冲）
```

后端容器启动前自动执行 `alembic upgrade head`；数据库与模型缓存在命名卷中持久化。

### 单容器部署（Render / Fly.io 等托管平台）

```bash
docker build -t aurel-app .
docker run -p 8000:8000 --env-file .env aurel-app
# 打开 http://127.0.0.1:8000 —— 前端页面与 API 同源，一个容器运行整站
```

前端构建产物由 FastAPI 直接托管（检测到 `frontend/dist` 时自动启用，SPA 路由回退 `index.html`）；
平台注入的 `PORT` 环境变量会被自动使用。注意：SQLite 数据存于容器文件系统，
托管平台重建容器会清空数据，重要数据请自行挂载持久卷。

## 安全约定

- 模型 API Key 只在 Python 后端从环境变量读取，不进入前端代码或 `VITE_*` 变量，日志自动脱敏
- 密码使用 PBKDF2-SHA256 加盐哈希；登录失败统一提示，防止用户枚举
- 所有业务数据严格按用户隔离，接口在后端校验访问权限
- 内置限流（`AUREL_RATE_LIMIT_PER_MINUTE`）与可选 Bearer 访问令牌（`AUREL_ACCESS_TOKEN`）；数据隐私说明见 `GET /api/v1/privacy`

## 接口文档

后端启动后访问 http://127.0.0.1:8000/docs 查看完整的 OpenAPI 文档。

## 项目结构

```
├── frontend/          # React + TypeScript + Vite + Tailwind CSS
│   └── src/           # pages / components / api / hooks / lib
├── backend/           # Python FastAPI
│   ├── app/           # models / routers / services / schemas
│   ├── migrations/    # Alembic 数据库迁移
│   ├── eval/          # 固定评测集与质量回归脚本
│   └── tests/         # pytest 测试
├── docs/              # 项目状态文档
└── docker-compose.yml # 一键部署（Nginx + 后端）
```
