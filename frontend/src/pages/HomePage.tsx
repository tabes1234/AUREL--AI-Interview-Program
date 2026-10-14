import { PointerGlow } from '../components/PointerGlow'
import { SiteHeader } from '../components/layout/SiteHeader'
import { WarmGreeting } from '../components/WarmGreeting'
import { XiaouCompanion } from '../components/XiaouCompanion'
import { BRAND } from '../lib/brand'

/**
 * 品牌首页：海天一色，只呈现名字、座右铭与四个栏目。
 * 背景为分层海景：图片层（缓慢漂移）→ 太阳倒影光纹 →
 * 水光 → 深蓝渐变遮罩 → 前景内容。
 * 原图 /images/aurel-sea-background.png（太阳居右，地平线约 55% 高度，文字置于左侧较暗海面）。
 */
export default function HomePage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0B2447]">
      {/* 0. 海蓝微光：全站统一鼠标跟随，主页用最完整档（含极淡运动光痕） */}
      <PointerGlow intensity="ambient" />
      {/* 1. 海景图片层：超宽图层缓慢漂移；移动端太阳更靠右避免压住标题，图片缺失时由深蓝底色兜底 */}
      <div
        aria-hidden="true"
        className="hero-sea-layer absolute inset-y-0 bg-cover bg-[position:88%_center] bg-no-repeat sm:bg-[position:72%_center]"
        style={{ backgroundImage: "url('/images/aurel-sea-background.png')" }}
      />

      {/* 2. 太阳倒影光纹：日光反射区极轻微的反光明暗变化 */}
      <div aria-hidden="true" className="hero-sun-glare" />

      {/* 3. 海面水光：极淡光带游移，只覆盖海的下半幅 */}
      <div
        aria-hidden="true"
        className="hero-sea-shimmer pointer-events-none absolute inset-x-0 bottom-0 h-[48%]"
      />

      {/* 4. 深蓝渐变遮罩：左侧加深保证文字对比度，右侧留出太阳与反光 */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'linear-gradient(100deg, rgba(9, 28, 56, 0.88) 0%, rgba(11, 36, 71, 0.72) 30%, rgba(13, 42, 82, 0.38) 58%, rgba(13, 42, 82, 0.10) 82%)',
        }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 h-28"
        style={{
          background: 'linear-gradient(to top, rgba(8, 24, 48, 0.55), transparent)',
        }}
      />

      {/* 5. 前景内容层 */}
      <div className="relative flex min-h-screen flex-col">
        <SiteHeader variant="overlay" />

        <main className="flex flex-1 items-center">
          <div className="mx-auto w-full max-w-6xl px-4 pb-24 pt-10 sm:px-6 lg:px-8">
            <h1 className="hero-title-text text-5xl font-bold tracking-tight sm:text-6xl lg:text-7xl">
              观澜 <span className="font-semibold tracking-wide">AUREL</span>
            </h1>
            <p className="hero-motto-text mt-6 text-xl font-medium tracking-[0.18em] sm:text-2xl">
              {BRAND.motto}
            </p>
            <p className="hero-en-motto mt-3 text-sm tracking-[0.12em] text-shallow/90 sm:text-base">
              {BRAND.enMotto}
            </p>
            {/* 暖心寄语：品牌氛围的轻声补充，次于主标题与座右铭 */}
            <WarmGreeting />
          </div>
        </main>
      </div>

      {/* 小鸥悬浮入口：点击直达知途 AI 对话 */}
      <XiaouCompanion />
    </div>
  )
}
