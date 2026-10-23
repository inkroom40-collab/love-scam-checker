"""JSON-Schemas für die strukturierten Claude-Ausgaben (strict: alle Felder required, keine Extras)."""


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


_S = {"type": "string"}
_N = {"type": "number"}
_LS = {"type": "array", "items": _S}

SCRIPT_SCHEMA = _obj({
    "meta": _obj({
        "title": _S, "logline": _S, "hook": _S, "twist": _S, "ending": _S, "tone": _S,
    }),
    "cast": {"type": "array", "items": _obj({"id": _S, "name": _S, "role": _S, "one_liner": _S})},
    "locations": {"type": "array", "items": _obj({"id": _S, "name": _S, "one_liner": _S})},
    "shots": {"type": "array", "items": _obj({
        "id": _S,
        "location_id": _S,
        "character_ids": _LS,
        "shot_type": _S,
        "camera_move": _S,
        "lens": _S,
        "action": _S,
        "duration_s": _N,
        "sfx": _S,
        "lines": {"type": "array", "items": _obj({"speaker_id": _S, "text": _S, "emotion": _S})},
    })},
})

CHARACTERS_SCHEMA = _obj({
    "characters": {"type": "array", "items": _obj({
        "id": _S, "name": _S, "age": _S, "gender": {"type": "string", "enum": ["female", "male", "nonbinary"]},
        "role": _S, "appearance": _S, "face": _S, "hair": _S, "body": _S, "wardrobe": _S,
        "signature_detail": _S, "personality": _S, "motivation": _S, "arc": _S,
        "voice": _obj({"timbre": _S, "pace": _S, "accent": _S, "catchphrase": _S}),
        "expressions": _LS,
    })},
})

ENVIRONMENTS_SCHEMA = _obj({
    "environments": {"type": "array", "items": _obj({
        "id": _S, "name": _S, "int_ext": {"type": "string", "enum": ["INT", "EXT", "INT/EXT"]},
        "time_of_day": _S, "description": _S, "architecture": _S, "lighting": _S,
        "color_palette": _LS, "key_props": _LS, "atmosphere": _S, "sound_ambience": _S,
    })},
})
