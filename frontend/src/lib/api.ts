export type Severity = "urgent" | "treat_soon" | "watch" | "restoration";
export type FindingStatus = "ai" | "confirmed" | "corrected";

export interface Finding {
  label: string;
  label_sk: string;
  severity: Severity;
  confidence: number;
  bbox: [number, number, number, number]; // x1, y1, x2, y2 v pixeloch originálu
  uncertainty?: number; // std confidence z MC Dropout (0.0 = bez meranej neistoty)
  tooth?: number; // približné FDI číslo zuba z pozície
}

export interface AnalyzeResult {
  job_id: string;
  filename: string;
  duration_ms: number;
  count: number;
  mode?: "standard" | "tiles" | "ens";
  findings: Finding[];
  feedback?: { index: number; status: FindingStatus }[];
}

// dev: cez Vite proxy (/api → :8000); prod: backend servíruje frontend z toho istého originu
export const API_BASE = import.meta.env.DEV ? "/api" : "";
const BASE = API_BASE;

export type Mode = "standard" | "tiles" | "ens";

export async function analyzeXray(file: File, conf: number, mode: Mode = "standard"): Promise<AnalyzeResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/analyze?conf=${conf}&mode=${mode}`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    if (res.status === 401) { window.location.href = "/login"; throw new Error("Neautorizovaný"); }
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Server odpovedal ${res.status}`);
  }
  return res.json();
}

export async function saveFeedback(jobId: string, index: number, status: FindingStatus): Promise<boolean> {
  if (status === "ai") return false;
  const res = await fetch(`${BASE}/results/${jobId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ index, status }),
  }).catch((e) => { console.error("Feedback sa nepodarilo uložiť:", e); return null; });
  return res?.ok ?? false;
}

export interface Metrics {
  cases_reviewed: number;
  confirmed: number;
  corrected: number;
  agreement_pct: number | null;
}

export async function fetchMetrics(): Promise<Metrics> {
  const res = await fetch(`${BASE}/metrics`);
  if (res.status === 401) { window.location.href = "/login"; throw new Error("Neautorizovaný"); }
  if (!res.ok) throw new Error("Metriky nie sú dostupné");
  return res.json();
}

export async function fetchResult(jobId: string): Promise<AnalyzeResult> {
  const res = await fetch(`${BASE}/results/${jobId}`);
  if (res.status === 401) { window.location.href = "/login"; throw new Error("Neautorizovaný"); }
  if (!res.ok) throw new Error(`Výsledok ${jobId} nenájdený`);
  return res.json();
}

export interface GeminiDetection {
  label: string;
  tooth: string;
  confidence: number;
  severity: string;
  description: string;
  /** orientačný rámček odvodený z čísla zuba (Gemini nevracia súradnice) */
  bbox_estimate?: [number, number, number, number] | null;
  bbox_estimate_source?: string | null;
}

export interface SecondOpinion {
  job_id: string;
  success: boolean;
  error: string | null;
  model?: string | null;
  overall_assessment: string;
  gemini_detections: GeminiDetection[];
  processing_time_ms: number;
  comparison: {
    matched: {
      label: string;
      tooth: string;
      yolo_confidence: number;
      gemini_confidence: number;
      description_gemini: string;
      bbox_estimate?: [number, number, number, number] | null;
    }[];
    yolo_only: { label: string; tooth: string; confidence: number }[];
    gemini_only: GeminiDetection[];
    summary: { yolo_count: number; gemini_count: number; matched_count: number; yolo_only_count: number; gemini_only_count: number };
  };
}

export async function fetchSecondOpinion(jobId: string): Promise<SecondOpinion> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 300000); // 5 min hard limit
  try {
    const res = await fetch(`${BASE}/vision/${jobId}`, { method: "POST", signal: ctrl.signal });
    if (res.status === 401) { window.location.href = "/login"; throw new Error("Neautorizovaný"); }
    if (!res.ok) {
      const detail = await res.json().catch(() => null);
      throw new Error(detail?.detail ?? `Server odpovedal ${res.status}`);
    }
    return res.json();
  } finally {
    clearTimeout(t);
  }
}

export async function fetchSecondOpinionRetry(jobId: string, tries = 2): Promise<SecondOpinion> {
  let lastErr: Error | null = null;
  for (let i = 0; i < tries; i++) {
    try {
      return await fetchSecondOpinion(jobId);
    } catch (e) {
      lastErr = e as Error;
      if (i < tries - 1) await new Promise((r) => setTimeout(r, 2000));
    }
  }
  throw lastErr ?? new Error("Neznáma chyba");
}
