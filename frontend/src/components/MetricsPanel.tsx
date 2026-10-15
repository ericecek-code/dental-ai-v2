import { useEffect, useState } from "react";
import { fetchMetrics, type Metrics } from "../lib/api";

export function MetricsPanel() {
  const [m, setM] = useState<Metrics | null>(null);

  useEffect(() => {
    fetchMetrics().then(setM).catch(() => undefined);
  }, []);

  if (!m || m.cases_reviewed === 0) return null;

  return (
    <div className="max-w-2xl mx-auto mt-6 bg-slate-900/60 rounded-xl p-4 ring-1 ring-slate-800 flex items-center gap-4 text-sm">
      <div className="text-3xl">{m.agreement_pct !== null && m.agreement_pct >= 70 ? "🤝" : "📊"}</div>
      <div className="flex-1">
        <p className="font-medium">
          Zhoda AI s lekárom:{" "}
          <span className="text-teal-300 text-lg font-semibold">
            {m.agreement_pct !== null ? `${m.agreement_pct} %` : "—"}
          </span>
        </p>
        <p className="text-xs text-slate-500">
          {m.cases_reviewed} prekontrolovaných prípadov · {m.confirmed} potvrdených ·{" "}
          {m.corrected} opravených
        </p>
      </div>
      <div className="h-2 w-28 rounded-full bg-slate-800 overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-teal-400 to-sky-500"
          style={{ width: `${m.agreement_pct ?? 0}%` }}
        />
      </div>
    </div>
  );
}
