"""Lokales Web-Dashboard: Projekte anlegen, Schritte starten, Assets hochladen, Ergebnisse ansehen."""
import io
import json
import mimetypes
import re
import sys
import threading
import time
import traceback
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, unquote, urlparse

from . import llm
from .cli import STEPS, new_project, run_step
from .config import FORMATS, GENRES, LOOKS
from .project import Project
from .render import IMAGE_EXT, VIDEO_EXT

WEB = Path(__file__).parent / "web"
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ASSET_KINDS = {"shots": IMAGE_EXT + VIDEO_EXT, "characters": IMAGE_EXT, "environments": IMAGE_EXT,
               "music": (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg")}
# Wovon hängt welcher Schritt ab? "edit" = Shot im Dashboard bearbeitet, "voices" = Stimme geändert
DEPENDS = {
    "script": [],
    "characters": ["script"],
    "environments": ["script"],
    "shots": ["script", "characters", "environments", "edit"],
    "voice": ["script", "characters", "edit", "voices"],
    "subs": ["voice", "characters"],
    "render": ["script", "edit", "voice", "subs", "assets"],
}
ANSI = re.compile(r"\x1b\[[0-9;]*m")


# ------------------------------------------------------------------ Jobs
class _ThreadStdout(io.TextIOBase):
    """Leitet print() eines Job-Threads in dessen Log um, alles andere geht an die Konsole."""

    def __init__(self, fallback):
        self.fallback = fallback
        self.local = threading.local()

    def write(self, s):
        job = getattr(self.local, "job", None)
        if job is None:
            return self.fallback.write(s)
        job.log(s)
        return len(s)

    def flush(self):
        self.fallback.flush()


STDOUT = _ThreadStdout(sys.stdout)


class Job:
    def __init__(self, project: str, label: str):
        self.id = uuid.uuid4().hex[:10]
        self.project, self.label = project, label
        self.status, self.output = "running", ""
        self.started, self.finished = time.time(), None
        self.current = None

    def log(self, s: str) -> None:
        self.output += ANSI.sub("", s)

    def as_dict(self) -> dict:
        return {"id": self.id, "project": self.project, "label": self.label, "status": self.status,
                "current": self.current, "started": self.started, "finished": self.finished, "log": self.output}


class Jobs:
    def __init__(self):
        self.all: dict[str, Job] = {}
        self.lock = threading.Lock()

    def active(self, project: str) -> Job | None:
        return next((j for j in self.all.values() if j.project == project and j.status == "running"), None)

    def start(self, project: str, label: str, fn) -> Job:
        with self.lock:
            if self.active(project):
                raise RuntimeError("Für dieses Projekt läuft bereits ein Job.")
            job = Job(project, label)
            self.all[job.id] = job

        def target():
            STDOUT.local.job = job
            try:
                fn(job)
                job.status = "done"
            except BaseException as exc:  # SystemExit aus den Schritten ebenfalls abfangen
                job.log(f"\n✖ {exc}\n" if isinstance(exc, SystemExit) else "\n" + traceback.format_exc())
                job.status = "error"
            finally:
                job.finished = time.time()
                job.current = None
                STDOUT.local.job = None

        threading.Thread(target=target, daemon=True).start()
        return job


JOBS = Jobs()


# ------------------------------------------------------------------ Projektstatus
def _status(proj: Project) -> dict:
    d, root = proj.data, proj.root
    stamps = d.get("steps", {})
    done = {
        "script": "script" in d,
        "characters": "characters" in d,
        "environments": "environments" in d,
        "shots": "shot_prompts" in d,
        "voice": "timeline" in d and (root / "audio" / "voiceover.wav").exists(),
        "subs": (root / "subtitles" / "subtitles.srt").exists(),
        "render": any((root / "render").glob("*_4k_*.mp4")),
    }
    # Neueste Asset-Änderung zählt als Abhängigkeit des Renders
    stamps = dict(stamps, assets=max([0] + [p.stat().st_mtime for p in (root / "assets").rglob("*") if p.is_file()]))
    out = {}
    for step in STEPS:
        ts = stamps.get(step)
        deps = DEPENDS[step]
        stale = bool(done[step] and ts and any(stamps.get(dep, 0) > ts or out.get(dep, {}).get("stale") for dep in deps))
        out[step] = {"done": done[step], "at": ts, "stale": stale}
    return out


def _assets(proj: Project) -> dict:
    res = {}
    for kind, exts in ASSET_KINDS.items():
        folder = proj.root / "assets" / kind if kind != "music" else proj.root / "assets"
        items = {}
        if folder.exists():
            for p in sorted(folder.iterdir()):
                if p.is_file() and p.suffix.lower() in exts and (kind != "music" or p.stem == "music"):
                    items[p.stem] = {"path": str(p.relative_to(proj.root)), "mtime": p.stat().st_mtime,
                                     "type": "video" if p.suffix.lower() in VIDEO_EXT else
                                     "audio" if kind == "music" else "image"}
        res[kind] = items
    return res


def _summary(proj: Project) -> dict:
    meta = proj.script.get("meta", {})
    renders = sorted((proj.root / "render").glob("*_4k_*.mp4"))
    return {"slug": proj.root.name, "title": meta.get("title") or proj.root.name,
            "logline": meta.get("logline", ""), "settings": proj.settings, "status": _status(proj),
            "render": str(renders[-1].relative_to(proj.root)) if renders else None,
            "job": (JOBS.active(proj.root.name) or SimpleNamespace(id=None)).id,
            "updated": proj.file.stat().st_mtime if proj.file.exists() else 0}


# ------------------------------------------------------------------ HTTP
class Handler(BaseHTTPRequestHandler):
    base: Path = Path("projects")
    server_version = "MicroDramaStudio/1.0"

    def log_message(self, fmt, *args):  # ruhige Konsole
        if "/api/jobs/" not in (args[0] if args else ""):
            sys.__stderr__.write(f"  {self.address_string()} {fmt % args}\n")

    # Helfer
    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _err(self, msg, status=400):
        self._json({"error": msg}, status)

    def _body(self) -> bytes:
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def _project(self, slug: str) -> Project | None:
        if not SLUG.match(slug):
            return None
        proj = Project(self.base / slug)
        return proj if proj.file.exists() else None

    # Routing
    def do_GET(self):
        url = urlparse(self.path)
        parts = [unquote(p) for p in url.path.strip("/").split("/") if p]
        if not parts:
            return self._file(WEB / "index.html", WEB)
        if parts[0] == "api":
            return self._api_get(parts[1:])
        if parts[0] == "files" and len(parts) >= 3:
            proj = self._project(parts[1])
            if not proj:
                return self._err("Projekt nicht gefunden", 404)
            return self._file(proj.root.joinpath(*parts[2:]), proj.root)
        self._err("Nicht gefunden", 404)

    def _api_get(self, parts):
        if parts == ["meta"]:
            return self._json({"steps": STEPS, "genres": GENRES, "looks": list(LOOKS),
                               "formats": {k: v["label"] for k, v in FORMATS.items()},
                               "tts": ["auto", "elevenlabs", "edge", "espeak", "silent"],
                               "claude": llm.has_credentials(), "base": str(self.base.resolve())})
        if parts == ["projects"]:
            self.base.mkdir(parents=True, exist_ok=True)
            items = [_summary(Project(p)) for p in self.base.iterdir() if (p / "project.json").exists()]
            return self._json(sorted(items, key=lambda x: -x["updated"]))
        if len(parts) == 2 and parts[0] == "projects":
            proj = self._project(parts[1])
            if not proj:
                return self._err("Projekt nicht gefunden", 404)
            srt = proj.root / "subtitles" / "subtitles.srt"
            return self._json(_summary(proj) | {"data": proj.data, "assets": _assets(proj),
                                                "srt": srt.read_text("utf-8") if srt.exists() else None})
        if len(parts) == 2 and parts[0] == "jobs":
            job = JOBS.all.get(parts[1])
            return self._json(job.as_dict()) if job else self._err("Job nicht gefunden", 404)
        if parts == ["jobs"]:
            return self._json([j.as_dict() | {"log": ""} for j in sorted(JOBS.all.values(), key=lambda j: -j.started)])
        self._err("Nicht gefunden", 404)

    def do_POST(self):
        parts = [unquote(p) for p in urlparse(self.path).path.strip("/").split("/") if p]
        try:
            payload = json.loads(self._body() or b"{}")
        except json.JSONDecodeError:
            return self._err("Ungültiges JSON")

        # Neues Projekt (+ optional kompletter Durchlauf)
        if parts == ["api", "projects"]:
            opts = _options(payload)
            args = SimpleNamespace(premise=payload.get("premise") or None, genre=payload.get("genre", "micro-drama"),
                                   lang=payload.get("lang", "de"), aspect=payload.get("aspect", "9:16"),
                                   look=payload.get("look", "cinematic"), seconds=int(payload.get("seconds", 30)),
                                   name=payload.get("name") or None, out=self.base, model=payload.get("model") or None,
                                   demo=bool(payload.get("demo")), preset=payload.get("preset", "medium"), **opts)
            if args.genre not in GENRES or args.aspect not in FORMATS or args.look not in LOOKS:
                return self._err("Ungültige Einstellungen")
            STDOUT.local.job = None
            proj = new_project(args)
            steps = STEPS if payload.get("render", True) else STEPS[:-1]
            if payload.get("run", True):
                job = JOBS.start(proj.root.name, "Komplette Folge", lambda j: _run(proj, steps, args, j))
                return self._json({"slug": proj.root.name, "job": job.id}, 201)
            return self._json({"slug": proj.root.name, "job": None}, 201)

        # Schritt(e) starten
        if len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "run":
            proj = self._project(parts[2])
            step = payload.get("step")
            if not proj or step not in STEPS:
                return self._err("Projekt oder Schritt unbekannt", 404)
            todo = STEPS[STEPS.index(step):] if payload.get("from_here") else [step]
            args = SimpleNamespace(**_options(payload))
            if "preset" in payload:
                proj.settings["preset"] = payload["preset"]
                proj.save()
            label = f"{step} → Ende" if payload.get("from_here") else step
            try:
                job = JOBS.start(proj.root.name, label, lambda j: _run(proj, todo, args, j))
            except RuntimeError as exc:
                return self._err(str(exc), 409)
            return self._json({"job": job.id}, 202)

        # Shot bearbeiten (Aktion, Dauer, Dialog)
        if len(parts) == 5 and parts[:2] == ["api", "projects"] and parts[3] == "shots":
            proj = self._project(parts[2])
            if not proj:
                return self._err("Projekt nicht gefunden", 404)
            if JOBS.active(proj.root.name):
                return self._err("Während ein Job läuft, kann nicht bearbeitet werden.", 409)
            shot = next((s for s in proj.script.get("shots", []) if s["id"] == parts[4]), None)
            if not shot:
                return self._err("Shot nicht gefunden", 404)
            for key in ("action", "shot_type", "camera_move", "lens", "sfx"):
                if isinstance(payload.get(key), str):
                    shot[key] = payload[key]
            if "duration_s" in payload:
                shot["duration_s"] = max(0.5, float(payload["duration_s"]))
            if isinstance(payload.get("lines"), list):
                shot["lines"] = [{"speaker_id": str(l.get("speaker_id", "narrator")), "text": str(l.get("text", "")),
                                  "emotion": str(l.get("emotion", "neutral"))} for l in payload["lines"] if l.get("text")]
            proj.data.setdefault("steps", {})["edit"] = time.time()
            proj.save()
            return self._json({"ok": True})

        # Stimme einer Figur ändern
        if len(parts) == 5 and parts[:2] == ["api", "projects"] and parts[3] == "voices":
            proj = self._project(parts[2])
            if not proj or not isinstance(payload.get("voice"), str):
                return self._err("Ungültig", 400)
            if JOBS.active(proj.root.name):
                return self._err("Während ein Job läuft, kann nicht bearbeitet werden.", 409)
            v = proj.data.setdefault("voices", {}).setdefault(parts[4], {"provider": payload.get("provider", "edge")})
            v["voice"] = payload["voice"]
            if payload.get("provider"):
                v["provider"] = payload["provider"]
            proj.data.setdefault("steps", {})["voices"] = time.time()
            proj.save()
            return self._json({"ok": True})
        self._err("Nicht gefunden", 404)

    def do_PUT(self):
        """Asset-Upload: PUT /api/projects/<slug>/assets/<kind>/<id>?ext=.png (Rohdaten im Body)."""
        url = urlparse(self.path)
        parts = [unquote(p) for p in url.path.strip("/").split("/") if p]
        if len(parts) != 6 or parts[:2] != ["api", "projects"] or parts[3] != "assets":
            return self._err("Nicht gefunden", 404)
        proj, kind, aid = self._project(parts[2]), parts[4], parts[5]
        ext = (parse_qs(url.query).get("ext", [""])[0]).lower()
        if not proj or kind not in ASSET_KINDS or not SLUG.match(aid) or ext not in ASSET_KINDS[kind]:
            return self._err("Ungültiger Upload (Projekt, Typ oder Dateiendung)")
        folder = proj.root / "assets" / (kind if kind != "music" else "")
        folder.mkdir(parents=True, exist_ok=True)
        stem = "music" if kind == "music" else aid
        for old in folder.glob(f"{stem}.*"):  # nur eine Variante pro Shot/Figur
            if old.suffix.lower() in ASSET_KINDS[kind]:
                old.unlink()
        (folder / f"{stem}{ext}").write_bytes(self._body())
        return self._json({"ok": True}, 201)

    def do_DELETE(self):
        parts = [unquote(p) for p in urlparse(self.path).path.strip("/").split("/") if p]
        if len(parts) == 6 and parts[:2] == ["api", "projects"] and parts[3] == "assets":
            proj, kind, aid = self._project(parts[2]), parts[4], parts[5]
            if not proj or kind not in ASSET_KINDS:
                return self._err("Ungültig")
            folder = proj.root / "assets" / (kind if kind != "music" else "")
            for old in folder.glob(f"{'music' if kind == 'music' else aid}.*"):
                old.unlink()
            return self._json({"ok": True})
        self._err("Nicht gefunden", 404)

    # Dateien mit Range-Support (Video-Scrubbing)
    def _file(self, path: Path, root: Path):
        try:
            path = path.resolve()
            path.relative_to(root.resolve())
        except ValueError:
            return self._err("Verboten", 403)
        if not path.is_file():
            return self._err("Datei nicht gefunden", 404)
        size = path.stat().st_size
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix in (".md", ".srt", ".ass", ".txt"):
            ctype = "text/plain; charset=utf-8"
        start, end, status = 0, size - 1, HTTPStatus.OK
        if m := re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", "")):
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else end
            elif m.group(2):
                start = max(0, size - int(m.group(2)))
            end = min(end, size - 1)
            status = HTTPStatus.PARTIAL_CONTENT
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", "no-cache")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with path.open("rb") as fh:
            fh.seek(start)
            left = end - start + 1
            try:
                while left > 0 and (chunk := fh.read(min(1 << 20, left))):
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass


def _options(p: dict) -> dict:
    return {"tts": p.get("tts", "auto"), "music": p.get("music") or None, "letterbox": bool(p.get("letterbox")),
            "no_burn": not p.get("burn", True), "speaker_names": bool(p.get("speaker_names"))}


def _run(proj: Project, steps: list, args, job: Job) -> None:
    for s in steps:
        job.current = s
        run_step(proj, s, args)
    print("\n✔ Fertig.")


def serve(base: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    Handler.base = Path(base).resolve()
    Handler.base.mkdir(parents=True, exist_ok=True)
    sys.stdout = STDOUT
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"🎬 Micro Drama Studio Dashboard → http://{host}:{port}   (Projekte: {Handler.base})", file=sys.__stdout__)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
