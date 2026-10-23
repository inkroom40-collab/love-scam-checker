"""ffmpeg/ffprobe-Helfer."""
import shutil
import subprocess
from pathlib import Path


def need(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise SystemExit(f"'{tool}' nicht gefunden – bitte installieren (z. B. apt install ffmpeg).")
    return path


def run(args: list, quiet: bool = True) -> None:
    proc = subprocess.run([need(args[0]), *map(str, args[1:])], capture_output=quiet, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Befehl fehlgeschlagen: {' '.join(map(str, args))}\n{(proc.stderr or '')[-2000:]}")


def duration(path: Path) -> float:
    out = subprocess.run(
        [need("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out or 0)
