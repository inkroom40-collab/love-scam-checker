"""Projektordner + project.json als zentrale 'Single Source of Truth'."""
import json
import re
import unicodedata
from pathlib import Path


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "episode"


class Project:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.file = self.root / "project.json"
        self.data: dict = json.loads(self.file.read_text("utf-8")) if self.file.exists() else {}

    @classmethod
    def create(cls, base: Path, title: str, settings: dict) -> "Project":
        root = Path(base) / slugify(title)
        root.mkdir(parents=True, exist_ok=True)
        proj = cls(root)
        proj.data.setdefault("settings", {}).update(settings)
        proj.save()
        return proj

    def save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), "utf-8")

    def path(self, *parts: str) -> Path:
        p = self.root.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    # Bequeme Zugriffe
    @property
    def settings(self) -> dict:
        return self.data.setdefault("settings", {})

    @property
    def script(self) -> dict:
        return self.data.get("script", {})

    def require(self, key: str, step: str) -> dict:
        if key not in self.data:
            raise SystemExit(f"Schritt '{step}' fehlt noch – zuerst ausführen.")
        return self.data[key]

    def character(self, cid: str) -> dict | None:
        return next((c for c in self.data.get("characters", []) if c["id"] == cid), None)

    def environment(self, eid: str) -> dict | None:
        return next((e for e in self.data.get("environments", []) if e["id"] == eid), None)
