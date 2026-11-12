import type { DayRisk, KmResult } from "../api";

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const fmtDay = (v: number | null) => (v === null ? "无法估计" : `第 ${v} 天`);

interface Props {
  km: KmResult;
  selectedDay: number | null;
  onClear: () => void;
}

export default function DayDetail({ km, selectedDay, onClear }: Props) {
  const day: DayRisk | null =
    selectedDay === null ? null : km.timeline.find((t) => t.days === selectedDay) ?? null;

  if (selectedDay === null) {
    return (
      <div className="detail-panel">
        <div className="empty">点选曲线上的台阶，查看该等待天数对应的风险集、收货订单与删失订单。</div>
      </div>
    );
  }

  if (day === null) {
    return (
      <div className="detail-panel">
        <div className="empty">第 {selectedDay} 天没有订单达到对应等待天数。</div>
      </div>
    );
  }

  const hasEvents = day.received > 0;
  const hasCensor = day.censored > 0;
  const headcount = day.at_risk;
  const before = hasEvents && headcount > 0
    ? day.survival_after / (1 - day.received / headcount)
    : day.survival_after;

  return (
    <div className="detail-panel">
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12 }}>
        <div>
          <strong style={{ fontSize: 14 }}>第 {day.days} 天</strong>
          <span style={{ color: "var(--ink-2)", marginLeft: 10, fontSize: 12.5 }}>
            风险集 {day.at_risk} 单 · 收货 {day.received} 单 · 删失 {day.censored} 单 · 当日结束后未收货{" "}
            {pct(day.survival_after)}
          </span>
        </div>
        <button className="toggle-table" type="button" onClick={onClear}>
          清除选择
        </button>
      </div>

      {hasEvents && hasCensor && (
        <div className="t-seq" style={{ marginTop: 6, color: "var(--ink-2)" }}>
          同日先计算 {day.received} 单收货（当日删失单仍计入风险集），再移除 {day.censored} 单删失。
        </div>
      )}

      <div className="detail-grid">
        <div className="detail-col">
          <h4>
            风险集 <span className="count">({day.at_risk})</span>
          </h4>
          <div className="order-chips">
            {day.at_risk_orders.map((id) => (
              <span key={id} className="order-chip">
                {id}
              </span>
            ))}
          </div>
        </div>
        <div className="detail-col">
          <h4>
            收货 <span className="count">({day.received})</span>
          </h4>
          <div className="order-chips">
            {day.received_orders.length === 0 ? (
              <span style={{ color: "var(--muted)", fontSize: 12 }}>无</span>
            ) : (
              day.received_orders.map((id) => (
                <span key={id} className="order-chip received">
                  {id}
                </span>
              ))
            )}
          </div>
        </div>
        <div className="detail-col">
          <h4>
            删失 <span className="count">({day.censored})</span>
          </h4>
          <div className="order-chips">
            {day.censored_orders.length === 0 ? (
              <span style={{ color: "var(--muted)", fontSize: 12 }}>无</span>
            ) : (
              day.censored_orders.map((id) => (
                <span key={id} className="order-chip censored">
                  {id}
                </span>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="detail-note">
        {hasEvents ? (
          <>
            当日收货前未收货比例 {pct(before)}，收货后降至 {pct(day.survival_after)}（当日跌幅{" "}
            {pct(day.received / headcount)}）。
          </>
        ) : (
          <>本日没有收货事件，曲线保持在 {pct(day.survival_after)}；{day.censored} 单在此日退出风险集。</>
        )}
        本次筛选的中位交期：{fmtDay(km.median_days)}；九十分位：{fmtDay(km.p90_days)}。
      </div>
    </div>
  );
}
