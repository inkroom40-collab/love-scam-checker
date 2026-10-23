"""Schritte 1–4: Skript, Charakter-Sheets, Umgebungen, Shot-Prompts (+ Markdown-Exporte)."""
from . import demo, llm, prompts
from .config import LOOKS, NEGATIVE_PROMPT
from .project import Project


def _ask(proj: Project, prompt: str, schema: dict, fallback: dict) -> dict:
    if proj.settings.get("demo"):
        return fallback
    return llm.generate_json(prompts.SHOWRUNNER, prompt, schema, proj.settings.get("model"))


# ---------------------------------------------------------------- 1. Skript
def write_script(proj: Project) -> dict:
    from .schemas import SCRIPT_SCHEMA

    s = proj.settings
    data = _ask(
        proj,
        prompts.script_prompt(s["premise"], s["genre"], s["language"], s["aspect"], s.get("seconds", 30)),
        SCRIPT_SCHEMA,
        demo.SCRIPT,
    )
    proj.data["script"] = data
    proj.save()

    m = data["meta"]
    out = [f"# {m['title']}", "", f"**Logline:** {m['logline']}", "",
           f"**Hook:** {m['hook']}  ", f"**Twist:** {m['twist']}  ", f"**Ende:** {m['ending']}  ",
           f"**Ton:** {m['tone']}", "", "## Besetzung", ""]
    out += [f"- **{c['name']}** (`{c['id']}`) – {c['role']}: {c['one_liner']}" for c in data["cast"]]
    out += ["", "## Drehbuch", ""]
    names = {c["id"]: c["name"] for c in data["cast"]} | {"narrator": "ERZÄHLER (V.O.)"}
    locs = {l["id"]: l["name"] for l in data["locations"]}
    t = 0.0
    for sh in data["shots"]:
        out.append(f"### {sh['id'].upper()} · {locs.get(sh['location_id'], sh['location_id'])} "
                   f"· {t:04.1f}s–{t + sh['duration_s']:04.1f}s")
        out.append(f"*{sh['shot_type']}, {sh['camera_move']}, {sh['lens']}*  ")
        out.append(f"{sh['action']}")
        if sh.get("sfx"):
            out.append(f"\n🔊 SFX: {sh['sfx']}")
        for ln in sh["lines"]:
            out.append(f"\n> **{names.get(ln['speaker_id'], ln['speaker_id']).upper()}** *({ln['emotion']})*  \n> {ln['text']}")
        out.append("")
        t += sh["duration_s"]
    out.append(f"---\nGesamtlänge laut Skript: **{t:.1f} s**")
    proj.path("script.md").write_text("\n".join(out), "utf-8")
    return data


# ---------------------------------------------------------------- 2. Charaktere
def character_core(c: dict) -> str:
    """Kompakte, immer gleiche Beschreibung → konsistente Figuren in jedem Shot."""
    return (f"{c['name'].strip(chr(39))}, {c['age']} year old {c['gender']}, {c['appearance']}, {c['face']}, "
            f"{c['hair']}, {c['body']}, wearing {c['wardrobe']}, {c['signature_detail']}")


def write_characters(proj: Project) -> list:
    from .schemas import CHARACTERS_SCHEMA

    script = proj.require("script", "script")
    data = _ask(proj, prompts.characters_prompt(script), CHARACTERS_SCHEMA, demo.CHARACTERS)["characters"]
    look = LOOKS[proj.settings.get("look", "cinematic")]
    for c in data:
        core = character_core(c)
        c["prompts"] = {
            "reference_portrait": f"character reference portrait of {core}, neutral expression, looking into camera, "
                                  f"seamless mid-grey studio backdrop, soft key light, {look}",
            "turnaround_sheet": f"character turnaround sheet, same person shown front view, three-quarter view, side "
                                f"profile and back view, full body, {core}, plain light grey background, even studio "
                                f"lighting, consistent proportions, {look}",
            "expression_sheet": f"facial expression sheet, 3x2 grid of close-up portraits of the same person: "
                                f"{', '.join(c['expressions'])}; {core}, {look}",
        }
    proj.data["characters"] = data
    proj.save()

    for c in data:
        md = [f"# Charakter-Sheet: {c['name']}", "",
              "| Feld | Wert |", "|---|---|",
              *[f"| {k} | {c[k]} |" for k in ("id", "age", "gender", "role", "appearance", "face", "hair", "body",
                                               "wardrobe", "signature_detail", "personality", "motivation", "arc")],
              f"| voice | {c['voice']['timbre']}; {c['voice']['pace']}; Akzent: {c['voice']['accent']} |",
              f"| catchphrase | „{c['voice']['catchphrase']}“ |",
              f"| expressions | {', '.join(c['expressions'])} |", "",
              "## Bild-Prompts (Midjourney / Flux / Nano Banana / SDXL)", ""]
        for k, v in c["prompts"].items():
            md += [f"**{k}**", "```", v, "```", ""]
        md += ["**Negative Prompt**", "```", NEGATIVE_PROMPT, "```", "",
               f"> Lege das fertige Referenzbild als `assets/characters/{c['id']}.png` ab – es dient als "
               "Character-Reference (--cref / IP-Adapter / Kling Elements) für alle Shots."]
        proj.path("characters", f"{c['id']}.md").write_text("\n".join(md), "utf-8")
    return data


# ---------------------------------------------------------------- 3. Umgebungen
def environment_core(e: dict) -> str:
    return (f"{e['int_ext']}. {e['name']}, {e['time_of_day']}: {e['description']}; {e['architecture']}; "
            f"lighting: {e['lighting']}; palette {', '.join(e['color_palette'])}; props: {', '.join(e['key_props'])}; "
            f"{e['atmosphere']}")


def write_environments(proj: Project) -> list:
    from .schemas import ENVIRONMENTS_SCHEMA

    script = proj.require("script", "script")
    data = _ask(proj, prompts.environments_prompt(script), ENVIRONMENTS_SCHEMA, demo.ENVIRONMENTS)["environments"]
    look = LOOKS[proj.settings.get("look", "cinematic")]
    ar = proj.settings["aspect"]
    for e in data:
        core = environment_core(e)
        e["prompts"] = {
            "establishing": f"empty set, no people, wide establishing shot of {core}, {look} --ar {ar}",
            "reverse_angle": f"empty set, no people, reverse angle of the same location, {core}, {look} --ar {ar}",
            "detail_plate": f"close detail shots of props: {', '.join(e['key_props'])}, in {e['name']}, "
                            f"{e['lighting']}, {look} --ar {ar}",
        }
    proj.data["environments"] = data
    proj.save()

    for e in data:
        md = [f"# Set / Umgebung: {e['name']}", "",
              "| Feld | Wert |", "|---|---|",
              *[f"| {k} | {e[k]} |" for k in ("id", "int_ext", "time_of_day", "description", "architecture",
                                               "lighting", "atmosphere", "sound_ambience")],
              f"| color_palette | {', '.join(e['color_palette'])} |",
              f"| key_props | {', '.join(e['key_props'])} |", "", "## Bild-Prompts", ""]
        for k, v in e["prompts"].items():
            md += [f"**{k}**", "```", v, "```", ""]
        md.append(f"> Fertiges Set-Bild als `assets/environments/{e['id']}.png` ablegen (Style-/Background-Reference).")
        proj.path("environments", f"{e['id']}.md").write_text("\n".join(md), "utf-8")
    return data


# ---------------------------------------------------------------- 4. Shot-Prompts (Bild + Video)
def write_shot_prompts(proj: Project) -> list:
    script = proj.require("script", "script")
    proj.require("characters", "characters")
    proj.require("environments", "environments")
    look = LOOKS[proj.settings.get("look", "cinematic")]
    ar = proj.settings["aspect"]
    shots = []
    md = [f"# Shotlist & Generierungs-Prompts – {script['meta']['title']}", "",
          f"Format: {ar} · 4K · 24 fps · Look: {proj.settings.get('look', 'cinematic')}", ""]
    for sh in script["shots"]:
        env = proj.environment(sh["location_id"])
        chars = [c for c in (proj.character(cid) for cid in sh["character_ids"]) if c]
        who = "; ".join(character_core(c) for c in chars) or "no people"
        where = environment_core(env) if env else sh["location_id"]
        emo = ", ".join(f"{ln['emotion']}" for ln in sh["lines"]) or "silent"
        image = (f"{sh['shot_type']}, {sh['lens']}. {sh['action']} CHARACTERS: {who}. SETTING: {where}. "
                 f"Mood: {emo}. {look} --ar {ar}")
        video = (f"{sh['camera_move']} camera, {sh['shot_type']}, {sh['lens']}. {sh['action']} "
                 f"Natural subtle motion, realistic physics, lip movement matching speech, "
                 f"cinematic {sh['duration_s']:.0f}-second shot, 24fps, 4K. Keep characters identical to reference images.")
        refs = [f"assets/characters/{c['id']}.png" for c in chars] + [f"assets/environments/{sh['location_id']}.png"]
        shots.append({"id": sh["id"], "image_prompt": image, "video_prompt": video,
                      "negative_prompt": NEGATIVE_PROMPT, "references": refs, "duration_s": sh["duration_s"]})
        md += [f"## {sh['id'].upper()} ({sh['duration_s']} s) – {sh['shot_type']}, {sh['camera_move']}", "",
               "**Keyframe (Text-to-Image)**", "```", image, "```",
               "**Bewegung (Image-to-Video: Kling / Veo / Runway / Sora / Hailuo)**", "```", video, "```",
               f"Referenzen: {', '.join(f'`{r}`' for r in refs)}  ",
               f"➡ Ergebnis speichern als `assets/shots/{sh['id']}.mp4` (oder `.png` für Standbild mit Ken-Burns).", ""]
    proj.data["shot_prompts"] = shots
    proj.save()
    proj.path("shotlist.md").write_text("\n".join(md), "utf-8")
    return shots
