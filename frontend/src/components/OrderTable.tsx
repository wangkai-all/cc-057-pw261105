import { useState } from "react";
import type { OrderRow, Status } from "../api";

const TABS: { key: Status; label: string }[] = [
  { key: "completed", label: "已全量收货" },
  { key: "waiting", label: "待收货（右删失）" },
];

interface Props {
  rows: OrderRow[];
  counts: { completed: number; waiting: number; cancelled: number };
  asOf: string;
}

export default function OrderTable({ rows, counts, asOf }: Props) {
  const [tab, setTab] = useState<Status>("waiting");
  const [expanded, setExpanded] = useState(true);
  const visible = rows.filter((r) => r.status === tab);

  return (
    <div className="card table-card">
      <div className="card-head">
        <div>
          <h2 style={{ margin: 0 }}>逐单核对</h2>
          <p>截止日 {asOf} 还原后的状态。等待天数为自然日：收货日或截止日与下单日之差。</p>
        </div>
        <button className="toggle-table" type="button" onClick={() => setExpanded((v) => !v)}>
          {expanded ? "收起明细" : "展开明细"}
        </button>
      </div>

      <div className="cutoff-presets" role="tablist" aria-label="订单状态" style={{ marginTop: 10 }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            className="preset"
            aria-selected={tab === t.key}
            aria-pressed={tab === t.key}
            onClick={() => setTab(t.key)}
          >
            {t.label} ({counts[t.key]})
          </button>
        ))}
        <span className="tab-note">已取消 {counts.cancelled} 单单列于右侧</span>
      </div>

      {expanded && (
        <>
          <div className="table-scroll">
            {visible.length === 0 ? (
              <div style={{ padding: 18, color: "var(--muted)" }}>该状态下没有订单。</div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>订单</th>
                    <th>供应商</th>
                    <th>物料</th>
                    <th>下单日</th>
                    <th>全量收货日</th>
                    <th>取消日</th>
                    <th>状态</th>
                    <th className="num">{tab === "waiting" ? "已等待天数" : "交期（自然日）"}</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((row) => {
                    const ignored = row.future_receipt_ignored || row.future_cancel_ignored;
                    return (
                      <tr key={row.order_id} className={ignored ? "future" : undefined}>
                        <td>{row.order_id}</td>
                        <td>{row.supplier}</td>
                        <td>{row.material}</td>
                        <td>{row.order_date}</td>
                        <td className={row.full_receipt_date ? "" : "muted-cell"}>
                          {row.full_receipt_date ?? "—"}
                        </td>
                        <td className={row.cancel_date ? "" : "muted-cell"}>
                          {row.cancel_date ?? "—"}
                        </td>
                        <td>
                          <StatusBadge status={row.status} />
                        </td>
                        <td className="num">
                          {row.wait_days}
                          {tab === "waiting" && <span className="flag">右删失</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
          <div className="footnote">
            高亮行表示该订单在截止日之后另有收货或取消记录；截止日当天不会提前生效。
            {tab === "waiting" && " 待收货订单的等待天数按截止日截断，构成右删失观测。"}
          </div>
        </>
      )}
    </div>
  );
}

export function StatusBadge({ status }: { status: Status }) {
  const label = status === "completed" ? "已收货" : status === "waiting" ? "待收货" : "已取消";
  return <span className={`badge ${status}`}>{label}</span>;
}
