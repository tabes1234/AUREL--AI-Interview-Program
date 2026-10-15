import { CheckCircle2 } from 'lucide-react'
import { SiteHeader } from '../components/layout/SiteHeader'
import { PageBackground } from '../components/PageBackground'
import { XiaouCompanion } from '../components/XiaouCompanion'
import { BRAND } from '../lib/brand'

const CAPABILITIES = [
  '问澜：以真实模型落问，一题一追问，于问答之间见真章',
  '观己：答案织成能力星图，每一分都附原文为证',
  '听澜与协奏：细听你的声音——客观指标记之于数，三位分析师接力品评',
  '知岗：读懂一份岗位描述，结论条条可溯原文',
  '知潮：真实岗位资料港，十行百业的潮水皆有来处',
  '拾贝：官方简历写作规范按行业陈列，条条可溯来源',
  '履历成章：七款原创版式，让经历落笔成章，导出与预览如一',
  '合契：简历与岗位相合相契，判断两侧皆有原文为凭',
  '知藏：知识藏于库中，检索出题，出处可查可回',
  '知途：小鸥相伴的职业规划，分层记忆，一步一履',
  '度衡与回澜：限时以度其衡，错题回澜，如期重逢',
]

/**
 * 观澜之意：项目介绍页。
 * 编辑感排版——主标题、品牌理念与连贯正文，不用功能卡片墙；
 * 背景为日落海景场景图，全部正文承载于一张暖白玻璃画布，与夕阳形成清晰前后层次。
 */
export default function AboutPage() {
  return (
    <div className="relative min-h-screen bg-surface">
      {/* 日落海景场景背景（固定底层，pointer-events: none）+ 柔和光晕 */}
      <PageBackground scene="about" />
      <SiteHeader variant="solid" />

      <main className="page-enter relative mx-auto w-full max-w-4xl px-3 pb-16 pt-10 sm:px-5 sm:pt-14 lg:px-8">
        {/* 暖白玻璃画布：承载全部正文，标题与理念不直接落在照片上 */}
        <div className="glass-surface glass-about rounded-3xl px-6 py-10 sm:px-10 sm:py-12 lg:px-14 lg:py-14">
          <header>
            <p className="text-sm font-medium tracking-[0.3em] text-brand-600">GUANLAN YI</p>
            <h1 className="mt-3 text-4xl font-bold tracking-tight text-ink-strong sm:text-5xl">
              观澜之意
            </h1>
            <p className="mt-8 text-xl font-medium leading-relaxed text-ink sm:text-2xl">
              「观水有术，必观其澜。」——《孟子》
              观澜取意于此：不逐大江大河的声势，只认真看见每一次练习激起的细微波澜——
              因为见微，方能知远。
            </p>
          </header>

          <div className="mt-10 space-y-8 text-[15px] leading-loose text-ink sm:text-base">
            <p>
              英文名 AUREL，取「珍贵的、金的」之意——如沙金沉于水底，被水流反复打磨，
              成色才渐渐显明。能力的成色也一样，要在一次次真实的表达里才看得清。
              座右铭「{BRAND.motto}」：「见微」是相信细节里藏着真相，一次停顿、一处含糊，
              往往预示着更大的差距或更大的潜力；「向新」是相信积累能带来改变，
              每一次练习都是向前一步——水滴石穿，静水流深。
            </p>
            <p>
              观澜是一个职业面试练习与能力探索的伙伴。它依你选择的行业与岗位生成问题，
              逐题追问，细听你的回答，给出有依据的改进建议，再把每一次练习沉淀为可见的成长轨迹
              ——如水位刻度，涨落皆有记录。身旁还有一位名叫小鸥的规划伙伴，
              记得你走过的水路，陪你把志向化作一步一履的行动。从行前的知识梳理，
              到临场的表达打磨，再到靠岸后的星图回望，它陪你完成一轮又一轮
              「练习—反馈—修正」的循环，如潮水往复，岸线渐新。观澜还引来十行百业的潮水——
              知潮的岗位不止一行一业，岸边拾贝滩上，官方简历规范按行业列好，条条可溯来源。
            </p>
            <p>
              观澜看重三件事：<strong className="font-semibold text-ink-strong">结果要有依据</strong>
              ——每个分数都附回答原文与评分理由，可追溯、可检验；
              <strong className="font-semibold text-ink-strong">隐私要被尊重</strong>
              ——你的简历、录音与分析只用于你自己的报告，随时可以删除；
              <strong className="font-semibold text-ink-strong">判断要留给人</strong>
              ——AI 的评分与建议是参考，掌舵的人始终是你。
            </p>
          </div>

          <hr className="mt-14 border-line/80" />

          <section className="mt-12" aria-labelledby="capabilities-heading">
            <h2 id="capabilities-heading" className="text-lg font-bold text-ink-strong">
              此刻真实可用的能力
            </h2>
            <p className="mt-1.5 text-sm text-ink-soft">
              以下均为已上线的功能，各居其名，各司其职。未开放前不做伪装入口，也不虚构任何数据。
            </p>
            <ul className="mt-6 grid gap-x-8 gap-y-3.5 sm:grid-cols-2">
              {CAPABILITIES.map((item) => (
                <li key={item} className="flex items-start gap-2.5 text-sm leading-relaxed text-ink">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-600/80" aria-hidden="true" />
                  {item}
                </li>
              ))}
            </ul>
          </section>

          <blockquote className="mt-14 border-l-2 border-ripple pl-5 text-[15px] leading-loose text-ink-soft sm:pl-6">
            水静，方能照见人影。API 密钥仅存于服务端环境变量，日志自动脱敏；
            录音只在内存中处理，不落盘；简历与回答记录只属于你，隐私说明在站内随时可查。
            整站可装进单只容器随处停靠，线上另有访问令牌、限流与会话登录为你护航。
          </blockquote>

          <footer className="mt-14 border-t border-line/70 pt-6 text-sm text-ink-soft">
            © 2026 观澜 AUREL · {BRAND.motto}
          </footer>
        </div>
      </main>

      {/* 小鸥悬浮入口：点击直达知途 AI 对话 */}
      <XiaouCompanion />
    </div>
  )
}
