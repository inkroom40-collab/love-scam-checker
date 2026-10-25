"""Grok (xAI) als Generator: Referenzbilder → Keyframes → Videoclips pro Shot.

Ablauf pro Folge:
  1. refs       Charakter-Porträts und Set-Bilder (grok-imagine-image)
  2. keyframes  erstes Bild jedes Shots, mit Figuren + Set als Referenz (konsistente Gesichter)
  3. videos     Image-to-Video aus dem Keyframe (grok-imagine-video), Länge = Shot-Länge laut Voiceover

Ergebnisse landen dort, wo der Render sie erwartet (assets/shots/<id>.mp4), danach einfach neu rendern.
"""
import base64
import datetime
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .project import Project
from .render import IMAGE_EXT, VIDEO_EXT

VIDEO_MODEL = os.environ.get("GROK_VIDEO_MODEL", "grok-imagine-video-1.5")
IMAGE_MODEL = os.environ.get("GROK_IMAGE_MODEL", "grok-imagine-image")
STAGES = ["refs", "keyframes", "videos"]
MAX_SECONDS = 15  # Obergrenze der Video-API pro Clip


def available() -> bool:
    try:
        import xai_sdk  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("XAI_API_KEY"))


def _client():
    try:
        from xai_sdk import Client
    except ImportError as exc:
        raise SystemExit("Paket 'xai-sdk' fehlt: pip install -r requirements.txt") from exc
    if not os.environ.get("XAI_API_KEY"):
        raise SystemExit("XAI_API_KEY ist nicht gesetzt – Key unter console.x.ai erstellen.")
    return Client()


def _data_url(path: Path) -> str:
    mime = {".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}.get(path.suffix.lower(), "png")
    return f"data:image/{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _find(folder: Path, stem: str, exts: tuple) -> Path | None:
    return next((folder / f"{stem}{e}" for e in exts if (folder / f"{stem}{e}").exists()), None)


def _download(url: str, target: Path) -> None:
    import requests

    r = requests.get(url, timeout=300)
    r.raise_for_status()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    tmp.write_bytes(r.content)
    tmp.replace(target)


def _save_image(resp, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64decode(resp.base64))


def _log(proj: Project, key: str, entry: dict) -> None:
    proj.data.setdefault("grok", {}).setdefault(key, {}).update(entry | {"at": time.time()})


# ------------------------------------------------------------------ 1. Referenzen
def generate_refs(proj: Project, client, force: bool = False) -> list:
    tasks = []
    for c in proj.require("characters", "characters"):
        target = proj.root / "assets" / "characters" / f"{c['id']}.png"
        if force or not _find(target.parent, c["id"], IMAGE_EXT):
            tasks.append((f"char:{c['id']}", c["prompts"]["reference_portrait"], "3:4", target))
    for e in proj.require("environments", "environments"):
        target = proj.root / "assets" / "environments" / f"{e['id']}.png"
        if force or not _find(target.parent, e["id"], IMAGE_EXT):
            prompt = e["prompts"]["establishing"].split(" --ar ")[0]
            tasks.append((f"env:{e['id']}", prompt, proj.settings["aspect"], target))
    done = []
    for key, prompt, ar, target in tasks:
        print(f"  🖼  {key:<22} {IMAGE_MODEL} {ar}")
        resp = client.image.sample(prompt=prompt, model=IMAGE_MODEL, image_format="base64",
                                   aspect_ratio=ar, resolution="2k")
        _save_image(resp, target)
        _log(proj, key, {"model": IMAGE_MODEL, "file": str(target.relative_to(proj.root))})
        done.append(key)
    if not tasks:
        print("  Alle Referenzbilder vorhanden (mit --force neu erzeugen).")
    return done


# ------------------------------------------------------------------ 2. Keyframes
def _references(proj: Project, shot: dict) -> list[Path]:
    refs = []
    for cid in shot["character_ids"]:
        if p := _find(proj.root / "assets" / "characters", cid, IMAGE_EXT):
            refs.append(p)
    if p := _find(proj.root / "assets" / "environments", shot["location_id"], IMAGE_EXT):
        refs.append(p)
    return refs


def _keyframe_one(proj: Project, client, shot: dict, prompt: str) -> str:
    refs = _references(proj, shot)
    kwargs = dict(prompt=prompt, model=IMAGE_MODEL, image_format="base64",
                  aspect_ratio=proj.settings["aspect"], resolution="2k")
    if refs:  # Multi-Referenz-Edit: hält Gesichter, Kostüme und Set konsistent
        kwargs["image_urls"] = [_data_url(p) for p in refs]
    resp = client.image.sample(**kwargs)
    target = proj.root / "assets" / "keyframes" / f"{shot['id']}.png"
    _save_image(resp, target)
    _log(proj, f"keyframe:{shot['id']}", {"model": IMAGE_MODEL, "refs": [p.name for p in refs],
                                           "file": str(target.relative_to(proj.root))})
    return f"{len(refs)} Referenzen"


# ------------------------------------------------------------------ 3. Videos
def _video_one(proj: Project, client, shot: dict, prompts: dict, opts: dict) -> str:
    plan = {s["id"]: s for s in proj.data.get("timeline", {}).get("shots", [])}
    seconds = plan.get(shot["id"], {}).get("duration", shot["duration_s"])
    duration = max(1, min(MAX_SECONDS, math.ceil(seconds)))
    kwargs = dict(prompt=prompts["video_prompt"], model=opts["model"], duration=duration,
                  aspect_ratio=proj.settings["aspect"], resolution=opts["resolution"],
                  generate_audio=opts["audio"], timeout=datetime.timedelta(minutes=15))
    keyframe = _find(proj.root / "assets" / "keyframes", shot["id"], IMAGE_EXT)
    if keyframe:
        mode = "image-to-video"
        kwargs["image_url"] = _data_url(keyframe)
        if opts["model"].endswith("1.5") and (refs := _references(proj, shot)):
            kwargs["reference_image_urls"] = [_data_url(p) for p in refs]  # erstes Bild bleibt gepinnt
    elif refs := _references(proj, shot):
        mode = "reference-to-video"
        kwargs["reference_image_urls"] = [_data_url(p) for p in refs]
    else:
        mode = "text-to-video"
        kwargs["prompt"] = prompts["image_prompt"].split(" --ar ")[0] + " " + prompts["video_prompt"]
    resp = client.video.generate(**kwargs)
    target = proj.root / "assets" / "shots" / f"{shot['id']}.mp4"
    _download(resp.url, target)  # ersetzt einen alten Clip erst nach erfolgreichem Download
    for old in target.parent.glob(f"{shot['id']}.*"):  # Standbild/anderes Format ersetzen
        if old != target and old.suffix.lower() in IMAGE_EXT + VIDEO_EXT:
            old.unlink()
    cost = resp.cost_usd
    _log(proj, f"video:{shot['id']}", {"model": resp.model or opts["model"], "mode": mode, "duration": duration,
                                        "resolution": opts["resolution"], "cost_usd": cost,
                                        "file": str(target.relative_to(proj.root))})
    return f"{mode}, {duration}s, {opts['resolution']}" + (f", ${cost:.2f}" if cost else "")


def _parallel(proj: Project, label: str, shots: list, fn, workers: int) -> list:
    ok, failed = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fn, sh): sh["id"] for sh in shots}
        for fut in as_completed(futures):
            sid = futures[fut]
            try:
                print(f"  ✔ {label} {sid}: {fut.result()}")
                ok.append(sid)
            except Exception as exc:  # z. B. Moderation, Timeout – die anderen Shots laufen weiter
                print(f"  ✖ {label} {sid}: {type(exc).__name__}: {str(exc)[:200]}")
                failed.append(sid)
    proj.save()
    if failed:
        print(f"  ⚠ {len(failed)} fehlgeschlagen: {', '.join(sorted(failed))} – mit --shots erneut versuchen.")
    return ok


def run(proj: Project, stages: list | None = None, shot_ids: list | None = None, force: bool = False,
        resolution: str = "720p", model: str | None = None, audio: bool = False, workers: int = 3) -> None:
    script = proj.require("script", "script")
    prompts = {p["id"]: p for p in proj.require("shot_prompts", "shots")}
    shots = [s for s in script["shots"] if not shot_ids or s["id"] in shot_ids]
    stages = stages or STAGES
    client = _client()
    opts = {"resolution": resolution, "model": model or VIDEO_MODEL, "audio": audio}

    if "refs" in stages:
        print("\n▶ Grok 1/3 Referenzbilder (Figuren & Sets)")
        generate_refs(proj, client, force)
        proj.save()
    if "keyframes" in stages:
        print("\n▶ Grok 2/3 Keyframes pro Shot")
        todo = [s for s in shots if force or shot_ids or not _find(proj.root / "assets" / "keyframes", s["id"], IMAGE_EXT)]
        if todo:
            _parallel(proj, "Keyframe", todo, lambda sh: _keyframe_one(proj, client, sh, prompts[sh["id"]]["image_prompt"].split(" --ar ")[0]), workers)
        else:
            print("  Alle Keyframes vorhanden.")
    if "videos" in stages:
        print(f"\n▶ Grok 3/3 Videoclips ({opts['model']}, {resolution}{', mit Ton' if audio else ''})")
        todo = [s for s in shots if force or shot_ids or not _find(proj.root / "assets" / "shots", s["id"], VIDEO_EXT)]
        if todo:
            _parallel(proj, "Video", todo, lambda sh: _video_one(proj, client, sh, prompts[sh["id"]], opts), workers)
        else:
            print("  Alle Shots haben bereits ein Video.")
        costs = [v.get("cost_usd") or 0 for k, v in proj.data.get("grok", {}).items() if k.startswith("video:")]
        if any(costs):
            print(f"  Bisherige Video-Kosten laut API: ${sum(costs):.2f}")
    print("\n  → Jetzt neu rendern: python -m studio render <projekt>")
