/**
 * 星图对照雷达图：纯 SVG 实现，无第三方依赖。
 * current（我的现值）实线填充，target（岗位目标）虚线描边；
 * 支持 3-8 个维度，刻度 0-10，网格为 2.5 / 5 / 7.5 / 10 四圈同心圆。
 */
const MAX_VALUE = 10
const RING_VALUES = [2.5, 5, 7.5, 10]

export interface SkillRadarDimension {
  name: string
  current: number
  target: number
}

export function SkillRadar({ dimensions }: { dimensions: SkillRadarDimension[] }) {
  const dims = dimensions.slice(0, 8)
  if (dims.length < 3) {
    return <p className="text-sm text-ink-soft">维度不足 3 项，暂无法绘制星图对照。</p>
  }

  const cx = 200
  const cy = 172
  const maxR = 108
  const labelR = maxR + 22
  const count = dims.length

  const angleOf = (index: number) => ((-90 + (360 / count) * index) * Math.PI) / 180
  const pointAt = (index: number, value: number) => {
    const clamped = Math.max(0, Math.min(MAX_VALUE, value))
    const radius = (clamped / MAX_VALUE) * maxR
    const angle = angleOf(index)
    return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) }
  }
  const toPolygon = (key: 'current' | 'target') =>
    dims
      .map((dim, index) => {
        const point = pointAt(index, dim[key])
        return `${point.x.toFixed(2)},${point.y.toFixed(2)}`
      })
      .join(' ')

  return (
    <figure className="m-0">
      <svg
        viewBox="0 0 400 344"
        className="h-auto w-full max-w-[360px]"
        role="img"
        aria-label="能力星图对照：实线区域为我的现值，虚线区域为岗位目标"
      >
        {/* 四圈同心网格 */}
        {RING_VALUES.map((value) => (
          <circle
            key={`ring-${value}`}
            cx={cx}
            cy={cy}
            r={(value / MAX_VALUE) * maxR}
            fill="none"
            stroke="#E2E8F0"
            strokeWidth="1"
          />
        ))}
        {/* 轴线 */}
        {dims.map((_dim, index) => {
          const outer = pointAt(index, MAX_VALUE)
          return (
            <line
              key={`axis-${index}`}
              x1={cx}
              y1={cy}
              x2={outer.x}
              y2={outer.y}
              stroke="#E2E8F0"
              strokeWidth="1"
            />
          )
        })}
        {/* 刻度值 */}
        {RING_VALUES.map((value) => (
          <text
            key={`tick-${value}`}
            x={cx + 5}
            y={cy - (value / MAX_VALUE) * maxR + 3}
            fontSize="9"
            fill="#94A3B8"
          >
            {value}
          </text>
        ))}
        {/* 岗位目标：虚线描边，不填充 */}
        <polygon
          points={toPolygon('target')}
          fill="none"
          stroke="#7185A2"
          strokeWidth="1.5"
          strokeDasharray="6 4"
          strokeLinejoin="round"
        />
        {/* 我的现值：实线填充 */}
        <polygon
          points={toPolygon('current')}
          fill="#4D83D6"
          fillOpacity="0.2"
          stroke="#4D83D6"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        {/* 维度名标签 */}
        {dims.map((dim, index) => {
          const angle = angleOf(index)
          const cos = Math.cos(angle)
          const sin = Math.sin(angle)
          const anchor = Math.abs(cos) < 0.2 ? 'middle' : cos > 0 ? 'start' : 'end'
          const dy = sin > 0.25 ? 10 : sin < -0.25 ? -4 : 4
          return (
            <text
              key={`label-${index}`}
              x={cx + labelR * cos}
              y={cy + labelR * sin + dy}
              textAnchor={anchor}
              fontSize="12"
              fontWeight="500"
              fill="#334155"
            >
              {dim.name}
            </text>
          )
        })}
      </svg>
      <figcaption className="mt-3 flex items-center gap-5 text-xs text-ink-soft">
        <span className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="h-2.5 w-2.5 rounded-sm bg-brand-600/20 ring-1 ring-[#4D83D6]"
          />
          我的现值
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-0 w-4 border-t-2 border-dashed border-[#7185A2]" />
          岗位目标
        </span>
      </figcaption>
    </figure>
  )
}
