import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { UploadZone } from "./components/UploadZone";
import { Viewer } from "./components/Viewer";
import { FindingCard } from "./components/FindingCard";
import Odontogram from "./components/Odontogram";
import { MetricsPanel } from "./components/MetricsPanel";
import { analyzeXray, fetchSecondOpinionRetry, saveFeedback, fetchResult, type AnalyzeResult, type FindingStatus, type Mode, type SecondOpinion } from "./lib/api";
import { API_BASE } from "./lib/api";

type Phase = "idle" | "loading" | "done";

const SEVERITY_LABELS: Record<string, { text: string; cls: string }> = {
  urgent: { text: "Akútne", cls: "bg-red-500/15 text-red-300 ring-red-500/40" },
  treat_soon: { text: "Riešiť čoskoro", cls: "bg-amber-500/15 text-amber-300 ring-amber-500/40" },
  watch: { text: "Sledovať", cls: "bg-sky-500/15 text-sky-300 ring-sky-500/40" },
  restoration: { text: "Restaurácia", cls: "bg-violet-500/15 text-violet-300 ring-violet-500/40" },
};

export default function App() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imgRatio, setImgRatio] = useState<number | null>(null); // šírka/výška — detekcia segmentovej snímky
  const [statuses, setStatuses] = useState<Record<number, FindingStatus>>({});
  const [activeIdx, setActiveIdx] = useState<number | null>(null);
  const [showGradcam, setShowGradcam] = useState(false);
  const [showHeat, setShowHeat] = useState(false); // heatmapa priamo na snímke (blend)
  const [showRest, setShowRest] = useState(false); // restaurácie defaultne skryté (zubár si ich zapne)
  const [bitewing, setBitewing] = useState(false); // bitewing režim: len kazy, bez číslovania zubov
  const [so, setSo] = useState<SecondOpinion | null>(null); // AI druhý názor (Gemini)
  const [showGeminiOnImage, setShowGeminiOnImage] = useState(false); // rámčeky Gemini na snímke
  const [soLoading, setSoLoading] = useState(false);
  const [soError, setSoError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
   const blobUrlRef = useRef<string | null>(null);

  useEffect(() => () => {
    if (timer.current) clearInterval(timer.current);
    // blob URL drží celý súbor v pamäti — bez uvoľnenia zostáva visieť do reloadu
    if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
  }, []);

  const startFakeProgress = () => {
    setProgress(4);
    timer.current = setInterval(() => {
      setProgress((p) => (p < 90 ? p + Math.random() * 3 + 0.5 : p));
    }, 1000);
  };

  const runAnalysis = useCallback(async (file: File, conf: number, mode: Mode) => {
    setPhase("loading");
    setError(null);
    setResult(null);
    setStatuses({});
    setShowGradcam(false);
    // Okamžitý preview cez blob URL
     // Revoke previous blob URL if any
     if (blobUrlRef.current) {
       URL.revokeObjectURL(blobUrlRef.current);
     }
     const blobUrl = URL.createObjectURL(file);
     blobUrlRef.current = blobUrl;
     setImageUrl(blobUrl);
     setSo(null); setSoError(null); // nová analýza = nový druhý názor
     setShowGeminiOnImage(false);
     setImgRatio(null);
     // pomer strán — panorama ≈ 1.7–2.0; bitewing/segment ≈ < 1.5 → upozornenie
     const probe = new Image();
     probe.onload = () => setImgRatio(probe.naturalWidth / probe.naturalHeight);
     probe.src = blobUrl;
     startFakeProgress();
    try {
      const r = await analyzeXray(file, conf, mode);
      setResult(r);
      // Fetch detailed result with feedback
      const detailed = await fetchResult(r.job_id);
      // Voliteľné pole nesmie zničiť hotovú analýzu — inak sa výsledok stratí
      // a používateľ vidí, že obraz snímky blikol a zmizol.
      if (Array.isArray(detailed?.feedback)) {
        detailed.feedback.forEach((fb: { index: number; status: FindingStatus }) => {
          setStatuses((prev) => ({ ...prev, [fb.index]: fb.status }));
        });
      }
      // Po úspešnej analýze prejdeme na backend URL (persistuje po refreshi)
      setImageUrl(`${API_BASE}/uploads/${r.job_id}`);
      setPhase("done");
      setProgress(100);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Neznáma chyba");
      setPhase("idle");
    } finally {
      if (timer.current) clearInterval(timer.current);
    }
  }, []);

  const mark = (idx: number, status: FindingStatus) => {
    setStatuses((s) => ({ ...s, [idx]: status }));
    if (result) saveFeedback(result.job_id, idx, status);
  };

  const activeTooth =
    activeIdx !== null && result?.findings[activeIdx]?.tooth != null
      ? result.findings[activeIdx].tooth!
      : null;

  const selectTooth = (tooth: number | null) => {
    if (!result) return;
    if (tooth === null) return setActiveIdx(null);
    const idx = result.findings.findIndex((f) => f.tooth === tooth);
    setActiveIdx(idx >= 0 ? idx : null);
  };

  // zobrazované nálezy: patológie vždy, restaurácie len po zapnutí prepínača;
  // bitewing režim: len kazy (Caries/Deep Caries), bez číslovania zubov
  // useMemo je tu povinné: nové pole pri každom rendere by zneplatnilo useCallback
  // draw v Vieweri a spôsobilo úplné prekreslenie canvasu pri každej zmene UI.
  const visible = useMemo(
    () =>
      result
        ? result.findings
            .map((f, i) => ({ f, i }))
            .filter(({ f }) => (showRest || f.severity !== "restoration"))
            .filter(({ f }) => !bitewing || f.label === "Caries" || f.label === "Deep Caries")
            .map(({ f, i }) => ({ f: bitewing ? { ...f, tooth: undefined } : f, i }))
        : [],
    [result, showRest, bitewing],
  );

  const viewerFindings = useMemo(() => visible.map((v) => v.f), [visible]);

  // orientačné rámčeky Gemini (len nálezy s udaným číslom zuba)
  const geminiBoxes = useMemo(
    () =>
      showGeminiOnImage && so?.success
        ? so.gemini_detections
            .filter((g) => Array.isArray(g.bbox_estimate))
            .map((g) => ({
              label: g.label,
              tooth: g.tooth,
              confidence: g.confidence,
              bbox: g.bbox_estimate as [number, number, number, number],
            }))
        : [],
    [showGeminiOnImage, so],
  );

  return (
    <div className="min-h-screen flex flex-col">
      <header className="glass sticky top-0 z-10 border-b border-slate-800/50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-400 to-sky-500 flex items-center justify-center text-xl shadow-lg shadow-teal-500/20">
              🦷
            </div>
            <div>
              <h1 className="font-semibold leading-tight text-slate-100">Dental AI</h1>
              <p className="text-xs text-slate-400 leading-tight">
                Druhý pohľad na RTG snímku
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-3 py-1.5 rounded-full glass text-slate-300 font-medium">
              demo · nie diagnóza
            </span>
            <a
              href="/logout"
              className="text-xs px-3 py-1.5 rounded-full bg-slate-800/80 hover:bg-slate-700 ring-1 ring-slate-700 text-slate-300 transition"
              title="Odhlásiť sa"
            >
              Odhlásiť
            </a>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6">
        {phase === "idle" && (
          <>
              <div className="flex items-center gap-2 mb-3 text-xs">
                <button
                  onClick={() => setBitewing((v) => !v)}
                  className={`px-3 py-1.5 rounded-lg font-medium ring-1 transition ${
                    bitewing
                      ? "bg-sky-500/20 text-sky-300 ring-sky-500/40"
                      : "bg-slate-800/60 text-slate-400 ring-slate-700 hover:bg-slate-800"
                  }`}
                >
                  🦷 Bitewing režim {bitewing ? "ZAP" : "vyp"}
                </button>
                <span className="text-slate-500">
                  {bitewing
                    ? "detekcia kazu bez číslovania zubov — pre segmentové snímky"
                    : "štandard: panoramatické RTG s číslovaním zubov"}
                </span>
              </div>
            <UploadZone onAnalyze={runAnalysis} error={error} />
            <MetricsPanel />
          </>
        )}

        {phase === "loading" && (
          <div className="max-w-2xl mx-auto mt-24 text-center space-y-6">
            <div className="relative w-24 h-24 mx-auto">
              <div className="absolute inset-0 rounded-full bg-teal-500/20 animate-pulse-ring" />
              <div className="absolute inset-2 rounded-full bg-teal-500/10 animate-pulse-ring" style={{ animationDelay: "0.5s" }} />
              <div className="absolute inset-0 flex items-center justify-center text-4xl">🦷</div>
            </div>
            <h2 className="text-lg font-medium text-slate-200">Analyzujem snímku…</h2>
            <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-teal-400 to-sky-500 transition-all duration-300 rounded-full"
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="flex justify-center gap-2">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="w-2 h-2 rounded-full bg-teal-400/60 animate-pulse-slow"
                  style={{ animationDelay: `${i * 0.3}s` }}
                />
              ))}
            </div>
            {imageUrl && (
              <img
                src={imageUrl}
                alt="RTG"
                className="mx-auto max-h-64 rounded-xl opacity-40 ring-1 ring-slate-800"
              />
            )}
          </div>
        )}

        {phase === "done" && result && imageUrl && (
          <>
            {imgRatio !== null && imgRatio < 1.5 && (
              <div className="rounded-xl bg-amber-500/10 ring-1 ring-amber-500/30 p-3 text-xs text-amber-200/90 flex items-start gap-2">
                <span>⚠️</span>
                <span>
                  <b>Segmentová snímka (bitewing?)</b> — aplikácia je zatiaľ ladená na{" "}
                  <b>panoramatické RTG</b>. Detekcia aj heatmapa fungujú, ale{" "}
                  <b>čísla zubov sú len orientačné</b> — overte ich v odontograme.
                </span>
              </div>
            )}
            {bitewing && (
              <div className="rounded-xl bg-sky-500/10 ring-1 ring-sky-500/30 p-3 text-xs text-sky-200/90 flex items-start gap-2">
                <span>🦷</span>
                <span>
                  <b>Bitewing režim</b> — zobrazené sú len kazy (Caries / Deep Caries),
                  číslovanie zubov a odontogram sú vypnuté.
                </span>
              </div>
            )}
          <div className="grid lg:grid-cols-[1fr_380px] gap-6">
              <Viewer
                imageUrl={imageUrl}
                findings={viewerFindings}
                activeIdx={activeIdx}
                onSelect={(i) => { if (i === null) { setActiveIdx(null); return; } const v = visible[i]; setActiveIdx(v ? v.i : null); }}
                heatmapUrl={showHeat ? `${API_BASE}/gradcam/${result.job_id}` : null}
                geminiFindings={geminiBoxes}
              />
              {/* Rýchla akčná lišta — Súhlasím/Opraviť hneď pod snímkou */}
              {activeIdx != null && result.findings[activeIdx] && (
                <div className="flex flex-wrap items-center gap-3 rounded-xl bg-slate-900/70 ring-1 ring-slate-800 p-3 glass">
                  <span className="text-sm text-slate-300 font-medium">
                    Zub {result.findings[activeIdx].tooth ?? "?"} ·{" "}
                    {result.findings[activeIdx].label_sk}{" "}
                    <span className="text-slate-500">
                      ({(result.findings[activeIdx].confidence * 100).toFixed(0)} %)
                    </span>
                  </span>
                  {(statuses[activeIdx] ?? "ai") === "ai" ? (
                    <>
                      <button
                        onClick={() => mark(activeIdx, "confirmed")}
                        className="text-sm px-4 py-2 rounded-lg bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/40 hover:bg-emerald-500/25 active:scale-95 transition-all font-medium"
                      >
                        ✓ Súhlasím
                      </button>
                      <button
                        onClick={() => mark(activeIdx, "corrected")}
                        className="text-sm px-4 py-2 rounded-lg bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/40 hover:bg-amber-500/25 active:scale-95 transition-all font-medium"
                      >
                        ✎ Opraviť
                      </button>
                    </>
                  ) : (
                    <span
                      className={`text-sm font-medium ${
                        statuses[activeIdx] === "confirmed" ? "text-emerald-300" : "text-amber-300"
                      }`}
                    >
                      {statuses[activeIdx] === "confirmed" ? "✓ potvrdené lekárom" : "✎ opravené lekárom"}
                    </span>
                  )}
                  <span className="text-xs text-slate-500 ml-auto">
                    kliknite na box alebo kartu nálezu na výber
                  </span>
                </div>
              )}
              {showGradcam && (
                <div className="rounded-xl overflow-hidden ring-1 ring-slate-800 bg-black">
                  <p className="text-xs text-slate-400 px-3 py-2 bg-slate-900/80">
                    🔥 Grad-CAM — kam sa model pozerá pri náleze s najvyššou istotou
                  </p>
                  <img
                    src={`${API_BASE}/gradcam/${result.job_id}`}
                    alt="Grad-CAM heatmapa"
                    className="w-full"
                  />
                </div>
              )}
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <a
                  href={`${API_BASE}/report/${result.job_id}`}
                  className="px-3 py-1.5 rounded-lg bg-teal-500/10 text-teal-300 ring-1 ring-teal-500/30 hover:bg-teal-500/20 transition text-xs font-medium"
                >
                  📄 PDF report pre pacienta
                </a>
                <button
                  onClick={() => setShowGradcam((v) => !v)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium ring-1 transition ${
                    showGradcam
                      ? "bg-orange-500/15 text-orange-300 ring-orange-500/30"
                      : "bg-orange-500/10 text-orange-300/80 ring-orange-500/30 hover:bg-orange-500/20"
                  }`}
                >
                  🔥 Grad-CAM {showGradcam ? "skryť" : "ukázať"}
                </button>
                <span className="ml-auto text-xs text-slate-500">
                  {result.count} nálezov · {result.duration_ms} ms ·{" "}
                  {result.mode === "tiles"
                    ? "hĺbkový sken"
                    : result.mode === "ens"
                      ? "ensemble 2 modely"
                      : "štandard"}
                </span>
              </div>
                <button
                  onClick={() => setShowHeat((v) => !v)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium ring-1 transition ${
                    showHeat
                      ? "bg-rose-500/20 text-rose-300 ring-rose-500/40"
                      : "bg-rose-500/10 text-rose-300/80 ring-rose-500/30 hover:bg-rose-500/20"
                  }`}
                >
                  🌡 Heatmapa na snímke {showHeat ? "skryť" : "ukázať"}
                </button>
                <button
                  onClick={() => setShowRest((v) => !v)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium ring-1 transition ${
                    showRest
                      ? "bg-violet-500/20 text-violet-300 ring-violet-500/40"
                      : "bg-violet-500/10 text-violet-300/70 ring-violet-500/30 hover:bg-violet-500/20"
                  }`}
                >
                  🔧 Plomby/implantáty {showRest ? "skryť" : "ukázať"}
                </button>
                <button
                  onClick={() => setBitewing((v) => !v)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium ring-1 transition ${
                    bitewing
                      ? "bg-sky-500/20 text-sky-300 ring-sky-500/40"
                      : "bg-sky-500/10 text-sky-300/70 ring-sky-500/30 hover:bg-sky-500/20"
                  }`}
                >
                  🦷 Bitewing režim {bitewing ? "ZAP (len kazy)" : "vyp"}
                </button>
                <button
                  onClick={() => {
                    if (!result) return;
                    setSoLoading(true); setSoError(null);
                    fetchSecondOpinionRetry(result.job_id)
                      .then(setSo)
                      .catch((e: unknown) => setSoError(e instanceof Error ? e.message : String(e)))
                      .finally(() => setSoLoading(false));
                  }}
                  disabled={soLoading}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium ring-1 transition bg-sky-500/10 text-sky-300 ring-sky-500/30 hover:bg-sky-500/20 disabled:opacity-50"
                >
                  {soLoading ? "🤖 Gemini analyzuje…" : "🤖 AI druhý názor (Gemini)"}
                </button>
                {so?.success && (
                  <button
                    onClick={() => setShowGeminiOnImage((v) => !v)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium ring-1 transition ${
                      showGeminiOnImage
                        ? "bg-sky-500/20 text-sky-200 ring-sky-500/40"
                        : "bg-sky-500/10 text-sky-300/80 ring-sky-500/30 hover:bg-sky-500/20"
                    }`}
                  >
                    🤖 Gemini na snímke {showGeminiOnImage ? "skryť" : "ukázať"}
                  </button>
                )}
            <aside className="space-y-3 lg:sticky lg:top-[76px] lg:max-h-[calc(100vh-100px)] lg:overflow-y-auto lg:pr-1">
              {soError && (
                <div className="text-xs text-rose-300 bg-rose-500/10 ring-1 ring-rose-500/30 rounded-lg p-2">{soError}</div>
              )}
              {soLoading && (
                <div className="rounded-xl bg-slate-900/70 ring-1 ring-sky-500/30 p-3 text-xs text-sky-300 animate-pulse-slow">
                  🤖 Gemini analyzuje snímku… (typicky 30–120 s)
                </div>
              )}
              {so && so.success && (
                <div className="space-y-2 rounded-xl bg-slate-900/70 ring-1 ring-sky-500/30 p-4 glass">
                  <p className="text-xs uppercase tracking-wide text-sky-300 font-medium">
                    🤖 AI druhý názor (Gemini VLM) · {so.processing_time_ms} ms
                    {so.model ? ` · ${so.model}` : ""}
                  </p>
                  <p className="text-[11px] text-slate-500">
                    Rámčeky na snímke sú orientačné — odvodené z čísla zuba
                    (Gemini nevracia súradnice).
                  </p>
                  {so.overall_assessment && (
                    <p className="text-sm text-slate-200 leading-relaxed">{so.overall_assessment}</p>
                  )}
                  {so.comparison.summary.matched_count > 0 && (
                    <div className="text-xs text-slate-300">
                      <p className="text-emerald-300 font-medium">Zhoda YOLO × Gemini: {so.comparison.summary.matched_count}</p>
                      <ul className="mt-1 space-y-1">
                        {so.comparison.matched.map((m, i) => (
                          <li key={i} className="bg-slate-800/60 rounded-lg px-3 py-1.5">
                            <b>{m.label}</b> · zub {m.tooth} · YOLO {(m.yolo_confidence * 100).toFixed(0)} % / Gemini {(m.gemini_confidence * 100).toFixed(0)} %
                            {m.description_gemini && <span className="text-slate-400"> — {m.description_gemini}</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {so.comparison.summary.gemini_only_count > 0 && (
                    <div className="text-xs text-slate-400">
                      <p className="text-amber-300 font-medium">Len Gemini (YOLO nevidel): {so.comparison.summary.gemini_only_count}</p>
                      <ul className="mt-1 space-y-1">
                        {so.comparison.gemini_only.map((g, i) => (
                          <li key={i} className="bg-slate-800/40 rounded-lg px-3 py-1.5">
                            <b>{g.label}</b>{g.tooth ? ` · zub ${g.tooth}` : ""} · {(g.confidence * 100).toFixed(0)} %
                            {g.description && <span> — {g.description}</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {so.comparison.summary.gemini_count === 0 && (
                    <p className="text-xs text-slate-400">Gemini nevrátil žiadne nálezy pre túto snímku.</p>
                  )}
                  <p className="text-[11px] text-slate-500">Dva nezávislé pohľady: YOLO detektor + jazykový model. Zhoda zvyšuje dôveru, rozdiel = overiť.</p>
                </div>
              )}
              {so && !so.success && (
                <div className="text-xs text-rose-300 bg-rose-500/10 ring-1 ring-rose-500/30 rounded-lg p-2">{so.error}</div>
              )}
              <h2 className="font-medium text-slate-300 text-sm uppercase tracking-wide">
                Nálezy — potvrďte alebo opravte
              </h2>
              {visible.map(({ f, i }) => (
                <FindingCard
                  key={i}
                  index={i}
                  finding={f}
                  status={statuses[i] ?? "ai"}
                  onMark={mark}
                  active={activeIdx === i}
                  onSelect={setActiveIdx}
                  severityMeta={SEVERITY_LABELS[f.severity]}
                />
              ))}
              {visible.length === 0 && (
                <p className="text-sm text-slate-400 bg-slate-900 rounded-lg p-4 ring-1 ring-slate-800">
                  Žiadne zobrazené nálezy. Skúste znížiť prah citlivosti
                  alebo zapnúť restaurácie.
                </p>
              )}
              {result.count === 0 && (
                <p className="text-sm text-slate-400 bg-slate-900 rounded-lg p-4 ring-1 ring-slate-800">
                  AI nenašla žiadne nálezy nad zvolenou citlivosťou. Skúste
                  znížiť prah citlivosti.
                </p>
              )}
            </aside>
          </div>

          {/* Odontogram — celá šírka, dole pod výsledkami (skrytý v bitewing režime) */}
          {!bitewing && (
            <div className="mt-2 bg-slate-900/50 rounded-2xl ring-1 ring-slate-800 p-5 glass">
              <Odontogram
                findings={viewerFindings.filter(
                  (f): f is typeof f & { tooth: number } => f.tooth != null,
                )}
                activeTooth={activeTooth}
                onSelectTooth={selectTooth}
              />
            </div>
          )}
          </>
        )}
      </main>

      <footer className="border-t border-slate-800/50 py-4 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>Dental AI v2 · demo pre súkromné použitie</span>
          <span>AI je asistent — klinické rozhodnutie vždy patrí lekárovi</span>
        </div>
      </footer>
    </div>
  );
}




