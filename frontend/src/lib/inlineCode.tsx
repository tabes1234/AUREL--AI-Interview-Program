import type { ReactNode } from 'react'

/**
 * 行内渲染：按反引号分段，奇数段渲染为轻量等宽代码样式。
 * 供澜讯置顶档案卡与技术档案阅读页共用；文本必须保证反引号成对。
 */
export function renderInline(text: string): ReactNode {
  const parts = text.split('`')
  return parts.map((part, index) =>
    index % 2 === 1 ? (
      <code
        key={index}
        className="rounded bg-shallow/70 px-1 py-0.5 text-[0.85em] font-medium text-brand-700"
      >
        {part}
      </code>
    ) : (
      <span key={index}>{part}</span>
    ),
  )
}
