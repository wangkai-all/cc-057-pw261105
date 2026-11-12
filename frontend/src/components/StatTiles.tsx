import type { KmResult } from "../api";

interface Props {
  km: KmResult;
}

export function fmtDays(value: number | null): string {
  return value === null ? "无法估计" : `${value}`;
}

export default function StatTiles({ km }: Props) {
  const median = km.median_days;
  const p90 = km.p90_days;
  return (
    <div className="stat-row">
      <div className="stat">
        <div className="label">已完成订单平均交期</div>
        <div className="value">
          {km.completed_mean_days === null ? "—" : km.completed_mean_days.toFixed(1)}
          {km.completed_mean_days !== null && <small>天</small>}
        </div>
        <div className="sub">基于 {km.completed} 单已全量收货 · 中位 {km.completed_median_days ?? "—"} 天</div>
      </div>

      <div className="stat">
        <div className="label">仍在等待</div>
        <div className="value">
          {km.waiting}
          <small>单</small>
        </div>
        <div className="sub">
          平均已等待 {km.waiting_mean_days === null ? "—" : km.waiting_mean_days.toFixed(1)} 天 · 最长{" "}
          {km.waiting_max_days ?? "—"} 天 · 右删失
        </div>
      </div>

      <div className="stat">
        <div className="label">中位交期（KM）</div>
        <div className="value" style={{ fontSize: median === null ? 19 : undefined }}>
          {fmtDays(median)}
          {median !== null && <small>天</small>}
        </div>
        <div className="sub">
          {median === null ? "曲线尚未降到 50%，无法估计" : "未收货比例首次 ≤ 50% 的等待天数"}
        </div>
      </div>

      <div className="stat">
        <div className="label">九十分位（KM）</div>
        <div className="value" style={{ fontSize: p90 === null ? 19 : undefined }}>
          {fmtDays(p90)}
          {p90 !== null && <small>天</small>}
        </div>
        <div className="sub">
          {p90 === null ? "曲线尚未降到 10%，无法估计" : "未收货比例首次 ≤ 10% 的等待天数"}
        </div>
      </div>
    </div>
  );
}
