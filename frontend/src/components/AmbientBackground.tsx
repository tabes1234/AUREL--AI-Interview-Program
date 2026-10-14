interface AmbientBackgroundProps {
  /** vivid：略显鲜明的清透蓝（用于项目简介页） */
  vivid?: boolean
}

/**
 * 全站统一的流动云团背景。
 * 纯 CSS 渐变色团缓慢漂移（30-46s 周期，transform/opacity 合成层动画），
 * 不产生任何 React 渲染开销；pointer-events: none 不拦截点击；
 * prefers-reduced-motion 下自动冻结为静态蓝白渐变。
 */
export function AmbientBackground({ vivid = false }: AmbientBackgroundProps) {
  return (
    <div aria-hidden="true" className="ambient-clouds">
      <div className="cloud-blob cloud-blob-1" />
      <div className="cloud-blob cloud-blob-2" />
      <div className="cloud-blob cloud-blob-3" />
      <div className="cloud-blob cloud-blob-4" />
      <div className="cloud-blob cloud-blob-5" />
      {vivid ? (
        <>
          <div className="cloud-blob cloud-blob-6" />
          <div className="cloud-blob cloud-blob-7" />
        </>
      ) : null}
    </div>
  )
}
