"""Nočný supervízor tréningu (1080 Ti) — spúšťa fázy, pri páde obnovuje z last.pt,
pri deadlini ukončí, vyhodnotí a napíše MORNING_REPORT.md.

Spustenie:  backend/.venv/Scripts/python.exe supervise_night.py
"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = (ROOT.parent / "backend" / ".venv" / "Scripts" / "python.exe").resolve()
REPORT = ROOT / "MORNING_REPORT.md"
DEADLINE = datetime(2026, 10, 5, 8, 5)   # po tejto čase nič nové, bežiace ukončiť
PHASES = [
    dict(name="v8s_night", model="yolov8s.pt", imgsz=1280, epochs=100, batch=3, patience=12, batch_min=3),
    dict(name="v8m_night", model="yolov8m.pt", imgsz=1280, epochs=100, batch=3, patience=12, batch_min=2),
]
ENV = dict(os.environ, PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True")


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def power_set(seconds: int) -> None:
    for arg in ("standby-timeout-ac", "hibernate-timeout-ac"):
        subprocess.run(["powercfg", "/change", arg, str(seconds)], capture_output=True)


def wait_with_deadline(proc: subprocess.Popen) -> str:
    """Čaká na proces; vráti 'done'/'deadline'/'crash'."""
    while proc.poll() is None:
        if datetime.now() > DEADLINE:
            proc.kill()
            time.sleep(5)
            return "deadline"
        time.sleep(30)
    return "done" if proc.returncode == 0 else "crash"


def run_phase(ph: dict) -> str:
    batch = ph["batch"]
    for attempt in range(1, 4):
        if datetime.now() > DEADLINE:
            return "deadline"
        log(f"{ph['name']}: štart (batch={batch}, pokus {attempt}/3)")
        proc = subprocess.Popen(
            [str(PY), str(ROOT / "train.py"),
             "--model", ph["model"], "--imgsz", str(ph["imgsz"]),
             "--epochs", str(ph["epochs"]), "--batch", str(batch),
             "--patience", str(ph["patience"]), "--workers", "6",
             "--name", ph["name"]],
            cwd=ROOT, env=ENV)
        status = wait_with_deadline(proc)
        best = ROOT / "runs" / ph["name"] / "weights" / "best.pt"
        last = ROOT / "runs" / ph["name"] / "weights" / "last.pt"
        if status == "deadline":
            return "deadline"
        if status == "done" and best.exists():
            log(f"{ph['name']}: dokončené (early stopping / epôch limit)")
            return "done"
        log(f"{ph['name']}: ukončené status={status} rc={proc.returncode}")
        # pád → obnoviť z checkpointu; bez checkpointu → reštart s menším batchom
        if last.exists():
            log(f"{ph['name']}: resume z last.pt")
            rproc = subprocess.Popen([str(PY), str(ROOT / "train_resume.py"), str(last)],
                                     cwd=ROOT, env=ENV)
            if wait_with_deadline(rproc) == "done" and best.exists():
                log(f"{ph['name']}: resume dokončené")
                return "done"
        batch = max(batch - 1, ph.get("batch_min", 2))
        time.sleep(20)
    log(f"{ph['name']}: VYDAL SA (3 pokusy)")
    return "failed"


def parse_epoch_table(run_dir: Path) -> list[str]:
    csv = run_dir / "results.csv"
    if not csv.exists():
        return ["_(bez výsledkov)_", ""]
    rows = [ln.strip().split(",") for ln in csv.read_text(encoding="utf-8").splitlines() if ln.strip()]
    header = rows[0]
    i_ep = header.index("epoch")
    i_map = header.index("metrics/mAP50(B)")
    i_map95 = header.index("metrics/mAP50-95(B)")
    out = ["| epocha | mAP50 | mAP50-95 | zmena mAP50 |", "|---|---|---|---|"]
    prev = None
    for r in rows[1:]:
        try:
            ep = int(float(r[i_ep]))
            m50 = float(r[i_map]) * 100
            m95 = float(r[i_map95]) * 100
        except (ValueError, IndexError):
            continue
        delta = "—" if prev is None else f"+{m50 - prev:.2f} pp"
        out.append(f"| {ep} | {m50:.1f} % | {m95:.1f} % | {delta} |")
        prev = m50
    out.append("")
    return out


def finalize() -> None:
    lines = [f"# 🌅 Ranný report tréningu — {datetime.now():%d.%m.%Y %H:%M}", ""]
    for ph in PHASES:
        run_dir = ROOT / "runs" / ph["name"]
        lines += [f"## {ph['name']} ({ph['model']}, imgsz {ph['imgsz']})", ""]
        lines += parse_epoch_table(run_dir)
        best = run_dir / "weights" / "best.pt"
        if best.exists():
            log(f"finalna validácia {ph['name']}")
            try:
                v = subprocess.run([str(PY), str(ROOT / "val_best.py"), str(best)],
                                   capture_output=True, text=True, timeout=900, cwd=ROOT)
                tail = [ln for ln in v.stdout.splitlines()
                        if ln.strip() and not ln.startswith(("Ultralytics", "val:", "Speed"))]
                lines += ["**Validácia best.pt (val split):**", "```",
                          "\n".join(tail[-10:]), "```", ""]
            except Exception as e:
                lines += [f"_(validácia zlyhala: {e})_", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    log(f"report uložený: {REPORT}")


def main() -> None:
    log("=== NOČNÝ SUPERVÍZOR ŠTART ===")
    power_set(0)  # zakázať uspanie PC na noc
    log("uspanie PC zakázané (standby/hibernate = 0)")
    info = {}
    try:
        for ph in PHASES:
            if datetime.now() > DEADLINE:
                break
            info[ph["name"]] = run_phase(ph)
    finally:
        try:
            finalize()
        except Exception as e:
            log(f"finalize chyba: {e}")
        power_set(1800)  # vrátiť uspanie na 30 min
        log("uspanie PC vrátené na 30 min; supervízor končí")


if __name__ == "__main__":
    main()
