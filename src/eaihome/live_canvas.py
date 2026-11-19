"""A source-bounded, local-only composition service for the EAIhome canvas.

The local model chooses only *which* prebuilt UI panels to show. Facts are
read from a fixed fictional CorrectionStore; model output is never HTML,
JavaScript, a task-status change, a decision or an external action.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, request
from urllib.parse import urlsplit

from .workstore import CorrectionStore

API = "eaihome.canvas.v1"
PANELS = frozenset({"overview", "tasks", "timeline", "sources", "prep", "document"})
OLLAMA = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3:4b"
REPO_ROOT = Path(__file__).resolve().parents[2]
HTML_FILE = REPO_ROOT / "demos" / "EAIhome_live_canvas.html"
DEMO_SCENARIO = REPO_ROOT / "fixtures" / "scenarios" / "EAIhome_mockup_corrections.json"
MODEL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*(?:/[A-Za-z0-9][A-Za-z0-9_.-]*)*(?::[A-Za-z0-9][A-Za-z0-9_.-]*)?$")


def validate_plan(value: object) -> dict:
    """Discard every model field except allowed panel IDs; no arbitrary code."""
    if not isinstance(value, dict) or not isinstance(value.get("panels"), list):
        raise ValueError("Het model gaf geen geldige indeling terug")
    panels: list[str] = []
    for name in value["panels"]:
        if isinstance(name, str) and name in PANELS and name not in panels:
            panels.append(name)
        if len(panels) >= 4:
            break
    if not panels:
        raise ValueError("Het model koos geen bruikbare onderdelen")
    return {"panels": panels}


def _call_ollama(path: str, payload: dict | None = None, timeout: float = 2.0) -> dict:
    """Only the fixed loopback Ollama endpoint is ever contacted."""
    if path not in {"/api/tags", "/api/generate"}:
        raise ValueError("Ongeldige lokale modelroute")
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = request.Request(
        OLLAMA + path,
        data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method="POST" if body is not None else "GET",
    )
    with request.urlopen(req, timeout=timeout) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError("Antwoord van lokaal model is te groot")
    result = json.loads(raw.decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("Ongeldig antwoord van lokaal model")
    return result


def model_available(model: str) -> bool:
    """The configured model must already be installed. Nothing is pulled."""
    if not MODEL_NAME.fullmatch(model):
        raise ValueError("Ongeldige modelnaam")
    try:
        models = _call_ollama("/api/tags", timeout=1.5).get("models", [])
        return any(isinstance(m, dict) and model in (m.get("model"), m.get("name")) for m in models)
    except (OSError, ValueError, error.URLError, TimeoutError, json.JSONDecodeError):
        return False


def plan_with_model(prompt: str, model: str) -> dict:
    """No source or personal content is passed to the LLM, only user prompt."""
    if not MODEL_NAME.fullmatch(model):
        raise ValueError("Ongeldige modelnaam")
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 600:
        raise ValueError("Een vraag moet tussen 1 en 600 tekens lang zijn")
    payload = {
        "model": model,
        "system": (
            "Je kiest een weergave voor een persoonlijke werkruimte. Je hebt GEEN "
            "toegang tot documenten, gegevens of tools. Geef alleen een JSON-object "
            "met 'panels': een lijst van 1 tot 4 unieke ID's uit overview, tasks, "
            "timeline, sources, prep, document. Kies op basis van de vraag. "
            "Een overzicht: overview, tasks, timeline. Een tijdlijn: timeline, "
            "sources. Overleg: prep, tasks, sources. Schrijven: document, sources. "
            "Geef nooit feiten, HTML, code, acties, opdrachten of aanvullende tekst."
        ),
        "prompt": prompt.strip(),
        "stream": False,
        "think": False,
        "format": {
            "type": "object",
            "properties": {"panels": {"type": "array", "items": {"type": "string", "enum": sorted(PANELS)}, "minItems": 1, "maxItems": 4}},
            "required": ["panels"],
            "additionalProperties": False,
        },
        "options": {"temperature": 0.1, "num_predict": 160},
    }
    result = _call_ollama("/api/generate", payload, timeout=40)
    text = result.get("response")
    if not isinstance(text, str) or len(text) > 3072:
        raise ValueError("Ongeldig JSON-antwoord van lokaal model")
    return validate_plan(json.loads(text))


def canvas_data(view: dict) -> dict:
    """Project source-backed demo items, never trust model-generated statuses."""
    items = [*view["open_tasks"], *view["proposed_tasks"], *view["other_objects"]]
    result = []
    for item in items:
        if item.get("kind") not in {"task", "commitment", "decision", "meeting"}:
            continue
        trace = item.get("trace") or []
        last = trace[-1] if trace else {}
        source = next((step.get("source", {}) for step in reversed(trace)
                       if step.get("source", {}).get("path")), {})
        recorded = last.get("recorded_at")
        try:
            shown = datetime.fromisoformat(recorded.replace("Z", "+00:00")).astimezone().strftime("%d %b %Y, %H:%M") if recorded else "Datum onbekend"
        except (ValueError, AttributeError):
            shown = "Datum onbekend"
        result.append({
            "id": str(item["id"])[:90],
            "title": str(item["title"])[:200],
            "kind": item["kind"],
            "status": str(item.get("status", "unknown"))[:40],
            "when": shown,
            "source": str(source.get("path", "geen bronlocatie"))[:240],
            "quote": str(source.get("quote", ""))[:550],
            "provenance_kind": "local_note" if last.get("source", {}).get("kind") == "unverified_local_operator_note" else "fixture",
        })
    return {"context": "Project Atlas · fictieve gegevens", "items": result, "events": [], "case_id": view["case_id"]}


def create_canvas_server(home: Path, model: str = DEFAULT_MODEL,
                         port: int = 0) -> ThreadingHTTPServer:
    if not isinstance(port, int) or not (0 <= port <= 65535):
        raise ValueError("Ongeldige poort")
    if not MODEL_NAME.fullmatch(model):
        raise ValueError("Ongeldige modelnaam")
    if not HTML_FILE.is_file() or not DEMO_SCENARIO.is_file():
        raise ValueError("De meegeleverde demo ontbreekt")
    store = CorrectionStore(home, DEMO_SCENARIO)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            pass

        def send(self, status: int, payload: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def send_json(self, status: int, data: dict) -> None:
            self.send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def is_local_request(self) -> bool:
            port_number = self.server.server_address[1]
            return self.headers.get("Host") in {f"127.0.0.1:{port_number}", f"localhost:{port_number}"}

        def do_GET(self) -> None:
            if not self.is_local_request():
                self.send_json(403, {"error": "Host niet toegestaan"})
                return
            path = urlsplit(self.path).path
            if path == "/":
                self.send(200, HTML_FILE.read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/status":
                self.send_json(200, {"api": API, "model": model, "model_ready": model_available(model), "local_only": True})
            elif path == "/api/data":
                try:
                    snapshot = store.view(datetime.now(timezone.utc).isoformat())
                    self.send_json(200, canvas_data(snapshot))
                except (ValueError, OSError) as exc:
                    self.send_json(409, {"error": "Fictieve casus niet beschikbaar: " + str(exc)[:150]})
            else:
                self.send_json(404, {"error": "Niet gevonden"})

        def do_POST(self) -> None:
            if not self.is_local_request():
                self.send_json(403, {"error": "Host niet toegestaan"})
                return
            if urlsplit(self.path).path != "/api/compose":
                self.send_json(404, {"error": "Niet gevonden"})
                return
            port_number = self.server.server_address[1]
            origin = self.headers.get("Origin")
            valid_origins = {f"http://127.0.0.1:{port_number}", f"http://localhost:{port_number}"}
            if origin and origin not in valid_origins:
                self.send_json(403, {"error": "Herkomst niet toegestaan"})
                return
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
                self.send_json(415, {"error": "Gebruik JSON"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 1 or size > 4096:
                    raise ValueError("Vraag te groot of leeg")
                data = json.loads(self.rfile.read(size).decode("utf-8"))
                if not isinstance(data, dict) or set(data) != {"prompt"}:
                    raise ValueError("Vraag bevat ongeldige velden")
                question = data["prompt"]
                if not model_available(model):
                    self.send_json(503, {"error": "Ollama of het gekozen model is niet beschikbaar"})
                    return
                self.send_json(200, plan_with_model(question, model))
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                self.send_json(400, {"error": str(exc)[:150]})
            except (TimeoutError, OSError, error.URLError) as exc:
                self.send_json(502, {"error": "Lokaal model gaf geen antwoord"})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def serve_canvas(home: Path, model: str = DEFAULT_MODEL, port: int = 8765) -> int:
    with create_canvas_server(home, model=model, port=port) as server:
        address = f"http://127.0.0.1:{server.server_address[1]}/"
        print("EAIhome · live canvas op", address, flush=True)
        print("Alleen fictieve data. Lokale LLM:", model, flush=True)
        print("Geen Ollama geïnstalleerd? Dan werkt de zichtbare demomodus.", flush=True)
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
    return 0