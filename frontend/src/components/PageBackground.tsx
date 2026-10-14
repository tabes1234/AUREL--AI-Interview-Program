export type BackgroundScene = 'auth' | 'about' | 'notices' | 'workspace'

interface PageBackgroundProps {
  /**
   * 场景标识，决定使用哪张底图与哪层遮罩（四套场景一一对应，禁止混用）：
   * - auth：深夜蓝海 → 登录 / 注册等身份验证页
   * - about：日落海景 → 观澜之意简介页
   * - notices：午后薰衣草 → 澜讯公告页
   * - workspace：蓝调雪景 → 行舟工作区全部功能页
   */
  scene: BackgroundScene
}

/**
 * 全站统一的场景背景层：背景图片 + 全局遮罩（三层结构中的第一、二层）。
 *
 * - 固定铺满视口、不随页面滚动位移，页面切换时由同场景布局复用，不重新挂载闪烁；
 * - pointer-events: none，不拦截点击、焦点与表单交互；
 * - 图片加载失败时由各场景类别的回退纯色承接（见 index.css 的 page-bg-image-*）；
 * - 玻璃内容表面（第三层隔离）由页面的 glass-* 工具类承担，同样定义在 index.css。
 */
export function PageBackground({ scene }: PageBackgroundProps) {
  return (
    <div aria-hidden="true" className="page-bg">
      <div className={`page-bg-image page-bg-image-${scene}`} />
      <div className={`page-bg-mask page-bg-mask-${scene}`} />
    </div>
  )
}
