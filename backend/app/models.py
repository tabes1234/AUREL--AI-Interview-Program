"""SQLAlchemy ORM 模型：用户账户、面试任务、问题、回答与报告。"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models_base import Base


def utcnow() -> datetime:
    """当前 UTC 时间（naive）。

    SQLite 不保留时区信息：读回的 datetime 一律是 naive，统一以 naive UTC
    写入/比较可避免 offset-naive/aware 混用崩溃。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    """账户：用户名 + 密码认证；密码只存 PBKDF2 摘要，绝不存明文。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 用户名：注册时去首尾空白；唯一性比较不区分大小写
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    # PBKDF2-SHA256 摘要（格式：pbkdf2_sha256$迭代次数$盐$哈希）
    password_hash: Mapped[str] = mapped_column(String(200))
    nickname: Mapped[str] = mapped_column(String(40))
    # 历史遗留列：邮箱验证码认证已移除，新用户不再写入；保留以兼容旧库
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # active / disabled
    status: Mapped[str] = mapped_column(String(20), default="active")
    # user / admin；管理员只能通过受控脚本（backend/scripts/create_admin.py）设置，
    # 注册接口不允许自设角色
    role: Mapped[str] = mapped_column(String(20), default="user", server_default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserSession(Base):
    """服务端会话：浏览器只持有不透明随机令牌（HttpOnly Cookie），库内仅存摘要。"""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class InterviewTask(Base):
    __tablename__ = "interview_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    position: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[str] = mapped_column(String(20))  # basic / intermediate / advanced
    language: Mapped[str] = mapped_column(String(10))  # zh / en
    question_count: Mapped[int] = mapped_column(Integer)
    # generating_questions -> ready -> in_progress -> generating_report -> completed
    # 任何 AI 步骤失败 -> failed（error_message 记录真实原因，可重试）
    status: Mapped[str] = mapped_column(String(30), default="generating_questions")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 问澜目录上下文（旧任务 / 直接创建的任务为 null；occupation_id="custom" 表示自定义职业）
    industry_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    occupation_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    experience_level: Mapped[str | None] = mapped_column(String(30), nullable=True)
    interview_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    focus_areas: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 归属用户（NULL = 迁移前的历史遗留数据，登录用户不可见）
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=utcnow, onupdate=utcnow
    )

    questions: Mapped[list["InterviewQuestion"]] = relationship(
        back_populates="task", order_by="InterviewQuestion.id", cascade="all, delete-orphan"
    )
    report: Mapped["InterviewReport | None"] = relationship(
        back_populates="task", uselist=False, cascade="all, delete-orphan"
    )


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("interview_tasks.id"), index=True)
    # 主问题的序号从 1 开始；追问与其主问题共享 order_index
    order_index: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(20))  # main / follow_up
    # 主问题专用：是否已完成追问决策（无论是否真的追问）
    follow_up_resolved: Mapped[bool] = mapped_column(default=False)
    parent_question_id: Mapped[int | None] = mapped_column(
        ForeignKey("interview_questions.id"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text)
    # 问澜结构化题元数据（追问 / 旧任务的问题为 null）
    category: Mapped[str | None] = mapped_column(String(30), nullable=True)  # 题型
    dimension: Mapped[str | None] = mapped_column(String(60), nullable=True)  # 能力维度
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)  # 考查目标
    rubric: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 评分要点
    suggested_follow_up: Mapped[str | None] = mapped_column(Text, nullable=True)  # 可选追问
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    task: Mapped[InterviewTask] = relationship(back_populates="questions")
    answer: Mapped["InterviewAnswer | None"] = relationship(
        back_populates="question", uselist=False, cascade="all, delete-orphan"
    )


class InterviewAnswer(Base):
    __tablename__ = "interview_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("interview_questions.id"), unique=True, index=True
    )
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    question: Mapped[InterviewQuestion] = relationship(back_populates="answer")


class InterviewReport(Base):
    __tablename__ = "interview_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("interview_tasks.id"), unique=True, index=True
    )
    overall_score: Mapped[float] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(Text)
    # T1 可解释评分结构：
    # dimensions: [{name, score, evidence, rationale}]
    # strengths: [str]
    # improvements: [{title, detail}]
    dimensions: Mapped[list[dict]] = mapped_column(JSON)
    strengths: Mapped[list[str]] = mapped_column(JSON)
    improvements: Mapped[list[dict]] = mapped_column(JSON)
    model_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    task: Mapped[InterviewTask] = relationship(back_populates="report")


class KnowledgeDocument(Base):
    """T2 RAG：上传的原始知识文档（txt / md / docx 提取文本）。"""

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    filename: Mapped[str] = mapped_column(String(300))
    content_text: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="ready")  # ready / failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="document", order_by="KnowledgeChunk.chunk_index",
        cascade="all, delete-orphan",
    )


class KnowledgeChunk(Base):
    """T2 RAG：文档分块，检索证据的最小可追溯单元。"""

    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_documents.id"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")


class ResumeMatchRecord(Base):
    """T9：简历与岗位语义匹配的历史记录（匹配依据可解释、可回看）。"""

    __tablename__ = "resume_match_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    position: Mapped[str] = mapped_column(String(120))
    job_description: Mapped[str] = mapped_column(Text, default="")
    resume_text: Mapped[str] = mapped_column(Text)
    # T9 可解释结构：
    # match_score: float
    # matched_skills: [{skill, evidence, job_evidence}]
    # missing_skills: [str]
    # suggestions: [str]（LLM 生成；失败降级时为空并记录 llm_error）
    # llm_error: str | None
    result: Mapped[dict] = mapped_column(JSON)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class ExpressionAnalysis(Base):
    """T5/T6：表达分析记录——真实转录（或直录文本）、客观指标与多角色工作流输出。

    transcript 只来自真实 ASR 或用户输入；ASR 未配置时 asr_status=not_configured
    且 transcript 为空，绝不伪造转录。
    """

    __tablename__ = "expression_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(20))  # recording / upload / text
    filename: Mapped[str | None] = mapped_column(String(300), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ok / not_configured / failed / not_attempted（纯文本输入未尝试 ASR）
    asr_status: Mapped[str] = mapped_column(String(30), default="not_attempted")
    asr_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    asr_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 客观指标（本地计算）：
    # {audio: {duration_ms, pause_count, longest_pause_ms, total_pause_ms, silence_ratio} | null,
    #  speech: {available, unavailable_reason?, char_count, speech_rate_cpm?, filler_words, filler_total}}
    metrics: Mapped[dict] = mapped_column(JSON)
    # T6 多角色工作流：{status, steps: [{role, title, status, output, error, elapsed_ms, attempts}], model_name}
    workflow: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class LlmCallRecord(Base):
    """T10：模型调用观测——每次真实模型调用一行，用于统计、排障与实验对比。

    写入失败绝不影响业务调用本身（见 services/llm_observability.py）。
    """

    __tablename__ = "llm_call_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 触发调用的登录用户（请求上下文注入；历史数据与运维通道调用为 NULL）
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    service: Mapped[str] = mapped_column(String(50), index=True)
    model: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(20), default="unversioned")
    status: Mapped[str] = mapped_column(String(20))  # success / error
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    experiment: Mapped[bool] = mapped_column(Boolean, default=False)
    error_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class JobAnalysis(Base):
    """知岗：JD 解析历史。result 仅保存通过结构化校验的分析结果。

    - evidence 均为 JD 原文摘录；服务端逐条核验，无法在原文定位的判断标记
      is_inferred=True（模型推断，置信度降低），绝不冒充原文结论。
    - jd_hash + version_no：同一用户对同一 JD 重复解析时版本递增，保留全部历史。
    """

    __tablename__ = "job_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))  # 岗位名称（列表展示与问澜联动用）
    jd_text: Mapped[str] = mapped_column(Text)  # 原始 JD 全文（证据核验与回看依据）
    jd_hash: Mapped[str] = mapped_column(String(64), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="ready")  # ready / failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # 来源岗位（知潮资料库条目，可为空=用户粘贴/上传的 JD）
    source_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class Resume(Base):
    """履历成章：结构化简历主档。content 为经 Pydantic 校验的结构化字段 JSON。"""

    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    template_id: Mapped[str] = mapped_column(String(40), default="clean")
    content: Mapped[dict] = mapped_column(JSON)
    current_version_no: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, onupdate=utcnow)

    versions: Mapped[list["ResumeVersion"]] = relationship(
        back_populates="resume", order_by="ResumeVersion.version_no.desc()",
        cascade="all, delete-orphan",
    )


class ResumeVersion(Base):
    """履历成章：简历版本快照。保存/恢复/复制都会生成新版本，历史不可变。"""

    __tablename__ = "resume_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(120))
    template_id: Mapped[str] = mapped_column(String(40))
    content: Mapped[dict] = mapped_column(JSON)
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    resume: Mapped[Resume] = relationship(back_populates="versions")


class ChallengeRun(Base):
    """度衡：限时模拟挑战。服务端时钟为唯一计时依据，防止客户端篡改。"""

    __tablename__ = "challenge_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    position: Mapped[str] = mapped_column(String(120))
    difficulty: Mapped[str] = mapped_column(String(20))  # basic / intermediate / advanced
    language: Mapped[str] = mapped_column(String(10), default="zh")
    question_count: Mapped[int] = mapped_column(Integer)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    # created -> in_progress -> evaluating -> completed / failed
    status: Mapped[str] = mapped_column(String(20), default="created")
    # 一次性生成的题目 JSON：[{order_index, content, category, dimension, rubric}]
    questions: Mapped[list[dict]] = mapped_column(JSON)
    # 答题 JSON：[{order_index, answer}]
    answers: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    overtime: Mapped[bool] = mapped_column(default=False)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 评分结果 JSON（与 InterviewReport 同构：dimensions/strengths/improvements/summary）
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class MistakeCard(Base):
    """回澜错题本：从问澜报告收集的待巩固题目，SM-2 间隔重复调度复习。"""

    __tablename__ = "mistake_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("interview_questions.id"), index=True
    )
    position: Mapped[str] = mapped_column(String(120), default="")
    question_content: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    dimension: Mapped[str | None] = mapped_column(String(60), nullable=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    rubric: Mapped[list | None] = mapped_column(JSON, nullable=True)
    my_answer: Mapped[str] = mapped_column(Text, default="")
    # SM-2 调度参数
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)  # 默认立即可复习
    last_grade: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-5
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class CareerConversation(Base):
    """知途：AI 职业顾问「小鸥」的对话会话。

    summary / summarized_until_id：分层记忆的会话摘要层。
    摘要由触发阈值后的增量消息归纳而成，可追溯到本会话 1..summarized_until_id
    的消息范围；摘要只压缩不改写用户原意。
    """

    __tablename__ = "career_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120), default="新的旅程")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summarized_until_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=utcnow, onupdate=utcnow
    )

    messages: Mapped[list["CareerMessage"]] = relationship(
        back_populates="conversation", order_by="CareerMessage.id",
        cascade="all, delete-orphan",
    )


class CareerMessage(Base):
    """知途：对话中的单条消息（user / assistant，均为用户可见的真实记录）。"""

    __tablename__ = "career_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("career_conversations.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))  # user / assistant
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    conversation: Mapped[CareerConversation] = relationship(back_populates="messages")


class CareerProfile(Base):
    """知途：用户长期职业档案（一人一份），由可追溯的事实条目构成。

    summary 是 AI 生成的当前情况参考，可被档案事实推翻；真正进入模型上下文的
    只有经过确认（confirmed）或用户亲述的事实条目。
    """

    __tablename__ = "career_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=utcnow, onupdate=utcnow
    )

    facts: Mapped[list["CareerProfileFact"]] = relationship(
        back_populates="profile", order_by="CareerProfileFact.id",
        cascade="all, delete-orphan",
    )


class CareerProfileFact(Base):
    """知途：档案中的单条记忆，来源三态严格区分，不得把 AI 猜测当成用户经历。

    - source_type=user_stated：用户原话明确说出（必须能定位到原文片段），视为已确认；
    - source_type=ai_generalized：AI 基于用户内容归纳，待用户确认；
    - source_type=ai_inferred：AI 推断的可能性，confidence 必填，永远待确认。
    source_message_id 不设外键约束：来源消息被删除后事实本身仍可保留。
    """

    __tablename__ = "career_profile_facts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("career_profiles.id"), index=True)
    category: Mapped[str] = mapped_column(String(30), default="other")
    content: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(20), default="ai_generalized")
    source_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=utcnow, onupdate=utcnow
    )

    profile: Mapped[CareerProfile] = relationship(back_populates="facts")


class CareerPlan(Base):
    """知途：阶段性职业行动计划（7/30/90 天）。规划不承诺求职成功或薪资结果。"""

    __tablename__ = "career_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(120))
    situation: Mapped[str] = mapped_column(Text, default="")
    focus_role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active / archived
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    # 规划所依据的数据版本：记录生成/复盘时实际使用的数据源与时间（第十六项需求）
    data_basis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=utcnow, onupdate=utcnow
    )

    actions: Mapped[list["CareerPlanAction"]] = relationship(
        back_populates="plan", order_by="CareerPlanAction.position",
        cascade="all, delete-orphan",
    )
    revisions: Mapped[list["CareerPlanRevision"]] = relationship(
        back_populates="plan", order_by="CareerPlanRevision.version_no.desc()",
        cascade="all, delete-orphan",
    )


class CareerPlanAction(Base):
    """知途：计划中的单个行动任务，可完成/跳过/复盘/调整期限。"""

    __tablename__ = "career_plan_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("career_plans.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    phase: Mapped[str] = mapped_column(String(10), default="30d")  # 7d / 30d / 90d
    goal: Mapped[str] = mapped_column(String(200))
    steps: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/done/skipped
    review: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_goal: Mapped[str | None] = mapped_column(String(200), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=utcnow, onupdate=utcnow
    )

    plan: Mapped[CareerPlan] = relationship(back_populates="actions")


class CareerPlanRevision(Base):
    """知途：规划版本快照。生成或任何调整都留档，历史不可变、可回溯。"""

    __tablename__ = "career_plan_revisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("career_plans.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    change_note: Mapped[str] = mapped_column(String(200), default="")
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    plan: Mapped[CareerPlan] = relationship(back_populates="revisions")


class CareerWorkflowRun(Base):
    """知途：多步骤联动工作流运行记录。

    每一步真实调用对应模块的服务（知岗/简历/合契/知藏/观己/度衡/成长轨迹/问澜），
    逐步记录状态与结果摘要；失败如实落库，绝不伪造成功结果。
    """

    __tablename__ = "career_workflow_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="running")  # running/succeeded/failed
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=utcnow, onupdate=utcnow
    )


class JobPosition(Base):
    """知潮：真实岗位资料库条目。

    数据来源原则：
    - 只保存真实核对过或用户手动导入的岗位；绝不编造岗位。
    - 来源未提供发布时间时 published_at 为空，published_note 标注「来源未提供发布时间」，
      不得伪造时间。
    - 无法确认是否仍在招聘时 hiring_status="unconfirmed"（招聘状态未确认），
      不能默认标记为正在招聘。
    - 公开展示遵循 display_permission：summary_only 只展示事实性摘要 + 原文链接，
      jd_full_text 不进入公开目录展示。
    """

    __tablename__ = "job_positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String(80), index=True)
    company_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    title: Mapped[str] = mapped_column(String(120), index=True)
    industry_id: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    occupation_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    location: Mapped[str] = mapped_column(String(200), default="")
    level: Mapped[str] = mapped_column(String(40), default="")  # 校招 / 社招 / 实习 / 岗位级别
    published_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    published_note: Mapped[str] = mapped_column(String(60), default="来源未提供发布时间")
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # official_seed（官方页面人工核对）/ manual（用户手动录入，无链接）/ user_import（用户导入）
    source_type: Mapped[str] = mapped_column(String(30), default="user_import")
    # summary_only（仅摘要+链接）/ full_text（原文可公开展示）
    display_permission: Mapped[str] = mapped_column(String(20), default="summary_only")
    responsibilities_summary: Mapped[str] = mapped_column(Text, default="")
    required_skills_summary: Mapped[str] = mapped_column(Text, default="")
    preferred_skills_summary: Mapped[str] = mapped_column(Text, default="")
    experience_summary: Mapped[str] = mapped_column(String(300), default="")
    # 原文全文仅用于知岗解析（导入者与解析流程），不进入公开目录展示
    jd_full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    # unconfirmed（未确认）/ open / closed
    hiring_status: Mapped[str] = mapped_column(String(20), default="unconfirmed")
    # ok（链接有效）/ stale（待核验）/ dead（源页面失效）
    link_status: Mapped[str] = mapped_column(String(20), default="unverified")
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    verified_note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    imported_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, onupdate=utcnow)

    favorites: Mapped[list["JobFavorite"]] = relationship(
        back_populates="position", cascade="all, delete-orphan"
    )


class JobPositionChange(Base):
    """知潮：岗位数据历史变化记录（创建/更新/核验/失效），历史不可变。"""

    __tablename__ = "job_position_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("job_positions.id"), index=True)
    change_type: Mapped[str] = mapped_column(String(20))  # created / updated / verified / stale
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str] = mapped_column(String(300), default="")
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class JobFavorite(Base):
    """知潮：用户岗位收藏。"""

    __tablename__ = "job_favorites"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("job_positions.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    position: Mapped[JobPosition] = relationship(back_populates="favorites")

    __table_args__ = (UniqueConstraint("user_id", "position_id", name="uq_job_favorite"),)


class CareerKnowledgeChunk(Base):
    """知途 RAG：职业知识分段（第十五阶段）。

    来源 scope：
    - global：全局共享资料——知潮真实岗位（job_position）、知岗解析结论（job_analysis）、
      岗位能力模型/就业指导资料（career_guide）。所有用户可检索，但仅含事实性摘要与来源引用。
    - user：用户个人资料衍生分段——已确认档案事实、个人简历结构（user_profile / user_resume），仅本人可见。
    向量表示：本地确定性词面哈希向量（128 维，可保存可复算）——方舟 embedding 未开通，
    如实命名为词面向量，不冒充语义向量。
    """

    __tablename__ = "career_knowledge_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(10), default="global", index=True)  # global / user
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    source_kind: Mapped[str] = mapped_column(String(30), index=True)
    source_id: Mapped[str] = mapped_column(String(60), default="")
    title: Mapped[str] = mapped_column(String(200), default="")
    industry_id: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    occupation_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    experience_level: Mapped[str] = mapped_column(String(30), default="")  # 校招/实习/社招/不限
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    vector: Mapped[list] = mapped_column(JSON, default=list)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class CareerSkillNode(Base):
    """知途能力图谱节点（第十五阶段）。

    status 四态严格区分，不得混用：
    - verified：已证实（来自真实练习结果：问澜报告、度衡挑战等）
    - user_stated：用户自述（档案已确认事实、简历中本人填写内容）
    - ai_inferred：AI 推断（必须带 confidence，待用户确认）
    - pending：尚待验证（用户或 AI 标记「需要通过练习/材料验证」）
    每个节点必须有来源（source_kind + source_ref），关系不由模型随意生成。
    """

    __tablename__ = "career_skill_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(30), index=True)
    # skill / required_skill / experience / direction / target_position / evidence / improvement_task
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    source_kind: Mapped[str] = mapped_column(String(30), default="user_manual")
    source_ref: Mapped[dict] = mapped_column(JSON, default=dict)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, onupdate=utcnow)


class CareerSkillEdge(Base):
    """知途能力图谱边：真实事件产生的关系（完成面试→证据连向技能等），带来源。"""

    __tablename__ = "career_skill_edges"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    from_node_id: Mapped[int] = mapped_column(ForeignKey("career_skill_nodes.id"), index=True)
    to_node_id: Mapped[int] = mapped_column(ForeignKey("career_skill_nodes.id"), index=True)
    relation: Mapped[str] = mapped_column(String(30))  # proves / requires / targets / practice_for / improves
    origin: Mapped[str] = mapped_column(String(20), default="auto")  # auto（真实事件）/ user（用户手动）
    source_kind: Mapped[str] = mapped_column(String(30), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class CareerPathComparison(Base):
    """知途：多职业路径比较（第十五阶段）。

    directions JSON 中每方向含四类分区：user_facts / job_requirements / ai_inferences /
    questions_to_confirm；绝不编造薪酬、就业概率或前景数字。
    """

    __tablename__ = "career_path_comparisons"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    note: Mapped[str] = mapped_column(String(500), default="")
    directions: Mapped[list] = mapped_column(JSON, default=list)
    comparison: Mapped[dict] = mapped_column(JSON, default=dict)
    data_basis: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class CareerEvalRun(Base):
    """知途：职业规划质量评测记录（第十五阶段，T4 扩展）。

    每次评测记录模型版本、提示词版本、数据集版本与真实结果；
    评价以人工编制的规则判定为主，不依赖模型自评。
    """

    __tablename__ = "career_eval_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str] = mapped_column(String(120), default="")
    prompt_version: Mapped[str] = mapped_column(String(20), default="")
    dataset_version: Mapped[str] = mapped_column(String(20), default="")
    mode: Mapped[str] = mapped_column(String(20), default="offline")  # offline（假客户端）/ live（真实模型）
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    results: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class UsageEvent(Base):
    """管理中心：使用事件采集表（观澜管理中心数据来源之一）。

    - event_type=page_view：前端路由级页面访问（仅登录后工作区页面上报）；
    - event_type=action：后端真实业务操作（注册/登录/出题/评分/解析等成功落库后记录）。
    只记录事件元数据，绝不写入聊天正文、简历内容、密码或验证码。
    自本表上线起采集，之前的历史业务量由各业务表真实数据直接统计。
    """

    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(20))  # page_view / action
    module: Mapped[str] = mapped_column(String(40), index=True)  # 模块标识（如 wenlan）
    name: Mapped[str] = mapped_column(String(60))  # 事件名（如 task_create / page_view）
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # success / error
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)


class AdminAuditLog(Base):
    """管理中心：管理员敏感操作审计（账号状态变更、数据导出等）。"""

    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(60))  # user_status_update / export_stats / ...
    target_type: Mapped[str] = mapped_column(String(40), default="")
    target_id: Mapped[str] = mapped_column(String(60), default="")
    # 非敏感操作详情（如变更前后的状态值、导出的统计范围）
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)


def _rebuild_legacy_users_table(connection) -> None:
    """旧库 users 表为「邮箱 NOT NULL + 唯一」结构，重建为用户名密码结构（幂等）。

    SQLite 无法修改列约束，按官方流程重建 users 表；期间临时关闭外键检查。
    旧账户没有用户名与密码，重建后记录保留（业务外键仍指向有效 id），但无法再登录。
    """
    from sqlalchemy import text

    info = connection.execute(text("PRAGMA table_info(users)")).mappings().all()
    if not info:
        return  # 表不存在：create_all 会按新结构建表
    columns = {row["name"]: row for row in info}
    if "username" in columns and columns["email"]["notnull"] != 1:
        return  # 已是新结构

    raw = connection.connection
    raw.execute("PRAGMA foreign_keys=OFF")
    try:
        raw.execute(
            """
            CREATE TABLE users_new (
                id INTEGER NOT NULL PRIMARY KEY,
                username VARCHAR(40),
                nickname VARCHAR(40) NOT NULL,
                email VARCHAR(120),
                status VARCHAR(20) NOT NULL,
                created_at DATETIME NOT NULL,
                last_login_at DATETIME,
                password_hash VARCHAR(200)
            )
            """
        )
        raw.execute(
            "INSERT INTO users_new (id, username, nickname, email, status, created_at, "
            "last_login_at, password_hash) "
            "SELECT id, NULL, nickname, email, status, created_at, last_login_at, NULL FROM users"
        )
        raw.execute("DROP TABLE users")
        raw.execute("ALTER TABLE users_new RENAME TO users")
        raw.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_users_username ON users(username)")
        raw.execute("DROP TABLE IF EXISTS email_verification_codes")
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.execute("PRAGMA foreign_keys=ON")


def ensure_sqlite_columns() -> None:
    """SQLite 已有表补列（create_all 只建新表、不改旧表）；逐条幂等，已存在则跳过。"""

    from sqlalchemy import text

    from app.database import engine

    statements = (
        ("users", "role", "VARCHAR(20) DEFAULT 'user'"),
        ("llm_call_records", "user_id", "INTEGER"),
        ("career_conversations", "summary", "TEXT"),
        ("career_conversations", "summarized_until_id", "INTEGER"),
        ("job_analyses", "source_job_id", "INTEGER"),
        ("career_plans", "data_basis", "JSON"),
    )
    with engine.connect() as connection:
        _rebuild_legacy_users_table(connection)
        for table, column, ddl in statements:
            try:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                connection.commit()
            except Exception:  # noqa: BLE001 — 列已存在等情况一律跳过
                connection.rollback()
        connection.execute(text("DROP TABLE IF EXISTS email_verification_codes"))
        connection.commit()
