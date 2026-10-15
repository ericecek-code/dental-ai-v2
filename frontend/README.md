# Frontend — Deň 1

Scaffold vytvoríš príkazom (Vite + React + TypeScript, potom doinštalovať Tailwind):

```bash
npm create vite@latest . -- --template react-ts
npm install
npm install -D tailwindcss postcss autoprefixer
npm run dev -- --host 127.0.0.1 --port 5173
```

Plán obrazoviek (wow poradie):
1. **UploadZone** — drag & drop RTG + slider citlivosti (0.05–0.95).
2. **Viewer s overlayom** — farebné bounding boxy (červená kaz, fialová lézia, oranžová retinovaný), zoom/pan, prepínač Grad-CAM heatmapy.
3. **Karty nálezov** — slovenské názvy, confidence, závažnosť, tlačidlá *Súhlasím / Opraviť* (zapisuje status → budovanie datasetu).
4. **Odontogram-lite** — SVG FDI 11–48, farebne označené zuby.
5. **PDF report** — „Čo vidíme na Vašej RTG", 1 strana, po slovensky.

Vite dev server proxy na backend: `server.proxy['/api'] → http://127.0.0.1:8000`.
