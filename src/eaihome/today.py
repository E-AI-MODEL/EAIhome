"""EAIhome Vandaag: een lokale, fictieve werkweergave.

Geen externe bronnen, authenticatie, automatische taakherkenning of publieke webserver.
De browser ziet uitsluitend data uit het vaste fictieve scenario en lokale correcties.
"""

from __future__ import annotations

import html
import secrets
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from .continuity import at
from .workstore import CorrectionStore

AMSTERDAM = ZoneInfo("Europe/Amsterdam")
PRESETS = (
    ("", "Nu"),
    ("2026-11-18T10:30:00+01:00", "18 november, ochtend"),
    ("2026-11-19T11:00:00+01:00", "19 november, na bevestiging"),
    ("2026-11-20T09:30:00+01:00", "20 november, na annulering"),
    ("2026-11-20T13:00:00+01:00", "20 november, na afronding"),
)
TASK_ACTIONS = {
    "proposed": (("task.accepted", "Aannemen"), ("task.dismissed", "Geen taak")),
    "accepted": (("task.completed", "Afronden"), ("task.dismissed", "Niet van toepassing")),
}
COMMITMENT_ACTIONS = {
    "reported": (("commitment.confirmed", "Toezegging bevestigen"),
                 ("commitment.cancelled", "Toezegging intrekken")),
    "confirmed": (("commitment.cancelled", "Toezegging intrekken"),),
}
STATUS_LABELS = {
    "proposed": "Voorgesteld", "accepted": "Aangenomen", "completed": "Afgerond",
    "dismissed": "Afgewezen", "reported": "Gerapporteerd",
    "confirmed": "Bevestigd", "cancelled": "Geannuleerd",
    "discussed": "Besproken", "scheduled": "Gepland",
}
KIND_LABELS = {"task": "Taak", "commitment": "Toezegging",
               "decision": "Besluit", "meeting": "Overleg"}

CSS = """
:root{color-scheme:light;--ink:#27302d;--muted:#65716c;--line:#d9ddd4;
--paper:#f8f8f3;--white:#fff;--accent:#385e4f;--accent-lite:#e8efe9;--warm:#9a6127}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
a{color:var(--accent);text-underline-offset:3px} a:hover{text-decoration-thickness:2px}
button,input,select{font:inherit} button{cursor:pointer}
button:focus-visible,summary:focus-visible,input:focus-visible,select:focus-visible,a:focus-visible{outline:3px solid #b77e35;outline-offset:3px}
.top{height:68px;background:var(--white);border-bottom:1px solid var(--line);display:flex;align-items:center;gap:14px;padding:0 max(24px,calc((100% - 1200px)/2))}
.brand{font-weight:760;letter-spacing:-.07em;font-size:27px;color:var(--accent)}
.top-note{font-size:13px;color:var(--muted);border-left:1px solid var(--line);padding-left:14px}
.shell{max-width:1200px;margin:auto;padding:42px 24px 90px}
.intro{display:flex;justify-content:space-between;align-items:start;gap:30px;margin-bottom:30px}
.eyebrow{font-size:12px;font-weight:740;letter-spacing:.11em;color:var(--accent);text-transform:uppercase}
h1{font-size:clamp(36px,5vw,55px);letter-spacing:-.045em;line-height:1.11;margin:7px 0 14px;font-weight:730}
.intro p{color:var(--muted);max-width:62ch;margin:0}
.time-select{display:flex;flex-direction:column;gap:5px;min-width:256px;font-size:13px;color:var(--muted)}
.time-select select,.time-select button{background:white;border:1px solid var(--line);border-radius:8px;padding:10px 12px;color:var(--ink)}
.time-select button{background:var(--accent);color:white;font-weight:600}
.notice{margin:0 0 24px;padding:14px 18px;border:1px solid #e3dfd4;border-left:3px solid var(--warm);background:#fffcf5;font-size:13px;color:#554d42}
.error{border-color:#b15739;background:#fff1e9;color:#702e20}
.workspace{display:grid;grid-template-columns:205px minmax(0,1fr);gap:45px;align-items:start}
aside{position:sticky;top:24px}
aside h2{font-size:13px;font-weight:740;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0 0 14px}
aside a{display:flex;justify-content:space-between;align-items:center;text-decoration:none;border-bottom:1px solid var(--line);padding:12px 2px;color:var(--ink);font-size:14px}
aside a:hover{color:var(--accent)}
aside .count{font-variant-numeric:tabular-nums;color:var(--muted)}
aside .footnote{font-size:12px;line-height:1.6;color:var(--muted);margin:28px 0 0}
.content{min-width:0}
.panel{scroll-margin-top:25px;margin:0 0 38px}
.panel-heading{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:12px;gap:15px}
h2{font-size:22px;font-weight:690;letter-spacing:-.025em;margin:0}
.panel-heading small{font-size:12px;color:var(--muted)}
.item{background:var(--white);border:1px solid var(--line);border-radius:10px;margin:0 0 10px;overflow:hidden}
.item-main{padding:19px 20px 16px}
.item-title{font-size:18px;font-weight:660;letter-spacing:-.015em;margin:0}
.item-top{display:flex;gap:16px;align-items:center;justify-content:space-between}
.pill{border-radius:100px;padding:4px 9px;background:#edf0eb;font-size:11px;font-weight:700;white-space:nowrap;letter-spacing:.02em}
.pill.open{background:var(--accent-lite);color:#205042}
.pill.proposed{background:#f9f0e2;color:#82521f}
.pill.closed{background:#ededed;color:#515751}
.kicker{margin:4px 0 0;color:var(--muted);font-size:13px}
.explain{margin:13px 0 0;font-size:13px;color:var(--muted)}
.item details{margin:0;border-top:1px solid var(--line)}
.item summary{padding:12px 20px;font-size:13px;font-weight:650;color:var(--accent);cursor:pointer;list-style-position:inside}
.item summary:hover{background:#f8faf6}
.proof{padding:3px 20px 16px;font-size:12px}
.proof-row{border-left:2px solid var(--line);padding:0 0 13px 14px;margin:0 0 8px;overflow-wrap:anywhere}
.proof-row strong{display:block;font-size:12px;font-weight:700}
.proof-row p{margin:4px 0;color:var(--muted)}
.proof-row code{font-size:11px}
.action-forms{padding:0 20px 20px;display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.action{display:flex;flex-direction:column;gap:8px;padding:12px;border-radius:7px;background:#f8f9f6;border:1px solid var(--line)}
.action label{font-size:12px;color:var(--muted);font-weight:600}
.action input[type=text]{width:100%;padding:9px;border:1px solid #cbd0c7;border-radius:6px;background:white;color:var(--ink)}
.action button{padding:9px 12px;border:none;border-radius:6px;background:var(--accent);color:white;font-weight:630;font-size:13px}
.action button.secondary{background:#edeeea;color:var(--ink);border:1px solid #cdd1c9}
.empty{background:#ffffffa6;border:1px dashed #c9d1ca;border-radius:9px;padding:17px 20px;font-size:14px;color:var(--muted)}
.screen-only{position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0,0,0,0)}
.bottom{border-top:1px solid var(--line);padding-top:18px;color:var(--muted);font-size:12px}
@media(max-width:760px){
.top{height:58px;padding:0 18px}.shell{padding:28px 16px 55px}
.intro{flex-direction:column;gap:20px}.time-select{width:100%}
.workspace{grid-template-columns:1fr;gap:24px}aside{position:static}
aside nav{display:flex;overflow-x:auto;gap:18px;border-bottom:1px solid var(--line)}
aside a{white-space:nowrap;border:none;padding:7px 0}aside a .count{margin-left:7px}
aside .footnote{margin:12px 0 0}h2{font-size:20px}
.item-main{padding:16px}.item summary{padding:12px 16px}
.proof{padding:3px 16px 16px}.action-forms{padding:0 16px 16px}
}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""


def h(value: object) -> str:
    return html.escape(str(value), quote=True)


def format_time(value: str) -> str:
    dt = at(value, "tijd")
    return dt.astimezone(AMSTERDAM).strftime("%d-%m-%Y %H:%M")


def _groups(view: dict) -> dict[str, list[dict]]:
    items = [
        *view["open_tasks"], *view["proposed_tasks"], *view["other_objects"]
    ]
    def ordered(matches: list[dict]) -> list[dict]:
        return sorted(matches, key=lambda x: (x["title"].casefold(), x["id"]))
    return {
        "open": ordered([x for x in items if x["kind"] == "task" and x["status"] == "accepted"]),
        "proposals": ordered([x for x in items if x["kind"] == "task" and x["status"] == "proposed"]),
        "processed": ordered([x for x in items if x["kind"] == "task" and x["status"] in {"completed", "dismissed"}]),
        "signals": ordered([x for x in items if x["kind"] != "task"]),
    }


def _proof(item: dict) -> str:
    trace = list(reversed(item["trace"]))
    if not trace:
        return "<p>Er zijn geen toegestane gebeurtenissen voor dit tijdstip gevonden.</p>"
    rows = []
    for event in trace:
        source = event.get("source", {})
        label = event.get("kind", "Onbekende gebeurtenis")
        who = event.get("actor_kind", "?")
        moment = format_time(event["recorded_at"])
        date_text = f"Geregistreerd op {moment}; vanaf {format_time(event['effective_at'])}."
        if source.get("kind") == "unverified_local_operator_note":
            ref = ("Lokale toelichting (identiteit niet gecontroleerd): "
                   + h(source.get("reason", "")))
        else:
            ref = ("Bron: <code>" + h(source.get("path", "?")) + "</code><p>"
                   + h(source.get("quote", "")) + "</p>"
                   + "<small>SHA-256: " + h(source.get("sha256", "?"))[:20] + "…</small>")
        rows.append(
            '<div class="proof-row"><strong>' + h(label) + " · " + h(who)
            + '</strong><p>' + h(date_text) + "</p><div>" + ref + "</div></div>"
        )
    return "".join(rows)


def _forms(item: dict, token: str) -> str:
    actions = TASK_ACTIONS.get(item["status"], ()) if item["kind"] == "task" else (
        COMMITMENT_ACTIONS.get(item["status"], ()) if item["kind"] == "commitment" else ()
    )
    if not actions:
        return ""
    revision = len(item["trace"])
    forms = []
    for event, title in actions:
        key = secrets.token_hex(16)
        secondary = ' class="secondary"' if event.endswith(("dismissed", "cancelled")) else ""
        forms.append(
            '<form class="action" method="post" action="/correct">'
            '<input type="hidden" name="token" value="' + h(token) + '">'
            '<input type="hidden" name="subject_id" value="' + h(item["id"]) + '">'
            '<input type="hidden" name="event_kind" value="' + h(event) + '">'
            '<input type="hidden" name="expected_revision" value="' + h(revision) + '">'
            '<input type="hidden" name="request_id" value="' + h(key) + '">'
            '<label>Toelichting voor: ' + h(title) + '</label>'
            '<input type="text" name="reason" required minlength="5" maxlength="500"'
            ' placeholder="Waarom pas je dit aan?" aria-label="Reden voor ' + h(title) + '">'
            '<button type="submit"' + secondary + '>' + h(title) + '</button></form>'
        )
    return ('<details class="correction"><summary>Status aanpassen'
            ' (alleen fictieve gegevens)</summary><div class="action-forms">'
            + "".join(forms) + "</div></details>")


def _item(item: dict, token: str, editable: bool) -> str:
    status = item["status"]
    klass = "open" if status == "accepted" else (
        "proposed" if status in {"proposed", "reported"} else "closed"
    )
    trace = item["trace"]
    latest = trace[-1] if trace else None
    explain = (
        "Laatst geregistreerd: " + format_time(latest["recorded_at"]) +
        ". " + KIND_LABELS.get(item["kind"], "Onderwerp") +
        " met " + str(len(trace)) + " brongebonden gebeurtenis(sen)."
    ) if latest else "Geen gebeurtenis voor deze datum."
    return (
        '<article class="item" id="' + h(item["id"]) + '">'
        '<div class="item-main"><div class="item-top"><h3 class="item-title">'
        + h(item["title"]) + '</h3><span class="pill ' + klass + '">'
        + h(STATUS_LABELS.get(status, status)) + '</span></div>'
        '<p class="kicker">' + h(KIND_LABELS.get(item["kind"], "Onderwerp"))
        + " · versie " + h(len(trace)) + '</p>'
        '<p class="explain">' + h(explain) + '</p></div>'
        '<details class="provenance"><summary>Bekijk bronnen en voorgeschiedenis'
        '</summary><div class="proof">' + _proof(item) + "</div></details>"
        + (_forms(item, token) if editable else "")
        + "</article>"
    )


def render_today(view: dict, token: str = "", *, editable: bool = False,
                 historical: str = "", message: str = "") -> str:
    """Render a complete, self-contained HTML page. No scripts, external assets or fetch."""
    sections = _groups(view)
    headings = (
        ("open", "Openstaand", "Alleen expliciet aangenomen taken."),
        ("proposals", "Nog te beoordelen", "Gevonden voorstellen zijn geen opdrachten."),
        ("processed", "Afgerond of afgewezen", "Menselijke correcties blijven terug te vinden."),
        ("signals", "Andere ontwikkelingen", "Toezeggingen en besluiten apart van taken."),
    )
    nav = "".join(
        '<a href="#' + k + '">' + h(title)
        + ' <span class="count">' + str(len(sections[k])) + "</span></a>"
        for k, title, _ in headings
    )
    current = h(format_time(view["known_at"]))
    options = "".join(
        '<option value="' + h(value) + '"' + (' selected' if historical == value else '') +
        ">" + h(label) + "</option>"
        for value, label in PRESETS
    )
    cards = []
    for key, title, description in headings:
        content = "".join(_item(item, token, editable) for item in sections[key])
        if not content:
            empty_notes = {
                "open": "Geen aangenomen open taken in deze fictieve registratie.",
                "proposals": "Geen voorgestelde taken in deze fictieve registratie.",
                "processed": "Nog geen afgeronde of afgewezen taken geregistreerd.",
                "signals": "Geen aanvullende ontwikkelingen in deze fictieve registratie.",
            }
            content = '<div class="empty">' + h(empty_notes[key]) + (
                " Dit zegt niets over je echte werk.</div>"
            )
        cards.append(
            '<section class="panel" id="' + key + '"><div class="panel-heading"><h2>'
            + h(title) + '</h2><small>' + h(description) + "</small></div>"
            + content + "</section>"
        )
    warning = (
        '<div role="alert" class="notice error">' + h(message) + "</div>"
        if message else ""
    )
    title = "EAIhome | Vandaag (fictieve proef)"
    return (
        '<!doctype html><html lang="nl"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>' + h(title) + '</title><style>' + CSS + '</style></head><body>'
        '<header class="top"><span class="brand">EAIhome</span>'
        '<span class="top-note">Lokale werkproef · fictieve gegevens</span></header>'
        '<div class="shell"><section class="intro"><div>'
        '<div class="eyebrow">Vandaag / Werkoverzicht</div>'
        '<h1>Waar waren we gebleven?</h1>'
        '<p>Bekijk voorgestelde en aangenomen taken, correcties en hun herkomst.'
        ' Dit overzicht is uitsluitend gebaseerd op de meegeleverde fictieve casus.</p>'
        '</div><form method="get" class="time-select"><label for="moment">Stand bekijken</label>'
        '<select name="at" id="moment">' + options + '</select>'
        '<button type="submit">Toon stand</button></form></section>'
        + warning +
        '<div class="notice">Testomgeving · geen koppeling met mail, agenda of echte personen. '
        + ('Historische weergave. Correcties maak je via <a href="/">Nu</a>.'
           if historical else
           'Correcties in dit lokale venster zijn niet door een identiteit gecontroleerd.')
        + ' Geregistreerde stand: <strong>' + current + '</strong>.'
        '</div><div class="workspace"><aside aria-label="Secties">'
        '<h2>Onderwerpen</h2><nav>' + nav + '</nav>'
        '<p class="footnote">Bronverwijzingen tonen waar informatie staat, '
        'niet of de conclusie inhoudelijk bewezen is. '
        'Een mogelijk werkpunt is pas open na bevestiging.</p>'
        '</aside><main class="content">' + "".join(cards)
        + '<footer class="bottom">EAIhome demo · geen echte autorisatie · geen externe acties.'
        ' De broninhoud blijft ongewijzigd.</footer></main></div></div></body></html>'
    )


def create_server(store: CorrectionStore, port: int = 0) -> ThreadingHTTPServer:
    """Create a server bound only to loopback, with same-origin POST and CSRF guard."""
    if not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("Poort moet tussen 0 en 65535 liggen")
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass

        def send_body(self, code: int, body: str, content_type: str = "text/html; charset=utf-8",
                      location: str = "") -> None:
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; script-src 'none'; "
                "form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
            )
            if location:
                self.send_header("Location", location)
            self.end_headers()
            self.wfile.write(data)

        def guarded(self) -> bool:
            port_number = self.server.server_address[1]
            hosts = {f"127.0.0.1:{port_number}", f"localhost:{port_number}"}
            if self.headers.get("Host") not in hosts:
                self.send_body(403, "<h1>Host niet toegestaan</h1>")
                return False
            return True

        def do_GET(self) -> None:
            if not self.guarded():
                return
            parsed = urlsplit(self.path)
            if parsed.path != "/" or len(self.path) > 250:
                self.send_body(404, "<h1>Niet gevonden</h1>")
                return
            try:
                params = parse_qs(parsed.query, max_num_fields=3)
                historical = params.get("at", [""])[0]
                if historical:
                    at(historical, "at")
                current = historical or datetime.now(timezone.utc).isoformat()
                view = store.view(current)
                self.send_body(200, render_today(view, token, editable=not bool(historical),
                                                  historical=historical))
            except (ValueError, OSError):
                self.send_body(400, "<h1>De gevraagde stand kan niet worden geopend.</h1>")

        def do_POST(self) -> None:
            if not self.guarded():
                return
            if urlsplit(self.path).path != "/correct":
                self.send_body(404, "<h1>Niet gevonden</h1>")
                return
            port_number = self.server.server_address[1]
            allowed = {f"http://127.0.0.1:{port_number}", f"http://localhost:{port_number}"}
            origin = self.headers.get("Origin")
            if origin and origin not in allowed:
                self.send_body(403, "<h1>Herkomst geweigerd</h1>")
                return
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/x-www-form-urlencoded":
                self.send_body(415, "<h1>Ongeldig formulier</h1>")
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 4096:
                    raise ValueError("Formulier is te groot of leeg")
                form = parse_qs(self.rfile.read(size).decode("utf-8"), max_num_fields=12,
                                keep_blank_values=True, strict_parsing=True)
                allowed_fields = {"token", "subject_id", "event_kind", "expected_revision",
                                  "request_id", "reason"}
                if set(form) != allowed_fields or any(len(v) != 1 for v in form.values()):
                    raise ValueError("Formulier is onvolledig")
                values = {k: v[0] for k, v in form.items()}
                if not secrets.compare_digest(values["token"], token):
                    self.send_body(403, "<h1>Ongeldige sessie</h1>")
                    return
                store.append(
                    request_id=values["request_id"], subject_id=values["subject_id"],
                    event_kind=values["event_kind"], actor_ref="local-demo-operator",
                    reason=values["reason"], expected_revision=int(values["expected_revision"]),
                )
                self.send_body(303, "", location="/#" + h(values["subject_id"]))
            except (ValueError, OSError) as exc:
                # No full trace or storage internals disclosed to the browser.
                view = store.view(datetime.now(timezone.utc).isoformat())
                self.send_body(409, render_today(view, token, editable=True,
                                                  message="Wijziging geweigerd: " + str(exc)))

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def serve_today(home: Path, scenario_path: Path, port: int = 8765) -> int:
    store = CorrectionStore(home, scenario_path)
    with create_server(store, port) as server:
        url = f"http://127.0.0.1:{server.server_address[1]}/"
        print(f"EAIhome fictieve Vandaag-proef: {url}", flush=True)
        print("Stoppen: Ctrl+C. Alleen lokale testgegevens; geen echte dossiers.", flush=True)
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
    return 0
