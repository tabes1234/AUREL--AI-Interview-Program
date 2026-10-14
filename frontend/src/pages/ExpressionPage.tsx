import {
  AudioLines,
  CheckCircle2,
  CircleAlert,
  FileAudio,
  History,
  Loader2,
  Mic,
  PenLine,
  Sparkles,
  Square,
  Trash2,
  Type,
  Upload,
  Volume2,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api/client'
import { AiStatusBadge } from '../components/AiStatusBadge'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeading, SectionHead, StatStrip } from '../components/editorial/Editorial'
import { blobToWavFile } from '../lib/audio'
import { formatDateTime } from '../lib/format'
import type {
  ExpressionRecord,
  ExpressionStatus,
  ExpressionTranscribeResponse,
  ExpressionWorkflowResponse,
  WorkflowStep,
} from '../types'

type InputMode = 'record' | 'upload' | 'text'

type StepRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped'

interface StepState {
  title: string
  status: StepRunStatus
  error?: string | null
}

const ROLE_ORDER = ['structure_analyst', 'depth_analyst', 'expression_coach'] as const

const ROLE_LABELS: Record<string, string> = {
  structure_analyst: '结构分析师',
  depth_analyst: '内容深度分析师',
  expression_coach: '表达教练',
}

interface IssueItem {
  type?: string
  evidence?: string
  suggestion?: string
}

const MODE_TABS: { key: InputMode; label: string; icon: typeof Mic }[] = [
  { key: 'record', label: '录音', icon: Mic },
  { key: 'upload', label: '上传音频', icon: Upload },
  { key: 'text', label: '粘贴文本', icon: Type },
]

function fmtDuration(ms: number | null | undefined): string {
  if (!ms || ms <= 0) return '—'
  const totalSeconds = Math.round(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return minutes > 0 ? `${minutes} 分 ${seconds} 秒` : `${seconds} 秒`
}

export function ExpressionPage() {
  const [status, setStatus] = useState<ExpressionStatus | null>(null)
  const [mode, setMode] = useState<InputMode>('record')

  const [recording, setRecording] = useState(false)
  const [recordSeconds, setRecordSeconds] = useState(0)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<number | null>(null)

  const [processing, setProcessing] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const [text, setText] = useState('')

  const [transcribeResult, setTranscribeResult] = useState<ExpressionTranscribeResponse | null>(null)
  const [analyzeResult, setAnalyzeResult] = useState<ExpressionWorkflowResponse | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [stepStates, setStepStates] = useState<Record<string, StepState>>({})
  const [records, setRecords] = useState<ExpressionRecord[]>([])
  const [error, setError] = useState<string | null>(null)

  const refreshRecords = useCallback(() => {
    api
      .listExpressionRecords()
      .then(setRecords)
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    document.title = '听澜 · 表达分析 | 观澜 AUREL'
    api
      .getExpressionStatus()
      .then(setStatus)
      .catch(() => undefined)
    refreshRecords()
    return () => {
      document.title = '观澜 AUREL — AI 驱动的能力探索与成长平台'
    }
  }, [refreshRecords])

  useEffect(
    () => () => {
      if (timerRef.current) window.clearInterval(timerRef.current)
      recorderRef.current?.stream.getTracks().forEach((track) => track.stop())
    },
    [],
  )

  const submitAudio = async (blob: Blob, name: string) => {
    setProcessing(true)
    setError(null)
    try {
      let file: File
      try {
        file = await blobToWavFile(blob, name.replace(/\.[^.]+$/, '') + '.wav')
      } catch {
        file = new File([blob], name, { type: blob.type || 'audio/webm' })
      }
      const result = await api.transcribeAudio(file)
      setTranscribeResult(result)
      setAnalyzeResult(null)
      refreshRecords()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '音频处理失败，请稍后再试')
    } finally {
      setProcessing(false)
    }
  }

  const startRecording = async () => {
    setError(null)
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('当前浏览器不支持录音，请使用 Chrome / Edge，或改用上传音频')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop())
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        if (blob.size > 0) void submitAudio(blob, 'recording.webm')
      }
      recorder.start()
      recorderRef.current = recorder
      setRecordSeconds(0)
      setRecording(true)
      timerRef.current = window.setInterval(() => setRecordSeconds((s) => s + 1), 1000)
    } catch {
      setError('无法访问麦克风：请允许浏览器使用麦克风后重试')
    }
  }

  const stopRecording = () => {
    if (timerRef.current) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
    recorderRef.current?.stop()
    recorderRef.current = null
    setRecording(false)
  }

  const runAnalyze = async (payload: { text?: string; analysisId?: number }) => {
    setAnalyzing(true)
    setError(null)
    setStepStates({})
    try {
      let result: ExpressionWorkflowResponse
      try {
        result = await api.analyzeExpressionStream(payload, (event, data) => {
          setStepStates((prev) => {
            if (event === 'step_started') {
              return { ...prev, [data.role]: { title: data.title, status: 'running' } }
            }
            const existing = prev[data.role]
            return {
              ...prev,
              [data.role]: {
                title: existing?.title ?? data.title,
                status: (data.status as StepRunStatus) ?? 'completed',
                error: data.error ?? null,
              },
            }
          })
        })
      } catch {
        // 流式通道异常时回退到普通接口，复盘仍然可用
        result = await api.analyzeExpression(payload)
      }
      setAnalyzeResult(result)
      refreshRecords()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '复盘分析失败，请稍后再试')
    } finally {
      setAnalyzing(false)
    }
  }

  const viewRecord = async (record: ExpressionRecord) => {
    setError(null)
    try {
      const detail = await api.getExpressionRecord(record.id)
      if (detail.workflow) {
        setTranscribeResult(null)
        setAnalyzeResult({
          id: detail.id,
          asr_status: detail.asr_status,
          transcript: detail.transcript,
          metrics: detail.metrics,
          workflow: detail.workflow,
          model_name: detail.model_name,
        })
      } else {
        setAnalyzeResult(null)
        setTranscribeResult({
          id: detail.id,
          source: detail.source,
          transcript: detail.transcript,
          asr_status: detail.asr_status as ExpressionTranscribeResponse['asr_status'],
          asr_provider: detail.asr_provider,
          asr_error: detail.asr_error,
          audio: detail.metrics.audio ?? { available: false, unavailable_reason: '无音频指标', duration_ms: null, pause: null },
          speech: detail.metrics.speech,
        })
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '记录读取失败')
    }
  }

  const removeRecord = async (record: ExpressionRecord) => {
    if (!window.confirm('确定删除这条表达记录吗？删除后无法恢复。')) return
    try {
      await api.deleteExpressionRecord(record.id)
      if (transcribeResult?.id === record.id) setTranscribeResult(null)
      if (analyzeResult?.id === record.id) setAnalyzeResult(null)
      refreshRecords()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '删除失败')
    }
  }

  const asr = status?.asr
  const canAnalyzeText = text.trim().length >= 30

  return (
    <div className="space-y-10">
      <PageHeading
        kicker="洞察"
        title="听澜"
        subtitle="说出你的回答，观澜负责倾听：语速、停顿一目了然，三位分析师陪你把表达磨得更亮。"
        actions={<AiStatusBadge className="shrink-0" />}
      />

      {asr && !asr.configured ? <AsrGuideCard providers={asr.providers} /> : null}
      {asr?.configured ? (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-100 bg-emerald-50/60 px-4 py-2.5 text-sm text-emerald-800">
          <Volume2 className="h-4 w-4 shrink-0" aria-hidden="true" />
          语音转文字已就绪（{asr.provider_label}），录音与上传都可以直接生成转录。
        </div>
      ) : null}

      <section aria-label="开始一段表达">
        <SectionHead
          title="开始一段表达"
          note="录一段回答、上传音频文件，或直接粘贴回答文本。"
        />
        <div className="mt-4 space-y-5 rounded-xl border border-line bg-white p-5 sm:p-6">
          <div className="flex flex-wrap gap-2" role="tablist" aria-label="输入方式">
            {MODE_TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={mode === tab.key}
                onClick={() => setMode(tab.key)}
                className={
                  'flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50 ' +
                  (mode === tab.key
                    ? 'bg-brand-600 text-white shadow-sm'
                    : 'bg-slate-100 text-ink-soft hover:bg-slate-200 hover:text-ink')
                }
              >
                <tab.icon className="h-4 w-4" aria-hidden="true" />
                {tab.label}
              </button>
            ))}
          </div>

          {mode === 'record' ? (
            <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed border-brand-200 bg-brand-50/40 px-6 py-10">
              {recording ? (
                <>
                  <div className="flex items-center gap-3">
                    <span className="relative flex h-4 w-4">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-60" />
                      <span className="relative inline-flex h-4 w-4 rounded-full bg-red-500" />
                    </span>
                    <p className="text-lg font-semibold tabular-nums text-ink-strong">
                      正在倾听… {fmtDuration(recordSeconds * 1000)}
                    </p>
                  </div>
                  <p className="text-sm text-ink-soft">从容地说，说完再点停止。</p>
                  <Button variant="secondary" size="lg" onClick={stopRecording}>
                    <Square className="h-4 w-4" aria-hidden="true" />
                    结束录音
                  </Button>
                </>
              ) : (
                <>
                  <Mic className="h-10 w-10 text-brand-600" aria-hidden="true" />
                  <p className="text-sm text-ink-soft">点击开始，用一两分钟把你的回答完整说出来。</p>
                  <Button size="lg" onClick={() => void startRecording()} disabled={processing}>
                    <Mic className="h-4 w-4" aria-hidden="true" />
                    开始录音
                  </Button>
                </>
              )}
            </div>
          ) : null}

          {mode === 'upload' ? (
            <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed border-slate-300 px-6 py-10">
              <FileAudio className="h-10 w-10 text-ink-soft" aria-hidden="true" />
              <p className="text-sm text-ink-soft">
                支持 {status?.audio_limits.supported_extensions.join(' / ') ?? 'wav / mp3 / m4a / webm'} 格式，20MB 以内
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept={(status?.audio_limits.supported_extensions ?? ['.wav', '.mp3']).join(',')}
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0]
                  if (file) void submitAudio(file, file.name)
                  event.target.value = ''
                }}
              />
              <Button variant="secondary" onClick={() => fileInputRef.current?.click()} disabled={processing}>
                <Upload className="h-4 w-4" aria-hidden="true" />
                选择音频文件
              </Button>
            </div>
          ) : null}

          {mode === 'text' ? (
            <div className="space-y-3">
              <textarea
                value={text}
                onChange={(event) => setText(event.target.value)}
                rows={7}
                maxLength={20000}
                placeholder="把你的面试回答写在这里（至少 30 字），例如：我负责的项目是……我做了……最终效果是……"
                className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3.5 py-3 text-sm leading-relaxed text-ink placeholder:text-slate-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25"
              />
              <div className="flex items-center justify-between text-xs text-ink-soft">
                <span>{text.trim().length < 30 ? '再写一点点，满 30 字即可开始复盘' : '可以直接开始复盘了'}</span>
                <span>{text.length}/20000</span>
              </div>
              <div className="flex justify-end">
                <Button onClick={() => void runAnalyze({ text: text.trim() })} disabled={analyzing || !canAnalyzeText}>
                  {analyzing ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Sparkles className="h-4 w-4" aria-hidden="true" />
                  )}
                  {analyzing ? '分析师们正在阅读，约需一分钟…' : '开始深度复盘'}
                </Button>
              </div>
            </div>
          ) : null}

          {processing ? (
            <p className="flex items-center gap-2 rounded-lg border border-brand-100 bg-brand-50/60 px-4 py-3 text-sm text-brand-700">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              正在处理音频，马上就好…
            </p>
          ) : null}

          {error ? (
            <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </p>
          ) : null}
        </div>
      </section>

      {analyzing ? (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-brand-100 bg-brand-50/60 px-4 py-3">
          <span className="text-sm font-medium text-brand-700">分析师们正在阅读：</span>
          {ROLE_ORDER.map((role) => {
            const state = stepStates[role]
            const status: StepRunStatus = state?.status ?? 'pending'
            const label = state?.title ?? ROLE_LABELS[role]
            return (
              <span key={role} className="flex items-center gap-1.5 text-sm">
                {status === 'running' ? (
                  <Loader2 className="h-4 w-4 animate-spin text-brand-600" aria-hidden="true" />
                ) : status === 'completed' ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                ) : status === 'failed' || status === 'skipped' ? (
                  <CircleAlert className="h-4 w-4 text-amber-500" aria-hidden="true" />
                ) : (
                  <span className="h-2 w-2 rounded-full bg-slate-300" aria-hidden="true" />
                )}
                <span className={status === 'running' ? 'font-medium text-brand-700' : 'text-ink-soft'}>
                  {label}
                  {status === 'running' ? '阅读中…' : ''}
                </span>
              </span>
            )
          })}
        </div>
      ) : null}

      {transcribeResult ? (
        <TranscribeResultCard
          result={transcribeResult}
          analyzing={analyzing}
          onAnalyze={() => void runAnalyze({ analysisId: transcribeResult.id })}
        />
      ) : null}

      {analyzeResult ? <WorkflowResultCard result={analyzeResult} /> : null}

      <section aria-label="表达记录">
        <SectionHead title="表达记录" note="最近的录音、转录与复盘记录。" />
        <div className="mt-2">
          {records.length === 0 ? (
            <EmptyState
              icon={AudioLines}
              title="还没有表达记录"
              description="第一次录音或复盘后，记录会出现在这里。"
            />
          ) : (
            <ul className="divide-y divide-line/80">
              {records.map((record) => (
                <li key={record.id} className="flex flex-wrap items-center gap-3 py-3.5">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink">
                      {record.source === 'upload' ? record.filename || '上传音频' : record.source === 'text' ? '粘贴文本' : '录音'}
                    </p>
                    <p className="mt-0.5 text-xs text-ink-soft">{formatDateTime(record.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {record.has_transcript ? (
                      <Badge tone="brand">
                        <PenLine className="h-3 w-3" aria-hidden="true" /> 有转录
                      </Badge>
                    ) : (
                      <Badge tone="neutral">无转录</Badge>
                    )}
                    {record.has_workflow ? <Badge tone="accent">已复盘</Badge> : null}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Button variant="ghost" size="sm" onClick={() => void viewRecord(record)}>
                      查看
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => void removeRecord(record)} aria-label="删除记录">
                      <Trash2 className="h-4 w-4 text-ink-soft" aria-hidden="true" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  )
}

function AsrGuideCard({ providers }: { providers: NonNullable<ExpressionStatus['asr']>['providers'] }) {
  const entries = Object.values(providers)
  if (entries.length === 0) return null
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-5">
      <div className="flex items-start gap-3">
        <CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" aria-hidden="true" />
        <div className="space-y-3">
          <div>
            <p className="font-semibold text-amber-900">语音转文字还没有启用</p>
            <p className="mt-1 text-sm leading-relaxed text-amber-800">
              录音和上传仍然可用：时长、停顿这些客观指标照常计算。只是转录文字暂时生成不了——以下三种方式任选其一即可开启，全部免费或用现有账号。
            </p>
          </div>
          <ul className="space-y-2">
            {entries.map((info) => (
              <li key={info.label} className="rounded-lg bg-white/70 px-3.5 py-2.5 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-ink">{info.label}</span>
                  {info.configured ? (
                    <Badge tone="accent">已就绪</Badge>
                  ) : (
                    <Badge tone="neutral">待启用</Badge>
                  )}
                </div>
                {!info.configured && info.setup ? (
                  <p className="mt-1 text-xs leading-relaxed text-ink-soft">{info.setup}</p>
                ) : null}
              </li>
            ))}
          </ul>
          <p className="text-xs leading-relaxed text-amber-700">
            在 backend/.env 中按上面的指引配置后重启后端即可。配置之前，观澜不会生成任何假的转录。
          </p>
        </div>
      </div>
    </div>
  )
}

function TranscribeResultCard({
  result,
  analyzing,
  onAnalyze,
}: {
  result: ExpressionTranscribeResponse
  analyzing: boolean
  onAnalyze: () => void
}) {
  const { audio, speech } = result
  return (
    <section aria-label="转录与客观指标">
      <SectionHead
        title="转录与客观指标"
        note={
          result.asr_status === 'ok'
            ? '以下转录来自真实语音识别，指标全部本地计算。'
            : result.asr_status === 'not_configured'
              ? '语音转文字尚未启用：没有生成转录（也绝不会伪造），客观指标照常。'
              : '语音识别这次没有成功，客观指标照常返回。'
        }
        action={
          hasTranscriptValue(result) ? (
            <Button onClick={onAnalyze} disabled={analyzing}>
              {analyzing ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Sparkles className="h-4 w-4" aria-hidden="true" />
              )}
              {analyzing ? '分析师们正在阅读，约需一分钟…' : '用这段转录开始复盘'}
            </Button>
          ) : undefined
        }
      />
      <div className="mt-4 space-y-5">
        {result.transcript ? (
          <div className="rounded-xl bg-surface p-4">
            <p className="text-sm leading-relaxed text-ink">{result.transcript}</p>
          </div>
        ) : (
          <p className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-relaxed text-ink-soft">
            {result.asr_error ?? '本次没有生成转录。'}
          </p>
        )}

        <StatStrip
          items={[
            {
              label: '音频时长',
              value: audio.available ? fmtDuration(audio.duration_ms) : '—',
              hint: audio.available ? undefined : audio.unavailable_reason ?? '该格式暂不支持本地解析',
            },
            {
              label: '停顿次数',
              value: audio.pause ? String(audio.pause.pause_count) : '—',
              hint: audio.pause ? `最长一次 ${fmtDuration(audio.pause.longest_pause_ms)}` : undefined,
            },
            {
              label: '语速',
              value: speech.available && speech.speech_rate_cpm ? `${speech.speech_rate_cpm} 字/分` : '—',
              hint:
                speech.available
                  ? `共 ${speech.char_count} 字`
                  : speech.unavailable_reason ?? '需要真实转录后才能计算',
            },
            {
              label: '填充词',
              value: speech.available ? `${speech.filler_total} 处` : '—',
              hint:
                speech.available && Object.keys(speech.filler_words).length > 0
                  ? Object.entries(speech.filler_words)
                      .slice(0, 3)
                      .map(([word, count]) => `${word}×${count}`)
                      .join('、')
                  : '比如「嗯」「就是」「然后」',
            },
          ]}
        />

        {audio.pause ? (
          <p className="text-xs text-ink-soft">
            静音占比 {(audio.pause.silence_ratio * 100).toFixed(1)}%，累计停顿 {fmtDuration(audio.pause.total_pause_ms)}。
          </p>
        ) : null}
      </div>
    </section>
  )
}

function hasTranscriptValue(result: ExpressionTranscribeResponse): boolean {
  return Boolean(result.transcript)
}

function WorkflowResultCard({ result }: { result: ExpressionWorkflowResponse }) {
  const workflow = result.workflow
  const statusLabel =
    workflow.status === 'completed' ? '复盘完成' : workflow.status === 'partial' ? '部分完成' : '复盘未完成'
  return (
    <section aria-label="深度复盘">
      <SectionHead
        title="深度复盘"
        note={`三位分析师依次阅读你的回答：${statusLabel}${result.model_name ? `（${result.model_name}）` : ''}`}
      />
      <div className="mt-2 space-y-4">
        {result.transcript ? (
          <details className="rounded-xl bg-surface px-4 py-3">
            <summary className="cursor-pointer text-sm font-medium text-ink">本次分析的文本</summary>
            <p className="mt-2 text-sm leading-relaxed text-ink-soft">{result.transcript}</p>
          </details>
        ) : null}

        <div className="divide-y divide-line/80">
          {workflow.steps.map((step) => (
            <WorkflowStepCard key={step.role} step={step} />
          ))}
        </div>
      </div>
    </section>
  )
}

function WorkflowStepCard({ step }: { step: WorkflowStep }) {
  if (step.status === 'completed' && step.output) {
    return (
      <div className="py-5 first:pt-0 last:pb-0">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />
          <span className="font-semibold text-ink-strong">{step.title}</span>
          <span className="text-xs text-ink-soft">
            用时 {fmtDuration(step.elapsed_ms)}
            {step.attempts > 1 ? ` · 重试 ${step.attempts - 1} 次后完成` : ''}
          </span>
        </div>
        {step.role === 'structure_analyst' ? <StructureOutputView output={step.output} /> : null}
        {step.role === 'depth_analyst' ? <DepthOutputView output={step.output} /> : null}
        {step.role === 'expression_coach' ? <CoachOutputView output={step.output} /> : null}
      </div>
    )
  }
  if (step.status === 'skipped') {
    return (
      <div className="py-5 text-sm text-ink-soft first:pt-0 last:pb-0">
        <p className="font-medium text-ink">{step.title}：未执行</p>
        <p className="mt-1 leading-relaxed">{step.error ?? '依赖的步骤未完成。'}</p>
      </div>
    )
  }
  return (
    <div className="py-5 first:pt-0 last:pb-0">
      <div className="flex items-center gap-2">
        <CircleAlert className="h-4 w-4 text-red-500" aria-hidden="true" />
        <span className="font-semibold text-red-700">{step.title}：这一步没有成功</span>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-red-600">{step.error ?? '未知错误'}</p>
    </div>
  )
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function asStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

function asIssues(value: unknown): IssueItem[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      type: asString(item.type),
      evidence: asString(item.evidence),
      suggestion: asString(item.suggestion),
    }))
}

function ScorePill({ score }: { score: number }) {
  const tone = score >= 8 ? 'text-emerald-600' : score >= 6 ? 'text-amber-600' : 'text-red-500'
  return (
    <span className={`text-2xl font-bold tabular-nums ${tone}`}>
      {score}
      <span className="text-sm font-medium text-ink-soft"> / 10</span>
    </span>
  )
}

function IssueList({ issues }: { issues: IssueItem[] }) {
  if (issues.length === 0) return null
  return (
    <ul className="space-y-2">
      {issues.map((issue, index) => (
        <li key={index} className="rounded-lg bg-amber-50/60 px-3.5 py-2.5 text-sm">
          <p className="font-medium text-ink">{issue.type || '待改进'}</p>
          {issue.evidence ? <p className="mt-0.5 text-xs leading-relaxed text-ink-soft">原文：「{issue.evidence}」</p> : null}
          {issue.suggestion ? <p className="mt-0.5 text-xs leading-relaxed text-brand-700">建议：{issue.suggestion}</p> : null}
        </li>
      ))}
    </ul>
  )
}

function StructureOutputView({ output }: { output: Record<string, unknown> }) {
  const score = asNumber(output.logic_score)
  const markers = asStringList(output.discourse_markers)
  const issues = asIssues(output.issues)
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        {score !== null ? <ScorePill score={score} /> : null}
        <span className="text-xs text-ink-soft">逻辑结构得分</span>
      </div>
      {asString(output.structure_summary) ? (
        <p className="text-sm leading-relaxed text-ink">{asString(output.structure_summary)}</p>
      ) : null}
      {markers.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {markers.map((marker) => (
            <span key={marker} className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs text-brand-700">
              {marker}
            </span>
          ))}
        </div>
      ) : null}
      <IssueList issues={issues} />
    </div>
  )
}

function DepthOutputView({ output }: { output: Record<string, unknown> }) {
  const score = asNumber(output.depth_score)
  const examples = asStringList(output.concrete_examples)
  const missing = asStringList(output.missing_substance)
  const issues = asIssues(output.issues)
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        {score !== null ? <ScorePill score={score} /> : null}
        <span className="text-xs text-ink-soft">内容深度得分</span>
      </div>
      {examples.length > 0 ? (
        <div>
          <p className="mb-1 text-xs font-medium text-ink-soft">有具体例证支撑</p>
          <ul className="space-y-1">
            {examples.map((example) => (
              <li key={example} className="rounded-lg bg-emerald-50/70 px-3.5 py-2 text-sm text-emerald-800">
                {example}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {missing.length > 0 ? (
        <div>
          <p className="mb-1 text-xs font-medium text-ink-soft">还缺少的实质内容</p>
          <div className="flex flex-wrap gap-1.5">
            {missing.map((item) => (
              <span key={item} className="rounded-full bg-red-50 px-2.5 py-0.5 text-xs text-red-700 ring-1 ring-inset ring-red-600/10">
                {item}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      <IssueList issues={issues} />
    </div>
  )
}

function CoachOutputView({ output }: { output: Record<string, unknown> }) {
  const fixes = Array.isArray(output.priority_fixes)
    ? output.priority_fixes
        .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
        .map((item) => ({ title: asString(item.title), detail: asString(item.detail) }))
        .filter((item) => item.title)
    : []
  const drills = asStringList(output.drill_suggestions)
  return (
    <div className="space-y-3">
      {asString(output.overall_assessment) ? (
        <p className="text-sm leading-relaxed text-ink">{asString(output.overall_assessment)}</p>
      ) : null}
      {fixes.length > 0 ? (
        <div>
          <p className="mb-1 text-xs font-medium text-ink-soft">优先改进</p>
          <ul className="space-y-1.5">
            {fixes.map((fix, index) => (
              <li key={fix.title} className="rounded-lg bg-brand-50/70 px-3.5 py-2 text-sm">
                <span className="font-semibold text-brand-700">{index + 1}. {fix.title}</span>
                {fix.detail ? <span className="text-ink-soft"> — {fix.detail}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {drills.length > 0 ? (
        <div>
          <p className="mb-1 text-xs font-medium text-ink-soft">今天就能练</p>
          <ul className="space-y-1">
            {drills.map((drill) => (
              <li key={drill} className="flex items-start gap-2 text-sm text-ink">
                <History className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" aria-hidden="true" />
                {drill}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
