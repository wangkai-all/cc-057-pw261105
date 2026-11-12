# 交期分析 · 已收货与待收货

同一页面还原统计截止日的订单状态，并估计交期分布：

- 已全量收货的订单记录交期（自然日），另列平均交期；
- 截止日仍未收货的订单按截止日截断，记录已等待天数并标为右删失；
- 截止日或之前已取消的订单单列，不进入交期曲线，页面注明曲线范围；
- Kaplan–Meier 曲线展示“尚未收货比例”随等待天数的变化；同一等待天数既有收货又有删失时，先计算收货事件，再移除删失；
- 点选台阶查看该等待天数的风险集、收货订单和删失订单；
- 曲线尚未降到 50% / 10% 时，中位数、九十分位显示“无法估计”，不填零。

技术栈：Python + DuckDB + FastAPI，React + TypeScript（Vite）。

## 目录

```
backend/
  app/model.py       日期校验、截止日状态还原、观测与逐单核对行
  app/km.py          Kaplan–Meier 估计（按公式实现，无额外统计依赖）
  app/analysis.py    单次请求的完整响应
  app/data.py        DuckDB 内存库、CSV 装载、筛选项
  app/main.py        FastAPI 接口
  data/orders.csv    样例订单（35 单，见下）
  data/make_sample.py 生成样例（含设计说明）
  tests/             单元测试与接口测试
frontend/
  src/Dashboard.tsx  页面骨架、筛选与口径说明
  src/components/KmChart.tsx  KM 阶梯曲线、删失标记、台阶点选
  src/components/DayDetail.tsx 风险集/收货/删失明细
  src/components/OrderTable.tsx 已收货、待收货逐单核对
  src/components/CancelledCard.tsx 截止日前取消订单单列
```

## 运行

后端（Python 3.11+）：

```bash
python3 -m venv .venv
.venv/bin/pip install duckdb fastapi "uvicorn[standard]" pytest httpx
cd backend
PYTHONPATH=. ../.venv/bin/python -m uvicorn app.main:app --port 8000
```

前端（Node 20+）：

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 ，/api 代理到 127.0.0.1:8000
```

生产构建：`npm run build` 后用 `npm run preview`；若后端不在 8000 端口，设置 `BACKEND_URL`。

测试：

```bash
cd backend && PYTHONPATH=. ../.venv/bin/python -m pytest -q tests
```

## 口径

1. 日期差按自然日计算；交期 = 全量收货日 − 下单日，已等待天数 = 截止日 − 下单日。
2. 还原截止日状态：只认截止日当天及之前的收货/取消。截止日之后才发生的收货或取消不提前生效。
3. 截止日当天发生的收货计为已收货；取消同理。
4. 截止日之后才下单的订单在该截止日尚未存在，不进入任何列表。
5. 截止日前已取消的订单不进入曲线；取消日晚于截止日的订单在本次截止日仍按待收货计入。
6. 平均交期只用已完成订单；尚未收货订单的平均已等待天数单列。
7. 同日既有收货又有删失：删失单仍计入当日风险集，先算收货，再从风险集移除。
8. 中位数 = 未收货比例首次 ≤ 50% 的等待天数；九十分位同理对应 ≤ 10%。曲线未达到该水平时返回 `null`，页面显示“无法估计”。

## 接口

- `GET /api/filters` — 供应商、物料、截止日范围与快捷截止日（月末、数据最新）。
- `GET /api/analysis?as_of=YYYY-MM-DD&supplier=&material=` — 曲线、逐单状态、已取消单、计数。
  订单行带 `future_receipt_ignored` / `future_cancel_ignored`，用于在表格中高亮“截止日后另有事件”的订单。
- `GET /api/health`、`GET /api/orders/{order_id}`、`POST /api/reload`。

## 样例数据

35 单刻意覆盖每种页面状态：

| 订单 | 覆盖点 |
|---|---|
| A-1001…A-1005 | 已收货，14–25 天短交期 |
| B-2001…B-2005 | 截止日 2026-06-30 时全部待收货（右删失） |
| C-3001 / C-3002 | 同日第 12 天：C-3001 收货、C-3002 删失（验证“先收货再删失”） |
| D-4001…D-4005 | 90–140 天长交期，决定曲线尾部与九十分位 |
| E-5001…E-5003 | 截止日前取消，单列且不进曲线 |
| F-6001 | 2026-07-10 收货：截止日 06-30 时仍待收货，切到 07-20 后才完成 |
| F-6002 | 2026-07-20 取消：06-30 时仍在曲线内，切到 07-20 后进入取消单列 |
| G-7001 / G-7002 | 收货日 = 截止日当天（计入）/ 次日（不计入） |
| K-9001…K-9003 | 全部待收货的供应商：曲线保持 100%，中位数无法估计 |
| L-9101…L-9103 | 全部已收货的供应商：曲线降到 0%，无删失 |

切换快捷截止日的默认值“数据最新”（2026-07-20）与“6 月末”（2026-06-30），即可逐单核对 F-6001、F-6002、G-7001 的状态翻转。
