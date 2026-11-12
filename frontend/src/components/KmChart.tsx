import { useEffect, useMemo, useState } from "react";
import type { CensorMark, DayRisk, KmResult, Step } from "../api";

interface Props {
  km: KmResult;
  selectedDay: number | null;
  onSelect: (days: number | null) => void;
}

const W = 900;
const H = 426;
const M = { top: 40, right: 34, bottom: 48, left: 56 };
const PLOT_W = W - M.left - M.right;
const PLOT_H = H - M.top - M.bottom;
const Y_TICKS = [0, 0.25, 0.5, 0.75, 1];

export const pct = (value: number) => `${(value * 100).toFixed(1)}%`;

export function lastStepBefore(steps: Step[], day: number): Step | null {
  let found: Step | null = null;
  for (const step of steps) {
    if (step.days > day) break;
    found = step;
  }
  return found;
}

function scaleX(maxDay: number) {
  const domainMax = Math.max(30, Math.ceil(maxDay / 30) * 30);
  const px = (d: number) => M.left + (Math.max(0, d) / domainMax) * PLOT_W;
  const ticks: number[] = [];
  for (let t = 0; t <= domainMax; t += 30) ticks.push(t);
  return { domainMax, px, ticks };
}

const py = (s: number) => M.top + (1 - s) * PLOT_H;

function nearestEventDay(km: KmResult, day: number): number | null {
  const candidates = [
    ...new Set([...km.steps.map((s) => s.days), ...km.censor_marks.map((c) => c.days)]),
  ];
  if (candidates.length === 0) return null;
  let best = candidates[0];
  for (const d of candidates) {
    if (Math.abs(d - day) < Math.abs(best - day)) best = d;
  }
  return best;
}

export default function KmChart({ km, selectedDay, onSelect }: Props) {
  const [hoverDay, setHoverDay] = useState<number | null>(null);
  const { steps, censor_marks, max_follow_up_days } = km;
  const { domainMax, px, ticks } = useMemo(() => scaleX(max_follow_up_days), [max_follow_up_days]);

  // A new cut-off or cohort is a new risk-set history; drop stale hover state.
  const signature = `${km.total}|${km.completed}|${km.waiting}|${km.max_follow_up_days}`;
  useEffect(() => {
    setHoverDay(null);
  }, [signature]);

  const path = useMemo(() => {
    const start = `M ${px(0)} ${py(1)}`;
    if (steps.length === 0) return `${start} L ${px(domainMax)} ${py(1)}`;
    const parts = [start, `L ${px(steps[0].days)} ${py(1)}`];
    for (const s of steps) parts.push(`L ${px(s.days)} ${py(s.survival)}`);
    parts.push(`L ${px(domainMax)} ${py(steps[steps.length - 1].survival)}`);
    return parts.join(" ");
  }, [steps, px, domainMax]);

  const resolved = hoverDay ?? selectedDay;
  const timeline: DayRisk | null =
    resolved === null ? null : km.timeline.find((t) => t.days === resolved) ?? null;

  const handleMove = (event: React.MouseEvent<SVGRectElement>) => {
    const svg = event.currentTarget.ownerSVGElement;
    if (!svg) return;
    const box = svg.getBoundingClientRect();
    const xPx = ((event.clientX - box.left) / box.width) * W;
    const day = Math.round(((xPx - M.left) / PLOT_W) * domainMax);
    setHoverDay(nearestEventDay(km, Math.max(0, Math.min(domainMax, day))));
  };

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby="km-title km-desc">
        <title id="km-title">未收货比例随等待天数的 Kaplan–Meier 阶梯曲线</title>
        <desc id="km-desc">
          阶梯下降处为全量收货事件；曲线上的短竖线为右删失（截止日仍未收货）。
          点选台阶可查看当天的风险集、收货和删失订单。
        </desc>

        {Y_TICKS.map((t) => (
          <g key={`y-${t}`}>
            <line x1={M.left} x2={W - M.right} y1={py(t)} y2={py(t)} stroke="var(--grid)" strokeWidth={1} />
            <text
              x={M.left - 9}
              y={py(t)}
              textAnchor="end"
              dominantBaseline="middle"
              fontSize={11}
              fill="var(--muted)"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {Math.round(t * 100)}%
            </text>
          </g>
        ))}
        {ticks.map((t) => (
          <g key={`x-${t}`}>
            <line x1={px(t)} x2={px(t)} y1={M.top} y2={H - M.bottom} stroke="var(--grid)" strokeWidth={1} />
            <text
              x={px(t)}
              y={H - M.bottom + 17}
              textAnchor="middle"
              fontSize={11}
              fill="var(--muted)"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {t}
            </text>
          </g>
        ))}

        <line x1={M.left} x2={W - M.right} y1={H - M.bottom} y2={H - M.bottom} stroke="var(--axis)" strokeWidth={1} />
        <line x1={M.left} x2={M.left} y1={M.top} y2={H - M.bottom} stroke="var(--axis)" strokeWidth={1} />
        <text x={M.left} y={16} fontSize={11} fill="var(--ink-2)">
          未收货比例
        </text>
        <text x={W - M.right} y={H - 8} textAnchor="end" fontSize={11} fill="var(--ink-2)">
          等待天数（自然日）
        </text>

        <path
          d={`${path} L ${px(domainMax)} ${py(0)} L ${px(0)} ${py(0)} Z`}
          fill="var(--accent)"
          opacity={0.07}
        />
        <path d={path} fill="none" stroke="var(--accent)" strokeWidth={2.5} strokeLinejoin="round" />

        {/* 50% reference: the median is where the curve first crosses it */}
        <line
          x1={M.left}
          x2={W - M.right}
          y1={py(0.5)}
          y2={py(0.5)}
          stroke="var(--accent)"
          strokeOpacity={0.3}
          strokeWidth={1}
        />

        {censor_marks.map((c: CensorMark) => {
          const active = resolved === c.days;
          // When the curve already sits on the baseline, draw the tick upward
          // so it stays inside the plot.
          const top = c.survival <= 0 ? py(0) - 11 : py(c.survival) - 4;
          const bottom = c.survival <= 0 ? py(0) : py(c.survival) + 7;
          return (
            <line
              key={`c-${c.days}`}
              x1={px(c.days)}
              x2={px(c.days)}
              y1={top}
              y2={bottom}
              stroke="var(--censor)"
              strokeWidth={active ? 3 : 1.75}
              strokeLinecap="round"
            />
          );
        })}

        {steps.map((s) => (
          <circle
            key={`dot-${s.days}`}
            cx={px(s.days)}
            cy={py(s.survival)}
            r={resolved === s.days ? 5 : 4}
            fill="var(--accent)"
            stroke="var(--surface)"
            strokeWidth={2}
            pointerEvents="none"
          />
        ))}

        {resolved !== null && (
          <g pointerEvents="none">
            <line
              x1={px(resolved)}
              x2={px(resolved)}
              y1={M.top}
              y2={H - M.bottom}
              stroke="var(--focus)"
              strokeWidth={1}
              opacity={0.35}
            />
          </g>
        )}

        {/* sweep layer under the per-step hit targets */}
        <rect
          x={M.left}
          y={M.top}
          width={PLOT_W}
          height={PLOT_H}
          fill="transparent"
          onMouseMove={handleMove}
          onMouseLeave={() => setHoverDay(null)}
          onClick={() => {
            if (hoverDay !== null) onSelect(selectedDay === hoverDay ? null : hoverDay);
          }}
          style={{ cursor: "crosshair" }}
        />

        {/* per-step hit targets: bigger than the mark, keyboard reachable */}
        {steps.map((s) => (
          <rect
            key={`hit-${s.days}`}
            x={px(s.days) - 9}
            y={py(s.survival) - 20}
            width={18}
            height={32}
            fill="transparent"
            style={{ cursor: "pointer" }}
            role="button"
            tabIndex={0}
            aria-label={`第 ${s.days} 天：风险集 ${s.at_risk} 单，收货 ${s.received} 单，删失 ${s.censored} 单，未收货比例 ${pct(s.survival)}`}
            onClick={() => onSelect(selectedDay === s.days ? null : s.days)}
            onFocus={() => setHoverDay(s.days)}
            onBlur={() => setHoverDay(null)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelect(selectedDay === s.days ? null : s.days);
              }
            }}
          />
        ))}

        {/* pure-censoring days: also selectable, since their risk set is part
            of the audit trail */}
        {censor_marks
          .filter((c) => !steps.some((s) => s.days === c.days))
          .map((c) => {
            const before = lastStepBefore(steps, c.days);
            const survival = before?.survival ?? 1;
            const atRisk = km.timeline.find((t) => t.days === c.days)?.at_risk ?? 0;
            return (
              <rect
                key={`hit-c-${c.days}`}
                x={px(c.days) - 7}
                y={py(survival) - 16}
                width={14}
                height={28}
                fill="transparent"
                style={{ cursor: "pointer" }}
                role="button"
                tabIndex={0}
                aria-label={`第 ${c.days} 天：删失日，风险集 ${atRisk} 单，删失 ${c.count} 单，未收货比例保持 ${pct(survival)}`}
                onClick={() => onSelect(selectedDay === c.days ? null : c.days)}
                onFocus={() => setHoverDay(c.days)}
                onBlur={() => setHoverDay(null)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(selectedDay === c.days ? null : c.days);
                  }
                }}
              />
            );
          })}
      </svg>

      {/* readout: same values on hover, keyboard focus and click; nothing is
          gated behind the pointer */}
      <div className="chart-readout" aria-live="polite">
        {resolved === null ? (
          <span className="readout-hint">悬停曲线查看该等待天数的风险集与事件；点选台阶锁定明细。</span>
        ) : timeline ? (
          <>
            <span className="readout-day">
              第 {resolved} 天{selectedDay === resolved ? "（已选中）" : "（悬停）"}
            </span>
            <span>
              风险集 <strong>{timeline.at_risk}</strong>
            </span>
            <span>
              收货 <strong>{timeline.received}</strong>
            </span>
            <span>
              删失 <strong>{timeline.censored}</strong>
            </span>
            <span>
              当日结束后未收货 <strong>{pct(timeline.survival_after)}</strong>
            </span>
            {timeline.received > 0 && timeline.censored > 0 && (
              <span className="readout-note">
                同日先计 {timeline.received} 单收货，再移除 {timeline.censored} 单删失
              </span>
            )}
            {timeline.received === 0 && (
              <span className="readout-note">
                纯删失日：曲线保持在 {pct(timeline.survival_after)}
              </span>
            )}
          </>
        ) : (
          <span className="readout-hint">该日没有订单达到对应等待天数。</span>
        )}
      </div>

      {(steps.length > 0 || censor_marks.length > 0) && (
        <div className="chart-legend">
          <span className="legend-item">
            <span className="line-key" />
            未收货比例 S(t)
          </span>
          <span className="legend-item">
            <span className="tick-key" />
            右删失（截止日仍未收货）
          </span>
          <span className="legend-item">
            <span className="dot-key" />
            全量收货事件日（可点选）
          </span>
          <span className="legend-item">
            <span className="line-key" style={{ opacity: 0.35 }} />
            50% 参考线
          </span>
        </div>
      )}
    </div>
  );
}
