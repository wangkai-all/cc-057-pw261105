export type Status = "completed" | "waiting" | "cancelled";

export interface OrderRow {
  order_id: string;
  supplier: string;
  material: string;
  order_date: string;
  full_receipt_date: string | null;
  cancel_date: string | null;
  status: Status;
  wait_days: number;
  observed_at: string | null;
  future_receipt_ignored: boolean;
  future_cancel_ignored: boolean;
}

export interface Step {
  days: number;
  survival: number;
  at_risk: number;
  received: number;
  censored: number;
  at_risk_orders: string[];
  received_orders: string[];
  censored_orders: string[];
}

export interface DayRisk {
  days: number;
  at_risk: number;
  received: number;
  censored: number;
  survival_after: number;
  at_risk_orders: string[];
  received_orders: string[];
  censored_orders: string[];
}

export interface CensorMark {
  days: number;
  survival: number;
  count: number;
  orders: string[];
}

export interface KmResult {
  total: number;
  completed: number;
  waiting: number;
  steps: Step[];
  censor_marks: CensorMark[];
  timeline: DayRisk[];
  points: { days: number; survival: number }[];
  median_days: number | null;
  p90_days: number | null;
  max_follow_up_days: number;
  completed_mean_days: number | null;
  completed_median_days: number | null;
  waiting_mean_days: number | null;
  waiting_max_days: number | null;
}

export interface AnalysisPayload {
  as_of: string;
  km: KmResult;
  orders: OrderRow[];
  cancelled_orders: OrderRow[];
  completed_orders: OrderRow[];
  waiting_orders: OrderRow[];
  counts: {
    placed: number;
    completed: number;
    waiting: number;
    cancelled: number;
    curve: number;
  };
  filters: { supplier: string | null; material: string | null };
}

export interface FilterOptions {
  suppliers: string[];
  materials: string[];
  min_cutoff: string;
  max_cutoff: string;
  default_cutoff: string;
  cutoff_presets: { date: string; label: string }[];
}

async function json<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export function fetchOptions(): Promise<FilterOptions> {
  return json<FilterOptions>("/api/filters");
}

export function fetchAnalysis(params: {
  asOf: string;
  supplier?: string | null;
  material?: string | null;
}): Promise<AnalysisPayload> {
  const qs = new URLSearchParams({ as_of: params.asOf });
  if (params.supplier) qs.set("supplier", params.supplier);
  if (params.material) qs.set("material", params.material);
  return json<AnalysisPayload>(`/api/analysis?${qs.toString()}`);
}
