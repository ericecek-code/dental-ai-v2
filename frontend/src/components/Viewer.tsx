import { useCallback, useEffect, useRef, useState } from "react";
import type { Finding } from "../lib/api";

export interface GeminiBox {
  label: string;
  tooth?: string;
  confidence?: number;
  bbox: [number, number, number, number];
}

interface Props {
  imageUrl: string;
  findings: Finding[];
  activeIdx: number | null;
  onSelect: (i: number | null) => void;
  heatmapUrl?: string | null; // Grad-CAM blendovaný priamo na snímku
  geminiFindings?: GeminiBox[]; // orientačné rámčeky z Gemini (odvodené z čísla zuba)
}

const BOX_COLORS: Record<string, string> = {
  urgent: "#ef4444",
  treat_soon: "#f59e0b",
  watch: "#38bdf8",
  restoration: "#a78bfa",
};

const MIN_ZOOM = 0.5; // pod fit-to-width — dovoľme aj oddialiť, ako v lekárskych prehliadačoch
const MAX_ZOOM = 8;
export function Viewer({
  imageUrl,
  findings,
  activeIdx,
  onSelect,
  heatmapUrl,
  geminiFindings = [],
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const heatRef = useRef<HTMLImageElement | null>(null);
  const [showBoxes, setShowBoxes] = useState(true);
  const [zoom, setZoom] = useState(1); // 1 = fit-to-width
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [imgError, setImgError] = useState(false); // snímku nebolo možné načítať (napr. vypršané prihlásenie)

  // čerstvé hodnoty pre natívny (nepasívny) wheel listener a pan logiku
  const view = useRef({ zoom: 1, offset: { x: 0, y: 0 }, fitScale: 1 });
  const drag = useRef({ active: false, startX: 0, startY: 0, offsetX: 0, offsetY: 0, moved: false });

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img || !img.complete) return;
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(img, 0, 0);
    // heatmapa blendovaná priamo na snímku (Overjet/ Pearl štýl)
    const heat = heatRef.current;
    if (heat && heat.complete && heat.naturalWidth > 0) {
      ctx.save();
      ctx.globalAlpha = 0.45;
      ctx.drawImage(heat, 0, 0, canvas.width, canvas.height);
      ctx.restore();
    }
    if (!showBoxes) return;
    // Overlay sa kreslí v pixloch originálu, ale obraz je zmenšený transformom
    // (fit). Bez tohto faktoru by boli rámčeky a labely na veľkom panorame
    // hrubé a nečitateľné. k = koľko canvasových px pripadá na 1 css px.
    const k = 1 / Math.max(0.05, view.current.fitScale);
    findings.forEach((f, i) => {
      const [x1, y1, x2, y2] = f.bbox;
      const isActive = activeIdx === i;
      const color = BOX_COLORS[f.severity] ?? "#94a3b8";
      const r = 10 * k; // zaoblenie — Overjet štýl
      const rr = (x: number, y: number, w: number, h: number, rad: number) => {
        ctx.beginPath();
        const rrFn = (ctx as CanvasRenderingContext2D & { roundRect?: (x: number, y: number, w: number, h: number, r: number) => void }).roundRect;
        if (rrFn) rrFn.call(ctx, x, y, w, h, rad);
        else ctx.rect(x, y, w, h);
      };
      // 1) polopriehľadné farebné plnenie + žiara
      ctx.save();
      ctx.shadowColor = color;
      ctx.shadowBlur = (isActive ? 20 : 9) * k;
      ctx.globalAlpha = isActive ? 0.42 : 0.26;
      ctx.fillStyle = color;
      rr(x1, y1, x2 - x1, y2 - y1, r);
      ctx.fill();
      ctx.restore();
      // 2) zaoblený rámček
      ctx.strokeStyle = color;
      ctx.lineWidth = Math.max(2, isActive ? 5 : 3) * k;
      rr(x1, y1, x2 - x1, y2 - y1, r);
      ctx.stroke();
      // 3) pill labele (zaoblená tabuľka) — názov + istota + zub
      const label = `${f.label_sk} ${(f.confidence * 100).toFixed(0)}%${f.tooth ? ` · zub ${f.tooth}` : ""}`;
      const fs = 14 * k;
      ctx.font = `bold ${fs}px system-ui`;
      const pad = 9 * k;
      const tw = ctx.measureText(label).width + pad * 2;
      const th = 22 * k;
      const px = Math.max(2 * k, Math.min(x1, canvas.width - tw - 2 * k));
      const py = y1 - th - 4 * k < 2 * k ? y1 + 4 * k : y1 - th - 4 * k;
      ctx.save();
      ctx.globalAlpha = 0.92;
      ctx.fillStyle = color;
      rr(px, py, tw, th, th / 2);
      ctx.fill();
      ctx.restore();
      ctx.fillStyle = "#0f172a";
      ctx.fillText(label, px + pad, py + th - fs * 0.32);
    });
    // Gemini nálezy — orientačné rámčeky odvodené z čísla zuba (prerušovaná čiara)
    const ctxAny = ctx as CanvasRenderingContext2D & {
      roundRect?: (x: number, y: number, w: number, h: number, r: number) => void;
    };
    const dashedRect = (x: number, y: number, w: number, h: number, rad: number) => {
      ctx.beginPath();
      if (ctxAny.roundRect) ctxAny.roundRect(x, y, w, h, rad);
      else ctx.rect(x, y, w, h);
    };
    const placedLabels: [number, number, number, number][] = [];
    const gfs = 12 * k;
    const gth = 20 * k;
    const gap = 4 * k;
    const padG = 8 * k;
    geminiFindings.forEach((g) => {
      const [x1, y1, x2, y2] = g.bbox;
      const color = "#38bdf8";
      ctx.save();
      ctx.setLineDash([12 * k, 8 * k]);
      ctx.strokeStyle = color;
      ctx.lineWidth = 3 * k;
      ctx.globalAlpha = 0.95;
      dashedRect(x1, y1, x2 - x1, y2 - y1, 10 * k);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 0.12;
      ctx.fillStyle = color;
      dashedRect(x1, y1, x2 - x1, y2 - y1, 10 * k);
      ctx.fill();
      ctx.restore();
      const gLabel = `Gemini: ${g.label}${g.tooth ? ` · zub ${g.tooth}` : ""}`;
      ctx.font = `bold ${gfs}px system-ui`;
      const gtw = ctx.measureText(gLabel).width + padG * 2;
      // štítok držíme v plátne (aby sa neorezal o pravý okraj)
      const gx = Math.max(2 * k, Math.min(x1, canvas.width - gtw - 2 * k));
      let gy = Math.max(2 * k, Math.min(canvas.height - gth - gap, y2 + gap));
      const overlapsLabel = (yy: number) =>
        placedLabels.some((r) => !(gx + gtw < r[0] || gx > r[2] || yy + gth < r[1] || yy > r[3]));
      let tries = 0;
      while (overlapsLabel(gy) && tries < 8) {
        gy += gth + 4 * k;
        tries += 1;
      }
      if (gy + gth > canvas.height) gy = Math.max(2 * k, y1 - gth - gap);
      // radšej samotný rámček než štítok, ktorý by sa prekrýval s iným
      if (overlapsLabel(gy)) return;
      placedLabels.push([gx, gy, gx + gtw, gy + gth]);
      ctx.save();
      ctx.globalAlpha = 0.92;
      ctx.fillStyle = color;
      dashedRect(gx, gy, gtw, gth, gth / 2);
      ctx.fill();
      ctx.restore();
      ctx.fillStyle = "#0b1220";
      ctx.fillText(gLabel, gx + padG, gy + gth - gfs * 0.32);
    });
  }, [findings, showBoxes, activeIdx, geminiFindings]);

  // načítanie heatmapy (pri blend režime) — prekresli po načítaní
  useEffect(() => {
    if (!heatmapUrl) {
      heatRef.current = null;
      drawRef.current?.();
      return;
    }
    // rýchle prepnutie prepínača by nechalo v heatRef starú (už neplatnú) heatmapu
    let cancelled = false;
    const h = new Image();
    h.crossOrigin = "anonymous";
    h.onload = () => {
      if (cancelled) return;
      heatRef.current = h;
      drawRef.current?.();
    };
    h.src = heatmapUrl;
    return () => {
      cancelled = true;
      h.onload = null;
      if (heatRef.current === h) heatRef.current = null;
      h.src = "";
    };
  }, [heatmapUrl]);

  // načítanie snímky + fit — reset pohľadu IBA pri novej snímke (nie pri hoveri/kartách)
  const drawRef = useRef(draw);
  drawRef.current = draw;
  useEffect(() => {
    setImgError(false);
    const canvas = canvasRef.current;
    if (!canvas) return;
    // StrictMode / rýchla zmena URL: rozpracované načítanie sa musí zrušiť, inak
    // sa bitmap prekreslí dvakrát a obraz blikne
    let cancelled = false;
    const img = new Image();
    img.onerror = () => { if (!cancelled) setImgError(true); };
    // Vypočíta fit, nastaví transform a prekreslí bitmapu — VŠETKO v jednom
    // task-e. canvas.width/height totiž podľa štandardu bitmapu vymaže, takže
    // čokoľvek odložené (rAF, setState → React commit) znamená aspoň jeden
    // vykreslený frame s prázdnym canvasom v starej scále → bliknutie obrazu.
    const fitAndPaint = (): boolean => {
      const el = containerRef.current;
      const cw = el?.clientWidth ?? 0;
      const ch = el?.clientHeight ?? 0;
      if (cw <= 100 || ch <= 100) return false; // layout ešite nie je platný
      // „fit to screen“: snímka sa zmestí CELÁ — obmedzuje šírka AJ výška kontajnera
      const fit = Math.min(1, cw / img.naturalWidth, ch / img.naturalHeight);
      view.current.fitScale = fit;
      view.current.zoom = 1;
      const cl = clampOffset(0, 0, 1);
      view.current.offset = cl;
      // 1) transform — pred vykreslením, inak by bol prvý frame zlý
      canvas.style.transform = `translate(${cl.x}px, ${cl.y}px) scale(${fit})`;
      // 2) bitmap hneď — žiadny medzikrok, v ktorom by canvas bol prázdny
      drawRef.current();
      // 3) React state až potom — hodnoty sú rovnaké, takže bez vizuálnej zmeny
      setZoom(1);
      setOffset(cl);
      return true;
    };
    img.onload = () => {
      if (cancelled) return;
      imgRef.current = img;
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      // bežne stihneme synchronne (clientWidth vynúti layout); ak kontajner ešte
      // nemá rozumné rozmery, skúsime to v nasledujúcom frame
      if (!fitAndPaint()) requestAnimationFrame(() => { if (!cancelled) fitAndPaint(); });
    };
    img.src = imageUrl;
    return () => {
      cancelled = true;
      img.onload = null;
      img.onerror = null;
      img.src = ""; // zruší načítanie nepoužitej snímky
    };
  }, [imageUrl]);

  // prekreslenie boxov bez resetu pohľadu
  useEffect(() => {
    draw();
  }, [draw]);

  // natívny wheel listener (React onWheel je pasívny → preventDefault nefunguje)
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const v = view.current;
      const rect = el.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;
      const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
      const newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, v.zoom * factor));
      const ratio = newZoom / v.zoom;
      const nx = cx - (cx - v.offset.x) * ratio;
      const ny = cy - (cy - v.offset.y) * ratio;
      // offset MUSÍ prejsť cez clamp — inak snímka „ubieha" zo stredu/okna
      // (a po oddialení sa nevráti do stredu) — rovnaké pravidlo ako pri ťahaní
      const clamped = clampOffset(nx, ny, newZoom);
      v.zoom = newZoom;
      v.offset = clamped;
      setZoom(newZoom);
      setOffset(clamped);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  // rýchle skrytie/zobrazenie rámčekov — pravý Ctrl (alebo pravé tlačidlo myši)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code === "ControlRight" && !e.repeat) {
        e.preventDefault();
        setShowBoxes((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // prepočet fitu pri zmene šírky okna (ak používateľ ešte neskroloval zoomom)
  useEffect(() => {
    const onResize = () => {
      const canvas = canvasRef.current;
      const img = imgRef.current;
      const el = containerRef.current;
      if (!canvas || !img || !el || view.current.zoom !== 1) return;
      const cw = el.clientWidth;
      const ch = el.clientHeight;
      if (cw > 100) {
        const fitW = cw / img.naturalWidth;
        const fitH = ch > 100 ? ch / img.naturalHeight : fitW;
        view.current.fitScale = Math.min(1, fitW, fitH);
        const cl = clampOffset(view.current.offset.x, view.current.offset.y, view.current.zoom);
        view.current.offset = cl;
        setOffset(cl);
        drawRef.current();
      }
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const clampOffset = (x: number, y: number, z: number) => {
    const canvas = canvasRef.current;
    const el = containerRef.current;
    if (!canvas || !el) return { x, y };
    const s = view.current.fitScale * z;
    const w = canvas.width * s;
    const h = canvas.height * s;
    const cw = el.clientWidth;
    const ch = el.clientHeight;
    // menšia snímka než okno → vycentruj (posúvať sa nedá); väčšia → drž v medziach
    const axis = (pos: number, content: number, box: number) =>
      content <= box ? (box - content) / 2 : Math.min(0, Math.max(box - content, pos));
    return { x: axis(x, w, cw), y: axis(y, h, ch) };
  };

  const onMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    drag.current = {
      active: true, moved: false,
      startX: e.clientX, startY: e.clientY,
      offsetX: view.current.offset.x, offsetY: view.current.offset.y,
    };
    setIsDragging(true);
  };

  const onMouseMove = (e: React.MouseEvent) => {
    if (!drag.current.active) return;
    const dx = e.clientX - drag.current.startX;
    const dy = e.clientY - drag.current.startY;
    if (Math.abs(dx) + Math.abs(dy) > 4) drag.current.moved = true;
    if (drag.current.moved) {
      const clamped = clampOffset(
        drag.current.offsetX + dx, drag.current.offsetY + dy, view.current.zoom
      );
      view.current.offset = clamped;
      setOffset(clamped);
    }
  };

  const endDrag = () => {
    drag.current.active = false;
    setIsDragging(false);
  };

  const onCanvasClick = (e: React.MouseEvent) => {
    if (drag.current.moved) { drag.current.moved = false; return; } // pan gesto — neselectuje
    // hit-test: klik na box = vyber nález (klik mimo = zruš)
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const scale = rect.width / canvas.width || 1;
    const ix = (e.clientX - rect.left) / scale;
    const iy = (e.clientY - rect.top) / scale;
    for (let i = findings.length - 1; i >= 0; i--) {
      const [x1, y1, x2, y2] = findings[i].bbox;
      if (ix >= x1 && ix <= x2 && iy >= y1 && iy <= y2) {
        onSelect(i);
        return;
      }
    }
    onSelect(null);
  };

  const zoomBy = (factor: number) => {
    const el = containerRef.current;
    const v = view.current;
    const cx = (el?.clientWidth ?? 0) / 2;
    const cy = (el?.clientHeight ?? 0) / 2;
    const newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, v.zoom * factor));
    const ratio = newZoom / v.zoom;
    const nx = cx - (cx - v.offset.x) * ratio;
    const ny = cy - (cy - v.offset.y) * ratio;
    const clamped = clampOffset(nx, ny, newZoom);
    v.zoom = newZoom;
    v.offset = clamped;
    setZoom(newZoom);
    setOffset(clamped);
  };

  const reset = () => {
    view.current.zoom = 1;
    const cl = clampOffset(0, 0, 1);
    view.current.offset = cl;
    setZoom(1);
    setOffset(cl);
  };

  const scale = view.current.fitScale * zoom;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <h2 className="font-medium text-slate-300 uppercase tracking-wide text-xs">
          RTG s AI overlayom
        </h2>
        <span className="text-xs text-slate-500 hidden md:inline">
          🖐 ťahaj = posun · koliesko = zoom · dvojklik = reset · pravý Ctrl / pravé tlačidlo = rámčeky
        </span>
        <label className="ml-auto flex items-center gap-1.5 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={showBoxes}
            onChange={(e) => setShowBoxes(e.target.checked)}
            className="accent-teal-400"
          />
          prekrytie (pravý Ctrl)
        </label>
        <div className="flex items-center gap-1">
          <button
            onClick={() => zoomBy(1 / 1.25)}
            className="px-2 py-1 bg-slate-700 hover:bg-slate-600 rounded text-slate-200 text-xs"
          >
            −
          </button>
          <span className="text-xs text-slate-400 w-10 text-center">{zoom.toFixed(1)}×</span>
          <button
            onClick={() => zoomBy(1.25)}
            className="px-2 py-1 bg-slate-700 hover:bg-slate-600 rounded text-slate-200 text-xs"
          >
            +
          </button>
          <button
            onClick={reset}
            className="px-2 py-1 bg-slate-700 hover:bg-slate-600 rounded text-slate-200 text-xs ml-1"
          >
            reset
          </button>
        </div>
      </div>
      <div
        ref={containerRef}
        className="rounded-xl overflow-hidden ring-1 ring-slate-800 bg-black relative select-none"
        style={{
          cursor: isDragging ? "grabbing" : "grab",
          height: "clamp(320px, calc(100vh - 240px), 78vh)",
        }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={endDrag}
        onMouseLeave={endDrag}
        onDoubleClick={reset}
        onContextMenu={(e) => {
          // pravé tlačidlo = skryť/zobraziť rámčeky (namiesto kontextovej ponuky)
          e.preventDefault();
          setShowBoxes((v) => !v);
        }}
      >
        <canvas
          ref={canvasRef}
          onClick={onCanvasClick}
          className="block"
          style={{
            transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
            transformOrigin: "0 0",
          }}
        />
      </div>
      {imgError && (
        <p className="text-xs text-amber-300 bg-amber-500/10 ring-1 ring-amber-500/30 rounded-lg px-3 py-2">
          Snímku sa nepodarilo načítať (vypršalo prihlásenie alebo súbor chýba?).
          Obnovte stránku a skúste to znova.
        </p>
      )}
    </div>
  );
}
