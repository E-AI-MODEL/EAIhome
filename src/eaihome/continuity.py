"""Fictieve werkcontinuiteit: getypeerde gebeurtenissen, twee tijdassen, bronankers.

Geen AI-inferentie, echte identiteit, autorisatie, persistentie of externe acties.
Brontekst is uitsluitend gegevens en kan geen overgang of bevoegdheid afdwingen.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "eaihome.work-demo.v1"
KINDS = {"task", "commitment", "decision", "meeting"}
ACTORS = {"person", "model", "system", "connector"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")

# (objecttype, toegestane oude status, nieuwe status of None, toegestane bronactoren)
# Een model kan een voorstel registreren, niet namens een persoon afhandelen.
TRANSITIONS: dict[str, tuple[str, set[str | None], str | None, set[str]]] = {
    "task.proposed": ("task", {None}, "proposed", {"model", "system", "person"}),
    "task.noted": ("task", {"proposed", "accepted", "completed"}, None, ACTORS),
    "task.accepted": ("task", {"proposed"}, "accepted", {"person"}),
    "task.completed": ("task", {"accepted"}, "completed", {"person"}),
    "task.dismissed": ("task", {"proposed", "accepted"}, "dismissed", {"person"}),
    "commitment.reported": ("commitment", {None}, "reported", {"model", "system", "person"}),
    "commitment.confirmed": ("commitment", {"reported"}, "confirmed", {"person"}),
    "commitment.cancelled": ("commitment", {"reported", "confirmed"}, "cancelled", {"person"}),
    "decision.proposed": ("decision", {None}, "proposed", {"model", "person"}),
    "decision.discussed": ("decision", {"proposed"}, "discussed", {"person"}),
    # 'decided' is intentionally excluded: no authenticated decision authority here.
    "meeting.scheduled": ("meeting", {None}, "scheduled", {"person", "connector"}),
    "meeting.cancelled": ("meeting", {"scheduled"}, "cancelled", {"person", "connector"}),
}


def at(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field}: verplichte tijd met tijdzone")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field}: ongeldige ISO-8601-tijd") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{field}: tijdzone ontbreekt")
    return dt.astimezone(timezone.utc)


def _string(obj: dict, field: str) -> str:
    value = obj.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}: verplichte tekst")
    return value


def _source(event: dict, root: Path) -> dict:
    """Een SHA-256 en letterlijk citaat binden de demo-annotatie aan een fixture.

    Dit controleert de vindplaats, niet de betekenis van de annotatie.
    """
    ref = _string(event, "source_ref")
    if not ref.startswith("fixtures/"):
        raise ValueError("Bronnen in deze proef moeten onder fixtures/ staan")
    fixtures = (root / "fixtures").resolve()
    file_path = (root / ref).resolve()
    try:
        file_path.relative_to(fixtures)
    except ValueError as exc:
        raise ValueError("Bronpad verlaat fixtures/") from exc
    if not file_path.is_file() or file_path.stat().st_size > 1024 * 1024:
        raise ValueError(f"Bron ontbreekt of is te groot: {ref}")
    raw = file_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    expected = _string(event, "source_sha256")
    if not SHA256.fullmatch(expected) or digest != expected:
        raise ValueError(f"Bronhash klopt niet: {ref}")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Alleen UTF-8 tekstfixtures zijn toegestaan") from exc
    quote = _string(event, "source_quote")
    if quote not in content:
        raise ValueError(f"Exact broncitaat ontbreekt: {ref}")
    start = content.index(quote)
    return {"path": ref, "sha256": digest, "quote": quote,
            "locator_kind": "utf8_text", "start": start, "end": start + len(quote)}


def load_scenario(path: Path, root: Path) -> dict:
    """Controleer alle gebeurtenissen en bronnen voor er een status wordt berekend."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError("Onbekende scenarioversie")
    context = _string(data, "context_id")
    _string(data, "case_id")
    subjects: dict[str, dict] = {}
    for sub in data.get("subjects", []):
        sid = _string(sub, "id")
        if sid in subjects or sub.get("kind") not in KINDS:
            raise ValueError(f"Dubbel of onbekend werkobject: {sid}")
        if sub.get("context_id") != context:
            raise ValueError("Werkobject ligt buiten de context")
        _string(sub, "title")
        subjects[sid] = sub
    if not subjects:
        raise ValueError("Geen werkobjecten")
    unique: dict[str, str] = {}
    validated = []
    for raw in data.get("events", []):
        eid = _string(raw, "id")
        sid = _string(raw, "subject_id")
        kind = _string(raw, "event_kind")
        actor = _string(raw, "actor_kind")
        _string(raw, "actor_ref")
        if raw.get("context_id") != context or sid not in subjects:
            raise ValueError(f"Gebeurtenis buiten de context: {eid}")
        if kind not in TRANSITIONS:
            raise ValueError(f"Onbekende gebeurtenis: {kind}")
        subject_kind, _, _, allowed_actors = TRANSITIONS[kind]
        if subjects[sid]["kind"] != subject_kind or actor not in allowed_actors:
            raise ValueError(f"Ongeoorloofde overgang of actor: {eid}")
        recorded = at(raw.get("recorded_at"), "recorded_at")
        effective = at(raw.get("effective_at"), "effective_at")
        anchor = _source(raw, root)
        fingerprint = json.dumps(raw, sort_keys=True, ensure_ascii=False)
        if eid in unique:
            if unique[eid] != fingerprint:
                raise ValueError(f"Eenzelfde event-ID bevat strijdige gegevens: {eid}")
            continue  # Exacte herhaling van dezelfde waarneming telt niet dubbel.
        unique[eid] = fingerprint
        validated.append({**raw, "_recorded": recorded, "_effective": effective, "_anchor": anchor})
    return {"schema": SCHEMA, "context_id": context, "case_id": data["case_id"],
            "subjects": subjects, "events": validated}


def work_status(scenario: dict, known_at: str, effective_at: str | None = None) -> dict[str, Any]:
    """Historisch beeld: wat was geregistreerd, en wat gold volgens die gegevens?"""
    known = at(known_at, "known_at")
    effective = at(effective_at or known_at, "effective_at")
    state = {sid: {"id": sid, "kind": sub["kind"], "title": sub["title"],
                   "status": "unknown", "trace": []}
             for sid, sub in scenario["subjects"].items()}
    events = sorted(scenario["events"], key=lambda e: (e["_effective"], e["_recorded"], e["id"]))
    for event in events:
        if event["_recorded"] > known or event["_effective"] > effective:
            continue
        object_type, old_states, next_state, _actors = TRANSITIONS[event["event_kind"]]
        target = state[event["subject_id"]]
        before = None if target["status"] == "unknown" else target["status"]
        if target["kind"] != object_type or before not in old_states:
            raise ValueError(f"Ongeldige statusovergang: {event['id']} ({before})")
        if next_state is not None:
            target["status"] = next_state
        target["trace"].append({
            "event_id": event["id"], "kind": event["event_kind"],
            "actor_kind": event["actor_kind"], "recorded_at": event["recorded_at"],
            "effective_at": event["effective_at"], "source": event["_anchor"],
        })
    items = list(state.values())
    return {
        "case_id": scenario["case_id"], "context_id": scenario["context_id"],
        "known_at": known_at, "effective_at": effective_at or known_at,
        "open_tasks": [x for x in items if x["kind"] == "task" and x["status"] == "accepted"],
        "proposed_tasks": [x for x in items if x["kind"] == "task" and x["status"] == "proposed"],
        "other_objects": [x for x in items if x["kind"] != "task" or x["status"] not in {"accepted", "proposed"}],
        "note": "Fictief en handmatig geannoteerd. Tekstanker is geen inhoudelijk bewijs; actoren zijn niet geauthenticeerd.",
    }
