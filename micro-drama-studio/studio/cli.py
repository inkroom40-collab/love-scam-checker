"""Kommandozeile: python -m studio <befehl> …"""
import argparse
import sys
import time
from pathlib import Path

from . import llm, render, subtitles, voice, writers
from .config import FORMATS, GENRES, LOOKS
from .project import Project, slugify

STEPS = ["script", "characters", "environments", "shots", "voice", "subs", "render"]


def _banner(txt: str) -> None:
    print(f"\n\033[1;35m▶ {txt}\033[0m")


def run_step(proj: Project, step: str, args) -> None:
    _run_step(proj, step, args)
    # Zeitstempel je Schritt → Dashboard erkennt veraltete Ergebnisse
    proj.data.setdefault("steps", {})[step] = time.time()
    proj.save()


def _run_step(proj: Project, step: str, args) -> None:
    if step == "script":
        _banner("1/7 Skript schreiben")
        d = writers.write_script(proj)
        print(f"  „{d['meta']['title']}“ – {len(d['shots'])} Shots → script.md")
    elif step == "characters":
        _banner("2/7 Charakter-Sheets")
        for c in writers.write_characters(proj):
            print(f"  👤 {c['name']} → characters/{c['id']}.md")
    elif step == "environments":
        _banner("3/7 Umgebungen / Sets")
        for e in writers.write_environments(proj):
            print(f"  🏠 {e['name']} → environments/{e['id']}.md")
    elif step == "shots":
        _banner("4/7 Shotlist + Bild-/Video-Prompts")
        print(f"  {len(writers.write_shot_prompts(proj))} Shots → shotlist.md")
    elif step == "voice":
        _banner("5/7 Voiceover")
        tl = voice.make_voiceover(proj, getattr(args, "tts", "auto"))
        print(f"  Provider: {tl['provider']} · Länge {tl['total']:.1f}s → audio/voiceover.wav")
        if abs(tl["total"] - proj.settings.get("seconds", 30)) > 4:
            print(f"  ⚠ Ziel waren {proj.settings.get('seconds', 30)}s – Dialog ggf. kürzen.")
    elif step == "subs":
        _banner("6/7 Untertitel")
        n = subtitles.make_subtitles(proj, getattr(args, "speaker_names", False))
        print(f"  {n['cues']} Untertitel → subtitles/subtitles.srt + .ass")
    elif step == "render":
        _banner("7/7 4K-Render")
        out = render.render(proj, burn_subs=not getattr(args, "no_burn", False),
                            letterbox=getattr(args, "letterbox", False), music=getattr(args, "music", None))
        print(f"  ✅ {out}")


def new_project(args) -> Project:
    demo = args.demo or not llm.has_credentials()
    if demo and not args.demo:
        print("ℹ Kein ANTHROPIC_API_KEY gefunden → Demo-Modus mit Beispielfolge.")
    premise = args.premise or "Oma will ihren Online-Prinzen heiraten – die Enkelin wittert Love Scam."
    settings = {"premise": premise, "genre": args.genre, "language": args.lang, "aspect": args.aspect,
                "look": args.look, "seconds": args.seconds, "demo": demo, "preset": args.preset}
    if args.model:
        settings["model"] = args.model
    title = args.name or ("der-prinz-aus-dubai" if demo else slugify(premise)[:40])
    proj = Project.create(Path(args.out), title, settings)
    print(f"📁 Projekt: {proj.root}")
    return proj


def cmd_new(args) -> None:
    proj = new_project(args)
    steps = STEPS if not args.no_render else STEPS[:-1]
    for s in steps:
        run_step(proj, s, args)
    print(f"\nFertig. Lege generierte Bilder/Videos in {proj.root}/assets/shots/<shot-id>.mp4|png ab und "
          f"führe `python -m studio render {proj.root}` erneut aus.")


def cmd_step(args) -> None:
    proj = Project(Path(args.project))
    if not proj.file.exists():
        sys.exit(f"Kein Projekt unter {args.project}")
    todo = STEPS[STEPS.index(args.step):] if args.from_here else [args.step]
    for s in todo:
        run_step(proj, s, args)


def cmd_dashboard(args) -> None:
    from .dashboard import serve

    serve(Path(args.projects), args.host, args.port)


def main() -> None:
    p = argparse.ArgumentParser(prog="studio", description="4K Cinematic Micro Drama Workflow (30 s)")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="neue Folge komplett generieren")
    n.add_argument("premise", nargs="?", help="Idee/Prämisse der Folge")
    n.add_argument("--genre", default="micro-drama", choices=list(GENRES))
    n.add_argument("--lang", default="de", help="Dialogsprache (de, en, …)")
    n.add_argument("--aspect", default="9:16", choices=list(FORMATS))
    n.add_argument("--look", default="cinematic", choices=list(LOOKS))
    n.add_argument("--seconds", type=int, default=30)
    n.add_argument("--name", help="Projektname (Ordner)")
    n.add_argument("--out", default="projects")
    n.add_argument("--model", help="Claude-Modell (Standard: claude-opus-5-5)")
    n.add_argument("--demo", action="store_true", help="ohne API: Beispielfolge verwenden")
    n.add_argument("--no-render", action="store_true", help="4K-Render überspringen")
    n.add_argument("--preset", default="medium", help="x264-Preset (ultrafast … veryslow)")
    _common(n)
    n.set_defaults(func=cmd_new)

    s = sub.add_parser("run", help="einzelnen Schritt (neu) ausführen")
    s.add_argument("step", choices=STEPS)
    s.add_argument("project", help="Projektordner")
    s.add_argument("--from-here", action="store_true", help="ab diesem Schritt alles danach ebenfalls")
    _common(s)
    s.set_defaults(func=cmd_step)

    r = sub.add_parser("render", help="Kurzform für: run render <projekt>")
    r.add_argument("project")
    _common(r)
    r.set_defaults(func=cmd_step, step="render", from_here=False)

    d = sub.add_parser("dashboard", help="Web-Dashboard starten")
    d.add_argument("--projects", default="projects", help="Ordner mit den Projekten")
    d.add_argument("--host", default="127.0.0.1")
    d.add_argument("--port", type=int, default=8765)
    d.set_defaults(func=cmd_dashboard)

    args = p.parse_args()
    args.func(args)


def _common(sp) -> None:
    sp.add_argument("--tts", default="auto", choices=["auto", "elevenlabs", "edge", "espeak", "silent"])
    sp.add_argument("--music", help="Musikdatei (sonst assets/music.*)")
    sp.add_argument("--letterbox", action="store_true", help="2.39:1-Kinobalken (nur 16:9)")
    sp.add_argument("--no-burn", action="store_true", help="Untertitel nicht einbrennen")
    sp.add_argument("--speaker-names", action="store_true", help="Sprechernamen in der SRT")
