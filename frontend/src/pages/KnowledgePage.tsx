import { FileSearch, FileText, Loader2, Trash2, Upload, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api/client'
import { AurelTaskStatus, useAsyncTask } from '../components/aurel-progress'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import type { KnowledgeDocumentDetail, RetrievalEvidence } from '../types'

export function KnowledgePage() {
  const [documents, setDocuments] = useState<Awaited<ReturnType<typeof api.listKnowledgeDocuments>>>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [detail, setDetail] = useState<KnowledgeDocumentDetail | null>(null)
  const [query, setQuery] = useState('')
  // 知识检索：统一任务状态机（真实计时）
  const searchTask = useAsyncTask({ debugLabel: 'knowledge-search' })
  const searching = searchTask.running
  const [searchError, setSearchError] = useState<string | null>(null)
  const [evidence, setEvidence] = useState<RetrievalEvidence[] | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let active = true
    api.listKnowledgeDocuments()
      .then((docs) => {
        if (active) setDocuments(docs)
      })
      .catch((error: unknown) => {
        if (active) setUploadError(error instanceof ApiError ? error.message : '加载失败')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const handleUpload = async (file: File) => {
    setUploading(true)
    setUploadError(null)
    try {
      const created = await api.uploadKnowledgeDocument(file)
      setDocuments((prev) => [created, ...prev])
    } catch (error) {
      setUploadError(error instanceof ApiError ? error.message : '上传失败')
    } finally {
      setUploading(false)
    }
  }

  const openDetail = async (id: number) => {
    try {
      setDetail(await api.getKnowledgeDocument(id))
    } catch (error) {
      setUploadError(error instanceof ApiError ? error.message : '加载详情失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await api.deleteKnowledgeDocument(id)
      setDocuments((prev) => prev.filter((d) => d.id !== id))
      if (detail?.id === id) setDetail(null)
    } catch (error) {
      setUploadError(error instanceof ApiError ? error.message : '删除失败')
    }
  }

  const handleSearch = async () => {
    const trimmed = query.trim()
    if (!trimmed) return
    setSearchError(null)
    await searchTask.run(async () => {
      const result = await api.searchKnowledge(trimmed)
      setEvidence(result.evidence)
    })
    if (searchTask.error) {
      setSearchError(searchTask.error)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-ink-strong">知藏 · 知识库</h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-soft">
            汇入你的资料，面试题目将有据可依。检索证据真实可溯，标注出处与匹配分。
          </p>
        </div>
      </div>

      <Card>
        <CardHeader
          title="上传文档"
          description="支持 .txt / .md / .docx，5MB 以内。上传后自动分块，供出题检索引用。"
        />
        <CardBody>
          <div className="flex flex-wrap items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.md,.docx"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (file) void handleUpload(file)
                event.target.value = ''
              }}
            />
            <Button onClick={() => fileInputRef.current?.click()} disabled={uploading}>
              {uploading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  解析入库中…
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4" aria-hidden="true" />
                  选择文件
                </>
              )}
            </Button>
            {uploadError ? (
              <p role="alert" className="text-sm text-red-600">
                {uploadError}
              </p>
            ) : null}
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="检索验证" description="输入关键词，查看知识库能找到哪些可追溯的证据片段。" />
        <CardBody>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <FileSearch
                className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
                aria-hidden="true"
              />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void handleSearch()
                }}
                placeholder="例如：React 状态管理"
                className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm text-ink placeholder:text-slate-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/25"
              />
            </div>
            <Button variant="secondary" onClick={() => void handleSearch()} disabled={searching || !query.trim()}>
              {searching ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
              检索
            </Button>
          </div>
          {searchTask.running ? (
            <AurelTaskStatus
              className="mt-4"
              title="知识检索"
              scene="zhicang.search"
              status={searchTask.status}
              elapsedMs={searchTask.elapsedMs}
            />
          ) : null}
          {searchError ? (
            <p role="alert" className="mt-3 text-sm text-red-600">
              {searchError}
            </p>
          ) : null}
          {evidence !== null ? (
            evidence.length === 0 ? (
              <p className="mt-4 text-sm text-ink-soft">没有找到相关片段，试试其他关键词。</p>
            ) : (
              <ul className="mt-4 space-y-3">
                {evidence.map((item) => (
                  <li
                    key={item.chunk_id}
                    className="rounded-lg border border-line bg-surface p-4"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <Badge tone="neutral">
                        {item.document_title} · 第 {item.chunk_index + 1} 块
                      </Badge>
                      <span className="text-xs font-medium text-brand-700">
                        匹配分 {item.score.toFixed(2)}
                      </span>
                    </div>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink">
                      {item.content}
                    </p>
                  </li>
                ))}
              </ul>
            )
          ) : null}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="文档列表" description={`${documents.length} 份文档`} />
        <CardBody>
          {loading ? (
            <div className="flex items-center gap-2 py-8 text-sm text-ink-soft">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              正在加载…
            </div>
          ) : documents.length === 0 ? (
            <EmptyState
              icon={FileText}
              title="知识库还空着"
              description="上传你的学习笔记或岗位资料，面试题目将围绕它们展开。"
            />
          ) : (
            <ul className="divide-y divide-line">
              {documents.map((doc) => (
                <li key={doc.id} className="flex items-center justify-between gap-3 py-3">
                  <button
                    type="button"
                    onClick={() => void openDetail(doc.id)}
                    className="min-w-0 flex-1 text-left rounded-lg px-2 py-1.5 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50"
                  >
                    <p className="truncate text-sm font-medium text-ink-strong">{doc.title}</p>
                    <p className="mt-0.5 text-xs text-ink-soft">
                      {doc.char_count} 字 · {doc.chunk_count} 块 ·{' '}
                      {new Date(doc.created_at).toLocaleString('zh-CN')}
                    </p>
                  </button>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge tone={doc.status === 'ready' ? 'brand' : 'preview'}>
                      {doc.status === 'ready' ? '就绪' : '异常'}
                    </Badge>
                    <button
                      type="button"
                      onClick={() => void handleDelete(doc.id)}
                      className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/50"
                      aria-label={`删除 ${doc.title}`}
                    >
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      {detail ? (
        <Card>
          <CardHeader
            title={detail.title}
            description={`${detail.filename} · ${detail.char_count} 字 · ${detail.chunk_count} 块`}
            action={
              <Button variant="ghost" size="sm" onClick={() => setDetail(null)}>
                <X className="h-4 w-4" aria-hidden="true" />
                关闭
              </Button>
            }
          />
          <CardBody>
            <div className="max-h-80 space-y-3 overflow-y-auto rounded-lg bg-surface p-4">
              {detail.chunks.map((chunk) => (
                <div key={chunk.id} className="rounded-lg border border-line bg-white p-3">
                  <p className="text-xs font-medium text-brand-700">第 {chunk.chunk_index + 1} 块 · {chunk.char_count} 字</p>
                  <p className="mt-1.5 whitespace-pre-wrap text-sm leading-relaxed text-ink">
                    {chunk.content}
                  </p>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      ) : null}
    </div>
  )
}
