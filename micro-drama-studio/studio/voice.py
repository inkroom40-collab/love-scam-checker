"""Schritt 5: Voiceover – jede Dialogzeile wird vertont, danach entsteht eine getimte Gesamtspur."""
import asyncio
import importlib.util
import os
import shutil
from pathlib import Path

from .config import EDGE_VOICES, EMOTION_PROSODY, WORDS_PER_SECOND
from .media import duration, run
from .project import Project

SHOT_LEAD_IN = 0.25   # Pause am Anfang jedes Shots
LINE_GAP = 0.20       # Pause zwischen zwei Zeilen
SHOT_TAIL = 0.35      # Luft nach der letzten Zeile

ELEVEN_DEFAULTS = {"female": "21m00Tcm4TlvDq8ikWAM", "male": "pNInz6obpgDQGcFmaJgB",
                   "nonbinary": "EXAVITQu4vr4xnSDxMaL", "narrator": "onwK4e9ZLuTAKqWW03F9"}


def pick_provider(requested: str) -> str:
    if requested != "auto":
        return requested
    if os.environ.get("ELEVENLABS_API_KEY"):
        return "elevenlabs"
    if importlib.util.find_spec("edge_tts"):
        return "edge"
    if shutil.which("espeak-ng") or shutil.which("espeak"):
        return "espeak"
    return "silent"


def assign_voices(proj: Project, provider: str) -> dict:
    """Ordnet jeder Figur eine eigene, gleichbleibende Stimme zu (überschreibbar in project.json → voices)."""
    lang = proj.settings["language"][:2]
    voices = proj.data.get("voices", {})
    pools = EDGE_VOICES.get(lang, EDGE_VOICES["en"])
    used = {"female": 0, "male": 0}
    for c in proj.data.get("characters", []):
        if c["id"] in voices and voices[c["id"]].get("provider") == provider:
            continue
        g = c["gender"] if c["gender"] in used else "female"
        if provider == "elevenlabs":
            vid = os.environ.get(f"ELEVENLABS_VOICE_{c['id'].upper()}", ELEVEN_DEFAULTS[c["gender"]])
        else:
            vid = pools[g][used[g] % len(pools[g])]
        used[g] += 1
        voices[c["id"]] = {"provider": provider, "voice": vid}
    if voices.get("narrator", {}).get("provider") != provider:
        voices["narrator"] = {"provider": provider, "voice": os.environ.get(
            "ELEVENLABS_VOICE_NARRATOR", ELEVEN_DEFAULTS["narrator"]) if provider == "elevenlabs" else pools["narrator"]}
    proj.data["voices"] = voices
    return voices


def _tts(provider: str, voice: str, text: str, emotion: str, lang: str, raw: Path, est: float) -> None:
    if provider == "elevenlabs":
        import requests

        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "accept": "audio/mpeg"},
            json={"text": text, "model_id": os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
                  "voice_settings": {"stability": 0.35, "similarity_boost": 0.8, "style": 0.55,
                                     "use_speaker_boost": True}},
            timeout=120,
        )
        r.raise_for_status()
        raw.write_bytes(r.content)
    elif provider == "edge":
        import edge_tts

        rate, pitch = EMOTION_PROSODY.get(emotion, ("+0%", "+0Hz"))
        asyncio.run(edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(raw)))
    elif provider == "espeak":
        exe = shutil.which("espeak-ng") or shutil.which("espeak")
        run([exe, "-v", lang, "-s", "165", "-w", raw, text])
    else:  # silent – Platzhalter mit geschätzter Länge, damit Timing & Untertitel trotzdem stimmen
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{est:.2f}", raw])


def make_voiceover(proj: Project, requested: str = "auto") -> dict:
    provider = pick_provider(requested)
    chain = [provider] + [p for p in ("espeak", "silent") if p != provider
                          and (p == "silent" or shutil.which("espeak-ng") or shutil.which("espeak"))]
    for i, prov in enumerate(chain):
        try:
            return _make_voiceover(proj, prov)
        except Exception as exc:  # Netzwerk, API-Limit, fehlende Stimme …
            if i == len(chain) - 1:
                raise
            print(f"  ⚠ TTS '{prov}' fehlgeschlagen ({type(exc).__name__}: {str(exc)[:120]}) → weiter mit '{chain[i + 1]}'")


def _make_voiceover(proj: Project, provider: str) -> dict:
    script = proj.require("script", "script")
    voices = assign_voices(proj, provider)
    lang = proj.settings["language"][:2]
    lines_dir = proj.root / "audio" / "lines"
    lines_dir.mkdir(parents=True, exist_ok=True)

    timeline = {"provider": provider, "shots": [], "lines": []}
    t = 0.0
    for sh in script["shots"]:
        cursor = t + SHOT_LEAD_IN
        for i, ln in enumerate(sh["lines"]):
            spk = ln["speaker_id"] if ln["speaker_id"] in voices else "narrator"
            est = max(0.8, len(ln["text"].split()) / WORDS_PER_SECOND)
            raw = lines_dir / f"{sh['id']}_{i:02d}_raw{'.wav' if provider in ('espeak', 'silent') else '.mp3'}"
            wav = lines_dir / f"{sh['id']}_{i:02d}_{spk}.wav"
            print(f"  🎙  {sh['id']} {spk:>10}: {ln['text']}")
            _tts(provider, voices[spk]["voice"], ln["text"], ln["emotion"], lang, raw, est)
            # Einheitliches Format + Stille am Anfang/Ende abschneiden
            run(["ffmpeg", "-y", "-i", raw, "-af",
                 "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                 "silenceremove=start_periods=1:start_threshold=-50dB,areverse" if provider != "silent" else "anull",
                 "-ar", "48000", "-ac", "2", wav])
            raw.unlink(missing_ok=True)
            d = duration(wav) or est
            timeline["lines"].append({"shot": sh["id"], "speaker": spk, "text": ln["text"], "emotion": ln["emotion"],
                                      "start": round(cursor, 3), "end": round(cursor + d, 3),
                                      "file": str(wav.relative_to(proj.root))})
            cursor += d + LINE_GAP
        needed = (cursor - LINE_GAP + SHOT_TAIL) - t if sh["lines"] else 0
        dur = round(max(sh["duration_s"], needed), 3)
        timeline["shots"].append({"id": sh["id"], "start": round(t, 3), "end": round(t + dur, 3), "duration": dur})
        t += dur
    timeline["total"] = round(t, 3)

    # Gesamtspur: alle Zeilen per adelay an ihre Position, dann auf -14 LUFS (Social-Media-Standard)
    args = ["ffmpeg", "-y", "-f", "lavfi", "-t", f"{t:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    chains, labels = [], ["[0:a]"]
    for i, ln in enumerate(timeline["lines"], start=1):
        args += ["-i", proj.root / ln["file"]]
        ms = int(ln["start"] * 1000)
        chains.append(f"[{i}:a]adelay={ms}|{ms}[l{i}]")
        labels.append(f"[l{i}]")
    graph = ";".join(chains + [f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=first,"
                                f"loudnorm=I=-14:TP=-1.5:LRA=11[out]"])
    out = proj.path("audio", "voiceover.wav")
    run(args + ["-filter_complex", graph, "-map", "[out]", "-ar", "48000", "-t", f"{t:.3f}", out])

    proj.data["timeline"] = timeline
    proj.save()
    return timeline
