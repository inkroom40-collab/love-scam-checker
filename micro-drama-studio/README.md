# 🎬 4K Cinematic Micro Drama Studio

Ein Workflow für **30-Sekunden-Micro-Dramen und Sitcoms** in 4K. Aus einer einzigen Idee erzeugt er:

| # | Schritt | Ergebnis |
|---|---------|----------|
| 1 | **Skript** | `script.md`: Logline, Hook, Twist, Cliffhanger, 6–9 Shots mit Dialog und Timing |
| 2 | **Charakter-Sheets** | `characters/<id>.md`: Aussehen, Garderobe, Stimme, Mimik sowie Prompts für Porträt, Turnaround und Expression Sheet |
| 3 | **Umgebungen** | `environments/<id>.md`: Set-Design, Licht, Farbpalette, Props sowie Prompts für Establishing Shot, Gegenschuss und Details |
| 4 | **Shotlist** | `shotlist.md`: pro Shot ein Keyframe-Prompt (Text-to-Image) und ein Motion-Prompt (Image-to-Video) mit Referenzbildern |
| 5 | **Voiceover** | `audio/lines/*.wav` (jede Zeile einzeln) und `audio/voiceover.wav` (getimt, auf −14 LUFS) |
| 6 | **Untertitel** | `subtitles/subtitles.srt` für den Upload und `subtitles.ass` mit Pop-in-Animation zum Einbrennen |
| 7 | **4K-Render** | `render/<projekt>_4k_9x16.mp4`: 2160×3840 bzw. 3840×2160, 24 fps, H.264 High, AAC 320k |

`project.json` ist die zentrale Projektdatei. Jeder Schritt liest sie und schreibt sie fort, deshalb kannst du jeden Schritt einzeln wiederholen oder die Datei von Hand anpassen.

## Installation

```bash
cd micro-drama-studio
pip install -r requirements.txt      # anthropic, edge-tts, requests
sudo apt install ffmpeg              # wird für Voiceover, Untertitel und Render gebraucht
export ANTHROPIC_API_KEY=sk-ant-...  # für Skript, Charaktere und Umgebungen
```

## Schnellstart

```bash
# Offline-Demo ohne API-Key: "Der Prinz aus Dubai"
python -m studio new --demo

# Eigene Folge (Micro-Drama, Hochformat, Deutsch)
python -m studio new "Eine Braut erfährt am Altar per WhatsApp, dass der Bräutigam verheiratet ist"

# Sitcom im 16:9-Kinoformat mit Letterbox, auf Englisch
python -m studio new "Two roommates both secretly adopt the same cat" \
    --genre sitcom --aspect 16:9 --letterbox --look sitcom-bright --lang en
```

### Optionen

| Option | Werte | Standard |
|---|---|---|
| `--genre` | `micro-drama`, `sitcom`, `thriller`, `romance` | `micro-drama` |
| `--aspect` | `9:16` (TikTok/Reels/Shorts), `16:9`, `1:1` | `9:16` |
| `--look` | `cinematic`, `teal-orange`, `sitcom-bright`, `noir` | `cinematic` |
| `--lang` | Sprache der Dialoge, z. B. `de`, `en` | `de` |
| `--seconds` | Ziellänge in Sekunden | `30` |
| `--tts` | `auto`, `elevenlabs`, `edge`, `espeak`, `silent` | `auto` |
| `--music` | Musikdatei. Sie wird per Sidechain automatisch unter die Stimmen geduckt. | `assets/music.*` |
| `--letterbox` | Kinobalken im Format 2.39:1 (nur bei 16:9) | aus |
| `--no-burn` | Untertitel nicht ins Bild einbrennen | aus |
| `--preset` | x264-Preset, `ultrafast` für schnelle Vorschauen | `medium` |
| `--model` | Claude-Modell | `claude-opus-5-5` |

## 🎥 Videos mit Grok (xAI)

Grok Imagine erzeugt die Bilder und Videoclips direkt aus den Sheets und der Shotlist:

1. **Referenzen** (`grok-imagine-image`): ein Porträt pro Figur und ein Set-Bild pro Umgebung → `assets/characters/`, `assets/environments/`
2. **Keyframes**: das erste Bild jedes Shots. Figuren und Set gehen als Referenzbilder mit, damit Gesichter, Kostüme und Räume in allen Shots gleich bleiben → `assets/keyframes/<shot>.png`
3. **Videos** (`grok-imagine-video-1.5`): Image-to-Video aus dem Keyframe, zusätzlich mit den Referenzen. Die Länge entspricht der Shot-Länge laut Voiceover (aufgerundet, max. 15 s). → `assets/shots/<shot>.mp4`

Der Render skaliert die Clips mit Lanczos auf 4K hoch, legt Film-Look, Voiceover und Untertitel darüber und schneidet sie auf die exakte Länge. Grok erzeugt höchstens 1080p.

```bash
pip install xai-sdk
export XAI_API_KEY=xai-...                     # Key unter console.x.ai

python -m studio grok projects/<name> --render            # alles: Referenzen → Keyframes → Videos → 4K
python -m studio grok projects/<name> --stage refs        # nur Referenzbilder
python -m studio grok projects/<name> --stage videos --shots s03,s07 --force   # einzelne Shots neu
python -m studio new "Idee …" --grok --resolution 1080p   # komplette Folge in einem Rutsch
```

| Option | Bedeutung | Standard |
|---|---|---|
| `--stage` | `all`, `refs`, `keyframes`, `videos` | `all` |
| `--shots` | nur bestimmte Shots, z. B. `s01,s04` | alle |
| `--force` | vorhandene Bilder und Videos neu erzeugen | aus |
| `--resolution` | `480p`, `720p`, `1080p` | `720p` |
| `--grok-model` | `grok-imagine-video-1.5` oder `grok-imagine-video` | `grok-imagine-video-1.5` |
| `--grok-audio` | Grok erzeugt eigenen Ton im Clip. Sonst stumm, weil das Voiceover vom Workflow kommt. | aus |
| `--workers` | parallele Anfragen | `3` |

- Vorhandene Assets werden übersprungen. Ein zweiter Lauf erzeugt nur, was noch fehlt, und deine eigenen Uploads bleiben erhalten.
- Schlägt ein Shot fehl (Moderation, Timeout), laufen die anderen weiter. Am Ende steht, welche Shots du mit `--shots` wiederholen musst. Ein vorhandener Clip wird nur ersetzt, wenn der neue erfolgreich heruntergeladen wurde.
- Modell, Modus, Länge und die von der API gemeldeten Kosten stehen pro Clip in `project.json` unter `grok`.
- Im Dashboard findest du dieselben Funktionen im Tab **Shots & Assets** (komplette Folge oder nur fehlende Videos, mit Auswahl von Modell, Auflösung und Ton) sowie auf jeder Shot-Karte (neuer Keyframe, Video neu). In den Tabs **Charaktere** und **Umgebungen** erzeugst du fehlende Referenzbilder.

## 🖥 Dashboard

```bash
python -m studio dashboard            # → http://127.0.0.1:8765
python -m studio dashboard --projects ~/serien --port 9000
```

Das Dashboard läuft lokal im Browser und nutzt dieselben Projektordner wie die Kommandozeile. Es braucht keine zusätzlichen Pakete.

- **Neue Folge**: Idee, Genre, Format, Look, Sprache, Länge und Voiceover festlegen, dann generieren. Der Fortschritt erscheint live im Log.
- **Pipeline**: Für jeden der 7 Schritte siehst du, ob er offen, fertig, veraltet oder gerade aktiv ist. Mit ▶ startest du einen einzelnen Schritt, mit ▶▶ diesen und alle folgenden. Veraltet heißt: Ein Schritt, von dem er abhängt, wurde später geändert. Das gilt auch für neu hochgeladene Assets beim Render.
- **Timeline**: Alle Shots im richtigen Längenverhältnis und farbig nach Set, mit Markierungen für die Dialogzeilen und einer Linie für die Ziellänge. Ein Klick auf einen Shot springt zu seiner Karte.
- **Render & Übersicht**: 4K-Player mit Download, Kennzahlen (Länge, Wörter pro Sekunde, Assets), Produktions-Checkliste und Musik-Upload.
- **Skript-Editor**: Einstellung, Kamera, Objektiv, Dauer, Action, SFX und Dialog pro Shot bearbeiten. Dialog-Änderungen markieren nur Shotlist, Voiceover, Untertitel und Render als veraltet.
- **Charaktere und Umgebungen**: Sheets mit Farbpalette, Prompts zum Kopieren und Referenzbildern per Drag & Drop. Die TTS-Stimme lässt sich pro Figur ändern.
- **Shots & Assets**: Ein generiertes Bild oder Video ziehst du direkt auf die Shot-Karte. Daneben stehen Keyframe-, Motion- und Negative-Prompt.
- **Voiceover und Untertitel**: Gesamtspur und jede Zeile einzeln anhören, SRT und ASS herunterladen.

> Der Server lauscht standardmäßig nur auf `127.0.0.1`. Mit `--host 0.0.0.0` erreichst du ihn auch aus dem Netzwerk. Das Dashboard hat aber keinen Login, also nur in vertrauenswürdigen Netzen verwenden.

## Der Produktions-Loop

1. Mit **`python -m studio new "…"`** entstehen Skript, Sheets, Prompts, Voiceover und Untertitel. Dazu kommt ein **4K-Animatic** mit Storyboard-Karten, mit dem du das Timing sofort prüfen kannst.
2. **Referenzen erzeugen:** Die Prompts aus `characters/*.md` und `environments/*.md` gibst du in Midjourney, Flux, Nano Banana oder einem ähnlichen Tool ein. Die Ergebnisse speicherst du so:
   - `assets/characters/<id>.png` als Character Reference (`--cref`, IP-Adapter, Kling Elements)
   - `assets/environments/<id>.png` als Set- und Style-Referenz
3. **Shots erzeugen:** Für jeden Shot in `shotlist.md` erstellst du zuerst den Keyframe und animierst ihn dann mit dem Motion-Prompt (Kling, Veo, Runway, Sora, Hailuo …). Speichere das Ergebnis als
   - `assets/shots/s01.mp4` (Video) **oder** `assets/shots/s01.png` (Standbild, das automatisch eine Ken-Burns-Fahrt passend zur Kamerabewegung bekommt).
4. Mit **`python -m studio render projects/<name>`** wird alles neu geschnitten: Shots auf die Länge der Voiceover-Spur, Film-Look (Kontrast, Vignette, Korn), Voiceover und Musik, eingebrannte Untertitel. Fehlende Shots bleiben Storyboard-Karten.

Einzelne Schritte wiederholst du so:

```bash
python -m studio run script     projects/<name> --from-here   # neues Skript und alles danach
python -m studio run voice      projects/<name> --tts elevenlabs
python -m studio run subs       projects/<name> --speaker-names
python -m studio render         projects/<name> --music track.mp3
```

## Voiceover

- **ElevenLabs** (die beste Qualität): Setze `ELEVENLABS_API_KEY`. Eigene Stimmen legst du pro Figur über `ELEVENLABS_VOICE_<ID>` fest (z. B. `ELEVENLABS_VOICE_GERDA=…`, `ELEVENLABS_VOICE_NARRATOR=…`).
- **Edge-TTS** (kostenlos, braucht Internet): Neural-Stimmen auf Deutsch und Englisch. Jede Figur bekommt automatisch eine eigene Stimme, und die Emotion steuert Tempo und Tonhöhe.
- **espeak / silent**: Offline-Fallback. `silent` erzeugt stumme Platzhalter in der geschätzten Sprechlänge, sodass Timing und Untertitel trotzdem stimmen.
- Schlägt ein Anbieter fehl, wechselt der Workflow automatisch zum nächsten.
- Die Zuordnung von Figuren zu Stimmen steht in `project.json` unter `voices` und lässt sich dort von Hand ändern.

Die Shot-Längen richten sich nach der **echten Länge des Voiceovers**: Ist ein Satz länger als geplant, verlängert sich der Shot. Wenn die Gesamtlänge mehr als 4 Sekunden von der Ziellänge abweicht, gibt der Workflow eine Warnung aus.

## Projektstruktur

```
projects/der-prinz-aus-dubai/
├── project.json            ← alle Daten (Skript, Figuren, Sets, Prompts, Timeline, Stimmen)
├── script.md
├── characters/gerda.md …
├── environments/kitchen.md …
├── shotlist.md
├── assets/                 ← hier legst du deine generierten Bilder, Videos und Musik ab
│   ├── characters/  environments/  shots/  music.mp3
├── audio/voiceover.wav, audio/lines/*.wav
├── subtitles/subtitles.srt, subtitles.ass
└── render/der-prinz-aus-dubai_4k_9x16.mp4
```
