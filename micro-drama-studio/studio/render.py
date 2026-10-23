"""Schritt 7: 4K-Schnitt – Shots (Video, Standbild mit Ken-Burns oder Storyboard-Karte) + Grade + Audio + Untertitel."""
from pathlib import Path

from .config import FORMATS, FPS
from .media import run
from .project import Project

VIDEO_EXT = (".mp4", ".mov", ".webm", ".mkv")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
PLACEHOLDER_COLORS = ["0x1b2631", "0x2c1f2b", "0x1f2b24", "0x2b261f", "0x1f2330", "0x30201f"]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _find(folder: Path, sid: str, exts: tuple) -> Path | None:
    return next((folder / f"{sid}{e}" for e in exts if (folder / f"{sid}{e}").exists()), None)


def _grade(w: int, h: int, letterbox: bool) -> str:
    """Film-Look: leichter S-Kontrast, Vignette, feines Korn, optional 2.39:1-Balken (nur Querformat)."""
    f = "eq=contrast=1.06:saturation=1.05,vignette=PI/5,noise=alls=4:allf=t"
    if letterbox and w > h:
        bar = int((h - w / 2.39) / 2)
        f += f",drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill,drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill"
    return f


def _shot_clip(proj: Project, shot: dict, plan: dict, idx: int, w: int, h: int, grade: str, out: Path) -> str:
    dur = plan["duration"]
    shots_dir = proj.root / "assets" / "shots"
    cover = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
    enc = ["-c:v", "libx264", "-preset", proj.settings.get("preset", "medium"), "-crf", "18",
           "-pix_fmt", "yuv420p", "-r", str(FPS), "-an"]

    if vid := _find(shots_dir, shot["id"], VIDEO_EXT):
        # Generiertes Video: auf Länge bringen (bei Bedarf letztes Bild halten)
        run(["ffmpeg", "-y", "-i", vid, "-t", f"{dur:.3f}", "-vf",
             f"{cover},fps={FPS},tpad=stop_mode=clone:stop_duration={dur:.3f},{grade}", *enc, "-t", f"{dur:.3f}", out])
        return f"Video  {vid.name}"

    frames = max(1, round(dur * FPS))
    move = shot.get("camera_move", "").lower()
    if any(k in move for k in ("out", "pull")):
        z = f"zoom='max(1.0,1.18-0.18*on/{frames})'"
    elif "static" in move:
        z = "zoom='1.02'"
    else:  # push-in / dolly in / default
        z = f"zoom='min(1.18,1.0+0.18*on/{frames})'"
    zoompan = f"zoompan={z}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={FPS}"

    if img := _find(shots_dir, shot["id"], IMAGE_EXT):
        # Standbild → Ken-Burns-Bewegung passend zur Kamerabewegung im Skript
        run(["ffmpeg", "-y", "-loop", "1", "-i", img, "-vf",
             f"scale={int(w * 1.25)}:{int(h * 1.25)}:force_original_aspect_ratio=increase,"
             f"crop={int(w * 1.25)}:{int(h * 1.25)},{zoompan},{grade}", "-frames:v", frames, *enc, out])
        return f"Bild   {img.name}"

    # Kein Asset vorhanden → Animatic-Karte mit Shot-Infos (Storyboard-Vorschau in echter 4K-Auflösung)
    txt = proj.path("render", "cards", f"{shot['id']}.txt")
    env = proj.environment(shot["location_id"])
    body = _wrap(shot["action"], 34 if h > w else 60)
    txt.write_text(f"{shot['id'].upper()}  ·  {shot['shot_type']}\n{shot['camera_move']}  ·  {shot['lens']}\n"
                   f"{env['name'] if env else shot['location_id']}\n\n{body}", "utf-8")
    fs = int(min(w, h) * 0.038)
    col = PLACEHOLDER_COLORS[idx % len(PLACEHOLDER_COLORS)]
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={col}:s={int(w * 1.2)}x{int(h * 1.2)}:r={FPS}:d={dur:.3f}",
         "-vf", f"drawtext=fontfile={FONT}:textfile={txt}:fontcolor=white@0.9:fontsize={fs}:line_spacing={fs // 2}:"
                f"x=(w-text_w)/2:y=(h-text_h)/2-h*0.08,{zoompan},{grade}",
         "-frames:v", frames, *enc, out])
    return "Karte  (kein Asset – Storyboard-Platzhalter)"


def _wrap(text: str, width: int) -> str:
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + len(word) + 1 > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return "\n".join(lines + [cur])


def render(proj: Project, burn_subs: bool = True, letterbox: bool = False, music: str | None = None) -> Path:
    script = proj.require("script", "script")
    tl = proj.require("timeline", "voiceover")
    fmt = FORMATS[proj.settings["aspect"]]
    w, h = fmt["width"], fmt["height"]
    grade = _grade(w, h, letterbox)
    clips_dir = proj.root / "render" / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    plans = {p["id"]: p for p in tl["shots"]}
    concat = []
    for i, sh in enumerate(script["shots"]):
        clip = clips_dir / f"{sh['id']}.mp4"
        src = _shot_clip(proj, sh, plans[sh["id"]], i, w, h, grade, clip)
        print(f"  🎬 {sh['id']}  {plans[sh['id']]['duration']:5.2f}s  {src}")
        concat.append(f"file '{clip.resolve()}'")
    lst = proj.path("render", "concat.txt")
    lst.write_text("\n".join(concat), "utf-8")

    picture = proj.path("render", "picture.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", picture])

    # Audio: Voiceover + optional Musik (automatisch unter die Stimme geduckt)
    vo = proj.root / "audio" / "voiceover.wav"
    music = music or next((str(p) for p in (proj.root / "assets").glob("music.*")), None)
    args = ["ffmpeg", "-y", "-i", picture, "-i", vo]
    vf = []
    if burn_subs and (proj.root / "subtitles" / "subtitles.ass").exists():
        vf = ["-vf", "ass=subtitles/subtitles.ass"]
    if music:
        args += ["-stream_loop", "-1", "-i", music]
        afilter = ("[2:a]volume=0.35,aformat=channel_layouts=stereo[m];[1:a]asplit=2[v][sc];"
                   "[m][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[md];"
                   "[v][md]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5[a]")
        amap = ["-filter_complex", afilter, "-map", "0:v", "-map", "[a]"]
    else:
        amap = ["-map", "0:v", "-map", "1:a"]
    title = script["meta"]["title"]
    final = proj.path("render", f"{proj.root.name}_4k_{proj.settings['aspect'].replace(':', 'x')}.mp4")
    _run_in(proj.root, args + amap + vf + [
        "-c:v", "libx264", "-preset", proj.settings.get("preset", "medium"), "-crf", "17", "-maxrate", "60M", "-bufsize", "120M", "-profile:v", "high",
        "-level", "5.2", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart",
        "-metadata", f"title={title}", "-t", f"{tl['total']:.3f}", final,
    ])
    return final


def _run_in(cwd: Path, args: list) -> None:
    """Der ass-Filter mag keine absoluten Pfade mit Sonderzeichen → im Projektordner ausführen."""
    import os

    old = os.getcwd()
    os.chdir(cwd)
    try:
        run(args)
    finally:
        os.chdir(old)
