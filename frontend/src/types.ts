export interface HealthResponse {
  status: string
  service: string
  version: string
}

export type InterviewDifficulty = 'basic' | 'intermediate' | 'advanced'

export type InterviewLanguage = 'zh' | 'en'

export interface InterviewConfig {
  position: string
  description: string
  difficulty: InterviewDifficulty
  language: InterviewLanguage
  questionCount: number
}

export type TaskStatus =
  | 'generating_questions'
  | 'ready'
  | 'in_progress'
  | 'generating_report'
  | 'completed'
  | 'failed'

export interface TaskSummary {
  id: number
  position: string
  difficulty: InterviewDifficulty
  language: InterviewLanguage
  question_count: number
  status: TaskStatus
  error_message: string | null
  created_at: string
  updated_at: string
  overall_score: number | null
}

export interface QuestionOut {
  id: number
  order_index: number
  type: 'main' | 'follow_up'
  parent_question_id: number | null
  content: string
  answer: string | null
  /** 问澜结构化题元数据（旧任务为 null） */
  category?: string | null
  dimension?: string | null
  goal?: string | null
  rubric?: string[] | null
  suggested_follow_up?: string | null
}

export interface TaskDetail extends TaskSummary {
  description: string
  questions: QuestionOut[]
  current_question_id: number | null
}

export interface AnswerResponse {
  task_status: TaskStatus
  answered_question_id: number
  next_question: QuestionOut | null
  all_answered: boolean
  report_id: number | null
}

export interface ScoreDimension {
  name: string
  score: number
  evidence: string
  rationale: string
}

export interface ImprovementItem {
  title: string
  detail: string
}

export interface ReportOut {
  id: number
  task_id: number
  overall_score: number
  summary: string
  dimensions: ScoreDimension[]
  strengths: string[]
  improvements: ImprovementItem[]
  model_name: string
  created_at: string
  position: string
  difficulty: InterviewDifficulty
  language: InterviewLanguage
}

export interface AiStatus {
  configured: boolean
  model: string | null
  base_url: string
  message: string
}

// ---------- 问澜：行业职业目录 ----------

export interface CatalogIndustry {
  id: string
  name: string
  occupation_count: number
}

export interface CatalogOccupation {
  id: string
  name: string
  industry_id: string
  aliases: string[]
  core_skills: string[]
  dimensions: string[]
  recommended_type: string
}

export type ExperienceLevel =
  | 'student'
  | 'fresh_graduate'
  | 'junior'
  | 'mid'
  | 'senior'
  | 'expert'
  | 'management'

export type InterviewType =
  | 'screening'
  | 'technical'
  | 'behavioral'
  | 'case'
  | 'leadership'
  | 'comprehensive'

export type FocusArea =
  | 'knowledge'
  | 'project'
  | 'practice'
  | 'analysis'
  | 'communication'
  | 'behavior'
  | 'scenario'
  | 'case_analysis'
  | 'comprehensive'

export interface GenerateQuestionsPayload {
  industryId: string
  occupationId: string
  customOccupation?: string
  experienceLevel: ExperienceLevel
  interviewType: InterviewType
  focusAreas: FocusArea[]
  difficulty: InterviewConfig['difficulty']
  language: InterviewConfig['language']
  questionCount: number
  jobDescription?: string
  knowledgeDocumentId?: number | null
}

// ---------- T2 知识库 ----------

export interface KnowledgeChunk {
  id: number
  chunk_index: number
  content: string
  char_count: number
}

export interface KnowledgeDocument {
  id: number
  title: string
  filename: string
  char_count: number
  status: string
  error_message: string | null
  created_at: string
  chunk_count: number
}

export interface KnowledgeDocumentDetail extends KnowledgeDocument {
  content_text: string
  chunks: KnowledgeChunk[]
}

export interface RetrievalEvidence {
  document_id: number
  document_title: string
  chunk_id: number
  chunk_index: number
  content: string
  score: number
}

export interface KnowledgeSearchResponse {
  query: string
  evidence: RetrievalEvidence[]
}

// ---------- T3 技能图谱 ----------

export interface SkillProfile {
  has_data: boolean
  completed_interviews: number
  average_score: number | null
  latest_score: number | null
  dimension_averages: Record<string, number>
  positions_practiced: string[]
}

export interface TrainingRecommendation {
  available: boolean
  message?: string | null
  weakest_dimension?: string | null
  weakest_score?: number | null
  strongest_dimension?: string | null
  suggested_difficulty?: string | null
  focus_hint?: string | null
  reasons: string[]
  based_on: Record<string, unknown>
}

export interface SkillGraphNode {
  name: string
  score: number
  trend_delta: number
  samples: number
  is_weakest: boolean
  is_strongest: boolean
}

export interface SkillGraph {
  available: boolean
  nodes: SkillGraphNode[]
  score_history: { date: string; position: string; score: number }[]
  average_score: number | null
  latest_score: number | null
  positions_practiced: string[]
}

// ---------- T9 简历匹配 ----------

/** 拖拽解析简历结果：text 为提取的纯文本；AI 失败时 title/position/content 为空并附 parse_error */
export interface ResumeParseResponse {
  filename: string
  text: string
  title: string | null
  position: string | null
  content: ResumeContentData | null
  parse_error: string | null
}

export interface MatchedSkill {
  skill: string
  evidence: string | null
  job_evidence: string | null
}

export interface ResumeMatchResult {
  match_score: number
  matched_skills: MatchedSkill[]
  missing_skills: string[]
  suggestions: string[]
  llm_error: string | null
}

export interface ResumeMatchResponse extends ResumeMatchResult {
  id: number
  model_name: string | null
}

export interface ResumeMatchRecord {
  id: number
  position: string
  match_score: number
  created_at: string
}

export interface ResumeMatchDetail extends ResumeMatchRecord {
  job_description: string
  resume_text: string
  result: ResumeMatchResult
  model_name: string | null
}

// ---------- 澜讯（平台公告） ----------

export interface AnnouncementItem {
  id: string
  type: string
  title: string
  summary: string
  items: string[]
  version: string | null
  /** YYYY-MM-DD；无据可查时为 null，不编造日期 */
  date: string | null
  /** 置顶档案扩展字段：仅置顶公告返回 true */
  pinned?: boolean
  tags?: string[]
  importance?: string | null
  updated_at?: string | null
}

export interface AnnouncementList {
  items: AnnouncementItem[]
}

/** 技术档案章节：段落 / 要点 / 可选表格；正文中的 `代码名词` 由前端等宽渲染 */
export interface TechArchiveSection {
  id: string
  heading: string
  paragraphs: string[]
  bullets: string[]
  table_head: string[] | null
  table_rows: string[][] | null
}

export interface TechArchiveDetail {
  announcement: AnnouncementItem
  sections: TechArchiveSection[]
}

// ---------- 拾贝：官方简历模板指南库（只读公开数据） ----------

export interface ResumeTemplateGuide {
  id: string
  name: string
  industry: string
  audience: string
  structure: string[]
  tips: string[]
  source_url: string
  source_title: string
  accessed_at: string
}

export interface ResumeGallery {
  verified_on: string
  templates: ResumeTemplateGuide[]
}

// ---------- T5 表达分析 / T6 多角色工作流 ----------

export interface AsrProviderInfo {
  label: string
  configured: boolean
  missing_env: string[]
  setup?: string
  installed?: boolean
  model?: string
  model_cached?: boolean
}

export interface AsrStatus {
  configured: boolean
  provider: string | null
  provider_label: string | null
  missing_env: string[]
  preference: string
  providers: Record<string, AsrProviderInfo>
}

export interface ExpressionStatus {
  asr: AsrStatus
  ark: { configured: boolean; model: string | null }
  audio_limits: {
    max_bytes: number
    max_mb: number
    supported_extensions: string[]
    note: string
  }
}

export interface PauseProfile {
  pause_count: number
  longest_pause_ms: number
  total_pause_ms: number
  silence_ratio: number
}

export interface AudioMetrics {
  available: boolean
  unavailable_reason: string | null
  duration_ms: number | null
  pause: PauseProfile | null
}

export interface SpeechMetrics {
  available: boolean
  unavailable_reason: string | null
  char_count: number
  speech_rate_cpm: number | null
  filler_words: Record<string, number>
  filler_total: number
}

export interface ExpressionTranscribeResponse {
  id: number
  source: string
  transcript: string | null
  asr_status: 'ok' | 'failed' | 'not_configured'
  asr_provider: string | null
  asr_error: string | null
  audio: AudioMetrics
  speech: SpeechMetrics
}

export interface WorkflowStep {
  role: string
  title: string
  status: 'completed' | 'failed' | 'skipped'
  output: Record<string, unknown> | null
  error: string | null
  elapsed_ms: number
  attempts: number
}

export interface ExpressionWorkflow {
  status: 'completed' | 'partial' | 'failed'
  steps: WorkflowStep[]
  model_name: string | null
}

// ---------- 知岗：JD 解析 ----------

/** 带原文证据的结论条目：is_inferred=true 表示证据无法在 JD 原文定位（模型推断）。 */
export interface TrackedItem {
  text: string
  evidence: string | null
  is_inferred: boolean
}

export interface JobAnalysisResult {
  position_name: string
  industry: string
  responsibilities: TrackedItem[]
  required_skills: TrackedItem[]
  preferred_skills: TrackedItem[]
  experience_requirement: TrackedItem
  education_requirement: TrackedItem
  tools: TrackedItem[]
  capability_dimensions: string[]
  interview_directions: string[]
  keywords: string[]
}

export interface JobAnalysisSummary {
  id: number
  title: string
  version_no: number
  status: 'ready' | 'failed'
  created_at: string
  jd_preview: string
  source_job_id: number | null
}

export interface JobAnalysisDetail extends JobAnalysisSummary {
  jd_text: string
  result: JobAnalysisResult | null
  model_name: string | null
  error_message: string | null
  user_edited: boolean
}

export interface JobUploadResponse {
  filename: string
  text: string
  char_count: number
}

export interface JobMatchedSkill {
  skill: string
  evidence: string | null
  job_evidence: string | null
  supporting_experiences?: string[]
}

export interface JobMissingSkill {
  skill: string
  job_evidence: string | null
  suggestion: string
}

export interface JobResumeMatchResponse {
  job_analysis_id: number
  resume_id: number
  resume_title: string
  matched_skills: JobMatchedSkill[]
  missing_skills: JobMissingSkill[]
  uncertain_items: { skill: string; reason: string }[]
  suggestions: string[]
  match_score: number
  score_note: string
  model_name: string | null
  llm_error: string | null
}

// ---------- 知潮：真实岗位资料库 ----------

/** 库内真实岗位：全部字段来自可核验来源，绝不编造。 */
export interface JobPosition {
  id: number
  company: string
  company_url: string | null
  title: string
  industry_id: string | null
  industry_name: string | null
  occupation_id: string | null
  occupation_name: string | null
  location: string
  level: string
  /** 来源未提供发布时间时为 null，前端如实显示 published_note */
  published_at: string | null
  published_note: string
  source_updated_at: string | null
  source_url: string | null
  source_type: 'official_seed' | 'user_import' | 'manual'
  display_permission: 'summary_only' | 'full_text'
  responsibilities_summary: string
  required_skills_summary: string
  preferred_skills_summary: string
  experience_summary: string
  /** unconfirmed = 招聘状态未确认（不能默认视为正在招聘） */
  hiring_status: 'unconfirmed' | 'open' | 'closed'
  link_status: 'ok' | 'stale' | 'dead' | 'no_link' | 'unverified'
  last_verified_at: string | null
  verified_note: string | null
  /** 超过核验周期未核验 → 可能已过期 */
  stale_hint: boolean
  is_favorited: boolean
  imported_by: number | null
  created_at: string
}

export interface JobPositionChange {
  id: number
  change_type: 'created' | 'updated' | 'verified' | 'stale'
  note: string
  created_at: string
}

export interface JobPositionListResponse {
  items: JobPosition[]
  total: number
  limit: number
  offset: number
}

export interface JobPositionDetail extends JobPosition {
  changes: JobPositionChange[]
}

export interface JobPositionImportPayload {
  company: string
  title: string
  location?: string
  level?: string
  industry_id?: string
  occupation_id?: string
  source_url?: string
  responsibilities_summary?: string
  required_skills_summary?: string
  preferred_skills_summary?: string
  experience_summary?: string
  jd_full_text?: string
  hiring_status?: 'unconfirmed' | 'open' | 'closed'
  display_permission?: 'summary_only' | 'full_text'
}

export interface JobPositionImportResponse {
  position: JobPosition
  is_duplicate: boolean
}

/** 库内岗位送入知岗解析的结果。 */
export interface JobAnalyzeFromPositionResponse {
  job_analysis_id: number
  reused: boolean
  position_name: string
}

/** 知潮岗位加入知途规划的返回：新计划与所依据的岗位解析记录。 */
export interface JobCareerPlanResponse {
  plan_id: number
  plan_title: string
  focus_role: string | null
  job_analysis_id: number
  reused_analysis: boolean
}


// ---------- 履历成章：模板参考来源与岗位适配诊断 ----------

export interface ResumeTemplateSource {
  name: string
  url: string
  purpose: string
  /** 查阅日期（YYYY-MM-DD），真实可追溯 */
  consulted_on: string
}

export interface ResumeKeywordGap {
  skill: string
  job_evidence: string | null
}

export interface ResumeWeakPoint {
  /** 逐字摘自简历原文的表达 */
  text: string
  reason: string
  /** 追问：帮助用户补充真实依据 */
  question: string
}

export interface ResumeOptimizeForJobResponse {
  keyword_gaps: ResumeKeywordGap[]
  weak_points: ResumeWeakPoint[]
  restructure_advice: string
  position: string
  model_name: string | null
}

// ---------- 履历成章：结构化简历 ----------

export interface ResumeBasicsData {
  name?: string
  phone?: string
  email?: string
  location?: string
  links?: string
  summary?: string
}

export interface EducationEntryData {
  school?: string
  degree?: string
  major?: string
  start?: string
  end?: string
  details?: string
}

export interface ExperienceEntryData {
  name?: string
  role?: string
  start?: string
  end?: string
  link?: string
  highlights?: string[]
}

export interface SkillEntryData {
  name?: string
  level?: string
  detail?: string
}

export interface CertificateEntryData {
  name?: string
  issuer?: string
  date?: string
}

export interface AwardEntryData {
  name?: string
  issuer?: string
  date?: string
  detail?: string
}

export interface ResumeContentData {
  basics?: ResumeBasicsData
  education?: EducationEntryData[]
  work?: ExperienceEntryData[]
  projects?: ExperienceEntryData[]
  skills?: SkillEntryData[]
  certificates?: CertificateEntryData[]
  awards?: AwardEntryData[]
}

export interface ResumeTemplate {
  id: string
  name: string
  description: string
  section_order: string[]
  accent: string
}

export interface ResumeVersionSummary {
  version_no: number
  title: string
  template_id: string
  note: string
  created_at: string
}

export interface ResumeSummary {
  id: number
  title: string
  template_id: string
  current_version_no: number
  created_at: string
  updated_at: string
}

export interface ResumeDetail extends ResumeSummary {
  content: ResumeContentData
  versions: ResumeVersionSummary[]
}

export interface ResumeVersionDetail extends ResumeVersionSummary {
  content: ResumeContentData
}

export interface ResumePolishResponse {
  polished: string
  notes: string
  model_name: string | null
}

export interface ExpressionWorkflowResponse {
  id: number
  asr_status: string
  transcript: string | null
  metrics: { audio: AudioMetrics | null; speech: SpeechMetrics }
  workflow: ExpressionWorkflow
  model_name: string | null
}

export interface ExpressionRecord {
  id: number
  source: string
  filename: string | null
  asr_status: string
  asr_provider: string | null
  asr_error: string | null
  has_transcript: boolean
  has_workflow: boolean
  created_at: string
}

export interface ExpressionDetail extends ExpressionRecord {
  transcript: string | null
  audio_duration_ms: number | null
  metrics: { audio: AudioMetrics | null; speech: SpeechMetrics }
  workflow: ExpressionWorkflow | null
  model_name: string | null
}

// ---------- 认证：用户名密码登录 ----------

export interface AuthUser {
  id: number
  username: string
  nickname: string
  status: string
  created_at: string
  last_login_at: string | null
}

export interface AuthMeResponse {
  authenticated: boolean
  user: AuthUser | null
}

// ---------- 星图对照（观己 × 知岗差距分析） ----------

/** current 为服务端回填的真实能力值（无数据为 0，见 has_data）；target 来自 AI 对岗位要求的判断。 */
export interface GapDimension {
  name: string
  current: number
  target: number
  gap_note: string
}

export interface GapAnalysisResponse {
  position: string
  has_data: boolean
  completed_interviews: number
  average_score: number | null
  dimensions: GapDimension[]
  overall_note: string
  model_name: string | null
}

// ---------- 澜记周报 ----------

export interface WeeklyReportDay {
  date: string
  count: number
  kinds: string[]
}

export interface WeeklyReport {
  week_start: string
  week_end: string
  days: WeeklyReportDay[]
  totals: Record<string, number>
  interviews_completed: number
  average_score: number | null
  active_days: number
  streak_current: number
  ai_note: string | null
}

// ---------- 回澜：错题本（SM-2 间隔重复） ----------

export interface MistakeCardOut {
  id: number
  question_id: number
  position: string
  question_content: string
  category: string | null
  dimension: string | null
  goal: string | null
  rubric: string[] | null
  my_answer: string
  repetitions: number
  ease_factor: number
  interval_days: number
  due_at: string
  last_grade: number | null
  last_reviewed_at: string | null
  review_count: number
  created_at: string
  is_due: boolean
}

export interface MistakeListResponse {
  total: number
  due_count: number
  cards: MistakeCardOut[]
}

// ---------- 度衡：限时模拟挑战 ----------

export interface ChallengeQuestion {
  order_index: number
  content: string
  category: string
  dimension: string
  rubric: string[]
}

export interface ChallengeAnswerEntry {
  order_index: number
  answer: string
}

export interface ChallengeOut {
  id: number
  position: string
  difficulty: string
  language: string
  question_count: number
  duration_minutes: number
  status: 'created' | 'in_progress' | 'evaluating' | 'completed' | 'failed'
  questions: ChallengeQuestion[]
  answers: ChallengeAnswerEntry[] | null
  started_at: string | null
  deadline_at: string | null
  submitted_at: string | null
  overtime: boolean
  overall_score: number | null
  result: {
    summary: string
    dimensions: ScoreDimension[]
    strengths: string[]
    improvements: ImprovementItem[]
    overall_score: number
  } | null
  model_name: string | null
  error_message: string | null
  created_at: string
  remaining_seconds: number | null
}

// ---------- 成长热力图 ----------

export interface GrowthHeatmapDay {
  date: string
  count: number
  kinds: string[]
}

export interface GrowthHeatmap {
  year: number
  days: GrowthHeatmapDay[]
  streak: { current: number; longest: number }
}

// ---------- 知途：AI 职业顾问「小鸥」 ----------

export interface CareerConversation {
  id: number
  title: string
  message_count: number
  created_at: string
  updated_at: string
}

export interface CareerMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface CareerConversationDetail extends CareerConversation {
  messages: CareerMessage[]
}

export interface CareerMessagePair {
  user_message: CareerMessage
  assistant_message: CareerMessage
  model_name: string | null
}

/** 事实来源三态：用户明说 / AI 归纳（待确认）/ AI 推断 */
export type CareerFactSourceType = 'user_stated' | 'ai_generalized' | 'ai_inferred'

export interface CareerProfileFact {
  id: number
  category: string
  content: string
  source_type: CareerFactSourceType | string
  source_message_id: number | null
  confidence: string | null
  quote: string | null
  confirmed: boolean
  created_at: string
  updated_at: string
}

export interface CareerProfileDetail {
  summary: string | null
  facts: CareerProfileFact[]
  confirmed_count: number
  pending_count: number
}

// ---------- 知途：结构化分析 ----------

export interface CareerAnalysisSituation {
  summary: string
  known: string[]
  uncertain: string[]
  suggested_focus: string[]
}

export interface CareerDirection {
  name: string
  fit: string
  relation: string
  requirements: string[]
  evidence: string[]
  unknowns: string[]
  conditions: string[]
  next_steps: string[]
}

export interface CareerDirectionsResult {
  directions: CareerDirection[]
  note: string
}

export interface CareerGapAnalysis {
  target_role: string
  have: string[]
  required: string[]
  proven: string[]
  missing: string[]
  buildable: string[]
  practice_tasks: string[]
  notes: string
  evidence_digest?: string
}

// ---------- 知途：行动计划 ----------

export interface CareerPlanAction {
  id: number
  plan_id: number
  phase: '7d' | '30d' | '90d' | string
  goal: string
  steps: string
  due_at: string | null
  status: 'pending' | 'done' | 'skipped' | string
  review: string | null
  related_goal: string | null
  position: number
  completed_at: string | null
}

export interface CareerPlan {
  id: number
  title: string
  situation: string
  focus_role: string | null
  status: string
  version_no: number
  conversation_id: number | null
  created_at: string
  updated_at: string
  actions: CareerPlanAction[]
}

export interface CareerPlanSummary {
  id: number
  title: string
  focus_role: string | null
  status: string
  version_no: number
  created_at: string
  updated_at: string
  pending_count: number
  done_count: number
  skipped_count: number
}

// ---------- 知途：联动工作流 ----------

export interface CareerWorkflowStep {
  key: string
  title: string
  status: string
  detail: string | null
}

export interface CareerWorkflowRun {
  id: number
  kind: string
  status: string
  params: Record<string, unknown>
  steps: CareerWorkflowStep[]
  result: Record<string, unknown> | null
  error_message: string | null
  created_at: string
  updated_at: string
}

// ---------- 知途：SSE 流式事件 ----------

export interface CareerStreamMeta {
  user_message: CareerMessage
  regenerated: boolean
  removed_previous: boolean
}

export interface CareerStreamDone {
  assistant_message: CareerMessage
  title: string
  model_name: string | null
}

export interface CareerStreamError {
  message: string
  status: number
  partial_saved: boolean
}

export interface CareerStreamEnd {
  facts_added: number
  summary_updated: boolean
}

export interface CareerStreamHandlers {
  onMeta?: (data: CareerStreamMeta) => void
  onDelta?: (text: string) => void
  onDone?: (data: CareerStreamDone) => void
  onError?: (data: CareerStreamError) => void
  onEnd?: (data: CareerStreamEnd) => void
}

// ---------- 知途：能力图谱（第十五阶段） ----------

/** 四态：已证实 / 用户自述 / AI 推断 / 尚待验证 */
export type SkillNodeStatus = 'verified' | 'user_stated' | 'ai_inferred' | 'pending'

export interface CareerSkillNode {
  id: number
  entity_type: string
  name: string
  status: SkillNodeStatus | string
  confidence: string | null
  source_kind: string
  source_ref: Record<string, unknown>
  quote: string | null
  note: string | null
  updated_at: string
}

export interface CareerSkillEdge {
  id: number
  from_node_id: number
  to_node_id: number
  from_name: string
  to_name: string
  relation: string
  origin: string
  source_kind: string
}

export interface CareerGraph {
  nodes: CareerSkillNode[]
  edges: CareerSkillEdge[]
  status_counts: Record<string, number>
}

// ---------- 知途：多职业路径比较 ----------

export interface PathSkillRequirement {
  requirement: string
  source: string
}

export interface PathDirection {
  name: string
  relevance: string
  skill_requirements: PathSkillRequirement[]
  evidence_gaps: string[]
  interests_constraints: string[]
  learning_cost: string
  verification_actions: string[]
  source: string
}

export interface CareerPathComparison {
  id: number
  title: string
  note: string
  directions: PathDirection[]
  comparison: {
    common?: string[]
    diverge?: string[]
    recommendation?: string
  }
  data_basis: {
    generated_at?: string
    knowledge_sources?: { title: string; source_kind: string; snippet?: string }[]
    job_sources?: { title: string; company?: string; source_url?: string | null }[]
    disclaimer?: string
  }
  created_at: string
}

// ---------- 知途：RAG 职业知识检索 ----------

export interface RetrievalHit {
  chunk_id: number
  title: string
  content: string
  source_kind: string
  source_id: string
  source_url: string | null
  scope: string
  industry_id: string | null
  occupation_id: string | null
  experience_level: string | null
  published_at: string | null
  last_verified_at: string | null
  stale: boolean
  stale_note: string | null
  fused_score: number
  rerank_boost: number
  final_score: number
}

export interface RetrievalOutcome {
  found: boolean
  message?: string
  results?: RetrievalHit[]
  retrieval_meta?: Record<string, unknown>
  disclaimer?: string
}

export interface RetrievalStats {
  total: number
  global: number
  user: number
  by_source_kind?: Record<string, number>
}

// ---------- 知途：规划版本与复盘 ----------

export interface PlanRevisionSummary {
  version_no: number
  change_note: string
  has_review: boolean
  created_at: string
}

export interface PlanRevisionDetail extends PlanRevisionSummary {
  snapshot: Record<string, unknown>
}

export interface PlanReviewAdjustment {
  phase: string
  goal: string
  steps?: string
  due_in_days?: number
  reason?: string
}

export interface PlanReviewResult {
  review_summary: string
  achievements: string[]
  blocked: string[]
  adjustments: PlanReviewAdjustment[]
  next_focus: string[]
  real_stats: Record<string, number>
}

// ---------- 知途：记忆透明化 / 成长反馈 / 评测 ----------

export interface MemoryUsage {
  conversation_id: number
  layers: {
    confirmed_facts: { id: number; category: string; content: string }[]
    related_history: { conversation_title: string; content: string; score: number }[]
    session_summary: string | null
    recent_window: number
  }
  assembled_context_preview: string
  note: string
}

export interface GrowthFeedback {
  available: boolean
  message: string | null
  interview_scores: { date: string; position: string; score: number }[]
  challenge_count: number
  completed_actions: { date: string | null; goal: string }[]
  heatmap: { total_active_days: number | null; current_streak: number | null }
  disclaimer: string
}

export interface CareerEvalRunRecord {
  id: number
  model: string
  prompt_version: string
  dataset_version: string
  mode: string
  metrics: Record<string, unknown>
  created_at: string
}
