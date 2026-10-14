import { BookOpen, Download, ExternalLink, FileDown, FileUp, History, Loader2, Plus, Save, ScanSearch, Sparkles, Trash2, X } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { motion } from 'motion/react'
import { api, ApiError } from '../api/client'
import { AurelTaskStatus, useAsyncTask } from '../components/aurel-progress'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeading, SectionHead, StatStrip } from '../components/editorial/Editorial'
import type {
  ExperienceEntryData,
  JobAnalysisSummary,
  ResumeBasicsData,
  ResumeContentData,
  ResumeDetail,
  ResumeOptimizeForJobResponse,
  ResumePolishResponse,
  ResumeSummary,
  ResumeTemplate,
  ResumeTemplateSource,
  ResumeVersionDetail,
  ResumeVersionSummary,
} from '../types'

// ---------- 常量与工具 ----------

const inputClass =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-ink placeholder:text-slate-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25'
const textareaClass = `${inputClass} resize-y leading-relaxed`

const FALLBACK_ACCENT = '#4D83D6'

const ACCEPTED_SUFFIXES = ['.pdf', '.docx', '.txt', '.md']

const DEFAULT_SECTION_ORDER = [
  'summary',
  'education',
  'work',
  'projects',
  'skills',
  'certificates',
  'awards',
  'links',
]

const SECTION_TITLES: Record<string, string> = {
  summary: '个人概述',
  work: '实习与工作经历',
  projects: '项目经历',
  education: '教育经历',
  skills: '技能与工具',
  certificates: '证书与语言能力',
  awards: '奖项与其他经历',
  links: '作品与链接',
}

type PolishSection = 'summary' | 'work' | 'projects' | 'awards'
type ListKey = 'work' | 'projects'

const POLISH_SECTIONS: { key: PolishSection; label: string }[] = [
  { key: 'summary', label: '个人概述' },
  { key: 'work', label: '工作经历' },
  { key: 'projects', label: '项目经历' },
  { key: 'awards', label: '奖项' },
]

const toMessage = (err: unknown, fallback: string): string => {
  if (err instanceof ApiError) return err.message
  if (err instanceof Error && err.message) return err.message
  return fallback
}

const formatDateTime = (iso: string): string => {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString('zh-CN')
}

const isHttpUrl = (value: string): boolean => /^https?:\/\//i.test(value.trim())

/** 供新建简历使用：仅空字段与空数组，不预置任何示例内容。 */
const emptyContent = (): ResumeContentData => ({
  basics: { name: '', phone: '', email: '', location: '', links: '', summary: '' },
  education: [],
  work: [],
  projects: [],
  skills: [],
  certificates: [],
  awards: [],
})

const normalizeExperience = (list: ExperienceEntryData[] | undefined): ExperienceEntryData[] =>
  (list ?? []).map((entry) => ({
    name: entry.name ?? '',
    role: entry.role ?? '',
    start: entry.start ?? '',
    end: entry.end ?? '',
    link: entry.link ?? '',
    highlights: (entry.highlights ?? []).map((item) => item),
  }))

/** 把后端返回的内容补齐为全字段结构，编辑器输入始终受控。 */
const normalizeContent = (raw: ResumeContentData | undefined): ResumeContentData => ({
  basics: {
    name: raw?.basics?.name ?? '',
    phone: raw?.basics?.phone ?? '',
    email: raw?.basics?.email ?? '',
    location: raw?.basics?.location ?? '',
    links: raw?.basics?.links ?? '',
    summary: raw?.basics?.summary ?? '',
  },
  education: (raw?.education ?? []).map((entry) => ({
    school: entry.school ?? '',
    degree: entry.degree ?? '',
    major: entry.major ?? '',
    start: entry.start ?? '',
    end: entry.end ?? '',
    details: entry.details ?? '',
  })),
  work: normalizeExperience(raw?.work),
  projects: normalizeExperience(raw?.projects),
  skills: (raw?.skills ?? []).map((entry) => ({
    name: entry.name ?? '',
    level: entry.level ?? '',
    detail: entry.detail ?? '',
  })),
  certificates: (raw?.certificates ?? []).map((entry) => ({
    name: entry.name ?? '',
    issuer: entry.issuer ?? '',
    date: entry.date ?? '',
  })),
  awards: (raw?.awards ?? []).map((entry) => ({
    name: entry.name ?? '',
    issuer: entry.issuer ?? '',
    date: entry.date ?? '',
    detail: entry.detail ?? '',
  })),
})

const rangeText = (start?: string, end?: string): string => {
  const s = start?.trim() ?? ''
  const e = end?.trim() ?? ''
  if (!s && !e) return ''
  return `${s || '待补充'} – ${e || '待补充'}`
}

// ---------- 表单基础组件 ----------

interface FieldInputProps {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  maxLength?: number
  type?: 'text' | 'email' | 'tel' | 'url'
}

function FieldInput({ label, value, onChange, placeholder, maxLength, type = 'text' }: FieldInputProps) {
  const id = useId()
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-ink-soft">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        maxLength={maxLength}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className={inputClass}
      />
    </div>
  )
}

interface FieldTextareaProps {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  rows?: number
  maxLength?: number
}

function FieldTextarea({
  label,
  value,
  onChange,
  placeholder,
  rows = 3,
  maxLength,
}: FieldTextareaProps) {
  const id = useId()
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-ink-soft">
        {label}
      </label>
      <textarea
        id={id}
        value={value}
        rows={rows}
        maxLength={maxLength}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className={textareaClass}
      />
    </div>
  )
}

function DeleteIconButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/50"
    >
      <Trash2 className="h-4 w-4" aria-hidden="true" />
    </button>
  )
}

// ---------- 结构化编辑器（七节） ----------

interface EditorProps {
  content: ResumeContentData
  onChange: (next: ResumeContentData) => void
}

function BasicsEditor({ content, onChange }: EditorProps) {
  const basics: ResumeBasicsData = content.basics ?? {}
  const update = (patch: Partial<ResumeBasicsData>) => {
    onChange({ ...content, basics: { ...basics, ...patch } })
  }
  return (
    <section className="space-y-3 p-5 sm:p-6">
      <div>
        <h3 className="text-sm font-semibold text-ink-strong">基本资料</h3>
        <p className="mt-0.5 text-xs text-ink-soft">
          请填写真实联系方式与概述；留空的内容在预览中会显示为待补充。
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <FieldInput
          label="姓名"
          value={basics.name ?? ''}
          onChange={(value) => update({ name: value })}
          placeholder="待补充：姓名"
          maxLength={40}
        />
        <FieldInput
          label="电话"
          value={basics.phone ?? ''}
          onChange={(value) => update({ phone: value })}
          placeholder="待补充：手机号"
          maxLength={30}
        />
        <FieldInput
          label="邮箱"
          type="email"
          value={basics.email ?? ''}
          onChange={(value) => update({ email: value })}
          placeholder="待补充：邮箱"
          maxLength={80}
        />
        <FieldInput
          label="所在城市"
          value={basics.location ?? ''}
          onChange={(value) => update({ location: value })}
          placeholder="待补充：城市"
          maxLength={40}
        />
        <FieldInput
          label="作品链接"
          value={basics.links ?? ''}
          onChange={(value) => update({ links: value })}
          placeholder="待补充：主页 / 仓库链接，可多行"
          maxLength={300}
        />
      </div>
      <FieldTextarea
        label="个人概述"
        value={basics.summary ?? ''}
        onChange={(value) => update({ summary: value })}
        placeholder="待补充：用三五句真实经历概括你的定位与优势"
        rows={4}
        maxLength={800}
      />
    </section>
  )
}

function EducationEditor({ content, onChange }: EditorProps) {
  const entries = content.education ?? []
  const update = (index: number, patch: Partial<(typeof entries)[number]>) => {
    onChange({
      ...content,
      education: entries.map((entry, i) => (i === index ? { ...entry, ...patch } : entry)),
    })
  }
  return (
    <section className="p-5 sm:p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-ink-strong">教育经历</h3>
          <p className="mt-0.5 text-xs text-ink-soft">
            按真实学历填写；未涵盖的培训经历可写在「奖项与其他经历」。
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onChange({ ...content, education: [...entries, {}] })}
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          添加条目
        </Button>
      </div>
      {entries.length === 0 ? (
        <p className="mt-3 text-xs text-ink-soft">
          本节暂无内容，点击「添加条目」开始填写真实教育经历。
        </p>
      ) : (
        <div className="mt-4 divide-y divide-line/70">
          {entries.map((entry, index) => (
            <div key={index} className="py-4 first:pt-0 last:pb-0">
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs font-semibold text-ink-soft">第 {index + 1} 条</span>
                <DeleteIconButton
                  label={`删除第 ${index + 1} 条教育经历`}
                  onClick={() =>
                    onChange({ ...content, education: entries.filter((_, i) => i !== index) })
                  }
                />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <FieldInput
                  label="学校"
                  value={entry.school ?? ''}
                  onChange={(value) => update(index, { school: value })}
                  placeholder="待补充：学校名称"
                  maxLength={60}
                />
                <FieldInput
                  label="学历 / 学位"
                  value={entry.degree ?? ''}
                  onChange={(value) => update(index, { degree: value })}
                  placeholder="待补充：如 本科"
                  maxLength={40}
                />
                <FieldInput
                  label="专业"
                  value={entry.major ?? ''}
                  onChange={(value) => update(index, { major: value })}
                  placeholder="待补充：专业名称"
                  maxLength={60}
                />
                <div className="grid grid-cols-2 gap-3">
                  <FieldInput
                    label="开始"
                    value={entry.start ?? ''}
                    onChange={(value) => update(index, { start: value })}
                    placeholder="如 2021.09"
                    maxLength={20}
                  />
                  <FieldInput
                    label="结束"
                    value={entry.end ?? ''}
                    onChange={(value) => update(index, { end: value })}
                    placeholder="如 2025.06"
                    maxLength={20}
                  />
                </div>
              </div>
              <div className="mt-3">
                <FieldTextarea
                  label="补充说明（选填）"
                  value={entry.details ?? ''}
                  onChange={(value) => update(index, { details: value })}
                  placeholder="待补充：课程方向、成绩排名等真实信息"
                  rows={2}
                  maxLength={300}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

interface ExperienceEditorProps extends EditorProps {
  sectionKey: ListKey
}

function ExperienceEditor({ sectionKey, content, onChange }: ExperienceEditorProps) {
  const entries = content[sectionKey] ?? []
  const meta =
    sectionKey === 'work'
      ? {
          title: '实习与工作经历',
          description: '写清公司、职位、时间段与要点；要点建议用动词开头、带真实结果。',
        }
      : {
          title: '项目经历',
          description: '写清项目名称、你的角色与关键产出；可附项目链接。',
        }

  const setList = (list: ExperienceEntryData[]) => {
    if (sectionKey === 'work') onChange({ ...content, work: list })
    else onChange({ ...content, projects: list })
  }
  const update = (index: number, patch: Partial<ExperienceEntryData>) => {
    setList(entries.map((entry, i) => (i === index ? { ...entry, ...patch } : entry)))
  }

  return (
    <section className="p-5 sm:p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-ink-strong">{meta.title}</h3>
          <p className="mt-0.5 text-xs text-ink-soft">{meta.description}</p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setList([...entries, { highlights: [''] }])}
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          添加条目
        </Button>
      </div>
      {entries.length === 0 ? (
        <p className="mt-3 text-xs text-ink-soft">
          本节暂无内容，点击「添加条目」开始填写真实经历。
        </p>
      ) : (
        <div className="mt-4 divide-y divide-line/70">
          {entries.map((entry, index) => (
            <div key={index} className="py-4 first:pt-0 last:pb-0">
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs font-semibold text-ink-soft">第 {index + 1} 条</span>
                <DeleteIconButton
                  label={`删除第 ${index + 1} 条${meta.title}`}
                  onClick={() => setList(entries.filter((_, i) => i !== index))}
                />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <FieldInput
                  label={sectionKey === 'work' ? '公司 / 组织' : '项目名称'}
                  value={entry.name ?? ''}
                  onChange={(value) => update(index, { name: value })}
                  placeholder="待补充：名称"
                  maxLength={80}
                />
                <FieldInput
                  label="职位 / 角色"
                  value={entry.role ?? ''}
                  onChange={(value) => update(index, { role: value })}
                  placeholder="待补充：角色"
                  maxLength={60}
                />
                <div className="grid grid-cols-2 gap-3">
                  <FieldInput
                    label="开始"
                    value={entry.start ?? ''}
                    onChange={(value) => update(index, { start: value })}
                    placeholder="如 2024.06"
                    maxLength={20}
                  />
                  <FieldInput
                    label="结束"
                    value={entry.end ?? ''}
                    onChange={(value) => update(index, { end: value })}
                    placeholder="如 2024.12 或 至今"
                    maxLength={20}
                  />
                </div>
                <FieldInput
                  label="链接（选填）"
                  value={entry.link ?? ''}
                  onChange={(value) => update(index, { link: value })}
                  placeholder="待补充：项目 / 仓库链接"
                  maxLength={300}
                />
              </div>
              <div className="mt-3">
                <p className="mb-1 text-xs font-medium text-ink-soft">经历要点（每条一行）</p>
                {(entry.highlights ?? []).map((highlight, hlIndex) => (
                  <div key={hlIndex} className="mb-2 flex items-start gap-2">
                    <textarea
                      value={highlight}
                      rows={2}
                      maxLength={300}
                      placeholder="待补充：一条经历要点"
                      onChange={(event) =>
                        update(index, {
                          highlights: (entry.highlights ?? []).map((item, j) =>
                            j === hlIndex ? event.target.value : item,
                          ),
                        })
                      }
                      className={textareaClass}
                    />
                    <button
                      type="button"
                      aria-label={`删除第 ${hlIndex + 1} 条要点`}
                      onClick={() =>
                        update(index, {
                          highlights: (entry.highlights ?? []).filter((_, j) => j !== hlIndex),
                        })
                      }
                      className="mt-1 rounded-md p-1.5 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/50"
                    >
                      <X className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                ))}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    update(index, { highlights: [...(entry.highlights ?? []), ''] })
                  }
                >
                  <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                  添加要点
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function SkillsEditor({ content, onChange }: EditorProps) {
  const entries = content.skills ?? []
  const update = (index: number, patch: Partial<(typeof entries)[number]>) => {
    onChange({
      ...content,
      skills: entries.map((entry, i) => (i === index ? { ...entry, ...patch } : entry)),
    })
  }
  return (
    <section className="p-5 sm:p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-ink-strong">技能与工具</h3>
          <p className="mt-0.5 text-xs text-ink-soft">只列出你真实掌握的技能；程度与说明据实填写。</p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => onChange({ ...content, skills: [...entries, {}] })}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          添加条目
        </Button>
      </div>
      {entries.length === 0 ? (
        <p className="mt-3 text-xs text-ink-soft">
          本节暂无内容，点击「添加条目」开始填写真实技能。
        </p>
      ) : (
        <div className="mt-4 divide-y divide-line/70">
          {entries.map((entry, index) => (
            <div key={index} className="py-4 first:pt-0 last:pb-0">
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs font-semibold text-ink-soft">第 {index + 1} 项</span>
                <DeleteIconButton
                  label={`删除第 ${index + 1} 项技能`}
                  onClick={() => onChange({ ...content, skills: entries.filter((_, i) => i !== index) })}
                />
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <FieldInput
                  label="技能 / 工具"
                  value={entry.name ?? ''}
                  onChange={(value) => update(index, { name: value })}
                  placeholder="待补充：名称"
                  maxLength={40}
                />
                <FieldInput
                  label="程度"
                  value={entry.level ?? ''}
                  onChange={(value) => update(index, { level: value })}
                  placeholder="待补充：如 熟练"
                  maxLength={20}
                />
                <FieldInput
                  label="说明（选填）"
                  value={entry.detail ?? ''}
                  onChange={(value) => update(index, { detail: value })}
                  placeholder="待补充：使用场景"
                  maxLength={120}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function CertificatesEditor({ content, onChange }: EditorProps) {
  const entries = content.certificates ?? []
  const update = (index: number, patch: Partial<(typeof entries)[number]>) => {
    onChange({
      ...content,
      certificates: entries.map((entry, i) => (i === index ? { ...entry, ...patch } : entry)),
    })
  }
  return (
    <section className="p-5 sm:p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-ink-strong">证书与语言</h3>
          <p className="mt-0.5 text-xs text-ink-soft">填写真实取得的证书或语言成绩，没有可留空本节。</p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onChange({ ...content, certificates: [...entries, {}] })}
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          添加条目
        </Button>
      </div>
      {entries.length === 0 ? (
        <p className="mt-3 text-xs text-ink-soft">
          本节暂无内容，点击「添加条目」开始填写真实证书。
        </p>
      ) : (
        <div className="mt-4 divide-y divide-line/70">
          {entries.map((entry, index) => (
            <div key={index} className="py-4 first:pt-0 last:pb-0">
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs font-semibold text-ink-soft">第 {index + 1} 项</span>
                <DeleteIconButton
                  label={`删除第 ${index + 1} 项证书`}
                  onClick={() =>
                    onChange({ ...content, certificates: entries.filter((_, i) => i !== index) })
                  }
                />
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <FieldInput
                  label="证书 / 语言"
                  value={entry.name ?? ''}
                  onChange={(value) => update(index, { name: value })}
                  placeholder="待补充：名称"
                  maxLength={60}
                />
                <FieldInput
                  label="颁发机构"
                  value={entry.issuer ?? ''}
                  onChange={(value) => update(index, { issuer: value })}
                  placeholder="待补充：机构"
                  maxLength={60}
                />
                <FieldInput
                  label="取得时间"
                  value={entry.date ?? ''}
                  onChange={(value) => update(index, { date: value })}
                  placeholder="如 2024.10"
                  maxLength={20}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function AwardsEditor({ content, onChange }: EditorProps) {
  const entries = content.awards ?? []
  const update = (index: number, patch: Partial<(typeof entries)[number]>) => {
    onChange({
      ...content,
      awards: entries.map((entry, i) => (i === index ? { ...entry, ...patch } : entry)),
    })
  }
  return (
    <section className="p-5 sm:p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-ink-strong">奖项与其他经历</h3>
          <p className="mt-0.5 text-xs text-ink-soft">奖学金、竞赛、志愿、社团等真实经历都可以写在这里。</p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => onChange({ ...content, awards: [...entries, {}] })}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          添加条目
        </Button>
      </div>
      {entries.length === 0 ? (
        <p className="mt-3 text-xs text-ink-soft">
          本节暂无内容，点击「添加条目」开始填写真实奖项与经历。
        </p>
      ) : (
        <div className="mt-4 divide-y divide-line/70">
          {entries.map((entry, index) => (
            <div key={index} className="py-4 first:pt-0 last:pb-0">
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs font-semibold text-ink-soft">第 {index + 1} 条</span>
                <DeleteIconButton
                  label={`删除第 ${index + 1} 条奖项`}
                  onClick={() => onChange({ ...content, awards: entries.filter((_, i) => i !== index) })}
                />
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <FieldInput
                  label="名称"
                  value={entry.name ?? ''}
                  onChange={(value) => update(index, { name: value })}
                  placeholder="待补充：奖项 / 经历名称"
                  maxLength={80}
                />
                <FieldInput
                  label="颁发方 / 组织"
                  value={entry.issuer ?? ''}
                  onChange={(value) => update(index, { issuer: value })}
                  placeholder="待补充：机构"
                  maxLength={60}
                />
                <FieldInput
                  label="时间"
                  value={entry.date ?? ''}
                  onChange={(value) => update(index, { date: value })}
                  placeholder="如 2024.05"
                  maxLength={20}
                />
              </div>
              <div className="mt-3">
                <FieldTextarea
                  label="说明（选填）"
                  value={entry.detail ?? ''}
                  onChange={(value) => update(index, { detail: value })}
                  placeholder="待补充：背景与结果"
                  rows={2}
                  maxLength={300}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

// ---------- 模板选择 ----------

function TemplatePicker({
  templates,
  value,
  onChange,
}: {
  templates: ResumeTemplate[]
  value: string
  onChange: (id: string) => void
}) {
  if (templates.length === 0) {
    return <p className="text-xs text-ink-soft">模板列表加载失败或暂不可用，保存时将沿用当前模板。</p>
  }
  return (
    <div className="flex flex-wrap gap-2">
      {templates.map((template) => {
        const active = template.id === value
        return (
          <button
            key={template.id}
            type="button"
            aria-pressed={active}
            title={template.description}
            onClick={() => onChange(template.id)}
            className={`flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50 ${
              active
                ? 'border-brand-600 bg-brand-50 text-brand-700'
                : 'border-line bg-white text-ink-soft hover:border-brand-600/50 hover:text-ink'
            }`}
          >
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: template.accent || FALLBACK_ACCENT }}
            />
            {template.name}
          </button>
        )
      })}
    </div>
  )
}

// ---------- 岗位适配诊断（只讲方法，不代写事实） ----------

const DIAG_JD_MIN_LENGTH = 30

function JobFitDiagnosisPanel({ resumeId, resumeTitle }: { resumeId: number; resumeTitle: string }) {
  const [mode, setMode] = useState<'history' | 'jd'>('history')
  const [analyses, setAnalyses] = useState<JobAnalysisSummary[] | null>(null)
  const [analysesLoading, setAnalysesLoading] = useState(true)
  const [analysesError, setAnalysesError] = useState<string | null>(null)
  const [analysisId, setAnalysisId] = useState<number | null>(null)
  const [jdText, setJdText] = useState('')
  const [position, setPosition] = useState('')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<ResumeOptimizeForJobResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    // loading 初始即为 true，无需在 effect 内同步置位
    api.listJobAnalyses()
      .then((list) => {
        if (active) setAnalyses(list)
      })
      .catch((err: unknown) => {
        if (active) setAnalysesError(toMessage(err, '知岗分析历史加载失败，可改用粘贴 JD 方式'))
      })
      .finally(() => {
        if (active) setAnalysesLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const readyAnalyses = (analyses ?? []).filter((item) => item.status === 'ready')
  const jdReady = jdText.trim().length >= DIAG_JD_MIN_LENGTH
  const canRun = mode === 'history' ? analysisId !== null : jdReady

  const handleRun = async () => {
    if (running || !canRun) return
    setRunning(true)
    setError(null)
    setResult(null)
    try {
      const response = await api.optimizeResumeForJob(resumeId, {
        ...(mode === 'history' && analysisId !== null ? { jobAnalysisId: analysisId } : {}),
        ...(mode === 'jd' ? { jdText: jdText.trim(), position: position.trim() } : {}),
      })
      setResult(response)
    } catch (err) {
      setError(toMessage(err, '诊断失败，请稍后再试'))
    } finally {
      setRunning(false)
    }
  }

  const modePillClass = (active: boolean) =>
    `rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50 ${
      active ? 'bg-brand-600 text-white' : 'bg-mist text-ink-soft hover:bg-shallow hover:text-ink'
    }`

  return (
    <div className="space-y-4 rounded-lg border border-line bg-mist p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="flex items-center gap-1.5 text-sm font-semibold text-ink-strong">
          <ScanSearch className="h-4 w-4 text-brand-600" aria-hidden="true" />
          岗位适配诊断
        </h4>
        <span className="text-xs text-ink-soft">诊断目标：{resumeTitle}</span>
      </div>

      <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800">
        诊断只指出改进方法，不会自动改写简历，也不会编造公司、经历、项目、奖项或数字指标；需要补充的内容，请由你确认真实性后手动编辑应用。
      </p>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          aria-pressed={mode === 'history'}
          onClick={() => setMode('history')}
          className={modePillClass(mode === 'history')}
        >
          从知岗分析历史选择
        </button>
        <button
          type="button"
          aria-pressed={mode === 'jd'}
          onClick={() => setMode('jd')}
          className={modePillClass(mode === 'jd')}
        >
          粘贴 JD 文本
        </button>
      </div>

      {mode === 'history' ? (
        <div>
          {analysesLoading ? (
            <p className="flex items-center gap-2 text-xs text-ink-soft">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              正在读取知岗分析历史…
            </p>
          ) : analysesError ? (
            <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              {analysesError}
            </p>
          ) : readyAnalyses.length === 0 ? (
            <EmptyState
              icon={ScanSearch}
              title="暂无已完成的知岗分析"
              description="可先到「知岗」页完成一次岗位分析，或改用粘贴 JD 文本的方式诊断。"
              action={
                <Button size="sm" variant="secondary" onClick={() => setMode('jd')}>
                  改为粘贴 JD 文本
                </Button>
              }
              className="py-6"
            />
          ) : (
            <ul className="max-h-64 space-y-1.5 overflow-y-auto pr-1">
              {readyAnalyses.map((item) => {
                const active = analysisId === item.id
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      aria-pressed={active}
                      onClick={() => setAnalysisId(item.id)}
                      className={`w-full rounded-lg border px-3 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50 ${
                        active ? 'border-brand-600 bg-white' : 'border-line bg-white/70 hover:border-brand-600/50'
                      }`}
                    >
                      <span className={`block truncate text-sm font-medium ${active ? 'text-brand-700' : 'text-ink-strong'}`}>
                        {item.title}
                      </span>
                      <span className="mt-0.5 block text-xs text-ink-soft">分析于 {formatDateTime(item.created_at)}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <FieldTextarea
            label="目标岗位 JD 原文"
            value={jdText}
            onChange={setJdText}
            placeholder={`粘贴招聘描述全文（至少 ${DIAG_JD_MIN_LENGTH} 字符），诊断会与简历文本逐项比对`}
            rows={6}
            maxLength={8000}
          />
          {jdText.trim().length > 0 && !jdReady ? (
            <p className="text-xs text-amber-700">
              JD 正文目前 {jdText.trim().length} 字符，不足 {DIAG_JD_MIN_LENGTH} 字符，请补全后再诊断。
            </p>
          ) : null}
          <FieldInput
            label="岗位名称（选填）"
            value={position}
            onChange={setPosition}
            placeholder="例如：数据分析实习生"
            maxLength={60}
          />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={() => void handleRun()} disabled={running || !canRun}>
          {running ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <ScanSearch className="h-4 w-4" aria-hidden="true" />
          )}
          {running ? '诊断进行中…' : '开始诊断'}
        </Button>
        {result || error ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setResult(null)
              setError(null)
            }}
          >
            清空结果
          </Button>
        ) : null}
      </div>

      {error ? (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      ) : null}

      {result ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-ink-strong">
              诊断结果{result.position.trim() ? ` · ${result.position.trim()}` : ''}
            </p>
            {result.model_name ? <Badge tone="brand">{result.model_name}</Badge> : null}
          </div>

          <div className="rounded-lg bg-white p-4 ring-1 ring-inset ring-line">
            <p className="text-xs font-semibold text-ink-strong">关键词缺口</p>
            <p className="mt-0.5 text-xs text-ink-soft">由岗位要求与简历文本比对得出，可复算。</p>
            {result.keyword_gaps.length === 0 ? (
              <p className="mt-2 text-xs text-ink-soft">未发现明显关键词缺口。</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {result.keyword_gaps.map((gap, index) => (
                  <li key={`${gap.skill}-${index}`} className="rounded-md bg-mist/60 p-2.5">
                    <Badge tone="brand">{gap.skill}</Badge>
                    {gap.job_evidence ? (
                      <p className="mt-1.5 text-xs leading-relaxed text-ink-soft">岗位要求依据：{gap.job_evidence}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-lg bg-white p-4 ring-1 ring-inset ring-line">
            <p className="text-xs font-semibold text-ink-strong">表达待补证据</p>
            <p className="mt-0.5 text-xs text-ink-soft">
              以下表达逐字摘自简历原文；真实依据只有你自己能补充，确认属实后再手动写入简历。
            </p>
            {result.weak_points.length === 0 ? (
              <p className="mt-2 text-xs text-ink-soft">未发现明显缺少证据支撑的表达。</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {result.weak_points.map((item, index) => (
                  <li key={index} className="rounded-md bg-mist/60 p-2.5">
                    <p className="text-xs leading-relaxed text-ink">「{item.text}」</p>
                    <p className="mt-1 text-xs leading-relaxed text-ink-soft">原因：{item.reason}</p>
                    <p className="mt-1 text-xs leading-relaxed text-brand-700">追问：{item.question}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-lg bg-white p-4 ring-1 ring-inset ring-line">
            <p className="text-xs font-semibold text-ink-strong">结构建议</p>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink">{result.restructure_advice}</p>
            <p className="mt-2 text-xs text-ink-soft">
              可参考 STAR（情境-任务-行动-结果）或 CAR（挑战-行动-结果）方法组织表述。
            </p>
          </div>

          <p className="text-xs leading-relaxed text-ink-soft">
            再次提醒：以上仅为改进建议，简历内容仍以你确认的真实信息为准。
          </p>
        </div>
      ) : null}
    </div>
  )
}

// ---------- 简历预览（纯静态，与导出结构一致） ----------

function PreviewSection({ label, accent, children }: { label: string; accent: string; children: React.ReactNode }) {
  return (
    <section>
      <h4
        className="mb-3 border-l-4 pl-2.5 text-sm font-bold"
        style={{ color: accent, borderColor: accent }}
      >
        {label}
      </h4>
      {children}
    </section>
  )
}

function PreviewEmptyHint() {
  return <p className="text-xs text-ink-soft">待补充</p>
}

function ResumePreview({
  content,
  template,
}: {
  content: ResumeContentData
  template: ResumeTemplate | null
}) {
  const accent = template?.accent || FALLBACK_ACCENT
  const orderSource = template?.section_order && template.section_order.length > 0
    ? template.section_order
    : DEFAULT_SECTION_ORDER
  const order = orderSource.filter((key) => key in SECTION_TITLES)

  const basics = content.basics ?? {}
  const name = basics.name?.trim() ?? ''
  const contacts = [basics.phone, basics.email, basics.location]
    .map((item) => item?.trim() ?? '')
    .filter((item) => item.length > 0)
  const linkLines = (basics.links ?? '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0)

  const renderSummary = () => {
    const text = basics.summary?.trim() ?? ''
    return text.length > 0 ? (
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{text}</p>
    ) : (
      <PreviewEmptyHint />
    )
  }

  const renderLinks = () =>
    linkLines.length === 0 ? (
      <PreviewEmptyHint />
    ) : (
      <ul className="space-y-1">
        {linkLines.map((line, index) =>
          isHttpUrl(line) ? (
            <li key={index}>
              <a
                href={line}
                target="_blank"
                rel="noreferrer"
                className="break-all text-sm text-brand-700 underline decoration-brand-300 underline-offset-2"
              >
                {line}
              </a>
            </li>
          ) : (
            <li key={index} className="break-all text-sm text-ink">
              {line}
            </li>
          ),
        )}
      </ul>
    )

  const renderEducation = () => {
    const entries = content.education ?? []
    if (entries.length === 0) return <PreviewEmptyHint />
    return (
      <div className="space-y-3">
        {entries.map((entry, index) => {
          const headline = [entry.school?.trim(), entry.degree?.trim(), entry.major?.trim()]
            .filter((item) => item && item.length > 0)
            .join(' · ')
          return (
            <div key={index}>
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <p className="text-sm font-semibold text-ink-strong">
                  {headline || '（待补充：学校与学历）'}
                </p>
                <p className="text-xs text-ink-soft">{rangeText(entry.start, entry.end)}</p>
              </div>
              {entry.details?.trim() ? (
                <p className="mt-1 text-sm leading-relaxed text-ink">{entry.details.trim()}</p>
              ) : null}
            </div>
          )
        })}
      </div>
    )
  }

  const renderExperience = (listKey: ListKey) => {
    const entries = content[listKey] ?? []
    if (entries.length === 0) return <PreviewEmptyHint />
    return (
      <div className="space-y-3">
        {entries.map((entry, index) => {
          const highlights = (entry.highlights ?? []).map((item) => item.trim()).filter((item) => item.length > 0)
          return (
            <div key={index}>
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <p className="text-sm font-semibold text-ink-strong">
                  {entry.name?.trim() || '（名称待补充）'}
                  {entry.role?.trim() ? ` · ${entry.role.trim()}` : ''}
                </p>
                <p className="text-xs text-ink-soft">{rangeText(entry.start, entry.end)}</p>
              </div>
              {entry.link?.trim() ? (
                <p className="mt-0.5 text-xs text-ink-soft">链接：{entry.link.trim()}</p>
              ) : null}
              {highlights.length > 0 ? (
                <ul className="mt-1.5 list-disc space-y-1 pl-5">
                  {highlights.map((item, hlIndex) => (
                    <li key={hlIndex} className="text-sm leading-relaxed text-ink">
                      {item}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          )
        })}
      </div>
    )
  }

  const renderSkills = () => {
    const entries = content.skills ?? []
    if (entries.length === 0) return <PreviewEmptyHint />
    return (
      <ul className="space-y-1.5">
        {entries.map((entry, index) => {
          const name = entry.name?.trim() ?? ''
          const level = entry.level?.trim() ?? ''
          const detail = entry.detail?.trim() ?? ''
          const headline = name || '待补充'
          const suffix = [level, detail].filter((item) => item.length > 0).join('，')
          return (
            <li key={index} className="text-sm leading-relaxed text-ink">
              <span className="font-medium text-ink-strong">{headline}</span>
              {suffix ? `（${suffix}）` : ''}
            </li>
          )
        })}
      </ul>
    )
  }

  const renderCertificates = () => {
    const entries = content.certificates ?? []
    if (entries.length === 0) return <PreviewEmptyHint />
    return (
      <ul className="space-y-1.5">
        {entries.map((entry, index) => {
          const name = entry.name?.trim() || '待补充'
          const meta = [entry.issuer?.trim(), entry.date?.trim()]
            .filter((item) => item && item.length > 0)
            .join(' · ')
          return (
            <li key={index} className="text-sm leading-relaxed text-ink">
              <span className="font-medium text-ink-strong">{name}</span>
              {meta ? `（${meta}）` : ''}
            </li>
          )
        })}
      </ul>
    )
  }

  const renderAwards = () => {
    const entries = content.awards ?? []
    if (entries.length === 0) return <PreviewEmptyHint />
    return (
      <div className="space-y-2">
        {entries.map((entry, index) => {
          const meta = [entry.issuer?.trim(), entry.date?.trim()]
            .filter((item) => item && item.length > 0)
            .join(' · ')
          return (
            <div key={index}>
              <p className="text-sm font-semibold text-ink-strong">
                {entry.name?.trim() || '（名称待补充）'}
                {meta ? `（${meta}）` : ''}
              </p>
              {entry.detail?.trim() ? (
                <p className="mt-0.5 text-sm leading-relaxed text-ink">{entry.detail.trim()}</p>
              ) : null}
            </div>
          )
        })}
      </div>
    )
  }

  const renderSection = (key: string) => {
    const label = SECTION_TITLES[key]
    switch (key) {
      case 'summary':
        return (
          <PreviewSection key={key} label={label} accent={accent}>
            {renderSummary()}
          </PreviewSection>
        )
      case 'links':
        return (
          <PreviewSection key={key} label={label} accent={accent}>
            {renderLinks()}
          </PreviewSection>
        )
      case 'education':
        return (
          <PreviewSection key={key} label={label} accent={accent}>
            {renderEducation()}
          </PreviewSection>
        )
      case 'work':
        return (
          <PreviewSection key={key} label={label} accent={accent}>
            {renderExperience('work')}
          </PreviewSection>
        )
      case 'projects':
        return (
          <PreviewSection key={key} label={label} accent={accent}>
            {renderExperience('projects')}
          </PreviewSection>
        )
      case 'skills':
        return (
          <PreviewSection key={key} label={label} accent={accent}>
            {renderSkills()}
          </PreviewSection>
        )
      case 'certificates':
        return (
          <PreviewSection key={key} label={label} accent={accent}>
            {renderCertificates()}
          </PreviewSection>
        )
      case 'awards':
        return (
          <PreviewSection key={key} label={label} accent={accent}>
            {renderAwards()}
          </PreviewSection>
        )
      default:
        return null
    }
  }

  return (
    <div className="rounded-lg border border-line bg-white p-5 sm:p-8">
      <p className="text-center text-2xl font-bold tracking-tight text-ink-strong">
        {name || '（姓名待补充）'}
      </p>
      <p className="mt-2 text-center text-xs text-ink-soft">
        {contacts.length > 0 ? contacts.join(' ｜ ') : '联系方式待补充'}
      </p>
      <div className="my-5 border-t border-line" />
      <div className="space-y-6">
        {order.map((key) => renderSection(key))}
      </div>
    </div>
  )
}

// ---------- 页面主组件 ----------

export default function ResumePage() {
  const [templates, setTemplates] = useState<ResumeTemplate[]>([])
  const [resumes, setResumes] = useState<ResumeSummary[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)

  const [parsing, setParsing] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [parseError, setParseError] = useState<string | null>(null)
  const [parseMessage, setParseMessage] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [detail, setDetail] = useState<ResumeDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)

  const [title, setTitle] = useState('')
  const [templateId, setTemplateId] = useState('clean')
  const [content, setContent] = useState<ResumeContentData>(emptyContent())
  const [saveNote, setSaveNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  const [versions, setVersions] = useState<ResumeVersionSummary[]>([])
  const [viewingVersion, setViewingVersion] = useState<ResumeVersionDetail | null>(null)

  const [pendingDeleteId, setPendingDeleteId] = useState<number | null>(null)

  const [polishSection, setPolishSection] = useState<PolishSection>('summary')
  const [polishIndex, setPolishIndex] = useState(0)
  const [polishText, setPolishText] = useState('')
  const [polishSuggestion, setPolishSuggestion] = useState<ResumePolishResponse | null>(null)
  // AI 润色：统一任务状态机（真实计时）
  const polishTask = useAsyncTask({ debugLabel: 'resume-polish' })
  const polishing = polishTask.running
  const [polishError, setPolishError] = useState<string | null>(null)
  const [polishNotice, setPolishNotice] = useState<string | null>(null)

  const [exportVersion, setExportVersion] = useState('')
  const [exporting, setExporting] = useState<'pdf' | 'docx' | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)
  const [exportMessage, setExportMessage] = useState<string | null>(null)

  const [templateSources, setTemplateSources] = useState<ResumeTemplateSource[]>([])
  const [diagOpen, setDiagOpen] = useState(false)

  useEffect(() => {
    document.title = '履历成章 · 简历 | 观澜 AUREL'
    return () => {
      document.title = '观澜 AUREL — AI 驱动的能力探索与成长平台'
    }
  }, [])

  useEffect(() => {
    let active = true
    Promise.all([api.listResumeTemplates(), api.listResumes()])
      .then(([templateList, resumeList]) => {
        if (!active) return
        setTemplates(templateList)
        setResumes(resumeList)
      })
      .catch((error: unknown) => {
        if (active) setListError(toMessage(error, '列表加载失败，请稍后刷新重试'))
      })
      .finally(() => {
        if (active) setListLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  // 模板设计参考来源：加载失败时静默，不显示该区块
  useEffect(() => {
    let active = true
    api.listResumeTemplateSources()
      .then((list) => {
        if (active) setTemplateSources(list)
      })
      .catch(() => {
        // 静默失败：参考来源只是辅助说明，不打扰用户
      })
    return () => {
      active = false
    }
  }, [])

  const applyDetail = (data: ResumeDetail) => {
    setDetail(data)
    setTitle(data.title)
    setTemplateId(data.template_id)
    setContent(normalizeContent(data.content))
    setVersions(data.versions ?? [])
    setSaveNote('')
    setViewingVersion(null)
  }

  const resetEditor = () => {
    setDetail(null)
    setTitle('')
    setTemplateId('clean')
    setContent(emptyContent())
    setVersions([])
    setSaveNote('')
    setViewingVersion(null)
    setSaveMessage(null)
    setSaveError(null)
    setPolishSuggestion(null)
    setPolishNotice(null)
    setPolishError(null)
    setPolishText('')
    setPolishSection('summary')
    setPolishIndex(0)
    setExportMessage(null)
    setExportError(null)
    setExportVersion('')
  }

  const openResume = async (id: number) => {
    setDetailLoading(true)
    setDetailError(null)
    setSaveMessage(null)
    setSaveError(null)
    setViewingVersion(null)
    setPolishError(null)
    setPolishNotice(null)
    setPolishSuggestion(null)
    setPolishText('')
    setPolishSection('summary')
    setPolishIndex(0)
    setExportMessage(null)
    setExportError(null)
    setExportVersion('')
    setPendingDeleteId(null)
    try {
      const data = await api.getResume(id)
      applyDetail(data)
    } catch (error) {
      setDetailError(toMessage(error, '加载简历失败，请稍后再试'))
    } finally {
      setDetailLoading(false)
    }
  }

  const handleParseFile = async (file: File) => {
    const lower = file.name.toLowerCase()
    if (!ACCEPTED_SUFFIXES.some((suffix) => lower.endsWith(suffix))) {
      setParseError('暂不支持该文件格式：请上传 PDF、Word（.docx）、TXT 或 Markdown 简历')
      return
    }
    setParsing(true)
    setParseError(null)
    setParseMessage(null)
    try {
      const response = await api.parseResumeFile(file)
      if (!response.content) {
        setParseError(response.parse_error ?? 'AI 未能解析出结构化内容，请稍后重试')
        return
      }
      const created = await api.createResume({
        title: response.title || file.name.replace(/\.[^.]+$/, '') || '我的简历',
        templateId: 'clean',
        content: normalizeContent(response.content),
      })
      setResumes((prev) => [created, ...prev])
      setParseMessage(`已从「${response.filename}」解析成章，请核对内容后保存。`)
      await openResume(created.id)
    } catch (error) {
      setParseError(toMessage(error, '解析失败，请稍后再试'))
    } finally {
      setParsing(false)
    }
  }

  const handleDelete = async (id: number) => {
    setListError(null)
    try {
      await api.deleteResume(id)
      setResumes((prev) => prev.filter((item) => item.id !== id))
      setPendingDeleteId(null)
      if (detail?.id === id) resetEditor()
    } catch (error) {
      setListError(toMessage(error, '删除失败，请稍后再试'))
    }
  }

  const handleSave = async () => {
    if (!detail) return
    setSaving(true)
    setSaveError(null)
    setSaveMessage(null)
    try {
      const saved = await api.saveResume(detail.id, {
        title: title.trim() || detail.title,
        templateId,
        content,
        note: saveNote.trim(),
      })
      setDetail(saved)
      setTitle(saved.title)
      setTemplateId(saved.template_id)
      setContent(normalizeContent(saved.content))
      setVersions(saved.versions ?? [])
      setSaveNote('')
      setViewingVersion(null)
      setSaveMessage(`已保存为 v${saved.current_version_no}，可在版本历史中查看。`)
    } catch (error) {
      setSaveError(toMessage(error, '保存失败，请稍后再试'))
    } finally {
      setSaving(false)
    }
  }

  // ---------- AI 表达优化（仅建议、确认制） ----------

  const switchPolishSection = (key: PolishSection) => {
    setPolishSection(key)
    setPolishIndex(0)
    setPolishText('')
    setPolishSuggestion(null)
    setPolishError(null)
    setPolishNotice(null)
  }

  const bringPolishText = () => {
    setPolishError(null)
    setPolishNotice(null)
    if (polishSection === 'summary') {
      setPolishText(content.basics?.summary?.trim() ?? '')
      return
    }
    if (polishSection === 'awards') {
      const entry = (content.awards ?? [])[polishIndex]
      if (!entry) return
      const fallback = [entry.name?.trim(), entry.issuer?.trim(), entry.date?.trim()]
        .filter((item) => item && item.length > 0)
        .join('，')
      setPolishText(entry.detail?.trim() || fallback)
      return
    }
    const entry = (content[polishSection] ?? [])[polishIndex]
    if (!entry) return
    setPolishText((entry.highlights ?? []).map((item) => item.trim()).filter((item) => item.length > 0).join('\n'))
  }

  const handlePolish = async () => {
    if (!detail) return
    const text = polishText.trim()
    if (!text) return
    setPolishError(null)
    setPolishSuggestion(null)
    setPolishNotice(null)
    await polishTask.run(async () => {
      const result = await api.polishResumeText(detail.id, polishSection, text)
      setPolishSuggestion(result)
    }, { timeoutMs: 180000 })
    if (polishTask.error) {
      setPolishError(polishTask.error)
    }
  }

  const applyPolishSuggestion = () => {
    if (!polishSuggestion) return
    const polished = polishSuggestion.polished.trim()
    if (!polished) {
      setPolishError('建议内容为空，未应用。')
      return
    }
    if (polishSection === 'summary') {
      setContent((prev) => ({ ...prev, basics: { ...prev.basics, summary: polished } }))
    } else if (polishSection === 'awards') {
      const list = content.awards ?? []
      if (polishIndex >= list.length) {
        setPolishError('所选条目已不存在，请重新选择。')
        return
      }
      setContent((prev) => ({
        ...prev,
        awards: (prev.awards ?? []).map((entry, i) =>
          i === polishIndex ? { ...entry, detail: polished } : entry,
        ),
      }))
    } else if (polishSection === 'work') {
      const list = content.work ?? []
      if (polishIndex >= list.length) {
        setPolishError('所选条目已不存在，请重新选择。')
        return
      }
      const lines = polished
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line.length > 0)
      setContent((prev) => ({
        ...prev,
        work: (prev.work ?? []).map((entry, i) =>
          i === polishIndex ? { ...entry, highlights: lines } : entry,
        ),
      }))
    } else {
      const list = content.projects ?? []
      if (polishIndex >= list.length) {
        setPolishError('所选条目已不存在，请重新选择。')
        return
      }
      const lines = polished
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line.length > 0)
      setContent((prev) => ({
        ...prev,
        projects: (prev.projects ?? []).map((entry, i) =>
          i === polishIndex ? { ...entry, highlights: lines } : entry,
        ),
      }))
    }
    setPolishSuggestion(null)
    setPolishError(null)
    setPolishNotice('建议已写入编辑器，尚未保存；点击「保存草稿」后才会生成新版本。')
  }

  // ---------- 导出 ----------

  const handleExport = async (format: 'pdf' | 'docx') => {
    if (!detail) return
    setExporting(format)
    setExportError(null)
    setExportMessage(null)
    try {
      const versionNo = exportVersion === '' ? undefined : Number(exportVersion)
      const { blob, filename } = await api.exportResume(detail.id, format, versionNo)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
      setExportMessage(`已下载：${filename}`)
    } catch (error) {
      setExportError(toMessage(error, '导出失败，请稍后再试'))
    } finally {
      setExporting(null)
    }
  }

  // ---------- 派生数据 ----------

  const previewTemplateId = viewingVersion?.template_id ?? templateId
  const previewTemplate = templates.find((item) => item.id === previewTemplateId) ?? null
  const previewContent = viewingVersion?.content ?? content
  const templateName = (id: string) => templates.find((item) => item.id === id)?.name ?? id

  const polishTargetEntries: { label: string }[] =
    polishSection === 'work'
      ? (content.work ?? []).map((entry, index) => ({
          label: `第 ${index + 1} 条：${entry.name?.trim() || '（名称待补充）'}`,
        }))
      : polishSection === 'projects'
        ? (content.projects ?? []).map((entry, index) => ({
            label: `第 ${index + 1} 条：${entry.name?.trim() || '（名称待补充）'}`,
          }))
        : polishSection === 'awards'
          ? (content.awards ?? []).map((entry, index) => ({
              label: `第 ${index + 1} 条：${entry.name?.trim() || '（名称待补充）'}`,
            }))
          : []

  const polishTargetLabel =
    polishSection === 'summary'
      ? '基本资料 · 个人概述'
      : polishTargetEntries[polishIndex]?.label ?? '（本节暂无条目，先在编辑器中添加）'

  const polishPlaceholder =
    polishSection === 'summary'
      ? '粘贴或从编辑器带入你的个人概述原文'
      : polishSection === 'awards'
        ? '粘贴或从编辑器带入奖项说明原文'
        : '粘贴或从编辑器带入经历要点原文（每行一条）'

  const currentVersionNo = viewingVersion?.version_no ?? detail?.current_version_no ?? null

  // ---------- 渲染 ----------

  return (
    <div>
      <PageHeading
        kicker="知行"
        title="履历成章"
        subtitle="把简历文件拖进来，自动解析成章；结构化编辑、模板预览、版本留痕。AI 只提建议，确认后才应用；导出即所得。"
      />

      {/* 我的简历：细线行列表 */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="mt-10"
      >
        <SectionHead
          title="我的简历"
          note={listLoading ? '正在读取…' : `${resumes.length} 份简历 · 模板与版本留痕`}
        />
        {listError ? (
          <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {listError}
          </p>
        ) : null}

        {parseMessage ? (
          <p className="mt-3 rounded-lg border border-brand-200 bg-brand-50/70 px-3 py-2 text-sm text-brand-700">
            {parseMessage}
          </p>
        ) : null}

        {/* 拖拽解析区：拖入简历文件即自动解析成章，无需手动输入任何内容 */}
        <div
          role="button"
          tabIndex={0}
          aria-label="拖拽或点击选择简历文件，自动解析"
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault()
              fileInputRef.current?.click()
            }
          }}
          onDragOver={(event) => {
            event.preventDefault()
            setDragActive(true)
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={(event) => {
            event.preventDefault()
            setDragActive(false)
            const file = event.dataTransfer.files?.[0]
            if (file) void handleParseFile(file)
          }}
          className={`mt-4 cursor-pointer rounded-xl border-2 border-dashed px-6 py-9 text-center transition ${
            dragActive
              ? 'border-brand-600 bg-brand-50/80'
              : 'border-line bg-white/60 hover:border-brand-500 hover:bg-brand-50/40'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.txt,.md"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) void handleParseFile(file)
              event.target.value = ''
            }}
          />
          {parsing ? (
            <>
              <Loader2 className="mx-auto h-7 w-7 animate-spin text-brand-600" aria-hidden="true" />
              <p className="mt-3 text-sm font-medium text-ink-strong">正在解析简历…</p>
              <p className="mt-1 text-xs text-ink-soft">正在把你的简历忠实转录为结构化内容</p>
            </>
          ) : (
            <>
              <FileUp className="mx-auto h-7 w-7 text-brand-500" aria-hidden="true" />
              <p className="mt-3 text-sm font-medium text-ink-strong">把简历文件拖到这里，自动解析成章</p>
              <p className="mt-1 text-xs text-ink-soft">
                支持 PDF、Word（.docx）、TXT、Markdown · 无需输入标题，AI 只忠实转录你的原文
              </p>
            </>
          )}
        </div>

        {parseError ? (
          <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {parseError}
          </p>
        ) : null}

        {listLoading ? (
          <div className="mt-6 flex items-center gap-2 text-sm text-ink-soft">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            正在读取…
          </div>
        ) : resumes.length === 0 ? (
          <p className="mt-4 max-w-2xl text-sm leading-relaxed text-ink-soft">
            还没有简历。把简历文件拖到上方解析区，自动成章；解析结果忠实转录你的原文，核对无误后保存即可。
          </p>
        ) : (
          <ul className="mt-2">
            {resumes.map((resume) => {
              const active = detail?.id === resume.id
              return (
                <li
                  key={resume.id}
                  className="group -mx-3 flex items-start gap-3 border-b border-line/70 px-3 py-4 transition-colors last:border-b-0 hover:bg-white/70"
                >
                  <button
                    type="button"
                    onClick={() => void openResume(resume.id)}
                    className="min-w-0 flex-1 rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
                  >
                    <p
                      className={`truncate text-[15px] font-semibold transition-colors group-hover:text-brand-700 ${
                        active ? 'text-brand-700' : 'text-ink-strong'
                      }`}
                    >
                      {resume.title}
                    </p>
                    <p className="mt-0.5 text-xs text-ink-soft">
                      {templateName(resume.template_id)} · v{resume.current_version_no} · 更新于{' '}
                      {formatDateTime(resume.updated_at)}
                    </p>
                  </button>
                  {pendingDeleteId === resume.id ? (
                    <div className="flex shrink-0 flex-col items-end gap-1 pt-0.5">
                      <button
                        type="button"
                        onClick={() => void handleDelete(resume.id)}
                        className="rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-red-600 transition-colors hover:bg-red-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/50"
                      >
                        确认删除
                      </button>
                      <button
                        type="button"
                        onClick={() => setPendingDeleteId(null)}
                        className="rounded-md px-2 py-1 text-xs text-ink-soft transition-colors hover:bg-mist focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
                      >
                        取消
                      </button>
                    </div>
                  ) : (
                    <DeleteIconButton
                      label={`删除 ${resume.title}`}
                      onClick={() => setPendingDeleteId(resume.id)}
                    />
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </motion.div>

      {detailError ? (
        <p role="alert" className="mt-10 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {detailError}
        </p>
      ) : null}

      {detailLoading ? (
        <div className="mt-10 flex items-center gap-2 py-8 text-sm text-ink-soft">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          正在加载简历…
        </div>
      ) : null}

      {!detail && !detailLoading && !detailError ? (
        <p className="mt-10 max-w-2xl text-sm leading-relaxed text-ink-soft">
          在上方选择一份已有简历，或拖入新的简历文件自动解析。履历成章提供七节结构化编辑、多款模板、版本管理与真实
          PDF / Word 导出；AI 只忠实转录你的原文并给出润色建议，经你确认后才会进入编辑器。
        </p>
      ) : null}

      {detail && !detailLoading ? (
        <>
          <div className="mt-12 grid items-start gap-10 lg:grid-cols-12">
            {/* 左：编辑稿 —— 一张连续的稿纸 */}
            <div className="min-w-0 lg:col-span-7">
            <SectionHead
              title="编辑"
              note={`当前 v${detail.current_version_no} · 切换模板即时反映在预览，点击「保存草稿」才生成新版本`}
            />
            <StatStrip
              className="mt-6"
              items={[
                {
                  label: '简历版本',
                  value: `v${detail.current_version_no}`,
                  hint: `共 ${versions.length} 个版本`,
                },
                {
                  label: '经历条目',
                  value: `${(content.work?.length ?? 0) + (content.projects?.length ?? 0)} 条`,
                  hint: '工作与项目',
                },
                {
                  label: '教育经历',
                  value: `${content.education?.length ?? 0} 条`,
                  hint: '如实填写',
                },
                {
                  label: '技能与工具',
                  value: `${content.skills?.length ?? 0} 项`,
                  hint: '只写真实掌握的',
                },
              ]}
            />

            <div className="mt-8 rounded-xl border border-line bg-white">
              <div className="space-y-4 border-b border-line/70 p-5 sm:p-6">
                <div>
                  <label htmlFor="resume-title" className="mb-1 block text-xs font-medium text-ink-soft">
                    简历标题
                  </label>
                  <input
                    id="resume-title"
                    value={title}
                    maxLength={60}
                    onChange={(event) => setTitle(event.target.value)}
                    className={inputClass}
                  />
                </div>

                <div>
                  <p className="mb-2 text-xs font-medium text-ink-soft">
                    简历模板（当前：{templateName(templateId)}，保存时生效）
                  </p>
                  <TemplatePicker templates={templates} value={templateId} onChange={setTemplateId} />
                </div>

                {templateSources.length > 0 ? (
                  <div className="rounded-lg border border-line bg-mist/50 p-3">
                    <p className="flex items-center gap-1.5 text-xs font-semibold text-ink-strong">
                      <BookOpen className="h-3.5 w-3.5 text-brand-600" aria-hidden="true" />
                      模板设计参考
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-ink-soft">
                      模板结构参考了清华大学学生职业发展指导中心与国家大学生就业服务平台的公开求职指导资料原创设计而成，示例均为虚构身份。
                    </p>
                    <ul className="mt-2 space-y-1">
                      {templateSources.map((source) => (
                        <li key={source.url} className="text-xs leading-relaxed text-ink-soft">
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium text-brand-600 hover:text-brand-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
                          >
                            {source.name}
                            <ExternalLink className="ml-1 inline h-3 w-3 align-[-1px]" aria-hidden="true" />
                          </a>
                          <span>
                            {' '}· {source.purpose} · 查阅于 {source.consulted_on}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                <div className="flex flex-col gap-3 border-t border-line/70 pt-4 sm:flex-row sm:items-end">
                  <div className="flex-1">
                    <label htmlFor="resume-note" className="mb-1 block text-xs font-medium text-ink-soft">
                      版本备注（选填）
                    </label>
                    <input
                      id="resume-note"
                      value={saveNote}
                      maxLength={100}
                      onChange={(event) => setSaveNote(event.target.value)}
                      placeholder="记录这次改动，例如：针对某岗位调整概述"
                      className={inputClass}
                    />
                  </div>
                  <Button variant="secondary" onClick={() => setDiagOpen((prev) => !prev)}>
                    <ScanSearch className="h-4 w-4" aria-hidden="true" />
                    岗位适配诊断
                  </Button>
                  <Button onClick={() => void handleSave()} disabled={saving}>
                    {saving ? (
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <Save className="h-4 w-4" aria-hidden="true" />
                    )}
                    {saving ? '保存中…' : '保存草稿'}
                  </Button>
                </div>

                {saveError ? (
                  <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                    {saveError}
                  </p>
                ) : null}
                {saveMessage ? (
                  <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                    {saveMessage}
                  </p>
                ) : null}

                {diagOpen && detail ? (
                  <JobFitDiagnosisPanel key={detail.id} resumeId={detail.id} resumeTitle={title.trim() || detail.title} />
                ) : null}
              </div>

              <div className="divide-y divide-line/70">

                <BasicsEditor content={content} onChange={setContent} />
                <EducationEditor content={content} onChange={setContent} />
                <ExperienceEditor sectionKey="work" content={content} onChange={setContent} />
                <ExperienceEditor sectionKey="projects" content={content} onChange={setContent} />
                <SkillsEditor content={content} onChange={setContent} />
                <CertificatesEditor content={content} onChange={setContent} />
                <AwardsEditor content={content} onChange={setContent} />

                {/* AI 表达优化 */}
                <section className="space-y-4 p-5 sm:p-6">
                  <div>
                    <h3 className="flex items-center gap-2 text-sm font-semibold text-ink-strong">
                      <Sparkles className="h-4 w-4 text-brand-600" aria-hidden="true" />
                      AI 表达优化（仅建议）
                    </h3>
                    <p className="mt-0.5 text-xs leading-relaxed text-ink-soft">
                      润色结果只是建议：只有点击「应用到编辑器」才会写入本地编辑器，且必须再点击「保存草稿」才会持久化为新版本。
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {POLISH_SECTIONS.map((item) => (
                      <button
                        key={item.key}
                        type="button"
                        aria-pressed={polishSection === item.key}
                        onClick={() => switchPolishSection(item.key)}
                        className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50 ${
                          polishSection === item.key
                            ? 'bg-brand-600 text-white'
                            : 'bg-mist text-ink-soft hover:bg-shallow hover:text-ink'
                        }`}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>

                  {polishSection !== 'summary' ? (
                    <div>
                      <label htmlFor="polish-entry" className="mb-1 block text-xs font-medium text-ink-soft">
                        应用到哪一条
                      </label>
                      <select
                        id="polish-entry"
                        value={polishIndex}
                        onChange={(event) => {
                          setPolishIndex(Number(event.target.value))
                          setPolishSuggestion(null)
                          setPolishNotice(null)
                        }}
                        className={inputClass}
                        disabled={polishTargetEntries.length === 0}
                      >
                        {polishTargetEntries.length === 0 ? (
                          <option value={0}>本节暂无条目，请先在编辑器中添加</option>
                        ) : (
                          polishTargetEntries.map((entry, index) => (
                            <option key={index} value={index}>
                              {entry.label}
                            </option>
                          ))
                        )}
                      </select>
                      <p className="mt-1 text-xs text-ink-soft">当前应用目标：{polishTargetLabel}</p>
                    </div>
                  ) : (
                    <p className="text-xs text-ink-soft">当前应用目标：{polishTargetLabel}</p>
                  )}
                  <p className="text-xs text-ink-soft">
                    {polishSection === 'summary'
                      ? '应用后，建议文本将写入「个人概述」。'
                      : polishSection === 'awards'
                        ? '应用后，建议文本将写入所选条目的「说明」。'
                        : '应用后，建议文本将按行拆分，替换所选条目的「经历要点」。'}
                  </p>

                  <FieldTextarea
                    label="待润色原文"
                    value={polishText}
                    onChange={setPolishText}
                    placeholder={polishPlaceholder}
                    rows={6}
                    maxLength={4000}
                  />

                  <div className="flex flex-wrap items-center gap-2">
                    <Button onClick={() => void handlePolish()} disabled={polishing || !polishText.trim() || !detail}>
                      {polishing ? (
                        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                      ) : (
                        <Sparkles className="h-4 w-4" aria-hidden="true" />
                      )}
                      {polishing ? '润色进行中…' : '获取润色建议'}
                    </Button>

                    {polishTask.running ? (
                      <AurelTaskStatus
                        className="mt-4 w-full"
                        title="AI 润色建议"
                        scene="lvli.optimize"
                        status={polishTask.status}
                        elapsedMs={polishTask.elapsedMs}
                      />
                    ) : null}
                    <Button variant="ghost" size="sm" onClick={bringPolishText} disabled={!detail}>
                      从编辑器带入原文
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setPolishText('')
                        setPolishSuggestion(null)
                        setPolishNotice(null)
                        setPolishError(null)
                      }}
                    >
                      清空
                    </Button>
                  </div>

                  <p className="text-xs text-ink-soft">
                    后端会做防捏造校验：若文本过短或与简历事实不符，会拒绝并返回原因（如实展示）。
                  </p>

                  {polishError ? (
                    <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                      {polishError}
                    </p>
                  ) : null}

                  {polishNotice ? (
                    <p className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-sm text-brand-700">
                      {polishNotice}
                    </p>
                  ) : null}

                  {polishSuggestion ? (
                    <div className="rounded-lg border border-line bg-mist p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="flex items-center gap-1.5 text-sm font-semibold text-ink-strong">
                          <Sparkles className="h-4 w-4 text-brand-600" aria-hidden="true" />
                          润色建议
                        </p>
                        {polishSuggestion.model_name ? (
                          <Badge tone="brand">{polishSuggestion.model_name}</Badge>
                        ) : null}
                      </div>
                      <p className="mt-2 whitespace-pre-wrap rounded-lg bg-white p-3 text-sm leading-relaxed text-ink ring-1 ring-inset ring-line">
                        {polishSuggestion.polished}
                      </p>
                      {polishSuggestion.notes.trim() ? (
                        <p className="mt-2 text-xs leading-relaxed text-ink-soft">
                          润色说明：{polishSuggestion.notes}
                        </p>
                      ) : null}
                      <p className="mt-2 text-xs text-ink-soft">应用目标：{polishTargetLabel}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button size="sm" onClick={applyPolishSuggestion}>
                          应用到编辑器
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setPolishSuggestion(null)
                            setPolishNotice(null)
                          }}
                        >
                          放弃
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </section>
              </div>
            </div>

              {/* 导出 */}
              <Card>
                <CardHeader
                  title="导出"
                  description="导出使用最近一次保存的简历内容；如需导出历史版本，可在下方选择。"
                />
                <CardBody className="space-y-4">
                  <div className="sm:max-w-xs">
                    <label htmlFor="export-version" className="mb-1 block text-xs font-medium text-ink-soft">
                      导出版本
                    </label>
                    <select
                      id="export-version"
                      value={exportVersion}
                      onChange={(event) => {
                        setExportVersion(event.target.value)
                        setExportMessage(null)
                        setExportError(null)
                      }}
                      className={inputClass}
                    >
                      <option value="">当前版本 v{detail.current_version_no}</option>
                      {versions.map((version) => (
                        <option key={version.version_no} value={version.version_no}>
                          v{version.version_no}（{version.note.trim() || formatDateTime(version.created_at)}）
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="secondary"
                      onClick={() => void handleExport('pdf')}
                      disabled={exporting !== null}
                    >
                      {exporting === 'pdf' ? (
                        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                      ) : (
                        <Download className="h-4 w-4" aria-hidden="true" />
                      )}
                      {exporting === 'pdf' ? '导出中…' : '导出 PDF'}
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => void handleExport('docx')}
                      disabled={exporting !== null}
                    >
                      {exporting === 'docx' ? (
                        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                      ) : (
                        <FileDown className="h-4 w-4" aria-hidden="true" />
                      )}
                      {exporting === 'docx' ? '导出中…' : '导出 Word'}
                    </Button>
                  </div>
                  {exportMessage ? (
                    <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                      {exportMessage}
                    </p>
                  ) : null}
                  {exportError ? (
                    <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                      {exportError}
                    </p>
                  ) : null}
                </CardBody>
              </Card>

              {/* 预览 */}
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
                <Card>
                  <CardHeader
                    title="简历预览"
                    description={`按「${previewTemplate?.name ?? '默认模板'}」的章节顺序渲染，与导出文件结构一致。${
                      currentVersionNo !== null ? `当前对应 v${currentVersionNo}。` : ''
                    }`}
                    action={
                      viewingVersion ? (
                        <Button variant="ghost" size="sm" onClick={() => setViewingVersion(null)}>
                          <X className="h-4 w-4" aria-hidden="true" />
                          返回当前版本
                        </Button>
                      ) : (
                        <span className="flex items-center gap-1.5 text-xs text-ink-soft">
                          <History className="h-3.5 w-3.5" aria-hidden="true" />
                          保存后自动生成新版本
                        </span>
                      )
                    }
                  />
                  <CardBody>
                    {viewingVersion ? (
                      <p className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
                        正在预览 v{viewingVersion.version_no} 历史版本内容（只读），不会影响编辑器；未保存的编辑内容暂不显示。
                      </p>
                    ) : null}
                    <div className="max-h-[720px] overflow-y-auto">
                      <ResumePreview content={previewContent} template={previewTemplate} />
                    </div>
                  </CardBody>
                </Card>
              </motion.div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  )
}
