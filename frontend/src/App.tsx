import { useEffect, useState } from "react";
import { fetchAnalysis, fetchOptions } from "./api";
import type { AnalysisPayload, FilterOptions } from "./api";
import Dashboard from "./Dashboard";
import type { Controls } from "./Dashboard";

export default function App() {
  const [options, setOptions] = useState<FilterOptions | null>(null);
  const [controls, setControls] = useState<Controls | null>(null);
  const [payload, setPayload] = useState<AnalysisPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [optionsError, setOptionsError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchOptions()
      .then((opts) => {
        if (cancelled) return;
        setOptions(opts);
        setControls({ asOf: opts.default_cutoff, supplier: "", material: "" });
      })
      .catch((err: Error) => {
        if (!cancelled) setOptionsError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!controls) return;
    let cancelled = false;
    setPending(true);
    fetchAnalysis({ asOf: controls.asOf, supplier: controls.supplier, material: controls.material })
      .then((data) => {
        if (cancelled) return;
        setPayload(data);
        setError(null);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setPending(false);
      });
    return () => {
      cancelled = true;
    };
  }, [controls]);

  if (optionsError) {
    return (
      <div className="shell">
        <div className="state-banner error" role="alert">
          无法连接后端：{optionsError}。请确认 API 已启动（uvicorn app.main:app --port 8000）。
        </div>
      </div>
    );
  }

  if (!options || !controls) {
    return (
      <div className="shell">
        <div className="state-banner loading">正在读取订单口径…</div>
      </div>
    );
  }

  return (
    <Dashboard
      controls={controls}
      options={options}
      payload={
        payload ?? {
          as_of: controls.asOf,
          km: {
            total: 0,
            completed: 0,
            waiting: 0,
            steps: [],
            censor_marks: [],
            timeline: [],
            points: [],
            median_days: null,
            p90_days: null,
            max_follow_up_days: 0,
            completed_mean_days: null,
            completed_median_days: null,
            waiting_mean_days: null,
            waiting_max_days: null,
          },
          orders: [],
          cancelled_orders: [],
          completed_orders: [],
          waiting_orders: [],
          counts: { placed: 0, completed: 0, waiting: 0, cancelled: 0, curve: 0 },
          filters: { supplier: null, material: null },
        }
      }
      error={error}
      pending={pending}
      onAsOf={(value) => setControls((c) => (c ? { ...c, asOf: value } : c))}
      onSupplier={(value) => setControls((c) => (c ? { ...c, supplier: value } : c))}
      onMaterial={(value) => setControls((c) => (c ? { ...c, material: value } : c))}
    />
  );
}
