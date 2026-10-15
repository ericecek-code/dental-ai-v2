type Severity = 'urgent' | 'treat_soon' | 'watch' | 'restoration';

interface Finding {
  tooth: number;
  severity: Severity;
  confidence: number;
}

interface OdontogramProps {
  findings: Finding[];
  activeTooth: number | null;
  onSelectTooth: (t: number | null) => void;
}

const UPPER_TEETH = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
const LOWER_TEETH = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];

const SEVERITY_ORDER: Record<Severity, number> = {
  urgent: 4,
  treat_soon: 3,
  watch: 2,
  restoration: 1,
};

const SEVERITY_COLORS: Record<Severity, string> = {
  urgent: '#ef4444',
  treat_soon: '#f59e0b',
  watch: '#38bdf8',
  restoration: '#a78bfa',
};

const LEGEND_ITEMS: { label: string; color: string }[] = [
  { label: 'Kaz (akútne)', color: SEVERITY_COLORS.urgent },
  { label: 'Riešiť čoskoro', color: SEVERITY_COLORS.treat_soon },
  { label: 'Sledovať', color: SEVERITY_COLORS.watch },
  { label: 'Plomba / korunka', color: SEVERITY_COLORS.restoration },
  { label: 'V poriadku', color: '#1e293b' },
];

function getWorstSeverity(findings: Finding[], tooth: number): Severity | null {
  const toothFindings = findings.filter((f) => f.tooth === tooth);
  if (toothFindings.length === 0) return null;
  return toothFindings.reduce((worst, f) =>
    SEVERITY_ORDER[f.severity] > SEVERITY_ORDER[worst] ? f.severity : worst
  , toothFindings[0].severity);
}

function Tooth({
  tooth,
  fillColor,
  isActive,
  onClick,
}: {
  tooth: number;
  fillColor: string;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col items-center gap-1 focus:outline-none"
      aria-label={`Tooth ${tooth}`}
    >
      <div
        className="w-[34px] h-[34px] rounded-md border border-slate-600 flex items-center justify-center transition-shadow"
        style={{
          backgroundColor: fillColor,
          boxShadow: isActive ? '0 0 0 2px #ffffff' : undefined,
        }}
      />
      <span className="text-[10px] text-slate-400 leading-none">{tooth}</span>
    </button>
  );
}

export default function Odontogram({ findings, activeTooth, onSelectTooth }: OdontogramProps) {
  const renderRow = (teeth: number[]) => (
    <div className="flex gap-1.5 justify-center">
      {teeth.map((tooth) => {
        const severity = getWorstSeverity(findings, tooth);
        const fillColor = severity ? SEVERITY_COLORS[severity] : '#1e293b';
        const isActive = activeTooth === tooth;
        return (
          <Tooth
            key={tooth}
            tooth={tooth}
            fillColor={fillColor}
            isActive={isActive}
            onClick={() => onSelectTooth(isActive ? null : tooth)}
          />
        );
      })}
    </div>
  );

  return (
    <div className="flex flex-col gap-3">
      <div className="text-center">
        <h3 className="text-sm font-semibold text-slate-200 tracking-wide">
          ODONTOGRAM — mapa zubov
        </h3>
      </div>

      <div className="flex flex-col gap-2">
        {renderRow(UPPER_TEETH)}
        {renderRow(LOWER_TEETH)}
      </div>

      <div className="flex gap-4 justify-center flex-wrap">
        {LEGEND_ITEMS.map((item) => (
          <div key={item.label} className="flex items-center gap-1.5">
            <div
              className="w-3 h-3 rounded-sm"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-xs text-slate-400">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
