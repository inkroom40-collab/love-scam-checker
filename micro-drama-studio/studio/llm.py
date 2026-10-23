"""Claude-Anbindung mit strukturierter JSON-Ausgabe."""
import json
import os

from .config import DEFAULT_MODEL


class LLMError(RuntimeError):
    pass


def generate_json(system: str, prompt: str, schema: dict, model: str | None = None) -> dict:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise LLMError("Paket 'anthropic' fehlt: pip install -r requirements.txt") from exc

    client = anthropic.Anthropic()
    params = dict(
        model=model or os.environ.get("STUDIO_MODEL", DEFAULT_MODEL),
        max_tokens=32000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": schema}},
    )
    try:
        # Server-seitiger Fallback: lehnt ein Modell ab, springt automatisch ein passendes ein.
        with client.beta.messages.stream(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params
        ) as stream:
            response = stream.get_final_message()
    except (TypeError, anthropic.BadRequestError):
        # Ältere SDK-Version oder Plattform ohne Fallback-Support
        with client.messages.stream(**params) as stream:
            response = stream.get_final_message()

    if response.stop_reason == "refusal":
        raise LLMError("Claude hat die Anfrage abgelehnt – bitte Prämisse anpassen.")
    if response.stop_reason == "max_tokens":
        raise LLMError("Antwort wurde abgeschnitten (max_tokens).")
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Ungültiges JSON von Claude: {text[:300]}") from exc


def has_credentials() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    return os.path.isdir(os.path.expanduser("~/.config/anthropic"))
