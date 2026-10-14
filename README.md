# 观澜 AUREL

> 观其微澜，见其远势。

AI 驱动的能力探索与成长平台。以 AI 模拟面试为第一个核心应用，未来扩展为 AI 能力分析、知识学习与个人成长平台。

## 项目结构

```
├── frontend/          # React + TypeScript + Vite + Tailwind CSS
├── backend/           # Python FastAPI + Pydantic + SQLAlchemy
│   ├── app/           # 应用代码（models / routers / services / schemas）
│   ├── migrations/    # Alembic 数据库迁移
│   └── .env           # 服务端密钥与配置（不提交到版本库）
├── docs/              # 项目状态文档
├── README.md
└── .gitignore
```

## 技术栈

**前端**：React 19、TypeScript、Vite、Tailwind CSS、React Router、Motion for React、Lucide React

**后端**：Python、FastAPI、Pydantic、SQLAlchemy 2.0、Alembic、httpx、Uvicorn、pytest

**AI**：火山方舟 Chat Completions（模型 glm-5-2-260617，密钥仅存于后端环境变量）；知识库检索采用本地 BM25 词频匹配（证据可追溯，不依赖 embedding 服务）；语音转文字为多提供方可插拔架构（硅基流动 SenseVoice 免费档 / 本地 faster-whisper 完全离线 / 豆包语音极速版可选，均不配置时如实标注「未配置」，绝不伪造转录）

**稳定性与观测**：模型调用自动重试（429/5xx 尊重 Retry-After）与超时控制；SSE 流式复盘进度；调用观测入库（成功率 / 延迟 / 提示词版本 / 实验分流对比）；固定评测集质量回归（`python -m eval.run_eval`）

## 快速开始

### 配置后端环境变量

在 `backend/` 下创建 `.env`：

```
ARK_API_KEY=你的火山方舟 API Key
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_MODEL=glm-5-2-260617
AUREL_DATABASE_URL=sqlite:///./aurel.db
```

未配置 `ARK_API_KEY` 时，前端会明确显示「AI 未配置」，创建面试任务入口禁用——不会伪造任何 AI 结果。

语音转文字（可选，三选一或全不配置）：

```
# 提供方选择：auto（默认，按就绪顺序自动挑选）/ siliconflow / local / volcengine
ASR_PROVIDER=auto

# 方案一：硅基流动 SenseVoiceSmall 免费档（https://siliconflow.cn 注册获取）
ASR_SILICONFLOW_API_KEY=

# 方案二：本地 faster-whisper，完全离线免费（pip install faster-whisper，首次使用自动经镜像下载模型）
ASR_LOCAL_MODEL=small
HF_ENDPOINT=https://hf-mirror.com

# 方案三：豆包语音极速版（独立于方舟的凭证，可选）
# SPEECH_APP_ID=
# SPEECH_ACCESS_TOKEN=
```

三者都不配置时，表达分析页如实显示「语音转文字尚未配置」及三条启用指引：转录功能不可用，但音频本地客观指标（时长、停顿、静音占比）与直接粘贴文本的多角色复盘照常工作，不会伪造任何转录内容。

### 安全与访问控制（可选，线上建议开启）

```
# 设置后所有 /api/v1 请求（除 /health、/ai/status、/expression/status）需携带
# Authorization: Bearer <令牌>；留空则保持本地开放模式
AUREL_ACCESS_TOKEN=

# 每客户端 IP 每分钟请求上限（0 关闭）
AUREL_RATE_LIMIT_PER_MINUTE=120
```

其他内置安全设置：SQLite 连接启用 `foreign_keys` / WAL / `busy_timeout`；日志自动脱敏 Bearer / api_key / token 形态字符串；API Key 绝不进入前端与日志；音频只在内存中处理、不落盘；数据隐私说明见 `GET /api/v1/privacy`。

### 邮件发送（默认：阿里云 DirectMail 邮件推送）

注册与登录的验证码邮件默认通过阿里云 DirectMail（邮件推送）`SingleSendMail` 官方接口发送（官方 V2 SDK `alibabacloud_dm20151123`，该单发方式不需要邮件模板）。完整人工配置流程：

1. 注册阿里云账号并完成实名认证。
2. 开通「邮件推送 DirectMail」服务（控制台搜索"邮件推送"）。
3. 在「发信域名」中添加你自己的域名，按控制台给出的记录类型（SPF / DKIM / MX 等）到域名 DNS 服务商处配置解析记录，并等待验证通过——域名未验证前真实发送必然失败。
4. 在「发信地址」中创建发件地址（如 `no-reply@你的域名`），并完成该地址的邮箱回执验证（按控制台要求）。
5. （本方式可跳过模板审核：SingleSendMail 为自由正文单发；如需批量/模板发送才需「邮件模板」审核。）
6. 在 RAM 访问控制创建子用户，仅授予 `AliyunDirectMailFullAccess`（或更小的仅发信权限），为其创建 AccessKey——不要使用主账号密钥。
7. 将服务端环境变量配置到 `backend/.env`（本地）或部署平台环境变量（线上）：

   ```
   MAIL_PROVIDER=aliyun_directmail
   ALIBABA_CLOUD_ACCESS_KEY_ID=你的AccessKeyId
   ALIBABA_CLOUD_ACCESS_KEY_SECRET=你的AccessKeySecret
   ALIBABA_CLOUD_REGION_ID=cn-hangzhou
   DIRECTMAIL_SENDER_ADDRESS=no-reply@你的域名
   ```

8. 重启 Python 后端。
9. 执行真实投递测试：`cd backend && .\.venv\Scripts\python.exe scripts\send_test_email.py 你的收件QQ邮箱`；也可先访问 `GET /api/v1/auth/email-status` 查看配置状态（只返回提供方名、布尔状态与缺失变量名，绝不含任何配置值）。
10. 检查目标收件箱、垃圾邮件，并到控制台「发送详情 / 投递记录」核对投递状态——云服务受理发送请求不代表收件箱必达。

可选适配器：原 QQ 邮箱 SMTP 发信保留为 `MAIL_PROVIDER=smtp_qq`（读取 `QQ_SMTP_USER` / `QQ_SMTP_AUTH_CODE`），默认不启用。本地开发可用 `MAIL_PROVIDER=mock` + `AUREL_MOCK_MAIL_CONFIRM=1` 启用开发模拟（控制台打印验证码并明确标记"开发模拟 · 非真实投递"，生产禁止）。

安全约定：凭证只保存在服务端 `.env` 或部署平台环境变量，绝不写进前端、`VITE_*`、日志或文档；发送失败时接口如实返回 502/503，未投递的验证码不会落库、无法用于注册；自动化测试全程使用模拟客户端/模拟 SMTP，不真实发信。

常见错误排查（接口以 502/503 如实返回原因，绝不携带凭证或验证码）：

- `InvalidAccessKeyId` / `SignatureDoesNotMatch`：AccessKey ID 或 Secret 填写有误，或 RAM 子用户缺少 DirectMail 发信权限（仅需发信权限，勿用主账号密钥）。
- `InvalidMailAddress` / `DomainNotExist` / `InvalidDomain`：发件地址未在控制台创建，或发信域名未完成 DNS 验证。
- 连接超时 / 网络错误：确认服务器出口可访问 `dm.{region}.aliyuncs.com`（443 端口）；接口对连接与读取各设 10 秒超时。
- 模板审核类错误仅批量/模板发送会出现；本项目使用 `SingleSendMail` 自由正文单发，无需创建邮件模板。
- 云服务受理请求 ≠ 收件箱必达：投递结果请到控制台「发送详情 / 投递记录」按返回的 env_id 查询；未受理成功的验证码不会落库，也不会返回"已发送"。

### 质量评测（T4）

```bash
# 在 backend/ 目录：对固定评测集执行真实模型评测（评分 + 出题）
python -m eval.run_eval            # 全部用例
python -m eval.run_eval --limit 3  # 每套件取前 3 个用例
```

指标：解析成功率、证据覆盖、关键概念覆盖、分数偏差（对比人工锚点）、延迟（平均 / P95）。报告写入 `backend/eval/reports/`，记录所用模型与提示词版本，可跨版本横向对比。

### 在线部署（Docker Compose）

```bash
# 1. 在仓库根目录创建 .env（与 backend/.env 变量一致：ARK_API_KEY / ARK_MODEL 等）
# 2. 构建并启动
docker compose up -d --build
# 3. 访问 http://localhost:8080（Nginx 托管前端并反代 /api 到后端，SSE 已关闭缓冲）
```

后端容器启动前自动执行 `alembic upgrade head`；数据库与 Whisper 模型缓存在命名卷中持久化。线上务必设置 `AUREL_ACCESS_TOKEN`。

### 启动后端（端口 8000）

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 启动前端（端口 5173）

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 即可访问。前端开发服务器已配置代理，`/api` 请求会自动转发到 `http://127.0.0.1:8000`。

## 测试与检查

```bash
# 后端测试（在 backend/ 目录）
python -m pytest

# 质量评测（在 backend/ 目录，需已配置 ARK_API_KEY，消耗真实模型调用）
python -m eval.run_eval

# 前端检查（在 frontend/ 目录）
npm run lint        # ESLint
npm run typecheck   # TypeScript 类型检查
npm run build       # 生产构建（含类型检查）
```

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/health` | 健康检查，返回 `{status, service, version}` |
| GET | `/api/v1/health/ready` | 就绪检查（含数据库连通性，失败返回 503） |
| GET | `/api/v1/privacy` | 数据隐私与留存说明（音频内存处理 / 密钥仅服务端 / 删除入口） |
| GET | `/api/v1/ai/status` | AI 配置状态（已配置 / 未配置） |
| GET | `/api/v1/auth/email-status` | 邮件服务受控诊断（当前提供方 / 是否已配置 / 缺失变量名，不含任何凭证值） |
| POST | `/api/v1/auth/register/send-code` | 注册验证码发送（真实投递成功才返回 sent，投递失败 502/503 如实报错） |
| POST | `/api/v1/auth/register/verify-code` | 注册验证（验证码 HMAC 摘要比对，成功即建号并下发 HttpOnly 会话 Cookie） |
| POST | `/api/v1/auth/login/send-code` | 登录验证码发送（与注册用途隔离） |
| POST | `/api/v1/auth/login/verify-code` | 登录验证（成功建立服务端可撤销会话） |
| POST | `/api/v1/auth/logout` | 登出（真实撤销服务端会话） |
| GET | `/api/v1/auth/me` | 当前登录用户（未登录返回 `authenticated: false` 而非报错） |
| POST | `/api/v1/jobs/analyze` | 知岗：JD 结构化解析（Pydantic 强校验 + 原文证据核验，无法定位的证据降级为「模型推断」，未提及字段标「未明确说明」） |
| POST | `/api/v1/jobs/upload` | 知岗：上传 JD 文件安全提取文本（txt / md / docx / pdf） |
| GET | `/api/v1/jobs/analyses` | 知岗：我的分析历史（含版本号） |
| GET / DELETE | `/api/v1/jobs/analyses/{id}` | 分析详情 / 删除（仅限本人数据） |
| POST | `/api/v1/jobs/analyses/{id}/interview-task` | 知岗×问澜联动：依据解析结果创建面试题集生成任务 |
| POST | `/api/v1/jobs/analyses/{id}/match` | 知岗×合契联动：解析结果与指定简历匹配（结果附证据与理由） |
| GET | `/api/v1/resumes/templates` | 履历成章：七款简历模板目录（章节顺序 + 主题色由后端统一下发） |
| POST / GET | `/api/v1/resumes` | 创建简历 / 我的简历列表 |
| GET / PUT / DELETE | `/api/v1/resumes/{id}` | 简历详情 / 保存（自动生成版本快照） / 删除（仅限本人数据） |
| GET | `/api/v1/resumes/{id}/versions` | 版本历史列表 |
| GET | `/api/v1/resumes/{id}/versions/{no}` | 不可变版本快照详情 |
| POST | `/api/v1/resumes/{id}/versions/{no}/restore` | 恢复到历史版本（生成新版本，不覆盖历史） |
| POST | `/api/v1/resumes/{id}/versions/{no}/duplicate` | 复制为新版本 |
| POST | `/api/v1/resumes/{id}/polish` | AI 润色建议（仅返回建议文本，经用户确认后才写入，禁止编造经历与数字） |
| GET | `/api/v1/resumes/{id}/export?format=pdf\|docx` | 真实导出（reportlab PDF / python-docx DOCX，中文字体内嵌） |
| GET | `/api/v1/observability/llm-calls` | 模型调用记录（最近 200 条，含状态 / 尝试次数 / 延迟 / 实验标记） |
| GET | `/api/v1/observability/llm-stats` | 调用统计聚合（按服务 / 按模型 / 成功率 / 平均延迟） |
| GET | `/api/v1/observability/prompt-versions` | 提示词版本注册表与变更记录 |
| POST | `/api/v1/interviews` | 创建面试任务并生成真实问题 |
| GET | `/api/v1/interviews` | 面试任务列表 |
| GET | `/api/v1/interviews/{id}` | 任务详情（含题目与进度） |
| POST | `/api/v1/interviews/{id}/answers` | 提交回答 |
| POST | `/api/v1/interviews/{id}/next` | 追问决策与推进下一题 |
| POST | `/api/v1/interviews/{id}/finish` | 完成面试并触发 T1 可解释评分 |
| GET | `/api/v1/interviews/{id}/report` | 评分报告（总分 / 四维度 / 证据 / 亮点 / 建议） |
| GET / POST | `/api/v1/knowledge/documents` | 知识文档列表 / 上传（txt / md / docx，自动分块） |
| GET / DELETE | `/api/v1/knowledge/documents/{id}` | 文档详情（含分块） / 删除 |
| GET | `/api/v1/knowledge/search?q=` | 知识库检索，返回带出处与匹配分的证据片段 |
| GET | `/api/v1/skills/profile` | 能力维度画像（真实历史评分聚合） |
| GET | `/api/v1/skills/graph` | 技能图谱（维度节点 + 总分走势） |
| GET | `/api/v1/skills/recommendation` | 自适应训练建议（最弱维度驱动难度与侧重） |
| POST | `/api/v1/matching/resume` | 简历与岗位匹配（命中与缺失均附原文证据，附 AI 提升建议） |
| GET | `/api/v1/matching/records` | 历史匹配记录 |
| GET | `/api/v1/expression/status` | 语音识别与 AI 模型配置状态（逐提供方，不泄露密钥） |
| POST | `/api/v1/expression/transcribe` | 上传音频真实转录 + 本地客观指标（未配置时转录为空并如实标注） |
| POST | `/api/v1/expression/analyze` | 文本/转录记录的多角色结构化复盘（结构分析师→深度分析师→表达教练） |
| POST | `/api/v1/expression/analyze/stream` | 同上，SSE 流式返回逐步进度事件（`step_started` / `step_finished` / `result`），前端实时展示每位分析师状态 |
| GET | `/api/v1/expression/records` | 表达分析历史记录 |
| GET | `/api/v1/expression/records/{id}` | 表达分析记录详情 |
| DELETE | `/api/v1/expression/records/{id}` | 删除表达分析记录 |

## 页面路由

| 路径 | 说明 |
| --- | --- |
| `/` | 品牌首页（真实海景背景 + 观澜 AUREL 标题入场 + 座右铭延迟淡入 + 观澜之意 / 行舟 / 澜讯三栏目导航） |
| `/about` | 观澜之意（项目简介，编辑感排版，无功能卡片墙） |
| `/announcements` | 澜讯（项目动态公告） |
| `/auth` | 登录 / 注册（邮箱验证码认证，含「开始你的学习之旅」引导） |
| `/app` | 行舟工作台（真实任务统计与最近任务，侧栏按启程 / 洞察 / 知行分组） |
| `/interview/new` | 问澜·创建面试（行业门类 + 职业方向选择，真实 AI 生成问题） |
| `/interview/:id` | 面试工作台（答题、追问、进度） |
| `/reports` | 回响·报告中心（真实任务与报告列表） |
| `/reports/:id` | T1 评分报告详情 |
| `/jobs` | 知岗（JD 粘贴 / 文件上传解析、原文证据、分析历史与版本、生成面试题、合契匹配联动） |
| `/resume` | 履历成章（七节结构化编辑、七款模板预览与切换、版本管理、AI 确认制润色、PDF / DOCX 真实导出） |
| `/knowledge` | 知藏·知识库（上传文档、检索验证、分块详情） |
| `/skills` | 观己·技能图谱（维度画像、总分走势、自适应训练建议） |
| `/matching` | 合契·简历匹配（命中与缺失双侧原文证据 + AI 建议） |
| `/expression` | 听澜·表达分析（录音 / 上传音频真实转录、语速停顿等客观指标、三角色结构化复盘、历史记录） |
| `/me` | 个人资料 |
| `/interview/preview` | 布局预览（保留） |
| 其他 | 404 页面 |

## 开发阶段

- 第一阶段（已完成）：基础工程、完整 UI、基础路由、健康检查与测试
- 第二阶段（已完成）：SQLAlchemy 数据模型与 Alembic 迁移、面试任务 CRUD、火山方舟真实模型调用、问题生成、回答、追问、T1 可解释评分、改进建议、报告与历史记录
- **第三阶段（已完成）**：RAG 知识库（文档上传 / 分块 / BM25 检索 / 出题证据注入）、技能图谱与自适应训练（真实历史报告驱动）、简历与岗位匹配（匹配依据可解释）
- **第四阶段（已完成）**：可插拔多提供方语音转录（硅基流动免费档 / 本地 faster-whisper 离线 / 豆包可选，未配置如实标注不伪造）、表达客观指标（停顿 / 语速 / 填充词）、多角色结构化复盘工作流（含重试、跳过与降级）
- **第五阶段（已完成）**：固定评测集质量回归（分数偏差 / 证据覆盖 / 延迟 P95）、访问控制与限流、日志脱敏、数据库安全 PRAGMA、模型调用超时与自动重试、SSE 流式复盘、就绪检查、调用观测与提示词版本管理、模型实验分流、Docker Compose 在线部署
- **第六阶段（已完成）**：邮箱验证码注册 / 登录（可插拔邮件提供方：阿里云 DirectMail 默认 / QQ SMTP 可选 / Mock 测试专用，验证码 HMAC 存储、有效期 / 冷却 / 次数限制、会话 HttpOnly Cookie）、全站观澜蓝白视觉升级（流动云团背景、鼠标光晕、纤细滚动条、prefers-reduced-motion）、知岗 JD 解析与履历成章简历系统（结构化编辑 / 七款模板 / 版本管理 / AI 确认制润色 / 真实 PDF / DOCX 导出）、知岗×问澜×合契联动
- 后续规划：向量检索增强、报告导出与分享、线上部署与真实邮件投递验证

详细进度见 [docs/STATUS.md](docs/STATUS.md)。

## 演示流程（约 5 分钟）

1. **创建面试**（`/interview/new`）：粘贴一份岗位 JD 或选择知识库文档，AI 真实生成问题；在面试工作台回答，体验追问决策与可解释评分报告（`/reports/:id`）。
2. **知识库与检索验证**（`/knowledge`）：上传一份 txt / md / docx，用检索框验证证据片段与匹配分——所有 AI 出题证据可溯源。
3. **技能图谱**（`/skills`）：查看由真实历史报告聚合的维度画像、总分走势与自适应训练建议。
4. **简历匹配**（`/matching`）：上传简历文本与岗位描述，查看命中/缺失技能的双侧原文证据与 AI 提升建议。
5. **表达分析**（`/expression`）：录音或上传音频看真实转录与语速/停顿指标，发起多角色复盘——前端将流式展示每位分析师「阅读中…」进度（SSE），完成后可在历史记录中回看。
6. **系统观测**（终端）：`curl http://127.0.0.1:8000/api/v1/observability/llm-stats` 查看刚才所有 AI 调用的成功率与延迟统计，`curl http://127.0.0.1:8000/api/v1/privacy` 查看数据隐私声明。

所有 AI 结果均为真实模型输出；未配置凭证的功能会如实显示「未配置」指引，绝不伪造。

## 约定

- 第三方模型调用只在 Python 后端执行，API Key 通过服务端环境变量读取（如 `ARK_API_KEY`），不进入前端代码或 `VITE_*` 变量。
- 未实现的功能在界面上以「预览」「尚未接入」明确标注，不伪装为已实现。
