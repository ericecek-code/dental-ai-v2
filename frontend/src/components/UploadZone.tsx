import { useEffect, useRef, useState } from "react";
import type { Mode } from "../lib/api";

interface Props {
  onAnalyze: (file: File, conf: number, mode: Mode) => void;
  error: string | null;
}

const MODES: { id: Mode; label: string; hint: string; icon: string }[] = [
  { id: "standard", label: "Štandard", hint: "originál + CLAHE pohľad (~5 s)", icon: "⚡" },
  { id: "tiles", label: "Hĺbkový sken", hint: "dlaždice v plnom rozlíšení — malé kazy (~5–15 s)", icon: "🔍" },
  { id: "ens", label: "Ensemble", hint: "dva modely sa dohodnú — najvyššia istota (~8 s)", icon: "🤝" },
];

export function UploadZone({ onAnalyze, error }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [conf, setConf] = useState(0.25);
  const [mode, setMode] = useState<Mode>("standard");
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // blob URL náhľadu sa uvoľní pri unmount-e (inak zostáva snímka v pamäti)
  const previewRef = useRef<string | null>(null);
  useEffect(() => () => {
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
  }, []);

  const pick = (f: File | null) => {
    if (!f) return;
    if (previewRef.current) {
      URL.revokeObjectURL(previewRef.current);
    }
    const url = URL.createObjectURL(f);
    previewRef.current = url;
    setFile(f);
    setPreview(url);
  };
  return (
    <div className="max-w-2xl mx-auto mt-10 space-y-6">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          pick(e.dataTransfer.files?.[0] ?? null);
        }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-2xl border-2 border-dashed p-12 text-center transition-all duration-300 card-hover
          ${dragOver
            ? "border-teal-400 bg-teal-400/5 scale-[1.01] shadow-lg shadow-teal-500/10"
            : "border-slate-700 hover:border-slate-500 bg-slate-900/50 hover:bg-slate-900/70"}`}
      >
        {preview ? (
          <img
            src={preview}
            alt="Náhľad RTG"
            className="mx-auto max-h-72 rounded-xl ring-1 ring-slate-700 shadow-lg"
          />
        ) : (
          <>
            <div className="text-5xl mb-4 animate-float">📤</div>
            <p className="font-medium text-lg text-slate-200">Pretiahnite RTG snímku sem</p>
            <p className="text-sm text-slate-400 mt-2">
              alebo kliknite a vyberte súbor (JPG, PNG, DICOM)
            </p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => pick(e.target.files?.[0] ?? null)}
        />
      </div>

      <div className="glass rounded-xl p-5 space-y-4">
        <div>
          <div className="flex items-center justify-between text-sm">
            <label htmlFor="conf" className="font-medium text-slate-200">
              Citlivosť detekcie
            </label>
            <span className="text-teal-300 font-mono bg-teal-500/10 px-2 py-0.5 rounded">{conf.toFixed(2)}</span>
          </div>
          <input
            id="conf"
            type="range"
            min={0.05}
            max={0.95}
            step={0.05}
            value={conf}
            onChange={(e) => setConf(Number(e.target.value))}
            className="w-full mt-3 accent-teal-400"
          />
          <p className="text-xs text-slate-500 mt-2">
            Nižšia citlivosť = AI hlási viac nálezov (vyšší recall, viac falošných
            poplachov). Pre druhý pohľad odporúčame 0.20–0.30.
          </p>
        </div>
        <div>
          <p className="text-sm font-medium mb-3 text-slate-200">Režim analýzy</p>
          <div className="grid sm:grid-cols-3 gap-3">
            {MODES.map((m) => (
              <button
                key={m.id}
                onClick={() => setMode(m.id)}
                className={`text-left px-4 py-3 rounded-xl ring-1 transition-all duration-200 card-hover ${
                  mode === m.id
                    ? "bg-teal-500/15 text-teal-200 ring-teal-500/40 shadow-md shadow-teal-500/10"
                    : "bg-slate-800/60 text-slate-300 ring-slate-700 hover:bg-slate-800 hover:ring-slate-600"
                }`}
              >
                <span className="text-lg">{m.icon}</span>
                <span className="block font-medium text-[13px] mt-1">{m.label}</span>
                <span className="text-xs text-slate-500 leading-tight block mt-0.5">{m.hint}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <p className="text-sm text-red-300 bg-red-500/10 ring-1 ring-red-500/30 rounded-lg px-4 py-3 animate-fade-in-up">
          {error}
        </p>
      )}

      <button
        disabled={!file}
        onClick={() => file && onAnalyze(file, conf, mode)}
        className="w-full py-3.5 rounded-xl font-medium bg-gradient-to-r from-teal-500 to-sky-600
          hover:from-teal-400 hover:to-sky-500 disabled:opacity-40 disabled:cursor-not-allowed
          transition-all duration-200 shadow-lg shadow-teal-500/20 hover:shadow-teal-500/30
          active:scale-[0.98] text-white"
      >
        Analyzovať snímku
      </button>
    </div>
  );
}





