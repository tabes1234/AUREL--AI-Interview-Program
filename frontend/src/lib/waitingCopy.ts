/**
 * 观澜 AUREL 统一等待文案配置。
 *
 * 每个场景是 string[]：第一项为主文案（短任务只显示它），
 * 后续项仅供长任务在等待期间缓慢轮换（轮换不代表进度增加）。
 * 文案必须与真实任务状态绑定：失败时立即停止等待文案，展示真实错误。
 */

export type WaitScene =
  // 通用操作
  | 'common.prepare'
  | 'common.read'
  | 'common.save'
  | 'common.update'
  | 'common.execute'
  | 'common.organize'
  | 'common.page'
  | 'common.network'
  // AI 通用
  | 'ai.start'
  | 'ai.waiting'
  | 'ai.streaming'
  | 'ai.organizing'
  | 'ai.long'
  // 问澜：AI 面试
  | 'wenlan.questions'
  | 'wenlan.followup'
  | 'wenlan.analyze'
  | 'wenlan.report'
  | 'wenlan.regenerate'
  // 知途与小鸥：职业规划及 AI 对话
  | 'career.chat'
  | 'career.direction'
  | 'career.plan'
  | 'career.action'
  | 'career.context'
  // 观己：能力分析
  | 'guanji.analyze'
  | 'guanji.report'
  // 拾阶：成长记录
  | 'shijie.update'
  | 'shijie.analyze'
  // 度衡：评估分析
  | 'duheng.run'
  | 'duheng.summary'
  // 知岗：岗位分析
  | 'zhigang.analyze'
  | 'zhigang.skills'
  // 履历成章：简历优化
  | 'lvli.analyze'
  | 'lvli.optimize'
  | 'lvli.generate'
  // 合契：岗位匹配
  | 'heqi.match'
  | 'heqi.gap'
  | 'heqi.report'
  // 知藏：知识检索
  | 'zhicang.search'
  | 'zhicang.organize'
  // 听澜：语音分析
  | 'tinglan.audio'
  | 'tinglan.expression'
  | 'tinglan.advice'
  // 协奏：多阶段任务
  | 'xiezou.prepare'
  | 'xiezou.summary'

export const WAITING_COPY: Record<WaitScene, string[]> = {
  // ---------- 通用操作 ----------
  'common.prepare': ['正在为你理清眼前的线索……'],
  'common.read': ['正在拾起与你有关的信息……'],
  'common.save': ['正在为这一步成长留下记录……'],
  'common.update': ['正在让这次调整稳妥生效……'],
  'common.execute': ['正在沿着你的问题寻找答案……'],
  'common.organize': ['正在将零散的信息汇成清晰的方向……'],
  'common.page': ['正在为你整理好接下来的视野……'],
  'common.network': ['正在等待服务回应，请稍候片刻……'],

  // ---------- AI 通用 ----------
  'ai.start': ['正在认真梳理你的问题……', '每一份清晰的结论，都值得认真整理……'],
  'ai.waiting': ['思路正在展开，正在等待生成结果……', '每一份清晰的结论，都值得认真整理……'],
  'ai.streaming': ['答案正在一点点浮现……'],
  'ai.organizing': ['正在把这些线索归拢成清晰的答案……'],
  'ai.long': ['每一份清晰的结论，都值得认真整理……'],

  // ---------- 问澜：AI 面试 ----------
  'wenlan.questions': ['正在结合岗位特点，为你铺开这一轮练习……', '每一份清晰的结论，都值得认真整理……'],
  'wenlan.followup': ['正在从你的回答中寻找值得深入的线索……'],
  'wenlan.analyze': ['正在回看你的表达，寻找可以进步的细节……'],
  'wenlan.report': ['正在将作答表现整理成下一步的练习方向……', '正在把这些线索归拢成清晰的答案……'],
  'wenlan.regenerate': ['正在调整提问角度，让练习更贴近你的目标……'],

  // ---------- 知途与小鸥 ----------
  'career.chat': ['小鸥正在认真整理你的问题……', '思路正在展开，正在等待生成结果……', '答案正在一点点浮现……'],
  'career.direction': ['正在梳理兴趣、能力与目标之间的联系……', '正在把这些线索归拢成清晰的答案……'],
  'career.plan': ['正在把远方的目标拆成可走的每一步……', '每一份清晰的结论，都值得认真整理……'],
  'career.action': ['正在为你的下一步寻找切实可行的路径……'],
  'career.context': ['正在回顾与你这次问题相关的信息……'],

  // ---------- 观己 ----------
  'guanji.analyze': ['正在汇集能力线索，寻找你的独特之处……'],
  'guanji.report': ['正在把经历与能力整理成更清晰的画像……', '正在把这些线索归拢成清晰的答案……'],

  // ---------- 拾阶 ----------
  'shijie.update': ['正在为这一段成长留下印记……'],
  'shijie.analyze': ['正在回看已经走过的每一步……'],

  // ---------- 度衡 ----------
  'duheng.run': ['正在按照当前评估标准检查结果……'],
  'duheng.summary': ['正在将分析依据整理成清晰的结论……'],

  // ---------- 知岗 ----------
  'zhigang.analyze': ['正在拆解岗位描述中的关键要求……', '正在把分散的信息归纳为清楚的脉络……'],
  'zhigang.skills': ['正在寻找职位要求与能力之间的关联……'],

  // ---------- 履历成章 ----------
  'lvli.analyze': ['正在整理你的经历与项目线索……'],
  'lvli.optimize': ['正在让经历中的重点和成果更加清晰……'],
  'lvli.generate': ['正在为你的经历梳理出更清楚的表达方式……'],

  // ---------- 合契 ----------
  'heqi.match': ['正在对照岗位要求与已有经历……'],
  'heqi.gap': ['正在寻找符合之处与仍可提升的地方……'],
  'heqi.report': ['正在将匹配结果汇成下一步的行动建议……'],

  // ---------- 知藏 ----------
  'zhicang.search': ['正在沿着你的线索寻找相关资料……'],
  'zhicang.organize': ['正在把分散的信息归纳为清楚的脉络……'],

  // ---------- 听澜 ----------
  'tinglan.audio': ['正在整理音频中的有效信息……'],
  'tinglan.expression': ['正在梳理语速、停顿与表达表现……', '正在把这些线索归拢成清晰的答案……'],
  'tinglan.advice': ['正在将分析结果转化为可实践的改进方向……'],

  // ---------- 协奏 ----------
  'xiezou.prepare': ['正在安排各项任务的执行顺序……'],
  'xiezou.summary': ['正在将不同环节的结果整合到一起……'],
}

/** 请求真正发出前（preparing）的统一文案：此刻还不能声称 AI 已在思考。 */
export const PREPARING_COPY = '正在为你理清眼前的线索……'

/** 流式接收阶段的场景覆盖：无覆盖时回退 ai.streaming。 */
const STREAMING_OVERRIDE: Partial<Record<WaitScene, string>> = {
  'career.chat': '答案正在一点点浮现……',
}

/** 按任务阶段取主文案。失败/取消时调用方应直接展示真实错误，不要再用等待文案。 */
export function copyForPhase(
  scene: WaitScene,
  phase: 'preparing' | 'loading' | 'streaming',
): string {
  if (phase === 'preparing') return PREPARING_COPY
  if (phase === 'streaming') {
    return STREAMING_OVERRIDE[scene] ?? WAITING_COPY['ai.streaming'][0]
  }
  const list = WAITING_COPY[scene] ?? WAITING_COPY['ai.waiting']
  return list[0]
}

/** 长任务轮换用的完整文案序列（含主文案）。 */
export function copySequence(scene: WaitScene): string[] {
  return WAITING_COPY[scene] ?? WAITING_COPY['ai.waiting']
}
