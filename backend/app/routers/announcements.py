"""澜讯：平台公告。

数据为真实的项目阶段记录（与 docs/STATUS.md 一致）；
日期仅在有据可查时提供（取自开发记录时间），绝不编造维护通知或活动信息。
文案采用观澜品牌语气，但事实内核不变：只写已上线、可验证的能力。

置顶技术档案（project-tech-archive）：项目的技术栈、架构与进度档案，
全部内容以真实源代码、依赖声明与测试执行结果为据；密钥与环境变量取值
绝不写入本文件。章节正文与列表分离，经详情端点提供。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/announcements", tags=["announcements"])


class Announcement(BaseModel):
    id: str
    type: str  # 项目档案 / 版本更新 / 阶段公告 / 维护修复
    title: str
    summary: str
    items: list[str]
    version: str | None = None
    date: str | None = None  # YYYY-MM-DD，仅在有据可查时提供
    # 置顶档案扩展字段（仅置顶公告使用，普通公告保持默认值）
    pinned: bool = False
    tags: list[str] = []
    importance: str | None = None
    updated_at: str | None = None


class ArchiveSection(BaseModel):
    """技术档案章节：段落 / 要点 / 可选表格，正文中的 `代码名词` 由前端等宽渲染。"""

    id: str
    heading: str
    paragraphs: list[str] = []
    bullets: list[str] = []
    table_head: list[str] | None = None
    table_rows: list[list[str]] | None = None


ANNOUNCEMENTS: list[Announcement] = [
    Announcement(
        id="project-tech-archive",
        type="项目档案",
        pinned=True,
        importance="重要",
        tags=["置顶公告", "技术架构", "项目纪实", "持续更新"],
        date="2026-10-14",
        updated_at="2026-10-14",
        title="观澜 AUREL｜一舟览澜：项目介绍与技术纪实",
        summary=(
            "见微知远，向新而行。登上这一叶小舟，览尽观澜的全貌：真实技术栈、系统架构、"
            "核心功能、AI 接入方案、安全机制、测试情况与当前进度——全部内容以真实源代码与"
            "测试执行结果为据，随项目迭代持续更新。"
        ),
        items=[
            "技术栈：`React 19` + `TypeScript` + `Tailwind CSS` 前端，`Python 3.13` + `FastAPI` + `SQLAlchemy` 后端",
            "AI 接入：火山方舟 Chat Completions 统一封装，连接池复用、SSE 流式、调用全量观测",
            "安全机制：PBKDF2 密码哈希、HttpOnly 会话 Cookie、数据按用户隔离、限流与 Origin 校验",
            "质量基线：后端 309 项测试全部通过（2026-10-14 回归），18 用例规则判定评测集",
        ],
    ),
    Announcement(
        id="milestone-phase-18",
        type="阶段公告",
        date="2026-10-14",
        title="小鸥登船：一句寄语，一位常伴的伙伴",
        summary=(
            "观澜有了会说话的伙伴——首页每七秒流转一句暖心寄语，右下角的小鸥"
            "悬停时轻声细语，一点即达知途。陪伴，从此不只是比喻。"
        ),
        items=[
            "暖心寄语：八句轻语有序流转，字符如波纹次第浮现",
            "小鸥悬浮入口：悬停轻声提示，触屏轻触可见，点击直达知途对话",
            "四页同享：主页、观澜之意、澜讯与行舟工作区，小鸥常伴右下角",
        ],
    ),
    Announcement(
        id="milestone-phase-17",
        type="阶段公告",
        date="2026-10-14",
        title="四景入画：夜海、落日、花田与雪原",
        summary=(
            "四张风景各归其位——认证页的深夜海、观澜之意的落日、澜讯的花田、"
            "行舟的雪原。一张磨砂玻璃把风景与文字温柔隔开，氛围常在，字句清晰。"
        ),
        items=[
            "PageBackground 统一场景背景组件，按路由分景，互不串用",
            "玻璃画布与遮罩令牌全站统一，正文始终在最清晰的一层",
            "认证、简介、澜讯与全部工作区页面接入，兼容回退与降动效齐备",
        ],
    ),
    Announcement(
        id="milestone-phase-15",
        type="阶段公告",
        date="2026-10-14",
        title="知途入深：能力图谱、多径对照与规划复盘",
        summary=(
            "小鸥不再只会答问——它开始绘制你的能力图谱，为你并排比较多条职业水路，"
            "并让每一份计划都能复盘、能回看、能迭代。"
        ),
        items=[
            "能力图谱：技能、经历与岗位相连，每条关系都有出处，四态分明",
            "多径对照：几条职业方向并排看，依据、成本与下一步一目了然",
            "规划版本化：每次复盘生成新版本，历史从不被覆盖",
            "知识检索升级：混合检索真实岗位资料，来源与证据随身携带",
        ],
    ),
    Announcement(
        id="milestone-phase-14",
        type="阶段公告",
        date="2026-10-13",
        title="知潮开埠：真实岗位资料港",
        summary=(
            "一个只装真实岗位的资料港开埠了。来自美团、小米、微软、腾讯官方页面的岗位"
            "在此停靠，从看见岗位到读懂岗位，再到匹配自己，一水贯通。"
        ),
        items=[
            "岗位检索与筛选：企业、地点、类型，来源链接与核验时间随行展示",
            "一键入知岗：库内岗位直接解析；一键入知途：岗位化作你的行动计划",
            "合契升级：真实岗位 × 你的简历，判断两侧皆附原文",
            "履历成章：七款原创版式模板，支持真实导出",
        ],
    ),
    Announcement(
        id="milestone-phase-13",
        type="阶段公告",
        date="2026-10-13",
        title="知途·小鸥：会记得你的职业规划伙伴",
        summary=(
            "自初见小鸥到今日，知途已长成完整的职业规划之所：分层记忆记住你说过的话，"
            "确认过的档案才作数，规划化作 7/30/90 天的行动，一步一履痕。"
        ),
        items=[
            "分层记忆：对话有摘要、档案有确认，被使用的信息你可以随时查看",
            "行动计划：7/30/90 天三段航程，勾选、复盘、改期皆可",
            "模块联动：问澜出题、知岗析岗、合契匹配，小鸥真实调用而非空谈",
            "数据主权：档案、会话、计划随时查看、导出与清除",
        ],
    ),
    Announcement(
        id="milestone-phase-12",
        type="维护修复",
        date="2026-10-13",
        title="匠人修船：拾阶谢幕、拖拽成章、问澜新装",
        summary="一次安静的修缮：该告别的好好告别，该顺手的地方更顺手，该好看的地方更好看。",
        items=[
            "拾阶功成身退，相关入口与说明已全部移除",
            "合契与履历成章支持拖拽上传简历，自动解析，免于手动填写",
            "问澜选项焕新：圆角卡片、选中微光，选择本身也成为一种体验",
        ],
    ),
    Announcement(
        id="milestone-phase-9",
        type="阶段公告",
        date="2026-10-13",
        title="五水汇流：拾阶 · 回澜 · 度衡 · 协奏 · 成长轨迹",
        summary="五条支流在同日汇入观澜：路线、错题、限时、协作与坚持，各有其用。",
        items=[
            "回澜错题本：错过的题沉淀下来，按记忆规律安排重逢",
            "度衡限时挑战：真实倒计时，检验临场功力",
            "协奏：结构、深度与表达三分析师并行会诊",
            "成长轨迹：全年活动热力图与连续打卡，坚持被看见",
        ],
    ),
    Announcement(
        id="milestone-phase-10",
        type="阶段公告",
        title="轻盈入画：编辑式版面与两处新洞察",
        summary=(
            "全站版面改作轻盈的编辑式画布，去繁就简；同时添了两件新器："
            "星图对照看差距，澜记周报回望一周。"
        ),
        items=[
            "Editorial 版式全站铺开，统一蓝白气韵",
            "星图对照：你的能力星图与目标岗位并置，差距清楚可见",
            "澜记周报：真实行为汇成一周小结，AI 只评所述之事",
        ],
    ),
    Announcement(
        id="milestone-brand-refresh",
        type="阶段公告",
        title="观澜焕新：新标志、海面波光与引航之旅",
        summary="观水有术，必观其澜——新标志取意波纹与地平线，首页有了流动的海，初来者有了引航。",
        items=[
            "原创矢量标志上线，全站统一应用",
            "首页海面波光层叠，静谧而生动",
            "「引航」五步教程：首次到访自动开启，随时可重游",
        ],
    ),
    Announcement(
        id="milestone-phase-6",
        type="阶段公告",
        title="门扉初开：账户认证、知岗与履历成章",
        summary="观澜开始认得每一位来客，也多了两间功课房：读岗位的知岗，成文章的履历。",
        items=[
            "账户认证：取一个用户名，设好密码，即可入门",
            "知岗：粘贴岗位描述，解析成结构化结论，条条可溯原文",
            "履历成章：结构化简历编辑与版本管理",
        ],
    ),
    Announcement(
        id="release-v0.3.0",
        type="版本更新",
        version="v0.3.0",
        date="2026-10-11",
        title="第五阶段发布：质量评测、访问控制与部署就绪",
        summary=(
            "第五阶段收官：看得见的评分背后，有了看不见的守护——"
            "质量有回归，访问有门禁，部署有舟楫。"
        ),
        items=[
            "固定评测集质量回归：分数偏差、证据覆盖与延迟皆有报告",
            "访问令牌、限流、日志脱敏与数据库安全设置",
            "模型调用超时与自动重试，复盘支持流式进度",
            "Docker Compose 一键部署（前端 8080 / 后端自动迁移）",
        ],
    ),
    Announcement(
        id="milestone-phase-4",
        type="阶段公告",
        date="2026-10-11",
        title="第四阶段完成：开口练习、客观指标与三人复盘",
        summary="听澜功成：把回答说出来，即得客观指标与三位分析师的接力点评。",
        items=[
            "多提供方语音转录：免费云档与完全离线皆可，未配置时如实标注",
            "语速、停顿、填充词等指标本地计算，不出本机",
            "结构分析师 → 深度分析师 → 表达教练，接力复盘",
        ],
    ),
    Announcement(
        id="fix-phase-2-followup",
        type="维护修复",
        date="2026-10-10",
        title="第二阶段收尾修复：路由切换与开发服务监听",
        summary="两处水下暗礁清除，行船更稳。详见 docs/STATUS.md 第二阶段收尾修复记录。",
        items=[
            "修复页面导航偶发白屏：移除路由切换动画竞态",
            "修复 Vite 仅监听 IPv6 导致 127.0.0.1 无法访问的问题",
        ],
    ),
    Announcement(
        id="milestone-phase-3",
        type="阶段公告",
        title="第三阶段完成：出题有据、能力有图、匹配有证",
        summary="知识库喂养问澜，真实评分织出能力星图，简历与岗位对答皆有原文为证。",
        items=[
            "知识文档上传与检索，出题证据标注出处与匹配分",
            "能力维度画像与自适应训练建议（真实历史报告驱动）",
            "简历与岗位匹配，命中与缺失均附原文证据",
        ],
    ),
    Announcement(
        id="milestone-phase-2",
        type="阶段公告",
        title="第二阶段完成：真实 AI 面试核心",
        summary="面试全程接入真实模型：问题由模型生成，追问由模型决断，评分可解释。",
        items=[
            "面试任务全程持久化，状态机管理进度",
            "可解释评分：四维度分项、原文证据与改进建议",
        ],
    ),
    Announcement(
        id="milestone-phase-1",
        type="阶段公告",
        title="第一阶段完成：基础工程与设计系统",
        summary="观澜的龙骨铺下：工程骨架、统一设计令牌与组件库、路由与动效体系。",
        items=["FastAPI + React + TypeScript 工程就绪，健康检查与测试通过"],
    ),
]


# ---------------------------------------------------------------------------
# 置顶技术档案：12 章节正文。
# 事实来源：frontend/package.json、backend/requirements.txt、app/config.py、
# app/main.py、app/models.py、app/services/*、docs/STATUS.md 与 2026-10-14
# pytest 回归结果（309 项全部通过）。环境变量只写名称，不写任何取值。
# ---------------------------------------------------------------------------

TECH_ARCHIVE_SECTIONS: list[ArchiveSection] = [
    ArchiveSection(
        id="overview",
        heading="01｜项目概览",
        paragraphs=[
            "观澜 AUREL（取意「观水有术，必观其澜」）是一个面向大学生与求职者的 AI 职业成长平台，"
            "品牌理念为「见微知远，向新而行」。项目围绕模拟面试、岗位理解、简历优化与职业规划四条主线，"
            "帮助用户看清自己的能力水位，再把远方的目标拆成可走的每一步。",
            "开发状态：后端 `pytest` 全量测试 309 项于 2026-10-14 回归全部通过。本档案所列能力均以"
            "真实源代码与测试结果为据，未实现的部分明确标注，不把规划当作成果。",
        ],
        bullets=[
            "核心目标：模拟面试（问澜）、岗位理解（知岗/知潮）、简历优化（履历成章/合契）、"
            "职业规划（知途/小鸥）与能力提升（观己/度衡/回澜/听澜）。",
            "使用场景：个人独立走完求职练习闭环——读懂一个岗位，练一场面试，沉淀错题，"
            "修订简历，再规划下一步。",
            "工程规模：前端 23 个路由页面，后端 19 个路由模块与 40+ 业务服务，数据库 32 张表。",
        ],
    ),
    ArchiveSection(
        id="frontend",
        heading="02｜前端技术栈",
        paragraphs=[
            "前端为单页应用（SPA），位于 `frontend/`；以下版本均取自 `package.json` 实际声明。",
        ],
        bullets=[
            "框架：`React ^19.3.0`，函数组件与 Hooks；未引入独立状态管理库，使用 React 内置 state "
            "与 Context（认证、新手引导）。",
            "语言：`TypeScript ~6.0.2`，全量类型定义集中在 `src/types.ts`，`tsc --noEmit` 类型检查独立成脚本。",
            "路由：`react-router-dom ^7.18.4`；公开页（首页/观澜之意/澜讯/认证/技术档案）与工作台分区，"
            "工作台全部经 `RequireAuth` 登录守卫。",
            "样式：`Tailwind CSS ^3.4.19`，自定义设计令牌（surface/mist/shallow/ripple/brand/ink/line "
            "色板与 card/raised 阴影层级），磨砂玻璃表面由全局 CSS 令牌统一实现。",
            "动画：`motion ^14.1.0`，`MotionConfig reducedMotion=\"user\"` 全站尊重系统减动效；"
            "背景水纹等轻动效由 CSS keyframes 实现。",
            "图标与图表：图标用 `lucide-react ^1.55.0`；能力星图、成长热力图、海洋流光进度等"
            "均为手写 SVG/CSS 组件，未引入图表库。",
            "网络层：原生 `fetch` 封装（`src/api/client.ts`），统一 `ApiError` 与 `/api/v1` 前缀；"
            "知途对话与听澜工作流使用 SSE 流式读取。",
            "语音采集：浏览器 `MediaRecorder` API 录音上传，转录在后端完成。",
            "构建与工具链：`Vite ^8.3.0`（dev 服务器 `/api` 代理至后端 8000 端口）、"
            "`ESLint ^10.12.0` + `typescript-eslint`；脚本 `dev` / `build`（`tsc && vite build`）/ `lint` / `typecheck`。",
            "如实说明：无前端单元测试框架，也未引入编辑器等重型第三方库；质量保障依赖类型检查、"
            "构建检查、后端全量接口测试与浏览器实测。",
        ],
    ),
    ArchiveSection(
        id="backend",
        heading="03｜后端技术栈",
        paragraphs=[
            "后端位于 `backend/`，运行于 `Python 3.13`，依赖以 `requirements.txt` 为准。",
        ],
        bullets=[
            "框架：`FastAPI >=0.115.0` + `uvicorn[standard]`；API 统一 `/api/v1` 前缀，`app/routers/` "
            "下 19 个路由模块（health、auth、announcements、catalog、interviews、knowledge、skills、"
            "matching、expression、jobs、job_library、resumes、mistakes、challenges、stats、career、"
            "career_intelligence、observability、privacy）。",
            "校验：`Pydantic v2`（>=2.7.0）定义全部请求/响应模型，输入边界统一校验。",
            "服务层：`app/services/` 40+ 业务模块（出题、评分、检索、JD 解析、简历解析与导出、ASR、"
            "音频指标、错题算法、知途记忆与规划、模型客户端等）；路由层只做参数校验与编排。",
            "中间件：CORS 白名单（默认放行本地 5173 开发源）、请求限流（默认 120 次/分钟）、"
            "跨站写请求 Origin 校验。",
            "文档与导出：`pypdf`、`python-docx` 安全提取上传文档文本；`reportlab` 生成 PDF 简历导出，"
            "支持中文显示。",
            "并发模型：同步 `def` 路由由 FastAPI 线程池执行，不阻塞事件循环；模型调用经共享 `httpx` "
            "连接池复用连接。",
            "配置与日志：集中配置（`app/config.py`）读取环境变量，缺失项明确报告；统一日志初始化，"
            "错误消息面向用户可读，不落敏感信息。",
            "启动流程：建表与幂等迁移（补列、废弃表清理）→ 知潮种子岗位导入（失败不阻塞启动）→ "
            "挂载中间件与路由。",
        ],
    ),
    ArchiveSection(
        id="database",
        heading="04｜数据库与数据访问层",
        paragraphs=[
            "数据库默认使用 `SQLite`（单文件 `aurel.db`），可通过 `AUREL_DATABASE_URL` 环境变量切换；"
            "数据访问层为 `SQLAlchemy >=2.0` ORM，`Alembic >=1.13` 迁移配置就绪。除公开公告外，"
            "全部业务表携带 `user_id` 字段，接口层逐条校验数据归属，杜绝跨用户访问。",
        ],
        bullets=[
            "账户与会话：`users`、`user_sessions`（仅存会话令牌的 SHA-256 摘要，不存原文）。",
            "问澜：`interview_tasks`（状态机管理进度）、`interview_questions`（主问/追问 + 评分量规）、"
            "`interview_answers`、`interview_reports`（四维可解释评分）。",
            "知藏与检索：`knowledge_documents`、`knowledge_chunks`（分块索引，检索增强出题）。",
            "知岗/知潮：`job_analyses`（证据核验 + 推断标注 + JD 内容哈希版本）、`job_positions`、"
            "`job_position_changes`（内容哈希去重与变更历史）、`job_favorites`。",
            "履历成章/合契：`resumes`、`resume_versions`（版本快照）、`resume_match_records`。",
            "听澜：`expression_analyses`（转录 + 音频/表达指标 + 多角色工作流结果）。",
            "度衡/回澜：`challenge_runs`（服务端计时）、`mistake_cards`（SM-2 间隔重复）。",
            "知途：`career_conversations`、`career_messages`、`career_profiles`、`career_profile_facts`"
            "（事实三态管理）、`career_plans`、`career_plan_actions`（7/30/90 天行动）、"
            "`career_plan_revisions`（版本快照）、`career_skill_nodes`/`career_skill_edges`（四态图谱）、"
            "`career_path_comparisons`、`career_workflow_runs`、`career_knowledge_chunks`（RAG 检索）。",
            "观测与评测：`llm_call_records`（模型调用全量记录：服务、模型、提示词版本、重试次数、"
            "耗时、token 用量）、`career_eval_runs`（质量评测）。",
            "迁移方式：启动时自动 `create_all` 并执行幂等迁移（补列、表重建、清理废弃表）；"
            "`alembic` 供正式迁移管理。",
        ],
    ),
    ArchiveSection(
        id="ai",
        heading="05｜AI 模型与接口架构",
        paragraphs=[
            "AI 能力统一经火山方舟（Volcano Ark）Chat Completions 接口接入（OpenAI 兼容协议）。"
            "接入地址、密钥与模型分别由环境变量 `ARK_BASE_URL`、`ARK_API_KEY`、`ARK_MODEL` 配置——"
            "密钥仅存于服务端环境变量，本档案不展示任何取值。",
            "全部模型调用经 `app/services/ark_client.py` 统一封装，业务层不直接接触 HTTP 细节；"
            "每次调用落库 `llm_call_records` 供观测与复盘。",
        ],
        bullets=[
            "三种调用形态：`chat`（完整回复，用于评分/解析类任务）、`chat_json`（结构化 JSON，"
            "温度 0.3 + 健壮解析，容忍代码块包裹）、`chat_stream`（SSE 增量流式，用于知途对话与听澜工作流）。",
            "连接复用：模块级共享 `httpx.Client` 连接池（复用 TCP/TLS 连接，上限 32 连接），"
            "消除每次请求重复握手开销。",
            "容错：超时分离配置（连接 10 秒 / 总 120 秒）；网络错误与 429/5xx 指数退避自动重试"
            "（最多 2 次，尊重 Retry-After）；流式一旦产出内容不再重试，中断即报错并保留已生成部分。",
            "提示词管理：`prompt_registry` 统一登记版本；上下文按需组装——知途采用分层记忆"
            "（确认事实 + 相关历史 + 会话摘要 + 近期窗口），不无限累积全量聊天记录。",
            "实验分流：支持按百分比分流实验模型（`LLM_EXPERIMENT_MODEL`），便于评测对比。",
            "语音识别：多提供方设计（`ASR_PROVIDER`）——云端 `siliconflow`（SenseVoice）、"
            "本地 `local`（faster-whisper）、`volcengine` 可选；语速、停顿、填充词等指标全部本地计算，"
            "不出本机。",
            "状态说明：以上链路均经真实调用验证；模型可用性依赖凭证配置，未配置时接口明确报告"
            "配置缺失，绝不以假结果冒充。",
        ],
    ),
    ArchiveSection(
        id="security",
        heading="06｜身份认证与安全机制",
        paragraphs=[
            "认证体系为用户名 + 密码（第十六阶段起，邮箱验证码体系已整体移除）。注册需用户名"
            "（3-24 位，唯一、不分大小写）、密码（8-64 位，须含字母与数字）与昵称。",
            "安全机制以服务端为准，前端隐藏仅作体验优化；数据隔离与权限校验在每个后端接口强制执行。",
        ],
        bullets=[
            "密码存储：PBKDF2-SHA256（Python 标准库实现，240,000 次迭代 + 随机盐），校验使用常数时间比较；"
            "登录失败统一提示，未知用户同样执行等量计算以防用户枚举。",
            "会话：登录后下发不透明高熵随机令牌，经 `HttpOnly` Cookie 保存，服务器仅存 SHA-256 摘要；"
            "登出真实撤销服务端会话；`AUREL_COOKIE_SECURE` 可启用 Secure Cookie，会话默认有效期 168 小时。",
            "写保护与限流：跨站写请求校验 Origin；CORS 仅放行白名单来源；全站请求限流（默认 120 次/分钟）。",
            "路由守卫：前端 `RequireAuth` 拦截未登录访问；后端受保护接口逐一校验登录状态与数据归属，"
            "业务数据按 `user_id` 隔离。",
            "密钥管理：模型密钥、访问令牌等全部仅存服务端环境变量，前端代码与接口响应不含任何密钥；"
            "后端对缺失配置精确报告变量名，不向匿名请求泄露内部信息。",
            "文件安全：上传校验类型与大小；DOCX/PDF 仅提取文本内容，不执行文件内部指令。",
            "如实说明：生产环境 HTTPS 与反向代理尚未部署（见第十节），当前安全基线面向本地与容器环境验证。",
        ],
    ),
    ArchiveSection(
        id="modules",
        heading="07｜核心业务功能与模块架构",
        paragraphs=[
            "功能以观澜品牌词汇命名，全部经真实页面、路由与后端接口实现；下表状态以 2026-10-14 "
            "代码与测试为据。",
        ],
        table_head=["模块", "路由", "状态", "承担职责"],
        table_rows=[
            ["行舟", "/app", "已实现", "个人工作空间：成长热力图、连续打卡、澜记周报与模块导航"],
            ["问澜", "/interview/new", "已实现", "AI 模拟面试：行业职业目录选题、题目生成、动态追问、四维可解释评分报告"],
            ["知途", "/career-guide", "已实现", "AI 职业规划（小鸥）：分层记忆、事实三态、7/30/90 天计划、能力图谱、多径对照、规划版本复盘，端到端流式对话"],
            ["观己", "/skills", "已实现", "能力维度画像与目标岗位星图对照（真实历史报告驱动）"],
            ["回响", "/reports", "已实现", "评分报告列表与详情回看"],
            ["度衡", "/challenges", "已实现", "限时挑战：服务端计时、超时判定、提交后评估"],
            ["回澜", "/mistakes", "已实现", "错题本：SM-2 间隔重复安排错题重逢"],
            ["知岗", "/jobs", "已实现", "JD 结构化解析：证据核验、推断标注、版本历史、用户可修订"],
            ["知潮", "/job-library", "已实现", "真实岗位资料库：官方来源、内容哈希去重、核验状态与过期标记"],
            ["履历成章", "/resume", "已实现", "结构化简历编辑、七款版式模板、版本管理、PDF/Word 真实导出；AI 仅生成建议，经确认才可保存"],
            ["合契", "/matching", "已实现", "岗位 × 简历匹配：命中与缺失均附两侧原文证据，分数附口径说明"],
            ["知藏", "/knowledge", "已实现", "知识文档上传、分块索引、检索增强出题（证据标注出处）"],
            ["听澜", "/expression", "已实现", "语音转录、客观表达指标（语速/停顿/填充词）与三分析师接力复盘"],
            ["协奏", "/concerto", "已实现", "结构、深度、表达多角色工作流的执行与结果呈现"],
            ["澜讯", "/announcements", "已实现", "平台公告系统；本技术档案即经此系统置顶发布"],
            ["引航", "全站", "已实现", "五步新手引导：首次进入自动开启，可随时重游"],
            ["拾阶", "—", "已下线", "成长路线功能于第十二阶段功成身退，入口与说明已移除"],
        ],
    ),
    ArchiveSection(
        id="design",
        heading="08｜视觉设计系统与交互体验",
        paragraphs=[
            "视觉体系遵循「观澜」设计关键词：自然、清新、优雅、简约、现代东方意境——"
            "高级感来自布局、留白、颜色层次与细节，而非堆叠动画。",
        ],
        bullets=[
            "四景背景：`PageBackground` 组件按路由分景——认证页深夜蓝海、观澜之意日落、澜讯薰衣草花田、"
            "工作区雪景；本地底图按场景专用、互不混用。",
            "玻璃表面：三层结构（背景图层 → 全局遮罩 → `glass-surface` 玻璃面板），`backdrop-filter` "
            "模糊 + 饱和度微调 + 细腻白边，正文永远置于玻璃面板内而非照片上；不支持 backdrop-filter 的"
            "浏览器自动回退高不透明度。",
            "设计令牌：雾白主背景 `#F8FBFF`、云水蓝渐变（mist/shallow/ripple）、主蓝 `#4D83D6`、"
            "深海蓝文字 `#263B57`、细线 `#DCE8F7`，全站统一引用。",
            "排版：Editorial 编辑式画布布局，侧边栏按「启程/洞察/知行」三组导航；卡片悬停轻微上移、阴影加深。",
            "动效：淡入、微位移、水纹轻动；全站支持 `prefers-reduced-motion`；桌面端低透明度鼠标跟随光晕"
            "（触屏与减动效模式下关闭）。",
            "品牌组件：原创矢量 Logo、小鸥悬浮伙伴（海鸥吉祥物，悬停轻语、点击直达知途）、"
            "首页暖心寄语（7 秒轮换、逐字波浪浮现）。",
            "加载体系：AurelProgress 海洋流光进度系统统一全站异步反馈——不确定任务用流光 + 真实已耗时，"
            "不伪造百分比；47 条分场景等待文案。",
            "首页：真实海景照片背景，多层独立波纹与光反效动效，标题入场与座右铭延迟淡入。",
        ],
    ),
    ArchiveSection(
        id="quality",
        heading="09｜开发质量与测试体系",
        paragraphs=["测试数字均来自真实执行结果，不以「配置存在」代替「运行验证」。"],
        bullets=[
            "后端：`pytest` 全量接口与单元测试，2026-10-14 回归 309 项全部通过；覆盖认证会话、"
            "面试全流程、RAG 检索、评分、简历解析与导出、匹配、知途记忆与规划、知潮数据核验、"
            "限流与访问控制等。",
            "AI 测试：测试中以 MockTransport 注入模拟模型响应，不依赖真实凭证；线上调用另有固定评测集"
            "（18 个用例）+ 规则判定器做质量回归，非模型自评。",
            "前端：`eslint`、`tsc --noEmit`、`vite build` 三道检查均须通过；无单元测试框架（如实记录），"
            "功能验证依赖浏览器实测。",
            "外部服务：语音多提供方在未配置时如实标注状态；模型凭证缺失时明确报告配置阻塞，不以假结果冒充。",
            "持续集成：暂未配置 CI，测试为本地手动执行（列入下一阶段计划，见第十一节）。",
        ],
    ),
    ArchiveSection(
        id="deployment",
        heading="10｜部署与运行方式",
        paragraphs=[
            "项目当前以本地开发与 Docker 容器化两种方式运行，尚未接入公网生产环境。",
        ],
        bullets=[
            "本地开发：后端 `uvicorn app.main:app`（默认 127.0.0.1:8000），前端 `npm run dev`"
            "（Vite 5173，`/api` 代理至后端）。",
            "容器部署：`docker-compose.yml` 一键编排——前端构建镜像并暴露 8080 端口，后端容器启动时"
            "自动执行建表迁移，并挂载数据卷与模型缓存卷。",
            "环境变量清单（均无默认密钥，取值由部署方提供）：`AUREL_DATABASE_URL`（数据库地址）、"
            "`ARK_BASE_URL` / `ARK_API_KEY` / `ARK_MODEL`（模型接入）、`ASR_PROVIDER` 及语音相关 `ASR_*`"
            "（语音识别）、`AUREL_ACCESS_TOKEN`（可选访问令牌）、`AUREL_RATE_LIMIT_PER_MINUTE`（限流阈值）、"
            "`AUREL_SESSION_TTL_HOURS`（会话有效期）、`AUREL_COOKIE_SECURE`（Secure Cookie 开关）。",
            "初始化：首次启动自动建表与幂等迁移；知潮种子岗位自动导入（失败不阻塞启动）。",
            "未完成事项：域名、HTTPS 证书与反向代理等生产部署环节尚未落地，为下一阶段工作。",
        ],
    ),
    ArchiveSection(
        id="progress",
        heading="11｜当前进展与待完善方向",
        paragraphs=[
            "以下状态严格区分「已验证」（有真实执行结果）与「已实现」（代码在册、主流程可用）。",
        ],
        bullets=[
            "已验证：认证与会话全流程；问澜出题-作答-追问-评分-报告全链路；知藏检索出题；知岗解析与修订；"
            "知潮岗位库与合契匹配；履历成章编辑、模板与导出；听澜转录、指标与工作流；知途对话、记忆与规划；"
            "度衡与回澜——以上均被 309 项后端测试覆盖。",
            "已实现：四景背景与玻璃体系、AurelProgress 进度系统、小鸥伙伴与暖心寄语、引航引导、"
            "澜讯公告与本技术档案。",
            "已知限制：模型能力依赖火山方舟凭证，未配置时相关功能明确报告阻塞；知途 RAG 向量为 128 维"
            "词面哈希方案（如实现状，语义召回弱于神经网络向量）；本地 Whisper 对非 WAV 音频依赖 PyAV 环境"
            "（新版 PyAV 与 Python 3.13 兼容问题），当前经 WAV 本地解码与云端提供方绕行；前端无单元测试与 CI。",
            "下一阶段：移动端真机细节打磨、生产环境部署（域名/HTTPS/反代）、RAG 语义向量升级评估、"
            "评测集持续扩充。",
        ],
    ),
    ArchiveSection(
        id="changelog",
        heading="12｜技术档案的更新记录",
        paragraphs=[
            "版本记录仅收录有据可查的变更，日期取自开发记录与各阶段公告；更早细节见下方各阶段公告。",
        ],
        table_head=["更新日期", "范围", "说明"],
        table_rows=[
            ["2026-10-14", "本篇", "技术档案建立：首次系统记录技术栈、架构、模块状态与测试情况，置顶于澜讯"],
            ["2026-10-14", "第十六至十九阶段", "用户名密码认证替换邮箱验证码、四景背景体系、小鸥伙伴与暖心寄语、全站 AI 性能优化与海洋流光进度系统"],
            ["2026-10-13 ~ 10-14", "第九至十五阶段", "回澜错题本、度衡限时、协奏工作流、拾阶下线、知潮岗位库、知途图谱与多径对照"],
            ["2026-10-10 ~ 10-11", "第一至五阶段与 v0.3.0", "工程骨架、真实 AI 面试核心、知识库出题、能力星图、语音复盘、质量评测与部署就绪"],
            ["日期待记", "第六至八阶段", "账户认证、知岗解析、履历成章、品牌标志与引航引导、编辑式版面改版（具体日期未记录，见对应公告）"],
        ],
    ),
]


@router.get("")
def list_announcements() -> dict:
    """澜讯列表：置顶档案永远在最前，其余按时间新旧排列（无日期的排后）。"""
    pinned = [a for a in ANNOUNCEMENTS if a.pinned]
    dated = [a for a in ANNOUNCEMENTS if a.date and not a.pinned]
    undated = [a for a in ANNOUNCEMENTS if not a.date and not a.pinned]
    dated.sort(key=lambda a: a.date or "", reverse=True)
    return {"items": [a.model_dump() for a in pinned + dated + undated]}


@router.get("/project-tech-archive")
def get_tech_archive() -> dict:
    """置顶技术档案详情：公告元数据 + 12 章节完整正文。"""
    for announcement in ANNOUNCEMENTS:
        if announcement.id == "project-tech-archive":
            return {
                "announcement": announcement.model_dump(),
                "sections": [s.model_dump() for s in TECH_ARCHIVE_SECTIONS],
            }
    raise HTTPException(status_code=404, detail="技术档案不存在")
