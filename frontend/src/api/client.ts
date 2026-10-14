import type {
  AiStatus,
  AnswerResponse,
  AuthMeResponse,
  CatalogIndustry,
  CatalogOccupation,
  ChallengeOut,
  ExpressionDetail,
  ExpressionRecord,
  ExpressionStatus,
  ExpressionTranscribeResponse,
  ExpressionWorkflowResponse,
  GapAnalysisResponse,
  GenerateQuestionsPayload,
  GrowthHeatmap,
  HealthResponse,
  InterviewConfig,
  JobAnalysisDetail,
  JobAnalysisSummary,
  JobResumeMatchResponse,
  JobUploadResponse,
  KnowledgeDocument,
  KnowledgeDocumentDetail,
  KnowledgeSearchResponse,
  AnnouncementList,
  TechArchiveDetail,
  MistakeCardOut,
  MistakeListResponse,
  ReportOut,
  ResumeContentData,
  ResumeDetail,
  ResumeParseResponse,
  ResumePolishResponse,
  ResumeSummary,
  ResumeTemplate,
  ResumeVersionDetail,
  ResumeVersionSummary,
  ResumeMatchDetail,
  ResumeMatchRecord,
  ResumeMatchResponse,
  SkillGraph,
  SkillProfile,
  TaskDetail,
  TaskSummary,
  TrainingRecommendation,
  WeeklyReport,
  CareerConversation,
  CareerConversationDetail,
  CareerMessagePair,
  CareerProfileDetail,
  CareerProfileFact,
  CareerGraph,
  CareerPathComparison,
  MemoryUsage,
  PlanRevisionSummary,
  PlanRevisionDetail,
  PlanReviewAdjustment,
  PlanReviewResult,
  GrowthFeedback,
  CareerEvalRunRecord,
  RetrievalOutcome,
  RetrievalStats,
  CareerAnalysisSituation,
  CareerDirectionsResult,
  CareerPlan,
  CareerPlanSummary,
  CareerStreamHandlers,
  CareerWorkflowRun,
  JobAnalyzeFromPositionResponse,
  JobCareerPlanResponse,
  JobPosition,
  JobPositionDetail,
  JobPositionImportPayload,
  JobPositionImportResponse,
  JobPositionListResponse,
  ResumeOptimizeForJobResponse,
  ResumeTemplateSource,
} from '../types'

const API_BASE = '/api/v1'

export type ExpressionStepEventName = 'step_started' | 'step_finished'

export interface ExpressionStepEvent {
  role: string
  title: string
  status?: 'completed' | 'failed' | 'skipped'
  error?: string | null
  elapsed_ms?: number
  attempts?: number
}

export type ExpressionStepListener = (
  event: ExpressionStepEventName,
  data: ExpressionStepEvent,
) => void

export class ApiError extends Error {
  readonly status: number | undefined

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<TResponse>(path: string, init?: RequestInit): Promise<TResponse> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { Accept: 'application/json', ...init?.headers },
      ...init,
    })
  } catch (err) {
    // 调用方主动取消（如组件卸载中止请求）时原样抛出，避免被误报为网络错误
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError('网络请求失败：无法连接后端服务')
  }

  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status)
  }

  if (response.status === 204) {
    return undefined as TResponse
  }

  return (await response.json()) as TResponse
}

async function parseErrorDetail(response: Response): Promise<string> {
  let detail = `请求失败（HTTP ${response.status}）`
  try {
    const body: unknown = await response.json()
    if (typeof body === 'object' && body !== null && 'detail' in body) {
      const raw = (body as { detail: unknown }).detail
      if (typeof raw === 'string') {
        detail = raw
      } else if (Array.isArray(raw)) {
        detail = raw
          .map((item) =>
            typeof item === 'object' && item !== null && 'msg' in item
              ? String((item as { msg: unknown }).msg)
              : String(item),
          )
          .join('；')
      }
    }
  } catch {
    // 响应体不是 JSON 时保留默认错误信息
  }
  return detail
}

function post<TResponse>(path: string, body?: unknown): Promise<TResponse> {
  return request<TResponse>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })
}

function put<TResponse>(path: string, body?: unknown): Promise<TResponse> {
  return request<TResponse>(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })
}

/** 文件下载：返回二进制与解析后的文件名（支持 UTF-8 Content-Disposition）。 */
async function requestBlob(path: string): Promise<{ blob: Blob; filename: string }> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, { headers: { Accept: '*/*' } })
  } catch {
    throw new ApiError('网络请求失败：无法连接后端服务')
  }
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status)
  }
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  const asciiMatch = disposition.match(/filename="([^"]+)"/i)
  let filename = 'resume'
  if (utf8Match) {
    try {
      filename = decodeURIComponent(utf8Match[1])
    } catch {
      filename = utf8Match[1]
    }
  } else if (asciiMatch) {
    filename = asciiMatch[1]
  }
  return { blob: await response.blob(), filename }
}

/**
 * 知途 SSE 流式对话：POST 一条用户消息并逐块接收小鸥回复。
 *
 * 事件协议（与后端 _stream_reply 对齐）：meta → delta* → done → end；
 * 失败时发 error 事件（partial_saved 表示已生成的部分内容是否已落库）。
 * 调用方通过 signal 停止生成（AbortError 会原样抛出）。
 */
export async function streamCareerChat(
  conversationId: number,
  mode: 'stream' | 'regenerate',
  content: string | null,
  handlers: CareerStreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  let response: Response
  try {
    response = await fetch(
      `${API_BASE}/career-guide/conversations/${conversationId}/${mode}`,
      {
        method: 'POST',
        headers: {
          Accept: 'text/event-stream',
          ...(content != null ? { 'Content-Type': 'application/json' } : {}),
        },
        body: content != null ? JSON.stringify({ content }) : undefined,
        signal,
      },
    )
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError('网络请求失败：无法连接后端服务')
  }

  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status)
  }
  if (!response.body) {
    throw new ApiError('当前浏览器不支持流式响应，请更换浏览器后重试')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const dispatch = (rawEvent: string, rawData: string) => {
    let payload: unknown
    try {
      payload = JSON.parse(rawData)
    } catch {
      return
    }
    if (payload === null || typeof payload !== 'object') return
    const data = payload as Record<string, unknown>
    if (rawEvent === 'meta' && handlers.onMeta) {
      handlers.onMeta(data as never)
    } else if (rawEvent === 'delta' && typeof data.text === 'string' && handlers.onDelta) {
      handlers.onDelta(data.text)
    } else if (rawEvent === 'done' && handlers.onDone) {
      handlers.onDone(data as never)
    } else if (rawEvent === 'error' && handlers.onError) {
      handlers.onError(data as never)
    } else if (rawEvent === 'end' && handlers.onEnd) {
      handlers.onEnd(data as never)
    }
  }

  const processBlock = (block: string) => {
    let eventName = 'message'
    const dataLines: string[] = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart())
      }
    }
    if (dataLines.length > 0) {
      dispatch(eventName, dataLines.join('\n'))
    }
  }

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let separator = buffer.indexOf('\n\n')
      while (separator >= 0) {
        processBlock(buffer.slice(0, separator))
        buffer = buffer.slice(separator + 2)
        separator = buffer.indexOf('\n\n')
      }
    }
    if (buffer.trim()) processBlock(buffer)
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError('流式连接中断，请重试')
  }
}

export const api = {
  health(): Promise<HealthResponse> {
    return request<HealthResponse>('/health')
  },

  aiStatus(): Promise<AiStatus> {
    return request<AiStatus>('/ai/status')
  },

  createInterview(config: InterviewConfig & { knowledgeDocumentId?: number | null }): Promise<TaskDetail> {
    return post<TaskDetail>('/interviews', {
      position: config.position,
      description: config.description,
      difficulty: config.difficulty,
      language: config.language,
      question_count: config.questionCount,
      ...(config.knowledgeDocumentId != null
        ? { knowledge_document_id: config.knowledgeDocumentId }
        : {}),
    })
  },

  // ---------- 问澜：行业职业目录与题集生成 ----------

  listIndustries(): Promise<CatalogIndustry[]> {
    return request<{ items: CatalogIndustry[] }>('/catalog/industries').then((r) => r.items)
  },

  listOccupations(industryId: string, q?: string): Promise<CatalogOccupation[]> {
    const params = new URLSearchParams({ industry_id: industryId })
    if (q) params.set('q', q)
    return request<{ items: CatalogOccupation[] }>(`/catalog/occupations?${params}`).then(
      (r) => r.items,
    )
  },

  generateQuestions(payload: GenerateQuestionsPayload): Promise<TaskDetail> {
    return post<TaskDetail>('/interviews/generate-questions', {
      industry_id: payload.industryId,
      occupation_id: payload.occupationId,
      ...(payload.occupationId === 'custom' && payload.customOccupation
        ? { custom_occupation: payload.customOccupation }
        : {}),
      experience_level: payload.experienceLevel,
      interview_type: payload.interviewType,
      focus_areas: payload.focusAreas,
      difficulty: payload.difficulty,
      language: payload.language,
      question_count: payload.questionCount,
      ...(payload.jobDescription ? { job_description: payload.jobDescription } : {}),
      ...(payload.knowledgeDocumentId != null
        ? { knowledge_document_id: payload.knowledgeDocumentId }
        : {}),
    })
  },

  listInterviews(limit = 50): Promise<TaskSummary[]> {
    return request<TaskSummary[]>(`/interviews?limit=${limit}`)
  },

  getInterview(taskId: number): Promise<TaskDetail> {
    return request<TaskDetail>(`/interviews/${taskId}`)
  },

  submitAnswer(taskId: number, questionId: number, content: string): Promise<AnswerResponse> {
    return post<AnswerResponse>(`/interviews/${taskId}/answers`, {
      question_id: questionId,
      content,
    })
  },

  resolveNext(taskId: number): Promise<AnswerResponse> {
    return post<AnswerResponse>(`/interviews/${taskId}/next`)
  },

  finishInterview(
    taskId: number,
  ): Promise<{ task_id: number; status: string; report_id: number | null }> {
    return post(`/interviews/${taskId}/finish`)
  },

  getReport(taskId: number): Promise<ReportOut> {
    return request<ReportOut>(`/interviews/${taskId}/report`)
  },

  // ---------- T2 知识库 ----------

  listKnowledgeDocuments(): Promise<KnowledgeDocument[]> {
    return request<KnowledgeDocument[]>('/knowledge/documents')
  },

  getKnowledgeDocument(id: number): Promise<KnowledgeDocumentDetail> {
    return request<KnowledgeDocumentDetail>(`/knowledge/documents/${id}`)
  },

  uploadKnowledgeDocument(file: File): Promise<KnowledgeDocument> {
    const form = new FormData()
    form.append('file', file)
    return request<KnowledgeDocument>('/knowledge/documents', {
      method: 'POST',
      body: form,
    })
  },

  deleteKnowledgeDocument(id: number): Promise<void> {
    return request<void>(`/knowledge/documents/${id}`, { method: 'DELETE' })
  },

  searchKnowledge(query: string): Promise<KnowledgeSearchResponse> {
    return request<KnowledgeSearchResponse>(
      `/knowledge/search?q=${encodeURIComponent(query)}`,
    )
  },

  // ---------- T3 技能图谱 ----------

  getSkillProfile(): Promise<SkillProfile> {
    return request<SkillProfile>('/skills/profile')
  },

  getSkillGraph(): Promise<SkillGraph> {
    return request<SkillGraph>('/skills/graph')
  },

  getTrainingRecommendation(): Promise<TrainingRecommendation> {
    return request<TrainingRecommendation>('/skills/recommendation')
  },

  // ---------- T9 简历匹配 ----------

  /** 拖拽解析简历文件：安全提取文本 + AI 忠实转录（不落库） */
  parseResumeFile(file: File, jdText?: string): Promise<ResumeParseResponse> {
    const form = new FormData()
    form.append('file', file)
    if (jdText && jdText.trim()) form.append('jd_text', jdText.trim())
    return request<ResumeParseResponse>('/resumes/parse', { method: 'POST', body: form })
  },

  matchResume(payload: {
    position: string
    jobDescription: string
    resumeText: string
  }): Promise<ResumeMatchResponse> {
    return post<ResumeMatchResponse>('/matching/resume', {
      position: payload.position,
      job_description: payload.jobDescription,
      resume_text: payload.resumeText,
    })
  },

  listMatchRecords(): Promise<ResumeMatchRecord[]> {
    return request<ResumeMatchRecord[]>('/matching/records')
  },

  getMatchRecord(id: number): Promise<ResumeMatchDetail> {
    return request<ResumeMatchDetail>(`/matching/records/${id}`)
  },

  // ---------- T5 表达分析 / T6 多角色工作流 ----------

  getExpressionStatus(): Promise<ExpressionStatus> {
    return request<ExpressionStatus>('/expression/status')
  },

  transcribeAudio(file: File): Promise<ExpressionTranscribeResponse> {
    const form = new FormData()
    form.append('file', file)
    return request<ExpressionTranscribeResponse>('/expression/transcribe', {
      method: 'POST',
      body: form,
    })
  },

  analyzeExpression(payload: { text?: string; analysisId?: number }): Promise<ExpressionWorkflowResponse> {
    return post<ExpressionWorkflowResponse>('/expression/analyze', {
      ...(payload.text != null ? { text: payload.text } : {}),
      ...(payload.analysisId != null ? { analysis_id: payload.analysisId } : {}),
    })
  },

  /** T8：SSE 流式复盘。逐步回调 step_started / step_finished，最终返回完整结果。 */
  async analyzeExpressionStream(
    payload: { text?: string; analysisId?: number },
    onStep: ExpressionStepListener,
  ): Promise<ExpressionWorkflowResponse> {
    let response: Response
    try {
      response = await fetch(`${API_BASE}/expression/analyze/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({
          ...(payload.text != null ? { text: payload.text } : {}),
          ...(payload.analysisId != null ? { analysis_id: payload.analysisId } : {}),
        }),
      })
    } catch {
      throw new ApiError('网络请求失败：无法连接后端服务')
    }
    if (!response.ok) {
      throw new ApiError(await parseErrorDetail(response), response.status)
    }
    if (!response.body) {
      throw new ApiError('当前浏览器不支持流式响应')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let result: ExpressionWorkflowResponse | null = null
    let streamError: string | null = null

    const handleFrame = (frame: string) => {
      const lines = frame.split('\n')
      const eventName = lines.find((line) => line.startsWith('event:'))?.slice(6).trim()
      const dataLine = lines.find((line) => line.startsWith('data:'))?.slice(5).trim()
      if (!eventName || !dataLine) return
      let data: unknown
      try {
        data = JSON.parse(dataLine)
      } catch {
        return
      }
      if (eventName === 'step_started' || eventName === 'step_finished') {
        onStep(eventName, data as ExpressionStepEvent)
      } else if (eventName === 'result') {
        result = data as ExpressionWorkflowResponse
      } else if (eventName === 'error') {
        streamError = String((data as { detail?: unknown }).detail ?? '复盘流程出现异常')
      }
    }

    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let separator = buffer.indexOf('\n\n')
      while (separator >= 0) {
        handleFrame(buffer.slice(0, separator))
        buffer = buffer.slice(separator + 2)
        separator = buffer.indexOf('\n\n')
      }
    }
    if (streamError) throw new ApiError(streamError, response.status)
    if (!result) throw new ApiError('复盘流式响应中断，请重试')
    return result
  },

  listExpressionRecords(limit = 20): Promise<ExpressionRecord[]> {
    return request<ExpressionRecord[]>(`/expression/records?limit=${limit}`)
  },

  getExpressionRecord(id: number): Promise<ExpressionDetail> {
    return request<ExpressionDetail>(`/expression/records/${id}`)
  },

  deleteExpressionRecord(id: number): Promise<void> {
    return request<void>(`/expression/records/${id}`, { method: 'DELETE' })
  },

  // ---------- 澜讯（平台公告） ----------
  listAnnouncements(): Promise<AnnouncementList> {
    return request<AnnouncementList>('/announcements')
  },

  /** 置顶技术档案详情：公告元数据 + 12 章节完整正文 */
  getTechArchive(): Promise<TechArchiveDetail> {
    return request<TechArchiveDetail>('/announcements/project-tech-archive')
  },

  // ---------- 认证：用户名密码注册/登录 ----------
  // 会话令牌由后端经 HttpOnly Cookie 下发，浏览器同源请求自动携带，前端不经手令牌
  authMe(): Promise<AuthMeResponse> {
    return request<AuthMeResponse>('/auth/me')
  },

  register(payload: { username: string; password: string; nickname: string }): Promise<AuthMeResponse> {
    return post<AuthMeResponse>('/auth/register', {
      username: payload.username,
      password: payload.password,
      nickname: payload.nickname,
    })
  },

  login(payload: { username: string; password: string }): Promise<AuthMeResponse> {
    return post<AuthMeResponse>('/auth/login', {
      username: payload.username,
      password: payload.password,
    })
  },

  logout(): Promise<{ ok: boolean }> {
    return post<{ ok: boolean }>('/auth/logout')
  },

  // ---------- 知岗：JD 解析与联动 ----------
  analyzeJob(jdText: string): Promise<JobAnalysisDetail> {
    return post<JobAnalysisDetail>('/jobs/analyze', { jd_text: jdText })
  },

  uploadJobFile(file: File): Promise<JobUploadResponse> {
    const form = new FormData()
    form.append('file', file)
    return request<JobUploadResponse>('/jobs/upload', { method: 'POST', body: form })
  },

  listJobAnalyses(): Promise<JobAnalysisSummary[]> {
    return request<JobAnalysisSummary[]>('/jobs/analyses')
  },

  getJobAnalysis(id: number): Promise<JobAnalysisDetail> {
    return request<JobAnalysisDetail>(`/jobs/analyses/${id}`)
  },

  deleteJobAnalysis(id: number): Promise<void> {
    return request<void>(`/jobs/analyses/${id}`, { method: 'DELETE' })
  },

  /** 依据知岗分析结果生成面试题（复用问澜题集流程）；position 可覆盖岗位名。 */
  createInterviewFromJob(
    analysisId: number,
    payload?: { position?: string; difficulty?: string; questionCount?: number },
  ): Promise<TaskDetail> {
    return post<TaskDetail>(`/jobs/analyses/${analysisId}/interview-task`, {
      ...(payload?.position ? { position: payload.position } : {}),
      ...(payload?.difficulty ? { difficulty: payload.difficulty } : {}),
      ...(payload?.questionCount != null ? { question_count: payload.questionCount } : {}),
    })
  },

  /** 知岗分析 × 履历成章简历的结构化匹配（合契联动）。 */
  matchJobWithResume(analysisId: number, resumeId: number): Promise<JobResumeMatchResponse> {
    return post<JobResumeMatchResponse>(`/jobs/analyses/${analysisId}/match`, {
      resume_id: resumeId,
    })
  },

  // ---------- 履历成章：简历模板 / 编辑 / 版本 / 导出 ----------
  listResumeTemplates(): Promise<ResumeTemplate[]> {
    return request<ResumeTemplate[]>('/resumes/templates')
  },

  listResumes(): Promise<ResumeSummary[]> {
    return request<ResumeSummary[]>('/resumes')
  },

  createResume(payload: {
    title: string
    templateId?: string
    content: ResumeContentData
  }): Promise<ResumeDetail> {
    return post<ResumeDetail>('/resumes', {
      title: payload.title,
      template_id: payload.templateId ?? 'clean',
      content: payload.content,
    })
  },

  getResume(id: number): Promise<ResumeDetail> {
    return request<ResumeDetail>(`/resumes/${id}`)
  },

  /** 保存草稿：后端自动生成新版本快照。 */
  saveResume(
    id: number,
    payload: { title?: string; templateId?: string; content: ResumeContentData; note?: string },
  ): Promise<ResumeDetail> {
    return put<ResumeDetail>(`/resumes/${id}`, {
      ...(payload.title != null ? { title: payload.title } : {}),
      ...(payload.templateId != null ? { template_id: payload.templateId } : {}),
      content: payload.content,
      note: payload.note ?? '',
    })
  },

  deleteResume(id: number): Promise<void> {
    return request<void>(`/resumes/${id}`, { method: 'DELETE' })
  },

  listResumeVersions(id: number): Promise<ResumeVersionSummary[]> {
    return request<ResumeVersionSummary[]>(`/resumes/${id}/versions`)
  },

  getResumeVersion(id: number, versionNo: number): Promise<ResumeVersionDetail> {
    return request<ResumeVersionDetail>(`/resumes/${id}/versions/${versionNo}`)
  },

  restoreResumeVersion(id: number, versionNo: number): Promise<ResumeDetail> {
    return post<ResumeDetail>(`/resumes/${id}/versions/${versionNo}/restore`)
  },

  duplicateResumeVersion(id: number, versionNo: number): Promise<ResumeVersionDetail> {
    return post<ResumeVersionDetail>(`/resumes/${id}/versions/${versionNo}/duplicate`)
  },

  /** AI 表达优化：仅返回建议（不自动保存），需用户确认后自行应用到编辑器。 */
  polishResumeText(id: number, section: string, text: string): Promise<ResumePolishResponse> {
    return post<ResumePolishResponse>(`/resumes/${id}/polish`, { section, text })
  },

  /** 真实文件导出（PDF / DOCX），返回二进制与建议文件名。 */
  exportResume(
    id: number,
    format: 'pdf' | 'docx',
    versionNo?: number,
  ): Promise<{ blob: Blob; filename: string }> {
    const params = new URLSearchParams({ format })
    if (versionNo != null) params.set('version_no', String(versionNo))
    return requestBlob(`/resumes/${id}/export?${params}`)
  },

  // ---------- 回澜：错题本（SM-2） ----------
  collectMistake(payload: { questionId: number; myAnswer?: string }): Promise<MistakeCardOut> {
    return post<MistakeCardOut>('/mistakes', {
      question_id: payload.questionId,
      my_answer: payload.myAnswer ?? '',
    })
  },

  listMistakes(): Promise<MistakeListResponse> {
    return request<MistakeListResponse>('/mistakes')
  },

  reviewMistake(cardId: number, grade: number): Promise<MistakeCardOut> {
    return post<MistakeCardOut>(`/mistakes/${cardId}/review`, { grade })
  },

  deleteMistake(cardId: number): Promise<void> {
    return request<void>(`/mistakes/${cardId}`, { method: 'DELETE' })
  },

  // ---------- 度衡：限时模拟挑战 ----------
  createChallenge(payload: {
    position: string
    difficulty: string
    questionCount: number
    durationMinutes: number
  }): Promise<ChallengeOut> {
    return post<ChallengeOut>('/challenges', {
      position: payload.position,
      difficulty: payload.difficulty,
      question_count: payload.questionCount,
      duration_minutes: payload.durationMinutes,
    })
  },

  listChallenges(): Promise<ChallengeOut[]> {
    return request<ChallengeOut[]>('/challenges')
  },

  getChallenge(id: number): Promise<ChallengeOut> {
    return request<ChallengeOut>(`/challenges/${id}`)
  },

  startChallenge(id: number): Promise<ChallengeOut> {
    return post<ChallengeOut>(`/challenges/${id}/start`)
  },

  submitChallenge(
    id: number,
    answers: { order_index: number; answer: string }[],
  ): Promise<ChallengeOut> {
    return post<ChallengeOut>(`/challenges/${id}/submit`, { answers })
  },

  // ---------- 成长热力图 ----------
  getGrowthHeatmap(year?: number): Promise<GrowthHeatmap> {
    return request<GrowthHeatmap>(`/stats/heatmap${year != null ? `?year=${year}` : ''}`)
  },

  // ---------- 澜记周报 ----------
  getWeeklyReport(signal?: AbortSignal): Promise<WeeklyReport> {
    return request<WeeklyReport>('/stats/weekly', { signal })
  },

  // ---------- 星图对照（观己 × 知岗差距分析） ----------
  gapAnalysis(jobAnalysisId: number): Promise<GapAnalysisResponse> {
    return post<GapAnalysisResponse>('/skills/gap-analysis', {
      job_analysis_id: jobAnalysisId,
    })
  },

  // ---------- 知途：AI 职业顾问「小鸥」 ----------
  listCareerConversations(search?: string): Promise<CareerConversation[]> {
    const params = new URLSearchParams()
    if (search && search.trim()) params.set('search', search.trim())
    const query = params.toString()
    return request<CareerConversation[]>(
      `/career-guide/conversations${query ? `?${query}` : ''}`,
    )
  },

  createCareerConversation(title?: string): Promise<CareerConversation> {
    return post<CareerConversation>('/career-guide/conversations', title ? { title } : null)
  },

  getCareerConversation(id: number): Promise<CareerConversationDetail> {
    return request<CareerConversationDetail>(`/career-guide/conversations/${id}`)
  },

  renameCareerConversation(id: number, title: string): Promise<CareerConversation> {
    return request<CareerConversation>(`/career-guide/conversations/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    })
  },

  deleteCareerConversation(id: number): Promise<void> {
    return request<void>(`/career-guide/conversations/${id}`, { method: 'DELETE' })
  },

  sendCareerMessage(id: number, content: string): Promise<CareerMessagePair> {
    return post<CareerMessagePair>(`/career-guide/conversations/${id}/messages`, { content })
  },

  // ---------- 知途：结构化分析 ----------

  analyzeCareerSituation(): Promise<CareerAnalysisSituation> {
    return post<CareerAnalysisSituation>('/career-guide/analysis/situation')
  },

  exploreCareerDirections(): Promise<CareerDirectionsResult> {
    return post<CareerDirectionsResult>('/career-guide/analysis/directions')
  },

  // ---------- 知途：长期职业档案 ----------

  getCareerProfile(): Promise<CareerProfileDetail> {
    return request<CareerProfileDetail>('/career-guide/profile')
  },

  addCareerFact(content: string, category = 'other'): Promise<CareerProfileFact> {
    return post<CareerProfileFact>('/career-guide/profile/facts', { content, category })
  },

  updateCareerFact(
    factId: number,
    payload: { content?: string; category?: string; confirmed?: boolean },
  ): Promise<CareerProfileFact> {
    return request<CareerProfileFact>(`/career-guide/profile/facts/${factId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },

  deleteCareerFact(factId: number): Promise<void> {
    return request<void>(`/career-guide/profile/facts/${factId}`, { method: 'DELETE' })
  },

  clearCareerFacts(): Promise<void> {
    return request<void>('/career-guide/profile/facts', { method: 'DELETE' })
  },

  organizeCareerProfile(conversationId?: number | null): Promise<CareerProfileDetail> {
    return post<CareerProfileDetail>('/career-guide/profile/organize', {
      conversation_id: conversationId ?? null,
    })
  },

  // ---------- 知途：行动计划 ----------

  listCareerPlans(): Promise<CareerPlanSummary[]> {
    return request<CareerPlanSummary[]>('/career-guide/plans')
  },

  generateCareerPlan(payload?: {
    conversation_id?: number | null
    goal?: string | null
  }): Promise<CareerPlan> {
    return post<CareerPlan>('/career-guide/plans/generate', payload ?? {})
  },

  getCareerPlan(planId: number): Promise<CareerPlan> {
    return request<CareerPlan>(`/career-guide/plans/${planId}`)
  },

  updateCareerPlan(
    planId: number,
    payload: { title?: string; status?: string },
  ): Promise<CareerPlan> {
    return request<CareerPlan>(`/career-guide/plans/${planId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },

  deleteCareerPlan(planId: number): Promise<void> {
    return request<void>(`/career-guide/plans/${planId}`, { method: 'DELETE' })
  },

  addCareerPlanAction(
    planId: number,
    payload: { phase: string; goal: string; steps?: string | null; related_goal?: string | null },
  ): Promise<CareerPlan> {
    return post<CareerPlan>(`/career-guide/plans/${planId}/actions`, payload)
  },

  updateCareerPlanAction(
    planId: number,
    actionId: number,
    payload: { status?: string; review?: string | null; due_at?: string | null },
  ): Promise<CareerPlan> {
    return request<CareerPlan>(`/career-guide/plans/${planId}/actions/${actionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },

  deleteCareerPlanAction(planId: number, actionId: number): Promise<CareerPlan> {
    return request<CareerPlan>(`/career-guide/plans/${planId}/actions/${actionId}`, {
      method: 'DELETE',
    })
  },

  // ---------- 知途：联动工作流与数据导出 ----------

  runCareerWorkflow(kind: 'gap_analysis' | 'interview_prep', params?: Record<string, unknown>): Promise<CareerWorkflowRun> {
    return post<CareerWorkflowRun>('/career-guide/workflows', { kind, params: params ?? {} })
  },

  getCareerWorkflow(runId: number): Promise<CareerWorkflowRun> {
    return request<CareerWorkflowRun>(`/career-guide/workflows/${runId}`)
  },

  listCareerWorkflows(): Promise<CareerWorkflowRun[]> {
    return request<CareerWorkflowRun[]>('/career-guide/workflows')
  },

  exportCareerData(): Promise<{ blob: Blob; filename: string }> {
    return requestBlob('/career-guide/export')
  },

  // ---------- 知途高级能力（第十五阶段） ----------
  getCareerGraph(): Promise<CareerGraph> {
    return request<CareerGraph>('/career-guide/graph')
  },

  syncCareerGraph(includeKnowledge = true): Promise<CareerGraph> {
    return post<CareerGraph>('/career-guide/graph/sync', { include_knowledge: includeKnowledge })
  },

  suggestCareerGraphNodes(): Promise<CareerGraph> {
    return post<CareerGraph>('/career-guide/graph/suggest', {})
  },

  updateCareerGraphNode(
    nodeId: number,
    payload: { status: string; note?: string | null },
  ): Promise<{ id: number; status: string; message: string }> {
    return request(`/career-guide/graph/nodes/${nodeId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },

  deleteCareerGraphNode(nodeId: number): Promise<void> {
    return request<void>(`/career-guide/graph/nodes/${nodeId}`, { method: 'DELETE' })
  },

  addCareerGraphEdge(payload: {
    from_node_id: number
    to_node_id: number
    relation: string
  }): Promise<CareerGraph> {
    return post<CareerGraph>('/career-guide/graph/edges', payload)
  },

  compareCareerPaths(payload: {
    directions: string[]
    note?: string
  }): Promise<CareerPathComparison> {
    return post<CareerPathComparison>('/career-guide/paths/compare', payload)
  },

  listCareerPathComparisons(): Promise<CareerPathComparison[]> {
    return request<CareerPathComparison[]>('/career-guide/paths')
  },

  getCareerPathComparison(id: number): Promise<CareerPathComparison> {
    return request<CareerPathComparison>(`/career-guide/paths/${id}`)
  },

  deleteCareerPathComparison(id: number): Promise<void> {
    return request<void>(`/career-guide/paths/${id}`, { method: 'DELETE' })
  },

  searchCareerKnowledge(payload: {
    query: string
    top_k?: number
    industry_id?: string | null
    occupation_id?: string | null
    experience_level?: string | null
    source_kinds?: string[]
  }): Promise<RetrievalOutcome> {
    return post<RetrievalOutcome>('/career-guide/retrieval/search', payload)
  },

  syncCareerRetrievalIndex(): Promise<{
    global_added: number
    user_added: number
    stats: RetrievalStats
  }> {
    return post('/career-guide/retrieval/sync', {})
  },

  getCareerRetrievalStats(): Promise<RetrievalStats> {
    return request<RetrievalStats>('/career-guide/retrieval/stats')
  },

  getCareerMemoryUsage(params: {
    conversation_id?: number | null
    query?: string
  } = {}): Promise<MemoryUsage> {
    const search = new URLSearchParams()
    if (params.conversation_id != null) search.set('conversation_id', String(params.conversation_id))
    if (params.query && params.query.trim()) search.set('query', params.query.trim())
    const query = search.toString()
    return request<MemoryUsage>(`/career-guide/memory/usage${query ? `?${query}` : ''}`)
  },

  clearCareerMemory(): Promise<{ deleted_conversations: number; deleted_facts: number }> {
    return request('/career-guide/memory', { method: 'DELETE' })
  },

  listPlanRevisions(planId: number): Promise<PlanRevisionSummary[]> {
    return request<PlanRevisionSummary[]>(`/career-guide/plans/${planId}/revisions`)
  },

  getPlanRevision(planId: number, versionNo: number): Promise<PlanRevisionDetail> {
    return request<PlanRevisionDetail>(`/career-guide/plans/${planId}/revisions/${versionNo}`)
  },

  reviewCareerPlan(planId: number): Promise<{
    plan: CareerPlan
    review: PlanReviewResult
    disclaimer: string
  }> {
    return post(`/career-guide/plans/${planId}/review`, {})
  },

  applyPlanReviewAdjustments(
    planId: number,
    adjustments: PlanReviewAdjustment[],
  ): Promise<{ plan: CareerPlan; message: string }> {
    return post(`/career-guide/plans/${planId}/review/apply`, { adjustments })
  },

  getGrowthFeedback(): Promise<GrowthFeedback> {
    return request<GrowthFeedback>('/career-guide/growth')
  },

  listCareerEvalRuns(limit = 20): Promise<CareerEvalRunRecord[]> {
    return request<CareerEvalRunRecord[]>(`/career-guide/eval-runs?limit=${limit}`)
  },

  runCareerOfflineEval(): Promise<{
    metrics: Record<string, unknown>
    dataset_version: string
    note: string
  }> {
    return post('/career-guide/eval/offline', {})
  },

  // ---------- 知潮：真实岗位资料库 ----------
  listJobPositions(params: {
    q?: string
    industry_id?: string
    occupation_id?: string
    location?: string
    level?: string
    company?: string
    stage?: string
    limit?: number
    offset?: number
  } = {}): Promise<JobPositionListResponse> {
    const search = new URLSearchParams()
    if (params.q && params.q.trim()) search.set('q', params.q.trim())
    if (params.industry_id) search.set('industry_id', params.industry_id)
    if (params.occupation_id) search.set('occupation_id', params.occupation_id)
    if (params.location && params.location.trim()) search.set('location', params.location.trim())
    if (params.level && params.level.trim()) search.set('level', params.level.trim())
    if (params.company && params.company.trim()) search.set('company', params.company.trim())
    if (params.stage) search.set('stage', params.stage)
    if (params.limit != null) search.set('limit', String(params.limit))
    if (params.offset != null) search.set('offset', String(params.offset))
    const query = search.toString()
    return request<JobPositionListResponse>(`/job-library${query ? `?${query}` : ''}`)
  },

  listFavoritePositions(): Promise<JobPositionListResponse> {
    return request<JobPositionListResponse>('/job-library/favorites')
  },

  getJobPosition(id: number): Promise<JobPositionDetail> {
    return request<JobPositionDetail>(`/job-library/${id}`)
  },

  /** 导入真实岗位：须提供可验证来源链接，或选择手动录入（无链接）。 */
  importJobPosition(payload: JobPositionImportPayload): Promise<JobPositionImportResponse> {
    return post<JobPositionImportResponse>('/job-library', payload)
  },

  toggleJobFavorite(id: number, favorited: boolean): Promise<void> {
    return request<void>(`/job-library/${id}/favorite`, { method: favorited ? 'DELETE' : 'POST' })
  },

  /** 单次访问来源链接核验有效性；只判断链接，不断定招聘状态。 */
  verifyJobPosition(id: number): Promise<JobPosition> {
    return post<JobPosition>(`/job-library/${id}/verify`)
  },

  /** 库内岗位送入知岗解析（复用现有 jd_analysis，证据核验规则不变）。 */
  analyzeJobFromPosition(id: number, forceNew = false): Promise<JobAnalyzeFromPositionResponse> {
    return post<JobAnalyzeFromPositionResponse>(`/job-library/${id}/analyze`, {
      force_new: forceNew,
    })
  },

  /** 库内岗位作为问澜出题条件（复用题集生成流程）。 */
  createInterviewFromPosition(id: number, forceNew = false): Promise<TaskDetail> {
    return post<TaskDetail>(`/job-library/${id}/interview-task`, { force_new: forceNew })
  },

  /** 库内岗位加入合契匹配：真实岗位 + 知岗解析 + 用户简历。 */
  matchPositionWithResume(id: number, resumeId: number): Promise<JobResumeMatchResponse> {
    return post<JobResumeMatchResponse>(`/job-library/${id}/match`, { resume_id: resumeId })
  },

  /** 库内岗位加入知途规划：先确保知岗解析，再复用现有 7/30/90 天规划生成。 */
  createCareerPlanFromPosition(id: number, forceNew = false): Promise<JobCareerPlanResponse> {
    return post<JobCareerPlanResponse>(`/job-library/${id}/career-plan`, { force_new: forceNew })
  },

  // ---------- 知岗：用户修改解析结果 ----------

  /** 修改知岗解析结果：服务端按同一证据标准重新核验，通过后标记 user_edited。 */
  updateJobAnalysis(
    id: number,
    payload: { result: JobAnalysisDetail['result']; title?: string },
  ): Promise<JobAnalysisDetail> {
    return request<JobAnalysisDetail>(`/jobs/analyses/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        result: payload.result,
        ...(payload.title != null ? { title: payload.title } : {}),
      }),
    })
  },

  // ---------- 履历成章：模板参考来源与岗位适配诊断 ----------

  listResumeTemplateSources(): Promise<ResumeTemplateSource[]> {
    return request<ResumeTemplateSource[]>('/resumes/template-sources')
  },

  /** 岗位适配诊断：关键词缺口 + 缺证据表达 + STAR 建议（只讲方法，不代写事实）。 */
  optimizeResumeForJob(
    resumeId: number,
    payload: { jobAnalysisId?: number; jdText?: string; position?: string },
  ): Promise<ResumeOptimizeForJobResponse> {
    return post<ResumeOptimizeForJobResponse>(`/resumes/${resumeId}/optimize-for-job`, {
      ...(payload.jobAnalysisId != null ? { job_analysis_id: payload.jobAnalysisId } : {}),
      ...(payload.jdText ? { jd_text: payload.jdText } : {}),
      position: payload.position ?? '',
    })
  },
}
