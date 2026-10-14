# AUREL 观澜 — 项目状态

更新时间：2026-10-14（仓库清理与工程化：代码分割、CI、README 重写、引航与澜讯内容更新）

## 仓库清理与工程化（已完成，2026-10-14）

### 仓库与文档清理

- 删除 AI 制作痕迹文件：`docs/design/` 两张设计参考图、[AiStatusBadge.tsx](../frontend/src/components/AiStatusBadge.tsx)（「AI 未配置」标识组件及其 hook `useAiStatus`，移除 8 个页面挂载）、`backend/scripts/integration_real.py` 开发期脚本；`ServiceStatus`（连接故障提示，非 AI 标识）保留
- [README.md](../README.md) 重写（273 → 约 100 行）：删除写死的模型 ID、已被移除的邮件验证码章节与死接口、过时开发阶段与演示流程；技术栈、快速开始、测试、Docker 部署、安全约定均与当前代码对齐
- 澜讯公告下线 11 条前期开发过程公告（第一阶段~第五阶段、v0.3.0 发布等），保留 5 条近期核心公告 + 置顶技术档案；[test_announcements.py](../backend/tests/test_announcements.py) 断言更新为「历史条目不得复活、保留公告须带日期」
- 引航引导第五步由「名笺」改为「知途问津 · AI 职业规划」（真实页面截图 `onboarding-career.png`），前四步文案按最新功能润色；旧名笺截图删除
- GitHub 仓库描述已通过 API 更新为英文简介

### 缺陷修复

- 工作台「本周澜记」周报请求在页面切换时被中止，每次留下 `net::ERR_ABORTED` 控制台噪声（浏览器网络层行为，JS 无法抑制）：[DashboardPage.tsx](../frontend/src/pages/DashboardPage.tsx) 改为模块级 60 秒缓存 + 在途请求去重，重复进入不重复请求；[client.ts](../frontend/src/api/client.ts) 的 `request` 对 AbortError 原样透传避免误报网络错误。浏览器实测刷新与多次往返 console 全净

### 工程化

- 路由级代码分割：[App.tsx](../frontend/src/App.tsx) 全部 22 个页面改为 `React.lazy` 动态导入（4 个命名导出页面在 `then` 中适配默认导出），Suspense fallback 为轻量旋转占位；生产构建主 chunk **852KB → 275KB（gzip 239 → 87KB，约 -63%）**，页面按需加载
- 新增 [.github/workflows/ci.yml](../.github/workflows/ci.yml)：push / PR 自动执行前端（npm ci + lint + typecheck + build）与后端（pip install + pytest）双 job，Node 22 / Python 3.13 并配依赖缓存

### 验证

- 后端 pytest 311/311 通过；前端 eslint / tsc / vite build 全绿；浏览器实测引航五步（第五步知途截图正确）、澜讯仅剩 1 置顶 + 5 条近期公告、懒加载路由切换正常、控制台无错误

## 海蓝微光：全站鼠标跟随光效重做（已完成，2026-10-14）

### 原问题根因

- [index.css](../frontend/src/index.css) 中 `.pointer-glow` 为 **36rem（576px）直径、中心透明度 0.3** 的大光斑——即「大面积、过于明显」的元凶
- 跟随缓动系数仅 0.08，感知明显拖后；鼠标停止后光斑**永久常亮**（无淡出）；无分页面强度，所有场景同一强度

### 新实现

- [PointerGlow.tsx](../frontend/src/components/PointerGlow.tsx)：重写为「海蓝微光」——主体 48–64px、透明度 0.055–0.11 冰蓝/雾蓝；跟随系数 0.22（基本跟手仍带呼吸感）；停止约 0.9s 后经 CSS 过渡（1100ms ease-out）自然淡出，移动时重新点亮，初始与空闲态均不可见；ambient 档新增滞后微光点（同元素 `::after`，透明度由两点距离自然驱动 ≤0.06，停止即贴合归零），快速移动时带出一条极淡短光痕——零额外 DOM、零额外监听。仍为 rAF + CSS 变量方案，不触发 React 渲染，组件卸载完整清理监听与动画帧；`pointer: fine` / `prefers-reduced-motion` 双重 gating，触屏与降动效完全关闭
- 分档强度（全站统一组件，无页面重复实现）：`ambient`（主页，最完整含光痕）→ `soft`（观澜之意，雾蓝协调夕阳）→ `deep`（认证页，深蓝避免玻璃过亮）→ `faint`（澜讯与技术档案）→ `whisper`（工作区全部页面含面试预览/进行，最克制）
- [index.css](../frontend/src/index.css)：`.pointer-glow` 区块重写（五档尺寸/配色变体 + `--idle` 淡出 + `pointer: coarse` 隐藏）；无 z-index 且组件位于正文 DOM 之前，天然处于装饰层；`pointer-events: none` 不拦截交互
- 挂载：新增 [HomePage.tsx](../frontend/src/pages/HomePage.tsx)（此前首页无光效）；其余 7 处（Auth/About/Announcements/TechArchive/AppLayout/InterviewPreview/InterviewSession）统一换用分档 prop；按钮/导航/输入框一律沿用自身 hover/focus/active 反馈，全局光效不随控件交互放大

### 验证

- 前端 eslint / tsc --noEmit / vite build 全绿；浏览器实测（evaluate 断言）：首页 ambient 64px、移动后 `--glow-x/y` 同步更新并点亮、停止 2.5s 后重新淡出；澜讯/档案 faint 48px 且光痕 `::after` 为 none；关于 soft 56px；工作区 whisper 48px；认证页 deep 48px（需未登录访问，已登录会被重定向到 /app 看到工作区 whisper 档，属预期）；触屏由 `pointer: coarse` CSS 兜底；控制台无本次改动引入的错误（stats/weekly 的 ERR_ABORTED 为登录态下工作台请求被导航打断的既有噪声，与光效无关）



## 澜讯置顶：项目介绍栏目「一舟览澜」+ AI 连接层再提速（已完成，2026-10-14）

### 内容与数据

- [announcements.py](../backend/app/routers/announcements.py)：`Announcement` 模型扩展可选字段 `pinned` / `tags` / `importance` / `updated_at`；新增置顶公告 `project-tech-archive`（标题「观澜 AUREL｜一舟览澜：项目介绍与技术纪实」，分类「项目档案」、重要、四枚标签），正文 12 章节（概览/前端/后端/数据库/AI/安全/模块/视觉/测试/部署/进展/更新记录）以 `ArchiveSection`（段落/要点/表格）结构化存放，全部内容取自真实源代码、依赖声明与 2026-10-14 pytest 回归结果；新增详情端点 `GET /api/v1/announcements/project-tech-archive`
- 置顶逻辑：列表端点按「置顶 → 有日期倒序 → 无日期」排序，置顶栏目不受普通公告排序与分页影响；列表中仅展示特殊标记的入口条目（不展开正文），点击进入独立阅读页；公告数据仍为代码内静态记录（无数据库表），如实定位
- [test_announcements.py](../backend/tests/test_announcements.py)：新增置顶唯一性与详情端点 12 章节、敏感信息零泄露断言

### 前端

- [AnnouncementsPage.tsx](../frontend/src/pages/AnnouncementsPage.tsx)：新增 `PinnedArchiveEntry` 置顶栏目条目（浅琥珀描边渐变 + 琥珀「置顶」标签 + 蓝色文档图标方块 + 两行截断摘要 + 更新时间 + 「阅读完整档案 →」），置于标题与普通公告列表之间，不与普通公告混排；普通公告列表过滤置顶项，原有渲染不变
- 新增 [TechArchivePage.tsx](../frontend/src/pages/TechArchivePage.tsx)（公开路由 `/announcements/tech-archive`）：薰衣草背景 + glass-notices 大阅读区渲染 12 章节；章节序号琥珀着色、反引号代码名词经 [inlineCode.tsx](../frontend/src/lib/inlineCode.tsx) 渲染为浅蓝底等宽样式、表格横向可滚；含返回澜讯、加载与错误重试态
- [types.ts](../frontend/src/types.ts) 与 [client.ts](../frontend/src/api/client.ts)：扩展 `AnnouncementItem` 可选字段，新增 `TechArchiveSection` / `TechArchiveDetail` 与 `api.getTechArchive()`

### AI 连接层再提速

- [ark_client.py](../backend/app/services/ark_client.py)：共享连接池 `keepalive_expiry` 30s → 300s（用户两次 AI 操作常间隔数分钟，30s 保活导致连接频繁失效重建；服务端提前断开时 httpx 自动重连，安全）；新增 `warmup_connection()`——启动时后台线程预完成与模型服务的 TCP/TLS 握手，消除重启后首次调用的建连延迟（失败静默、未配置密钥时跳过）；`chat` / `chat_stream` 支持可选 `max_tokens`，`chat_json` 统一设 6000 生成上限，防止结构化输出偶发长尾拖长等待（正常输出在 EOS 自然停止，不受影响）
- [main.py](../backend/app/main.py)：启动流程接入 `warmup_connection()`

### 验证

- 后端 pytest 311 项全部通过；前端 eslint / tsc --noEmit / vite build 全绿；浏览器实测：置顶栏目条目形态（无正文展开、琥珀特殊标记）、点击进独立阅读页、12 章节完整、返回导航、移动端视口无溢出、控制台无错误均通过；后端已重启生效


## 第十九阶段：全站 AI 性能专项优化与海洋流光进度系统（已完成，2026-10-14）

### 后端真实提速

- [ark_client.py](../backend/app/services/ark_client.py)：新增模块级共享 httpx.Client 连接池（`_shared_http_client`，线程安全、atexit 关闭、MockTransport 注入兼容保留独立客户端），`chat()` 经模块级 `_post()` 走共享池，`chat_stream()` 无注入时复用共享池——消除每次模型调用重复的 TCP/TLS 握手；超时/重试/观测逻辑不变
- 测试同步：test_stability.py 五处 patch 点由 `ark_client.httpx.post` 迁移至 `ark_client._post`
- 架构核查结论：全部路由为同步 `def`（FastAPI 线程池执行，无事件循环阻塞）；知途对话已有端到端真流式（chat_stream + SSE）；题集/评分/解析等 JSON 结构化输出保留完整结果模式

### 前端统一进度系统（新增 aurel-progress）

- [AurelProgress](../frontend/src/components/aurel-progress/AurelProgress.tsx)：海洋流光进度条——冰蓝→天蓝→主蓝→深海蓝渐变、水光纹理流动、前沿高光亮斑、呼吸感；不确定模式（默认）与确定模式双支持；错误/取消/超时转静止柔和警示色
- [AurelLoading](../frontend/src/components/aurel-progress/AurelLoading.tsx)：统一加载容器（条+文案+真实已耗时+重试）
- [AurelTaskStatus](../frontend/src/components/aurel-progress/AurelTaskStatus.tsx)：AI 长任务面板（任务名+状态徽标+耗时+取消/重试）
- [useAsyncTask](../frontend/src/components/aurel-progress/useAsyncTask.ts)：状态机 idle/preparing/loading/streaming/success/error/cancelled/timeout，防重入、真实计时、可选超时、AbortController 取消；终态立即结束动画
- [useRotatingCopy](../frontend/src/components/aurel-progress/useRotatingCopy.ts)：长任务文案缓慢轮换（7s，不代表进度，reduced-motion 不轮换）
- [waitingCopy.ts](../frontend/src/lib/waitingCopy.ts)：47 个场景等待文案配置（通用操作/AI 通用/问澜/知途/观己/拾阶/度衡/知岗/履历成章/合契/知藏/听澜/协奏），preparing 阶段统一「正在为你理清眼前的线索……」，流式场景覆盖
- [index.css](../frontend/src/index.css)：流光动画 keyframes（aurel-shimmer-flow/wave-drift/indeterminate/breath），prefers-reduced-motion 全部降级为静态

### 全站接入（按钮级+长任务面板）

- 问澜会话页：提交回答「面试官凝思」面板（追问决策文案）、报告生成「观澜鉴析」面板（失败保持面板态+重试，修复原失败后 actionError 不可见缺陷）、整页加载流光化
- 问澜新建页：「问澜成题」面板（题集生成真实计时）
- 知途面板：当前情况总结/职业方向探索面板 + 7/30/90 天计划生成面板
- 知岗 JobsPage：岗位解析面板；合契 MatchingPage：拖拽匹配与资料库岗位匹配双面板（heqi.match 文案）
- 知藏 KnowledgePage：知识检索面板；履历成章 ResumePage：AI 润色建议面板
- 拾阶 ChallengesPage：出题「限时挑战出题」面板 + 交卷「挑战评分」面板

### 验证

- 后端 pytest 309 项全部通过；前端 lint/tsc/build 全部通过
- 浏览器实测（真实账号+真实模型）：「问澜成题」面板（流光条/场景文案/计时 3s→19s 增长）、生成约 50s 后跳转会话页；「面试官凝思」面板（提交 1 秒内出现，文案+计时 5.5s，按钮禁用），追问正常生成；console 无错误
- 修复过程：useAsyncTask 曾缺 loading 状态推进导致 preparing 文案长期驻留，已修复并复测通过


## 品牌文案润色（已完成，2026-10-14）

- [AboutPage.tsx](../frontend/src/pages/AboutPage.tsx)：观澜之意全文升级——引文深化「不逐大江大河的声势，只认真看见细微波澜」；正文增「沙金沉于水底」「如水位刻度，涨落皆有记录」「如潮水往复，岸线渐新」等意象；能力清单十行全部改为对仗式表述；隐私段以「水静，方能照见人影」起笔。全部事实表述保持不变
- [announcements.py](../backend/app/routers/announcements.py)：新增第十七/十八阶段两条真实公告（「四景入画」「小鸥登船」，2026-10-14，类型徽章与条目齐备）；[AnnouncementsPage.tsx](../frontend/src/pages/AnnouncementsPage.tsx) 页面简介改为「澜讯是观澜的水文志……水面之上是功能，水面之下是工夫」，空状态文案微调
- [OnboardingGuide.tsx](../frontend/src/components/onboarding/OnboardingGuide.tsx)：引航五步文案全部润色（临水初见「见微，方能知远」、扬帆行舟「港湾与水路」、问澜起笔「追问随回答而深」、观己知远「静水照影」、泊岸拾澜「泊岸小憩，再启新程」），副题改为「愿它如灯引水，照见你的方向」；步骤结构、截图与真实栏目的对应关系未动
- 验证：前端 lint/tsc/build 通过；后端重启后浏览器实测三处文案全部生效、排版无溢出

## 第十八阶段：动态暖心寄语 + 小鸥 AI 伙伴（已完成，2026-10-14）

### 本阶段变更

- 暖心寄语：新增文案配置 [warmMessages.ts](../frontend/src/lib/warmMessages.ts)（8 条陪伴语，每条停留 7 秒有序轮换）与展示组件 [WarmGreeting.tsx](../frontend/src/components/WarmGreeting.tsx)——整句 480ms 淡出 + 逐字波浪淡入（位移 3px、延迟 40ms/字、半像素柔化），固定 2em 最小高度防布局跳动；屏幕阅读器读整句（sr-only + 逐字层 aria-hidden）；页面后台时暂停轮换；prefers-reduced-motion 下关闭逐字波动
- 小鸥 Logo：复用项目既有原创海鸥吉祥物 [GullMascot.tsx](../frontend/src/components/GullMascot.tsx)（品牌蓝白矢量 SVG，48px 下轮廓清晰，自带 reduced-motion 支持），未重复造轮子
- 小鸥悬浮入口：新增提示文案配置 [xiaouTips.ts](../frontend/src/lib/xiaouTips.ts)（8 条，全部对应真实功能）与共享组件 [XiaouCompanion.tsx](../frontend/src/components/XiaouCompanion.tsx)——固定右下角（24px 边距 + 64px 圆形玻璃按钮）；桌面悬停 300ms 出玻璃气泡（移入气泡保持、离开 220ms 收起、按序轮换不重置）、点击直达知途；触屏首次轻触出提示、再触进入、点外部收起；键盘可聚焦 Enter/Space 触发；漂浮动画 4.4s/3px，尊重 prefers-reduced-motion
- 点击目标：`/career-guide` 知途——项目内真实存在的小鸥 AI 对话页（流式输出、会话列表、欢迎语「你好，我是小鸥……」），零新增模型调用代码
- 挂载范围：[HomePage](../frontend/src/pages/HomePage.tsx)（寄语在英文座右铭下方）、[AboutPage](../frontend/src/pages/AboutPage.tsx)、[AnnouncementsPage](../frontend/src/pages/AnnouncementsPage.tsx)、[AppLayout](../frontend/src/components/layout/AppLayout.tsx)（覆盖全部工作区路由）；认证页 AuthPage 不挂载；面试预览/进行两个全屏专注流暂不挂载（避免遮挡底部输入区）
- 动效样式：[index.css](../frontend/src/index.css) 新增 warm-char-in / xiaou-float 关键帧及 prefers-reduced-motion 覆盖

### 本阶段验证（全部实际运行）

- 前端 lint / tsc（build 内含）/ 生产构建：全部通过
- 浏览器实测（两轮共 10 项）：主页寄语波浪入场与 7 秒轮换无布局跳动；悬停 400ms 气泡出现、移入气泡保持、移开收起、点击直达 /career-guide；知途真实对话可用（发送「你好」获得流式回复）；工作区 /app 与 /about 挂载正常、/auth 正确隐藏；控制台无新增 JS 错误

### 已知限制

- 知途对话依赖后端已配置的模型服务；本机未配置模型凭证时流式请求会中止并在界面给出明确错误提示（属既有环境限制，非本次改动引入）

## 第十七阶段：四套场景背景与统一磨砂玻璃视觉系统（已完成，2026-10-14）

### 本阶段变更

- 场景背景组件：新增 [PageBackground.tsx](../frontend/src/components/PageBackground.tsx)——`scene` 四值（`auth` / `about` / `notices` / `workspace`）一一对应四张本地底图，禁止混用；固定铺满视口、`pointer-events: none`、随布局复用不重复挂载
- 三层结构（[index.css](../frontend/src/index.css)）：第一层 `page-bg-image-*` 背景图片（`cover` + 每张图配套回退纯色，加载失败不破相）；第二层 `page-bg-mask-*` 全局遮罩（低透明度渐变，仅调亮度色温，不模糊内容）；第三层 `glass-surface` + `glass-auth/about/notices/workspace` 玻璃表面令牌（半透明底色 + `backdrop-filter: blur(14-16px) saturate` + 细腻白边 + 轻柔阴影，`--glass-blur` 变量统一管理），`@supports` 回退提高不透明度；正文容器一律不加 `filter: blur`
- 四张底图落位 `frontend/public/images/backgrounds/`：`auth-night-ocean.jpg` 深夜蓝海 → 认证页；`about-sunset.jpg` 日落海景 → 观澜之意；`notices-lavender.jpg` 午后薰衣草 → 澜讯；`workspace-snow.png` 蓝调雪景 → 行舟工作区全部真实路由
- 页面接入：[AuthPage.tsx](../frontend/src/pages/AuthPage.tsx) 夜海 + 浅蓝白玻璃卡片（页头 logo 与「返回首页」转浅色，登录/注册切换共享同一背景）；[AboutPage.tsx](../frontend/src/pages/AboutPage.tsx) 日落 + 单张暖白玻璃画布承载全部正文（含版权行）；[AnnouncementsPage.tsx](../frontend/src/pages/AnnouncementsPage.tsx) 薰衣草 + 大面积浅紫白玻璃阅读区，公告条目从独立白卡改为面板内细分隔线分隔；[AppLayout.tsx](../frontend/src/components/layout/AppLayout.tsx) 雪景 + 冰白玻璃画布（`rgba(248,251,255,0.86)` 16px 模糊）承载全部 16 个工作区路由，页面切换画布稳定；面试预览/进行两个独立布局页同步接入雪景 + 玻璃画布
- 云团背景组件 `AmbientBackground` 保留（404 页继续使用），其余页面已全部切换为场景背景；业务逻辑、路由、认证、数据请求零改动

### 本阶段验证（全部实际运行）

- 前端 lint / tsc（build 内含）/ 生产构建：全部通过
- 后端 pytest：309 项全部通过（后端无改动，回归确认）
- 浏览器实测（browser_use，共 19 项检查全部 PASS）：认证页夜海图加载、浅色页头可读、玻璃卡片文字清晰、登录/注册标签切换无背景闪烁、输入框交互正常；观澜之意日落图加载、暖白玻璃面板、标题避开太阳高光、版权行在面板内；澜讯薰衣草图加载、玻璃阅读区、分隔线式条目；行舟 /app 与 /skills 切换背景稳定不闪、玻璃画布与侧边栏正常、/me 一致；控制台无错误

### 待人工检查

- 真机移动端视口（浏览器代理无法 resize 视口，已用样式检查替代：侧栏自动收起、画布自适应）
- 个人本地高分屏下玻璃模糊的渲染细节（backdrop-filter 在不同 GPU 下观感略有差异）

## 第十六阶段：认证改造——移除邮箱验证码，改用用户名密码（已完成，2026-10-14）

### 本阶段变更

- 后端模型：`User` 新增 `username`（唯一，比较不区分大小写）与 `password_hash`（PBKDF2-SHA256、240k 迭代，仅用标准库 hashlib 实现，不引入新依赖）；`email` 保留为可空遗留列；`EmailVerificationCode` 模型删除
- 幂等迁移：`ensure_sqlite_columns` 新增旧 users 表重建——PRAGMA 检测旧「邮箱 NOT NULL」结构后，临时关闭外键按官方流程重建表（历史行与 id 全部保留）、重建 username 唯一索引、`DROP TABLE IF EXISTS email_verification_codes`；旧账户记录保留但无用户名密码，无法再登录（本地开发数据可接受）
- 密码服务：`services/password_service.py`（hash / verify，`hmac.compare_digest` 常量时间比较，格式异常一律返回 False）
- 路由重写（[auth.py](../backend/app/routers/auth.py)）：`POST /auth/register`（username/password/nickname）、`POST /auth/login`（username/password）；保留 `/auth/me`、`/auth/logout`；登录失败统一 401「用户名或密码不匹配」防用户枚举（未知用户也做同量级 PBKDF2 计算抹平时序）；停用账户 403；HttpOnly Cookie 会话与登出真实撤销逻辑不变；`/auth/email-status` 端点删除
- 校验规则：用户名 3-24 位中英文/数字/下划线；密码 8-64 位且同时含字母与数字；昵称 2-20 字
- 邮箱子系统整体删除：`email_service.py`、`verification_service.py`、`scripts/send_test_email.py`、`tests/test_email_delivery.py` 删除；`config.py` 邮件提供方/QQ SMTP/`secret_key` 配置段移除；requirements 移除 alibabacloud SDK；`.env.example` 邮件段移除
- 前端：[AuthPage.tsx](../frontend/src/pages/AuthPage.tsx) 表单改为 用户名+密码（注册含昵称与确认密码，客户端校验规则与后端一致），文案寓意化、左栏品牌语同步更新，保留双栏白卡布局与 redirect 回跳；`client.ts` 换为 `register` / `login`；`types.ts` 的 `AuthUser` 去邮箱加用户名；[MePage.tsx](../frontend/src/pages/MePage.tsx) 名笺显示用户名并移除邮箱验证行；[AboutPage.tsx](../frontend/src/pages/AboutPage.tsx) 与澜讯公告文案同步清理邮箱认证描述

### 本阶段验证（全部实际运行）

- 后端 pytest：**309 项全部通过**（331 − 22 项邮箱用例；`test_auth.py` 重写为用户名密码专项：注册成功落 PBKDF2 摘要且响应不含密码/重名 400/非法用户名与弱密码 422/错误密码与未知用户提示一致/停用账户 403/登出服务端真实撤销/跨站写请求 403/跨用户隔离）
- 前端 lint / tsc（build 内含）/ 生产构建：全部通过
- 旧 aurel.db 副本端到端实测：users 表成功重建（username/password_hash 加入、email 转可空）、验证码表删除、注册 201 → 登录 200 → 错误密码 401 统一提示 → /me 识别 → logout 撤销后 /me 未登录，全链路正常

### 注意事项

- 邮箱验证码时代的旧账户无法再登录：数据与业务外键完整性保留，用新用户名重新注册即可
- `backend/.env` 中遗留的 `QQ_SMTP_*` / `MAIL_PROVIDER` 等变量已不再被读取，可自行清理

## 第十五阶段：知途 AI 职业规划高级能力、知识检索与评测系统（已完成）

### 本阶段变更

- RAG 职业知识检索（知藏扩展）：新增 `CareerKnowledgeChunk` 分块模型与 `career_retrieval.py`——知潮岗位摘要/就业指导/知岗解析/知藏文档/档案事实统一分段入库；128 维本地词面哈希向量（如实标注 `local_hashed_term_vector`，不冒充语义向量）；BM25+向量双路 → RRF 融合 → 规则重排（行业/职业/经验过滤、30 天内新近加权、过期资料 -0.2 降权并标注「可能已过期」）；结果附来源链接与依据片段，检索不到时如实返回「没有找到可靠依据」
- 职业能力图谱：`CareerSkillNode/CareerSkillEdge` 两表 + `career_skill_graph.py`——节点四态（verified 已证实 / user_stated 用户自述 / ai_inferred AI 推断 / pending 尚待验证）；问澜报告完成（维度分 ≥75 → verified，否则 pending + improvement_task）、简历保存、知岗解析、档案确认四类真实事件自动同步图谱；AI 提议节点 quote 必须能在材料原文定位，定位不到直接丢弃，且一律 ai_inferred 待确认；verified 只能来自真实练习、不可手工标记或降级
- 多职业路径比较：`career_paths.py`——2-4 个方向并排比较（关联度/技能要求附来源/证据缺口/兴趣限制/学习成本/验证行动），检索知潮真实岗位与知藏证据注入上下文，比较结果与数据依据（含岗位来源链接、招聘状态）保存可回看；不编造薪酬、就业概率或前景预测
- 规划版本与成长反馈：复盘 `review_plan` 基于真实完成统计（done/skipped/pending/overdue）生成新版本，历史 revisions 不覆盖可回看；`growth_feedback` 只来自问澜评分、度衡挑战与行动记录，无记录返回空状态
- 记忆透明化：`GET /memory/usage` 预览一次回答将使用的分层上下文（已确认档案/相关历史召回/会话摘要/近期窗口）；`DELETE /memory` 一键清除全部会话与档案事实重新开始
- 模型质量评测（T4 扩展）：`career_eval_rules.py` 十项确定性规则判定器（录用承诺/薪酬编造/不确定性明示/事实依据/记忆一致/计划可执行/RAG 诚实/证据引用/不安全建议/矛盾澄清）；`eval/career_evalset.json` 18 个人工编制用例覆盖九类场景（信息不足/方向冲突/无真实 JD/前后矛盾/目标变化/长对话记忆/简历核验/RAG 无证据/不安全建议），bad/good 配对保证判定器与人工标注完全一致（judge_accuracy == 1.0，不依赖模型自评）；`run_career_eval.py` 支持离线校验与 `--live` 真实模型违规率评测，运行记录（model/prompt_version/dataset_version/metrics）入库
- 模块联动深化：复盘与差距分析真实读取知岗解析数、简历数、图谱已证实技能与检索证据；问澜/知岗/履历成章完成后自动同步图谱（`interview_service` / `resume_service` / `routers/jobs.py` 钩子）
- 后端路由：`routers/career_intelligence.py` 18 个新端点（graph / paths / retrieval / memory / revisions / review / growth / eval-runs），全部登录隔离、越权 404；提示词注册表新增 4 个版本化条目
- 前端：`CareerAdvisorPanel` 扩展为六标签（档案/计划/图谱/路径/知识/联动）——图谱四态节点管理、路径比较表单与历史记录、知识检索与记忆分层预览；计划详情新增「版本与复盘」（版本列表/复盘建议勾选采纳）；计划列表新增「成长轨迹」真实数据区
- 岗位→知途规划联动补全（第十五阶段补充）：新增 `POST /job-library/{id}/career-plan`——库内真实岗位先确保知岗解析（复用已有解析），再调用现有 7/30/90 天规划生成；`generate_plan` 落库时在 `plan.data_basis` 记录数据版本与岗位解析依据（job_analysis_id/job_title），复盘时继续更新；知潮岗位详情新增「加入知途规划」按钮，成功后提示并可跳转知途
- 图谱手动建边 UI（最终期前补全）：图谱标签新增「手动建立关系」表单（起点/终点节点下拉 + 六种关系类型），调用既有 `POST /graph/edges`，手动关系标注「用户添加」可追溯，节点四态不因此改变

### 本阶段验证（全部实际运行）

- 后端 pytest：331 项全部通过（基线 329 + 新增 2 项岗位→知途规划联动测试：解析复用/独立新计划/跨用户隔离/data_basis 依据记录）
- 前端 lint / tsc / 生产构建：全部通过无错误
- curl 直测（真实模型）：图谱 AI 提议返回 3 个 ai_inferred 节点且依据均可定位；路径比较真实引用美团/腾讯岗位来源并附免责声明；计划生成 + 复盘生成第 2 版（复盘统计「完成 0/待办 11/逾期 0」来自真实数据）；离线评测 judge_accuracy = 1.0（18 例 × 9 场景）
- 岗位→知途规划 curl 真实模型直测：美团 AI全栈工程师岗位生成「美团AI全栈工程师校招冲刺计划」（201，76.7s，含真实知岗解析）；二次调用复用解析（reused_analysis=true，46.8s 仅跑规划）并生成独立新计划；计划列表中新旧计划并存、版本不覆盖
- 浏览器实测：六个标签全部正常渲染（图谱空态+操作按钮/路径表单/知识检索框/档案回归），控制台无错误；未登录访问新端点正确返回 401；「加入知途规划」按钮已通过构建与类型检查（UI 点击实测未做，API 层已真实验证）

### 未实现 / 下一阶段（如实记录）

- 向量检索为本地词面哈希向量（方舟 embedding 接口未开通）；接入真实语义 embedding 后可无缝替换，检索接口结构不变
- `--live` 真实模型评测的违规率报告未做定时运行（可手动 `python -m eval.run_career_eval --live` 执行）
- 「加入知途规划」与「手动建立关系」按钮已通过构建、类型检查与 API 层真实直测，浏览器内点击实操未做（需登录会话）

### 邮件方案最终决策（2026-10-13 用户确认；2026-10-14 起作废）

- （已作废）本节 QQ 邮箱 SMTP 方案随第十六阶段「邮箱验证码认证整体移除、改用用户名密码」而废止，历史记录保留备查

### 文案焕新（品牌语气统一，最终期准备）

- 澜讯公告：重写全部条目文案（观澜水意象语气，事实内核不变），并补齐第六~十五阶段共 8 条真实阶段公告（日期取自开发记录，无据可查的如实标注「日期待记」）；共 14 条
- 观澜之意：引言引入《孟子》出处；能力清单从 8 条扩至 10 条（覆盖问澜/观己/听澜协奏/知岗/知潮/履历成章/合契/知藏/知途/度衡回澜，全部已上线）；正文补入小鸥伙伴叙述
- 引航五步：标题与正文重写为临水初见→扬帆行舟→问澜起笔→观己知远→泊岸拾澜的水意象旅程（栏目对应与截图不变）
- 注册登录：副标题、左栏品牌语、寄码成功与 503 提示曾寓意化（「短笺」「潮信」意象），2026-10-14 用户决定连同海景磨砂改版一并回退为原版文案（见下节）；安全逻辑与真实错误提示未动

### 注册登录页回退（2026-10-14 用户决定）

- 用户决定回退「海景磨砂」注册登录页：[AuthPage.tsx](../frontend/src/pages/AuthPage.tsx) 恢复为原版双栏白卡设计（深蓝品牌左栏 + 白色表单区 + AmbientBackground 云雾背景 + PointerGlow）与原版文案；index.css 中 `.auth-sea-haze` / `.auth-panel` 海景磨砂样式已删除；标题「初入观澜 / 再会观澜」与认证逻辑（发送/冷却/6 位校验/注册登录用途隔离/错误与 503 状态）保留不变
- 同轮曾试作的登录跳转补强（401 会话过期广播与监听跳转）与注册/登录模式切换淡入，按用户决定全部撤销，恢复项目原有实现；既有认证跳转行为不变（RequireAuth 未登录跳转时携带 `?redirect=`、登录/注册成功后回原目标或 `/app`、引航完成标记避免重复弹出）

## 第十四阶段：真实岗位资料库、JD 分析、简历模板与岗位证据系统（已完成）

### 数据来源核对结论（开发前实际访问核对）

- 五个官方来源（美团招聘、Microsoft Careers、腾讯招聘、小米招聘、国家大学生就业服务平台）均公开可访问
- 各站均未提供可授权的公开批量抓取接口/条款，遵循「不绕过访问限制、不批量抓取」原则，采用三种合法途径建立资料库：
  1. **官方公开页面人工核对的真实种子**（`app/data/job_seed.json`，8 条：美团 5 + 小米 1 + Microsoft 1 + 腾讯 1，每条含来源 URL、企业官网链接、事实性摘要，`source_type=official_seed`）
  2. **用户手动导入**（企业/岗位名必填 + 来源链接选填，含 SSRF 防护）
  3. **单条来源链接核验**（仅判断链接是否可打开）
- 未实现自动定时抓取（无授权，如实不做）；不编造任何岗位、薪资与发布时间

### 本阶段变更

**后端：知潮岗位资料库（models / services/job_library.py / routers/job_library.py）**
- 新增 `JobPosition`（唯一ID/来源企业+官网链接/岗位名/行业/职业分类/地点/级别/发布与更新时间/原始URL/来源类型/职责与必需·加分技能·经验四摘要/`content_hash` 内容指纹/`hiring_status`/`link_status`/`display_permission`/发布与核验时间）与 `JobPositionChange`（created/updated/verified/stale 变化留痕）两张表，`ensure_sqlite_columns` 幂等迁移
- 真实性硬规则：来源无发布时间 → 如实标注「来源未提供发布时间」（不伪造）；招聘状态默认 `unconfirmed`「招聘状态未确认」（不默认正在招聘，链接核验也不改变招聘状态）；超过 30 天未核验 → 列表标注「可能已过期」；`display_permission=summary_only` 默认（不永久公开展示完整 JD 原文）
- 导入 `POST /job-library`：`_assert_public_http_url` 拒绝非 http(s)、localhost/.local 域名与 IP 字面量私网地址；核验端点再做 DNS 解析级 `_assert_resolvable_public_host` 内网/保留段拦截（双层 SSRF 防护）
- SHA-256 归一化内容指纹查重（导入与种子幂等）；检索支持关键词/行业/职业/地点/经验阶段/企业过滤与收藏夹；收藏按用户隔离
- 8 个端点：列表 / 详情（含变更时间线）/ 导入 / 收藏切换 / 来源核验 / 库内岗位→知岗解析（同岗位同内容复用已有解析，返回真实 `reused`）/ →问澜出题 / →合契匹配

**后端：知岗扩展（routers/jobs.py）**
- 解析记录新增 `source_job_id` 溯源（来自资料库哪个岗位）；`PATCH /jobs/analyses/{id}` 用户可修改解析结果（evidence/is_inferred 只读原样保留，保存后 `user_edited=true` 前端显示「已由用户修订」徽标）

**后端：履历成章（services/resume_templates.py 新建 / resume_export.py / routers/resumes.py / services/resume_optimize.py）**
- 7 种真实版式差异模板（后端唯一事实源，导出 PDF/DOCX 与前端预览共用同一 section_order）：清爽通用 / 校园应届（教育前置）/ 技术研发（技能置顶）/ 产品运营（项目前置）/ 设计创意（左右分栏 layout=two-column）/ 科研学术（教育与成果前置）/ 财务管理（证书突出）
- 模板参考来源接口：清华学生职业发展指导中心简历指导 PDF + 国家大学生就业服务平台求职指导，附外链与 2026-10-13 查阅时间；仅借鉴通用结构与 STAR 原则转为原创模板，不复制任何真实简历
- `POST /resumes/{id}/optimize-for-job` 岗位适配诊断：STAR/CAR 结构建议、关键词缺口（缺什么学什么）、弱表达识别（缺具体证据处提问追问）、可补充证据方向；剔除模型编造的简历引用；全响应附「仅方法建议、不代写事实、AI 新增内容须用户确认」免责说明

**后端：合契真实岗位匹配（services/job_matching.py / routers/matching.py 扩展）**
- `POST /resumes/{id}/match-position/{position_id}`：命中技能逐项附「JD 原文依据 + 简历对应证据」双溯源；缺失技能附学习建议；`uncertain_items` 简历表述不清项；匹配分数附 `score_note` 全文说明「仅为文本与技能层内部指标，不代表获得面试或录用的概率」

**前端**
- 新建知潮页 `JobLibraryPage.tsx`（/job-library，侧栏「知行」组新增「知潮」条目）：真实性说明区、检索筛选（关键词/行业/企业/地点/经验阶段/收藏）、导入表单、列表（状态徽标/元信息行/过期提示）、详情卡（摘要/来源核验区带「查看企业原始岗位」外链/变更时间线/联动按钮：送知岗解析·生成问澜题集·加入合契匹配·收藏/匹配结果内嵌展示）、如实空状态
- JobsPage：新增「从岗位资料库选择」入口（选择后自动调库内解析注入现有详情链路）与「编辑解析」功能（四分组条目可改、evidence/is_inferred 只读、保存后徽标）
- MatchingPage：新增「用资料库岗位匹配」独立区块（岗位搜索选择器 + 简历下拉 + 双证据结果渲染）
- ResumePage：模板选择器下方展示参考来源小卡（外链 + 查阅日期）；新增「岗位适配诊断」面板（知岗历史/粘贴 JD 二选一，三板块结果 + amber 免责声明）

### 本阶段验证（全部实际运行）

| 项目 | 结果 |
| --- | --- |
| 后端 pytest 全量 | 313 passed（基线 276 + 新增 37 项知潮专项：种子真实性/发布时间诚实/unconfirmed/搜索过滤/空状态/收藏隔离/导入校验/SSRF 拒绝内网/链接核验不改招聘状态/stale 过期提示/库内解析复用 reused/证据核验/PATCH user_edited/模板来源/诊断缺口与伪造引用剔除/跨用户隔离/401） |
| 前端 lint / tsc / build | 全部通过（修复 4 处 react-hooks/set-state-in-effect 后清零；仅原有 chunk>500kB 警告） |
| 浏览器实测（内置浏览器） | 知潮页：8 条种子岗位渲染、每条「招聘状态未确认」徽标与来源/核验元信息、真实性说明区、关键词「AI」筛选 8→6 生效、详情卡摘要/原始岗位外链/联动按钮、导入表单出现；送知岗解析（真实火山方舟模型调用，后端日志 POST /job-library/8/analyze 201，真实模型 200）→ 生成解析记录 #2 → 再次点击提示条「已复用『Data Science Intern（IEG 数据科学实习）』的知岗解析（记录 #2）」；知岗页：资料库选择器、解析历史详情、编辑解析进入/取消正常；合契页：资料库匹配区块、真实岗位选项加载；履历成章页：参考来源小卡（清华 + ncss + 查阅日期）、岗位适配诊断面板展开正常；各页 console 无本站报错 |

### 未实现 / 下一阶段（如实记录）

- 自动定时抓取岗位：因来源站无授权批量抓取条款，未实现；维持「种子 + 手动导入 + 单条核验」三途径
- 导入表单的浏览器提交实操未执行（后端导入校验与 SSRF 防护已由 pytest 覆盖）；收藏、合契匹配、问澜出题按钮浏览器未实际点击（接口层已由 pytest 真实覆盖）
- 知岗「送知岗解析」在资料库详情卡内为原地完成设计（成功提示条位于页面顶部），不跳转知岗页
- 真实邮件投递验证延续待办（等待阿里云 DirectMail 凭证）

## 第十三阶段：知途·小鸥 AI 职业规划与长期记忆系统（已完成）

### 本阶段变更

**后端：持久化数据模型与迁移**
- `models.py` 新增 6 张表：`CareerProfile`（每用户唯一长期档案）、`CareerProfileFact`（事实三态：user_stated / ai_generalized / ai_inferred，含 quote 溯源、confidence、confirmed、source_message_id）、`CareerPlan` / `CareerPlanAction`（7d/30d/90d 阶段任务：goal/steps/due_at/status/review/related_goal）、`CareerPlanRevision`（每次变更版本快照）、`CareerWorkflowRun`（联动工作流逐步留痕）；`career_conversations` 增加 `summary` 与 `summarized_until_id`（SQLite 幂等 ALTER TABLE 迁移助手 `ensure_sqlite_columns`，启动时自动补列）

**后端：流式模型适配（统一服务层，前端不直连模型）**
- `ArkClient` 新增 `chat_stream()`：OpenAI 兼容 SSE 行解析、连接阶段可重试（尊重 Retry-After）、开始输出后失败即如实中断；`record_llm_call` 观测；`transport` 参数支持测试注入 MockTransport

**后端：分层长记忆服务（career_memory.py）**
- 受控上下文组装：已确认档案 → BM25 相关历史召回（其他会话，排除当前）→ 会话摘要 → 近 12 条消息 → 新消息
- 摘要触发：未摘要消息 ≥24 条才调用模型合并摘要（可溯源 summarized_until_id，不整段重总结）；模型失败如实跳过
- 事实三态抽取：user_stated 的 quote 必须是用户原话连续片段（归一化校验，伪造自动降级 ai_generalized + 待确认）；去重、每类上限、绝不把 AI 猜测自动变成事实

**后端：分析引擎（career_analyst.py）**
- 当前情况总结（含不确定点）、职业方向探索（2-4 方向 × fit 三态，不武断不下结论）、能力差距分析（真实结合知岗 JD / 履历成章简历 / 观己评分 / 度衡挑战 / 成长轨迹）、7/30/90 天计划生成（due_at 按阶段真实计算 + 首个 Revision 快照）

**后端：模块联动工作流（career_workflow.py）**
- `gap_analysis`：读档案 → 知岗解析 → 履历成章简历 → 知藏检索 → 汇总观己/度衡/成长轨迹 → AI 差距分析，每步实时写库留痕，缺数据如实 skip
- `interview_prep`：定位目标 → 知藏证据 → 真实调用 `interview_service.create_task` 创建问澜练习；失败写 run.error_message，绝不伪造成功

**后端：路由重写（routers/career.py，19 个端点）**
- SSE 流式：`POST /conversations/{id}/stream`、`/regenerate`（事件协议 meta → delta* → done → end；失败发 error 含 status/partial_saved；停止生成时已生成部分落库保留；失败重试自动复用同内容用户消息不重复入库；GeneratorExit 处理）
- 会话：搜索（标题+消息内容）、PATCH 改标题、删除；分析：situation / directions；档案：查看 / 手动补充 / 编辑 / 确认 / 删除 / 清空 / AI 整理；计划：列表 / 生成 / 详情 / 改标题归档 / 删除 / 任务增删改（完成、跳过、复盘、调整期限，均走版本快照）；工作流：创建 / 详情 / 列表；`GET /export` 导出全部个人数据
- 全部端点复用现有登录认证，按 user_id 严格隔离（越权一律 404）

**前端：知途页完整重构（CareerGuidePage + CareerAdvisorPanel）**
- 对话：新建会话 / 流式渲染 / 停止生成（AbortController，停止后部分保留并与服务端同步）/ 失败重试（复用服务端消息）/ 重新生成 / 复制 / Enter 发送 Shift+Enter 换行 / 回到底部按钮 / 搜索防抖 300ms / 行内重命名（Enter 保存 Esc 取消）/ 删除 / 移动端抽屉列表
- 首次欢迎语与 6 条快捷开场按产品文案原文呈现；用户消息靠右、AI 靠左
- 右栏三 Tab：**职业档案**（事实三态徽标 + 待确认项「确认无误」/编辑/删除、手动补充、AI 整理、清空记忆、导出数据、当前情况总结 / 职业方向探索按钮与结果展示）；**行动计划**（生成 7/30/90 天计划、按阶段分组、勾选完成/跳过/恢复、复盘编辑、改期、手动补任务、归档/删除、版本号）；**模块联动**（gap_analysis / interview_prep 一键运行、步骤状态时间线 ✓/—/×、差距结果与问澜任务直达链接、历史运行记录）

### 本阶段验证（全部实际运行）

| 项目 | 结果 |
| --- | --- |
| 后端 pytest 全量 | 276 passed（新增 test_career_memory.py 24 项：流式与持久化 / 未配置 503 阻塞 / 失败重试 / regenerate / 停止部分落库 / 三态抽取与伪造降级 / 档案确认编辑删除清空 / 档案隔离 / 摘要触发 / 召回与删除退出召回 / 工作流真实失败记录 / 计划生命周期与档案联动 / 数据隔离 / 导出与删除 / 搜索 / MockTransport 测真实 ArkClient.chat_stream 含重试与断流） |
| 后端 SSE 直测（真实模型 glm-5-2-260617） | meta→30 delta→done→end 全链路，真实 AI 回复落库、标题自动生成、model_name 记录 |
| 分析引擎直测（真实模型） | situation 返回 summary + known/uncertain/focus，如实标注未验证信息 |
| 前端 lint / tsc / build | 全部通过（仅原有 chunk>500kB 警告） |
| 浏览器实测（内置浏览器） | 欢迎语与 6 条快捷开场渲染；真实流式回复逐步出现；停止生成保留部分内容；重新生成替换旧回复；复制按钮；计划生成（真实 AI 输出「前端工程师转型产品经理秋招计划」+ 7 天分组任务）；档案/联动 Tab 正常；搜索过滤与重命名生效；663px 视口下汉堡菜单与抽屉正常（移动断点行为验证）；console 仅停止生成时预期的 ERR_ABORTED，无本站报错 |

### 未实现 / 下一阶段（如实记录）

- 「安排面试训练」工作流与「AI 整理档案 / 职业方向探索」的前端按钮已接通真实接口，但浏览器端未实际点击运行（对应后端链路已由 pytest 真实覆盖）
- 计划任务的「调整期限」浏览器实操未执行（接口层已由 pytest 覆盖）
- 移动端 375px 宽度的精确视口截图因内置浏览器无法强制 resize 未执行（663px 已落入移动断点，行为正确）
- 真实邮件投递验证延续待办（等待阿里云 DirectMail 凭证）

## 第十二阶段：拾阶下线 / 拖拽解析成章 / 问澜选项升级（已完成）

### 本阶段变更

**拾阶（/ladder）整体下线**（用户决定移除该功能）
- 后端：删除 `routers/ladder.py`、`schemas/ladder.py`、`services/ladder_service.py`、`models.LadderPlan/LadderStep`；`main.py` 移除路由注册；`prompt_registry` 移除 ladder 版本；`growth_stats.py` 与 `routers/stats.py` 移除 ladder 热力图/周报数据源与图例；`test_growth_features.py` 移除 5 项拾阶测试并清理失效 import；迁移文件 `f7a2c9d4e1b8` 同步移除 ladder 表创建（保留度衡/回澜）；本地开发库孤儿表已 DROP
- 前端：删除 `LadderPage.tsx`、App.tsx 路由、侧栏「拾阶」条目（Milestone 图标一并清理）、行舟页「另有渡口」拾阶链接、热力图 kind 标签、知途页右侧「成长规划」面板与 ladder API/类型；关于页过时文案修正
- 小鸥（知途）系统提示词中已删除「拾阶路线图」相关描述（保留仍在服务的功能引用）

**合契 + 履历成章：拖拽简历文件 → 自动解析（无需手动输入任何内容，含标题）**
- 新增后端 `POST /api/v1/resumes/parse`（需登录，multipart file + 可选 jd_text）：复用 knowledge_service 的安全文本提取（txt/md/docx/pdf，仅提取不执行），AI（service=resume_parse，v1.0）把简历原文忠实转录为结构化内容 + 自动生成标题 + 自动识别目标岗位；防编造硬校验与润色同源——结构化结果中的数字必须都能在原文找到，连续 3 次不过即拒绝；AI 不可用/失败时如实降级（text 照常返回，title/position/content 为空并附 parse_error），不落库、不伪造
- `_coerce_ai_content` 温和矫正模型常见类型偏差（links 数组→字符串、highlights 字符串→数组），真实模型冒烟已验证该矫正必要且有效
- 合契页（MatchingPage）：删除「目标岗位」输入框与「简历内容」文本域，改为大拖拽区（PDF/DOCX/TXT/MD）；文件落选即自动解析并显示已识别岗位；JD 选填——拖拽时没填 JD 会在提交前带 JD 自动补一次解析；未识别出岗位时如实提示
- 履历成章页（ResumePage）：删除「新建简历」按钮与手动标题表单，改为常驻拖拽解析区——文件落选即 AI 解析 → 自动创建简历（标题取 AI 生成或文件名）→ 自动打开编辑器供核对保存；空态与引导文案同步更新

**问澜选项区视觉升级**
- `RadioCardGroup`（ui/Field.tsx，问澜与度衡共用）：分组标题加品牌渐变竖条眉标；选项卡升级为圆角 xl 卡片，选中态浅蓝渐变底 + 柔和投影 + 右上角蓝色圆形对勾指示器，未选中态 hover 微上移 + 边框渐蓝；题目侧重胶囊选中态加对勾图标与浅蓝渐变

### 本阶段验证（全部实际运行）

| 项目 | 结果 |
| --- | --- |
| 后端 pytest 全量 | 252 passed（移除 5 项拾阶测试，新增 7 项解析回归：登录校验/txt 结构化解析/类型拒绝/空文本/捏造数字拒绝重试/反复失败如实降级/未配置 AI 降级） |
| 前端 lint / tsc / build | 全部通过（仅原有 chunk>500kB 警告） |
| 解析端到端（真实模型） | POST /resumes/parse 上传 txt 简历 → 真实 AI 返回 title「林澜 · 前端工程师」+ position「前端工程师」+ 完整结构化 content，parse_error=null；首测暴露 links 数组类型偏差，经提示词明确 + 温和矫正后通过 |
| 浏览器实测（内置浏览器） | /app 侧栏无拾阶；/resume 拖拽区在、无新建按钮；/matching 拖拽区在、无岗位/简历手输框、未解析时开始匹配禁用；/interview/new 选项卡新样式与选中切换正常；各页 console 无本站报错 |
| 孤儿数据清理 | 本地库 ladder_plans / ladder_steps 已 DROP，全库源码无 ladder/拾阶残留（grep 验证） |

### 未实现 / 下一阶段（如实记录）

- 知途页右侧面板的浏览器复核因视口 616px < xl 断点无法展开（响应式按设计隐藏）；已由源码检查确认仅剩「职业档案/目标岗位」两节
- 合契/履历成章的拖拽全流程浏览器实操（模拟文件拖放）未执行，接口层已用真实模型端到端覆盖
- 跨会话长期对话记忆、真实邮件投递验证（延续第十一阶段待办）

## 第十一阶段：小鸥吉祥物 + 知途（AI 职业顾问）（已完成）

### 本阶段变更

- 品牌吉祥物（原创矢量，无 Emoji / 远程图片）：
  - `frontend/public/images/aurel-logo-mark.svg`：品牌方印升级为「海鸥掠过日出海平线」（海鸥 + 日光 + 三层微澜），`frontend/public/favicon.svg` 同步更新
  - `frontend/public/images/aurel-gull-mascot.svg`：AI 顾问「小鸥」吉祥物（圆润头身、舒展双翼、脚下静水微澜，清亮蓝/淡天蓝/白）
  - `frontend/src/components/BrandMark.tsx`：品牌图形 + 文字组合实现；`LogoMark.tsx` 保留原导入路径做薄转发，全站首页/侧栏 Logo 自动统一为海鸥体系
  - `frontend/src/components/GullMascot.tsx`：头像组件，idle/thinking（呼吸+涟漪）/speaking（翼尖起伏）/error 四态，motion 实现，尊重 prefers-reduced-motion
- 知途（AI 职业顾问「小鸥」，`/career-guide`，需登录）：
  - 后端：`career_conversations` / `career_messages` 模型（create_all 幂等建表）、`/api/v1/career-guide` 路由（会话增删查 + 发消息）、小鸥人设提示词注册 `career_guide v1.0`、复用 ArkClient（chat 文本通道）与 map_ark_error；AI 失败时整对消息不落库并如实报错
  - 前端：`CareerGuidePage` 三栏布局（左：旅程手记历史+新对话；中：自然消息流，用户靠右浅蓝气泡、小鸥靠左带头像，不逐条装卡；右：可折叠职业档案/成长规划/目标岗位，全部读取真实接口、空态如实引导）；窄屏响应式（<md 单列 + 页头新对话入口）；进入自动回到最近对话
  - 导航：顶部导航统一为 观澜之意 / 行舟 / 知途 / 澜讯 / 引航；侧栏「启程」组新增 知途（Bird 图标）
- 本阶段不含跨会话长期对话记忆（下一阶段接入）

### 本阶段验证（全部实际运行）

| 项目 | 结果 |
| --- | --- |
| 后端 pytest 全量 | 249 passed（含知途 6 项新回归：会话列表/消息落库+自动标题/空白拒绝/用户隔离/删除/未配置 AI 不落库） |
| 前端 lint / tsc / build | 全部通过（仅原有 chunk>500kB 警告） |
| 知途 API 端到端（真实模型） | 创建会话 → 发消息 → 真实 AI 回复（小鸥人设生效）→ 首条消息自动成为标题 → 列表计数/排序正确 |
| 浏览器验证 | 知途页消息流（用户靠右/小鸥靠左带头像）、空会话状态、话题填入、新对话、首页导航五项、方印海鸥 Logo、SVG 文件访问：全部通过 |
| console | 无本站报错（唯一 TypeError 来自浏览器扩展 content-script，与本站无关） |

### 未实现 / 下一阶段

- 跨会话长期对话记忆；知途回答结合用户能力快照的深度个性化（当前提示词仅给通用指引）
- 真实邮件投递验证仍等待 QQ_SMTP 凭证（延续第十阶段）

## 第十阶段：Editorial 编辑式改版 + 两大创新功能（已完成）

### 新功能（含金量项）

**星图对照 —— 观己 × 知岗差距分析（观己页新区块）**
- 后端 `POST /api/v1/skills/gap-analysis`：将观己能力快照（四维均分）与知岗解析（capability_dimensions）交给 AI，输出 3-8 维「现值 vs 岗位目标」差距分析；维度名必须逐字复用候选清单，`current` 一律由服务端从真实报告回填（无数据如实记 0），不采信模型给的现值；AI 输出经 `GapAnalysisAiPlan` Pydantic 结构化校验，不合格返回 502
- 前端 `components/SkillRadar.tsx`：纯 SVG 双雷达对比图（current 实线填充 / target 虚线，四圈网格），无第三方依赖；观己页选择知岗解析后一键生成，含差距点评与总评引用

**澜记周报 —— 近 7 日真实活动聚合 + AI 短评（行舟页「本周澜记」区块）**
- 后端 `GET /api/v1/stats/weekly`：聚合近 7 天问澜/度衡/听澜/回澜/拾阶真实行为（逐日活动、分类合计、周内均分、活跃日、全年口径连续天数）；AI 短评（service=weekly_note）失败或未配置时如实降级为 `ai_note=null`，绝不伪造
- 前端：行舟页「澜迹」下方引用式排版展示；真实环境已验证 AI 短评生成（如「本周练习如静水微澜…」）

### Editorial 编辑式全站改版（主页除外）

- **新增编辑式原语** `components/editorial/Editorial.tsx`：PageHeading（眉题+大标题+副题+动作）、SectionHead（章节标题+渐隐细线）、EntryRow（细线分隔条目行）、StatStrip（无边框统计带）、TimelineList/TimelineRow（纵向时间线）、QuietLink（安静下划线链接）
- **左侧导航重做**：浅蓝白渐变底、分组眉题细线（启程/洞察/知行）、无框导航行 + 选中左侧细指示线（motion layoutId 平滑移动）、hover 仅变色；回响/回澜作为已实现功能如实列入洞察组
- **行舟工作台重写**：开放式四层结构 —— ①大标题「行舟」（眉题「观澜 · 见微知远」，无「工作区」字样）②问澜为唯一浅蓝渐变背景区 + 右侧「行囊」（知岗/履历成章/合契/知藏细线条目）+「另有渡口」安静链接 ③「航程」时间线 +「最近回响」行列表 ④「澜迹」统计带+热力图+「本周澜记」；所有文案寓意化（行囊/渡口/航程/回响/澜迹/澜记）
- **其余页面全部去卡片化**（问澜/观己/回响/报告详情/拾阶/度衡/回澜/知岗/履历成章/合契/知藏/听澜/协奏/名笺）：页首统一 PageHeading、列表改细线行或时间线、统计改 StatStrip 直接融入页面；仅表单/作答区等确需边界处保留轻面板；度衡限时作答区为该页唯一浅蓝强调区；合契结果两栏对照（匹配项浅蓝强调）；协奏三席位细线分栏
- 主区宽度放宽至 max-w-7xl，保留流动云团背景、鼠标光晕、纤细滚动条与 prefers-reduced-motion 支持（既有基础设施，未重复实现）

### 修复

- 履历成章页（ResumePage）JSX 结构损坏（被中断的改造遗留）：补 section/div 闭合、清理孤儿闭标签、删除无用版本管理函数与状态（保留 viewingVersion 预览与保存成功提示）、恢复 Card 组件导入
- stats.py 中间态占位实现重写为最终版

### 本阶段验证（全部实际运行）

- 后端全量 pytest：**243 passed**（新增 4 项：星图对照现值回填/隔离/坏结构 502、周报聚合/AI 降级不真调外部 API）
- 前端 ESLint 0 error、`tsc --noEmit` 通过、生产构建通过（仅原有 chunk 体积警告）
- 接口实测：`GET /api/v1/stats/weekly` 200（days=7、totals 真实、AI 短评真实生成）；Vite 代理链路 200
- 浏览器实测（内置浏览器，桌面）：/app 行舟四层结构、行囊/渡口/航程/回响/澜迹/本周澜记全部渲染正常且无「工作区」字样；/skills 星图对照区块与空状态正常；/resume 修复后正常渲染；/ladder、/jobs、/concerto 编辑式布局生效；全部无 console error（仅后端重启窗口期出现过一次 ERR_ABORTED 瞬态，复测正常）

### 尚未验证 / 待办（如实记录）

- 星图对照的**真实 AI 端到端生成**（需先在知岗创建解析）与问澜/度衡等页面的深度交互未逐一走查
- 375px 手机端真机/设备仿真仍未执行
- **真实邮件投递仍未验证**：需用户在 `.env` 填入 `QQ_SMTP_USER` 与 `QQ_SMTP_AUTH_CODE`；阿里云 DirectMail 凭证未配置（可选备用）

## 第九阶段：五大成长功能（拾阶 · 回澜 · 度衡 · 协奏 · 成长轨迹）（已完成）

### 本阶段变更

**拾阶 — AI 个性化进阶路线图（`/ladder`）**
- 后端新增 `models.LadderPlan/LadderStep`、`services/ladder_service.py`、`routers/ladder.py`：基于观己能力快照 + 目标岗位 / 三档水平（入门起步 / 稳步进阶 / 冲刺精通）生成 2-5 阶段、4-24 步的路线图，AI 输出经 Pydantic（`LadderAiPlan`）结构化校验，步骤可逐项勾选（`PATCH /steps/{id}?done=`），全部按登录用户隔离
- 前端新建 `LadderPage.tsx`：创建表单 + 计划列表卡（进度条）+ 按阶段分组展开的里程碑勾选
- 修复：`LadderPlanSummary.progress` computed_field 访问未声明 `steps` 导致列表端点 500（已声明字段并新增回归测试 `test_ladder_plan_list_serializes_progress`）

**回澜 — 错题本 + SM-2 间隔重复（`/mistakes`）**
- 后端新增 `models.MistakeCard`、`services/mistake_service.py`（含标准 SM-2 调度：q≥3 间隔 1→6→×EF，遗忘重置，EF 下限 1.3）、`routers/mistakes.py`：从问澜报告一键收题（自动回填当时回答与考察意图，409 防重复），`GET /mistakes` 由服务端计算 `is_due`
- 前端新建 `MistakesPage.tsx`：三统计卡（收进 / 今日待复习 / 已掌握）+ 卡片展开详情 + 四档自评复习 + 「下一回在 X 天后再遇见它」反馈

**度衡 — 限时模拟挑战（`/challenges`）**
- 后端新增 `models.ChallengeRun`、`services/challenge_service.py`、`routers/challenges.py`：AI 出题 → 服务端时钟计时（防客户端篡改，超时提交标记 overtime）→ 四维度评分（总分=维度均分，不采信模型给的 overall）
- 前端新建 `ChallengesPage.tsx`：创建表单（岗位 / 难度 / 3-8 题 / 5-30 分钟）+ 本地倒计时（初始值取服务端 remaining_seconds，剩 60 秒变红）+ 到时自动交卷 + 结果页（总分 / 维度条 / 改进建议）+ 历史记录

**协奏 — 三角色并行协作台（`/concerto`）**
- 前端新建 `ConcertoPage.tsx`：复用听澜 SSE 流（`analyzeExpressionStream`），结构分析师 / 深度分析师 / 表达教练三席位实时渲染 pending→running→done 状态，完成后三列并观展示各自评分与问题清单；独立实现席位渲染，不依赖听澜页内部组件

**成长轨迹 — 热力图 + 连续打卡（`/app` 工作台）**
- 后端新增 `services/growth_stats.py`、`routers/stats.py`：聚合当年全部真实活动（问澜 / 知藏 / 度衡 / 拾阶勾选），输出 365 天 `days[{date,count,kinds}]` + `streak{current,longest}`（仅真实数据，无任何伪造）
- 前端 `DashboardPage.tsx` 新增「成长轨迹」GitHub 风格五档热力图（53 周网格 + 图例 + 连续 / 最长天数）；功能卡扩至 7 张（拾阶 / 度衡 / 回澜 / 协奏全部亮起，无「即将上线」残留）

**其他**
- `SidebarNav.tsx`：洞察组 5 项（观己 / 回响 / 拾阶 / 度衡 / 回澜）、知行组协奏启用；`App.tsx` 新增 4 条受保护路由
- `ReportDetailPage.tsx`：问答回顾每题新增「收进错题本」按钮
- 邮件服务（上一轮完成）：默认 `MAIL_PROVIDER=smtp_qq`（用户自有 QQ 邮箱），验证邮件为寓意文化风格文案（「观水有术，必观其澜」）

### 本阶段验证

- 后端全量 pytest：**239 passed**（新增 6 项：拾阶生成/勾选/隔离/AI结构拒绝/列表回归、回澜 SM-2 数值演进、度衡全流程/超时/防重复提交、热力图真实计数）
- 前端 ESLint 0 error；`tsc --noEmit` 通过；生产构建通过
- 真实 AI 端到端冒烟：`POST /api/v1/ladder/plans`（产品经理 / 稳步进阶）真实生成 7 步路线图（model=glm-5-2-260617，首步「构建用户故事与场景拆解」）
- 接口验证：拾阶列表 200（修复后）、勾选里程碑 → 热力图当日 `kinds:["ladder"]` + `streak.current=1` 全链路通过
- 浏览器实测：/ladder 卡片进度 14%「1 / 7 个里程碑已完成」、步骤勾选状态正确；/app 成长轨迹热力图网格与「连续 1 天 · 最长 1 天」正常；/mistakes /challenges /concerto 页面与空状态正常；无 console error

### 尚未验证 / 待办（如实记录）

- **真实邮件投递仍未验证**：需用户在 `.env` 填入 `QQ_SMTP_USER`（QQ 邮箱地址）与 `QQ_SMTP_AUTH_CODE`（QQ 邮箱设置→账户→开启 SMTP 服务获取的授权码）；阿里云 DirectMail 凭证亦未配置（可选备用）
- 度衡 / 协奏 / 回澜的**真实 AI 端到端**仅冒烟验证了拾阶出图；其余功能链路由 Fake 注入测试覆盖
- 375px 手机端真机 / 设备仿真仍未执行（内置浏览器代理视口限制）

## 第八阶段：引航对话框精致化 / 认证页品牌化 / 首页动效增强（已完成）

### 本阶段变更

**引航（新手引导）精致化**
- `OnboardingGuide.tsx` 重做为双栏品牌化对话框：左栏深蓝渐变品牌面板（Logo + 五步目录，当前步高亮），右栏白色内容区（顶部细进度条、图标章、大数字水印、步骤横移切换动画）
- 每一步对应一个真实栏目并展示该页面的**真实界面截图**（`frontend/public/onboarding/` 下 5 张，来自实际运行页面：首页 / 行舟 / 问澜 / 观己 / 名笺），并显示「对应栏目」胶囊标签；步骤 4、5 更名为「观己与回响」「名笺与澜讯」以与侧栏栏目一致
- 遮罩由 30% 加深至 60% 深蓝并加轻微背景模糊，对话框改为纯白底，解决「背景太透看不清字」的问题；对话框增加高度约束（max-h + 内容区可滚动），小屏不溢出

**认证页品牌化**
- `AuthPage.tsx` 重做为双栏卡片：左栏深蓝品牌面板（Logo + 双语座右铭 + 三条特性文案，窄屏隐藏），右栏表单（图标输入框、渐变按钮）；全部认证逻辑、验证码安全规则与 503 未配置提示逐字保留，未动任何邮件 / 会话逻辑

**首页动效调整**
- 按用户要求**删除首页海面三层 SVG 波纹线**（`HomePage.tsx` 波纹层 + `index.css` 全部 ripple 样式与关键帧一并移除），海景仅保留图片缓慢漂移、太阳倒影光纹与水光
- 文字渐变增强：标题 / 中文座右铭渐变 background-size 300%、周期 6.5s、颜色更饱和；英文座右铭颜色加深（#a9d0f7）
- 海面浮动增强：海景漂移幅度 ±1.8% + scale 1.03、倒影光纹透明度提高、内部页云团漂移幅度加大（14-20% 位移）

### 本阶段验证

- 后端全量 pytest：228 passed（本轮无后端代码改动，回归确认无破坏）
- 前端 ESLint：0 error 0 warning；`tsc -b` 通过；生产构建通过（chunk 体积提示为既有现象）
- 浏览器实测：首页无波浪线残留、文字渐变与海面浮动可感知；引航对话框遮罩明显加深、每步真实截图与栏目标签显示正常（无破图）、步进 / 目录高亮 / 进度条正常；/auth 双栏卡片正常且无指定禁句；/about 云团背景正常；无 JS console 错误
- 截图辅助登录说明：为截取受保护页面，曾临时以**环境变量**（`MAIL_PROVIDER=mock` + `AUREL_MOCK_MAIL_CONFIRM=1`，未改 `.env`，仅限本地开发）启动开发模拟邮件通道注册 `guide_shots@qq.com`，截图完成后已恢复正式配置后端；该账号仅存于本地 SQLite，不入 Git

### 尚未验证 / 待办（如实记录）

- **375px 手机端真机 / 设备仿真仍未执行**（内置浏览器代理视口约 663-968px 无法下调；663px 窄视口布局正常）
- **真实邮件投递仍未验证**（阿里云 DirectMail 凭证未配置，属既有待办）
- 引导内截图为当前页面快照，后续页面大改版时需重新截取替换 `frontend/public/onboarding/*.png`

## 第七阶段：品牌视觉升级 / 海面动态 / 新 Logo / 引航教程（已完成）

### 本阶段变更

**品牌与设计令牌**
- 新建 `frontend/src/components/LogoMark.tsx`：原创矢量标志（圆角方印 + 日出海平线：远方日光点 + 三层白色微澜，蓝渐变底白负空间），`LogoMark`（图标版）+ `LogoLockup`（横向品牌版）两个变体，全站唯一定义；删除旧 `BrandMark.tsx`，首页 / 侧边栏 / 登录页 / 认证页 / 面试预览 / 面试进行 / 404 页全部换用新组件
- `frontend/public/favicon.svg` 同步重绘为新标志
- `index.css` 补充规范命名令牌别名（`--aurel-blue-pale/-light/-mid`、`--aurel-blue`、`--aurel-blue-dark`、`--aurel-text`、`--aurel-text-muted`、`--aurel-border`，与既有令牌一一对应）

**首页（海景 Hero）**
- 文字动效：主标题约 850ms 模糊聚焦入场；中文座右铭延迟 320ms 淡入；英文座右铭（更小）延迟 600ms 淡入；标题与中文座右铭以 `background-clip: text` 做「白 → 淡冰蓝 → 天蓝 → 白」8s 循环渐变（错相），英文做 9s 白→淡冰蓝颜色缓变；全部配极轻深蓝投影保证海景上可读，含 `@supports` 兜底
- 海面分层动态（均为 `pointer-events: none` 的独立背景层）：图片层 64s 漂移 + 1.8% 微缩放；`.hero-ripples` 三层 SVG 波纹贴合原图海面（底部 46%，顶缘遮罩渐隐）——细波光 26s 向左、中水纹 19s 向右、长涌 34s 向左带透明度呼吸；太阳倒影区低透明度光纹 16s 缓慢蠕动（radial 遮罩限定右侧，非光柱）；保留原有斜向水光带
- 移动端隐藏第三层波纹、降低倒影透明度；`prefers-reduced-motion` 下所有海面 / 文字动画冻结为静态
- 顶部导航固定四项：观澜之意 / 行舟 / 澜讯 / 引航

**引航（首次访问引导）**
- 新建 `components/onboarding/`（`OnboardingGuide.tsx` 引导界面、`onboarding-context.ts` 上下文与本地标记、`use-onboarding-autostart.ts` 自动启动）
- 五步文案与真实功能一一对应（初识观澜 / 循径行舟 / 开启问澜 / 观己拾阶 / 留下名笺）；含步骤进度点、上一步 / 下一步 / 跳过 / 完成引航、ESC 与点击遮罩关闭；遮罩为柔和半透明深蓝（非黑幕）
- 首次进入行舟（/app）自动开启一次；完成或跳过写 `localStorage.aurel_onboarding_done`，刷新不再弹出；顶部「引航」随时可重新打开并从第 1 步开始

**文案**
- 全局删除「观澜只需 QQ 邮箱验证码即可登门，全程不会索要你的 QQ 密码或邮箱密码。」（认证页不再显示该句；真实错误提示、邮件未配置 503 状态与验证码安全逻辑全部保留未动）

### 本阶段验证

- 后端全量 pytest：228 passed
- 前端 ESLint：0 error 0 warning；`tsc -b` 通过；生产构建通过（chunk 体积提示为既有现象）
- 浏览器验收（dev server 实测）：首页四项导航顺序正确；新 Logo 生效；三层波纹动画名 / 周期（26s/19s/34s）与倒影光纹（glare-creep）实测正确；海景图 200；引航完整流程（步进 / 跳过 / 完成后标记 / 重开从第 1 步）通过；行舟首进自动弹出且刷新不再弹；/auth 已无禁句且表单完整；工作台各页云团背景正常；无 JS console 错误
- 未验证项：375px 手机端设备仿真（浏览器代理视口固定 663px 无法下调，与上一轮一致）；真实邮件投递仍未验证（依赖阿里云 DirectMail 凭证，属既有待办）

## 第六阶段：邮箱认证 / 知岗 / 履历成章 / 全站视觉（已完成，含集成验收）

### 本阶段新增功能

**邮箱验证码认证（可插拔邮件提供方）**
- `services/email_service.py`：`EmailProvider` 抽象层 + `AlibabaDirectMailProvider`（默认，调用阿里云 DirectMail 官方 SingleSendMail 接口）+ `SmtpQqProvider`（可选备用，SSL 465）+ `MockEmailProvider`（仅自动测试）；`MAIL_PROVIDER` 配置选择，业务层不依赖具体服务商
- 验证码：`secrets` 六位数字、5 分钟有效期、60 秒重发冷却、最多 5 次错误尝试、注册 / 登录用途隔离、一次性使用、服务端限流；库内仅存 HMAC-SHA256 摘要（密钥 `AUREL_SECRET_KEY`）
- 投递语义：真实投递成功才落库与返回 sent；未配置 503（`email-status` 精确列出缺失变量名，不含凭证值）、服务商拒绝 502；不允许未投递的验证码完成注册
- 会话：高熵不透明令牌 + HttpOnly + SameSite=Lax Cookie（生产 `AUREL_COOKIE_SECURE=true` 加 Secure），库内只存 SHA-256 摘要，登出真实撤销
- 邮件文案：主题「观澜 AUREL｜开启新程前，请确认身份」，正文含座右铭「见微知远，向新而行」，主题不含验证码明文

**知岗（JD 解析）与联动**
- `services/jd_analysis.py`：火山方舟模型 + Pydantic 结构化校验（岗位 / 行业 / 职责 / 技能 / 经验 / 学历 / 工具 / 能力维度 / 面试方向 / 关键词），服务端逐条核验 evidence 是否可在 JD 原文定位，定位不到降级 `is_inferred=true`；未提及字段一律「未明确说明」；注入防护（JD 视为数据）；文件上传安全提取（txt/md/docx/pdf）
- 同一 JD 重复解析版本递增、历史可回看；`POST /jobs/analyses/{id}/interview-task` 复用现有问澜 `create_task` 流程；`POST /jobs/analyses/{id}/match` 与简历内容匹配（词典 + BM25，结论附证据）

**履历成章（简历系统）**
- 七节结构化编辑（基本资料 / 教育 / 工作实习 / 项目 / 技能 / 证书语言 / 奖项其他）、七款模板（clean / campus / tech / product / design / research / finance，章节顺序 + 主题色差异，后端统一下发）
- 版本管理：保存即快照、不可变历史、恢复生成新版本、复制版本
- AI 润色确认制：仅生成建议文本，用户确认后才写入；服务端硬校验禁止建议中新增公司名 / 学历 / 奖项 / 编造数字
- 真实导出：reportlab PDF + python-docx DOCX，中文字体内嵌，导出与预览同源渲染

**全站观澜视觉**
- 首页：真实海景背景 + 白色标题入场 + 座右铭延迟淡入 + 三栏目导航
- 内部页：AmbientBackground 流动云团（20-40s 周期、多云团不同步、pointer-events:none）、桌面鼠标跟随光晕、纤细云水蓝滚动条、侧栏「启程 / 洞察 / 知行」分组（拾阶 / 度衡 / 协奏如实标注「即将上线」）
- `prefers-reduced-motion` 全局生效（CSS 媒体查询 + MotionConfig reducedMotion="user"）

### 集成验收结果（2026-10-13 实际执行）

| 检查项 | 方式 | 结果 |
| --- | --- | --- |
| 后端全量测试 | `python -m pytest`（backend/） | **228 passed**（原 183 + 知岗 / 履历成章 / 邮件提供方新增 45；无删减） |
| 前端 lint / tsc / 生产构建 | `npm run lint` / `npm run build` | 0 错误；构建成功（仅 chunk 体积提示） |
| 首页视觉 | 浏览器实际操作 | 海景照片背景、观澜 AUREL 标题、座右铭「见微知远，向新而行」、仅三栏目、标题座右铭平滑淡入、无技术化状态提示，全部通过 |
| 观澜之意页 | 浏览器实际操作 | 编辑感排版（主标题 + 理念 + 连贯正文 + 留白），无功能卡片墙，云团背景，通过 |
| 工作台 | 浏览器实际操作 | 侧栏「启程 / 洞察 / 知行」分组与「即将上线」标注（抽屉与桌面态）、蓝白层次、云团背景、无技术化状态提示，通过 |
| 知岗 / 履历成章 / 问澜页面 | 浏览器实际操作 | 知岗 JD 输入与解析入口、问澜「行业门类 + 职业方向」选择器、履历成章新建 / 模板选择对话框，均蓝白风格正常渲染 |
| 邮件状态如实报告 | `GET /api/v1/auth/email-status` | `provider=aliyun_directmail, configured=false, missing=[ALIBABA_CLOUD_ACCESS_KEY_ID, ALIBABA_CLOUD_ACCESS_KEY_SECRET, DIRECTMAIL_SENDER_ADDRESS]`，未伪造成功 |
| **知岗真实解析（真模型端到端）** | 真实调用 glm-5-2-260617（HTTP 201，46.9s） | 5 条职责全部证据核验通过（非推断）、4 必需技能 + 3 加分 + 5 工具、学历 / 经验正确提取；JD 未写明岗位名与行业 → 如实标「未明确说明」 |
| **简历真实导出（端到端）** | API 创建简历 → 导出 | PDF 33KB（%PDF 魔数）与 DOCX 37KB（PK 魔数）；PDF 文本抽取验证中文字（张三 / 前端工程师 / 计算机科学）渲染正常 |
| 认证与数据权限 | curl（修复 PowerShell Cookie 头 quirk 后复测） | 会话 Cookie 认证正常；未登录访问受保护接口 401；未注册邮箱登录 404；写方法 Origin 校验与限流中间件在位 |
| 代码级安全检查 | 静态检查 | `.gitignore` 含 `.env`/`.env.*`（保留 `.env.example`）；前端源码无 `import.meta.env.VITE_*` 用法（无秘密进前端包）；CORS 默认仅 localhost 来源；Cookie HttpOnly + SameSite=Lax + 可配置 Secure |
| 移动端布局 | 663px 窄视口 | 侧栏收纳为汉堡抽屉、抽屉内分组完整、无横向溢出；**375px 真机 / 设备仿真未执行**（验收工具无法调整视口） |

### 尚未验证 / 待办（如实记录）

- **真实邮件投递未验证**：阿里云 DirectMail 三项凭证（AccessKey ID / Secret / 发信地址）未配置，`email-status` 如实报告缺失；人工验证脚本 `backend/scripts/send_test_email.py` 备好，配置后即可执行
- **面试题生成真模型端到端未在本轮执行**：问澜生成与评分走同一已实测的 ArkClient（知岗解析本轮已真实验证该链路），生成 / 评分逻辑由 228 项测试中的 mock 回归覆盖
- **375px 手机真机验证未执行**（663px 窄视口正常）
- 本地开发库中留有验收用账号 `acceptance@aurel.local`（会话令牌仅存于本地 DB，不入 Git）

### 线上部署所需配置（README 已含操作说明）

- `ARK_API_KEY` / `ARK_MODEL`（模型能力，必配）
- `MAIL_PROVIDER=aliyun_directmail` + `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` / `DIRECTMAIL_SENDER_ADDRESS`（邮件，注册登录必需）
- `AUREL_SECRET_KEY`（会话与验证码 HMAC 密钥）、`AUREL_COOKIE_SECURE=true`、`AUREL_CORS_ORIGINS`（生产域名）、可选 `AUREL_ACCESS_TOKEN`（运维通道）

---

## 第五阶段：质量评测 / 密钥与数据控制 / 稳定性 / 调用观测 / 部署（已完成）

### T4 — 固定测试集与质量评测

- `backend/eval/evalset.json`（aurel-evalset-v1）：5 个评分用例（人工锚点分 + must_cover 关键概念，覆盖事件循环 / 空泛回答识别 / 高并发短链 / 数据口径 / flex 基础）+ 2 个出题用例（数量与长度约束）
- `backend/eval/run_eval.py`：对固定用例发起**真实模型调用**，指标包括——解析成功率、证据完整率、维度覆盖、分数偏差（对比人工锚点）、关键概念覆盖率、出题数量准确率、延迟（平均 / P95）；报告写入 `eval/reports/`（已 gitignore），记录所用模型与全部提示词版本，可跨版本横向对比

### T7 — 密钥保护与数据控制

- **访问控制**：`middleware.AccessControlMiddleware`——设置 `AUREL_ACCESS_TOKEN` 后所有 `/api/v1` 请求强制 `Authorization: Bearer <令牌>`（401 JSON）；健康检查 / AI 状态 / 表达状态三个探测端点豁免；OPTIONS 预检放行；默认不设置保持本地开放模式
- **限流**：`RateLimitMiddleware`——每客户端 IP 每分钟滑动窗口（默认 120，0 关闭），超限 429 + `Retry-After`；`X-Forwarded-For` 首值识别真实 IP
- **日志脱敏**：`logging_setup.SecretRedactionFilter` 自动遮蔽日志中的 `Bearer xxx` / `api_key=xxx` / `token=xxx`
- **数据库安全**：SQLite 连接事件监听自动启用 `foreign_keys=ON` / `WAL` / `synchronous=NORMAL` / `busy_timeout=5000`
- **数据隐私**：`GET /api/v1/privacy` 返回数据留存声明（音频仅内存处理不落盘、密钥仅服务端环境变量、数据库存储范围与删除入口）
- 中间件顺序（Starlette 后添加在外层）：CORS → 限流 → 访问控制

### T8 — 超时 / 限流 / 重试 / SSE 稳定性

- **Ark 客户端**：连接超时 10s、总超时 120s；自动重试 2 次（429/500/502/503/504），尊重响应 `Retry-After`（上限 5s），否则 0.5s 指数退避；每次尝试与最终结果均记入观测
- **SSE 流式复盘**：`POST /api/v1/expression/analyze/stream` 以 `text/event-stream` 逐步推送 `step_started` / `step_finished` / `result` 事件（异常时推送 `error`）；响应头 `Cache-Control: no-cache` + `X-Accel-Buffering: no`
- **前端进度**：表达分析页流式消费 SSE（fetch + ReadableStream），三位分析师实时显示「阅读中…」进度状态；流式不可用时自动回退普通接口
- **就绪检查**：`GET /api/v1/health/ready` 含数据库连通性探测，失败返回 503（供容器编排探针）

### T10 — 模型与提示词版本实验、调用观测

- **观测入库**：`llm_call_records` 表（服务 / 模型 / 提示词版本 / 状态 / 尝试次数 / 延迟 / 实验标记 / 错误类型与信息 / token 用量 JSON），迁移 `a8d1f2c3e4b7` 已执行；所有 Ark 调用（评分 / 出题 / 追问 / 匹配建议 / 复盘工作流）在 finally 中自动记录，观测写入失败只告警不影响主流程
- **观测 API**：`GET /api/v1/observability/llm-calls`（最近 200 条）、`GET /llm-stats`（按服务 / 按模型聚合成功率与延迟）、`GET /prompt-versions`
- **提示词版本注册表**：`services/prompt_registry.py`——五个服务统一登记 `v1.0` 与变更记录，评测报告与观测记录均携带版本号
- **实验分流**：设置 `LLM_EXPERIMENT_MODEL` + `LLM_EXPERIMENT_PERCENT`（0-100）后按概率将调用路由到候选模型，实验标记随观测入库，可在 `llm-stats` 中对比两组质量与延迟

### 部署与配置

- `Dockerfile.backend`（python:3.13-slim，启动前自动 `alembic upgrade head`）、`Dockerfile.frontend`（node:24 构建 → nginx 托管）、`deploy/nginx.conf`（/api 反代 + SSE 关闭缓冲 + SPA 路由）、`docker-compose.yml`（数据卷持久化数据库与 Whisper 模型缓存，前端 8080 端口）
- `.env.example` 补充全部第五阶段变量说明；`.gitignore` 排除数据库文件与评测报告

### 真实测试结果（均已实际执行）

| 检查项 | 命令 / 方式 | 结果 |
| --- | --- | --- |
| 后端全量测试 | `python -m pytest`（backend/） | **124 passed**（原 95 + 新增 29：访问控制 / 限流 / 脱敏 / 重试与超时 / SSE / 观测 / 评测脚本单元） |
| 真实质量评测 | `python -m eval.run_eval`（glm-5-2-260617） | 评分 5/5 解析成功：平均分数偏差 **0.88**，证据覆盖 **100%**，关键概念覆盖 **100%**，P95 延迟 49.9s；出题 2/2 数量准确率 **100%** |
| SSE 真实冒烟 | `/expression/analyze/stream`（真实模型） | 事件序 `step_started → step_finished ×3 → result`，三角色全 completed（16.4s / 24.5s / 39.3s），复盘记录入库 |
| 观测实证 | `GET /observability/llm-stats` | expression_workflow 6 次 / scoring 5 次 / question_generator 2 次调用，0 错误，全部真实记录 |
| 就绪与隐私 | `GET /health/ready` / `GET /privacy` | 200；数据库探测与隐私声明结构完整 |
| 前端检查 | lint / typecheck / build | 0 错误，构建成功 |
| 服务版本 | `GET /health` | version 0.3.0 |

### 关键技术决策

- **中间件顺序依赖 Starlette 语义**：后添加的中间件在外层——访问控制最外、CORS 最内，保证预检请求不被鉴权拦截
- **观测记录与业务解耦**：`record_llm_call` 使用独立会话并全量吞错，观测任何异常不影响面试主流程
- **评测锚点人工标注**：分数偏差对比人工锚点而非模型自评，指标可信可复现；报告含模型与提示词版本，支持后续 A/B
- **SSE 用 POST**（而非 GET + EventSource）：复盘需提交文本体，前端以 fetch 流式读取并手动分帧，同时天然复用统一鉴权与错误处理

---

## 第四阶段：语音转录 / 表达客观指标 / 多角色复盘工作流（已完成）

### 语音服务核实结论（先于实现的调研）

- 火山方舟当前接入的 glm-5-2-260617 是**文本对话模型**，不具备语音转文字能力；方舟豆包 ASR 端点实测 404（本账号未开通）
- 豆包语音（openspeech.bytedance.com）使用**独立于方舟的凭证**（SPEECH_APP_ID / SPEECH_ACCESS_TOKEN），本环境未配置
- 免费可用平替已落地两条：**硅基流动 SenseVoiceSmall（免费档）** 与 **本地 faster-whisper（完全离线免费）**；豆包语音作为可选第三提供方保留，不配置不影响使用

### 已完成内容

**T5 — 可插拔语音识别（不绑定任何单一厂商，绝不伪造转录）**

- `services/asr_service.py`：统一 `AsrProvider` 协议（`transcribe(audio, filename) -> TranscriptionResult`），三个实现：
  - `SiliconFlowAsr`：硅基流动 OpenAI 兼容 `/v1/audio/transcriptions`，模型 FunAudioLLM/SenseVoiceSmall，免费档；自动清理 SenseVoice 的 `<|zh|>` 语言/情绪标记；覆盖超时、401/403、429、非 200、空结果等失败分支
  - `LocalWhisperAsr`：本地 faster-whisper（CPU/int8，默认 small 模型），完全离线、无需任何凭证；首次使用经 `HF_ENDPOINT`（默认 hf-mirror.com 国内镜像）自动下载，模型进程内缓存；VAD 过滤静音
  - `VolcengineFlashAsr`：豆包语音录音文件识别极速版（独立凭证，可选保留），支持句级时间戳
- 工厂 `get_asr_provider()`：`ASR_PROVIDER=auto`（默认）时按 硅基流动 → 豆包 → 本地 Whisper 顺序挑选**就绪**提供方（本地 Whisper 的就绪条件为已安装且模型已缓存）；可显式指定 `siliconflow` / `local` / `volcengine`
- 全部未就绪时工厂返回 `None`，路由如实返回 `asr_status=not_configured`、`transcript=""`，并给出三条启用路径指引；**本地客观指标照常计算**，不伪造任何转录文字
- `asr_status()`：逐提供方上报配置状态（是否就绪、缺失的环境变量、启用方法、模型是否已缓存），不泄露密钥
- 前端 `lib/audio.ts`：浏览器 MediaRecorder 录音 → AudioContext 解码 PCM → 统一封装 16-bit 单声道 WAV 上传；同时支持音频文件上传（wav/mp3/m4a/webm/ogg/flac，20MB 内）

**T5 — 表达客观指标（全部本地计算，无外部依赖）**

- `services/audio_metrics.py`：
  - WAV（PCM）解析：时长、采样率、位深、多声道平均；非 WAV 格式给出明确格式错误
  - 停顿画像：30ms 滑动窗口 RMS，低于全局峰值 8% 判静音 → 停顿次数、最长停顿、停顿时长合计、静音占比
  - 语速：转录字数 / 净说话时长（总时长扣除静音）字/分钟；转录不可用时 `available=false` 并注明原因，不编造
  - 填充词：嗯/啊/呃/哎/emm/uh/um/那个/就是/然后/其实 模式计数与合计

**T6 — 多角色结构化复盘工作流**

- `services/expression_workflow.py`：默认流程 **结构分析师 → 内容深度分析师 → 表达教练**，教练以前两份结构化报告为输入（角色间真实数据依赖）
- 每个角色有独立 Pydantic 输出 schema，模型返回经 `model_validate` 强校验；列表字段做键名容错规整
- 失败处理：单步 schema 校验失败或模型调用失败自动**重试一次**；依赖步骤未完成时后续步骤标记 `skipped`；全流程不抛异常，返回 `completed / partial / failed` 整体状态，每步记录耗时与尝试次数
- AI 模型未配置时三角色均如实标记失败原因，不生成假复盘

**数据与 API**

- 数据模型：`ExpressionAnalysis` 表（转录文本、提供方、客观指标 JSON、工作流结果 JSON、状态与错误信息），Alembic 迁移 `7c4f2a91d8e3` 已执行
- API（前缀 `/api/v1/expression`）：
  - `GET /status` 语音服务与 AI 模型配置状态、音频限制与格式
  - `POST /transcribe` 上传音频 → 真实转录 + 本地客观指标，未配置时转录为空但指标照算
  - `POST /analyze` 直接提交文本或引用转录记录 → 多角色工作流复盘
  - `GET /records` / `GET /records/{id}` / `DELETE /records/{id}` 历史记录
- 前端 `/expression`：录音 / 上传 / 直接贴文本三入口；未配置状态下显示三条启用引导；客观指标卡片、三角色复盘结果（评分与建议）、历史记录列表；长耗时复盘按钮文案为「分析师们正在阅读，约需一分钟…」
- 路由与侧边栏导航（AudioLines 图标，「表达分析」）已注册，沿用纯 CSS 进入动画，无路由竞态

### 配置项（backend/.env，全部可选；不配也能用本地指标与文本复盘）

| 变量 | 作用 | 默认 |
| --- | --- | --- |
| `ASR_PROVIDER` | `auto` / `siliconflow` / `local` / `volcengine` | `auto` |
| `ASR_SILICONFLOW_API_KEY` | 硅基流动免费档 Key（siliconflow.cn 注册） | 空 |
| `ASR_LOCAL_MODEL` | 本地 faster-whisper 模型规格（tiny/base/small/medium…） | `small` |
| `HF_ENDPOINT` | 模型下载镜像 | `https://hf-mirror.com` |
| `SPEECH_APP_ID` / `SPEECH_ACCESS_TOKEN` | 豆包语音极速版独立凭证（可选） | 空 |

### 真实测试结果（均已实际执行）

| 检查项 | 命令 / 方式 | 结果 |
| --- | --- | --- |
| 后端测试 | `python -m pytest`（backend/） | 95 passed（T5/T6 单元与集成 + 前三阶段回归） |
| 真实转录集成测试 | 本地 faster-whisper small + `tests/assets/sample_speech.wav`（约 11 秒中文语音） | 真实识别出中文内容，提供方标记 `local_whisper:small`，无伪造 |
| 未配置场景 | 三提供方均不就绪 | 接口 201 返回 `not_configured`、空转录 + 三条启用指引，本地停顿指标照常返回 |
| 工作流失败处理 | mock schema 不符 / ArkError | 单步重试一次后记 failed，依赖步骤 skipped，整体 partial/failed 如实返回 |
| 三角色真实复盘 | glm-5-2-260617 串行三角色 | 结构 8.5/10、深度 6/10，教练建议齐全，每步含耗时与尝试次数 |
| 前端检查 | lint / typecheck / build | 0 错误，构建成功 |
| 浏览器端到端 | 录音 → 转录 → 三角色复盘 → 历史记录 | 全流程通过；导航无白屏；控制台无错误 |

浏览器端验证为实际浏览器操作（页面快照 + 交互点击），未使用自动化端到端测试框架（如 Playwright），该类测试在第五阶段补充。

### 第五阶段需要的准备

- 质量评测体系、隐私保护（音频/简历等敏感数据留存策略）、服务稳定性与部署（含 ASR 模型首次下载与常驻内存的资源评估）

---

## 第三阶段：RAG / 技能图谱 / 简历匹配（已完成）

### 体验修复（第三阶段开始前，均已完成）

- **路由切换需刷新**：彻底移除 motion/react 的路由生命周期依赖，`PageTransition` 改为纯 CSS 进入动画（`.page-enter` / `.card-enter`），无 JS 生命周期可卡死，任何页面间导航均即时渲染
- **移除状态徽章**：「AI 已就绪（模型名）」与「后端服务器在线」徽章在正常时静默，仅在未配置 / 连接失败时才显示警示
- **AI 出题提速**：精简 prompt 与输出限制（题目约 50 字内），创建任务到出题时间明显缩短
- **加载文案寓意化**：出题「凝题中…」、评分「映照进行中…」等，不出现「AI 正在准备」类描述

### 已完成内容

**T2 — RAG 知识库（出题有据可依，证据真实可溯）**

- 数据模型：`KnowledgeDocument` / `KnowledgeChunk` 两张表，迁移已执行
- `services/knowledge_service.py`：txt / md / docx 文本提取（docx 解析 XML）、按段落聚合约 500 字分块、知识库 CRUD
- `services/retrieval.py`：本地 BM25 检索内核（中文单字 + 相邻双字分词），检索结果带匹配分与文档出处（文档名 + 块号），全程可追溯
- 出题集成：创建面试任务可指定知识文档，问题生成前先检索相关片段注入 prompt，题目紧扣资料内容
- API：`GET/POST /api/v1/knowledge/documents`、`GET /api/v1/knowledge/documents/{id}`、`DELETE ...`、`GET /api/v1/knowledge/search?q=...`
- 前端 `/knowledge`：上传（5MB 内）、检索验证、文档列表、分块详情查看、删除

**T3 — 技能图谱与自适应训练（真实历史报告驱动）**

- `services/skill_service.py`：从已完成面试的真实评分报告聚合四维度画像（内容深度 / 表达清晰 / 逻辑结构 / 岗位匹配）、总分走势、强弱项判定
- 自适应训练建议：最弱维度驱动下一程的难度档位与侧重方向，并给出具体练习方法；无历史数据时明确提示先完成一场面试
- API：`GET /api/v1/skills/profile`、`GET /api/v1/skills/graph`、`GET /api/v1/skills/recommendation`
- 前端 `/skills`：维度画像、总分走势、下一程建议卡片、「按建议开一场」直达创建面试

**T9 — 简历与岗位语义匹配（匹配依据可解释）**

- `services/matching_service.py`：技能词典 + 词边界匹配（英文别名按 `\b` 正则，「Java」不会误命中「JavaScript」）；每个命中技能附简历原文依据与岗位原文依据；缺失技能如实列出
- 统计层必算（匹配度、命中、缺失），LLM 层尽力而为：真实模型生成提升建议，失败时明确标注降级原因，不伪造建议
- 匹配记录持久化（`ResumeMatchRecord`），`GET /api/v1/matching/records` 可回看
- API：`POST /api/v1/matching/resume`、`GET /api/v1/matching/records`
- 前端 `/matching`：目标岗位 / 岗位描述 / 简历粘贴或文件上传（txt / md）、匹配结果（分数、命中与缺隙双侧证据、AI 建议）

**前端接入**

- 三个新页面注册进路由与侧边栏导航，工作台功能模块入口全部指向真实页面
- 工作台能力统计区文案改为「查看技能图谱，寻找下一程方向」直达链接

### 关键技术决策

- **检索端不依赖 embedding API**：实测火山方舟 embedding 端点 404（未开通），检索采用本地 BM25 词频匹配——无外部依赖、结果可解释（匹配分来自词频统计）、证据始终可追溯。若后续开通 embedding 服务，可在 `retrieval.py` 平滑替换为向量检索
- **所有真实模型调用失败时降级并如实标注**（与既定约定一致），不生成假 AI 结果

### 真实测试结果（均已实际执行）

| 检查项 | 命令 / 方式 | 结果 |
| --- | --- | --- |
| 后端测试 | `python -m pytest`（backend/） | 51 passed（T2/T3/T9 单元与集成 + 前两阶段回归） |
| 前端 Lint | `npm run lint`（frontend/） | 0 错误 0 警告 |
| 前端类型检查 | `npm run typecheck`（frontend/） | 通过 |
| 前端生产构建 | `npm run build`（frontend/） | 成功 |
| 浏览器渲染验证 | 三个新页面 | 全部正常，无 JS 错误，无卡住透明元素 |
| 知识库端到端 | 上传 txt → API/页面检索 | 分块 1 块 495 字，检索「性能优化」命中匹配分 2.14，证据含出处与原文 |
| 简历匹配端到端 | 页面提交前端工程师简历 | 匹配度 66.5，命中 React/TypeScript/JavaScript 均带双侧原文证据，Node.js 正确列入缺失，「Java」未误命中 JavaScript；AI 建议来自真实模型（glm-5-2-260617） |
| 技能图谱端到端 | 页面访问 | 维度画像 / 总分走势 / 自适应建议均由真实历史评分驱动（最近 1 场面试，最弱维度内容深度驱动难度与侧重） |
| 导航切换验证 | 侧边栏连续导航 5+ 页面 | 全部即时渲染，无白屏、无需刷新 |

浏览器端验证为实际浏览器操作（页面快照 + 交互点击），未使用自动化端到端测试框架（如 Playwright），该类测试在第五阶段补充。

### 第四阶段（已完成）

- 语音识别（Web 端录音 / 上传 + 后端多提供方可插拔 ASR：硅基流动免费档 / 本地 faster-whisper 离线 / 豆包可选）、表达客观指标、多角色 AI 复盘工作流，详见上方第四阶段章节
- 若需更强检索质量：仍可在开通火山方舟 embedding 服务后切换向量检索（本地 BM25 已满足当前需求）

---

## 第二阶段：真实 AI 面试核心（已完成）

### 已完成内容

**后端（backend/）— 数据层**
- SQLAlchemy 2.0 ORM：`InterviewTask` / `InterviewQuestion` / `InterviewAnswer` / `InterviewReport` 四张表（`app/models.py`）
- 任务状态机：`generating_questions → ready → in_progress → generating_report → completed`，异常进入 `failed` 并保留原因
- Alembic 迁移（`migrations/versions/1ba61df3306d_init_interview_tables.py`）已执行，`alembic_version` 记录到位；开发库为 SQLite（`backend/aurel.db`），连接串可经环境变量切换 PostgreSQL
- `backend/.env`（已 gitignore）配置 `ARK_API_KEY` / `ARK_BASE_URL` / `ARK_MODEL` / `DATABASE_URL`，密钥仅存在于服务端

**后端 — AI 能力层（全部真实调用，无任何假结果）**
- `services/ark_client.py`：火山方舟 Chat Completions 客户端（httpx），含 JSON 健壮解析（代码块剥离 / 尾逗号容忍）
- `services/question_generator.py`：按岗位 + 题目数生成结构化面试问题
- `services/follow_up.py`：基于回答内容实时判断是否追问并生成追问
- `services/scoring.py`：T1 可解释评分引擎——总分 + 四维度（内容深度 / 表达清晰 / 逻辑结构 / 岗位匹配）分项分，每项含回答原文证据、评分理由，另有整体亮点与改进建议
- `services/interview_service.py`：流程编排（创建生成问题 → 答题 → 追问决策 → 下一题 → 全部完成触发评分）；评分失败时任务回滚至 `in_progress` 并返回明确错误

**后端 — API（`app/routers/interviews.py`）**
- `POST /api/v1/interviews` 创建任务并生成问题（201）
- `GET /api/v1/interviews` 任务列表 / `GET /api/v1/interviews/{task_id}` 任务详情
- `POST /api/v1/interviews/{task_id}/answers` 提交回答
- `POST /api/v1/interviews/{task_id}/next` 追问决策与推进
- `POST /api/v1/interviews/{task_id}/finish` 完成并触发 T1 评分
- `GET /api/v1/interviews/{task_id}/report` 评分报告
- `GET /api/v1/ai/status` AI 配置状态（已配置 / 未配置，不泄露密钥）

**前端（frontend/）**
- `/interview/new`：真实创建任务表单，提交即调用后端生成真实问题；AI 未配置时创建按钮禁用并明确提示
- `/interview/:id`（InterviewSessionPage）：真实面试工作台——进度指示（第 N 题 / 共 M 题，追问时显示「第 N 题追问」）、答题提交、追问交互、已回答记录回看
- `/reports`：报告中心从后端拉取真实任务与报告列表（区分已完成 / 进行中）
- `/reports/:id`（ReportDetailPage）：T1 报告详情——总分、四维度分项（证据 + 理由）、亮点、改进建议、完整问答回顾
- `/app` 工作台：真实任务统计与最近任务列表
- 全局 AI 状态徽章（AiStatusBadge）：实时显示模型配置状态

### 真实测试结果（均已实际执行）

| 检查项 | 命令 | 结果 |
| --- | --- | --- |
| 后端测试 | `python -m pytest`（backend/） | 23 passed（含 mock 模型、未配置 key、404、评分失败回滚、追问排序等场景） |
| 数据库迁移 | alembic | 4 张表 + `alembic_version` 均已创建，版本 `1ba61df3306d` |
| 前端 Lint | `npm run lint`（frontend/） | 0 错误 0 警告 |
| 前端类型检查 | `npm run typecheck`（frontend/） | 通过 |
| 前端生产构建 | `npm run build`（frontend/） | 成功 |
| 真实模型端到端 | 火山方舟 glm-5-2-260617 | 创建任务生成 3 个真实问题 → 每题真实追问 → T1 评分返回完整可解释结构 |
| 浏览器渲染验证 | 首页 / 工作台 / 报告中心 / 报告详情 / 创建任务 / 面试工作台 | 全部通过，无 JS 错误；答题与追问交互正常 |

浏览器端验证为实际浏览器操作（页面快照 + 交互点击），未使用自动化端到端测试框架（如 Playwright），该类测试在第五阶段补充。

### 错误处理约定（本阶段已落实）

- 模型未配置：创建任务返回明确错误，前端禁用入口并显示「未配置」
- 模型调用失败 / 网络错误：任务进入 `failed`（评分阶段则回滚 `in_progress`），API 返回可读错误信息，前端展示，不伪造任何 AI 输出
- 任务状态异常（如对 `completed` 任务再答题）：返回 409 / 404 语义化错误

### 第二阶段收尾修复（2026-10-10）

**问题 1：Vite 仅监听 IPv6，`127.0.0.1:5173` 无法访问**
- 现象：浏览器打开页面空白（连接被拒）
- 修复：`vite.config.ts` 增加 `server.host: true`，同时监听 IPv4 / IPv6

**问题 2：从工作台导航到创建面试页闪现后空白**
- 现象：`/app` → `/interview/new` 时表单闪现后永久空白（DOM 存在但卡在 `opacity: 0; translateY(-8px)` 的 exit 样式），刷新才恢复
- 根因：三层嵌套动画竞态——AppLayout 的 `AnimatePresence mode="wait"` 路由切换动画 + 页面内 `PageTransition`（带 exit）+ 页内 `AnimatePresence` 与 `layoutId`。由于 React Router 的 `Outlet` 由 context 驱动，exit 动画期间渲染的已是新页面内容，`layoutId` 在新旧子树快速交替时触发共享布局竞态，使新页面卡死在退出样式
- 修复：
  - `InterviewNewPage`：移除冗余的 `PageTransition` 包装与 `layoutId="interview-setup-card"`（保留 failed/form 状态切换动画）
  - `AppLayout`：路由切换改为纯进入动画（保留 A1 淡入位移），去掉 exit 等待机制，从根上消除该类竞态
- 验证：浏览器实际操作 `/app ↔ /interview/new` 连续 5 次导航 + `/reports` 均正常，无卡住的透明元素（JS 检查 opacity:0 元素数为 0），控制台无错误；lint / typecheck / build 全部通过

### 第三阶段需要的准备（已落实）

- 火山方舟 API Key 与模型（已就绪）；RAG 检索最终采用本地 BM25 方案（embedding 端点未开通，见第三阶段关键技术决策）
- 第三阶段已实现：RAG 知识库、个性化技能图谱、自适应训练、简历与岗位匹配

---

## 第一阶段：基础工程（已完成）

### 已完成内容

**前端（frontend/）**
- Vite + React 19 + TypeScript + Tailwind CSS 工程，统一设计令牌（#F8FAFC / #1D4ED8 / #0F766E / #334155）
- 六个页面：品牌首页 `/`、工作台 `/app`、面试任务设置 `/interview/new`、面试工作台预览 `/interview/preview`、报告中心 `/reports`、404 页面
- 工作台布局（桌面左侧导航 + 移动端抽屉导航）与独立面试工作台布局
- 统一 UI 组件：Button / ButtonLink、Card、Badge、EmptyState、TextField / TextAreaField / RadioCardGroup、PreviewBanner、ServiceStatus
- 动画组合：A1 路由淡入位移（PageTransition + AnimatePresence）、A2 顺序流程横向滑入（StaggerList）、A3 共享元素动效（侧边栏导航指示条 layoutId、面试设置表单与确认卡片切换 layoutId、预览页步骤指示器 layoutId）
- `MotionConfig reducedMotion="user"` + CSS `prefers-reduced-motion` 兜底
- 面试设置表单：必填校验、长度限制、错误提示（aria-invalid / aria-describedby）、提交后明确显示"预览模式，正式任务创建将在第二阶段接入"
- 统一 API 客户端（fetch 包装 + ApiError），健康检查 30 秒轮询 + 手动重试，区分加载中 / 已连接 / 连接失败三种状态
- Vite 代理：`/api` → `http://127.0.0.1:8000`

**后端（backend/）**
- FastAPI + Pydantic 模块化结构（app/main、app/config、app/routers/health、app/schemas/health）
- `GET /api/v1/health` 返回 Pydantic Schema 定义的健康信息
- CORS 配置（默认允许 Vite 开发服务器来源，可用 `AUREL_CORS_ORIGINS` 环境变量覆盖）
- pytest 测试 3 项：健康检查 200 与字段校验、API 未知路径 404、根路径 404

### 真实测试结果（均已实际执行）

| 检查项 | 命令 | 结果 |
| --- | --- | --- |
| 后端测试 | `python -m pytest`（backend/） | 3 passed |
| 前端 Lint | `npm run lint`（frontend/） | 0 错误 0 警告 |
| 前端类型检查 | `npm run typecheck`（frontend/） | 通过 |
| 前端生产构建 | `npm run build`（frontend/） | 成功（626ms） |
| 后端健康检查（直连 8000） | HTTP GET | `{"status":"ok","service":"aurel-api","version":"0.1.0"}` |
| 前端代理转发（5173 → 8000） | HTTP GET | 同上，代理正常 |
| 浏览器渲染验证 | 首页 / 工作台 / 面试设置 | 全部通过（含表单校验交互） |
| 浏览器渲染验证 | 面试预览 / 报告中心 / 404 | 全部通过（含 404 返回工作台导航） |

浏览器端验证为实际浏览器操作（页面快照 + 交互点击），未使用自动化端到端测试框架（如 Playwright），该类测试在第五阶段补充。

### 启动命令

```bash
# 后端
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 前端
cd frontend
npm run dev
```

### 未实现 / 明确标注的事项

- 真实 AI 面试（题目生成、评分、反馈）：第二阶段接入火山方舟，当前所有相关界面均以「预览」「尚未接入」标注
- 任务数据持久化：第二阶段引入数据库（优先 SQLite，保留 PostgreSQL 迁移能力）
- 能力分析、成长记录模块：界面上标注「尚未接入」，按钮禁用
- 报告中心：仅布局预览 + 空状态，无示例数据

### 第二阶段需要的准备

- 火山方舟 API Key：通过后端环境变量 `ARK_API_KEY` 配置，以及实际使用的模型/接入点 ID 环境变量
- 第二阶段将实现：SQLAlchemy 数据模型、模型适配层、真实 AI 面试流程、评分引擎、结果历史
