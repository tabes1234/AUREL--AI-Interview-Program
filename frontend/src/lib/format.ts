import { DIFFICULTY_LABELS, LANGUAGE_LABELS } from './brand'
import type { TaskStatus } from '../types'

export const STATUS_LABELS: Record<TaskStatus, string> = {
  generating_questions: '生成问题中',
  ready: '待开始',
  in_progress: '进行中',
  generating_report: '生成报告中',
  completed: '已完成',
  failed: '失败',
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function difficultyLabel(value: string): string {
  return DIFFICULTY_LABELS[value as keyof typeof DIFFICULTY_LABELS] ?? value
}

export function languageLabel(value: string): string {
  return LANGUAGE_LABELS[value as keyof typeof LANGUAGE_LABELS] ?? value
}

// ---------- 问澜：目录与题集标签 ----------

export const EXPERIENCE_LABELS: Record<string, string> = {
  student: '在校生 / 实习',
  fresh_graduate: '应届毕业生',
  junior: '初级',
  mid: '中级',
  senior: '高级',
  expert: '资深专家',
  management: '管理与负责人',
}

export const INTERVIEW_TYPE_LABELS: Record<string, string> = {
  screening: '初筛与基础问答',
  technical: '专业技术面试',
  behavioral: '行为与项目经历',
  case: '场景分析与案例',
  leadership: '管理与领导力',
  comprehensive: '综合模拟',
}

export const FOCUS_LABELS: Record<string, string> = {
  knowledge: '专业知识',
  project: '项目经历',
  practice: '实践能力',
  analysis: '问题分析与解决',
  communication: '沟通与协作',
  behavior: '行为面试',
  scenario: '场景应对',
  case_analysis: '案例分析',
  comprehensive: '综合能力',
}

export const QUESTION_CATEGORY_LABELS: Record<string, string> = {
  knowledge: '专业知识',
  project: '项目经历',
  practice: '实践能力',
  analysis: '问题分析',
  communication: '沟通协作',
  behavior: '行为面试',
  scenario: '场景应对',
  case_analysis: '案例分析',
}
