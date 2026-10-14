/**
 * 观澜 AUREL 海洋流光进度系统：全站统一加载反馈。
 *
 * - AurelProgress：流光进度条（不确定/确定双模式）。
 * - AurelLoading：统一加载容器（条 + 文案 + 耗时 + 重试）。
 * - AurelTaskStatus：AI 长任务进度面板（任务名 + 状态徽标 + 取消/重试）。
 * - useAsyncTask：异步任务状态机（preparing/loading/streaming/终态 + 超时/取消/防重入）。
 * - useRotatingCopy：长任务等待文案缓慢轮换（不代表进度）。
 */
export { AurelProgress, type AurelProgressStatus } from './AurelProgress'
export { AurelLoading } from './AurelLoading'
export { AurelTaskStatus } from './AurelTaskStatus'
export {
  useAsyncTask,
  formatElapsed,
  isTerminal,
  type AsyncTaskStatus,
  type UseAsyncTaskOptions,
  type UseAsyncTaskReturn,
} from './useAsyncTask'
export { useRotatingCopy } from './useRotatingCopy'
