import type { FindingStatus } from "../lib/api";
import type { Finding } from "../lib/api";

interface Props {
  index: number;
  finding: Finding;
  status: FindingStatus;
  onMark: (index: number, status: FindingStatus) => void;
  active: boolean;
  onSelect: (index: number) => void;
  severityMeta: { text: string; cls: string };
}

const STATUS_BADGE: Record<FindingStatus, { text: string; cls: string } | null> = {
  ai: null,
  confirmed: { text: "✓ potvrdené lekárom", cls: "text-emerald-300" },
  corrected: { text: "✎ opravené lekárom", cls: "text-amber-300" },
};

export function FindingCard({
  index,
  finding,
  status,
  onMark,
  active,
  onSelect,
  severityMeta,
}: Props) {
  const badge = STATUS_BADGE[status];
  return (
    <div
      onClick={() => onSelect(index)}
      className={`glass rounded-xl p-3 ring-1 transition-all duration-200 cursor-pointer animate-fade-in-up card-hover
        ${active ? "ring-teal-400/60 bg-slate-900/80 glow-teal" : "ring-slate-800/60 hover:ring-slate-700"}`}
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="shrink-0 text-[11px] font-bold px-2 py-0.5 rounded-md bg-slate-800 text-teal-300 ring-1 ring-teal-500/25">
            {finding.tooth ? `Z ${finding.tooth}` : "—"}
          </span>
          <div className="min-w-0">
            <p className="font-medium text-slate-100 truncate">{finding.label_sk}</p>
            <p className="text-[11px] text-slate-500 truncate">{finding.label}</p>
          </div>
        </div>
        <span
          className={`shrink-0 text-[11px] px-2 py-0.5 rounded-full ring-1 font-medium ${severityMeta.cls}`}
        >
          {severityMeta.text}
        </span>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <div className="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-teal-400 to-sky-500 transition-all duration-500"
            style={{ width: `${finding.confidence * 100}%` }}
          />
        </div>
        <span className="text-xs font-mono text-slate-400">
          {(finding.confidence * 100).toFixed(0)} %
        </span>
      </div>
      <div className="mt-2 flex items-center gap-2">
        {status === "ai" ? (
          <>
            <button
              onClick={(e) => { e.stopPropagation(); onMark(index, "confirmed"); }}
              className="text-xs px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-300
                ring-1 ring-emerald-500/30 hover:bg-emerald-500/20 hover:ring-emerald-500/50
                active:scale-95 transition-all duration-150 font-medium"
            >
              ✓ Súhlasím
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onMark(index, "corrected"); }}
              className="text-xs px-3 py-1.5 rounded-lg bg-amber-500/10 text-amber-300
                ring-1 ring-amber-500/30 hover:bg-amber-500/20 hover:ring-amber-500/50
                active:scale-95 transition-all duration-150 font-medium"
            >
              ✎ Opraviť
            </button>
          </>
        ) : (
          <span className={`text-xs font-medium ${badge!.cls}`}>{badge!.text}</span>
        )}
      </div>
    </div>
  );
}
