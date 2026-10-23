"""Schritt 6: Untertitel als SRT (Plattform-Upload) und ASS (cinematic eingebrannt)."""
from .config import FORMATS
from .project import Project

MAX_CHARS = 32  # kurze Häppchen lesen sich auf dem Handy besser


def _chunks(text: str, start: float, end: float) -> list:
    words, parts, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > MAX_CHARS:
            parts.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    parts.append(cur)
    total = sum(len(p) for p in parts) or 1
    out, t = [], start
    for p in parts:
        d = (end - start) * len(p) / total
        out.append((t, t + d, p))
        t += d
    return out


def _srt_ts(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def _ass_ts(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def make_subtitles(proj: Project, speaker_names: bool = False) -> dict:
    tl = proj.require("timeline", "voiceover")
    names = {c["id"]: c["name"].strip("'") for c in proj.data.get("characters", [])}
    fmt = FORMATS[proj.settings["aspect"]]
    w, h = fmt["width"], fmt["height"]
    vertical = h > w
    font_size = int(w * (0.058 if vertical else 0.036))
    margin_v = int(h * (0.24 if vertical else 0.08))  # Hochformat: über der TikTok/Reels-UI

    cues = []
    for ln in tl["lines"]:
        for s, e, txt in _chunks(ln["text"], ln["start"], ln["end"]):
            cues.append({"start": s, "end": e, "text": txt, "speaker": ln["speaker"]})

    srt = []
    for i, c in enumerate(cues, 1):
        prefix = f"{names.get(c['speaker'], c['speaker']).upper()}: " if speaker_names and c["speaker"] != "narrator" else ""
        srt.append(f"{i}\n{_srt_ts(c['start'])} --> {_srt_ts(c['end'])}\n{prefix}{c['text']}\n")
    proj.path("subtitles", "subtitles.srt").write_text("\n".join(srt), "utf-8")

    ass = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: Dialog,Inter,{font_size},&H00FFFFFF,&H000000FF,&H00101010,&H96000000,-1,0,0,0,100,100,1,0,1,"
        f"{max(4, font_size // 12)},{max(2, font_size // 22)},2,{int(w * .08)},{int(w * .08)},{margin_v},1",
        f"Style: Narrator,Inter,{font_size},&H0080E6FF,&H000000FF,&H00101010,&H96000000,-1,-1,0,0,100,100,1,0,1,"
        f"{max(4, font_size // 12)},{max(2, font_size // 22)},2,{int(w * .08)},{int(w * .08)},{margin_v},1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for c in cues:
        style = "Narrator" if c["speaker"] == "narrator" else "Dialog"
        # kleiner Pop-in-Effekt wie bei Social-Captions
        anim = r"{\fad(60,40)\fscx92\fscy92\t(0,90,\fscx100\fscy100)}"
        ass.append(f"Dialogue: 0,{_ass_ts(c['start'])},{_ass_ts(c['end'])},{style},"
                   f"{names.get(c['speaker'], c['speaker'])},0,0,0,,{anim}{c['text']}")
    proj.path("subtitles", "subtitles.ass").write_text("\n".join(ass) + "\n", "utf-8")
    return {"cues": len(cues)}
