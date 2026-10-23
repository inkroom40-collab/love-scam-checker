"""Zentrale Einstellungen: Formate, Looks, Stimmen."""

FORMATS = {
    # Micro-Dramen laufen auf TikTok/Reels/Shorts – Hochformat ist Standard.
    "9:16": {"width": 2160, "height": 3840, "label": "4K UHD vertikal (2160x3840)"},
    "16:9": {"width": 3840, "height": 2160, "label": "4K UHD (3840x2160)"},
    "1:1": {"width": 2160, "height": 2160, "label": "4K quadratisch (2160x2160)"},
}

FPS = 24
TARGET_SECONDS = 30
WORDS_PER_SECOND = 2.6  # Schätzung für Sprechtempo, wenn keine echte Audiolänge vorliegt

GENRES = {
    "micro-drama": (
        "Vertical micro drama: hook in the first 2 seconds, high emotional stakes, "
        "a reveal or twist around second 20, and a cliffhanger ending that makes people want part 2."
    ),
    "sitcom": (
        "Single-camera sitcom: a clear comedic premise, escalating misunderstanding, "
        "rhythmic setup-punchline dialogue, a button joke at the very end."
    ),
    "thriller": "Short thriller: dread from frame one, withheld information, a shocking final image.",
    "romance": "Romantic micro drama: longing, a meet-cute or betrayal, an emotional beat that lands in the last shot.",
}

# Basis-Look, der an jeden Bild-/Video-Prompt angehängt wird, damit alles wie aus einem Film aussieht.
LOOKS = {
    "cinematic": (
        "cinematic film still, shot on ARRI Alexa 35, anamorphic lens, shallow depth of field, "
        "motivated practical lighting, rich contrast, subtle film grain, Kodak Vision3 500T color science, "
        "8K detail, photorealistic, 4K UHD"
    ),
    "teal-orange": (
        "blockbuster teal and orange grade, shot on RED V-Raptor, 35mm prime, high dynamic range, "
        "volumetric haze, crisp skin texture, photorealistic, 4K UHD"
    ),
    "sitcom-bright": (
        "bright high-key single-camera sitcom look, soft key light, warm practicals, saturated colors, "
        "shot on Sony Venice 2, 35mm, natural skin tones, photorealistic, 4K UHD"
    ),
    "noir": (
        "neo-noir, hard side light, deep shadows, wet reflective surfaces, neon accents, "
        "shot on ARRI Alexa Mini LF, 40mm anamorphic, photorealistic, 4K UHD"
    ),
}

NEGATIVE_PROMPT = (
    "blurry, low resolution, watermark, text, logo, extra fingers, deformed hands, distorted face, "
    "cartoon, CGI look, oversaturated, plastic skin, duplicate characters"
)

# Edge-TTS-Stimmpools (kostenlos). Jede Figur bekommt eine eigene Stimme aus dem passenden Pool.
EDGE_VOICES = {
    "de": {
        "female": ["de-DE-KatjaNeural", "de-DE-AmalaNeural", "de-DE-SeraphinaMultilingualNeural", "de-AT-IngridNeural"],
        "male": ["de-DE-ConradNeural", "de-DE-KillianNeural", "de-DE-FlorianMultilingualNeural", "de-CH-JanNeural"],
        "narrator": "de-DE-FlorianMultilingualNeural",
    },
    "en": {
        "female": ["en-US-AriaNeural", "en-US-JennyNeural", "en-GB-SoniaNeural", "en-US-AvaMultilingualNeural"],
        "male": ["en-US-GuyNeural", "en-US-DavisNeural", "en-GB-RyanNeural", "en-US-AndrewMultilingualNeural"],
        "narrator": "en-US-AndrewMultilingualNeural",
    },
}

# Emotion → leichte Prosodie-Anpassung für Edge-TTS (rate, pitch)
EMOTION_PROSODY = {
    "angry": ("+8%", "+2Hz"),
    "excited": ("+10%", "+4Hz"),
    "happy": ("+5%", "+3Hz"),
    "sad": ("-10%", "-3Hz"),
    "whisper": ("-8%", "-2Hz"),
    "scared": ("+6%", "+3Hz"),
    "sarcastic": ("-4%", "-1Hz"),
    "shocked": ("+4%", "+5Hz"),
    "calm": ("-5%", "+0Hz"),
}

DEFAULT_MODEL = "claude-opus-5-5"
