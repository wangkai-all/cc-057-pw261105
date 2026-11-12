import type { OrderRow } from "../api";

interface Props {
  rows: OrderRow[];
}

export default function CancelledCard({ rows }: Props) {
  return (
    <div className="card cancelled-card">
      <div className="card-head">
        <div>
          <h2>
            截止日前已取消 <span className="count-pill">{rows.length}</span>
          </h2>
          <p>
            这些订单在截止日或之前已取消，<strong>不进入交期曲线</strong>；
            下方曲线与中位数均已剔除它们。取消日期晚于截止日的订单在本次截止日仍按待收货计入曲线。
          </p>
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="detail-panel">
          <div className="empty">本次筛选与截止日下没有已取消订单。</div>
        </div>
      ) : (
        <div className="table-scroll" style={{ maxHeight: 260 }}>
          <table>
            <thead>
              <tr>
                <th>订单</th>
                <th>供应商</th>
                <th>物料</th>
                <th>下单日</th>
                <th>取消日</th>
                <th className="num">下单至取消（天）</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.order_id}>
                  <td>{row.order_id}</td>
                  <td>{row.supplier}</td>
                  <td>{row.material}</td>
                  <td>{row.order_date}</td>
                  <td>{row.cancel_date ?? "—"}</td>
                  <td className="num">{row.wait_days}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
