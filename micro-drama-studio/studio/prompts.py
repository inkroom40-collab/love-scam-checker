"""Prompt-Vorlagen für die einzelnen Workflow-Schritte."""
import json

from .config import GENRES, TARGET_SECONDS

SHOWRUNNER = (
    "You are an award-winning showrunner, screenwriter and cinematographer specialised in vertical "
    "micro dramas and short-form sitcoms that go viral on TikTok, Reels and YouTube Shorts. "
    "You write tight, visual, emotionally loaded scenes where every second counts, and you think in shots. "
    "All dialogue must be written in the requested language; all visual descriptions in English "
    "(they feed image and video generation models)."
)


def script_prompt(premise: str, genre: str, language: str, aspect: str, seconds: int = TARGET_SECONDS) -> str:
    words = int(seconds * 2.3)
    return f"""Write a complete {seconds}-second episode.

PREMISE: {premise}
FORMAT: {genre} – {GENRES.get(genre, genre)}
DIALOGUE LANGUAGE: {language}
ASPECT RATIO: {aspect} (compose shots for this frame)

Rules:
- 6 to 9 shots, durations summing to exactly {seconds} seconds (each shot 2–6 s).
- Shot 1 must be a scroll-stopping hook (visual shock, bold line, or mystery).
- Max ~{words} spoken words in total so the voiceover fits the runtime. Short, punchy lines.
- 2–4 characters. Ids are lowercase slugs (e.g. "lena"). Use speaker_id "narrator" for voiceover narration.
- Location ids are lowercase slugs (e.g. "kitchen"). Max 3 locations.
- shot_type: e.g. "extreme close-up", "medium two-shot", "over-the-shoulder", "wide establishing".
- camera_move: e.g. "slow push-in", "handheld", "whip pan", "static", "dolly out", "crane down".
- lens: focal length + character, e.g. "85mm shallow focus".
- action: purely visual English description of what happens in frame (blocking, expressions, light).
- emotion per line: one word (angry, sad, happy, whisper, sarcastic, shocked, scared, calm, excited, neutral).
- sfx: short English sound design note (or empty string).
- Ending: {"cliffhanger" if genre != "sitcom" else "button joke"}."""


def characters_prompt(script: dict) -> str:
    return f"""Create production-ready CHARACTER SHEETS for every cast member (not the narrator) of this episode.
They will be used to generate consistent AI images across all shots, so be extremely specific and visual
(exact hair colour/length/style, eye colour, skin tone, distinctive features, exact garments with colours/materials).
Keep the same ids. Personality/motivation/arc may be in English. expressions: 4–6 key facial expressions the
character needs in this episode. voice.catchphrase in the dialogue language of the script.

EPISODE:
{json.dumps(script, ensure_ascii=False, indent=2)}"""


def environments_prompt(script: dict) -> str:
    return f"""Create production-ready ENVIRONMENT / SET DESIGN sheets for every location of this episode.
They must allow generating consistent backgrounds across shots: architecture, materials, layout, practical
light sources, colour palette (hex or named colours), key props, atmosphere (haze, rain, dust), ambient sound.
Keep the same ids. Everything in English.

EPISODE:
{json.dumps(script, ensure_ascii=False, indent=2)}"""
