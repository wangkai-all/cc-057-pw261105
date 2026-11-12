import { useEffect, useState } from "react";
import type { AnalysisPayload, FilterOptions } from "./api";
import KmChart from "./components/KmChart";
import DayDetail from "./components/DayDetail";
import StatTiles from "./components/StatTiles";
import OrderTable from "./components/OrderTable";
import CancelledCard from "./components/CancelledCard";

export interface Controls {
  asOf: string;
  supplier: string;
  material: string;
}

interface Props {
  controls: Controls;
  options: FilterOptions;
  payload: AnalysisPayload;
  error: string | null;
  pending: boolean;
  onAsOf: (value: string) => void;
  onSupplier: (value: string) => void;
  onMaterial: (value: string) => void;
}

export default function Dashboard({
  controls,
  options,
  payload,
  error,
  pending,
  onAsOf,
  onSupplier,
  onMaterial,
}: Props) {
  const [selectedDay, setSelectedDay] = useState<number | null>(null);

  // A new cut-off or cohort is a different risk-set history; drop the selection.
  useEffect(() => {
    setSelectedDay(null);
  }, [controls.asOf, controls.supplier, controls.material]);

  const scope =
    controls.supplier || controls.material
      ? [controls.supplier || "全部供应商", controls.material || "全部物料"].join(" · ")
      : "全部供应商 · 全部物料";

  return (
    <div className={`shell${pending ? " is-pending" : ""}`}>
      <header className="page-head">
        <h1>交期分析：已收货与待收货</h1>
        <p>
          在同一页面还原截⾄统计截止日的订单状态：已经全量收货的记录交期，仍在等待的记录已等待天数并标为右删失。
          曲线为 Kaplan–Meier 未收货比例，已剔除截止日前取消的订单。
        </p>
      </header>

      <div className="controls" role="search" aria-label="筛选条件">
        <div className="field">
          <label htmlFor="supplier">供应商</label>
          <select id="supplier" value={controls.supplier} onChange={(e) => onSupplier(e.target.value)}>
            <option value="">全部供应商</option>
            {options.suppliers.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="material">物料</label>
          <select id="material" value={controls.material} onChange={(e) => onMaterial(e.target.value)}>
            <option value="">全部物料</option>
            {options.materials.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="asof">统计截止日</label>
          <input
            id="asof"
            type="date"
            min={options.min_cutoff}
            max={options.max_cutoff}
            value={controls.asOf}
            onChange={(e) => onAsOf(e.target.value)}
          />
        </div>

        <div className="field">
          <span className="label" style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-2)" }}>
            快捷截止日
          </span>
          <div className="cutoff-presets">
            {options.cutoff_presets.map((p) => (
              <button
                key={p.date}
                type="button"
                className="preset"
                aria-pressed={controls.asOf === p.date}
                title={p.date}
                onClick={() => onAsOf(p.date)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div className="state-banner error" role="alert">
          <span>无法加载该截止日的分析：{error}</span>
        </div>
      )}

      <div className="context-line" aria-live="polite">
        当前口径：<strong>{scope}</strong> · 截止日 <strong>{payload.as_of}</strong> · 已下单{" "}
        <strong>{payload.counts.placed}</strong> 单（已收货 {payload.counts.completed}、待收货{" "}
        {payload.counts.waiting}、已取消 {payload.counts.cancelled}）；进入曲线 <strong>{payload.counts.curve}</strong> 单
        {pending && " · 刷新中…"}
      </div>

      <StatTiles km={payload.km} />

      <section className="card" aria-labelledby="curve-title">
        <div className="card-head">
          <div>
            <h2 id="curve-title">未收货比例随等待天数的变化（Kaplan–Meier）</h2>
            <p>
              台阶向下为全量收货事件；短竖线为右删失（截止日仍未收货的等待订单）。同日既有收货又有删失时，
              先计算收货，再移除删失。点台阶可核对当天风险集。
            </p>
          </div>
          <span className="tip-word">自然日</span>
        </div>

        {payload.km.total === 0 ? (
          <div className="detail-panel">
            <div className="empty">该筛选与截止日下没有可进入曲线的订单（可能全部已取消或尚未下单）。</div>
          </div>
        ) : (
          <>
            <KmChart km={payload.km} selectedDay={selectedDay} onSelect={setSelectedDay} />
            <DayDetail km={payload.km} selectedDay={selectedDay} onClear={() => setSelectedDay(null)} />
          </>
        )}

        <div className="footnote">
          曲线范围：已剔除截止日前取消的 {payload.counts.cancelled} 单，仅包含 {payload.counts.curve} 单
          （其中已收货 {payload.km.completed} 单、右删失 {payload.km.waiting} 单）。
          取消单见下方单列。
        </div>
      </section>

      <div className="split">
        <OrderTable rows={payload.completed_orders.concat(payload.waiting_orders)} counts={payload.counts} asOf={payload.as_of} />
        <div>
          <CancelledCard rows={payload.cancelled_orders} />
          <section className="card method" aria-labelledby="method-title">
            <h2 id="method-title" style={{ fontSize: 15, margin: "0 0 6px" }}>
              口径说明
            </h2>
            <ol>
              <li>日期差按自然日计算；收货日或截止日与下单日之差即交期/等待天数。</li>
              <li>截止日之后才发生的收货或取消不提前生效；切换截止日后可逐单核对。</li>
              <li>已全量收货的订单进入交期统计；仍在等待的按截止日截断，标为右删失。</li>
              <li>同一天既有收货又有删失：该日删失单仍计入风险集，先算收货事件，再移除删失。</li>
              <li>平均交期仅用已完成订单；中位数/九十分位由 KM 曲线首次到达 50%/10% 的台阶给出。</li>
              <li>曲线未降到对应水平时显示“无法估计”，不以零代替。</li>
            </ol>
          </section>
        </div>
      </div>
    </div>
  );
}
