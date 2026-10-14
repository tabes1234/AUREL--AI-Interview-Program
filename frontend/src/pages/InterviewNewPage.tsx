import {
  AlertCircle,
  BookOpenText,
  Check,
  ChevronDown,
  Loader2,
  RotateCcw,
  Search,
  Sparkles,
  Waves,
} from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { AurelTaskStatus, useAsyncTask } from '../components/aurel-progress'
import { PageHeading } from '../components/editorial/Editorial'
import { Button, ButtonLink } from '../components/ui/Button'
import { RadioCardGroup, TextAreaField } from '../components/ui/Field'
import { cn } from '../lib/cn'
import {
  EXPERIENCE_LABELS,
  FOCUS_LABELS,
  INTERVIEW_TYPE_LABELS,
} from '../lib/format'
import type {
  CatalogIndustry,
  CatalogOccupation,
  ExperienceLevel,
  FocusArea,
  InterviewType,
  KnowledgeDocument,
} from '../types'

const CUSTOM_OCCUPATION_MIN = 2
const CUSTOM_OCCUPATION_MAX = 60
const JOB_DESCRIPTION_MAX = 2000

const DIFFICULTY_OPTIONS = [
  { value: 'basic', label: '基础', description: '贴近岗位常见面试问题' },
  { value: 'intermediate', label: '进阶', description: '考察深度理解与场景应对' },
  { value: 'advanced', label: '高阶', description: '高压追问与综合案例' },
]

const LANGUAGE_OPTIONS = [
  { value: 'zh', label: '中文', description: '以中文进行问答' },
  { value: 'en', label: '英文', description: '以英文进行问答' },
]

const QUESTION_COUNT_OPTIONS = [
  { value: '5', label: '5 道', description: '快速练习' },
  { value: '8', label: '8 道', description: '标准练习' },
  { value: '10', label: '10 道', description: '完整模拟（推荐）' },
  { value: '15', label: '15 道', description: '深度演练' },
]

const EXPERIENCE_OPTIONS = Object.entries(EXPERIENCE_LABELS).map(([value, label]) => ({
  value,
  label,
}))

const INTERVIEW_TYPE_OPTIONS = Object.entries(INTERVIEW_TYPE_LABELS).map(([value, label]) => ({
  value,
  label,
}))

const FOCUS_OPTIONS = (Object.entries(FOCUS_LABELS) as [FocusArea, string][]).map(
  ([value, label]) => ({ value, label }),
)

interface SelectOption {
  id: string
  label: string
  hint?: string
}

interface SearchSelectProps {
  label: string
  required?: boolean
  placeholder: string
  disabled?: boolean
  loading?: boolean
  selectedLabel: string | null
  options: SelectOption[]
  emptyText: string
  onSelect: (id: string) => void
  error?: string
}

/** 可搜索下拉选择器：支持按名称/别名过滤与键盘关闭。 */
function SearchSelect({
  label,
  required,
  placeholder,
  disabled,
  loading,
  selectedLabel,
  options,
  emptyText,
  onSelect,
  error,
}: SearchSelectProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return options
    return options.filter((option) => option.label.toLowerCase().includes(q))
  }, [options, query])

  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-ink-strong">
        {label}
        {required ? <span className="ml-1 text-red-500">*</span> : null}
      </label>
      <div className="relative">
        <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-soft">
          <Search className="h-4 w-4" aria-hidden="true" />
        </span>
        <input
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-label={label}
          disabled={disabled}
          value={open ? query : (selectedLabel ?? '')}
          placeholder={selectedLabel ?? placeholder}
          onChange={(event) => {
            setQuery(event.target.value)
            setOpen(true)
          }}
          onFocus={() => {
            setQuery('')
            setOpen(true)
          }}
          onKeyDown={(event) => {
            if (event.key === 'Escape') setOpen(false)
          }}
          className={cn(
            'w-full rounded-lg border bg-white py-2.5 pl-10 pr-3.5 text-sm text-ink placeholder:text-slate-400 transition-colors focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:bg-slate-50',
            error
              ? 'border-red-400 focus:border-red-500 focus:ring-red-400/25'
              : 'border-slate-300 focus:border-brand-600 focus:ring-brand-600/25',
          )}
        />
        {open && !disabled ? (
          <>
            <div
              className="fixed inset-0 z-20"
              aria-hidden="true"
              onMouseDown={() => setOpen(false)}
            />
            <ul
              role="listbox"
              className="absolute z-30 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-line bg-white py-1 shadow-lg shadow-brand-900/10"
            >
              {loading ? (
                <li className="flex items-center gap-2 px-3.5 py-3 text-sm text-ink-soft">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  目录加载中…
                </li>
              ) : filtered.length === 0 ? (
                <li className="px-3.5 py-3 text-sm text-ink-soft">{emptyText}</li>
              ) : (
                filtered.map((option) => (
                  <li key={option.id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={option.label === selectedLabel}
                      onMouseDown={(event) => {
                        event.preventDefault()
                        onSelect(option.id)
                        setOpen(false)
                      }}
                      className={cn(
                        'flex w-full flex-col items-start px-3.5 py-2 text-left transition-colors hover:bg-brand-50',
                        option.label === selectedLabel && 'bg-brand-50',
                      )}
                    >
                      <span className="text-sm font-medium text-ink-strong">{option.label}</span>
                      {option.hint ? (
                        <span className="mt-0.5 text-xs text-ink-soft">{option.hint}</span>
                      ) : null}
                    </button>
                  </li>
                ))
              )}
            </ul>
          </>
        ) : null}
      </div>
      {error ? (
        <p role="alert" className="mt-1.5 flex items-center gap-1 text-xs text-red-600">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {error}
        </p>
      ) : null}
    </div>
  )
}

interface FormErrors {
  industry?: string
  occupation?: string
  customOccupation?: string
}

type SubmitPhase = 'form' | 'creating' | 'failed'

export default function InterviewNewPage() {
  const navigate = useNavigate()

  // 第一屏两个主要选择器
  const [industries, setIndustries] = useState<CatalogIndustry[]>([])
  const [industriesLoading, setIndustriesLoading] = useState(true)
  const [industryId, setIndustryId] = useState('')
  const [occupations, setOccupations] = useState<CatalogOccupation[]>([])
  const [occupationsLoading, setOccupationsLoading] = useState(false)
  const [occupationId, setOccupationId] = useState('')
  const [customOccupation, setCustomOccupation] = useState('')

  // 更多设置
  const [showMore, setShowMore] = useState(false)
  const [experienceLevel, setExperienceLevel] = useState<ExperienceLevel>('fresh_graduate')
  const [interviewType, setInterviewType] = useState<InterviewType>('comprehensive')
  const [focusAreas, setFocusAreas] = useState<FocusArea[]>(['comprehensive'])
  const [difficulty, setDifficulty] = useState('intermediate')
  const [language, setLanguage] = useState('zh')
  const [questionCount, setQuestionCount] = useState('10')
  const [jobDescription, setJobDescription] = useState('')
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [knowledgeDocumentId, setKnowledgeDocumentId] = useState<string>('')

  const [errors, setErrors] = useState<FormErrors>({})
  const [phase, setPhase] = useState<SubmitPhase>('form')
  const [submitError, setSubmitError] = useState<string | null>(null)

  // 题集生成链路统一任务状态：真实计时、防重复提交
  const createTask = useAsyncTask({ debugLabel: 'interview-create' })

  useEffect(() => {
    let cancelled = false
    api
      .listIndustries()
      .then((items) => {
        if (cancelled) return
        setIndustries(items)
        setIndustriesLoading(false)
      })
      .catch(() => {
        if (!cancelled) setIndustriesLoading(false)
      })
    api
      .listKnowledgeDocuments()
      .then((docs) => {
        if (!cancelled) setDocuments(docs)
      })
      .catch(() => {
        // 知识库列表加载失败不阻塞建题，静默降级为不引用
      })
    return () => {
      cancelled = true
    }
  }, [])

  // 行业切换后按需加载对应职业（事件驱动），并清除不再适用的旧职业选项
  const occupationRequestRef = useRef(0)

  function handleIndustrySelect(id: string) {
    setIndustryId(id)
    setOccupationId('')
    setCustomOccupation('')
    setOccupations([])
    setOccupationsLoading(false)
    setErrors((prev) => ({ ...prev, industry: undefined, occupation: undefined, customOccupation: undefined }))
    if (!id || id === 'other') return
    const seq = ++occupationRequestRef.current
    setOccupationsLoading(true)
    api
      .listOccupations(id)
      .then((items) => {
        if (occupationRequestRef.current !== seq) return
        setOccupations(items)
        setOccupationsLoading(false)
      })
      .catch(() => {
        if (occupationRequestRef.current !== seq) return
        setOccupationsLoading(false)
      })
  }

  const industryOptions: SelectOption[] = useMemo(
    () =>
      industries.map((item) => ({
        id: item.id,
        label: item.name,
        hint:
          item.id === 'other'
            ? '目录之外的行业，使用自定义职业'
            : `${item.occupation_count} 个职业方向`,
      })),
    [industries],
  )

  const occupationOptions: SelectOption[] = useMemo(() => {
    const catalogItems = occupations.map((item) => ({
      id: item.id,
      label: item.name,
      hint:
        item.aliases.length > 0
          ? `${item.core_skills.join(' · ')}｜别名：${item.aliases.join('、')}`
          : item.core_skills.join(' · '),
    }))
    return [...catalogItems, { id: 'custom', label: '自定义职业', hint: '目录中没有的职业，手动填写' }]
  }, [occupations])

  const selectedIndustry = industries.find((item) => item.id === industryId) ?? null
  const selectedOccupation = occupations.find((item) => item.id === occupationId) ?? null
  const isOtherIndustry = industryId === 'other'
  const isCustomOccupation = occupationId === 'custom' || isOtherIndustry

  function toggleFocus(value: FocusArea) {
    setFocusAreas((prev) => {
      const next = prev.includes(value)
        ? prev.filter((item) => item !== value)
        : [...prev, value]
      return next.length === 0 ? ['comprehensive'] : next
    })
  }

  function validate(): FormErrors {
    const next: FormErrors = {}
    if (!industryId) {
      next.industry = '请选择行业门类'
    }
    if (!occupationId && !isOtherIndustry) {
      next.occupation = '请选择职业方向'
    }
    if (isCustomOccupation) {
      const name = customOccupation.trim()
      if (!name) {
        next.customOccupation = '请填写职业名称'
      } else if (name.length < CUSTOM_OCCUPATION_MIN || name.length > CUSTOM_OCCUPATION_MAX) {
        next.customOccupation = `职业名称需在 ${CUSTOM_OCCUPATION_MIN}-${CUSTOM_OCCUPATION_MAX} 个字符之间`
      }
    }
    return next
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors = validate()
    setErrors(nextErrors)
    if (nextErrors.industry || nextErrors.occupation || nextErrors.customOccupation) {
      return
    }

    setPhase('creating')
    setSubmitError(null)
    await createTask.run(async () => {
      try {
        const task = await api.generateQuestions({
          industryId,
          occupationId: isOtherIndustry ? 'custom' : occupationId,
          customOccupation: isCustomOccupation ? customOccupation.trim() : undefined,
          experienceLevel,
          interviewType,
          focusAreas,
          difficulty: difficulty as 'basic' | 'intermediate' | 'advanced',
          language: language as 'zh' | 'en',
          questionCount: Number(questionCount),
          jobDescription: jobDescription.trim(),
          knowledgeDocumentId: knowledgeDocumentId ? Number(knowledgeDocumentId) : null,
        })
        navigate(`/interview/${task.id}`)
      } catch (error) {
        setPhase('failed')
        setSubmitError(
          error instanceof ApiError ? error.message : '题集生成失败，请检查后端服务是否运行',
        )
      }
    })
  }

  const busy = phase === 'creating'

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeading
        kicker="启程"
        title="问澜"
        subtitle="循行业脉络，生成职业面试题。"
      />

      <div className="mt-8">
        <AnimatePresence mode="wait" initial={false}>
          {phase === 'failed' ? (
            <motion.div
              key="error"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.28, ease: 'easeOut' }}
            >
              <div className="flex flex-col items-center py-10 text-center">
                <AlertCircle className="h-11 w-11 text-red-500" aria-hidden="true" />
                <h2 className="mt-4 text-lg font-bold text-ink-strong">题集生成失败</h2>
                <p className="mt-2 max-w-md text-sm leading-relaxed text-red-700">
                  {submitError}
                </p>
                <p className="mt-1 text-xs text-ink-soft">
                  若提示未配置，请在 backend/.env 中填写 ARK_API_KEY 与 ARK_MODEL 后重启后端。
                </p>
                <div className="mt-6">
                  <Button variant="secondary" onClick={() => setPhase('form')}>
                    <RotateCcw className="h-4 w-4" aria-hidden="true" />
                    返回表单
                  </Button>
                </div>
              </div>
            </motion.div>
          ) : (
            <div key="form">
              <form
                onSubmit={handleSubmit}
                noValidate
                className="space-y-7 rounded-xl border border-line bg-white p-5 sm:p-8"
              >
                <div>
                  <h2 className="text-lg font-bold tracking-tight text-ink-strong">行业与职业</h2>
                  <p className="mt-1 text-sm text-ink-soft">
                    先定行业门类，再选职业方向；目录之外可自定义
                  </p>
                </div>
                <SearchSelect
                      label="行业门类"
                      required
                      placeholder="搜索或选择行业（共 24 类 + 其他）"
                      loading={industriesLoading}
                      selectedLabel={selectedIndustry?.name ?? null}
                      options={industryOptions}
                      emptyText="没有匹配的行业"
                      error={errors.industry}
                      onSelect={handleIndustrySelect}
                    />

                    {isOtherIndustry ? (
                      <div>
                        <label
                          htmlFor="custom-occupation"
                          className="mb-1.5 block text-sm font-medium text-ink-strong"
                        >
                          自定义职业
                          <span className="ml-1 text-red-500">*</span>
                        </label>
                        <input
                          id="custom-occupation"
                          type="text"
                          value={customOccupation}
                          maxLength={CUSTOM_OCCUPATION_MAX}
                          placeholder="填写「其他行业」下的具体职业，例如：碳中和咨询师"
                          onChange={(event) => {
                            setCustomOccupation(event.target.value)
                            if (errors.customOccupation) {
                              setErrors((prev) => ({ ...prev, customOccupation: undefined }))
                            }
                          }}
                          className={cn(
                            'w-full rounded-lg border bg-white px-3.5 py-2.5 text-sm text-ink placeholder:text-slate-400 transition-colors focus:outline-none focus:ring-2',
                            errors.customOccupation
                              ? 'border-red-400 focus:border-red-500 focus:ring-red-400/25'
                              : 'border-slate-300 focus:border-brand-600 focus:ring-brand-600/25',
                          )}
                        />
                        {errors.customOccupation ? (
                          <p role="alert" className="mt-1.5 flex items-center gap-1 text-xs text-red-600">
                            <AlertCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                            {errors.customOccupation}
                          </p>
                        ) : null}
                      </div>
                    ) : (
                      <SearchSelect
                        label="职业方向"
                        required
                        placeholder={
                          industryId ? '搜索职业（支持名称与别名）' : '请先选择行业门类'
                        }
                        disabled={!industryId}
                        loading={occupationsLoading}
                        selectedLabel={occupationId === 'custom' ? '自定义职业' : (selectedOccupation?.name ?? null)}
                        options={occupationOptions}
                        emptyText="没有匹配的职业，可尝试「自定义职业」"
                        error={errors.occupation}
                        onSelect={(id) => {
                          setOccupationId(id)
                          if (id !== 'custom') setCustomOccupation('')
                          setErrors((prev) => ({ ...prev, occupation: undefined, customOccupation: undefined }))
                        }}
                      />
                    )}

                    {isCustomOccupation && !isOtherIndustry ? (
                      <div>
                        <label
                          htmlFor="custom-occupation-inline"
                          className="mb-1.5 block text-sm font-medium text-ink-strong"
                        >
                          自定义职业名称
                          <span className="ml-1 text-red-500">*</span>
                        </label>
                        <input
                          id="custom-occupation-inline"
                          type="text"
                          value={customOccupation}
                          maxLength={CUSTOM_OCCUPATION_MAX}
                          placeholder="填写目录中没有的职业，例如：增长黑客"
                          onChange={(event) => {
                            setCustomOccupation(event.target.value)
                            if (errors.customOccupation) {
                              setErrors((prev) => ({ ...prev, customOccupation: undefined }))
                            }
                          }}
                          className={cn(
                            'w-full rounded-lg border bg-white px-3.5 py-2.5 text-sm text-ink placeholder:text-slate-400 transition-colors focus:outline-none focus:ring-2',
                            errors.customOccupation
                              ? 'border-red-400 focus:border-red-500 focus:ring-red-400/25'
                              : 'border-slate-300 focus:border-brand-600 focus:ring-brand-600/25',
                          )}
                        />
                        {errors.customOccupation ? (
                          <p role="alert" className="mt-1.5 flex items-center gap-1 text-xs text-red-600">
                            <AlertCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                            {errors.customOccupation}
                          </p>
                        ) : null}
                      </div>
                    ) : null}

                    {/* 更多设置：收纳次要项，默认折叠 */}
                    <div className="rounded-xl border border-line bg-mist/60">
                      <button
                        type="button"
                        onClick={() => setShowMore((prev) => !prev)}
                        className="flex w-full items-center justify-between px-5 py-4 text-left"
                        aria-expanded={showMore}
                      >
                        <span className="flex items-center gap-2 text-sm font-semibold text-ink-strong">
                          <Waves className="h-4 w-4 text-brand-600" aria-hidden="true" />
                          更多设置
                          <span className="text-xs font-normal text-ink-soft">
                            经验阶段、面试类型、侧重、难度等已按常用值预设
                          </span>
                        </span>
                        <ChevronDown
                          className={cn(
                            'h-4 w-4 text-ink-soft transition-transform',
                            showMore && 'rotate-180',
                          )}
                          aria-hidden="true"
                        />
                      </button>
                      {showMore ? (
                        <div className="space-y-7 border-t border-line px-5 py-6">
                          <RadioCardGroup
                            legend="经验阶段"
                            name="experience"
                            options={EXPERIENCE_OPTIONS}
                            value={experienceLevel}
                            onChange={(value) => setExperienceLevel(value as ExperienceLevel)}
                            columns={2}
                          />

                          <RadioCardGroup
                            legend="面试类型"
                            name="interview-type"
                            options={INTERVIEW_TYPE_OPTIONS}
                            value={interviewType}
                            onChange={(value) => setInterviewType(value as InterviewType)}
                            columns={2}
                          />

                          <fieldset>
                            <legend className="mb-1.5 text-sm font-medium text-ink-strong">
                              题目侧重
                              <span className="ml-1.5 text-xs font-normal text-ink-soft">
                                可多选，出题将围绕所选侧重
                              </span>
                            </legend>
                            <div className="flex flex-wrap gap-2">
                              {FOCUS_OPTIONS.map((option) => {
                                const active = focusAreas.includes(option.value)
                                return (
                                  <button
                                    key={option.value}
                                    type="button"
                                    onClick={() => toggleFocus(option.value)}
                                    aria-pressed={active}
                                    className={cn(
                                      'flex items-center gap-1.5 rounded-full border px-4 py-1.5 text-xs font-medium transition-all duration-200',
                                      active
                                        ? 'border-brand-600 bg-gradient-to-r from-brand-50 to-brand-100/80 text-brand-700 shadow-[0_1px_6px_rgba(77,131,214,0.18)] ring-1 ring-brand-600/25'
                                        : 'border-slate-300 bg-white text-ink-soft hover:-translate-y-0.5 hover:border-brand-600/50 hover:text-brand-700',
                                    )}
                                  >
                                    {active ? <Check className="h-3 w-3" strokeWidth={3} aria-hidden="true" /> : null}
                                    {option.label}
                                  </button>
                                )
                              })}
                            </div>
                          </fieldset>

                          <RadioCardGroup
                            legend="难度"
                            name="difficulty"
                            options={DIFFICULTY_OPTIONS}
                            value={difficulty}
                            onChange={setDifficulty}
                          />

                          <RadioCardGroup
                            legend="练习语言"
                            name="language"
                            options={LANGUAGE_OPTIONS}
                            value={language}
                            onChange={setLanguage}
                            columns={2}
                          />

                          <RadioCardGroup
                            legend="题目数量"
                            name="question-count"
                            options={QUESTION_COUNT_OPTIONS}
                            value={questionCount}
                            onChange={setQuestionCount}
                          />

                          <TextAreaField
                            label="岗位描述"
                            value={jobDescription}
                            placeholder="粘贴真实招聘要求（职责、技能、经验），出题将参考其内容"
                            maxLength={JOB_DESCRIPTION_MAX}
                            rows={4}
                            onChange={setJobDescription}
                            hint="仅作为参考资料，不会当作指令执行"
                          />

                          {documents.length > 0 ? (
                            <div>
                              <label
                                htmlFor="knowledge-select"
                                className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-ink-strong"
                              >
                                <BookOpenText className="h-4 w-4 text-brand-600" aria-hidden="true" />
                                参考知识库
                                <span className="text-xs font-normal text-ink-soft">
                                  选填，出题将围绕所选文档检索引用
                                </span>
                              </label>
                              <select
                                id="knowledge-select"
                                value={knowledgeDocumentId}
                                onChange={(event) => setKnowledgeDocumentId(event.target.value)}
                                className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-ink focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25"
                              >
                                <option value="">不引用知识库</option>
                                {documents.map((doc) => (
                                  <option key={doc.id} value={doc.id}>
                                    {doc.title}（{doc.chunk_count} 块）
                                  </option>
                                ))}
                              </select>
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </div>

                    {/* 成题等待期长任务面板：真实状态 + 已耗时（不虚构进度） */}
                    {busy && createTask.running ? (
                      <AurelTaskStatus
                        title="问澜成题"
                        scene="wenlan.questions"
                        status={createTask.status}
                        elapsedMs={createTask.elapsedMs}
                      />
                    ) : null}

                    <div className="flex items-center justify-between gap-3 border-t border-line pt-6">
                      <p className="hidden text-xs text-ink-soft sm:block">
                        将以{EXPERIENCE_LABELS[experienceLevel]}视角、
                        {INTERVIEW_TYPE_LABELS[interviewType]}生成 {questionCount} 道题
                      </p>
                      <div className="flex items-center gap-3">
                        <ButtonLink to="/app" variant="ghost">
                          取消
                        </ButtonLink>
                        <Button type="submit" disabled={busy}>
                          {busy ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                              问澜成题中，静候片刻…
                            </>
                          ) : (
                            <>
                              <Sparkles className="h-4 w-4" aria-hidden="true" />
                              生成问澜题集
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  </form>
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
